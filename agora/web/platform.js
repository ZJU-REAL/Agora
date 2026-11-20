/* One session controller for all native pages; replay renders persisted observations. */
const $ = (id) => document.getElementById(id);
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const urlParams = new URLSearchParams(location.search),
  runId = urlParams.get("run"),
  initialActor = urlParams.get("actor");
const frameCache = new Map();
let frameVersion = 0,
  sessionVersion = 0,
  userVersion = 0;
let selectedPlatform = urlParams.get("platform") || "xiaohongshu",
  world = {},
  data = null,
  sessionId = null,
  frame = -1,
  busy = false,
  pendingViewerStep = null,
  draftAssets = [],
  dialogAction = null;
const embedded = urlParams.get("embed") === "1";
if (embedded) document.body.classList.add("embedded");
function setBusy(value) {
  busy = value;
  $("userSelect").disabled = value;
  $("newSession").disabled = value || !!runId;
  $("platformRoot").setAttribute("aria-busy", String(value));
}
// Bounded, tab-local presentation state. Historical observations remain untouched.
const viewStates = new Map();
let renderedView = null,
  renderedSignature = null,
  discardFormState = false;
function viewKey(o) {
  return JSON.stringify([
    sessionId,
    runId ? "run" : frame < 0 ? "live" : "history",
    o.platform,
    o.screen,
    o.post?.post_id,
    o.profile?.user_id,
    o.profile?.tab,
    o.community?.name,
    o.feed_type,
    o.query,
    o.collection?.folder_id,
  ]);
}
function rememberView() {
  if (!renderedView) return;
  const root = $("platformRoot"),
    fields = {};
  if (!runId && !discardFormState) {
    root
      .querySelectorAll("input:not([type=file]),textarea,select")
      .forEach((el, i) => {
        fields[el.name || el.getAttribute("aria-label") || `field-${i}`] =
          el.value;
      });
  }
  viewStates.delete(renderedView);
  viewStates.set(renderedView, {
    y: scrollY,
    fields,
    assets: discardFormState ? [] : [...draftAssets],
    focus: root.contains(document.activeElement)
      ? {
          name: document.activeElement.name,
          label: document.activeElement.getAttribute("aria-label"),
          start: document.activeElement.selectionStart,
          end: document.activeElement.selectionEnd,
        }
      : null,
    scrolls: [
      ...root.querySelectorAll(
        ".note-scroll,.xhs-note,.xhs-categories,.reddit-sidebar",
      ),
    ].map((el) => [el.className, el.scrollTop, el.scrollLeft]),
  });
  while (viewStates.size > 8) viewStates.delete(viewStates.keys().next().value);
  discardFormState = false;
}
function restoreView(o, key, previous) {
  const state = viewStates.get(key),
    root = $("platformRoot");
  if (state && !runId && frame < 0) {
    root
      .querySelectorAll("input:not([type=file]),textarea,select")
      .forEach((el, i) => {
        const name = el.name || el.getAttribute("aria-label") || `field-${i}`;
        if (name in state.fields) el.value = state.fields[name];
      });
    if (o.screen === "studio") draftAssets = [...state.assets];
  }
  if (state)
    for (const [className, top, left] of state.scrolls) {
      const el = root.getElementsByClassName(className)[0];
      if (el) {
        el.scrollTop = top;
        el.scrollLeft = left;
      }
    }
  // Opening a note overlays its feed; it must not move the page behind it.
  const y =
    state?.y ??
    (o.platform === "xiaohongshu" && o.screen === "detail" ? scrollY : 0);
  window.scrollTo({ top: y, behavior: "instant" });
  if (o.screen === "studio") updateComposerSelection(o);
  root.querySelectorAll("form").forEach(updateInputState);
  if (key === previous && state?.focus) {
    const el = [...root.querySelectorAll("input,textarea,select")].find((el) =>
      state.focus.name
        ? el.name === state.focus.name
        : state.focus.label &&
          el.getAttribute("aria-label") === state.focus.label,
    );
    if (el) {
      el.focus({ preventScroll: true });
      if (el.setSelectionRange && state.focus.start !== null)
        try {
          el.setSelectionRange(state.focus.start, state.focus.end);
        } catch {}
    }
  }
  if (key !== previous && o.screen === "detail" && o.platform === "xiaohongshu")
    root.querySelector(".note-close")?.focus({ preventScroll: true });
}
function current() {
  return frame < 0
    ? data?.observation
    : frameCache.get(data?.trajectory?.[frame]?.step);
}
function editable() {
  return !runId && frame < 0 && current()?.status === "active" && !busy;
}
function actionButton(name, args, text, extraClass = "") {
  const available = current()?.available_actions?.[name];
  const zh = current()?.platform === "xiaohongshu";
  const names = {
    like_post: ["点赞", "Like"],
    unlike_post: ["取消点赞", "Unlike"],
    collect_post: ["收藏", "Save"],
    uncollect_post: ["取消收藏", "Unsave"],
    bookmark_post: ["收藏", "Bookmark"],
    unbookmark_post: ["取消收藏", "Remove bookmark"],
    open_post: ["打开内容与评论", "Open post and replies"],
    back: ["返回", "Go back"],
    view_media: ["切换图片", "View image"],
    open_notifications: ["通知", "Notifications"],
    add_to_collection: ["加入收藏专辑", "Add to collection"],
    repost: ["转发", "Repost"],
    undo_repost: ["取消转发", "Undo repost"],
    quote_post: ["引用", "Quote"],
    upvote_post: ["赞成", "Upvote"],
    downvote_post: ["反对", "Downvote"],
    clear_post_vote: ["取消投票", "Remove vote"],
    upvote_comment: ["赞成", "Upvote comment"],
    downvote_comment: ["反对", "Downvote comment"],
    clear_comment_vote: ["取消投票", "Remove comment vote"],
    like_comment: ["点赞评论", "Like comment"],
    unlike_comment: ["取消点赞评论", "Unlike comment"],
    view_profile: ["查看资料", "View profile"],
    open_studio: ["创作", "Compose a post"],
  };
  const label = names[name]?.[zh ? 0 : 1];
  return `<button type="button" class="${extraClass}" ${label ? `aria-label="${label}" title="${label}"` : ""} data-action="${name}" data-args="${esc(JSON.stringify(args || {}))}" ${!editable() || !available || extraClass.includes("carousel-end") ? "disabled" : ""}>${text}</button>`;
}
function toast(message) {
  $("toast").textContent = message;
  $("toast").classList.add("visible");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => $("toast").classList.remove("visible"), 3500);
}
async function api(path, value) {
  if (runId) {
    if (value !== undefined) throw Error("回放中的账号画面只读。");
    if (path === "/api/world")
      path = "/api/run-world?run=" + encodeURIComponent(runId);
    else if (path.startsWith("/api/session?"))
      path =
        path.replace("/api/session?", "/api/run-session?") +
        "&run=" +
        encodeURIComponent(runId);
  } else
    path +=
      (path.includes("?") ? "&" : "?") +
      "platform=" +
      encodeURIComponent(selectedPlatform);
  const response = await fetch(
    agoraPath(path),
    value !== undefined
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(value),
        }
      : {},
  );
  const result = await response.json();
  if (!response.ok) throw Error(result.error || "请求失败");
  return result;
}
async function applyFrame() {
  if (pendingViewerStep === null || !data) return;
  if (pendingViewerStep < 0) {
    frame = -1;
    return;
  }
  const step = pendingViewerStep,
    version = ++frameVersion;
  const index = data.trajectory.findIndex((e) => e.step === step);
  if (index < 0) return;
  if (!frameCache.has(step)) {
    const snapshot = await api(
      "/api/session?id=" + sessionId + "&step=" + step,
    );
    if (version !== frameVersion || step !== pendingViewerStep) return;
    frameCache.set(step, snapshot.observation);
    if (frameCache.size > 4) frameCache.delete(frameCache.keys().next().value);
  }
  frame = index;
}
function render() {
  if (!current()) return;
  document.title =
    { xiaohongshu: "小红书", x: "X", reddit: "Reddit" }[current().platform] +
    " · Agora";
  nativeRender(current());
  $("newSession").disabled = !!runId || busy;
}
async function loadSession(id, incremental = false) {
  const version = ++sessionVersion;
  const sid = Number(id),
    after =
      incremental && sessionId === sid ? data?.trajectory?.at(-1)?.step : 0;
  const next = await api(
    "/api/session?id=" + sid + "&compact=1" + (after ? "&after=" + after : ""),
  );
  if (version !== sessionVersion || (incremental && sessionId !== sid)) return;
  if (after) next.trajectory = [...data.trajectory, ...next.trajectory];
  if (sessionId !== sid) {
    frameCache.clear();
    ++frameVersion;
  }
  sessionId = sid;
  data = next;
  $("userSelect").value = next.observation.user_id;
  await applyFrame();
  if (!busy) render();
}
async function loadWorld() {
  world = await api("/api/world");
  $("sourceName").textContent = world.world_id;
  $("userSelect").innerHTML = world.users
    .map(
      (u) => `<option value="${u.user_id}">${esc(u.name || u.handle)}</option>`,
    )
    .join("");
}
async function startUser(id) {
  const version = ++userVersion;
  setBusy(true);
  try {
    const existing = world.sessions
      ?.filter((s) => s.user_id === id && s.status === "active")
      .at(-1);
    const session = existing || (await api("/api/session", { user_id: id }));
    if (version !== userVersion) return;
    frame = -1;
    await loadSession(session.session_id);
  } catch (e) {
    toast(e.message);
  } finally {
    if (version === userVersion) {
      setBusy(false);
      render();
    }
  }
}
async function act(type, args = {}) {
  if (!editable()) return;
  setBusy(true);
  try {
    const response = await api("/api/action", {
      session_id: sessionId,
      action_type: type,
      arguments: args,
    });
    if (response.result?.success === false)
      toast(response.result.error || "这个操作未完成");
    else if (
      ["publish_draft", "create_post", "reply_post", "create_comment"].includes(
        type,
      )
    ) {
      discardFormState = true;
      if (type === "publish_draft") viewStates.delete(renderedView);
    }
    await loadSession(sessionId);
    return response;
  } catch (e) {
    toast(e.message);
  } finally {
    setBusy(false);
    render();
  }
}
function dialog(title, fields, onSubmit) {
  $("dialogTitle").textContent = title;
  $("dialogFields").innerHTML = fields;
  dialogAction = onSubmit;
  $("actionDialog").showModal();
}
async function nativeAction(type, args = {}) {
  if (!editable()) return;
  const o = current();
  if (type === "refresh" && args.feed_type === "nearby" && !args.location) {
    dialog(
      "选择附近的城市",
      `<label>城市<input name="location" value="${esc(o.location || "")}" placeholder="例如：示例城市" required/></label>`,
      (v) => act(type, { ...args, location: v.location }),
    );
    return;
  }
  if (type === "create_collection") {
    dialog(
      "新建收藏专辑",
      '<label>专辑名称<input name="name" maxlength="80" required/></label>',
      (v) => act(type, { name: v.name }),
    );
    return;
  }
  if (type === "create_community") {
    dialog(
      "Create a community",
      '<label>Community name<input name="name" placeholder="r/your_community" required/></label><label>Title<input name="title" maxlength="300" required/></label><label>Description<textarea name="description"></textarea></label>',
      (v) => act(type, v),
    );
    return;
  }
  if (type === "edit_profile") {
    const zh = o.platform === "xiaohongshu";
    dialog(
      zh ? "编辑资料" : "Edit profile",
      `<label>${zh ? "名称" : "Name"}<input name="display_name" value="${esc(o.account.name)}" maxlength="80"/></label><label>${zh ? "简介" : "Bio"}<textarea name="bio">${esc(o.account.bio)}</textarea></label>`,
      (v) => act(type, v),
    );
    return;
  }
  if (type === "add_to_collection") {
    dialog(
      "加入收藏专辑",
      `<label>选择专辑<select name="folder_id">${o.collections.map((f) => `<option value="${f.folder_id}">${esc(f.name)}</option>`).join("")}</select></label>`,
      (v) => act(type, { ...args, folder_id: Number(v.folder_id) }),
    );
    return;
  }
  if (
    ["create_comment", "edit_comment", "edit_post", "quote_post"].includes(
      type,
    ) &&
    !args.content &&
    !args.body &&
    !args.quote_body
  ) {
    const label =
      type === "quote_post"
        ? "Quote this post"
        : type === "edit_post"
          ? o.platform === "xiaohongshu"
            ? "编辑笔记"
            : "Edit post"
          : type === "edit_comment"
            ? o.platform === "xiaohongshu"
              ? "编辑评论"
              : "Edit comment"
            : o.platform === "xiaohongshu"
              ? "回复"
              : "Reply";
    const comments = [...(o.post?.comments || [])];
    let comment;
    while (comments.length) {
      const next = comments.shift();
      if (next.comment_id === args.comment_id) {
        comment = next;
        break;
      }
      comments.push(...(next.replies || []));
    }
    dialog(
      label,
      `${type === "edit_post" ? `<label>${o.platform === "xiaohongshu" ? "标题" : "Title"}<input name="title" maxlength="${o.contract.title_limit}" value="${esc(o.post.title || "")}"/></label>` : ""}<label>${esc(label)}<textarea name="text" required>${type === "edit_post" ? esc(o.post.body) : type === "edit_comment" ? esc(comment?.content || "") : ""}</textarea></label>`,
      (v) =>
        act(type, {
          ...args,
          ...(type === "edit_post" ? { title: v.title } : {}),
          [type === "edit_post"
            ? "body"
            : type === "quote_post"
              ? "quote_body"
              : "content"]: v.text,
        }),
    );
    return;
  }
  if (type === "crosspost") {
    dialog(
      "Crosspost",
      `<label>Community<select name="community">${o.communities
        .filter((c) => c.visibility === "public" || c.joined)
        .map((c) => `<option value="${esc(c.name)}">${esc(c.name)}</option>`)
        .join("")}</select></label>`,
      (v) => act(type, { ...args, community: v.community }),
    );
    return;
  }
  if (type === "seek_video") {
    dialog(
      "视频位置",
      '<label>秒数<input type="number" name="seconds" min="0" required/></label>',
      (v) => act(type, { position_ms: Math.round(Number(v.seconds) * 1000) }),
    );
    return;
  }
  if (type === "approve_member") {
    dialog(
      "Approve a member",
      '<label>User ID<input type="number" name="user_id" min="1" required/></label>',
      (v) => act(type, { ...args, user_id: Number(v.user_id) }),
    );
    return;
  }
  return act(type, args);
}
async function nativeUpload(file) {
  if (!file || !editable()) return;
  if (file.size > 8 * 1024 * 1024) return toast("上传素材最大 8 MiB");
  setBusy(true);
  try {
    const encoded = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result.split(",")[1]);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
    await api("/api/assets", {
      user_id: current().user_id,
      filename: file.name,
      data_base64: encoded,
    });
    await loadSession(sessionId);
    toast("素材已上传");
  } catch (e) {
    toast(e.message);
  } finally {
    setBusy(false);
    render();
  }
}
function composerValues(form) {
  const o = current(),
    fields = Object.fromEntries(new FormData(form));
  const args = {
    body: fields.body || "",
    assets: draftAssets.map((asset_id) => ({ asset_id })),
  };
  if (o.platform !== "x") args.title = fields.title || "";
  if (o.platform === "reddit") {
    args.community = fields.community;
    if (fields.url) args.url = fields.url;
  }
  if (o.platform === "xiaohongshu") {
    args.topics = (fields.topics || "")
      .split(/[,，]/)
      .map((t) => t.trim())
      .filter(Boolean);
    if (fields.location) args.location = fields.location;
  }
  const videos = args.assets.filter(
    (s) =>
      o.asset_library.find((a) => a.asset_id === s.asset_id)?.media_type ===
      "video",
  );
  if (videos.length) {
    args.assets.forEach((s) => {
      if (
        o.asset_library.find((a) => a.asset_id === s.asset_id)?.media_type ===
        "image"
      )
        s.role = "cover";
    });
    args.post_type = "video";
  }
  return args;
}
function xTextLength(text) {
  const emoji =
    /(?:[0-9#*]\uFE0F?\u20E3|\p{Regional_Indicator}{2}|\p{Extended_Pictographic}(?:\uFE0F|\p{Emoji_Modifier})?(?:\u200D\p{Extended_Pictographic}(?:\uFE0F|\p{Emoji_Modifier})?)*)/gu;
  const weight = (s) =>
    [...s].reduce((n, c) => {
      const p = c.codePointAt(0);
      return (
        n +
        (p <= 4351 ||
        (p >= 8192 && p <= 8205) ||
        (p >= 8208 && p <= 8223) ||
        (p >= 8242 && p <= 8247)
          ? 1
          : 2)
      );
    }, 0);
  return text
    .normalize("NFC")
    .split(/(https?:\/\/[^\s<>]+)/)
    .reduce((sum, part) => {
      if (/^https?:\/\//.test(part)) return sum + 23;
      let cursor = 0,
        total = 0;
      for (const match of part.matchAll(emoji)) {
        total += weight(part.slice(cursor, match.index)) + 2;
        cursor = match.index + match[0].length;
      }
      return sum + total + weight(part.slice(cursor));
    }, 0);
}
function updateInputState(form) {
  const text = form.querySelector("textarea"),
    o = current();
  if (!text || !o) return;
  const count =
    o.platform === "x" ? xTextLength(text.value) : [...text.value].length;
  const limit = o.contract.body_limit,
    counter = form.querySelector("[data-character-count]");
  text.setCustomValidity(
    count > limit
      ? o.platform === "xiaohongshu"
        ? `正文不能超过 ${limit} 字`
        : `Use ${limit} characters or fewer`
      : "",
  );
  if (counter) {
    counter.textContent = `${count} / ${limit}`;
    counter.classList.toggle("over-limit", count > limit);
  }
  const empty =
    !text.value.trim() && !(form.id === "composeForm" && draftAssets.length);
  form
    .querySelectorAll("button[type=submit],button:not([type])")
    .forEach((button) => {
      const needsBody =
        form.matches("[data-inline-post],[data-comment]") || o.platform === "x";
      button.disabled = !editable() || count > limit || (needsBody && empty);
    });
}
function wireNative(o) {
  const root = $("platformRoot");
  root.onclick = (e) => {
    const copy = e.target.closest("[data-copy-link]");
    if (copy) {
      const link =
        location.origin +
        agoraPath(
          `/account?platform=${o.platform}&post=${copy.dataset.copyLink}`,
        );
      if (navigator.clipboard)
        navigator.clipboard
          .writeText(link)
          .then(() =>
            toast(o.platform === "xiaohongshu" ? "链接已复制" : "Link copied"),
          )
          .catch(() => toast(link));
      else toast(link);
      return;
    }
    const navToggle = e.target.closest("[data-toggle-nav]");
    if (navToggle) {
      const open = document.body.classList.toggle("nav-open");
      root
        .querySelector(".reddit-menu-toggle")
        ?.setAttribute("aria-expanded", String(open));
      return;
    }
    const filter = e.target.closest("[data-notification-filter]");
    if (filter) {
      root
        .querySelectorAll("[data-notification-filter]")
        .forEach((b) => b.classList.toggle("active", b === filter));
      root.querySelectorAll("[data-notification-kind]").forEach((row) => {
        row.hidden =
          filter.dataset.notificationFilter !== "all" &&
          !filter.dataset.notificationFilter
            .split(",")
            .includes(row.dataset.notificationKind);
      });
      return;
    }
    const button = e.target.closest("[data-action]");
    if (button) {
      e.stopPropagation();
      nativeAction(
        button.dataset.action,
        JSON.parse(button.dataset.args || "{}"),
      );
      return;
    }
    const card = e.target.closest("[data-post]");
    if (
      card &&
      !e.target.closest("a,input,textarea,summary,form,button,details,video")
    )
      act("open_post", { post_id: Number(card.dataset.post) });
    const pick = e.target.closest("[data-pick]");
    if (pick && editable()) {
      const id = pick.dataset.pick;
      draftAssets = draftAssets.includes(id)
        ? draftAssets.filter((v) => v !== id)
        : [...draftAssets, id];
      pick.classList.toggle("selected", draftAssets.includes(id));
      updateComposerSelection(o);
    }
    const move = e.target.closest("[data-move]");
    if (move && editable()) {
      const from = draftAssets.indexOf(move.dataset.asset),
        to = from + Number(move.dataset.move);
      if (from >= 0 && to >= 0 && to < draftAssets.length) {
        [draftAssets[from], draftAssets[to]] = [
          draftAssets[to],
          draftAssets[from],
        ];
        updateComposerSelection(o);
      }
    }
  };
  root.oninput = (e) => {
    if (e.target.form) updateInputState(e.target.form);
  };
  root.onkeydown = (e) => {
    const note = root.querySelector(".xhs-note-overlay");
    if (note && e.key === "Tab") {
      const controls = [
        ...note.querySelectorAll(
          "button:not(:disabled),input,textarea,select,summary,a[href],video[controls]",
        ),
      ].filter(
        (el) =>
          el.getClientRects().length &&
          !el.closest("details:not([open]) > div"),
      );
      const first = controls[0],
        last = controls.at(-1);
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last?.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first?.focus();
      }
    }
    const card = e.target.closest("[data-post]");
    if (card === e.target && ["Enter", " "].includes(e.key)) {
      e.preventDefault();
      act("open_post", { post_id: Number(card.dataset.post) });
    }
  };
  root.querySelectorAll("form[data-search]").forEach(
    (form) =>
      (form.onsubmit = (e) => {
        e.preventDefault();
        const query = form.querySelector("input").value.trim();
        if (query)
          act("search", {
            query,
            ...(o.platform === "reddit" && o.community
              ? { community: o.community.name }
              : {}),
          });
      }),
  );
  root.querySelectorAll("form[data-comment]").forEach(
    (form) =>
      (form.onsubmit = (e) => {
        e.preventDefault();
        const body = form.querySelector("textarea,input").value;
        if (body.trim())
          act(
            o.platform === "x" ? "reply_post" : "create_comment",
            o.platform === "x"
              ? { post_id: o.post.post_id, body }
              : { post_id: o.post.post_id, content: body },
          );
      }),
  );
  const inline = root.querySelector("form[data-inline-post]");
  if (inline)
    inline.onsubmit = (e) => {
      e.preventDefault();
      const body = inline.querySelector("textarea").value;
      if (body.trim() && inline.reportValidity()) act("create_post", { body });
    };
  const compose = root.querySelector("#composeForm");
  if (compose) {
    draftAssets = (o.draft?.assets || []).map((s) => s.asset_id);
    compose.onsubmit = async (e) => {
      e.preventDefault();
      if (!editable()) return;
      const args = composerValues(compose);
      const published = e.submitter?.dataset.publish === "1";
      const saved = await act("save_draft", args);
      if (published && saved && saved.result?.success !== false)
        await act("publish_draft");
    };
    updateComposerSelection(o);
  }
  const upload = root.querySelector("#nativeUpload");
  if (upload) upload.onchange = (e) => nativeUpload(e.target.files[0]);
  root.querySelectorAll("[data-sort]").forEach(
    (select) =>
      (select.onchange = () =>
        act(
          o.screen === "community" ? "view_community" : "refresh",
          o.screen === "community"
            ? { community: o.community.name, sort: select.value }
            : {
                feed_type: o.feed_type,
                sort: select.value,
                time_range: o.time_range || "all",
              },
        )),
  );
  root.querySelectorAll("[data-time-range]").forEach(
    (select) =>
      (select.onchange = () =>
        act(
          o.screen === "community" ? "view_community" : "refresh",
          o.screen === "community"
            ? {
                community: o.community.name,
                sort: "top",
                time_range: select.value,
              }
            : {
                feed_type: o.feed_type,
                sort: "top",
                time_range: select.value,
              },
        )),
  );
  root.querySelectorAll("video").forEach((video) => {
    video.onloadedmetadata = () => {
      video.currentTime = Math.min(
        video.duration || 0,
        (o.post?.video_position_ms || 0) / 1000,
      );
    };
  });
  root.querySelectorAll("form").forEach(updateInputState);
  if (!editable()) {
    root
      .querySelectorAll("input,textarea")
      .forEach((el) => (el.readOnly = true));
    root.querySelectorAll("select").forEach((el) => (el.disabled = true));
  }
}
function updateComposerSelection(o) {
  const selected = $("selectedAssets");
  if (selected)
    selected.innerHTML = draftAssets
      .map((id, index) => {
        const asset = o.asset_library.find((a) => a.asset_id === id);
        return asset
          ? `<div class="selected-asset">${nativeMedia(asset)}<span>${index + 1}</span><button type="button" aria-label="Move earlier" data-move="-1" data-asset="${esc(id)}" ${!editable() || index === 0 ? "disabled" : ""}>${pi("back")}</button><button type="button" aria-label="Move later" data-move="1" data-asset="${esc(id)}" ${!editable() || index === draftAssets.length - 1 ? "disabled" : ""}>${pi("forward")}</button><button type="button" class="remove-asset" aria-label="Remove media" data-pick="${esc(id)}" ${!editable() ? "disabled" : ""}>${pi("close")}</button></div>`
          : "";
      })
      .join("");
  $("platformRoot")
    .querySelectorAll(".library-asset")
    .forEach((el) => {
      const selected = draftAssets.includes(el.dataset.pick);
      el.classList.toggle("selected", selected);
      el.setAttribute("aria-pressed", String(selected));
    });
  const form = $("composeForm");
  if (form) updateInputState(form);
}
document.addEventListener("click", (e) => {
  document
    .querySelectorAll(".p-post-menu[open],.x-repost-menu[open]")
    .forEach((menu) => {
      if (!menu.contains(e.target)) menu.open = false;
    });
});
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape" || $("actionDialog").open) return;
  document
    .querySelectorAll("details[open]")
    .forEach((menu) => (menu.open = false));
  document.body.classList.remove("nav-open");
  if (current()?.platform === "xiaohongshu" && current()?.screen === "detail")
    act("back");
});
window.addEventListener("message", async (e) => {
  if (
    !embedded ||
    !runId ||
    e.origin !== location.origin ||
    e.source !== parent ||
    e.data?.type !== "agora:frame" ||
    e.data.run !== runId ||
    !Number.isInteger(e.data.step)
  )
    return;
  pendingViewerStep = e.data.step;
  await applyFrame();
  render();
});
$("actionForm").onsubmit = async (e) => {
  e.preventDefault();
  if (!editable() || $("dialogSubmit").disabled) return;
  const value = Object.fromEntries(new FormData(e.target));
  $("dialogSubmit").disabled = true;
  try {
    const result = dialogAction && (await dialogAction(value));
    if (result && result.result?.success !== false) $("actionDialog").close();
  } finally {
    $("dialogSubmit").disabled = false;
  }
};
document
  .querySelectorAll("[data-dialog-close]")
  .forEach((b) => (b.onclick = () => $("actionDialog").close()));
