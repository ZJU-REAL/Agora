"""Two world initializers and explicit account starting conditions."""

import copy
import hashlib
import json
import math
from pathlib import Path

from agora.core import AssetInput, PersonaProfile
from agora.population import extend_population

MODE_FIELDS = {
    "world_mode",
    "focal_start",
    "focal_template_user_id",
    "focal_starter_posts",
    "new_account_name",
    "focal_profile",
    "background_start",
    "background_tasks",
    "include_starter_assets",
}

# Use the same eligibility rule for validation, copying and the source picker.
PUBLIC_ORIGINAL_POST = (
    "p.visibility='public' AND p.deleted=0 AND p.removed_by IS NULL "
    "AND p.original_post_id IS NULL AND p.reply_to_post_id IS NULL "
    "AND (p.community IS NULL OR EXISTS (SELECT 1 FROM community c "
    "WHERE c.name=p.community AND c.visibility='public'))"
)


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def has_user(source, user):
    return type(user) is int and bool(
        source.db.execute("SELECT 1 FROM user WHERE user_id=?", (user,)).fetchone()
    )


def resolve_accounts(source, config):
    mode = config.get("world_mode", "background")
    start = config.get("focal_start", "new" if mode == "ai_only" else "existing")
    background = config.get(
        "background_start", "new" if mode == "ai_only" else "existing"
    )
    if (
        mode not in {"background", "ai_only"}
        or start not in {"new", "existing"}
        or background not in {"new", "existing"}
    ):
        raise ValueError("Unknown world mode or account starting condition")
    if mode == "ai_only" and (start != "new" or background != "new"):
        raise ValueError("纯 AI 世界请新建参与账号；接手历史账号请使用背景世界。")
    count = config.get("agent_count")
    if count is not None and (type(count) is not int or not 1 <= count <= 100):
        raise ValueError("agent_count must be between 1 and 100")
    selected = config.get("user_ids")
    if selected is not None and (
        not isinstance(selected, list)
        or len(selected) > 100
        or (not selected and not (start == "new" and count is not None))
        or any(not has_user(source, u) for u in selected)
        or len(set(selected)) != len(selected)
    ):
        raise ValueError("Select distinct existing source accounts")
    focal = config.get("focal_user_id")
    if focal is not None and not has_user(source, focal):
        raise ValueError("Choose an existing source account")
    if start == "existing" and focal is None:
        if selected:
            focal = selected[0]
        elif count is not None:
            row = source.db.execute(
                "SELECT user_id FROM user ORDER BY user_id LIMIT 1"
            ).fetchone()
            focal = row[0] if row else None
    if start == "existing" and focal is None:
        raise ValueError("背景世界没有可接手账号，请导入账号或选择新建账号。")
    if start == "existing" and selected is not None and focal not in selected:
        raise ValueError("The tested account must participate in the run")
    if count is None:
        if selected is None:
            raise ValueError("Specify agent_count or source user_ids")
        count = len(selected) + (start == "new")
    if not 1 <= count <= 100:
        raise ValueError("agent_count must be between 1 and 100")
    template = config.get("focal_template_user_id", focal if start == "new" else None)
    if template is not None and not has_user(source, template):
        raise ValueError("Choose an existing account template")
    starter = config.get("focal_starter_posts", 0)
    if (
        type(starter) is not int
        or not 0 <= starter <= 20
        or (starter and start != "new")
    ):
        raise ValueError("New accounts may preload 0–20 public original posts")
    if starter and template is None:
        raise ValueError("预置内容需要选择模板账号。")
    if (
        starter
        and not source.db.execute(
            f"SELECT 1 FROM post p WHERE p.user_id=? AND {PUBLIC_ORIGINAL_POST} LIMIT 1",
            (template,),
        ).fetchone()
    ):
        raise ValueError("模板账号没有可预置的公开主帖。")
    name = config.get("new_account_name", "受测新号")
    if not isinstance(name, str) or not name.strip() or len(name) > 80:
        raise ValueError("New account display names must contain 1–80 characters")
    if not isinstance(config.get("focal_profile", {}), dict):
        raise TypeError("focal_profile must be a persona object")
    if type(config.get("include_starter_assets", True)) is not bool:
        raise ValueError("include_starter_assets must be boolean")
    tasks = config.get("background_tasks", [])
    if (
        not isinstance(tasks, list)
        or len(tasks) > count - 1
        or any(not isinstance(t, str) or len(t) > 4000 for t in tasks)
    ):
        raise ValueError(
            "Provide at most one task per background account, each at most 4000 characters"
        )
    if background == "new":
        if selected and selected != ([focal] if start == "existing" else []):
            raise ValueError(
                "New background accounts cannot also select historical user_ids"
            )
        users = [focal] if start == "existing" else []
    elif selected is not None:
        users = list(selected)
        if start == "existing":
            users.remove(focal)
            users.insert(0, focal)
    else:
        users = [focal] if start == "existing" else []
        users += [
            row[0]
            for row in source.db.execute(
                "SELECT user_id FROM user WHERE (? IS NULL OR user_id!=?) ORDER BY user_id LIMIT ?",
                (
                    focal if start == "existing" else None,
                    focal,
                    count - len(users) - (start == "new"),
                ),
            )
        ]
    if len(users) + (start == "new") > count:
        raise ValueError("agent_count is smaller than the selected accounts")
    return (
        users,
        focal if start == "existing" else None,
        count,
        {
            "world_mode": mode,
            "focal_start": start,
            "background_start": background,
            "focal_template_user_id": template,
            "focal_starter_posts": starter,
            "new_account_name": name.strip(),
            "focal_profile": copy.deepcopy(config.get("focal_profile", {})),
            "include_starter_assets": config.get("include_starter_assets", True),
            "background_tasks": list(tasks),
            "source_focal_user_id": focal if start == "existing" else None,
            "separate_tasks": "background_tasks" in config
            or bool(set(config) & MODE_FIELDS),
            "legacy_shared_policy": selected is not None
            and "agent_count" not in config
            and "focal_user_id" not in config
            and not bool(set(config) & MODE_FIELDS),
        },
    )


