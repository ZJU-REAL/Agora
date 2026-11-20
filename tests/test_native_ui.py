"""Chromium regressions for native scrolling, local drafts and exact replay.

Run with Playwright installed; AGORA_CHROMIUM can select a local browser binary.
The fixture creates a tiny isolated world and launches one browser at a time.
"""

import os
from pathlib import Path

import pytest
import test_iap_console

from agora.platforms import x_weighted_length

playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def mounted_server(tmp_path_factory):
    yield from test_iap_console.mounted_server.__wrapped__(tmp_path_factory)


@pytest.fixture(scope="module")
def browser():
    executable = os.environ.get("AGORA_CHROMIUM")
    if not executable:
        matches = sorted(
            Path.home().glob(
                ".cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"
            )
        )
        if matches:
            executable = str(matches[-1])
    if not executable:
        pytest.skip("Install Chromium or set AGORA_CHROMIUM to run UI regressions")
    with playwright.sync_playwright() as driver:
        instance = driver.chromium.launch(
            executable_path=executable,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-features=PaintHolding",
            ],
        )
        yield instance
        instance.close()


def ready(page):
    page.wait_for_function("current()?.status === 'active' && !busy", polling=100)


def action(page, name, args=None):
    page.evaluate("([name,args]) => act(name,args)", [name, args or {}])
    ready(page)


@pytest.mark.parametrize("platform", ["xiaohongshu", "x", "reddit"])
def test_native_chrome_scroll_and_draft_survive_refresh(
    browser, mounted_server, platform
):
    root, _, _ = mounted_server
    page = browser.new_page(viewport={"width": 1440, "height": 640})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.goto(root + "/account?platform=" + platform)
        ready(page)
        action(
            page,
            "refresh",
            {"feed_type": "for_you" if platform != "xiaohongshu" else "discover"},
        )
        page.evaluate("window.scrollBy(0, 450)")
        page.wait_for_function("scrollY > 50", polling=100)
        geometry = page.evaluate("""() => {
            const rect = s => document.querySelector(s)?.getBoundingClientRect();
            return { shell: rect('.sandbox-bar').top,
                header: rect('.xhs-header,.x-timeline-header,.reddit-header').top,
                join: rect('.x-feed-tabs') ? rect('.x-feed-tabs').top - rect('.x-sticky-heading').bottom : 0 };
        }""")
        assert geometry == {"shell": 0, "header": 38, "join": 0}
        # Polling an unchanged observation must retain the actual DOM, not just its look.
        assert page.evaluate("""async () => {
            const before = document.querySelector('#platformRoot').firstElementChild;
            await loadSession(sessionId);
            return before === document.querySelector('#platformRoot').firstElementChild;
        }""")
        y = page.evaluate("scrollY")
        post = page.evaluate("current().cards[0].post_id")
        action(
            page,
            "upvote_post" if platform == "reddit" else "like_post",
            {"post_id": post},
        )
        assert abs(page.evaluate("scrollY") - y) <= 2
        action(page, "open_studio")
        form = page.locator("#composeForm")
        form.locator("textarea[name=body]").fill("Unsaved writing 保留文字 👩🏽‍💻")
        title = form.locator("input[name=title]")
        if title.count():
            title.fill("Draft title")
        page.evaluate("document.querySelector('[data-pick]').click()")
        selected = page.evaluate("[...draftAssets]")
        # Uploading reloads the library and used to lose both text and media selection.
        from PIL import Image

        fixture = mounted_server[2] / f"upload-{platform}.png"
        Image.new("RGB", (17, 19), "#a8b9c2").save(fixture)
        page.locator("#nativeUpload").set_input_files(str(fixture))
        page.wait_for_function("!busy && current().library_total >= 3", polling=100)
        assert (
            form.locator("textarea[name=body]").input_value()
            == "Unsaved writing 保留文字 👩🏽‍💻"
        )
        assert page.evaluate("draftAssets") == selected
        if title.count():
            assert title.input_value() == "Draft title"
        action(page, "view_asset_library", {"offset": 0})
        assert (
            form.locator("textarea[name=body]")
            .input_value()
            .startswith("Unsaved writing")
        )
        assert page.evaluate("draftAssets") == selected
        # Save and publish the exact visible text through the real native form.
        page.evaluate(
            "document.querySelector('#composeForm').requestSubmit(document.querySelector('[data-publish]'))"
        )
        page.wait_for_function("!busy && current().screen !== 'studio'", polling=100)
        body = page.evaluate("current().post?.body || current().cards[0].body")
        assert body == "Unsaved writing 保留文字 👩🏽‍💻"
        if platform == "xiaohongshu":
            action(page, "back")
            action(page, "open_post", {"post_id": post})
            page.evaluate("document.querySelector('.note-scroll').scrollTop = 75")
            assert page.evaluate("document.body.classList.contains('note-open')")
            assert page.evaluate("getComputedStyle(document.body).overflow") == "hidden"
            page.keyboard.press("Escape")
            ready(page)
            assert not page.evaluate("document.body.classList.contains('note-open')")
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert not errors
    finally:
        page.close()


