"""Cross-account journeys through the actual AI platform interface."""

import asyncio
import base64
import hashlib
import io
import json
import shutil
import sqlite3
import subprocess

import pytest
from PIL import Image

from agora.api import AgentAPI, PlatformHub
from agora.decisions import DecisionJournal
from agora.memory import AgentMemory
from agora.platforms import x_weighted_length
from agora.read_views import prepare_read_views
from agora.session import SocialSession
from agora.world import open_world


@pytest.fixture
def platforms(tmp_path):
    primary = open_world("products", tmp_path, "xiaohongshu")
    hub = PlatformHub(primary)
    hub.add_platforms()
    api = AgentAPI(hub)
    accounts = {}
    for platform in ("xiaohongshu", "x", "reddit"):
        accounts[platform] = {}
        for name in ("author", "reader"):
            account = api.register({"platform": platform, "handle": name + "_agent"})
            auth = "Bearer " + account["token"]
            _, session, _ = api.dispatch("POST", "/v1/sessions", {}, {}, auth)
            accounts[platform][name] = {
                "auth": auth,
                "session_id": session["session_id"],
                "user_id": account["user_id"],
            }
        if platform == "reddit":
            hub.worlds[platform].create_community(
                accounts[platform]["author"]["user_id"],
                "r/photography",
                "Photography",
                rules=["Be helpful"],
            )
    yield hub, api, accounts
    hub.shutdown()
    primary.close()


def act(platforms, platform, who, kind, args=None, request_id=None):
    hub, api, accounts = platforms
    user = accounts[platform][who]
    if request_id is None:
        session = SocialSession(hub.worlds[platform], user["session_id"])
        request_id = f"step-{session.state['step']}"
    _, receipt, _ = api.dispatch(
        "POST",
        f"/v1/sessions/{user['session_id']}/actions",
        {},
        {"action_type": kind, "arguments": args or {}, "request_id": request_id},
        user["auth"],
    )
    return receipt


def publish(platforms, platform, **extra):
    args = {"body": "An experience worth discussing"}
    if platform != "x":
        args["title"] = (
            "我的记录" if platform == "xiaohongshu" else "A useful experience"
        )
    if platform == "reddit":
        args["community"] = "r/photography"
    args.update(extra)
    receipt = act(platforms, platform, "author", "create_post", args)
    assert receipt["status"] == "succeeded", receipt
    return receipt["result"]["post_id"]


def upload(platforms, platform, who="author", alt_text=None):
    stream = io.BytesIO()
    Image.new("RGB", (20, 16), "red").save(stream, format="PNG")
    _, api, accounts = platforms
    _, asset, _ = api.dispatch(
        "POST",
        "/v1/assets",
        {},
        {
            "filename": "photo.png",
            "data_base64": base64.b64encode(stream.getvalue()).decode(),
            "alt_text": alt_text,
        },
        accounts[platform][who]["auth"],
    )
    return asset


@pytest.mark.parametrize("platform", ["xiaohongshu", "x", "reddit"])
def test_account_owned_sessions_and_private_trajectory(platforms, platform):
    _, api, accounts = platforms
    author, reader = accounts[platform]["author"], accounts[platform]["reader"]
    with pytest.raises(PermissionError):
        api.dispatch(
            "GET",
            f"/v1/sessions/{author['session_id']}/trajectory",
            {},
            {},
            reader["auth"],
        )
    _, own, _ = api.dispatch(
        "GET", f"/v1/sessions/{reader['session_id']}", {}, {}, reader["auth"]
    )
    assert own["platform"] == platform
    assert "feed_score" not in json.dumps(own) and "diagnostics" not in own


@pytest.mark.parametrize("platform", ["xiaohongshu", "x", "reddit"])
def test_idempotent_creation_and_conflicting_retry(platforms, platform):
    args = {"body": "one publication"}
    if platform != "x":
        args["title"] = "One"
    if platform == "reddit":
        args["community"] = "r/photography"
    first = act(platforms, platform, "author", "create_post", args, "same")
    second = act(platforms, platform, "author", "create_post", args, "same")
    assert first == second
    assert (
        platforms[0]
        .worlds[platform]
        .db.execute("SELECT COUNT(*) FROM post")
        .fetchone()[0]
        == 1
    )
    with pytest.raises(ValueError, match="Idempotency"):
        act(
            platforms,
            platform,
            "author",
            "create_post",
            {**args, "body": "changed"},
            "same",
        )


