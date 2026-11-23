"""Journeys for configured activity, native culture, text and locality evidence."""

import asyncio
import json
import shutil
import subprocess

import pytest
from PIL import Image

from agora.content_features import LocalityMatcher
from agora.demo import populate
from agora.policies import PersonaPolicy
from agora.population import extend_population
from agora.recommendation import RecommendationConfig, RecommendationEngine
from agora.runner import run_sessions
from agora.session import SocialSession
from agora.world import open_world
from oasis import AssetInput, PersonaProfile


@pytest.fixture
def make_world(tmp_path):
    worlds = []

    def make(platform, **values):
        world = open_world(platform, tmp_path, platform)
        worlds.append(world)
        author = world.create_user("author", "Author")
        persona = {
            "interests": {"coffee": 1},
            "posting_probability": 0,
            "like_probability": 0,
            "comment_probability": 0,
            "locale": "en-US",
            "culture": {
                "save_probability": 0,
                "repost_probability": 0,
                "follow_probability": 0,
                "join_probability": 0,
            },
            **values,
        }
        reader = world.add_persona(
            PersonaProfile("reader", "reader", "Reader", **persona)
        )
        if platform == "reddit":
            world.create_community(
                author, "r/photography", "Photography", "Photography and cameras"
            )
            world.create_community(
                author,
                "r/coffeehouse",
                "Coffee",
                "Coffee and brewing",
                rules=["Explain your evidence"],
            )
        extra = (
            {"community": "r/coffeehouse", "title": "Coffee"}
            if platform == "reddit"
            else {}
        )
        post = world.create_post(
            author, body="Coffee extraction comparison", topics=["coffee"], **extra
        )
        return world, author, reader, post

    yield make
    for world in worlds:
        world.close()


def act(session, name, **arguments):
    return asyncio.run(session.act(name, arguments))


def policy(world, user, seed=42, creator=False):
    profile = json.loads(
        world.db.execute(
            "SELECT persona_json FROM persona WHERE user_id=?", (user,)
        ).fetchone()[0]
    )
    return PersonaPolicy(seed, profile, creator)


def neutral_engine(world, **overrides):
    options = {
        "channel_limit": 2,
        "slate_size": 8,
        "page_size": 8,
        "exploration_fraction": 0,
        "topic_weight": 0,
        "following_weight": 0,
        "quality_weight": 0,
        "freshness_weight": 0,
        "fatigue_weight": 0,
        "collaborative_weight": 0,
        "graph_weight": 0,
        "community_weight": 0,
        "text_weight": 1,
        "author_diversity_penalty": 0,
        "topic_diversity_penalty": 0,
        "community_diversity_penalty": 0,
        **overrides,
    }
    return RecommendationEngine(
        world.db, RecommendationConfig(**options), world.preset.name
    )


@pytest.mark.parametrize("platform", ["xiaohongshu", "x", "reddit"])
@pytest.mark.parametrize("seed", [1, 7, 42])
def test_zero_activity_is_respected_without_automatic_approval(
    make_world, platform, seed
):
    world, _, reader, _ = make_world(platform)
    before = world.db.execute("SELECT COUNT(*) FROM post").fetchone()[0]
    report = asyncio.run(
        run_sessions(
            world,
            [reader],
            4,
            8,
            policy_factory=lambda _: policy(world, reader, seed, creator=True),
        )
    )
    assert not report["failures"]
    assert world.db.execute("SELECT COUNT(*) FROM post").fetchone()[0] == before
    assert (
        world.db.execute(
            'SELECT COUNT(*) FROM "like" WHERE user_id=?', (reader,)
        ).fetchone()[0]
        == 0
    )
    assert (
        world.db.execute(
            "SELECT COUNT(*) FROM comment WHERE user_id=?", (reader,)
        ).fetchone()[0]
        == 0
    )


@pytest.mark.parametrize("platform", ["xiaohongshu", "x", "reddit"])
def test_a_new_account_can_create_when_its_profile_requests_creation(
    make_world, platform
):
    world, _, reader, _ = make_world(platform, posting_probability=1)
    report = asyncio.run(
        run_sessions(
            world,
            [reader],
            4,
            8,
            policy_factory=lambda _: policy(world, reader, creator=False),
        )
    )
    assert not report["failures"]
    created = world.db.execute(
        "SELECT COUNT(*) FROM post WHERE user_id=? AND reply_to_post_id IS NULL",
        (reader,),
    ).fetchone()[0]
    assert created == 2
    session = SocialSession(world, report["session_ids"][0])
    actions = [event["action"]["action_type"] for event in session.trajectory()]
    if platform == "reddit":
        assert actions.index("view_community") < actions.index("save_draft")
        assert world.db.execute(
            "SELECT DISTINCT community FROM post WHERE user_id=?", (reader,)
        ).fetchall() == [("r/coffeehouse",)]


