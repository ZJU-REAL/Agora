"""Behavioral contrasts for native distribution and actual feedback evidence."""

import asyncio
import json
import shutil
import subprocess

import pytest
from PIL import Image

from agora.recommendation import RecommendationConfig, RecommendationEngine
from agora.session import SocialSession
from agora.world import open_world
from oasis import AssetInput, PersonaProfile


@pytest.fixture
def worlds(tmp_path):
    opened = []

    def make(platform):
        world = open_world(platform, tmp_path, platform)
        opened.append(world)
        author = world.create_user("author", "Author")
        reader = world.create_user("reader", "Reader")
        if platform == "reddit":
            world.create_community(
                author, "r/coffeehouse", "Coffee", rules=["Explain your evidence"]
            )
            world.create_community(
                author, "r/photography", "Photography", rules=["Describe your camera"]
            )
        return world, author, reader

    yield make
    for world in opened:
        world.close()


def act(session, action, **arguments):
    return asyncio.run(session.act(action, arguments))


def engine(world, **overrides):
    config = {
        "exploration_fraction": 0,
        "slate_size": 20,
        "page_size": 20,
        "topic_weight": 0,
        "following_weight": 0,
        "freshness_weight": 0,
        "fatigue_weight": 0,
        "collaborative_weight": 0,
        "graph_weight": 0,
        "community_weight": 0,
        "author_diversity_penalty": 0,
        "topic_diversity_penalty": 0,
        "community_diversity_penalty": 0,
        **overrides,
    }
    return RecommendationEngine(
        world.db, RecommendationConfig(**config), world.preset.name
    )


def cards(session):
    return [p["post_id"] for p in session.observe()["cards"]]


@pytest.mark.parametrize(
    "platform,expected", [("xiaohongshu", "saved"), ("x", "liked")]
)
def test_note_saves_and_x_likes_have_different_distribution_objectives(
    worlds, platform, expected
):
    world, author, reader = worlds(platform)
    saved = world.create_post(author, body="Practical reference", topics=["coffee"])
    liked = world.create_post(author, body="Quick observation", topics=["coffee"])
    for i in range(30):
        user = world.create_user(f"save-{i}", "Saver")
        world.save_post(user, saved)
    world.db.execute("UPDATE post SET num_likes=60 WHERE post_id=?", (liked,))
    world.db.commit()
    ids, _ = engine(world).rank(reader, 0, 42)
    assert ids[0] == {"saved": saved, "liked": liked}[expected]


@pytest.mark.parametrize("platform", ["xiaohongshu", "x", "reddit"])
def test_saved_reaction_undo_and_repeated_actions_do_not_manufacture_interest(
    worlds, platform
):
    world, author, reader = worlds(platform)
    extra = (
        {"community": "r/coffeehouse", "title": "Coffee"}
        if platform == "reddit"
        else {}
    )
    post = world.create_post(author, body="Coffee", topics=["coffee"], **extra)
    session = SocialSession.start(world, reader)
    act(session, "open_post", post_id=post)
    before = session.engine.interests(reader, 0)["coffee"]
    save, unsave = {
        "xiaohongshu": ("collect_post", "uncollect_post"),
        "x": ("bookmark_post", "unbookmark_post"),
        "reddit": ("save_post", "unsave_post"),
    }[platform]
    act(session, save, post_id=post)
    learned = session.engine.interests(reader, 0)["coffee"]
    act(session, save, post_id=post)
    assert session.engine.interests(reader, 0)["coffee"] == learned
    act(session, unsave, post_id=post)
    assert session.engine.interests(reader, 0)["coffee"] == pytest.approx(before)


def test_x_social_graph_retrieves_old_content_and_loses_boost_when_peer_unlikes(worlds):
    world, author, reader = worlds("x")
    peer = world.create_user("peer", "Peer")
    old = world.create_post(author, body="Older relevant conversation")
    for i in range(30):
        world.create_post(author, body=f"Recent {i}")
    world.follow_user(reader, peer)
    world.like_post(peer, old)
    recommender = engine(world, graph_weight=3, quality_weight=0, channel_limit=2)
    ids, diagnostics = recommender.rank(reader, 0, 42)
    assert ids[0] == old and old in diagnostics["retrieval"]["social_graph"]
    world.unlike_post(peer, old)
    ids, diagnostics = recommender.rank(reader, 0, 42)
    assert old not in diagnostics["retrieval"]["social_graph"]
    assert ids[0] != old


