/* Agora developer workspace and an observation-only account viewer. */
const $ = (id) => document.getElementById(id);
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const icon = (name) => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
const query = new URLSearchParams(location.search);
const mode = document.body.dataset.view;
const platforms = {
  xiaohongshu: {
    name: "小红书",
    subtitle: "兴趣发现 · 生活社区",
    description: "图文笔记、视频与收藏，<br>围绕生活经验展开互动。",
    caption: "发现 / 关注 / 同城",
    short: "生活兴趣社区",
  },
  x: {
    name: "X / Twitter",
    subtitle: "公开讨论 · 实时信息",
    description: "帖子、回复与引用转发，<br>观察信息如何进入讨论。",
    caption: "For You / Following",
    short: "公开信息与讨论",
  },
  reddit: {
    name: "Reddit",
    subtitle: "主题社区 · 深度讨论",
    description: "社区、投票与帖子讨论，<br>在不同规则下参与互动。",
    caption: "Home / Popular / Latest",
    short: "主题社区与讨论",
  },
};
const states = {
  queued: "准备中",
  running: "运行中",
  paused: "已暂停",
  pausing: "暂停中",
  stopping: "停止中",
  completed: "已完成",
  canceled: "已停止",
  failed: "运行失败",
  interrupted: "进程中断",
};
const actions = {
  start_session: "开始浏览",
  end_session: "结束会话",
  refresh: "刷新信息流",
  scroll: "继续浏览",
  search: "搜索内容",
  open_post: "打开内容",
  back: "返回列表",
  dwell: "阅读停留",
  create_post: "发布内容",
  open_studio: "进入创作工作台",
  save_draft: "选择素材并保存草稿",
  publish_draft: "发布草稿",
  view_profile: "查看个人主页",
  open_notifications: "查看通知与回复",
  open_notification: "打开通知",
  like_post: "点赞",
  unlike_post: "取消点赞",
  collect_post: "收藏笔记",
  uncollect_post: "取消收藏",
  not_interested: "不感兴趣",
  follow_user: "关注作者",
  unfollow_user: "取消关注",
  create_comment: "发表评论",
  reply_post: "回复帖子",
  quote_post: "引用帖子",
  repost: "转发帖子",
  undo_repost: "撤销转发",
  bookmark_post: "保存书签",
  unbookmark_post: "移除书签",
  view_saved: "查看已保存内容",
  upvote_post: "赞同帖子",
  downvote_post: "反对帖子",
  clear_post_vote: "撤销帖子投票",
  upvote_comment: "赞同评论",
  downvote_comment: "反对评论",
  clear_comment_vote: "撤销评论投票",
  like_comment: "点赞评论",
  unlike_comment: "取消评论点赞",
  edit_post: "编辑内容",
  delete_post: "删除内容",
  edit_comment: "编辑评论",
  delete_comment: "删除评论",
  list_communities: "浏览社区",
  view_community: "进入社区",
  create_community: "创建社区",
  join_community: "加入社区",
  leave_community: "退出社区",
  crosspost: "跨社区分享",
  remove_post: "移除帖子",
  approve_post: "恢复帖子",
  approve_member: "批准成员",
  create_collection: "新建收藏专辑",
  view_collection: "打开收藏专辑",
  add_to_collection: "加入收藏专辑",
  pin_comment: "置顶评论",
  unpin_comment: "取消置顶",
  view_media: "查看下一张图片",
  play_video: "播放视频",
  seek_video: "调整视频位置",
  edit_profile: "编辑个人资料",
  policy_failure: "模型或策略调用失败",
  decision_failure: "动作执行失败",
  save_post: "保存帖子",
  unsave_post: "取消保存",
};
const screens = {
  feed: "信息流",
  detail: "内容详情",
  studio: "创作工作台",
  profile: "个人主页",
  search: "搜索结果",
  notifications: "通知与回复",
  saved: "已保存内容",
  community: "社区",
  communities: "社区列表",
  collection: "收藏专辑",
};
let selectedPlatform = platforms[query.get("platform")]
  ? query.get("platform")
  : "xiaohongshu";
let world = null,
  providers = [],
  runList = [],
  selectedRun = query.get("run"),
  run = null,
  runWorld = null,
  selectedActor = null,
  actorSession = null,
  actorData = null,
  replayIndex = -1,
  replayTimer = null,
  loadVersion = 0,
  polling = false;