@pytest.mark.parametrize("platform", ["xiaohongshu", "x", "reddit"])
def test_reading_precedes_a_configured_reaction(make_world, platform):
    world, _, reader, post = make_world(platform, like_probability=1)
    session = SocialSession.start(world, reader)
    act(session, "open_post", post_id=post)
    behavior = policy(world, reader)
    reading = asyncio.run(behavior.act(session.observe(), {}))
    assert reading["action_type"] == "dwell"
    act(session, reading["action_type"], **reading["arguments"])
    reaction = asyncio.run(behavior.act(session.observe(), {}))
    assert reaction["action_type"] == (
        "upvote_post" if platform == "reddit" else "like_post"
    )


def test_negative_interest_rejects_the_topic_without_a_downvote(make_world):
    world, author, reader, _ = make_world(
        "reddit", interests={"coffee": 1, "fitness": -2}
    )
    post = world.create_post(
        author,
        body="Fitness training",
        title="Fitness",
        topics=["fitness"],
        community="r/coffeehouse",
    )
    session = SocialSession.start(world, reader)
    act(session, "open_post", post_id=post)
    choice = asyncio.run(policy(world, reader).act(session.observe(), {}))
    assert choice["action_type"] == "not_interested"
    act(session, choice["action_type"], **choice["arguments"])
    assert (
        world.db.execute(
            "SELECT COUNT(*) FROM dislike WHERE user_id=?", (reader,)
        ).fetchone()[0]
        == 0
    )


@pytest.mark.parametrize(
    "language,word,body",
    [
        ("en-US", "coffee", "Coffee brewing ratios"),
        ("zh-CN", "咖啡", "手冲咖啡的参数比较"),
    ],
)
def test_untagged_older_content_is_retrieved_from_actual_text(
    make_world, language, word, body
):
    world, author, reader, _ = make_world(
        "xiaohongshu", locale=language, interests={word: 2}
    )
    old = world.create_post(author, body=body)
    for i in range(20):
        world.create_post(author, body=f"Different material {i}")
    ids, diagnostic = neutral_engine(world).rank(reader, 0, 42)
    assert old in diagnostic["retrieval"]["text_interest"] and ids[0] == old
    private = world.create_post(author, body=body, visibility="private")
    ids, _ = neutral_engine(world).rank(reader, 0, 42)
    assert private not in ids


def test_actual_feedback_learns_unlabeled_text_without_leaking_diagnostics(make_world):
    world, author, reader, _ = make_world("x", interests={})
    learned = world.create_post(author, body="Grind calibration")
    similar = world.create_post(author, body="Grind comparison")
    unrelated = world.create_post(author, body="Garden planting")
    session = SocialSession.start(world, reader)
    act(session, "open_post", post_id=learned)
    act(session, "like_post", post_id=learned)
    ids, diagnostic = neutral_engine(world).rank(reader, 0, 42)
    assert ids.index(similar) < ids.index(unrelated)
    assert diagnostic["text_interests"]["grind"] > 0
    assert "text_interests" not in json.dumps(session.observe())


@pytest.mark.parametrize(
    "value,query,expected",
    [
        ("浙江省杭州市西湖区", "杭州", True),
        ("杭州市/西湖区", "杭州市", True),
        ("杭州市/西湖区", "杭州市/西湖区", True),
        ("上海市/西湖区", "杭州市/西湖区", False),
        ("New York/Manhattan", "York", False),
        ("杭州路", "杭州", False),
    ],
)
def test_locality_levels_are_explicit_instead_of_arbitrary_substrings(
    value, query, expected
):
    assert LocalityMatcher().matches(value, query) is expected


def test_location_aliases_are_loaded_from_the_world_manifest(make_world):
    world, author, reader, _ = make_world("xiaohongshu")
    path = world.config.world_dir / "world.json"
    manifest = json.loads(path.read_text())
    manifest["location_aliases"] = {"杭州": ["Hangzhou", "杭州市"]}
    path.write_text(json.dumps(manifest))
    here = world.create_post(author, body="Coffee here", location="杭州市/西湖区")
    away = world.create_post(author, body="Coffee away", location="上海市/徐汇区")
    session = SocialSession.start(world, reader)
    act(session, "refresh", feed_type="nearby", location="Hangzhou")
    ids = [card["post_id"] for card in session.observe()["cards"]]
    assert here in ids and away not in ids


