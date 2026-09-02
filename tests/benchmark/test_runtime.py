import json

from benchmarks.runtime import candidate_factory, observer_factory


def test_runtime_builds_model_candidate_without_secret(tmp_path):
    provider = tmp_path / "provider.json"
    provider.write_text(json.dumps({
        "provider": "rednote-gemini-gateway",
        "model_id": "runway-gemini-default",
        "api_key_env": "TEST_KEY",
        "limits": {"max_requests": 1, "max_output_tokens": 64},
    }), encoding="utf-8")
    config = tmp_path / "episode.json"
    value = {"candidate": {
        "type": "model", "policy_id": "candidate", "policy_version": "1",
        "provider_config": "provider.json", "max_attempts": 1}}
    create, policy_id, version = candidate_factory(value, config)
    candidate = create()
    assert (policy_id, version) == ("candidate", "1")
    assert candidate.client.limits.max_requests == 1
    assert candidate.supports_multimodal_context is False


def test_runtime_rejects_changed_provider_config(tmp_path):
    provider = tmp_path / "provider.json"
    provider.write_text(json.dumps({
        "provider": "rednote-gemini-gateway", "model_id": "model"}),
        encoding="utf-8")
    value = {"candidate": {
        "type": "model", "policy_id": "candidate", "policy_version": "1",
        "provider_config": "provider.json",
        "provider_config_sha256": "0" * 64}}
    import pytest
    with pytest.raises(ValueError, match="checksum mismatch"):
        candidate_factory(value, tmp_path / "episode.json")


def test_runtime_builds_model_observer(tmp_path):
    value = {"observer": {
        "type": "model", "observer_id": "judge", "observer_version": "1",
        "provider": {"provider": "rednote-gemini-gateway",
                     "model_id": "runway-gemini-default",
                     "limits": {"max_requests": 1}}}}
    observer = observer_factory(value, tmp_path / "episode.json")()
    assert observer.observer_id == "judge"
    assert observer.supports_multimodal_context is False


def test_runtime_enables_vision_only_when_provider_declares_it(tmp_path):
    value = {"candidate": {
        "type": "model", "policy_id": "candidate", "policy_version": "1",
        "provider": {"provider": "rednote-gemini-gateway",
                     "model_id": "vision-model", "supports_vision": True}}}
    candidate = candidate_factory(value, tmp_path / "episode.json")[0]()
    assert candidate.supports_multimodal_context is True


def test_runtime_builds_versioned_observer_pool(tmp_path):
    value = {"observer": {
        "type": "pool", "pool_version": "pool-1", "observers": [
            {"type": "scripted", "observer_id": "a",
             "observer_version": "1"},
            {"type": "scripted", "observer_id": "b",
             "observer_version": "1"}]}}
    pool = observer_factory(value, tmp_path / "episode.json")()
    assert pool.observer_version == "pool-1"
    assert [item.observer_id for item in pool.observers] == ["a", "b"]


def test_runtime_loads_observer_pool_file(tmp_path):
    pool_path = tmp_path / "pool.json"
    pool_path.write_text(json.dumps({
        "type": "pool", "pool_version": "pool-file-1", "observers": [
            {"type": "scripted", "observer_id": "a",
             "observer_version": "1"}]}), encoding="utf-8")
    pool = observer_factory(
        {"observer_pool_config": "pool.json"},
        tmp_path / "episode.json")()
    assert pool.observer_version == "pool-file-1"


def test_runtime_rejects_changed_observer_pool_file(tmp_path):
    pool_path = tmp_path / "pool.json"
    pool_path.write_text(json.dumps({
        "type": "pool", "pool_version": "pool-file-1", "observers": [
            {"type": "scripted", "observer_id": "a",
             "observer_version": "1"}]}), encoding="utf-8")
    import pytest
    with pytest.raises(ValueError, match="pool config checksum mismatch"):
        observer_factory({
            "observer_pool_config": "pool.json",
            "observer_pool_config_sha256": "0" * 64,
        }, tmp_path / "episode.json")


def test_pool_resolves_member_provider_relative_to_pool_file(tmp_path):
    pool_dir = tmp_path / "pool"
    pool_dir.mkdir()
    (pool_dir / "provider.json").write_text(json.dumps({
        "provider": "local-transformers", "model_path": "/unused",
        "model_id": "local-model",
    }), encoding="utf-8")
    (pool_dir / "pool.json").write_text(json.dumps({
        "type": "pool", "pool_version": "relative-1", "observers": [{
            "type": "model", "observer_id": "local", "observer_version": "1",
            "provider_config": "provider.json",
        }],
    }), encoding="utf-8")
    pool = observer_factory(
        {"observer_pool_config": "pool/pool.json"},
        tmp_path / "episode.json")()
    assert pool.observers[0].client.model_id == "local-model"
