"""Browser regressions for platform context, replay positions and slow requests.

DOM activation avoids compositor stability waits in older Playwright drivers.
Assertions still cover real form events, requests and persisted native frames.
"""

import time

import pytest
import requests
import test_iap_console
import test_native_ui


@pytest.fixture(scope="module")
def browser():
    yield from test_native_ui.browser.__wrapped__()


@pytest.fixture(scope="module")
def mounted_server(tmp_path_factory):
    yield from test_iap_console.mounted_server.__wrapped__(tmp_path_factory)


def developer_ready(page, platform):
    page.wait_for_function(
        "p => world?.preset === p && !developerLoading", arg=platform, polling=100
    )


def make_run(root, platform="xiaohongshu", **extra):
    config = {
        "name": "Workbench regression",
        "agent_count": 2,
        "focal_user_id": 1,
        "provider_id": "development",
        "background_provider_id": "development",
        "ticks": 1,
        "steps_per_tick": 4,
        "seed": 42,
        "goal": "",
        "pace_ms": 0,
        **extra,
    }
    response = requests.post(root + "/api/runs?platform=" + platform, json=config)
    assert response.status_code == 201, response.text
    run = response.json()
    if config["pace_ms"] == 0:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            run = requests.get(root + "/api/runs/" + run["run_id"]).json()
            if run["status"] == "completed":
                return run
            time.sleep(0.05)
        pytest.fail("Isolated run did not complete")
    return run


def viewer_ready(page):
    page.wait_for_function("actorData?.trajectory?.length > 0", polling=100)


def assert_native_step(page):
    step = page.evaluate("currentEvent().step")
    child = next(frame for frame in page.frames if "/account?" in frame.url)
    child.wait_for_function(
        "step => typeof current === 'function' && current()?.screen && "
        "data?.trajectory?.[frame]?.step === step",
        arg=step,
        polling=100,
    )
    assert child.evaluate("!editable()")


def test_platform_drafts_budget_and_late_world_response(browser, mounted_server):
    root, _, _ = mounted_server
    page = browser.new_page(viewport={"width": 1024, "height": 900})
    try:
        page.goto(root + "/developer?platform=xiaohongshu")
        developer_ready(page, "xiaohongshu")
        page.locator("#goal").fill("小红书独立配置")
        page.locator("#agentCount").fill("5")
        page.locator("#saveConfig").evaluate("el => el.click()")
        page.locator('[data-platform="x"]').evaluate("el => el.click()")
        developer_ready(page, "x")
        assert page.locator("#goal").input_value() == ""
        assert "platform=x" in page.locator("#exploreLink").get_attribute("href")
        page.locator("#goal").fill("X 独立配置")
        page.locator('[data-platform="xiaohongshu"]').evaluate("el => el.click()")
        developer_ready(page, "xiaohongshu")
        assert page.locator("#goal").input_value() == "小红书独立配置"
        assert page.locator("#agentCount").input_value() == "5"
        page.locator("#agentCount").fill("32")
        page.locator("#ticks").fill("100")
        assert page.locator("#launchButton").is_disabled()
        assert "2400" in page.locator("#launchReadiness").inner_text()
        page.locator("#ticks").fill("1")
        assert page.locator("#launchButton").is_enabled()

        # Hold a successful X response until after Reddit has become current.
        page.evaluate("""() => {
            const original = window.fetch;
            window.releaseWorld = null;
            window.fetch = async (...args) => {
                const response = await original(...args);
                if (String(args[0]).includes('/api/world?platform=x'))
                    return new Promise(resolve => { window.releaseWorld = () => resolve(response); });
                return response;
            };
        }""")
        page.locator('[data-platform="x"]').evaluate("el => el.click()")
        page.wait_for_function("typeof releaseWorld === 'function'", polling=100)
        page.locator('[data-platform="reddit"]').evaluate("el => el.click()")
        developer_ready(page, "reddit")
        page.evaluate("releaseWorld()")
        page.wait_for_timeout(150)
        assert page.evaluate("world.preset") == "reddit"
        assert "platform=reddit" in page.locator("#exploreLink").get_attribute("href")
        assert page.locator("#goal").input_value() == ""
    finally:
        page.close()


