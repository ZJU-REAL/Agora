from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PlatformPreset:
    name: str
    allow_dislike: bool
    allow_repost: bool
    allow_collect: bool
    allow_gallery: bool
    allow_video: bool
    feed_types: tuple[str, ...]


PLATFORM_PRESETS = {
    "generic": PlatformPreset("generic", True, True, True, True, True,
                              ("discover", "following")),
    "xiaohongshu": PlatformPreset("xiaohongshu", False, False, True, True,
                                  True, ("discover", "following")),
    "reddit": PlatformPreset("reddit", True, True, False, True, True,
                             ("discover", "following")),
    "x": PlatformPreset("x", False, True, True, True, True,
                        ("discover", "following")),
}


@dataclass(frozen=True)
class AssetInput:
    path: str | Path
    role: str = "content"
    caption: str | None = None
    alt_text: str | None = None
    transcript: str | None = None


@dataclass(frozen=True)
class PersonaProfile:
    profile_id: str
    handle: str
    display_name: str
    bio: str = ""
    profile_version: str = "1.0"
    locale: str = "zh-CN"
    timezone: str = "Asia/Shanghai"
    niches: tuple[str, ...] = ()
    content_formats: dict[str, float] = field(
        default_factory=lambda: {"text": 1.0})
    interests: dict[str, float] = field(default_factory=dict)
    posting_probability: float = 0.05
    comment_probability: float = 0.2
    like_probability: float = 0.3
    tone: tuple[str, ...] = ("natural", )
    example_posts: tuple[str, ...] = ()
    policy_type: str = "scripted"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PersonaProfile":
        identity = data.get("identity", {})
        creator = data.get("creator", {})
        behavior = data.get("social_behavior", {})
        style = data.get("style", {})
        activity = data.get("activity", {})
        return cls(
            profile_id=data["profile_id"],
            profile_version=data.get("profile_version", "1.0"),
            handle=identity.get("handle", data.get("handle", data["profile_id"])),
            display_name=identity.get("display_name",
                                      data.get("display_name", data["profile_id"])),
            bio=identity.get("bio", data.get("bio", "")),
            locale=identity.get("locale", data.get("locale", "zh-CN")),
            timezone=identity.get("timezone",
                                  data.get("timezone", "Asia/Shanghai")),
            niches=tuple(creator.get("niche", data.get("niches", []))),
            content_formats=dict(
                creator.get("content_formats",
                            data.get("content_formats", {"text": 1.0}))),
            interests=dict(data.get("interests", {})),
            posting_probability=float(
                activity.get("posting_probability",
                             data.get("posting_probability", 0.05))),
            comment_probability=float(
                behavior.get("reply_probability",
                             data.get("comment_probability", 0.2))),
            like_probability=float(
                behavior.get("like_probability",
                             data.get("like_probability", 0.3))),
            tone=tuple(style.get("tone", data.get("tone", ["natural"]))),
            example_posts=tuple(
                style.get("example_posts", data.get("example_posts", []))),
            policy_type=data.get("policy_type", "scripted"),
        )


@dataclass(frozen=True)
class Observation:
    user: dict[str, Any]
    tick: int
    feed: list[dict[str, Any]]
    own_recent_posts: list[dict[str, Any]]


@dataclass(frozen=True)
class TickResult:
    tick: int
    actions: list[dict[str, Any]]
    events: list[dict[str, Any]]
