"""Real configuration, launch, reuse and empty-source journeys in Chromium."""

import os
import signal
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
import requests
import test_native_ui

from agora.world import open_world


@contextmanager
def serve(root, bootstrap):
    if not bootstrap:
        open_world("modes", root).close()
    ports = []
    for _ in range(2):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            ports.append(sock.getsockname()[1])
    args = [
        sys.executable,
        "-m",
        "agora",
        "--data-root",
        str(root),
        "serve",
        "modes",
        "--port",
        str(ports[0]),
        "--api-port",
        str(ports[1]),
        "--base-path",
        "/agora",
    ]
    if bootstrap:
        args.append("--bootstrap")
    process = subprocess.Popen(
        args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True
    )
    console = f"http://127.0.0.1:{ports[0]}/agora"
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                if requests.get(console + "/api/platforms", timeout=1).ok:
                    break
            except requests.RequestException:
                pass
            if process.poll() is not None:
                pytest.fail(process.stderr.read())
            time.sleep(0.1)
        else:
            pytest.fail("Mode test server did not start")
        yield console, f"http://127.0.0.1:{ports[1]}"
    finally:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


@pytest.fixture(scope="module")
def modes_server(tmp_path_factory):
    with serve(tmp_path_factory.mktemp("mode-ui"), True) as server:
        yield server


@pytest.fixture(scope="module")
def empty_server(tmp_path_factory):
    with serve(tmp_path_factory.mktemp("empty-mode-ui"), False) as server:
        yield server


@pytest.fixture(scope="module")
def browser():
    yield from test_native_ui.browser.__wrapped__()


def ready(page):
    page.wait_for_function(
        "world && !developerLoading && !capacity.active_runs", polling=100
    )


def launch(page):
    page.locator("#agentCount").fill("1")
    page.locator("#ticks").fill("1")
    page.locator("#steps").fill("4")
    page.locator(".advanced-settings summary").evaluate("el => el.click()")
    page.locator("#pace").select_option("0")
    page.locator("#launchButton").evaluate("el => el.click()")
    page.wait_for_url("**/viewer?**")
    page.wait_for_function(
        "run?.status === 'completed' && actorData?.trajectory?.length > 0", polling=100
    )
    return page.evaluate("run")


@pytest.mark.parametrize("platform", ["xiaohongshu", "x", "reddit"])
@pytest.mark.parametrize(
    "mode,start,preload",
    [
        ("background", "existing", 0),
        ("background", "new", 0),
        ("background", "new", 1),
        ("ai_only", "new", 0),
        ("ai_only", "new", 1),
    ],
)
def test_modes_launch_select_focal_and_reuse(
    browser, modes_server, platform, mode, start, preload
):
    root, _ = modes_server
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    try:
        page.goto(root + "/developer?platform=" + platform)
        ready(page)
        template = page.evaluate(
            "world.users.find(u => u.user_id !== 1 && u.seedable_posts > 0)?.user_id || world.users.find(u => u.seedable_posts > 0).user_id"
        )
        before = requests.get(
            root + "/api/world", params={"platform": platform}, timeout=10
        ).json()
        page.locator("#worldMode").select_option(mode)
        page.locator("#focalStart").select_option(start)
        if start == "new":
            page.locator("#newAccountName").fill("起号与运营验收")
            page.locator("#starterPosts").fill(str(preload))
            if preload:
                page.locator("#focalUser").select_option(str(template))
            assert page.locator("#newAccountFields").is_visible()
        else:
            page.locator("#focalUser").select_option(str(template))
            assert page.locator("#newAccountFields").is_hidden()
        page.locator("#goal").fill("受测任务")
        page.evaluate("focalProfileBase = {tone:['specific']}; rememberDraft()")
        page.locator("#saveConfig").evaluate("el => el.click()")
        page.reload()
        ready(page)
        assert page.locator("#worldMode").input_value() == mode
        assert page.locator("#focalStart").input_value() == start
        if preload:
            assert page.locator("#starterPosts").input_value() == "1"
        capture = os.environ.get("AGORA_MODE_SCREENSHOTS")
        if capture and platform == "xiaohongshu" and start == "new":
            folder = Path(capture)
            folder.mkdir(parents=True, exist_ok=True)
            page.evaluate("document.fonts.ready")
            page.evaluate("window.scrollTo(0,0)")
            page.screenshot(
                path=str(folder / f"{mode}-preload-{preload}-desktop.png"),
                full_page=True,
            )
        page.set_viewport_size({"width": 390, "height": 844})
        page.evaluate("window.scrollTo(0,0)")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        mode_bounds = page.locator("#worldMode").bounding_box()
        assert (
            mode_bounds
            and mode_bounds["y"] >= 0
            and mode_bounds["y"] + mode_bounds["height"] <= 844
        )
        assert (
            page.locator("#launchButton").bounding_box()["y"]
            + page.locator("#launchButton").bounding_box()["height"]
            <= 844
        )
        if capture and platform == "xiaohongshu" and start == "new":
            page.evaluate("window.scrollTo(0,0)")
            page.screenshot(
                path=str(folder / f"{mode}-preload-{preload}-mobile.png"),
                full_page=True,
            )
        run = launch(page)
        config, state = run["config"], run["config"]["initial_state"]
        assert config["world_mode"] == mode and config["focal_start"] == start
        assert config["focal_profile"] == {"tone": ["specific"]}
        assert page.evaluate("selectedActor") == config["focal_user_id"]
        assert state["active_accounts"] == 1
        if start == "new":
            assert state["focal_posts"] == preload
        else:
            assert state["focal_posts"] >= next(
                u["seedable_posts"] for u in before["users"] if u["user_id"] == template
            )
        if mode == "ai_only":
            assert state["world_users"] == 1 and state["posts"] == preload
        else:
            assert state["world_users"] == before["user_count"] + (start == "new")
        assert ("纯 AI 世界" if mode == "ai_only" else "背景世界") in page.locator(
            "#viewerInitialState"
        ).inner_text()
        assert run["failure_count"] == 0, run.get("report")
        page.locator("#reuseRun").evaluate("el => el.click()")
        page.wait_for_url("**/developer?**")
        page.wait_for_function(
            'world && !developerLoading && !$("configOrigin").hidden', polling=100
        )
        assert page.locator("#worldMode").input_value() == mode
        assert page.locator("#focalStart").input_value() == start
        expected_source = template if (preload or start == "existing") else ""
        assert page.locator("#focalUser").input_value() == str(expected_source)
        assert page.locator("#goal").input_value() == "受测任务"
        assert page.evaluate("focalProfileBase") == {"tone": ["specific"]}
        after = requests.get(
            root + "/api/world", params={"platform": platform}, timeout=10
        ).json()
        assert (after["user_count"], after["post_count"]) == (
            before["user_count"],
            before["post_count"],
        )
        assert not errors
    finally:
        page.close()