$("newSession").onclick = async () => {
  if (runId || busy) return;
  setBusy(true);
  try {
    const next = await api("/api/session", {
      user_id: Number($("userSelect").value),
    });
    frame = -1;
    pendingViewerStep = null;
    await loadWorld();
    await loadSession(next.session_id);
  } catch (e) {
    toast(e.message);
  } finally {
    setBusy(false);
    render();
  }
};
$("userSelect").onchange = () => startUser(Number($("userSelect").value));
async function main() {
  try {
    $("developerLink").href = agoraPath(
      "/developer?platform=" + selectedPlatform,
    );
    $("viewerLink").href = agoraPath("/viewer?platform=" + selectedPlatform);
    await loadWorld();
    if (runId) {
      const visit = world.sessions
        .filter((s) => !initialActor || s.user_id === Number(initialActor))
        .at(-1);
      if (visit) {
        $("userSelect").value = visit.user_id;
        await loadSession(visit.session_id);
      } else {
        $("platformRoot").innerHTML =
          '<div class="p-loading">等待账号开始行动…</div>';
      }
      setInterval(async () => {
        if (document.hidden || busy) return;
        try {
          if (sessionId) await loadSession(sessionId, true);
          else {
            await loadWorld();
            const visit = world.sessions.find(
              (s) => !initialActor || s.user_id === Number(initialActor),
            );
            if (visit) await loadSession(visit.session_id);
          }
        } catch (e) {
          toast(e.message);
        }
      }, 2000);
    } else {
      const user =
        world.users.find((u) => u.handle === "reader") || world.users.at(-1);
      if (!user) {
        $("platformRoot").innerHTML =
          '<div class="p-loading">当前数据集没有账号，请先导入数据。</div>';
        return;
      }
      $("userSelect").value = user.user_id;
      await startUser(user.user_id);
      if (urlParams.get("post"))
        await act("open_post", { post_id: Number(urlParams.get("post")) });
    }
  } catch (e) {
    toast(e.message);
    $("platformRoot").innerHTML =
      '<div class="p-loading">平台暂时无法加载，请稍后重试。</div>';
  }
}
main();