def test_reddit_votes_switch_and_comments_belong_to_crosspost(platforms):
    post = publish(platforms, "reddit")
    world = platforms[0].worlds["reddit"]
    reader = platforms[2]["reddit"]["reader"]["user_id"]
    act(platforms, "reddit", "reader", "open_post", {"post_id": post})
    up = act(platforms, "reddit", "reader", "upvote_post", {"post_id": post})
    assert up["observation"]["post"]["vote"] == 1
    down = act(platforms, "reddit", "reader", "downvote_post", {"post_id": post})
    assert down["observation"]["post"]["vote"] == -1
    assert (
        world.db.execute(
            'SELECT COUNT(*) FROM "like" WHERE user_id=? AND post_id=?', (reader, post)
        ).fetchone()[0]
        == 0
    )
    world.create_community(reader, "r/discussion", "Discussion")
    shared = act(
        platforms,
        "reddit",
        "reader",
        "crosspost",
        {"post_id": post, "community": "r/discussion"},
    )
    assert shared["status"] == "succeeded"
    crosspost = shared["result"]["post_id"]
    act(platforms, "reddit", "reader", "open_post", {"post_id": crosspost})
    comment = act(
        platforms,
        "reddit",
        "reader",
        "create_comment",
        {"post_id": crosspost, "content": "A separate conversation"},
    )
    assert (
        world.db.execute(
            "SELECT post_id FROM comment WHERE comment_id=?",
            (comment["result"]["comment_id"],),
        ).fetchone()[0]
        == crosspost
    )
    assert world.get_thread(post) == []
    comment_id = comment["result"]["comment_id"]
    up = act(
        platforms, "reddit", "reader", "upvote_comment", {"comment_id": comment_id}
    )
    assert up["observation"]["post"]["comments"][0]["vote"] == 1
    down = act(
        platforms, "reddit", "reader", "downvote_comment", {"comment_id": comment_id}
    )
    assert down["observation"]["post"]["comments"][0]["vote"] == -1
    assert down["observation"]["post"]["comments"][0]["score"] == -1
    clear = act(
        platforms, "reddit", "reader", "clear_comment_vote", {"comment_id": comment_id}
    )
    assert clear["observation"]["post"]["comments"][0]["vote"] == 0


def test_reddit_private_community_and_moderator_approval(platforms):
    hub, _, accounts = platforms
    world = hub.worlds["reddit"]
    owner, reader = (
        accounts["reddit"]["author"]["user_id"],
        accounts["reddit"]["reader"]["user_id"],
    )
    world.create_community(owner, "r/privateclub", "Private", visibility="private")
    post = world.create_post(
        owner, body="private text", title="Private", community="r/privateclub"
    )
    denied = act(platforms, "reddit", "reader", "open_post", {"post_id": post})
    assert denied["status"] == "failed"
    world.approve_member(owner, "r/privateclub", reader)
    allowed = act(platforms, "reddit", "reader", "open_post", {"post_id": post})
    assert allowed["observation"]["post"]["body"] == "private text"
    with pytest.raises(PermissionError):
        world.moderate_post(reader, post)
    world.moderate_post(owner, post)
    assert world.get_feed(reader, eligible_post_ids=[post]) == []
    world.moderate_post(owner, post, removed=False)
    assert world.get_feed(reader, eligible_post_ids=[post])


def test_reddit_link_posts_and_title_edit_rule(platforms):
    post = publish(platforms, "reddit", body="", url="https://example.com/story")
    opened = act(platforms, "reddit", "author", "open_post", {"post_id": post})
    assert opened["observation"]["post"]["post_type"] == "link"
    assert opened["observation"]["post"]["url"] == "https://example.com/story"
    changed = act(
        platforms,
        "reddit",
        "author",
        "edit_post",
        {"post_id": post, "body": "new", "title": "Changed"},
    )
    assert changed["status"] == "failed"