@pytest.mark.parametrize("platform", ["xiaohongshu", "x", "reddit"])
def test_empty_source_ui_launches_without_hidden_demo_posts(
    browser, empty_server, platform
):
    root, _ = empty_server
    page = browser.new_page(viewport={"width": 390, "height": 844})
    try:
        page.goto(root + "/developer?platform=" + platform)
        ready(page)
        assert page.locator("#launchButton").is_disabled()
        page.locator("#focalStart").select_option("new")
        assert page.locator("#launchButton").is_enabled()
        run = launch(page)
        assert run["config"]["initial_state"]["world_users"] == 1
        assert run["config"]["initial_state"]["posts"] == 0
        assert run["failure_count"] == 0
    finally:
        page.close()


def test_source_search_beyond_picker_and_stale_response(browser, modes_server):
    root, native = modes_server
    target = None
    for i in range(205):
        response = requests.post(
            native + "/v1/accounts",
            json={
                "platform": "x",
                "handle": f"outside_{i}",
                "display_name": f"Searchable account {i}",
            },
            timeout=10,
        )
        assert response.status_code == 201, response.text
        target = response.json()["user_id"]
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    try:
        page.goto(root + "/developer?platform=x")
        ready(page)
        assert page.locator("#sourceSearchField").is_visible()
        assert page.evaluate("world.users.length") == 200
        page.locator("#sourceAccountQuery").fill("outside_204")
        page.wait_for_function("sourceResults.length === 1", polling=100)
        page.locator("#focalUser").select_option(str(target))
        page.locator("#saveConfig").evaluate("el => el.click()")
        page.reload()
        ready(page)
        page.wait_for_function("sourceSelectedExtra !== null", polling=100)
        assert page.locator("#focalUser").input_value() == str(target)
        # A response from the old platform must not replace the next platform's picker.
        page.route(
            "**/api/source-users?**",
            lambda route: route.fulfill(
                json={
                    "users": [
                        {
                            "user_id": 99999,
                            "handle": "stale",
                            "name": "Stale result",
                            "seedable_posts": 0,
                        }
                    ]
                }
            ),
        )
        page.evaluate("developerVersion++; searchSourceAccounts(); developerVersion++")
        page.wait_for_timeout(300)
        assert page.evaluate("sourceAccounts().some(u => u.user_id === 99999)") is False
        assert (
            requests.get(
                root + "/api/source-users",
                params={"platform": "x", "id": target},
                timeout=10,
            ).json()["users"][0]["user_id"]
            == target
        )
        assert (
            requests.get(
                root + "/api/source-users", params={"query": "a" * 81}, timeout=10
            ).status_code
            == 400
        )
        assert requests.get(native + "/api/source-users", timeout=10).status_code == 403
    finally:
        page.close()


def test_legacy_reuse_resets_new_modes_and_retains_shared_tasks(browser, modes_server):
    root, _ = modes_server
    page = browser.new_page()
    try:
        page.goto(root + "/developer?platform=x")
        ready(page)
        page.locator("#worldMode").select_option("ai_only")
        page.locator("#starterPosts").fill("2")
        page.evaluate("applyConfiguration({user_ids:[1,2],goal:'Legacy shared task'})")
        assert page.locator("#worldMode").input_value() == "background"
        assert page.locator("#focalStart").input_value() == "existing"
        assert page.locator("#focalUser").input_value() == "1"
        assert page.locator("#starterPosts").input_value() == "0"
        assert page.locator("#backgroundTasks").input_value() == "Legacy shared task"
    finally:
        page.close()
