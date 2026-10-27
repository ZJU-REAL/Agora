"""Episode-wide candidate resource accounting, including retries and resumes."""

from dataclasses import replace


class EpisodeBudget:
    def __init__(self, limits, max_ticks):
        self.limits = {"max_actions": max_ticks, **limits}
        unknown = set(self.limits) - {
            "max_actions",
            "max_model_calls",
            "max_total_tokens",
        }
        if unknown:
            raise ValueError(f"Unknown budget limits: {sorted(unknown)}")
        for name, value in self.limits.items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        self.actions = self.calls = self.tokens = 0
        self.unknown_usage = False

    def charge_calls(self, records):
        self.calls += len(records)
        for record in records:
            values = [record.get("input_tokens"), record.get("output_tokens")]
            if any(value is None for value in values):
                self.unknown_usage = True
            else:
                if any(
                    not isinstance(value, int) or isinstance(value, bool) or value < 0
                    for value in values
                ):
                    raise ValueError("Invalid provider token usage")
                self.tokens += sum(values)
        if "max_total_tokens" in self.limits and self.unknown_usage:
            raise ValueError("Token budget cannot be verified: missing provider usage")
        for name, used in (
            ("max_model_calls", self.calls),
            ("max_total_tokens", self.tokens),
        ):
            if name in self.limits and used > self.limits[name]:
                raise ValueError(f"Episode budget exceeded: {name}")

    def remaining(self):
        return {
            "actions": max(0, self.limits["max_actions"] - self.actions),
            "model_calls": (
                max(0, self.limits["max_model_calls"] - self.calls)
                if "max_model_calls" in self.limits
                else None
            ),
            "tokens": (
                max(0, self.limits["max_total_tokens"] - self.tokens)
                if "max_total_tokens" in self.limits
                else None
            ),
        }

    def exhausted(self):
        return any(
            value == 0 for value in self.remaining().values() if value is not None
        )

    def prepare(self, candidate):
        remaining = self.remaining()
        client = getattr(candidate, "client", None)
        if client is not None and hasattr(client, "limits"):
            configured = getattr(client, "configured_limits", client.limits)
            changes = {}
            if remaining["model_calls"] is not None:
                changes["max_requests"] = min(
                    configured.max_requests,
                    client.request_count + remaining["model_calls"],
                )
            if remaining["tokens"] is not None:
                changes["max_output_tokens"] = min(
                    configured.max_output_tokens, remaining["tokens"]
                )
            client.limits = replace(configured, **changes)