@pytest.mark.parametrize(
    "aliases", [[], {"A": ["alias"], "B": ["alias"]}, {"A": "alias"}]
)
def test_invalid_or_ambiguous_location_aliases_are_rejected(aliases):
    with pytest.raises(ValueError):
        LocalityMatcher(aliases)


def test_x_relationship_evidence_decays_with_the_actual_like_time(make_world):
    world, author, reader, _ = make_world("x")
    peer = world.create_user("peer", "Peer")
    old = world.create_post(author, body="Older signal")
    fresh = world.create_post(author, body="Current signal")
    world.follow_user(reader, peer)
    world.like_post(peer, old)
    world.set_time(128 * 60000)
    world.like_post(peer, fresh)
    world.db.execute(
        "UPDATE post SET created_at=128 WHERE post_id IN (?,?)", (old, fresh)
    )
    world.db.commit()
    ids, diagnostic = neutral_engine(world, graph_weight=3, text_weight=0).rank(
        reader, 128, 42
    )
    assert ids.index(fresh) < ids.index(old)
    by_id = {record["post_id"]: record for record in diagnostic["decisions"]}
    assert (
        by_id[fresh]["components"]["social_graph"]
        > by_id[old]["components"]["social_graph"]
    )


def test_x_replies_to_the_reader_are_retrieved_with_conversation_context(make_world):
    world, author, reader, _ = make_world("x")
    own = world.create_post(reader, body="A question")
    reply = world.create_post(author, body="A reply", reply_to_post_id=own)
    for i in range(20):
        world.create_post(author, body=f"Other {i}")
    ids, diagnostic = neutral_engine(world, graph_weight=3, text_weight=0).rank(
        reader, 0, 42
    )
    assert ids[0] == reply and reply in diagnostic["retrieval"]["conversations"]


def test_reddit_chooses_related_postable_community_and_requests_evidence(make_world):
    world, _, reader, _ = make_world("reddit", posting_probability=1)
    world.join_community(reader, "r/photography")
    session = SocialSession.start(world, reader)
    behavior = policy(world, reader)
    actions = []
    for _ in range(3):
        choice = asyncio.run(behavior.act(session.observe(), {}))
        actions.append(choice)
        act(session, choice["action_type"], **choice["arguments"])
    assert actions[0]["arguments"]["community"] == "r/coffeehouse"
    assert actions[-1]["action_type"] == "save_draft"
    assert actions[-1]["arguments"]["community"] == "r/coffeehouse"
    assert "evidence" in actions[-1]["arguments"]["body"]


def test_reddit_does_not_publish_off_topic_when_its_only_related_group_is_restricted(
    make_world,
):
    world, author, reader, _ = make_world("reddit", posting_probability=1)
    world.db.execute(
        "UPDATE community SET visibility='restricted' WHERE name='r/coffeehouse'"
    )
    world.join_community(reader, "r/coffeehouse")
    session = SocialSession.start(world, reader)
    groups = {g["name"]: g for g in session.observe()["communities"]}
    assert not groups["r/coffeehouse"]["posting_allowed"]
    assert (
        asyncio.run(policy(world, reader).act(session.observe(), {}))["action_type"]
        == "refresh"
    )
    world.approve_member(author, "r/coffeehouse", reader)
    assert {g["name"]: g for g in world.list_communities(reader)}["r/coffeehouse"][
        "posting_allowed"
    ]


def test_reddit_keeps_the_community_whose_rules_it_read_while_preparing_a_draft(
    make_world,
):
    world, author, reader, _ = make_world("reddit", posting_probability=1)
    session = SocialSession.start(world, reader)
    behavior = policy(world, reader)
    first = asyncio.run(behavior.act(session.observe(), {}))
    assert first["arguments"]["community"] == "r/coffeehouse"
    act(session, first["action_type"], **first["arguments"])
    world.create_post(
        author,
        body="Coffee comparison with photos",
        title="Coffee photography",
        topics=["coffee"],
        community="r/photography",
    )
    act(session, "view_community", community="r/photography")
    second = asyncio.run(behavior.act(session.observe(), {}))
    act(session, second["action_type"], **second["arguments"])
    draft = asyncio.run(behavior.act(session.observe(), {}))
    assert draft["action_type"] == "save_draft"
    assert draft["arguments"]["community"] == "r/coffeehouse"


def test_background_accounts_have_distinct_activity_and_selective_membership(
    make_world,
):
    world, author, reader, _ = make_world("reddit")
    world.create_community(author, "r/technology", "Technology", "Software and design")
    users = extend_population(world, [reader], 9, 42)[1:]
    profiles = [
        json.loads(
            world.db.execute(
                "SELECT persona_json FROM persona WHERE user_id=?", (user,)
            ).fetchone()[0]
        )
        for user in users
    ]
    assert len({p["culture"]["role"] for p in profiles}) == 4
    assert len({p["posting_probability"] for p in profiles}) > 1
    assert all(
        1
        <= world.db.execute(
            "SELECT COUNT(*) FROM community_member WHERE user_id=?", (user,)
        ).fetchone()[0]
        <= 2
        for user in users
    )