def test_x_reposts_share_source_topics_feedback_and_feed_slot(worlds):
    world, author, reader = worlds("x")
    source = world.create_post(author, body="Coffee", topics=["coffee"])
    peer = world.create_user("peer", "Peer")
    repost = world.repost(peer, source)
    quote = world.repost(peer, source, quote_body="A different view #discussion")
    assert world.get_post_topics(repost) == ["coffee"]
    assert world.get_post_topics(quote) == ["coffee", "discussion"]
    ids, _ = engine(world).rank(reader, 0, 42)
    assert len(set(ids) & {source, repost}) == 1 and quote in ids
    session = SocialSession.start(world, reader)
    act(session, "open_post", post_id=source)
    before = session.engine.interests(reader, 0)["coffee"]
    act(session, "repost", post_id=source)
    learned = session.engine.interests(reader, 0)["coffee"]
    assert learned > before
    act(session, "repost", post_id=source)
    assert session.engine.interests(reader, 0)["coffee"] == learned
    act(session, "undo_repost", post_id=source)
    assert session.engine.interests(reader, 0)["coffee"] == pytest.approx(before)


def test_x_following_keeps_conversation_context_and_chronology(worlds):
    world, author, reader = worlds("x")
    stranger = world.create_user("stranger", "Stranger")
    own = world.create_post(reader, body="My conversation")
    unrelated = world.create_post(stranger, body="Unrelated conversation")
    hidden_reply = world.create_post(
        author, body="Reply to stranger", reply_to_post_id=unrelated
    )
    reply_to_reader = world.create_post(
        author, body="Reply to you", reply_to_post_id=own
    )
    world.follow_user(reader, author)
    session = SocialSession.start(world, reader)
    act(session, "refresh", feed_type="following")
    assert reply_to_reader in cards(session) and hidden_reply not in cards(session)
    assert cards(session).index(reply_to_reader) < cards(session).index(own)


def test_x_unavailable_or_rejected_original_cannot_return_through_repost(worlds):
    world, author, reader = worlds("x")
    source = world.create_post(author, body="Original")
    peer = world.create_user("peer", "Peer")
    repost = world.repost(peer, source)
    session = SocialSession.start(world, reader)
    act(session, "open_post", post_id=source)
    act(session, "not_interested", post_id=source)
    ids, _ = engine(world).rank(reader, 0, 42)
    assert source not in ids and repost not in ids
    world.follow_user(reader, peer)
    act(session, "refresh", feed_type="following")
    assert repost not in cards(session)
    world.db.execute("DELETE FROM agora_feedback WHERE kind='not_interested'")
    world.db.execute("UPDATE post SET visibility='private' WHERE post_id=?", (source,))
    world.db.commit()
    ids, _ = engine(world).rank(reader, 0, 42)
    assert repost not in ids


@pytest.mark.parametrize("seed", [1, 7, 42])
def test_reddit_voted_quality_beats_downvoted_argument_volume(worlds, seed):
    world, author, reader = worlds("reddit")
    useful = world.create_post(
        author, body="Useful", title="Evidence", community="r/coffeehouse"
    )
    heated = world.create_post(
        author, body="Heated", title="Argument", community="r/coffeehouse"
    )
    world.db.execute(
        "UPDATE post SET num_likes=20,num_dislikes=1 WHERE post_id=?", (useful,)
    )
    world.db.execute(
        "UPDATE post SET num_likes=2,num_dislikes=30 WHERE post_id=?", (heated,)
    )
    world.db.executemany(
        "INSERT INTO comment(post_id,user_id,content,created_at) VALUES (?,?,?,0)",
        [(heated, author, "Argument") for _ in range(100)],
    )
    world.db.commit()
    ids, _ = engine(world).rank(reader, 0, seed)
    assert ids[0] == useful


def test_reddit_community_learning_distinguishes_identical_topics(worlds):
    world, author, reader = worlds("reddit")
    coffee = world.create_post(
        author,
        body="Coffee",
        title="Coffee",
        community="r/coffeehouse",
        topics=["photography"],
    )
    photo = world.create_post(
        author,
        body="Photo",
        title="Photo",
        community="r/photography",
        topics=["photography"],
    )
    session = SocialSession.start(world, reader)
    act(session, "open_post", post_id=coffee)
    act(session, "upvote_post", post_id=coffee)
    ids, diagnostic = engine(world, quality_weight=0, community_weight=2).rank(
        reader, 0, 42
    )
    assert ids.index(coffee) < ids.index(photo)
    assert diagnostic["community_interests"]["r/coffeehouse"] > 0
    assert session.observe()["community"]["rules"] == ["Explain your evidence"]
    assert "community_interests" not in json.dumps(session.observe())
    new_reader = world.create_user("new-reader", "New reader")
    assert not session.engine.community_interests(new_reader, 0)


