from __future__ import annotations

from dataclasses import dataclass
from itertools import product


@dataclass(frozen=True)
class AblationCondition:
    condition_id: str
    observer_pool_version: str
    npc_persona_distribution: str
    evaluation_awareness: bool


def build_ablation_matrix(
        observer_pools: tuple[str, ...],
        persona_distributions: tuple[str, ...],
        awareness_values: tuple[bool, ...] = (False, True),
        ) -> tuple[AblationCondition, ...]:
    if not observer_pools or not persona_distributions:
        raise ValueError("Ablations require observer and persona variants")
    return tuple(AblationCondition(
        condition_id=(f"observer-{observer}__personas-{personas}__"
                      f"aware-{str(aware).lower()}"),
        observer_pool_version=observer,
        npc_persona_distribution=personas,
        evaluation_awareness=aware)
        for observer, personas, aware in product(
            observer_pools, persona_distributions, awareness_values))
