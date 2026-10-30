from __future__ import annotations

from benchmarks.state import ObserverJudgment, StateDelta
import json
import math
from benchmarks.adapters import JsonModelCandidate


class JsonModelObserver:
    """Provider-neutral observer with bounded structured social-state output."""

    def __init__(self, observer_id, observer_version, client,
                 parse_failure_mode="raise", supports_vision=False,
                 expected_model_id=None):
        if parse_failure_mode not in {"raise", "neutral"}:
            raise ValueError("parse_failure_mode must be raise or neutral")
        self.observer_id = observer_id
        self.observer_version = observer_version
        self.client = client
        self.expected_model_id = expected_model_id
        self.parse_failure_mode = parse_failure_mode
        self.supports_multimodal_context = supports_vision
        self._records = []

    async def judge(self, action, outcome, context):
        user_payload = json.dumps({
            "action": {"action_type": action.action_type,
                       "arguments": action.arguments},
            "outcome": outcome,
            "is_direct_target": context.get("is_direct_target", True),
            "target_actor_id": context.get("target_actor_id"),
            "persona": context.get("persona", {}),
            "culture": context.get("culture", {}),
            "relationship_before": context.get("relationship_before", {}),
            "history": context.get("history", []),
            "original_post": context.get("original_post"),
            "observed_reaction": context.get("observed_reaction", {}),
        }, ensure_ascii=False)
        multimodal_parts = context.get("multimodal_parts", [])
        user_content = ([{"type": "text", "text": user_payload},
                         *multimodal_parts]
                        if multimodal_parts else user_payload)
        try:
            response = await self.client.complete([{
                "role": "system",
                "content": (
                    "Judge the target user's immediate reaction to one social "
                    "action. Output exactly one compact JSON object, no markdown: "
                    '{"attitude":0,"arousal":0,"trust":0,'
                    '"engagement_intent":0,"confidence":0,"evidence":"..."}. '
                    "The first four values must be numbers in [-1,1], confidence "
                    "in [0,1], and evidence one short sentence grounded only in "
                    "the supplied context and observed public response. Respect the "
                    "target person's culture and history; do not treat polite words "
                    "alone as trust or assume unobserved effects."),
            }, {
                "role": "user",
                "content": user_content,
            }])
        except Exception as error:
            self._records.append({"status": "request_failed", "model_id": None,
                                  "input_tokens": None, "output_tokens": None,
                                  "error_type": type(error).__name__})
            raise
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
            if self.expected_model_id is not None and response.model_id != self.expected_model_id:
                raise ValueError("Observer provider returned a different model")
            value = JsonModelCandidate._parse_json_object(response.text)
            judgment = self._judgment(value, context)
        except Exception as error:
            record["status"] = "parse_failed"
            record["error_type"] = type(error).__name__
            self._records.append(record)
            if self.parse_failure_mode == "raise":
                raise
            judgment = self._judgment({
                "attitude": 0, "arousal": 0, "trust": 0,
                "engagement_intent": 0, "confidence": 0,
                "evidence": "Observer output was invalid; neutral fallback.",
            }, context)
        else:
            self._records.append(record)
        return (judgment,)

    def _judgment(self, value, context):
        return ObserverJudgment(
            self.observer_id, self.observer_version, context["target_actor_id"],
            StateDelta(**{name: float(value[name]) for name in (
                "attitude", "arousal", "trust", "engagement_intent")}),
            float(value["confidence"]), str(value["evidence"]),
            effect_scope="direct" if context.get("is_direct_target", True) else "bystander")

    def drain_call_records(self):
        records = list(self._records)
        self._records.clear()
        return records


class ObserverPool:
    """Aggregates versioned observers without exposing individual bias as truth."""

    def __init__(self, pool_version, observers, weights=None):
        if not observers:
            raise ValueError("Observer pool cannot be empty")
        identities = [(item.observer_id, item.observer_version)
                      for item in observers]
        if len(identities) != len(set(identities)):
            raise ValueError("Observer identities must be unique")
        self.observer_id = "observer-pool"
        self.observer_version = pool_version
        self.observers = tuple(observers)
        weights = [1.0] * len(observers) if weights is None else weights
        if len(weights) != len(observers) or any(
                not isinstance(weight, (int, float)) or isinstance(weight, bool)
                or not math.isfinite(weight) or weight <= 0 for weight in weights):
            raise ValueError("Observer weights must be finite positive numbers")
        self.weights = dict(zip(identities, weights))
        self.supports_multimodal_context = any(
            getattr(item, "supports_multimodal_context", False)
            for item in self.observers)

    async def judge(self, action, outcome, context):
        raw = []
        for observer in self.observers:
            member_context = dict(context)
            if not getattr(observer, "supports_multimodal_context", False):
                member_context.pop("multimodal_parts", None)
            raw.extend(await observer.judge(action, outcome, member_context))
        grouped = {}
        for item in raw:
            grouped.setdefault(item.target_actor_id, []).append(item)
        aggregated = []
        for target, items in grouped.items():
            def weight(item):
                return self.weights[(item.observer_id, item.observer_version)]
            total_weight = sum(weight(item) for item in items)
            confidence_sum = sum(item.confidence * weight(item) for item in items)
            def weighted(name):
                return (sum(getattr(item.delta, name) * item.confidence * weight(item) for item in items)
                        / confidence_sum if confidence_sum else 0.0)
            aggregated.append(ObserverJudgment(
                self.observer_id, self.observer_version, target,
                StateDelta(
                    attitude=weighted("attitude"), arousal=weighted("arousal"),
                    trust=weighted("trust"), engagement_intent=weighted("engagement_intent")),
                confidence_sum / total_weight,
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
    observer_version = "3"

    async def judge(self, action, outcome, context):
        target = context["target_actor_id"]
        is_direct = context.get("is_direct_target", True)
        if action.action_type == "do_nothing":
            delta = StateDelta(engagement_intent=-0.05, arousal=-0.05)
            evidence = "The candidate did not engage."
        else:
            content = str(action.arguments.get("content",
                                               action.arguments.get("body", "")))
            norms = context.get("culture", {})
            hostile = any(token in content.casefold() for token in
                          ("闭嘴", "不在乎", "愚蠢", "idiot", "shut up",
                           *[word.casefold() for word in norms.get("avoid_phrases", [])]))
            deescalation = not hostile and any(token in content.casefold() for token in
                ("说清楚", "确认事实", "核对", "依据", "修正", "限制", "证据", "source", "correct",
                 *[word.casefold() for word in norms.get("prefer_phrases", [])]))
            delta = (StateDelta(attitude=0.15, arousal=-0.2, trust=0.1,
                                engagement_intent=0.1)
                     if deescalation else
                     StateDelta(attitude=-0.15, arousal=0.2, trust=-0.15)
                     if hostile else StateDelta())
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