def test_reddit_subscription_only_and_community_diversity(worlds):
    world, author, reader = worlds("reddit")
    world.join_community(reader, "r/coffeehouse")
    coffee = [
        world.create_post(
            author, body=f"Coffee {i}", title="Coffee", community="r/coffeehouse"
        )
        for i in range(8)
    ]
    photo = world.create_post(
        author, body="Photo", title="Photo", community="r/photography"
    )
    ids, _ = engine(world, community_diversity_penalty=2).rank(reader, 0, 42)
    assert photo in ids[:2]
    session = SocialSession.start(world, reader)
    act(session, "refresh", feed_type="following", sort="best")
    assert set(cards(session)) <= set(coffee)
    act(session, "leave_community", community="r/coffeehouse")
    act(session, "refresh", feed_type="following", sort="best")
    assert cards(session) == []


@pytest.mark.parametrize("surface", ["community", "following", "popular"])
@pytest.mark.parametrize("sort", ["top", "hot"])
def test_reddit_bounded_sorts_find_old_winners_beyond_latest_500(worlds, surface, sort):
    world, author, reader = worlds("reddit")
    world.join_community(reader, "r/coffeehouse")
    winner = world.create_post(
        author, body="Old winner", title="Old winner", community="r/coffeehouse"
    )
    world.db.execute("UPDATE post SET num_likes=10000 WHERE post_id=?", (winner,))
    # SQL fixture models a larger corpus without generating simulation events.
    world.db.executemany(
        "INSERT INTO post(user_id,content,title,community,created_at) VALUES (?,?,'Recent','r/coffeehouse',0)",
        [(author, f"Recent {i}") for i in range(550)],
    )
    world.db.commit()
    session = SocialSession.start(world, reader)
    if surface == "community":
        act(session, "view_community", community="r/coffeehouse", sort=sort)
    else:
        act(session, "refresh", feed_type=surface, sort=sort)
    assert cards(session)[0] == winner
    request_cards = json.loads(
        world.db.execute(
            "SELECT cards_json FROM agora_request ORDER BY request_id DESC LIMIT 1"
        ).fetchone()[0]
    )
    assert len(request_cards) <= session.config.slate_size


def test_reddit_time_windows_use_configured_virtual_duration(worlds):
    world, author, reader = worlds("reddit")
    old = world.create_post(author, body="Old", title="Old", community="r/coffeehouse")
    world.db.execute(
        "UPDATE simulation_state SET current_tick=2,tick_duration_ms=3600000,current_time_ms=7200000"
    )
    fresh = world.create_post(
        author, body="Fresh", title="Fresh", community="r/coffeehouse"
    )
    world.db.commit()
    session = SocialSession.start(world, reader)
    for sort in ["best", "top", "hot"]:
        act(
            session,
            "view_community",
            community="r/coffeehouse",
            sort=sort,
            time_range="hour",
        )
        assert fresh in cards(session) and old not in cards(session)


def test_xhs_nearby_keeps_location_across_refresh_and_learns_interest(worlds):
    world, author, reader = worlds("xiaohongshu")
    world.attach_persona(
        reader, PersonaProfile("reader", "reader", "Reader", interests={"coffee": 2})
    )
    relevant = world.create_post(
        author, body="Cafe", title="Cafe", location="Hangzhou", topics=["coffee"]
    )
    other = world.create_post(
        author, body="Photo", title="Photo", location="Hangzhou", topics=["photo"]
    )
    outside = world.create_post(
        author, body="Outside", title="Outside", location="Shanghai", topics=["coffee"]
    )
    session = SocialSession.start(world, reader)
    act(session, "refresh", feed_type="nearby", location=" Hangzhou ")
    assert cards(session)[0] == relevant and outside not in cards(session)
    act(session, "refresh")
    assert set(cards(session)) <= {relevant, other}
    assert session.observe()["location"] == "Hangzhou"


def test_xhs_collection_folder_saves_contribute_once(worlds):
    world, author, reader = worlds("xiaohongshu")
    post = world.create_post(author, body="Coffee", topics=["coffee"])
    session = SocialSession.start(world, reader)
    act(session, "open_post", post_id=post)
    folder = act(session, "create_collection", name="References")["folder_id"]
    before = session.engine.interests(reader, 0)["coffee"]
    act(session, "add_to_collection", folder_id=folder, post_id=post)
    after = session.engine.interests(reader, 0)["coffee"]
    assert after > before
    act(session, "add_to_collection", folder_id=folder, post_id=post)
    assert session.engine.interests(reader, 0)["coffee"] == after


