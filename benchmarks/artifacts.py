from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from oasis import AgoraOasis


ARTIFACT_FORMAT_VERSION = 2


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ArtifactFile:
    path: str
    sha256: str
    byte_size: int


@dataclass(frozen=True)
class WorldArtifactManifest:
    artifact_id: str
    world_artifact_version: str
    format_version: int
    source_world_id: str
    platform: str
    tick: int
    seeds: dict[str, int]
    actor_pool_version: str
    observer_pool_version: str
    scenario_suite_version: str
    exposure_mode: str
    exposure_policy_version: str
    files: tuple[ArtifactFile, ...]
    metadata: dict[str, Any]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "WorldArtifactManifest":
        return cls(
            artifact_id=value["artifact_id"],
            world_artifact_version=value["world_artifact_version"],
            format_version=int(value["format_version"]),
            source_world_id=value["source_world_id"],
            platform=value["platform"],
            tick=int(value["tick"]),
            seeds={key: int(seed) for key, seed in value["seeds"].items()},
            actor_pool_version=value["actor_pool_version"],
            observer_pool_version=value["observer_pool_version"],
            scenario_suite_version=value["scenario_suite_version"],
            exposure_mode=value.get("exposure_mode", "controlled_exposure"),
            exposure_policy_version=value.get("exposure_policy_version",
                                              "controlled-dynamic-v2"),
            files=tuple(ArtifactFile(**item) for item in value["files"]),
            metadata=dict(value.get("metadata", {})),
        )


