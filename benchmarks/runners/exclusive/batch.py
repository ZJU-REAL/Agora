from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from benchmarks.artifacts import WorldArtifact
from benchmarks.failures import classify_failure
from benchmarks.protocol import CandidatePolicy, EpisodeManifest
from benchmarks.runners.exclusive.runner import ExclusiveRunner, RunResult
from benchmarks.state import ObserverPolicy


@dataclass(frozen=True)
class BatchItemResult:
    seed: int
    run_id: str
    status: str
    output_dir: Path
    error_type: str | None = None
    error_message: str | None = None
    failure_class: str | None = None


class ExclusiveBatchRunner:
    """Runs isolated seeds concurrently with bounded failure containment."""

    def __init__(self, artifact: WorldArtifact, output_root: str | Path,
                 max_concurrency: int = 1):
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        self.artifact = artifact
        self.output_root = Path(output_root)
        self.max_concurrency = max_concurrency

    async def run(self,
                  template: EpisodeManifest,
                  seeds: list[int],
                  candidate_factory: Callable[[], CandidatePolicy],
                  observer_factory: Callable[[], ObserverPolicy] | None = None,
                  run_prefix: str | None = None) -> tuple[BatchItemResult, ...]:
        if not seeds or len(seeds) != len(set(seeds)):
            raise ValueError("Seeds must be a non-empty unique list")
        semaphore = asyncio.Semaphore(self.max_concurrency)
        prefix = run_prefix or template.candidate_id

        async def execute(seed: int) -> BatchItemResult:
            run_id = f"{prefix}-seed-{seed}"
            manifest = replace(template, seed=seed, run_id=run_id)
            runner = ExclusiveRunner(self.artifact, self.output_root)
            async with semaphore:
                try:
                    result: RunResult = await runner.run(
                        manifest, candidate_factory(),
                        observer_factory() if observer_factory else None)
                    return BatchItemResult(seed, run_id, result.status,
                                           result.output_dir)
                except Exception as error:
                    return BatchItemResult(
                        seed, run_id, "failed", self.output_root / run_id,
                        type(error).__name__, str(error),
                        classify_failure(error).value)

        return tuple(await asyncio.gather(*(execute(seed) for seed in seeds)))