def copy_asset(source, target, asset_id, user, alt_text=None, transcript=None):
    row = source.db.execute(
        "SELECT object_key,checksum_sha256,byte_size FROM media_asset WHERE asset_id=? AND status='ready'",
        (asset_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Initial account media is unavailable")
    path = (source.config.media_path / row[0]).resolve()
    if (
        source.config.media_path.resolve() not in path.parents
        or file_sha256(path) != row[1]
        or path.stat().st_size != row[2]
    ):
        raise ValueError("Source media checksum mismatch")
    existing = target.db.execute(
        "SELECT 1 FROM media_asset WHERE asset_id=?", (asset_id,)
    ).fetchone()
    imported_id = asset_id if existing else target.import_media(path).asset_id
    target.db.execute(
        "INSERT OR IGNORE INTO creator_asset(user_id,asset_id,alt_text,transcript) VALUES (?,?,?,?)",
        (user, imported_id, alt_text, transcript),
    )
    return imported_id


def create_focal(source, target, config):
    template = config["focal_template_user_id"]
    row = (
        source.db.execute(
            "SELECT persona_json FROM persona WHERE user_id=?", (template,)
        ).fetchone()
        if template
        else None
    )
    base = (
        json.loads(row[0])
        if row
        else {
            "interests": {
                "摄影" if source.preset.name == "xiaohongshu" else "photography": 1
            },
            "locale": "zh-CN" if source.preset.name == "xiaohongshu" else "en-US",
            "posting_probability": 0.25,
        }
    )
    base.update(config["focal_profile"])
    next_id = target.db.execute(
        "SELECT COALESCE(MAX(user_id),0)+1 FROM user"
    ).fetchone()[0]
    handle = f"ai_{abs(config['seed']) % 100000}_{next_id}"
    while target.db.execute(
        "SELECT 1 FROM user WHERE user_name=?", (handle,)
    ).fetchone():
        handle = f"ai_{abs(config['seed']) % 100000}_{next_id}_n"
        next_id += 1
    base.update(
        profile_id=f"initial-{handle}",
        handle=handle,
        display_name=config["new_account_name"],
    )
    base["identity"] = {
        **base.get("identity", {}),
        "handle": handle,
        "display_name": config["new_account_name"],
    }
    profile = PersonaProfile.from_dict(base)
    for value in [
        profile.posting_probability,
        profile.comment_probability,
        profile.like_probability,
    ]:
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("Persona activity probabilities must be between 0 and 1")
    return target.add_persona(profile)


def initialize_accounts(source, target, config):
    mode = config["world_mode"]
    if mode == "ai_only":
        tick_ms, at_time = source.db.execute(
            "SELECT tick_duration_ms,current_time_ms FROM simulation_state WHERE singleton=1"
        ).fetchone()
        target.db.execute(
            "UPDATE simulation_state SET tick_duration_ms=? WHERE singleton=1",
            (tick_ms,),
        )
        target.set_time(at_time)
        for row in source.db.execute(
            "SELECT name,title,description,rules_json FROM community WHERE visibility='public' ORDER BY name LIMIT 100"
        ):
            target.db.execute(
                "INSERT OR IGNORE INTO community(name,title,description,rules_json,creator_id) VALUES (?,?,?,?,NULL)",
                row,
            )
        if (
            source.preset.name == "reddit"
            and not target.db.execute("SELECT 1 FROM community LIMIT 1").fetchone()
        ):
            target.db.execute(
                "INSERT INTO community(name,title,description,rules_json,creator_id) VALUES ('r/general','General discussion','A place for AI accounts to start conversations','[]',NULL)"
            )
        target.db.commit()
    users = list(config["user_ids"])
    if config["focal_start"] == "new":
        focal = create_focal(source, target, config)
        users.insert(0, focal)
    else:
        focal = config["source_focal_user_id"]
    preloaded = []
    if config["focal_start"] == "new" and config["focal_starter_posts"]:
        template = config["focal_template_user_id"]
        for row in source.db.execute(
            "SELECT p.post_id,p.content,p.title,p.post_type,p.language,p.community,p.location,p.created_at,p.link_url "
            f"FROM post p WHERE p.user_id=? AND {PUBLIC_ORIGINAL_POST} ORDER BY p.post_id DESC LIMIT ?",
            (template, config["focal_starter_posts"]),
        ):
            if (
                row[5]
                and not target.db.execute(
                    "SELECT 1 FROM community WHERE name=? AND visibility!='private'",
                    (row[5],),
                ).fetchone()
            ):
                raise ValueError("Preloaded posts need an available public community")
            assets = []
            for (
                asset,
                key,
                position,
                role,
                caption,
                alt,
                transcript,
            ) in source.db.execute(
                "SELECT p.asset_id,m.object_key,p.position,p.role,p.caption,p.alt_text,p.transcript "
                "FROM post_asset p JOIN media_asset m ON m.asset_id=p.asset_id WHERE p.post_id=? ORDER BY p.position",
                (row[0],),
            ):
                copied = copy_asset(source, target, asset, focal, alt, transcript)
                copied_key = target.db.execute(
                    "SELECT object_key FROM media_asset WHERE asset_id=?", (copied,)
                ).fetchone()[0]
                assets.append(
                    AssetInput(
                        target.media.path_for(copied_key),
                        role,
                        caption,
                        alt,
                        transcript,
                    )
                )
            pid = target.create_post(
                focal,
                body=row[1],
                title=row[2],
                post_type=row[3],
                assets=assets,
                topics=source.get_post_topics(row[0]),
                language=row[4],
                community=row[5],
                location=row[6],
            )
            target.db.execute(
                "UPDATE post SET created_at=?,link_url=? WHERE post_id=?",
                (row[7], row[8], pid),
            )
            preloaded.append(
                {"post_id": pid, "source_post_id": row[0], "origin": "account_preload"}
            )
    if config["include_starter_assets"] and config["focal_start"] == "new":
        for asset, alt, transcript in source.db.execute(
            "SELECT DISTINCT pa.asset_id,pa.alt_text,pa.transcript FROM post_asset pa JOIN post p ON p.post_id=pa.post_id "
            "LEFT JOIN community c ON c.name=p.community WHERE p.visibility='public' AND p.deleted=0 "
            "AND p.removed_by IS NULL AND (c.name IS NULL OR c.visibility='public') ORDER BY pa.asset_id LIMIT 12",
        ):
            copy_asset(source, target, asset, focal, alt, transcript)
    if len(users) < config["agent_count"]:
        users = extend_population(
            target,
            users,
            config["agent_count"],
            config["seed"],
            provide_assets=config["include_starter_assets"],
        )
    if mode == "ai_only" and config["include_starter_assets"]:
        for user in users[1:]:
            target.db.execute(
                "INSERT OR IGNORE INTO creator_asset(user_id,asset_id,alt_text,transcript) SELECT ?,asset_id,alt_text,transcript FROM creator_asset WHERE user_id=?",
                (user, focal),
            )
    target.db.commit()
    target.set_seed(config["seed"])
    config["user_ids"] = users
    config["focal_user_id"] = focal
    tasks = config["background_tasks"]
    config["agent_goals"] = {
        str(user): config["goal"]
        if index == 0
        else (
            tasks[index - 1]
            if index - 1 < len(tasks)
            else ("" if config["separate_tasks"] else config["goal"])
        )
        for index, user in enumerate(users)
    }
    config["initial_state"] = {
        "world_mode": mode,
        "focal_start": config["focal_start"],
        "focal_user_id": focal,
        "world_users": target.db.execute("SELECT COUNT(*) FROM user").fetchone()[0],
        "active_accounts": len(users),
        "posts": target.db.execute(
            "SELECT COUNT(*) FROM post WHERE deleted=0"
        ).fetchone()[0],
        "comments": target.db.execute(
            "SELECT COUNT(*) FROM comment WHERE deleted=0"
        ).fetchone()[0],
        "media": target.db.execute(
            "SELECT COUNT(*) FROM media_asset WHERE status='ready'"
        ).fetchone()[0],
        "focal_posts": target.db.execute(
            "SELECT COUNT(*) FROM post WHERE user_id=? AND deleted=0", (focal,)
        ).fetchone()[0],
        "focal_assets": target.db.execute(
            "SELECT COUNT(*) FROM creator_asset WHERE user_id=?", (focal,)
        ).fetchone()[0],
        "preloaded_posts": preloaded,
    }
