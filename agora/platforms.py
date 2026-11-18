"""Versioned product contracts for the three AI-facing social platforms."""

import json
import re
import unicodedata
from dataclasses import asdict, dataclass, replace

import regex


@dataclass(frozen=True)
class ProductContract:
    platform: str
    display_name: str
    version: str
    feeds: tuple[str, ...]
    title_limit: int | None
    body_limit: int
    max_images: int
    capabilities: tuple[str, ...]

    def to_dict(self):
        return asdict(self)


CONTRACTS = {
    "xiaohongshu": ProductContract(
        "xiaohongshu",
        "小红书",
        "xhs-basic-v1",
        ("discover", "following", "nearby"),
        20,
        1000,
        20,
        ("notes", "gallery", "video", "collections", "pinned_comments"),
    ),
    "x": ProductContract(
        "x",
        "X / Twitter",
        "x-standard-v1",
        ("for_you", "following"),
        None,
        280,
        4,
        ("posts", "replies", "reposts", "quotes", "bookmarks", "threads"),
    ),
    "reddit": ProductContract(
        "reddit",
        "Reddit",
        "reddit-basic-v2",
        ("for_you", "following", "popular", "latest"),
        300,
        40000,
        20,
        ("communities", "votes", "comment_votes", "crossposts", "saved", "moderation"),
    ),
    "generic": ProductContract(
        "generic",
        "Agora",
        "generic-v1",
        ("discover", "following"),
        200,
        10000,
        20,
        ("posts", "gallery", "video"),
    ),
}


def x_weighted_length(text):
    """twitter-text v3 weights; basic URL and Unicode emoji tokenization."""
    text = unicodedata.normalize("NFC", text)
    emoji = regex.compile(
        r"(?:[0-9#*]\uFE0F?\u20E3|\p{Regional_Indicator}{2}|\p{Extended_Pictographic}(?:\uFE0F|\p{Emoji_Modifier})?(?:\u200D\p{Extended_Pictographic}(?:\uFE0F|\p{Emoji_Modifier})?)*)"
    )
    total = 0
    for part in re.split(r"(https?://[^\s<>]+)", text):
        if re.match(r"^https?://", part):
            total += 23
            continue
        cursor = 0
        for match in emoji.finditer(part):
            total += (
                sum(_x_char_weight(char) for char in part[cursor : match.start()]) + 2
            )
            cursor = match.end()
        total += sum(_x_char_weight(char) for char in part[cursor:])
    return total


def _x_char_weight(char):
    point = ord(char)
    return (
        1
        if point <= 4351
        or 8192 <= point <= 8205
        or 8208 <= point <= 8223
        or 8242 <= point <= 8247
        else 2
    )


def contract_for(world):
    contract = CONTRACTS[world.preset.name]
    path = world.config.world_dir / "world.json"
    limits = (
        json.loads(path.read_text()).get("product_limits", {}) if path.exists() else {}
    )
    if not isinstance(limits, dict) or set(limits) - {
        "title_limit",
        "body_limit",
        "max_images",
    }:
        raise ValueError("Unknown product limit fields")
    if world.preset.name == "x" and "title_limit" in limits:
        raise ValueError("X standard posts do not have a title field")
    for key, value in limits.items():
        if type(value) is not int or not 1 <= value <= (
            100 if key == "max_images" else 100000
        ):
            raise ValueError("Product limits must be bounded positive integers")
    return (
        replace(contract, **limits, version=contract.version + "-custom")
        if limits
        else contract
    )


def validate_creation(platform, args, library, contract=None):
    contract = contract or CONTRACTS[platform]
    body = args.get("body", "")
    if not isinstance(body, str):
        raise TypeError("body must be text")
    size = x_weighted_length(body) if platform == "x" else len(body)
    if size > contract.body_limit:
        raise ValueError(
            f"{contract.display_name} body exceeds {contract.body_limit} {'weighted characters' if platform == 'x' else 'characters'}"
        )
    if platform == "x" and args.get("title"):
        raise ValueError("X posts have no separate title")
    title = args.get("title", "")
    if contract.title_limit is not None and (
        not isinstance(title, str) or len(title) > contract.title_limit
    ):
        raise ValueError(f"Title exceeds {contract.title_limit} characters")
    if platform == "reddit" and (not title.strip() or not args.get("community")):
        raise ValueError("Reddit posts require a title and a community")
    specs = args.get("assets", [])
    formats = {asset["asset_id"]: asset["media_type"] for asset in library}
    content = [spec for spec in specs if spec.get("role", "content") == "content"]
    images = [spec for spec in content if formats.get(spec.get("asset_id")) == "image"]
    if len(images) > contract.max_images:
        raise ValueError(f"This platform accepts at most {contract.max_images} images")
    if len({spec.get("asset_id") for spec in specs}) != len(specs):
        raise ValueError("A post cannot attach the same asset twice")
    media_type = args.get("post_type") or (
        "video"
        if any(formats.get(spec.get("asset_id")) == "video" for spec in content)
        else "gallery"
        if len(images) > 1
        else "image"
        if images
        else "text"
    )
    if platform == "reddit" and args.get("url"):
        if (
            not isinstance(args["url"], str)
            or not re.match(r"^https?://[^\s]+$", args["url"])
            or specs
        ):
            raise ValueError("Link posts need an HTTP(S) URL and no media attachments")
        media_type = "link"
    elif args.get("url"):
        raise ValueError("Use the body for links on this platform")
    if media_type not in {"text", "image", "gallery", "video", "link"}:
        raise ValueError("Unknown post format")
    return media_type
