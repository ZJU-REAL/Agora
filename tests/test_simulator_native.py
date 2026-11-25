"""Native platform semantics, bounded replay and replaceable small data."""

import asyncio
import json
import struct
import zlib

import pytest

from agora.core import PersonaProfile
from agora.core.data_import import DatasetImporter
from agora.core.media import LocalMediaStore, MediaValidationError
from agora.demo import populate
from agora.distribution import reddit_hot
from agora.experiments import ExperimentManager
from agora.session import SocialSession
from agora.world import open_world


def act(session, kind, args=None):
    return asyncio.run(session.act(kind, args or {}))


@pytest.fixture
def world(tmp_path):
    world = open_world("native", tmp_path, "xiaohongshu")
    author = world.add_persona(
        PersonaProfile("author", "author", "笔记作者", interests={"摄影": 1})
    )
    reader = world.add_persona(
        PersonaProfile("reader", "reader", "读者", interests={"摄影": 1})
    )
    yield world, author, reader
    world.close()


def test_comment_paging_is_bounded_and_preserves_public_identity(world):
    world, author, reader = world
    post = world.create_post(author, body="摄影记录", title="摄影")
    world.db.executemany(
        "INSERT INTO comment(post_id,user_id,content,created_at) VALUES (?,?,?,?)",
        [(post, author, "Comment " + str(i), i) for i in range(350)],
    )
    world.db.commit()
    session = SocialSession.start(world, reader)
    act(session, "open_post", {"post_id": post})
    first = session.observe()["post"]["comments"]
    assert len(first) == 20
    assert all(
        c["author_name"] == "笔记作者" and c["author_handle"] == "author" for c in first
    )
    act(session, "load_comments", {"offset": 20, "sort": "new"})
    second = session.observe()["post"]["comments"]
    assert len(second) == 20
    assert not {c["comment_id"] for c in first} & {c["comment_id"] for c in second}
    assert session.observe()["post"]["num_comments"] == 350


def test_profile_tabs_do_not_leak_saves_or_change_received_likes(world):
    world, author, reader = world
    own = world.create_post(author, body="作者笔记", title="作者")
    other = world.create_post(reader, body="读者笔记", title="读者")
    world.like_post(reader, own)
    world.save_post(author, other)
    author_session = SocialSession.start(world, author)
    act(author_session, "view_profile")
    assert author_session.observe()["profile"]["received_likes"] == 1
    act(author_session, "view_profile", {"tab": "saved"})
    assert author_session.observe()["profile"]["received_likes"] == 1
    assert [p["post_id"] for p in author_session.observe()["cards"]] == [other]
    reader_session = SocialSession.start(world, reader)
    act(reader_session, "open_post", {"post_id": own})
    with pytest.raises(PermissionError):
        act(reader_session, "view_profile", {"user_id": author, "tab": "saved"})


@pytest.mark.parametrize("platform", ["xiaohongshu", "x", "reddit"])
def test_publication_returns_to_native_post_surface(platform, tmp_path):
    world = open_world("publish", tmp_path, platform)
    user = world.add_persona(PersonaProfile("user", "user", "Creator"))
    if platform == "reddit":
        world.create_community(user, "r/testing", "Testing")
    session = SocialSession.start(world, user)
    args = {"body": "A new post"}
    if platform != "x":
        args["title"] = "New post"
    if platform == "reddit":
        args["community"] = "r/testing"
    try:
        result = act(session, "create_post", args)
        observation = session.observe()
        if platform == "x":
            assert observation["screen"] == "feed"
            assert observation["cards"][0]["post_id"] == result["post_id"]
        else:
            assert observation["screen"] == "detail"
            assert observation["post"]["post_id"] == result["post_id"]
        if platform == "reddit":
            assert (
                observation["post"]["vote"] == 1 and observation["post"]["score"] == 1
            )
    finally:
        world.close()


def test_reddit_following_is_subscription_only_while_for_you_can_discover(tmp_path):
    world = open_world("feeds", tmp_path, "reddit")
    author = world.add_persona(PersonaProfile("a", "author", "Author"))
    user = world.add_persona(
        PersonaProfile("r", "reader", "Reader", interests={"coffee": 2})
    )
    world.create_community(author, "r/photography", "Photography")
    world.create_community(author, "r/coffeehouse", "Coffee")
    world.join_community(user, "r/photography")
    subscribed = world.create_post(
        author,
        body="Photo",
        title="Photo",
        community="r/photography",
        topics=["photography"],
    )
    discovered = world.create_post(
        author,
        body="Coffee",
        title="Coffee",
        community="r/coffeehouse",
        topics=["coffee"],
    )
    try:
        session = SocialSession.start(world, user)
        assert session.observe()["feed_type"] == "for_you"
        assert discovered in [p["post_id"] for p in session.observe()["cards"]]
        act(session, "refresh", {"feed_type": "following", "sort": "new"})
        assert [p["post_id"] for p in session.observe()["cards"]] == [subscribed]
        act(session, "refresh", {"feed_type": "home"})
        assert discovered in [p["post_id"] for p in session.observe()["cards"]]
    finally:
        world.close()


def test_reddit_hot_uses_virtual_time_in_seconds():
    assert reddit_hot(2, 10000, 60000) > reddit_hot(100, 0, 60000)
    assert reddit_hot(-3, 1, 60000) < reddit_hot(3, 1, 60000)


def test_compact_metadata_preserves_exact_on_demand_observations(world):
    world, author, reader = world
    post = world.create_post(author, body="Original note", title="Original")
    session = SocialSession.start(world, reader)
    act(session, "open_post", {"post_id": post})
    before = session.state["step"]
    act(session, "like_post", {"post_id": post})
    after = session.state["step"]
    assert session.observe_at(before)["post"]["num_likes"] == 0
    assert session.observe_at(after)["post"]["num_likes"] == 1
    assert all(
        "observation" not in e
        for e in session.trajectory(include_observations=False, compact=True)
    )
    assert session.observe()["post"]["num_likes"] == 1


