from __future__ import annotations

from enum import Enum


class FailureClass(str, Enum):
    INVALID_EPISODE = "invalid_episode"
    MODEL_FAILURE = "model_failure"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"


def classify_failure(error: Exception) -> FailureClass:
    if isinstance(error, (ValueError, KeyError, FileNotFoundError)):
        return FailureClass.INVALID_EPISODE
    if isinstance(error, (TimeoutError, ConnectionError)) or (
            "model-call" in str(error).lower()
            or "candidate exhausted" in str(error).lower()):
        return FailureClass.MODEL_FAILURE
    return FailureClass.INFRASTRUCTURE_FAILURE