def test_actor_positions_filter_and_mode_roundtrip(browser, mounted_server):
    root, _, _ = mounted_server
    run = make_run(
        root,
        recommendation={
            "slate_size": 6,
            "page_size": 3,
            "exploration_fraction": 0.2,
            "topic_weight": 1.75,
        },
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    try:
        page.goto(root + "/viewer?platform=xiaohongshu&run=" + run["run_id"])
        viewer_ready(page)
        focal = page.evaluate("selectedActor")
        page.evaluate("chooseFrame(2)")
        focal_step = page.evaluate("currentEvent().step")
        assert_native_step(page)
        other = int(
            page.locator('.actor-card[aria-pressed="false"]').first.get_attribute(
                "data-actor"
            )
        )
        page.locator(f'[data-actor="{other}"]').evaluate("el => el.click()")
        page.wait_for_function(
            "id => selectedActor === id && actorData?.observation?.user_id === id",
            arg=other,
            polling=100,
        )
        page.evaluate("chooseFrame(0)")
        page.locator(f'[data-actor="{focal}"]').evaluate("el => el.click()")
        page.wait_for_function(
            "([id,step]) => selectedActor === id && currentEvent()?.step === step && replayIndex >= 0",
            arg=[focal, focal_step],
            polling=100,
        )
        assert_native_step(page)
        page.locator("#timelineFilter").select_option("create")
        assert page.locator(".timeline-event").count() > 0
        page.locator(".timeline-event").first.evaluate("el => el.click()")
        page.wait_for_function("actionGroup(currentEvent()) === 'create'", polling=100)
        assert_native_step(page)
        assert "公开选择理由" in page.locator("#decisionDetail").inner_text()
        assert (
            page.locator('.stat-bar[aria-label="创作操作"]').get_attribute(
                "aria-valuenow"
            )
            != "0"
        )
        page.locator("#timelineFilter").select_option("failed")
        assert page.locator(".timeline-event").count() == 0
        assert "没有此类记录" in page.locator("#actionTimeline").inner_text()
        page.locator("#timelineFilter").select_option("all")
        selected_step = page.evaluate("currentEvent().step")
        page.reload()
        viewer_ready(page)
        page.wait_for_function(
            "step => currentEvent()?.step === step", arg=selected_step, polling=100
        )
        assert page.evaluate("selectedActor") == focal
        page.locator('[data-mode="developer"]').evaluate("el => el.click()")
        developer_ready(page, "xiaohongshu")
        page.locator('[data-mode="viewer"]').evaluate("el => el.click()")
        viewer_ready(page)
        assert page.evaluate("selectedRun") == run["run_id"]
        assert page.evaluate("selectedActor") == focal
        assert page.evaluate("currentEvent().step") == selected_step
        assert_native_step(page)
        second = make_run(root, name="Another isolated experiment")
        page.evaluate("void loadRun('" + second["run_id"] + "')")
        page.wait_for_function(
            "id => run?.run_id === id && actorData?.trajectory?.length > 0",
            arg=second["run_id"],
            polling=100,
        )
        page.evaluate("void loadRun('" + run["run_id"] + "')")
        page.wait_for_function(
            "([id,step]) => run?.run_id === id && currentEvent()?.step === step",
            arg=[run["run_id"], selected_step],
            polling=100,
        )
        page.locator("#reuseRun").evaluate("el => el.click()")
        developer_ready(page, "xiaohongshu")
        page.wait_for_function(
            "!document.getElementById('configOrigin').hidden", polling=100
        )
        assert page.locator("#agentCount").input_value() == "2"
        assert page.locator("#ticks").input_value() == "1"
        assert page.locator("#runName").input_value().endswith("副本")
        assert page.evaluate("experimentConfig().recommendation.topic_weight") == 1.75
        assert page.evaluate("experimentConfig().recommendation.page_size") == 3
        # Reuse loads configuration; it does not start another run.
        assert (
            len(requests.get(root + "/api/runs?platform=xiaohongshu").json()["runs"])
            == 2
        )
    finally:
        page.close()


def test_latest_wins_over_slow_history_and_archive_platform_is_correct(
    browser, mounted_server
):
    root, _, _ = mounted_server
    run = make_run(root, "x")
    page = browser.new_page(viewport={"width": 390, "height": 844})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        # The saved run determines the platform even when the incoming query is wrong.
        page.goto(root + "/viewer?platform=reddit&run=" + run["run_id"])
        viewer_ready(page)
        assert page.locator("#viewerPlatform").input_value() == "x"
        assert page.evaluate("selectedPlatform") == "x"
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert page.locator(
            ".viewer-toolbar select,.playback select,.timeline-filter select"
        ).evaluate_all(
            "fields => fields.every(field => parseFloat(getComputedStyle(field).fontSize) >= 16)"
        )
        page.evaluate("""() => {
            const original = window.fetch;
            window.releaseHistory = null;
            window.fetch = async (...args) => {
                const response = await original(...args);
                if (String(args[0]).includes('/api/run-session') && String(args[0]).includes('&step='))
                    return new Promise(resolve => { window.releaseHistory = () => resolve(response); });
                return response;
            };
            void chooseFrame(0);
        }""")
        page.wait_for_function("typeof releaseHistory === 'function'", polling=100)
        page.locator("#liveButton").evaluate("el => el.click()")
        page.evaluate("releaseHistory()")
        page.wait_for_timeout(150)
        assert page.evaluate("replayIndex") == -1
        assert page.locator("#liveButton").evaluate(
            "el => el.classList.contains('active')"
        )
        assert page.evaluate("currentEvent().step") == page.evaluate(
            "actorData.trajectory.at(-1).step"
        )
        assert "历史回放" in page.locator("#replayMode").inner_text()
        assert not page.locator(".platform-window").evaluate(
            "el => el.classList.contains('loading')"
        )
        assert not errors
    finally:
        page.close()


def test_live_controls_and_no_stale_ui_on_missing_run(browser, mounted_server):
    root, _, _ = mounted_server
    run = make_run(root, "reddit", ticks=3, steps_per_tick=3, pace_ms=400)
    page = browser.new_page(viewport={"width": 1024, "height": 900})
    try:
        page.goto(root + "/viewer?platform=reddit&run=" + run["run_id"])
        viewer_ready(page)
        page.locator("#pauseRun").evaluate("el => el.click()")
        page.wait_for_function("run?.status === 'paused'", polling=100)
        assert page.locator("#resumeRun").is_visible()
        page.locator("#resumeRun").evaluate("el => el.click()")
        page.wait_for_function("run?.status === 'running'", polling=100)
        page.locator("#stopRun").evaluate("el => el.click()")
        page.wait_for_function("run?.status === 'canceled'", polling=100)
        assert page.locator("#exportRun").is_enabled()
        page.evaluate("void loadRun('000000000000').catch(() => {})")
        page.wait_for_function(
            "document.getElementById('viewerEmptyTitle').textContent.includes('加载失败')",
            polling=100,
        )
        assert page.locator("#viewerWorkspace").is_hidden()
        assert page.locator("#exportRun").is_disabled()
        assert page.locator("#retryViewer").is_visible()
    finally:
        page.close()