def test_mobile_reddit_navigation_and_x_weighted_input(browser, mounted_server):
    root, _, _ = mounted_server
    page = browser.new_page(viewport={"width": 390, "height": 844})
    try:
        page.goto(root + "/account?platform=reddit")
        ready(page)
        page.evaluate("document.querySelector('[data-toggle-nav]').click()")
        assert page.locator(".reddit-sidebar").is_visible()
        page.evaluate(
            "document.querySelector('.reddit-sidebar [data-action=list_communities]').click()"
        )
        ready(page)
        assert page.evaluate("current().screen") == "communities"
        assert not page.locator(".reddit-sidebar").is_visible()
        page.goto(root + "/account?platform=x")
        ready(page)
        action(page, "refresh", {"feed_type": "for_you"})
        assert page.locator(".x-mobile-post").is_visible()
        for text in [
            "中文" * 71,
            "👩🏽‍💻" * 141,
            "🇨🇳",
            "1️⃣",
            "https://example.org/" + "x" * 300,
            "e\u0301",
        ]:
            assert page.evaluate("xTextLength", text) == x_weighted_length(text)
        inline = page.locator("[data-inline-post]")
        assert inline.locator("button[type=submit]").is_disabled()
        inline.locator("textarea").fill("中文" * 71)
        assert inline.locator("button[type=submit]").is_disabled()
        inline.locator("textarea").fill("Ready to post")
        assert inline.locator("button[type=submit]").is_enabled()
    finally:
        page.close()


def test_historical_frame_is_read_only_and_unchanged_poll_keeps_dom(
    browser, mounted_server
):
    root, _, _ = mounted_server
    page = browser.new_page(viewport={"width": 800, "height": 700})
    try:
        page.goto(root + "/account?platform=xiaohongshu&embed=1")
        ready(page)
        action(page, "open_studio")
        action(page, "save_draft", {"title": "历史标题", "body": "历史正文"})
        step = page.evaluate("data.trajectory.at(-1).step")
        action(page, "save_draft", {"title": "新标题", "body": "新正文"})
        page.evaluate(
            "async step => {pendingViewerStep=step; await applyFrame(); render();}",
            step,
        )
        assert page.locator("input[name=title]").input_value() == "历史标题"
        assert page.locator("input[name=title]").get_attribute("readonly") is not None
        assert page.locator("textarea[name=body]").input_value() == "历史正文"
        assert page.locator("#sandboxBar").is_hidden()
        assert page.locator("[data-publish]").is_disabled()
        assert page.evaluate("""async () => {
            const before = document.querySelector('#composeForm');
            await loadSession(sessionId, true);
            return before === document.querySelector('#composeForm');
        }""")
    finally:
        page.close()