const route = (path) => agoraPath(path);
const viewerUrl = (id, platform = selectedPlatform) =>
  route(
    "/viewer?platform=" +
      encodeURIComponent(platform) +
      "&run=" +
      encodeURIComponent(id),
  );
function logo(platform) {
  return `<span class="platform-logo ${esc(platform)}">${platform === "xiaohongshu" ? "小红书" : platform === "x" ? "𝕏" : '<svg viewBox="0 0 32 32"><path d="m17 10 2-6 6 1"/><circle cx="26" cy="5" r="2"/><ellipse cx="16" cy="20" rx="11" ry="8" fill="white" stroke="white"/><circle cx="4" cy="16" r="3"/><circle cx="28" cy="16" r="3"/><circle cx="12" cy="19" r="1.5" fill="#ff5b23" stroke="#ff5b23"/><circle cx="20" cy="19" r="1.5" fill="#ff5b23" stroke="#ff5b23"/><path d="M11 23q5 4 10 0" stroke="#ff5b23"/></svg>'}</span>`;
}
function avatar(user) {
  const name = user?.name || user?.handle || "A";
  return `<span class="avatar">${esc(name.slice(0, 2))}</span>`;
}
function toast(message) {
  $("toast").textContent = message;
  $("toast").classList.add("visible");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => $("toast").classList.remove("visible"), 4000);
}
async function api(path, value) {
  const response = await fetch(
    route(path),
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
function platformPath(path) {
  return (
    path +
    (path.includes("?") ? "&" : "?") +
    "platform=" +
    encodeURIComponent(selectedPlatform)
  );
}
function status(value) {
  return `<span class="run-status ${esc(value)}">${esc(states[value] || value)}</span>`;
}
function modelName(id) {
  return id === "development"
    ? "开发策略"
    : providers.find((p) => p.provider_id === id)?.display_name ||
        providers.find((p) => p.provider_id === id)?.model_id ||
        id;
}
function setLinks() {
  document.querySelectorAll("[data-route]").forEach((a) => {
    a.href = route(
      a.dataset.route + "?platform=" + encodeURIComponent(selectedPlatform),
    );
  });
  document
    .querySelectorAll("[data-mode]")
    .forEach((a) => a.classList.toggle("active", a.dataset.mode === mode));
  if ($("exploreLink"))
    $("exploreLink").href = route("/account?platform=" + selectedPlatform);
}
function number(id) {
  return Number($(id).value);
}
function experimentConfig() {
  const slate = number("slateSize");
  return {
    name:
      $("runName").value.trim() ||
      `${platforms[selectedPlatform].name} · 受测账号运营`,
    agent_count: number("agentCount"),
    focal_user_id: number("focalUser"),
    provider_id: $("focalModel").value,
    background_provider_id: $("backgroundModel").value,
    ticks: number("ticks"),
    steps_per_tick: number("steps"),
    seed: number("seed"),
    goal: $("goal").value,
    pace_ms: number("pace"),
    recommendation: {
      slate_size: slate,
      page_size: Math.min(6, slate),
      exploration_fraction: number("exploration"),
    },
  };
}
function updateSummary() {
  if (!world) return;
  const focal = world.users.find((u) => u.user_id === number("focalUser"));
  const count = number("agentCount") || 1;
  const config = experimentConfig();
  $("populationNote").textContent =
    `1 个受测 agent + ${Math.max(0, count - 1)} 个背景账号`;
  $("summaryPlatform").innerHTML =
    logo(selectedPlatform) +
    `<div><strong>${platforms[selectedPlatform].name}</strong><small>${platforms[selectedPlatform].subtitle}</small></div>`;
  $("summaryAgent").innerHTML =
    avatar(focal) +
    `<div><strong>${esc(focal?.name || focal?.handle || "选择账号")}</strong><small>@${esc(focal?.handle || "")}</small></div><span class="small-badge">受测</span>`;
  $("summaryPopulation").textContent = `${Math.max(0, count - 1)} agents`;
  $("summaryTicks").textContent = `${config.ticks} rounds`;
  $("summaryActions").textContent =
    `${config.ticks * config.steps_per_tick} actions`;
  $("summaryModel").textContent = modelName(config.provider_id);
  $("summarySeed").textContent = config.seed;
  const selected = providers.find((p) => p.provider_id === config.provider_id);
  $("modelNote").innerHTML =
    icon("link") +
    `<span>${config.provider_id === "development" ? "当前使用规则驱动的开发策略，无模型 API 调用。添加模型连接后可运行真实模型账号。" : `受测模型：${esc(selected?.model_id || "")}。每账号请求上限 ${selected?.limits?.max_requests || "—"}，支持${selected?.supports_vision ? "图文" : "文字"}输入。`}</span>`;
}
function renderPlatforms() {
  $("platformCards").innerHTML = Object.entries(platforms)
    .map(
      ([key, p]) =>
        `<button type="button" class="platform-card ${selectedPlatform === key ? "selected" : ""}" data-platform="${key}" aria-pressed="${selectedPlatform === key}"><span class="selected-check">${icon("check")}</span>${logo(key)}<strong>${p.name}</strong><p>${p.description}</p><span class="platform-caption"><span></span>${p.caption}</span></button>`,
    )
    .join("");
}
async function loadProviders() {
  providers = (await api("/api/providers")).providers;
  const oldFocal = $("focalModel").value,
    oldBackground = $("backgroundModel").value;
  const options =
    '<option value="development">开发策略 · 无 API 调用</option>' +
    providers
      .map(
        (p) =>
          `<option value="${esc(p.provider_id)}" ${!p.credential_available ? "disabled" : ""}>${esc(p.display_name || p.model_id)}${p.credential_available ? "" : " · 未配置凭据"}</option>`,
      )
      .join("");
  $("focalModel").innerHTML = options;
  $("backgroundModel").innerHTML = options;
  if (providers.some((p) => p.provider_id === oldFocal))
    $("focalModel").value = oldFocal;
  if (providers.some((p) => p.provider_id === oldBackground))
    $("backgroundModel").value = oldBackground;
  $("modelCount").textContent = providers.length;
  renderSavedModels();
  updateSummary();
}
async function loadDeveloperPlatform() {
  renderPlatforms();
  setLinks();
  world = await api(platformPath("/api/world"));
  $("focalUser").innerHTML = world.users
    .map(
      (u) =>
        `<option value="${u.user_id}">${esc(u.name || u.handle)} · @${esc(u.handle)}</option>`,
    )
    .join("");
  const preferred = world.users.find((u) => u.handle === "reader");
  if (preferred) $("focalUser").value = preferred.user_id;
  updateSummary();
  await loadRecent();
}
async function loadRecent() {
  const data = await api(platformPath("/api/runs"));
  runList = data.runs;
  $("recentRuns").innerHTML =
    runList
      .slice(0, 5)
      .map(
        (r) =>
          `<div class="run-row"><div class="run-row-title">${logo(selectedPlatform)}<div><strong>${esc(r.name)}</strong><small>${new Date(r.created_at).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false })} · ${esc(r.run_id)}</small></div></div><span class="run-row-count">${r.config.user_ids.length} agents</span><div class="run-row-progress"><small>${r.completed_ticks} / ${r.config.ticks} 轮</small><div class="mini-progress"><span style="width:${Math.min(100, (r.completed_ticks / r.config.ticks) * 100)}%"></span></div></div>${status(r.status)}<a class="text-button" href="${viewerUrl(r.run_id)}">打开 Viewer ${icon("arrow")}</a></div>`,
      )
      .join("") ||
    '<div class="empty-state compact">这个平台还没有实验。配置完成后，启动第一场模拟。</div>';
}
function renderSavedModels() {
  $("savedModels").innerHTML =
    providers
      .map(
        (p) =>
          `<div class="saved-model ${$("providerId").value === p.provider_id ? "selected" : ""}"><button class="text-button" type="button" data-edit-model="${esc(p.provider_id)}">${icon("link")}${esc(p.display_name || p.model_id)}</button><button type="button" class="test-model" data-test-model="${esc(p.provider_id)}">测试连接</button></div>`,
      )
      .join("") ||
    '<span class="inline-note">还没有模型连接。填入服务地址、模型 ID 和 API Key 即可添加。</span>';
}
function protocolFields() {
  const protocol = $("providerProtocol").value;
  $("endpointField").hidden = protocol === "gemini";
  $("providerUrl").required = protocol !== "gemini";
  $("providerAuth").closest("label").hidden = protocol !== "openai-compatible";
}
function openModels() {
  $("modelDialog").showModal();
  renderSavedModels();
}
function editModel(id) {
  const p = providers.find((p) => p.provider_id === id);
  if (!p) return;
  $("providerId").value = p.provider_id;
  $("providerName").value = p.display_name || p.model_id;
  $("providerProtocol").value = p.provider;
  $("providerUrl").value = p.base_url;
  $("providerModel").value = p.model_id;
  $("providerKey").value = "";
  $("providerBudget").value = p.limits.max_requests || 100;
  $("providerTokens").value = p.limits.max_output_tokens || 1024;
  $("providerTimeout").value = p.limits.timeout_seconds || 60;
  $("providerVision").checked = p.supports_vision;
  $("providerAuth").value = p.auth_style;
  $("modelFeedback").textContent = "编辑已有连接；API Key 留空会保留原凭据。";
  protocolFields();
  renderSavedModels();
}
async function saveModel(event) {
  event.preventDefault();
  const button = $("saveModel");
  button.disabled = true;
  $("modelFeedback").textContent = "正在保存…";
  const value = {
    provider_id: $("providerId").value || undefined,
    display_name: $("providerName").value,
    provider: $("providerProtocol").value,
    base_url: $("providerUrl").value,
    model_id: $("providerModel").value,
    api_key: $("providerKey").value || undefined,
    auth_style: $("providerAuth").value,
    supports_vision: $("providerVision").checked,
    limits: {
      max_requests: number("providerBudget"),
      max_output_tokens: number("providerTokens"),
      timeout_seconds: number("providerTimeout"),
    },
  };
  try {
    const saved = await api("/api/providers", value);
    $("providerKey").value = "";
    $("providerId").value = saved.provider_id;
    await loadProviders();
    $("focalModel").value = saved.provider_id;
    updateSummary();
    $("modelFeedback").textContent = "已保存。可测试连接，或关闭窗口启动实验。";
    toast("模型连接已保存");
  } catch (e) {
    $("modelFeedback").textContent = e.message;
  } finally {
    button.disabled = false;
  }
}
function saveConfiguration() {
  const value = experimentConfig();
  value.platform = selectedPlatform;
  localStorage.setItem("agora-experiment-config", JSON.stringify(value));
  toast("实验配置已保存到当前浏览器");
}
async function restoreConfiguration() {
  try {
    const value = JSON.parse(
      localStorage.getItem("agora-experiment-config") || "null",
    );
    if (!value) return;
    if (!query.has("platform") && platforms[value.platform]) {
      selectedPlatform = value.platform;
      await loadDeveloperPlatform();
    }
    for (const [key, id] of Object.entries({
      name: "runName",
      agent_count: "agentCount",
      focal_user_id: "focalUser",
      provider_id: "focalModel",
      background_provider_id: "backgroundModel",
      ticks: "ticks",
      steps_per_tick: "steps",
      seed: "seed",
      goal: "goal",
      pace_ms: "pace",
    })) {
      if (value[key] !== undefined) $(id).value = value[key];
    }
    if (value.recommendation) {
      $("slateSize").value = value.recommendation.slate_size;
      $("exploration").value = value.recommendation.exploration_fraction;
    }
    if (!$("focalModel").value) $("focalModel").value = "development";
    if (!$("backgroundModel").value) $("backgroundModel").value = "development";
    if (!$("focalUser").value) $("focalUser").selectedIndex = 0;
    updateSummary();
  } catch (e) {
    toast("保存的配置无法读取，已使用默认配置");
  }
}
async function launch(event) {
  event.preventDefault();
  const button = $("launchButton");
  button.disabled = true;
  button.innerHTML = icon("clock") + "正在准备沙盒…";
  try {
    const config = experimentConfig();
    const job = await api(platformPath("/api/runs"), config);
    location.href = viewerUrl(job.run_id);
  } catch (e) {
    toast(e.message);
    button.disabled = false;
    button.innerHTML = icon("play") + "启动模拟" + icon("arrow");
  }
}
function duration(ms) {
  const seconds = Math.round((ms || 0) / 1000);
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}
function stopReplay() {
  clearInterval(replayTimer);
  replayTimer = null;
  $("playReplay").innerHTML = icon("play");
  $("playReplay").setAttribute("aria-label", "播放回放");
}
function currentEvent() {
  return replayIndex < 0
    ? actorData?.trajectory?.at(-1)
    : actorData?.trajectory?.[replayIndex];
}
function sendFrame() {
  const frame = $("accountFrame");
  if (!frame.hidden && frame.contentWindow)
    frame.contentWindow.postMessage(
      {
        type: "agora:frame",
        run: selectedRun,
        step: replayIndex < 0 ? -1 : currentEvent()?.step || 0,
      },
      location.origin,
    );
}
function renderActors() {
  const users = (run?.users || []).filter((u) =>
    run.config.user_ids.includes(u.user_id),
  );
  users.sort(
    (a, b) =>
      Number(b.user_id === run.config.focal_user_id) -
      Number(a.user_id === run.config.focal_user_id),
  );
  const scrollTop = $("actorList").scrollTop;
  $("actorCount").textContent = users.length;
  $("actorList").innerHTML = users
    .map((u) => {
      const count = run.events.filter(
        (e) =>
          e.user_id === u.user_id &&
          !["start_session", "end_session"].includes(e.action.action_type),
      ).length;
      return `<button type="button" class="actor-card ${u.user_id === selectedActor ? "selected" : ""}" data-actor="${u.user_id}">${avatar(u)}<span><span class="actor-card-name">${esc(u.name)}</span><small>${u.user_id === run.config.focal_user_id ? '<span class="actor-role">受测</span>' : "背景账号"} · ${count} 步</small></span></button>`;
    })
    .join("");
  $("actorList").scrollTop = scrollTop;
  $("runProgress").textContent =
    `${run.completed_ticks} / ${run.config.ticks} 轮 · ${run.config.user_ids.length} 个账号`;
}
function renderRun() {
  if (!run) return;
  $("viewerEmpty").hidden = true;
  $("viewerWorkspace").hidden = false;
  $("viewerControls").hidden = false;
  $("viewerTitle").textContent = run.name;
  $("viewerSubtitle").textContent =
    `${platforms[selectedPlatform].name} · ${run.config.user_ids.length} 个账号 · seed ${run.config.seed} · 独立实验 ${run.run_id}`;
  $("viewerStatus").className = `run-status ${run.status}`;
  $("viewerStatus").textContent = states[run.status] || run.status;
  const option = Array.from($("viewerRun").options).find(
    (o) => o.value === run.run_id,
  );
  if (option)
    option.textContent = `${run.name} · ${states[run.status] || run.status}`;
  $("exportRun").disabled = false;
  $("runModelLabel").textContent =
    run.model === "persona-development" &&
    (!run.background_model || run.background_model === "persona-development")
      ? "规则驱动开发策略 · 模型调用 0"
      : `受测 ${run.model === "persona-development" ? "开发策略" : run.model} · 背景 ${run.background_model === "persona-development" ? "开发策略" : run.background_model || run.model}`;
  $("runMetricsLabel").textContent =
    `${run.metrics.created_posts} 条发布 · ${run.metrics.comments + (run.metrics.replies || 0)} 次评论/回复 · ${run.metrics.exposures} 次曝光 · ${run.metrics.model_calls} 次模型调用`;
  $("pauseRun").hidden = run.status !== "running";
  $("resumeRun").hidden = run.status !== "paused";
  $("stopRun").hidden = !["running", "paused", "queued", "pausing"].includes(
    run.status,
  );
  renderActors();
}
function renderFrame() {
  if (!actorData) return;
  const event = currentEvent();
  const observation =
    replayIndex < 0 ? actorData.observation : event?.observation;
  const user = run.users.find((u) => u.user_id === selectedActor);
  $("stageActor").innerHTML =
    avatar(user) +
    `<div><strong>${esc(user?.name || "")}</strong><small>${selectedActor === run.config.focal_user_id ? "受测 agent" : "背景账号"} · ${esc(platforms[selectedPlatform].name)}</small></div>`;
  $("screenBadge").textContent =
    screens[observation?.screen] || observation?.screen || "等待行动";
  $("frameTime").textContent = duration(observation?.elapsed_ms);
  $("windowAddress").textContent =
    selectedPlatform.toUpperCase() + " / AGENT " + selectedActor;
  const trajectory = actorData.trajectory || [];
  const index =
    replayIndex < 0 ? Math.max(0, trajectory.length - 1) : replayIndex;
  $("frameSlider").max = Math.max(0, trajectory.length - 1);
  $("frameSlider").value = index;
  $("stepCounter").textContent = `${index + 1} / ${trajectory.length}`;
  $("liveButton").classList.toggle("active", replayIndex < 0);
  $("previousFrame").disabled = !trajectory.length || index === 0;
  $("nextFrame").disabled =
    !trajectory.length || index >= trajectory.length - 1;
  $("playReplay").disabled = !trajectory.length;
  $("decisionStep").textContent =
    "STEP " + String(event?.step || 0).padStart(2, "0");
  const action = event?.action;
  const result = event?.result;
  const creation =
    action &&
    ["save_draft", "create_post", "publish_draft", "open_studio"].includes(
      action.action_type,
    );
  if (event) {
    const specs = action.arguments?.assets || [];
    const imageIds = specs.filter((s) => s.asset_id).slice(0, 6);
    $("decisionDetail").innerHTML =
      `<div class="decision-action"><span class="action-glyph ${creation ? "creation" : ""}">${icon(creation ? "grid" : "eye")}</span><div><h3>${esc(actions[action.action_type] || action.action_type)}</h3><small>tick ${event.tick} · ${duration(event.elapsed_ms)}</small></div></div><div class="decision-outcome ${result?.success === false ? "failed" : ""}">${icon(result?.success === false ? "clock" : "check")}${result?.success === false ? "执行失败 · " + esc(result.error_type || "") : "已记录这一步的实际观察"}</div>${action.rationale ? `<div class="rationale"><span class="rationale-label">公开选择理由</span><p>${esc(action.rationale)}</p></div>` : '<div class="inline-note">这一步未提供公开选择理由。</div>'}${imageIds.length ? `<div class="selected-media">${imageIds.map((s) => `<img src="${route("/api/run-media?run=" + encodeURIComponent(selectedRun) + "&id=" + encodeURIComponent(s.asset_id))}" alt="本次选择的素材" loading="lazy"/>`).join("")}</div>` : ""}<details class="decision-details"><summary>动作参数与结果</summary><pre>${esc(JSON.stringify({ action: action.action_type, arguments: action.arguments, result }, null, 2))}</pre></details>`;
  } else {
    $("decisionDetail").innerHTML =
      '<div class="empty-state compact">等待账号开始行动…</div>';
  }
  $("timelineCount").textContent = trajectory.length + " 步";
  $("actionTimeline").innerHTML = trajectory
    .map(
      (e, i) =>
        `<button type="button" class="timeline-event ${i === index ? "selected" : ""}" data-frame="${i}"><span><strong>${esc(actions[e.action.action_type] || e.action.action_type)}</strong><small>tick ${e.tick} · ${duration(e.elapsed_ms)}</small></span><span>${String(e.step).padStart(2, "0")}</span></button>`,
    )
    .join("");
  const timeline = $("actionTimeline");
  if (replayIndex < 0) timeline.scrollTop = timeline.scrollHeight;
  else {
    const active = timeline.querySelector(".selected");
    if (active)
      timeline.scrollTop +=
        active.getBoundingClientRect().top -
        timeline.getBoundingClientRect().top -
        timeline.clientHeight / 2;
  }
  sendFrame();
}
async function loadActor(userId, version = loadVersion) {
  stopReplay();
  selectedActor = userId;
  replayIndex = -1;
  actorSession = runWorld.sessions.find(
    (s) => s.user_id === userId,
  )?.session_id;
  actorData = null;
  renderActors();
  $("accountFrame").hidden = true;
  $("frameEmpty").hidden = false;
  $("frameEmpty").textContent = "等待这个账号开始行动…";
  if (!actorSession) return;
  const data = await api(
    "/api/run-session?run=" +
      encodeURIComponent(selectedRun) +
      "&id=" +
      actorSession,
  );
  if (version !== loadVersion || selectedActor !== userId) return;
  actorData = data;
  const frame = $("accountFrame");
  frame.src = route(
    "/account?run=" +
      encodeURIComponent(selectedRun) +
      "&actor=" +
      userId +
      "&embed=1",
  );
  frame.hidden = false;
  $("frameEmpty").hidden = true;
  renderFrame();
}
async function loadRun(id) {
  const version = ++loadVersion;
  selectedRun = id;
  stopReplay();
  if (!id) {
    run = null;
    actorData = null;
    $("viewerWorkspace").hidden = true;
    $("viewerControls").hidden = true;
    $("viewerEmpty").hidden = false;
    return;
  }
  const data = await api("/api/runs/" + encodeURIComponent(id));
  if (version !== loadVersion) return;
  run = data;
  runWorld = await api("/api/run-world?run=" + encodeURIComponent(id));
  if (version !== loadVersion) return;
  renderRun();
  selectedActor = run.config.focal_user_id || run.config.user_ids[0];
  const url = new URL(location.href);
  url.searchParams.set("run", id);
  url.searchParams.set("platform", selectedPlatform);
  history.replaceState({}, "", url);
  await loadActor(selectedActor, version);
}
async function loadViewerPlatform() {
  setLinks();
  const data = await api(platformPath("/api/runs"));
  runList = data.runs;
  $("viewerRun").innerHTML =
    '<option value="">选择一个实验</option>' +
    runList
      .map(
        (r) =>
          `<option value="${esc(r.run_id)}">${esc(r.name)} · ${esc(states[r.status] || r.status)}</option>`,
      )
      .join("");
  const initial = runList.some((r) => r.run_id === selectedRun)
    ? selectedRun
    : runList[0]?.run_id || "";
  $("viewerRun").value = initial;
  await loadRun(initial);
}
async function pollViewer() {
  if (polling || !selectedRun || document.hidden) return;
  if (
    actorData &&
    ["completed", "canceled", "failed", "interrupted"].includes(run?.status)
  )
    return;
  polling = true;
  const version = loadVersion,
    id = selectedRun,
    actor = selectedActor;
  try {
    const next = await api("/api/runs/" + encodeURIComponent(id));
    if (version !== loadVersion) return;
    run = next;
    runWorld = await api("/api/run-world?run=" + encodeURIComponent(id));
    if (version !== loadVersion) return;
    renderRun();
    if (!actorSession) {
      await loadActor(actor, version);
      return;
    }
    const last = actorData?.trajectory?.at(-1)?.step;
    const nextData = await api(
      "/api/run-session?run=" +
        encodeURIComponent(id) +
        "&id=" +
        actorSession +
        (last ? "&after=" + last : ""),
    );
    if (version !== loadVersion || actor !== selectedActor) return;
    if (last && actorData) {
      nextData.trajectory = [...actorData.trajectory, ...nextData.trajectory];
    }
    actorData = nextData;
    renderFrame();
  } catch (e) {
    toast(e.message);
  } finally {
    polling = false;
  }
}
function chooseFrame(index) {
  stopReplay();
  replayIndex = Math.max(
    0,
    Math.min(index, (actorData?.trajectory?.length || 1) - 1),
  );
  renderFrame();
}
function playReplay() {
  if (replayTimer) {
    stopReplay();
    return;
  }
  const length = actorData?.trajectory?.length || 0;
  if (!length) return;
  if (replayIndex < 0 || replayIndex === length - 1) replayIndex = 0;
  $("playReplay").textContent = "Ⅱ";
  $("playReplay").setAttribute("aria-label", "暂停回放");
  renderFrame();
  replayTimer = setInterval(
    () => {
      if (replayIndex >= actorData.trajectory.length - 1) {
        stopReplay();
        return;
      }
      replayIndex++;
      renderFrame();
    },
    1200 / Number($("replaySpeed").value),
  );
}
async function controlRun(command) {
  try {
    await api("/api/runs/" + encodeURIComponent(selectedRun) + "/control", {
      command,
    });
    await pollViewer();
    toast(
      { pause: "已请求暂停", resume: "模拟继续运行", stop: "已请求停止" }[
        command
      ],
    );
  } catch (e) {
    toast(e.message);
  }
}
async function exportRun() {
  try {
    const data = await api(
      "/api/runs/" + encodeURIComponent(selectedRun) + "/export",
    );
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "agora-" + selectedRun + ".json";
    link.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    toast(e.message);
  }
}
function wireDeveloper() {
  $("platformCards").onclick = async (e) => {
    const card = e.target.closest("[data-platform]");
    if (!card) return;
    selectedPlatform = card.dataset.platform;
    try {
      await loadDeveloperPlatform();
    } catch (e) {
      toast(e.message);
    }
  };
  $("experimentForm").addEventListener("input", updateSummary);
  $("experimentForm").addEventListener("change", updateSummary);
  $("runName").addEventListener("input", updateSummary);
  $("lessAgents").onclick = () => {
    $("agentCount").value = Math.max(1, number("agentCount") - 1);
    updateSummary();
  };
  $("moreAgents").onclick = () => {
    $("agentCount").value = Math.min(100, number("agentCount") + 1);
    updateSummary();
  };
  $("experimentForm").onsubmit = launch;
  $("saveConfig").onclick = saveConfiguration;
  $("addModel").onclick = openModels;
  $("modelsNav").onclick = openModels;
  $("configNav").onclick = () =>
    window.scrollTo({ top: 0, behavior: "smooth" });
  $("runsNav").onclick = () =>
    $("recentSection").scrollIntoView({ behavior: "smooth" });
  $("closeModels").onclick = () => $("modelDialog").close();
  $("providerProtocol").onchange = protocolFields;
  $("modelForm").onsubmit = saveModel;
  $("newModel").onclick = () => {
    $("modelForm").reset();
    $("providerId").value = "";
    $("modelFeedback").textContent = "";
    protocolFields();
    renderSavedModels();
  };
  $("savedModels").onclick = async (e) => {
    const edit = e.target.closest("[data-edit-model]");
    if (edit) {
      editModel(edit.dataset.editModel);
      return;
    }
    const test = e.target.closest("[data-test-model]");
    if (!test) return;
    test.disabled = true;
    $("modelFeedback").textContent = "正在发送一次模型连接测试…";
    try {
      const result = await api("/api/providers/test", {
        provider_id: test.dataset.testModel,
      });
      $("modelFeedback").textContent = result.success
        ? `连接成功 · ${result.model_id} · ${result.elapsed_ms} ms`
        : result.error;
    } catch (e) {
      $("modelFeedback").textContent = e.message;
    } finally {
      test.disabled = false;
    }
  };
  $("modelDialog").addEventListener("close", () => {
    $("providerKey").value = "";
  });
  protocolFields();
}
function wireViewer() {
  $("viewerPlatform").innerHTML = Object.entries(platforms)
    .map(([key, p]) => `<option value="${key}">${p.name}</option>`)
    .join("");
  $("viewerPlatform").value = selectedPlatform;
  $("viewerPlatform").onchange = async () => {
    selectedPlatform = $("viewerPlatform").value;
    selectedRun = null;
    try {
      await loadViewerPlatform();
    } catch (e) {
      toast(e.message);
    }
  };
  $("viewerRun").onchange = () =>
    loadRun($("viewerRun").value).catch((e) => toast(e.message));
  $("actorList").onclick = (e) => {
    const b = e.target.closest("[data-actor]");
    if (b) {
      loadVersion++;
      loadActor(Number(b.dataset.actor)).catch((e) => toast(e.message));
    }
  };
  $("actionTimeline").onclick = (e) => {
    const b = e.target.closest("[data-frame]");
    if (b) chooseFrame(Number(b.dataset.frame));
  };
  $("frameSlider").oninput = () => chooseFrame(number("frameSlider"));
  $("previousFrame").onclick = () =>
    chooseFrame(
      (replayIndex < 0 ? actorData.trajectory.length - 1 : replayIndex) - 1,
    );
  $("nextFrame").onclick = () => chooseFrame(replayIndex + 1);
  $("playReplay").onclick = playReplay;
  $("replaySpeed").onchange = () => {
    if (replayTimer) {
      stopReplay();
      playReplay();
    }
  };
  $("liveButton").onclick = () => {
    stopReplay();
    replayIndex = -1;
    renderFrame();
  };
  $("accountFrame").onload = sendFrame;
  $("pauseRun").onclick = () => controlRun("pause");
  $("resumeRun").onclick = () => controlRun("resume");
  $("stopRun").onclick = () => controlRun("stop");
  $("exportRun").onclick = exportRun;
}
async function main() {
  setLinks();
  $("developerPage").hidden = mode !== "developer";
  $("viewerPage").hidden = mode !== "viewer";
  try {
    if (mode === "developer") {
      wireDeveloper();
      await Promise.all([loadDeveloperPlatform(), loadProviders()]);
      await restoreConfiguration();
      setInterval(() => {
        if (!document.hidden) loadRecent().catch((e) => toast(e.message));
      }, 5000);
    } else {
      wireViewer();
      await loadViewerPlatform();
      setInterval(pollViewer, 1600);
    }
  } catch (e) {
    toast(e.message);
  }
}
main();
