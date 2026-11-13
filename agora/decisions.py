"""Durable decisions: one receipt for action, memory and call attribution."""

from __future__ import annotations

import copy
import hashlib
import json

from agora.memory import AgentMemory


def _dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class DecisionJournal:
    def __init__(self, world):
        self.world = world

    def begin(self, session, decision_id):
        row = self.world.db.execute(
            "SELECT session_id, user_id FROM agent_decision WHERE decision_id = ?",
            (decision_id,),
        ).fetchone()
        if row:
            if row != (session.session_id, session.user_id):
                raise PermissionError("Decision belongs to another session")
            return
        with self.world.atomic():
            self.world.db.execute(
                "INSERT INTO agent_decision(decision_id,session_id,user_id,tick,status,before_json) VALUES (?, ?, ?, ?, 'pending', ?)",
                (
                    decision_id,
                    session.session_id,
                    session.user_id,
                    self.world.current_tick,
                    _dump(session.observe()),
                ),
            )

    def response(self, session, decision_id, action, records=()):
        self.begin(session, decision_id)
        raw = _dump(action)
        fingerprint = hashlib.sha256(raw.encode()).hexdigest()
        row = self.world.db.execute(
            "SELECT request_hash, status FROM agent_decision WHERE decision_id = ?",
            (decision_id,),
        ).fetchone()
        if row[0] is not None and row[0] != fingerprint:
            raise ValueError("Idempotency key was already used for a different action")
        if row[1] in {"succeeded", "failed"}:
            return
        with self.world.atomic():
            self.world.db.execute(
                "UPDATE agent_decision SET status='ready', action_json=?, request_hash=?, model_records_json=? WHERE decision_id=?",
                (raw, fingerprint, _dump(list(records)), decision_id),
            )

    def receipt(self, decision_id):
        row = self.world.db.execute(
            "SELECT status, result_json, after_json, step, failure_type FROM agent_decision WHERE decision_id = ?",
            (decision_id,),
        ).fetchone()
        if not row or row[0] not in {"succeeded", "failed"}:
            return None
        return {
            "decision_id": decision_id,
            "status": row[0],
            "result": json.loads(row[1]),
            "observation": json.loads(row[2]),
            "step": row[3],
            "failure_type": row[4],
        }

    def _calls(self, session, decision_id, records):
        for ordinal, record in enumerate(records):
            self.world.db.execute(
                "INSERT OR IGNORE INTO agent_model_call(session_id,step,tick,status,model_id,input_tokens,output_tokens,elapsed_ms,error_type,request_id,decision_id,ordinal) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session.session_id,
                    session.state["step"],
                    self.world.current_tick,
                    record["status"],
                    record.get("model_id"),
                    record.get("input_tokens"),
                    record.get("output_tokens"),
                    record.get("elapsed_ms"),
                    record.get("error_type"),
                    record.get("request_id"),
                    decision_id,
                    ordinal,
                ),
            )

    def fail(
        self,
        session,
        decision_id,
        error,
        records=(),
        action=None,
        failure_type="policy",
    ):
        self.begin(session, decision_id)
        cached = self.receipt(decision_id)
        if cached:
            return cached
        result = {
            "success": False,
            "error_type": type(error).__name__,
            "failure_type": failure_type,
            "error": str(error)
            if failure_type == "action"
            else "Decision could not complete",
        }
        with self.world.atomic():
            session._event(
                {
                    "action_type": "policy_failure"
                    if failure_type == "policy"
                    else "decision_failure",
                    "arguments": {},
                    "requested_action": action,
                },
                result,
            )
            after = session.observe()
            self.world.db.execute(
                "UPDATE agent_decision SET status='failed',result_json=?,after_json=?,step=?,failure_type=? WHERE decision_id=?",
                (
                    _dump(result),
                    _dump(after),
                    session.state["step"],
                    failure_type,
                    decision_id,
                ),
            )
            self._calls(session, decision_id, records)
        return self.receipt(decision_id)

    async def execute(
        self, session, decision_id, action, records=(), advance_clock=False
    ):
        self.response(session, decision_id, action, records)
        cached = self.receipt(decision_id)
        if cached:
            return cached
        row = self.world.db.execute(
            "SELECT before_json, model_records_json FROM agent_decision WHERE decision_id=?",
            (decision_id,),
        ).fetchone()
        before = json.loads(row[0])
        records = json.loads(row[1])
        previous_state = copy.deepcopy(session.state)
        phase = "action"
        try:
            with self.world.atomic():
                result = await session.act(
                    action["action_type"],
                    action.get("arguments", {}),
                    action.get("rationale"),
                )
                if advance_clock:
                    self.world.set_time(
                        self.world.current_time_ms
                        + max(
                            0,
                            session.state["elapsed_ms"] - previous_state["elapsed_ms"],
                        )
                    )
                after = session.observe()
                if advance_clock:
                    self.world.db.execute(
                        "UPDATE agora_session_event SET observation_json=? WHERE session_id=? AND step=?",
                        (_dump(after), session.session_id, session.state["step"]),
                    )
                phase = "infrastructure"
                AgentMemory(self.world).remember(
                    session.user_id,
                    session.session_id,
                    action,
                    result,
                    observation=before,
                    after_observation=after,
                )
                self.world.db.execute(
                    "UPDATE agent_decision SET status='succeeded',result_json=?,after_json=?,step=? WHERE decision_id=?",
                    (_dump(result), _dump(after), session.state["step"], decision_id),
                )
                self._calls(session, decision_id, records)
        except Exception as error:  # noqa: BLE001 - rollback the complete decision, then write its failure receipt
            session.state = previous_state
            return self.fail(session, decision_id, error, records, action, phase)
        return self.receipt(decision_id)
