from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from oasis.agora_oasis import AgoraOasis
from oasis.agora_types import AssetInput, PersonaProfile


@dataclass(frozen=True)
class ImportReport:
    users: int = 0
    personas: int = 0
    posts: int = 0
    comments: int = 0
    relations: int = 0
    interactions: int = 0
    skipped: int = 0


class DatasetImporter:
    """Imports a versioned JSONL dataset into one Agora-OASIS world."""

    def __init__(self, sandbox: AgoraOasis):
        self.sandbox = sandbox

    async def import_manifest(self, manifest_path: str | Path) -> ImportReport:
        path = Path(manifest_path).resolve(strict=True)
        manifest = self._load_manifest(path)
        dataset = manifest.get("dataset", {})
        namespace = manifest.get("import", {}).get(
            "id_namespace", dataset.get("name", path.stem))
        files = manifest.get("files", {})
        root = path.parent

        counts = {"users": 0, "personas": 0, "posts": 0, "comments": 0,
                  "relations": 0, "interactions": 0, "skipped": 0}
        for row in self._rows(root, files.get("users")):
            external_id = str(row["external_id"])
            if self._lookup(namespace, "user", external_id):
                counts["skipped"] += 1
                continue
            user_id = self.sandbox.create_user(
                handle=row["handle"],
                display_name=row.get("display_name", row["handle"]),
                bio=row.get("bio", ""),
            )
            self._map(namespace, "user", external_id, user_id)
            counts["users"] += 1

        for row in self._rows(root, files.get("personas")):
            profile = PersonaProfile.from_dict(row)
            if self._lookup(namespace, "persona", profile.profile_id):
                counts["skipped"] += 1
                continue
            user_id = self.sandbox.add_persona(profile)
            self._map(namespace, "persona", profile.profile_id, user_id)
            user_external_id = row.get("user_external_id")
            if user_external_id:
                self._map(namespace, "user", str(user_external_id), user_id)
            counts["personas"] += 1

        for row in self._rows(root, files.get("relations")):
            external_id = str(row["external_id"])
            if self._lookup(namespace, "relation", external_id):
                counts["skipped"] += 1
                continue
            if row.get("type") != "follow":
                raise ValueError(f"Unsupported relation type: {row.get('type')}")
            actor_id = int(self._required(
                namespace, "user", str(row["actor_external_id"])))
            target_id = int(self._required(
                namespace, "user", str(row["target_external_id"])))
            if not self.sandbox.follow_user(actor_id, target_id):
                raise ValueError(f"Duplicate follow relation: {external_id}")
            self._map(namespace, "relation", external_id, external_id)
            counts["relations"] += 1

        media_root = (root / files.get("media_root", "media")).resolve()
        if root not in media_root.parents and media_root != root:
            raise ValueError("media_root escapes manifest directory")
        for row in self._rows(root, files.get("posts")):
            external_id = str(row["external_id"])
            if self._lookup(namespace, "post", external_id):
                counts["skipped"] += 1
                continue
            author_id = self._required(namespace, "user",
                                       str(row["author_external_id"]))
            assets = []
            for item in row.get("assets", []):
                media_path = (media_root / item["path"]).resolve(strict=True)
                if media_root not in media_path.parents:
                    raise ValueError(
                        f"Media path escapes media_root: {item['path']}")
                assets.append(AssetInput(
                    path=media_path, role=item.get("role", "content"),
                    caption=item.get("caption"),
                    alt_text=item.get("alt_text"),
                    transcript=item.get("transcript")))
            reply_external_id = row.get("reply_to_post_external_id")
            reply_to_post_id = (int(self._required(
                namespace, "post", str(reply_external_id)))
                if reply_external_id else None)
            post_id = self.sandbox.create_post(
                author_id=int(author_id),
                body=row.get("body", ""),
                title=row.get("title"),
                post_type=row.get("post_type", "text"),
                assets=assets,
                topics=list(row.get("topics", [])),
                language=row.get("language"),
                visibility=row.get("visibility", "public"),
                community=row.get("community"),
                location=row.get("location"),
                reply_to_post_id=reply_to_post_id,
            )
            self._map(namespace, "post", external_id, post_id)
            counts["posts"] += 1

        pending = list(self._rows(root, files.get("comments")))
        while pending:
            progressed = False
            remaining = []
            for row in pending:
                external_id = str(row["external_id"])
                if self._lookup(namespace, "comment", external_id):
                    counts["skipped"] += 1
                    progressed = True
                    continue
                parent_external_id = row.get("parent_external_id")
                parent_id = (self._lookup(namespace, "comment",
                                          str(parent_external_id))
                             if parent_external_id else None)
                if parent_external_id and parent_id is None:
                    remaining.append(row)
                    continue
                post_id = int(
                    self._required(namespace, "post",
                                   str(row["post_external_id"])))
                author_id = int(
                    self._required(namespace, "user",
                                   str(row["author_external_id"])))
                result = await self.sandbox.create_comment(
                    author_id, post_id, row["content"],
                    int(parent_id) if parent_id is not None else None)
                if not result.get("success"):
                    raise ValueError(
                        f"Could not import comment {external_id}: {result}")
                self._map(namespace, "comment", external_id,
                          result["comment_id"])
                counts["comments"] += 1
                progressed = True
            if not progressed:
                unresolved = [row["external_id"] for row in remaining]
                raise ValueError(
                    f"Unresolved or cyclic comment parents: {unresolved}")
            pending = remaining

        interaction_actions = {
            "like": self.sandbox.like_post,
            "collect": self.sandbox.collect_post,
            "downvote": self.sandbox.dislike_post,
        }
        for row in self._rows(root, files.get("interactions")):
            external_id = str(row["external_id"])
            if self._lookup(namespace, "interaction", external_id):
                counts["skipped"] += 1
                continue
            interaction_type = row.get("type")
            action = interaction_actions.get(interaction_type)
            if action is None:
                raise ValueError(
                    f"Unsupported interaction type: {interaction_type}")
            actor_id = int(self._required(
                namespace, "user", str(row["actor_external_id"])))
            post_id = int(self._required(
                namespace, "post", str(row["post_external_id"])))
            if not action(actor_id, post_id):
                raise ValueError(
                    f"Duplicate {interaction_type} interaction: {external_id}")
            self._map(namespace, "interaction", external_id, external_id)
            counts["interactions"] += 1

        self.sandbox.platform.db.commit()
        return ImportReport(**counts)

    def _lookup(self, namespace: str, entity_type: str,
                external_id: str) -> str | None:
        row = self.sandbox.platform.db.execute(
            "SELECT internal_id FROM external_id_map WHERE namespace = ? "
            "AND entity_type = ? AND external_id = ?",
            (namespace, entity_type, external_id),
        ).fetchone()
        return row[0] if row else None

    def _required(self, namespace: str, entity_type: str,
                  external_id: str) -> str:
        value = self._lookup(namespace, entity_type, external_id)
        if value is None:
            raise ValueError(
                f"Missing {entity_type} external_id {external_id!r} "
                f"in namespace {namespace!r}.")
        return value

    def _map(self, namespace: str, entity_type: str, external_id: str,
             internal_id: Any) -> None:
        self.sandbox.platform.db.execute(
            "INSERT INTO external_id_map "
            "(namespace, entity_type, external_id, internal_id) "
            "VALUES (?, ?, ?, ?)",
            (namespace, entity_type, external_id, str(internal_id)),
        )

    @staticmethod
    def _rows(root: Path, relative_path: str | None) -> Iterable[dict]:
        if not relative_path:
            return []
        path = (root / relative_path).resolve(strict=True)
        if root not in path.parents:
            raise ValueError(f"Dataset file escapes manifest root: {path}")
        with path.open("r", encoding="utf-8") as stream:
            return [json.loads(line) for line in stream if line.strip()]

    @staticmethod
    def _load_manifest(path: Path) -> dict:
        if path.suffix.lower() == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError(
                "PyYAML is required for YAML manifests; use JSON instead.") from exc
        return yaml.safe_load(path.read_text(encoding="utf-8"))