@pytest.mark.parametrize("tone", [("brief",), ("evidence-seeking",)])
def test_persona_tone_changes_the_actual_followup(make_world, tone):
    world, _, reader, post = make_world("xiaohongshu", tone=tone, comment_probability=1)
    session = SocialSession.start(world, reader)
    act(session, "open_post", post_id=post)
    behavior = policy(world, reader)
    reading = asyncio.run(behavior.act(session.observe(), {}))
    act(session, reading["action_type"], **reading["arguments"])
    reply = asyncio.run(behavior.act(session.observe(), {}))
    assert reply["action_type"] == "create_comment"
    assert ("measurements" in reply["arguments"]["content"]) == (
        tone == ("evidence-seeking",)
    )


@pytest.mark.parametrize(
    "format_name,asset_count", [("text", 0), ("image", 1), ("gallery", 2)]
)
def test_drafts_respect_requested_media_format(
    make_world, tmp_path, format_name, asset_count
):
    world, _, reader, _ = make_world(
        "xiaohongshu", posting_probability=1, content_formats={format_name: 1}
    )
    for i, color in enumerate(["red", "blue"]):
        path = tmp_path / f"{i}.png"
        Image.new("RGB", (32, 32), color).save(path)
        world.create_post(
            reader,
            body="Library material",
            post_type="image",
            assets=[AssetInput(path)],
        )
    session = SocialSession.start(world, reader)
    behavior = policy(world, reader)
    open_studio = asyncio.run(behavior.act(session.observe(), {}))
    act(session, open_studio["action_type"], **open_studio["arguments"])
    draft = asyncio.run(behavior.act(session.observe(), {}))
    assert draft["action_type"] == "save_draft"
    assert len(draft["arguments"]["assets"]) == asset_count
    act(session, "save_draft", **draft["arguments"])


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="Video requires ffmpeg")
def test_video_only_creation_uses_real_library_video_and_cover(make_world, tmp_path):
    world, _, reader, _ = make_world(
        "xiaohongshu", posting_probability=1, content_formats={"video": 1}
    )
    clip = tmp_path / "clip.mp4"
    cover = tmp_path / "cover.png"
    Image.new("RGB", (32, 32), "blue").save(cover)
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:size=32x32:rate=2:duration=2",
            "-c:v",
            "mpeg4",
            str(clip),
        ],
        check=True,
    )
    world.create_post(
        reader,
        body="Video library",
        title="Video",
        post_type="video",
        assets=[AssetInput(clip), AssetInput(cover, role="cover")],
    )
    session = SocialSession.start(world, reader)
    behavior = policy(world, reader)
    act(session, "open_studio")
    draft = asyncio.run(behavior.act(session.observe(), {}))
    act(session, "save_draft", **draft["arguments"])
    result = act(session, "publish_draft")
    assert result["post_id"] and session.observe()["post"]["post_type"] == "video"


def test_new_fixtures_cover_multiple_places_without_increasing_corpus(tmp_path):
    world = open_world("fixture", tmp_path, "xiaohongshu")
    try:
        populated = populate(world)
        assert populated["posts"] == 6 and populated["users"] == 4
        locations = {
            r[0] for r in world.db.execute("SELECT DISTINCT location FROM post")
        }
        assert len(locations) > 1
        assert world.db.execute("SELECT COUNT(*) FROM media_asset").fetchone()[0] == 3
    finally:
        world.close()


def test_examples_are_not_recycled_as_a_new_post_every_round(make_world):
    world, _, reader, _ = make_world(
        "x",
        posting_probability=1,
        example_posts=("A specific coffee example.",),
        culture={"posting_cooldown_ticks": 1},
    )
    report = asyncio.run(
        run_sessions(
            world, [reader], 3, 5, policy_factory=lambda _: policy(world, reader)
        )
    )
    assert not report["failures"]
    bodies = [
        r[0]
        for r in world.db.execute(
            "SELECT content FROM post WHERE user_id=? AND reply_to_post_id IS NULL ORDER BY post_id",
            (reader,),
        )
    ]
    assert len(bodies) == 3 and len(set(bodies)) == 3


@pytest.mark.parametrize("value", [-1, 2, float("nan"), True])
def test_invalid_activity_values_are_rejected(value):
    with pytest.raises(ValueError):
        PersonaPolicy(42, {"posting_probability": value})