def test_mobile_workspace_primary_action_and_models_are_reachable(
    browser, mounted_server
):
    root, _, _ = mounted_server
    page = browser.new_page(viewport={"width": 390, "height": 844})
    try:
        page.goto(root + "/developer")
        page.wait_for_function("world?.users?.length > 0", polling=100)
        bounds = page.locator("#launchButton").bounding_box()
        assert bounds and bounds["y"] + bounds["height"] <= 844
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert page.get_by_role("spinbutton", name="参与 agent 总数").count() == 1
        page.locator("#mobileModels").evaluate("el => el.click()")
        assert page.get_by_role("dialog", name="连接你的模型").is_visible()
        assert page.locator("#providerProxy").is_visible()
        page.locator("#providerKey").fill("not-a-real-key")
        page.locator("#closeModels").evaluate("el => el.click()")
        assert page.locator("#providerKey").input_value() == ""
        assert page.locator("#goal").input_value() == ""
        assert page.locator("#agentCount").get_attribute("max") == "32"
    finally:
        page.close()


def test_workspace_launch_and_expand_preserve_readonly_native_frame(
    browser, mounted_server
):
    root, _, _ = mounted_server
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    try:
        page.goto(root + "/developer")
        page.wait_for_function("world?.users?.length > 0", polling=100)
        page.locator("#agentCount").fill("2")
        page.locator("#ticks").fill("1")
        page.locator("#steps").fill("2")
        page.locator(".advanced-settings summary").evaluate("el => el.click()")
        page.locator("#pace").select_option("0")
        page.locator("#runName").fill("Workspace browser regression")
        page.locator("#launchButton").evaluate("el => el.click()")
        page.wait_for_url("**/viewer?**")
        page.wait_for_function("actorData?.trajectory?.length >= 2", polling=100)
        page.evaluate("chooseFrame(0)")
        child = next(frame for frame in page.frames if "/account?" in frame.url)
        child.wait_for_function("current()?.screen && frame >= 0", polling=100)
        assert page.locator('.actor-card[aria-pressed="true"]').count() == 1
        step = page.evaluate("currentEvent().step")
        assert child.evaluate("!editable()")
        assert page.evaluate("""() => {
            window.agoraTestFrame = document.querySelector('#accountFrame');
            const before = agoraTestFrame.clientWidth;
            document.querySelector('#expandStage').click();
            return agoraTestFrame === document.querySelector('#accountFrame') && agoraTestFrame.clientWidth > before;
        }""")
        assert page.evaluate("currentEvent().step") == step
        assert child.evaluate("data.trajectory[frame].step") == step
        page.locator("#expandStage").evaluate("el => el.click()")
        assert page.evaluate(
            "agoraTestFrame === document.querySelector('#accountFrame')"
        )
        assert not page.locator("#viewerWorkspace").evaluate(
            "el => el.classList.contains('stage-expanded')"
        )
        assert child.locator('link[href$="native.css"]').count() == 1
        assert child.locator('link[href$="studio.css"]').count() == 0
        target = page.locator('.actor-card[aria-pressed="false"]').first.get_attribute(
            "data-actor"
        )
        page.locator(f'[data-actor="{target}"]').evaluate("el => el.click()")
        page.wait_for_function(
            "actorData?.observation?.user_id === selectedActor", polling=100
        )
        assert (
            page.locator(f'[data-actor="{target}"]').get_attribute("aria-pressed")
            == "true"
        )
        assert page.locator('.actor-card[aria-pressed="true"]').count() == 1
        # Moving the playhead changes selection without rebuilding the timeline list.
        assert page.evaluate("""async () => {
            const before = document.querySelector('#actionTimeline').firstElementChild;
            await chooseFrame(1);
            return before === document.querySelector('#actionTimeline').firstElementChild;
        }""")
    finally:
        page.close()