def test_x_replies_quotes_reposts_and_original_reactions(platforms):
    original = publish(platforms, "x")
    world = platforms[0].worlds["x"]
    act(platforms, "x", "reader", "open_post", {"post_id": original})
    reply = act(
        platforms, "x", "reader", "reply_post", {"post_id": original, "body": "A reply"}
    )
    assert reply["status"] == "succeeded", reply
    assert (
        world.db.execute(
            "SELECT reply_to_post_id FROM post WHERE post_id=?",
            (reply["result"]["post_id"],),
        ).fetchone()[0]
        == original
    )
    quoted = act(
        platforms,
        "x",
        "reader",
        "quote_post",
        {"post_id": original, "quote_body": "My context"},
    )
    assert quoted["status"] == "succeeded"
    repost = act(platforms, "x", "reader", "repost", {"post_id": original})
    repeated = act(platforms, "x", "reader", "repost", {"post_id": original})
    assert repost["result"]["post_id"] == repeated["result"]["post_id"]
    wrapper = repost["result"]["post_id"]
    act(platforms, "x", "reader", "open_post", {"post_id": wrapper})
    liked = act(platforms, "x", "reader", "like_post", {"post_id": wrapper})
    assert liked["status"] == "succeeded", liked
    assert (
        world.db.execute(
            "SELECT num_likes FROM post WHERE post_id=?", (original,)
        ).fetchone()[0]
        == 1
    )
    assert (
        world.db.execute(
            "SELECT num_likes FROM post WHERE post_id=?", (wrapper,)
        ).fetchone()[0]
        == 0
    )
    assert world.require_post(1, original)["num_shares"] == 2
    undone = act(platforms, "x", "reader", "undo_repost", {"post_id": wrapper})
    assert undone["status"] == "succeeded", undone
    assert world.require_post(1, original)["num_shares"] == 1
    act(platforms, "x", "reader", "open_post", {"post_id": original})
    repeated_undo = act(platforms, "x", "reader", "undo_repost", {"post_id": original})
    assert repeated_undo["result"]["changed"] is False
    assert world.require_post(1, original)["num_shares"] == 1


@pytest.mark.parametrize("platform", ["xiaohongshu", "x"])
def test_feed_reaction_state_belongs_to_current_account(platforms, platform):
    post = publish(platforms, platform)
    refreshed = act(platforms, platform, "reader", "refresh")
    card = next(p for p in refreshed["observation"]["cards"] if p["post_id"] == post)
    assert card["liked"] is False
    liked = act(platforms, platform, "reader", "like_post", {"post_id": post})
    card = next(p for p in liked["observation"]["cards"] if p["post_id"] == post)
    assert card["liked"] is True and card["num_likes"] == 1
    author = act(platforms, platform, "author", "view_profile")
    card = next(p for p in author["observation"]["cards"] if p["post_id"] == post)
    assert card["liked"] is False and card["num_likes"] == 1
    unliked = act(platforms, platform, "reader", "unlike_post", {"post_id": post})
    card = next(p for p in unliked["observation"]["cards"] if p["post_id"] == post)
    assert card["liked"] is False and card["num_likes"] == 0


@pytest.mark.parametrize(
    "text,expected",
    [
        ("hello", 5),
        ("你好", 4),
        ("👨‍👩‍👧‍👦", 2),
        ("🇨🇳", 2),
        ("https://example.com/a/very/long/path", 23),
    ],
)
def test_x_weighted_text_contract(text, expected):
    assert x_weighted_length(text) == expected


def test_x_standard_post_length_and_no_title(platforms):
    valid = act(platforms, "x", "author", "create_post", {"body": "中" * 140})
    assert valid["status"] == "succeeded"
    invalid = act(platforms, "x", "author", "create_post", {"body": "中" * 141})
    assert invalid["status"] == "failed"
    titled = act(
        platforms,
        "x",
        "author",
        "create_post",
        {"body": "text", "title": "not supported"},
    )
    assert titled["status"] == "failed"


def test_x_following_is_chronological_and_bookmarks_are_private(platforms):
    world = platforms[0].worlds["x"]
    owner = platforms[2]["x"]["author"]["user_id"]
    old = publish(platforms, "x", body="Old")
    new = publish(platforms, "x", body="New")
    world.db.execute("UPDATE post SET num_likes=10000 WHERE post_id=?", (old,))
    world.db.commit()
    act(platforms, "x", "reader", "refresh", {"feed_type": "for_you"})
    act(platforms, "x", "reader", "follow_user", {"followee_id": owner})
    feed = act(platforms, "x", "reader", "refresh", {"feed_type": "following"})
    assert [p["post_id"] for p in feed["observation"]["cards"]][:2] == [new, old]
    act(platforms, "x", "reader", "bookmark_post", {"post_id": old})
    saved = act(platforms, "x", "reader", "view_saved")
    assert [p["post_id"] for p in saved["observation"]["cards"]] == [old]
    other = act(platforms, "x", "author", "view_saved")
    assert other["observation"]["cards"] == []