class WorldArtifact:
    """A frozen, checksummed baseline used to create isolated episodes."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    @property
    def manifest_path(self) -> Path:
        return self.root / "manifest.json"

    @property
    def manifest(self) -> WorldArtifactManifest:
        return WorldArtifactManifest.from_dict(
            json.loads(self.manifest_path.read_text(encoding="utf-8")))

    @classmethod
    def create(cls,
               sandbox: AgoraOasis,
               root: str | Path,
               *,
               artifact_id: str,
               version: str,
               npc_seed: int = 0,
               event_seed: int = 0,
               actor_pool_version: str = "development",
               observer_pool_version: str = "development",
               scenario_suite_version: str = "development",
               exposure_mode: str = "controlled_exposure",
               exposure_policy_version: str = "controlled-dynamic-v2",
               resources: dict[str, str | Path] | None = None,
               metadata: dict[str, Any] | None = None) -> "WorldArtifact":
        root = Path(root)
        if root.exists():
            raise FileExistsError(f"Artifact already exists: {root}")
        root.mkdir(parents=True)

        database = root / "baseline.db"
        destination = sqlite3.connect(database)
        try:
            sandbox.platform.db.backup(destination)
        finally:
            destination.close()

        if sandbox.config.media_path.exists():
            shutil.copytree(sandbox.config.media_path, root / "media")
        else:
            (root / "media").mkdir()
        if resources:
            resource_root = root / "resources"
            resource_root.mkdir()
            for name, source in resources.items():
                if "/" in name or "\\" in name or name in {".", ".."}:
                    raise ValueError(f"Invalid artifact resource name: {name}")
                source_path = Path(source)
                if not source_path.is_file():
                    raise FileNotFoundError(
                        f"Artifact resource does not exist: {source_path}")
                shutil.copy2(source_path, resource_root / name)

        world_seed = sandbox.platform.db.execute(
            "SELECT seed FROM simulation_state WHERE singleton = 1"
        ).fetchone()[0]
        files = cls._inventory(root)
        artifact_metadata = dict(metadata or {})
        if exposure_mode == "controlled_exposure":
            artifact_metadata.setdefault("controlled_post_ids", [
                int(row[0]) for row in sandbox.platform.db.execute(
                    "SELECT post_id FROM post WHERE visibility = 'public' "
                    "ORDER BY post_id").fetchall()
            ])
        manifest = WorldArtifactManifest(
            artifact_id=artifact_id,
            world_artifact_version=version,
            format_version=ARTIFACT_FORMAT_VERSION,
            source_world_id=sandbox.config.world_id,
            platform=sandbox.preset.name,
            tick=sandbox.current_tick,
            seeds={"world": int(world_seed), "npc": npc_seed,
                   "event": event_seed},
            actor_pool_version=actor_pool_version,
            observer_pool_version=observer_pool_version,
            scenario_suite_version=scenario_suite_version,
            exposure_mode=exposure_mode,
            exposure_policy_version=exposure_policy_version,
            files=files,
            metadata=artifact_metadata,
        )
        (root / "manifest.json").write_text(
            json.dumps(asdict(manifest), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        artifact = cls(root)
        artifact.validate()
        return artifact

    @staticmethod
    def _inventory(root: Path) -> tuple[ArtifactFile, ...]:
        return tuple(
            ArtifactFile(path=path.relative_to(root).as_posix(),
                         sha256=_sha256(path), byte_size=path.stat().st_size)
            for path in sorted(root.rglob("*"))
            if path.is_file() and path.name != "manifest.json"
        )

    def validate(self) -> WorldArtifactManifest:
        manifest = self.manifest
        if manifest.format_version != ARTIFACT_FORMAT_VERSION:
            raise ValueError(
                f"Unsupported artifact format: {manifest.format_version}")
        if manifest.exposure_mode == "learned_recommender":
            raise ValueError(
                "Learned recommender artifacts cannot be used by the main protocol")
        if (manifest.exposure_mode == "controlled_exposure"
                and "controlled_post_ids" not in manifest.metadata):
            raise ValueError("Controlled exposure has no frozen post set")
        actor_ids = manifest.metadata.get("actor_user_ids")
        if actor_ids is not None:
            policies = manifest.metadata.get("actor_policies", {})
            missing_policies = sorted(set(actor_ids) - set(policies))
            if missing_policies:
                raise ValueError(
                    f"Artifact has unversioned actor policies: {missing_policies}")
        candidate_assets = manifest.metadata.get("candidate_asset_keys", [])
        if (not isinstance(candidate_assets, list)
                or any(not isinstance(key, str) or not key
                       or Path(key).name != key
                       for key in candidate_assets)
                or len(candidate_assets) != len(set(candidate_assets))):
            raise ValueError("candidate_asset_keys must be unique strings")
        missing_assets = [key for key in candidate_assets
                          if not (self.root / "resources" / key).is_file()]
        if missing_assets:
            raise ValueError(
                f"Candidate assets are missing from resources: {missing_assets}")
        asset_metadata = manifest.metadata.get("candidate_asset_metadata", {})
        if not isinstance(asset_metadata, dict) or any(
                key not in candidate_assets or not isinstance(value, dict)
                for key, value in asset_metadata.items()):
            raise ValueError(
                "candidate_asset_metadata must describe whitelisted assets")
        expected = {item.path: item for item in manifest.files}
        actual = {item.path: item for item in self._inventory(self.root)}
        if expected.keys() != actual.keys():
            missing = sorted(expected.keys() - actual.keys())
            unexpected = sorted(actual.keys() - expected.keys())
            raise ValueError(f"Artifact file mismatch: missing={missing}, "
                             f"unexpected={unexpected}")
        for path, item in expected.items():
            if item.sha256 != actual[path].sha256 or (
                    item.byte_size != actual[path].byte_size):
                raise ValueError(f"Artifact checksum mismatch: {path}")
        if "baseline.db" not in actual:
            raise ValueError("Artifact has no baseline.db")
        return manifest

    def clone_episode(self, episode_root: str | Path,
                      episode_id: str) -> Path:
        manifest = self.validate()
        episode_root = Path(episode_root)
        world_dir = episode_root / "world"
        if episode_root.exists():
            raise FileExistsError(f"Episode workspace exists: {episode_root}")
        world_dir.mkdir(parents=True)
        shutil.copy2(self.root / "baseline.db", world_dir / "sandbox.db")
        shutil.copytree(self.root / "media", world_dir / "media")
        (world_dir / "world.json").write_text(json.dumps({
            "world_id": episode_id,
            "preset": manifest.platform,
            "format_version": 1,
            "source_artifact": manifest.artifact_id,
            "world_artifact_version": manifest.world_artifact_version,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return world_dir
