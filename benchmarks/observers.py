from __future__ import annotations

from benchmarks.state import ObserverJudgment, StateDelta
import json
from benchmarks.adapters import JsonModelCandidate


class JsonModelObserver:
    """Provider-neutral observer with bounded structured social-state output."""

    def __init__(self, observer_id, observer_version, client,
                 parse_failure_mode="raise", supports_vision=False):
        if parse_failure_mode not in {"raise", "neutral"}:
            raise ValueError("parse_failure_mode must be raise or neutral")
        self.observer_id = observer_id
        self.observer_version = observer_version
        self.client = client
        self.parse_failure_mode = parse_failure_mode
        self.supports_multimodal_context = supports_vision
        self._records = []

    async def judge(self, action, outcome, context):
        user_payload = json.dumps({
            "action": {"action_type": action.action_type,
                       "arguments": action.arguments},
            "outcome": outcome,
            "is_direct_target": context.get("is_direct_target", True),
        }, ensure_ascii=False)
        multimodal_parts = context.get("multimodal_parts", [])
        user_content = ([{"type": "text", "text": user_payload},
                         *multimodal_parts]
                        if multimodal_parts else user_payload)
        response = await self.client.complete([{
            "role": "system",
            "content": (
                "Judge the target user's immediate reaction to one social "
                "action. Output exactly one compact JSON object, no markdown: "
                '{"attitude":0,"arousal":0,"trust":0,'
                '"engagement_intent":0,"confidence":0,"evidence":"..."}. '
                "The first four values must be numbers in [-1,1], confidence "
                "in [0,1], and evidence one short sentence grounded only in "
                "the supplied action/outcome."),
        }, {
            "role": "user",
            "content": user_content,
        }])
        record = {
            "model_id": response.model_id,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "provider_request_id": response.provider_request_id,
            "status": "completed",
            "error_type": None,
            "raw_output": response.text,
        }
        try:
            value = JsonModelCandidate._parse_json_object(response.text)
        except Exception as error:
            record["status"] = "parse_failed"
            record["error_type"] = type(error).__name__
            self._records.append(record)
            if self.parse_failure_mode == "raise":
                raise
            value = {
                "attitude": 0, "arousal": 0, "trust": 0,
                "engagement_intent": 0, "confidence": 0,
                "evidence": "Observer output was invalid; neutral fallback.",
            }
        else:
            self._records.append(record)
        return (ObserverJudgment(
            self.observer_id, self.observer_version,
            context["target_actor_id"],
            StateDelta(
                attitude=float(value["attitude"]),
                arousal=float(value["arousal"]),
                trust=float(value["trust"]),
                engagement_intent=float(value["engagement_intent"])),
            float(value["confidence"]), str(value["evidence"]),
            effect_scope=("direct" if context.get("is_direct_target", True)
                          else "bystander")),)

    def drain_call_records(self):
        records = list(self._records)
        self._records.clear()
        return records


class ObserverPool:
    """Aggregates versioned observers without exposing individual bias as truth."""

    def __init__(self, pool_version, observers):
        if not observers:
            raise ValueError("Observer pool cannot be empty")
        identities = [(item.observer_id, item.observer_version)
                      for item in observers]
        if len(identities) != len(set(identities)):
            raise ValueError("Observer identities must be unique")
        self.observer_id = "observer-pool"
        self.observer_version = pool_version
        self.observers = tuple(observers)
        self.supports_multimodal_context = any(
            getattr(item, "supports_multimodal_context", False)
            for item in self.observers)

    async def judge(self, action, outcome, context):
        raw = []
        for observer in self.observers:
            raw.extend(await observer.judge(action, outcome, context))
        grouped = {}
        for item in raw:
            grouped.setdefault(item.target_actor_id, []).append(item)
        aggregated = []
        for target, items in grouped.items():
            count = len(items)
            aggregated.append(ObserverJudgment(
                self.observer_id, self.observer_version, target,
                StateDelta(
                    attitude=sum(item.delta.attitude for item in items) / count,
                    arousal=sum(item.delta.arousal for item in items) / count,
                    trust=sum(item.delta.trust for item in items) / count,
                    engagement_intent=sum(
                        item.delta.engagement_intent for item in items) / count),
                sum(item.confidence for item in items) / count,
                " | ".join(f"{item.observer_id}: {item.evidence}"
                           for item in items),
                delay_ticks=max(item.delay_ticks for item in items),
                effect_scope=items[0].effect_scope))
        return tuple(aggregated)

    def drain_call_records(self):
        records = []
        for observer in self.observers:
            if hasattr(observer, "drain_call_records"):
                records.extend({"observer_id": observer.observer_id, **item}
                               for item in observer.drain_call_records())
        return records


class ScriptedDevelopmentObserver:
    """Deterministic development observer; never use it for published scores."""

    observer_id = "scripted-development"
    observer_version = "1"

    async def judge(self, action, outcome, context):
        target = context["target_actor_id"]
        is_direct = context.get("is_direct_target", True)
        if action.action_type == "do_nothing":
            delta = StateDelta(engagement_intent=-0.05, arousal=-0.05)
            evidence = "The candidate did not engage."
        else:
            content = str(action.arguments.get("content", ""))
            deescalation = any(token in content for token in
                               ("谢谢", "理解", "确认", "愿意", "抱歉"))
            delta = (StateDelta(attitude=0.15, arousal=-0.2, trust=0.1,
                                engagement_intent=0.1)
                     if deescalation else
                     StateDelta(attitude=-0.05, arousal=0.1, trust=-0.05))
            evidence = ("Matched development de-escalation signals."
                        if deescalation else
                        "No development de-escalation signal matched.")
        if not is_direct:
            delta = StateDelta(
                attitude=delta.attitude * 0.35,
                arousal=delta.arousal * 0.35,
                trust=delta.trust * 0.35,
                engagement_intent=delta.engagement_intent * 0.35)
        return (ObserverJudgment(
            self.observer_id, self.observer_version, target, delta, 1.0,
            evidence, delay_ticks=0 if is_direct else 1,
            effect_scope="direct" if is_direct else "bystander"),)


class ConfiguredScriptedObserver(ScriptedDevelopmentObserver):
    def __init__(self, observer_id, observer_version):
        self.observer_id = observer_id
        self.observer_version = observer_version