def test_xhs_collection_pin_and_nested_comment_deletion(platforms):
    post = publish(platforms, "xiaohongshu")
    act(platforms, "xiaohongshu", "reader", "open_post", {"post_id": post})
    root = act(
        platforms,
        "xiaohongshu",
        "reader",
        "create_comment",
        {"post_id": post, "content": "How?"},
    )["result"]["comment_id"]
    act(platforms, "xiaohongshu", "author", "open_post", {"post_id": post})
    pinned = act(
        platforms, "xiaohongshu", "author", "pin_comment", {"comment_id": root}
    )
    assert pinned["observation"]["post"]["comments"][0]["is_pinned"]
    liked = act(
        platforms, "xiaohongshu", "author", "like_comment", {"comment_id": root}
    )
    assert liked["observation"]["post"]["comments"][0]["liked"]
    unliked = act(
        platforms, "xiaohongshu", "author", "unlike_comment", {"comment_id": root}
    )
    assert not unliked["observation"]["post"]["comments"][0]["liked"]
    reply = act(
        platforms,
        "xiaohongshu",
        "author",
        "create_comment",
        {"post_id": post, "content": "Like this", "parent_comment_id": root},
    )
    folder = act(
        platforms, "xiaohongshu", "reader", "create_collection", {"name": "参考"}
    )["result"]["folder_id"]
    added = act(
        platforms,
        "xiaohongshu",
        "reader",
        "add_to_collection",
        {"folder_id": folder, "post_id": post},
    )
    assert added["status"] == "succeeded"
    denied = act(
        platforms, "xiaohongshu", "author", "view_collection", {"folder_id": folder}
    )
    assert denied["status"] == "failed"
    deleted = act(
        platforms, "xiaohongshu", "reader", "delete_comment", {"comment_id": root}
    )
    assert deleted["status"] == "succeeded"
    comments = platforms[0].worlds["xiaohongshu"].get_thread(post)
    assert (
        comments[0]["content"] == "[deleted]"
        and comments[0]["replies"][0]["comment_id"] == reply["result"]["comment_id"]
    )


def test_reused_asset_does_not_share_private_library_annotations(platforms):
    private = upload(platforms, "xiaohongshu", "author", "private account annotation")
    other = upload(platforms, "xiaohongshu", "reader")
    assert private["asset_id"] == other["asset_id"]
    assert other["alt_text"] is None
    assert private["alt_text"] == "private account annotation"


def test_memory_failure_rolls_back_publication_and_keeps_correct_call_receipt(
    platforms, monkeypatch
):
    world = platforms[0].worlds["x"]
    user = platforms[2]["x"]["author"]
    session = SocialSession(world, user["session_id"])

    def broken(*args, **kwargs):
        raise RuntimeError("memory write failed")

    monkeypatch.setattr(AgentMemory, "remember", broken)
    journal = DecisionJournal(world)
    receipt = asyncio.run(
        journal.execute(
            session,
            "fault",
            {"action_type": "create_post", "arguments": {"body": "must roll back"}},
            [
                {
                    "status": "completed",
                    "model_id": "fake",
                    "input_tokens": 10,
                    "output_tokens": 5,
                }
            ],
        )
    )
    assert receipt["status"] == "failed" and receipt["failure_type"] == "infrastructure"
    assert world.db.execute("SELECT COUNT(*) FROM post").fetchone()[0] == 0
    assert (
        world.db.execute(
            "SELECT step FROM agent_model_call WHERE decision_id='fault'"
        ).fetchone()[0]
        == receipt["step"]
    )


