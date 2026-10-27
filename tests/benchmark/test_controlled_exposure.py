import asyncio

from benchmarks import WorldArtifact
from oasis import AgoraOasis
from oasis.agora_types import PersonaProfile


def test_controlled_exposure_hides_episode_posts(tmp_path):
    sandbox = AgoraOasis.local("source", tmp_path / "worlds",
                               preset="xiaohongshu")
    npc = sandbox.create_user("npc", "NPC")
    candidate = sandbox.create_user("candidate", "Candidate")
    frozen_post = sandbox.create_post(npc, body="Frozen scenario post")
    artifact = WorldArtifact.create(
        sandbox, tmp_path / "artifact", artifact_id="world", version="1")
    sandbox.close()

    artifact.clone_episode(tmp_path / "episode", "episode")
    episode = AgoraOasis.local("world", tmp_path / "episode")
    episode.create_post(candidate, body="Candidate-created post")
    observation = episode.observe_controlled(
        candidate, artifact.manifest.metadata["controlled_post_ids"])
    assert [post["post_id"] for post in observation.feed] == [frozen_post]
    episode.close()


def test_npcs_share_frozen_pool_but_rerank_after_earlier_likes(tmp_path):
    sandbox = AgoraOasis.local("world", tmp_path, preset="xiaohongshu")
    human = sandbox.create_user("human", "Human")
    candidate = sandbox.create_user("candidate", "Candidate")
    human_post = sandbox.create_post(human, body="Human reference",
                                     topics=["human-topic"])
    candidate_post = sandbox.create_post(candidate, body="Candidate content",
                                         topics=["candidate-topic"])
    first = sandbox.add_persona(PersonaProfile(
        "first", "first", "First", interests={"candidate-topic": 1.0},
        posting_probability=0, comment_probability=0, like_probability=1))
    second = sandbox.add_persona(PersonaProfile(
        "second", "second", "Second", interests={"human-topic": 0.5},
        posting_probability=0, comment_probability=0, like_probability=1))
    sandbox.set_seed(1)  # Freezes the actor order as first, then second.

    before = sandbox.get_feed(second, eligible_post_ids=[
        human_post, candidate_post], record_impressions=False)
    assert before[0]["post_id"] == human_post

    result = asyncio.run(sandbox.advance(
        content_pool_post_ids=[human_post, candidate_post],
        actor_user_ids=[first, second]))
    observations = [action for action in result.actions
                    if action["action"] == "observe_feed"]
    assert [item["user_id"] for item in observations] == [first, second]
    assert all(item["content_pool_post_ids"] == [human_post, candidate_post]
               for item in observations)
    assert observations[1]["post_ids"][0] == candidate_post
    likes = [action["post_id"] for action in result.actions
             if action["action"] == "like_post"]
    assert likes == [candidate_post, candidate_post]
    sandbox.close()