def test_streamed_export_preserves_full_replay_and_metrics(tmp_path):
    world = open_world("export", tmp_path, "xiaohongshu")
    data = populate(world)
    manager = ExperimentManager(world)
    try:
        job = manager.start(
            {
                "agent_count": 4,
                "focal_user_id": data["reader_id"],
                "ticks": 2,
                "steps_per_tick": 8,
            }
        )
        manager.threads[job["run_id"]].join(15)
        inspected = manager.inspect(job["run_id"], event_limit=2)
        assert inspected["status"] == "completed"
        assert inspected["events_truncated"]
        path = manager.export_file(job["run_id"])
        exported = json.loads(path.read_text())
        assert exported["metrics"] == inspected["metrics"]
        assert exported["world_events"] == manager.export(job["run_id"])["world_events"]
        assert len(exported["events"]) == inspected["events_total"]
        assert not exported["events_truncated"]
        assert all(
            "observation" in event
            for t in exported["trajectories"]
            for event in t["trajectory"]
        )
        path.unlink()
    finally:
        manager.shutdown()
        world.close()


def test_import_binds_persona_to_user_and_imports_communities_out_of_order_comments(
    tmp_path,
):
    dataset = tmp_path / "dataset"
    dataset.mkdir()

    def rows(name, values):
        (dataset / name).write_text("\n".join(json.dumps(v) for v in values) + "\n")

    rows(
        "users.jsonl",
        [
            {"external_id": "u1", "handle": "one", "display_name": "One"},
            {"external_id": "u2", "handle": "two", "display_name": "Two"},
        ],
    )
    rows(
        "personas.jsonl",
        [
            {
                "profile_id": "voice",
                "user_external_id": "u1",
                "identity": {"handle": "unused"},
                "style": {"tone": ["curious"], "example_posts": ["Tell me more."]},
            }
        ],
    )
    rows(
        "communities.jsonl",
        [
            {
                "external_id": "c1",
                "name": "r/imported",
                "title": "Imported",
                "creator_external_id": "u1",
                "members": ["u2"],
                "rules": ["Be constructive"],
            }
        ],
    )
    rows(
        "posts.jsonl",
        [
            {
                "external_id": "p1",
                "author_external_id": "u1",
                "title": "Imported question",
                "body": "A discussion",
                "community": "r/imported",
            }
        ],
    )
    rows(
        "comments.jsonl",
        [
            {
                "external_id": "reply",
                "author_external_id": "u1",
                "post_external_id": "p1",
                "content": "A reply",
                "parent_external_id": "root",
            },
            {
                "external_id": "root",
                "author_external_id": "u2",
                "post_external_id": "p1",
                "content": "A question",
            },
        ],
    )
    manifest = dataset / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "dataset": {"name": "imported"},
                "files": {
                    k: k + ".jsonl"
                    for k in ("users", "personas", "communities", "posts", "comments")
                },
            }
        )
    )
    world = open_world("imported", tmp_path, "reddit")
    try:
        report = asyncio.run(DatasetImporter(world).import_manifest(manifest))
        assert (
            report.users == 2
            and report.personas == 1
            and report.communities == 1
            and report.comments == 2
        )
        assert world.db.execute("SELECT COUNT(*) FROM user").fetchone()[0] == 2
        assert world.db.execute("SELECT user_id FROM persona").fetchone()[0] == 1
        assert world.get_thread(1)[0]["replies"][0]["content"] == "A reply"
        again = asyncio.run(DatasetImporter(world).import_manifest(manifest))
        assert again.users == 0 and again.communities == 0 and again.comments == 0
    finally:
        world.close()


def test_large_image_rejected_from_header_before_pixel_decode(tmp_path):
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    image = tmp_path / "large.png"
    image.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 5000, 5000, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
        + chunk(b"IEND", b"")
    )
    with pytest.raises(MediaValidationError, match="16 megapixel"):
        LocalMediaStore(tmp_path / "media").import_file(image)


def test_fixture_is_small_and_has_platform_specific_styles(tmp_path):
    for platform in ("xiaohongshu", "x", "reddit"):
        world = open_world(platform, tmp_path, platform)
        try:
            result = populate(world)
            assert result["users"] == 4 and result["posts"] == 6
            voices = [
                json.loads(r[0])
                for r in world.db.execute("SELECT persona_json FROM persona")
            ]
            assert all(v["example_posts"] for v in voices)
            assert len({tuple(v["tone"]) for v in voices}) >= 3
        finally:
            world.close()


def test_asset_library_pages_keep_selected_draft_media(world, tmp_path):
    from PIL import Image

    from agora.core import AssetInput

    world, author, _ = world
    for index in range(24):
        image = tmp_path / f"asset-{index}.png"
        Image.new("RGB", (2, 2), (index, 0, 0)).save(image)
        world.create_post(
            author,
            body="Photo",
            title="Photo",
            assets=[AssetInput(image)],
            post_type="image",
        )
    session = SocialSession.start(world, author)
    act(session, "open_studio")
    first = session.observe()["asset_library"]
    assert len(first) == 20
    chosen = first[0]["asset_id"]
    act(
        session,
        "save_draft",
        {"title": "Draft", "body": "A note", "assets": [{"asset_id": chosen}]},
    )
    act(session, "view_asset_library", {"offset": 20})
    next_page = session.observe()
    assert next_page["library_total"] == 24
    assert len(next_page["asset_library"]) == 5
    assert chosen in [a["asset_id"] for a in next_page["asset_library"]]