def test_memory_remembers_observed_criticism_after_leaving_post(platforms):
    post = publish(platforms, "xiaohongshu")
    world = platforms[0].worlds["xiaohongshu"]
    reader = platforms[2]["xiaohongshu"]["reader"]["user_id"]
    asyncio.run(world.create_comment(reader, post, "这个经验缺少依据，请补充来源。"))
    act(platforms, "xiaohongshu", "author", "open_post", {"post_id": post})
    act(platforms, "xiaohongshu", "author", "back")
    memory = AgentMemory(world).retrieve(
        platforms[2]["xiaohongshu"]["author"]["user_id"], "依据"
    )
    assert "请补充来源" in json.dumps(memory, ensure_ascii=False)


def test_legacy_read_views_do_not_modify_frozen_database(tmp_path):
    path = tmp_path / "old.db"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE post(post_id INTEGER,content TEXT)")
    db.execute("INSERT INTO post VALUES (1,'old')")
    db.execute("CREATE TABLE simulation_state(current_tick INTEGER)")
    db.execute("INSERT INTO simulation_state VALUES (3)")
    db.commit()
    db.close()
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    prepare_read_views(db)
    assert db.execute("SELECT content,deleted,link_url FROM post").fetchone() == (
        "old",
        0,
        None,
    )
    assert (
        db.execute("SELECT current_time_ms FROM simulation_state").fetchone()[0]
        == 180000
    )
    db.close()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_x_gallery_limit_and_visible_four_image_grid(platforms):
    _, api, accounts = platforms
    assets = []
    for color in ("red", "blue", "green", "yellow", "purple"):
        stream = io.BytesIO()
        Image.new("RGB", (20, 16), color).save(stream, format="PNG")
        _, asset, _ = api.dispatch(
            "POST",
            "/v1/assets",
            {},
            {
                "filename": "photo.png",
                "data_base64": base64.b64encode(stream.getvalue()).decode(),
            },
            accounts["x"]["author"]["auth"],
        )
        assets.append({"asset_id": asset["asset_id"]})
    post = publish(platforms, "x", assets=assets[:4])
    feed = act(platforms, "x", "reader", "refresh", {"feed_type": "for_you"})
    assert (
        len(
            next(
                item for item in feed["observation"]["cards"] if item["post_id"] == post
            )["assets"]
        )
        == 4
    )
    too_many = act(
        platforms, "x", "author", "create_post", {"body": "five", "assets": assets}
    )
    assert too_many["status"] == "failed"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="Video features require ffmpeg")
def test_video_playback_position_controls_visual_input(platforms, tmp_path):
    from agora.backends.visual import session_visual_parts

    path = tmp_path / "clip.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=64x48:rate=4:duration=2",
            "-c:v",
            "mpeg4",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
    )
    hub, api, accounts = platforms
    _, asset, _ = api.dispatch(
        "POST",
        "/v1/assets",
        {},
        {
            "filename": "clip.mp4",
            "data_base64": base64.b64encode(path.read_bytes()).decode(),
        },
        accounts["xiaohongshu"]["author"]["auth"],
    )
    post = publish(
        platforms,
        "xiaohongshu",
        assets=[{"asset_id": asset["asset_id"]}],
        post_type="video",
    )
    first = act(platforms, "xiaohongshu", "reader", "open_post", {"post_id": post})
    before = session_visual_parts(hub.worlds["xiaohongshu"], first["observation"])
    played = act(
        platforms, "xiaohongshu", "reader", "play_video", {"duration_ms": 1000}
    )
    assert played["observation"]["post"]["video_position_ms"] == 1000
    after = session_visual_parts(hub.worlds["xiaohongshu"], played["observation"])
    assert before[-1] != after[-1]
    invalid = act(
        platforms, "xiaohongshu", "reader", "seek_video", {"position_ms": 999999}
    )
    assert invalid["status"] == "failed"


def test_custom_product_limits_are_exposed_and_enforced(platforms):
    from agora.platforms import contract_for

    world = platforms[0].worlds["xiaohongshu"]
    path = world.config.world_dir / "world.json"
    value = json.loads(path.read_text())
    value["product_limits"] = {"title_limit": 5, "max_images": 2}
    path.write_text(json.dumps(value))
    assert contract_for(world).version.endswith("-custom")
    rejected = act(
        platforms,
        "xiaohongshu",
        "author",
        "create_post",
        {"body": "text", "title": "long title"},
    )
    assert rejected["status"] == "failed"
    accepted = act(
        platforms,
        "xiaohongshu",
        "author",
        "create_post",
        {"body": "text", "title": "short"},
    )
    assert accepted["status"] == "succeeded"
