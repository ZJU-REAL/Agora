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
let frameVersion = 0;
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
  return `<button type="button" class="${extraClass}" data-action="${name}" data-args="${esc(JSON.stringify(args || {}))}" ${!editable() || !available ? "disabled" : ""}>${text}</button>`;
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
  const sid = Number(id),
    after =
      incremental && sessionId === sid ? data?.trajectory?.at(-1)?.step : 0;
  const next = await api(
    "/api/session?id=" + sid + "&compact=1" + (after ? "&after=" + after : ""),
  );
  if (after) next.trajectory = [...data.trajectory, ...next.trajectory];
  sessionId = sid;
  data = next;
  await applyFrame();
  render();
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
  busy = true;
  try {
    const existing = world.sessions
      ?.filter((s) => s.user_id === id && s.status === "active")
      .at(-1);
    const session = existing || (await api("/api/session", { user_id: id }));
    frame = -1;
    await loadSession(session.session_id);
  } catch (e) {
    toast(e.message);
  } finally {
    busy = false;
    render();
  }
}
async function act(type, args = {}) {
  if (!editable()) return;
  busy = true;
  try {
    const response = await api("/api/action", {
      session_id: sessionId,
      action_type: type,
      arguments: args,
    });
    if (response.result?.success === false)
      toast(response.result.error || "这个操作未完成");
    await loadSession(sessionId);
    return response;
  } catch (e) {
    toast(e.message);
  } finally {
    busy = false;
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
  if (type === "share_post") {
    const link =
      location.origin +
      agoraPath("/account?platform=" + o.platform + "&post=" + args.post_id);
    if (navigator.clipboard) await navigator.clipboard.writeText(link);
    toast(o.platform === "xiaohongshu" ? "笔记链接已复制" : "Link copied");
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
    dialog(
      o.platform === "x" ? "Edit profile" : "编辑资料",
      `<label>名称<input name="display_name" value="${esc(o.account.name)}" maxlength="80"/></label><label>简介<textarea name="bio">${esc(o.account.bio)}</textarea></label>`,
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
          ? "编辑内容"
          : "回复";
    dialog(
      label,
      `<label>${esc(label)}<textarea name="text" required>${type === "edit_post" ? esc(o.post.body) : ""}</textarea></label>`,
      (v) =>
        act(type, {
          ...args,
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
  if (!file) return;
  if (file.size > 8 * 1024 * 1024) return toast("上传素材最大 8 MiB");
  const encoded = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(",")[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
  try {
    await api("/api/assets", {
      user_id: current().user_id,
      filename: file.name,
      data_base64: encoded,
    });
    await loadSession(sessionId);
    toast("素材已上传");
  } catch (e) {
    toast(e.message);
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
function wireNative(o) {
  const root = $("platformRoot");
  root.onclick = (e) => {
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
    if (card && !e.target.closest("a,input,textarea,summary,form"))
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
      if (body.trim()) act("create_post", { body });
    };
  const compose = root.querySelector("#composeForm");
  if (compose) {
    draftAssets = (o.draft?.assets || []).map((s) => s.asset_id);
    compose.onsubmit = async (e) => {
      e.preventDefault();
      const args = composerValues(compose);
      const published = e.submitter?.dataset.publish === "1";
      const saved = await act("save_draft", args);
      if (published && saved?.result?.success !== false)
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
}
function updateComposerSelection(o) {
  const selected = $("selectedAssets");
  if (selected)
    selected.innerHTML = draftAssets
      .map((id, index) => {
        const asset = o.asset_library.find((a) => a.asset_id === id);
        return asset
          ? `<div class="selected-asset">${nativeMedia(asset)}<span>${index + 1}</span><button type="button" data-move="-1" data-asset="${esc(id)}" ${!editable() ? "disabled" : ""}>←</button><button type="button" data-move="1" data-asset="${esc(id)}" ${!editable() ? "disabled" : ""}>→</button></div>`
          : "";
      })
      .join("");
}
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
  const value = Object.fromEntries(new FormData(e.target));
  $("actionDialog").close();
  if (dialogAction) await dialogAction(value);
};
document
  .querySelectorAll("[data-dialog-close]")
  .forEach((b) => (b.onclick = () => $("actionDialog").close()));
$("newSession").onclick = async () => {
  if (runId) return;
  const next = await api("/api/session", {
    user_id: Number($("userSelect").value),
  });
  await loadWorld();
  await loadSession(next.session_id);
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