def test_xhs_gallery_reading_is_bounded_and_editing_uses_actual_assets(
    worlds, tmp_path
):
    world, author, reader = worlds("xiaohongshu")
    images = []
    for i, color in enumerate(["red", "blue", "green"]):
        path = tmp_path / f"{i}.png"
        Image.new("RGB", (32, 32), color).save(path)
        images.append(AssetInput(path))
    post = world.create_post(
        author,
        body="Gallery",
        title="Gallery",
        topics=["photo"],
        post_type="gallery",
        assets=images,
    )
    session = SocialSession.start(world, reader)
    act(session, "open_post", post_id=post)
    act(session, "view_media", index=1)
    learned = session.engine.interests(reader, 0)["photo"]
    for i in [0, 1, 0, 1]:
        act(session, "view_media", index=i)
    assert session.engine.interests(reader, 0)["photo"] == learned
    act(session, "view_media", index=2)
    assert session.engine.interests(reader, 0)["photo"] > learned
    owner = SocialSession.start(world, author)
    act(owner, "open_post", post_id=post)
    act(owner, "edit_post", post_id=post, body="Updated", title="Updated")
    assert owner.observe()["post"]["body"] == "Updated"
    assert len(owner.observe()["post"]["assets"]) == 3


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="Video requires ffmpeg")
def test_video_seeking_and_replay_do_not_create_unbounded_reading_feedback(
    worlds, tmp_path
):
    world, author, reader = worlds("xiaohongshu")
    path = tmp_path / "video.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:size=32x32:rate=2:duration=60",
            "-c:v",
            "mpeg4",
            str(path),
        ],
        check=True,
    )
    post = world.create_post(
        author,
        body="Clip",
        title="Clip",
        topics=["video"],
        post_type="video",
        assets=[AssetInput(path)],
    )
    session = SocialSession.start(world, reader)
    act(session, "open_post", post_id=post)
    before = session.engine.interests(reader, 0)["video"]
    act(session, "seek_video", position_ms=30000)
    assert session.engine.interests(reader, 0)["video"] == before
    act(session, "play_video", duration_ms=30000)
    after = session.engine.interests(reader, 0)["video"]
    assert after > before
    act(session, "seek_video", position_ms=0)
    act(session, "play_video", duration_ms=30000)
    act(session, "dwell", duration_ms=30000)
    assert session.engine.interests(reader, 0)["video"] == after


def test_click_evidence_counts_displayed_opportunities_not_reopening(worlds):
    world, author, reader = worlds("xiaohongshu")
    post = world.create_post(author, body="Coffee", topics=["coffee"])
    session = SocialSession.start(world, reader)
    for _ in range(5):
        act(session, "open_post", post_id=post)
        act(session, "back")
    _, diagnostic = engine(world).rank(reader, 0, 42)
    assert diagnostic["decisions"][0]["evidence"] == {
        "clicks": 1,
        "impressions": 1,
        "readers": 0,
    }
    assert (
        world.db.execute(
            "SELECT COUNT(*) FROM agora_feedback WHERE kind='open_post'"
        ).fetchone()[0]
        == 1
    )


def test_private_posts_cannot_starve_bounded_native_candidate_windows(worlds):
    world, author, reader = worlds("reddit")
    public = world.create_post(
        author, body="Public", title="Public", community="r/coffeehouse"
    )
    world.db.executemany(
        "INSERT INTO post(user_id,content,title,community,created_at,visibility) VALUES (?,?,'Hidden','r/coffeehouse',0,'private')",
        [(author, f"Private {i}") for i in range(550)],
    )
    world.db.commit()
    session = SocialSession.start(world, reader)
    act(session, "view_community", community="r/coffeehouse", sort="new")
    assert cards(session) == [public]


@pytest.mark.parametrize("platform", ["xiaohongshu", "x"])
def test_reading_evidence_affects_distribution_without_repeated_click_bonus(
    worlds, platform
):
    world, author, reader = worlds(platform)
    read = world.create_post(author, body="Read thoughtfully", topics=["coffee"])
    clicked = world.create_post(author, body="Opened briefly", topics=["coffee"])
    session = SocialSession.start(world, reader)
    act(session, "open_post", post_id=read)
    act(session, "dwell", duration_ms=15000)
    act(session, "back")
    act(session, "open_post", post_id=clicked)
    act(session, "back")
    recommender = engine(world)
    ids, diagnostic = recommender.rank(reader, 0, 42)
    assert ids[0] == read
    by_id = {item["post_id"]: item for item in diagnostic["decisions"]}
    assert by_id[read]["evidence"]["readers"] == 1
    assert by_id[clicked]["evidence"]["readers"] == 0


@pytest.mark.parametrize(
    "version", ["agora-hybrid-v1", "agora-hybrid-v2", "agora-hybrid-v3"]
)
def test_previous_policy_versions_remain_available_without_new_graph_rules(
    worlds, version
):
    world, author, reader = worlds("x")
    world.create_post(author, body="Hello")
    ids, diagnostic = engine(world, policy_version=version).rank(reader, 0, 42)
    assert ids and diagnostic["policy_version"] == version
    assert "social_graph" not in diagnostic["retrieval"]
