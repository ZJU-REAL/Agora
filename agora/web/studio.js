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
    description: "图文笔记 · 视频 · 收藏",
    caption: "发现 / 关注 / 同城",
    short: "生活兴趣社区",
  },
  x: {
    name: "X / Twitter",
    subtitle: "公开讨论 · 实时信息",
    description: "帖子 · 回复 · 引用转发",
    caption: "For You / Following",
    short: "公开信息与讨论",
  },
  reddit: {
    name: "Reddit",
    subtitle: "主题社区 · 深度讨论",
    description: "主题社区 · 投票 · 嵌套评论",
    caption: "For You / Following / Popular",
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
const observationCache = new Map();
let frameObservation = null,
  frameFetchVersion = 0;
const contextKey = "agora-workbench:" + window.AGORA_BASE_PATH;
function readStorage(key, local = false) {
  try {
    return JSON.parse(
      (local ? localStorage : sessionStorage).getItem(key) || "null",
    );
  } catch {
    return null;
  }
}
function writeStorage(key, value, local = false) {
  try {
    (local ? localStorage : sessionStorage).setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}
let workspaceContext = readStorage(contextKey) || {
  platform: "xiaohongshu",
  viewer: {},
};
workspaceContext.viewer ||= {};
workspaceContext.runs ||= {};
let recommendationBase = {},
  launchError = "";
let capacity = {
    max_active_agents: 32,
    max_active_runs: 1,
    max_run_actions: 2400,
    active_runs: 0,
  },
  developerVersion = 0,
  developerLoading = false;
let actorPositions = new Map(),
  timelineFilter = "all",
  replayPlaying = false,
  replayGeneration = 0,
  controlPending = false;
let pendingInitialActor = Number(query.get("actor")) || null,
  pendingInitialStep = Number(query.get("step")) || null;
let selectedPlatform = platforms[query.get("platform")]
  ? query.get("platform")
  : platforms[workspaceContext.platform]
    ? workspaceContext.platform
    : "xiaohongshu";
let world = null,
  providers = [],
  runList = [],
  selectedRun =
    query.get("run") || workspaceContext.viewer[selectedPlatform]?.run || null,
  run = null,
  runWorld = null,
  selectedActor = null,
  actorSession = null,
  actorData = null,
  replayIndex = -1,
  replayTimer = null,
  loadVersion = 0,
  polling = false,
  launching = false,
  actorSignature = null,
  frameSignature = null,
  timelineSignature = null;
const route = (path) => agoraPath(path);
const viewerUrl = (id, platform = selectedPlatform) =>
  route(
    "/viewer?platform=" +
      encodeURIComponent(platform) +
      "&run=" +
      encodeURIComponent(id),
  );
function logo(platform) {
  return `<span class="platform-logo ${esc(platform)}">${platform === "xiaohongshu" ? "小红书" : platform === "x" ? '<svg viewBox="0 0 24 24"><path d="M18.9 2H22l-6.8 7.8L23.2 22h-6.3l-5-7.6L5.2 22H2.1l8.3-9.6L1 2h6.5l4.6 7Zm-1.1 18h1.7L6.5 3.9H4.7Z" fill="currentColor" stroke="none"/></svg>' : '<svg viewBox="0 0 32 32"><path d="m17 10 2-6 6 1"/><circle cx="26" cy="5" r="2"/><ellipse cx="16" cy="20" rx="11" ry="8" fill="white" stroke="white"/><circle cx="4" cy="16" r="3"/><circle cx="28" cy="16" r="3"/><circle cx="12" cy="19" r="1.5" fill="#ff5b23" stroke="#ff5b23"/><circle cx="20" cy="19" r="1.5" fill="#ff5b23" stroke="#ff5b23"/><path d="M11 23q5 4 10 0" stroke="#ff5b23"/></svg>'}</span>`;
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
    const target = new URL(route(a.dataset.route), location.origin);
    target.searchParams.set("platform", selectedPlatform);
    if (a.dataset.route === "/viewer") {
      const context = workspaceContext.viewer[selectedPlatform];
      if (context?.run) target.searchParams.set("run", context.run);
    }
    a.href = target.pathname + target.search;
  });
  document
    .querySelectorAll("[data-mode]")
    .forEach((a) => a.classList.toggle("active", a.dataset.mode === mode));
  $("exploreLink").href = route("/account?platform=" + selectedPlatform);
  if (run && mode === "viewer")
    $("reuseRun").href = route(
      "/developer?platform=" +
        selectedPlatform +
        "&reuse=" +
        encodeURIComponent(run.run_id),
    );
}
function rememberPlatform() {
  workspaceContext.platform = selectedPlatform;
  writeStorage(contextKey, workspaceContext);
  const url = new URL(location.href);
  url.searchParams.set("platform", selectedPlatform);
  history.replaceState({}, "", url);
  setLinks();
}
function configKey(local = false) {
  return contextKey + (local ? ":saved:" : ":draft:") + selectedPlatform;
}
function rememberDraft() {
  if (world && !developerLoading) writeStorage(configKey(), experimentConfig());
}
function rememberPosition() {
  if (!run || !selectedActor || !actorData) return;
  const position = { step: replayIndex < 0 ? null : currentEvent()?.step };
  actorPositions.set(selectedActor, position);
  const positions = Object.fromEntries(actorPositions);
  delete workspaceContext.runs[selectedRun];
  workspaceContext.runs[selectedRun] = { actor: selectedActor, positions };
  while (Object.keys(workspaceContext.runs).length > 8)
    delete workspaceContext.runs[Object.keys(workspaceContext.runs)[0]];
  workspaceContext.viewer[selectedPlatform] = {
    run: selectedRun,
    actor: selectedActor,
  };
  writeStorage(contextKey, workspaceContext);
  const url = new URL(location.href);
  url.searchParams.set("platform", selectedPlatform);
  url.searchParams.set("run", selectedRun);
  url.searchParams.set("actor", selectedActor);
  if (position.step) url.searchParams.set("step", position.step);
  else url.searchParams.delete("step");
  history.replaceState({}, "", url);
  setLinks();
}
const actionGroups = {
  browse: {
    name: "浏览",
    icon: "eye",
    types: [
      "refresh",
      "scroll",
      "search",
      "open_post",
      "back",
      "dwell",
      "view_profile",
      "open_notifications",
      "open_notification",
      "view_saved",
      "view_collection",
      "view_media",
      "play_video",
      "seek_video",
      "view_asset_library",
    ],
  },
  create: {
    name: "创作",
    icon: "grid",
    types: [
      "create_post",
      "open_studio",
      "save_draft",
      "publish_draft",
      "edit_post",
      "delete_post",
      "edit_comment",
      "delete_comment",
      "upload_asset",
    ],
  },
  interact: {
    name: "互动",
    icon: "link",
    types: [
      "like_post",
      "unlike_post",
      "collect_post",
      "uncollect_post",
      "not_interested",
      "create_comment",
      "reply_post",
      "quote_post",
      "repost",
      "undo_repost",
      "bookmark_post",
      "unbookmark_post",
      "upvote_post",
      "downvote_post",
      "clear_post_vote",
      "upvote_comment",
      "downvote_comment",
      "clear_comment_vote",
      "like_comment",
      "unlike_comment",
      "crosspost",
      "save_post",
      "unsave_post",
      "add_to_collection",
      "pin_comment",
      "unpin_comment",
    ],
  },
  social: {
    name: "关系",
    icon: "users",
    types: [
      "follow_user",
      "unfollow_user",
      "list_communities",
      "view_community",
      "create_community",
      "join_community",
      "leave_community",
      "remove_post",
      "approve_post",
      "approve_member",
      "create_collection",
      "edit_profile",
    ],
  },
  system: { name: "其他", icon: "clock", types: [] },
};
function actionGroup(event) {
  return (
    Object.keys(actionGroups).find((key) =>
      actionGroups[key].types.includes(event?.action?.action_type),
    ) || "system"
  );
}
function actionIcon(event) {
  return event?.result?.success === false
    ? "close"
    : actionGroups[actionGroup(event)].icon;
}
function selectValue(id, value) {
  const select = $(id);
  if (![...select.options].some((option) => option.value === String(value))) {
    const option = new Option("原配置不可用 · " + value, value);
    option.disabled = true;
    select.add(option);
  }
  select.value = value;
}
function number(id) {
  return Number($(id).value);
}
function experimentConfig() {
  const slate = number("slateSize");
  return {
    name:
      $("runName").value.trim() ||
      `${platforms[selectedPlatform].name} · 主账号运营`,
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
      ...recommendationBase,
      slate_size: slate,
      page_size: number("pageSize"),
      exploration_fraction: number("exploration"),
    },
  };
}
function updateSummary() {
  if (!world) return;
  const focal = world.users.find((u) => u.user_id === number("focalUser"));
  const count = number("agentCount") || 1,
    config = experimentConfig();
  $("populationNote").textContent =
    `1 个受测账号 + ${Math.max(0, count - 1)} 个背景账号`;
  $("summaryPlatform").innerHTML =
    logo(selectedPlatform) +
    `<div><strong>${platforms[selectedPlatform].name}</strong><small>${platforms[selectedPlatform].subtitle}</small></div>`;
  $("summaryAgent").innerHTML =
    avatar(focal) +
    `<div><strong>${esc(focal?.name || "选择账号")}</strong><small>@${esc(focal?.handle || "")}</small></div><span class="small-badge">受测</span>`;
  $("summaryPopulation").textContent = `${Math.max(0, count - 1)} 个`;
  $("summaryTicks").textContent = `${config.ticks} 轮`;
  $("summaryActions").textContent =
    `${config.ticks * config.steps_per_tick} 次`;
  $("summaryTotal").textContent =
    `${config.ticks * config.steps_per_tick * count} 次`;
  $("summaryModel").textContent = modelName(config.provider_id);
  $("summaryBackground").textContent = modelName(config.background_provider_id);
  $("summarySeed").textContent = config.seed;
  $("focalIdentity").textContent = focal
    ? `来自 ${platforms[selectedPlatform].name} 的已有账号，保留原有个人资料。`
    : "请选择已有平台账号。";
  const backgrounds = world.users
    .filter((u) => u.user_id !== focal?.user_id)
    .sort((a, b) => a.user_id - b.user_id)
    .slice(0, Math.max(0, count - 1));
  const generated = Math.max(0, count - 1 - backgrounds.length);
  $("backgroundIdentity").textContent =
    count === 1
      ? "没有背景账号，仅观察受测账号。"
      : `${backgrounds.length} 个已有账号${generated ? ` + ${generated} 个新生成账号` : ""}。${backgrounds
          .slice(0, 3)
          .map((u) => u.name || u.handle)
          .join("、")}${backgrounds.length > 3 ? "等" : ""}`;
  const descriptions = [
    ["受测", config.provider_id],
    ["背景", config.background_provider_id],
  ]
    .filter(([role]) => role !== "背景" || count > 1)
    .map(([role, id]) => {
      const selected = providers.find((p) => p.provider_id === id);
      return id === "development"
        ? `${role}：规则驱动开发策略，无模型 API 调用`
        : `${role}：${selected?.model_id || id}，${selected?.supports_vision ? "图文" : "文字"}输入`;
    });
  $("modelNote").innerHTML =
    icon("link") + `<span>${esc(descriptions.join("；"))}。</span>`;
  const invalid = [...$("experimentForm").elements].find(
    (el) => el.willValidate && !el.validity.valid,
  );
  const unavailable = [
    config.provider_id,
    ...(count > 1 ? [config.background_provider_id] : []),
  ].find(
    (id) =>
      id !== "development" &&
      !providers.some((p) => p.provider_id === id && p.credential_available),
  );
  let problem = developerLoading
    ? "正在切换平台，请稍候。"
    : !focal
      ? "这个平台没有可用账号，请先导入账号数据。"
      : invalid
        ? `请检查${invalid.labels?.[0]?.childNodes?.[0]?.textContent?.trim() || "配置参数"}。`
        : unavailable
          ? "所选模型缺少可用凭据，请连接模型或选择开发策略。"
          : config.ticks * config.steps_per_tick * count >
              capacity.max_run_actions
            ? `总动作上限超过 ${capacity.max_run_actions} 次，请减少账号、轮数或每轮动作。`
            : number("pageSize") > number("slateSize")
              ? "每页展示数量不能超过推荐列表长度。"
              : capacity.active_runs >= capacity.max_active_runs
                ? "已有模拟运行中，请到 Viewer 暂停或结束该实验。"
                : launchError;
  $("launchReadiness").className =
    "launch-readiness" + (problem ? " error" : "");
  $("launchReadiness").innerHTML =
    icon(problem ? "clock" : "check") +
    `<span>${esc(problem || (config.provider_id === "development" ? "可启动 · 受测账号使用开发策略" : "可启动 · 模型凭据已配置，建议先测试连接"))}</span>`;
  $("launchButton").disabled =
    launching || (!!problem && problem !== launchError);
  $("lessAgents").disabled = count <= 1;
  $("moreAgents").disabled = count >= Number($("agentCount").max);
  $("capacityNote").textContent =
    `最多 ${capacity.max_active_runs} 个并发模拟 · ${capacity.max_active_agents} 个活跃账号`;
}
function renderPlatforms() {
  $("platformCards").innerHTML = Object.entries(platforms)
    .map(
      ([key, p]) =>
        `<button type="button" class="platform-card ${selectedPlatform === key ? "selected" : ""}" data-platform="${key}" aria-pressed="${selectedPlatform === key}"><span class="selected-check">${icon("check")}</span>${logo(key)}<strong>${p.name}</strong><p>${p.description}</p><span class="platform-caption">${p.caption}</span></button>`,
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
  const version = ++developerVersion,
    platform = selectedPlatform;
  developerLoading = true;
  $("launchButton").disabled = true;
  renderPlatforms();
  rememberPlatform();
  try {
    const [capabilities, nextWorld] = await Promise.all([
      api("/api/platforms"),
      api("/api/world?platform=" + platform),
    ]);
    if (version !== developerVersion) return;
    capacity = capabilities.capacity || capacity;
    $("agentCount").max = capacity.max_active_agents;
    world = nextWorld;
    $("focalUser").innerHTML = world.users
      .map(
        (u) =>
          `<option value="${u.user_id}">${esc(u.name || u.handle)} · @${esc(u.handle)}</option>`,
      )
      .join("");
    $("experimentForm").reset();
    recommendationBase = {};
    launchError = "";
    const preferred =
      world.users.find((u) => u.handle === "reader") || world.users[0];
    if (preferred) $("focalUser").value = preferred.user_id;
    $("focalModel").value = "development";
    $("backgroundModel").value = "development";
    $("runName").value = "";
    $("configOrigin").hidden = true;
    developerLoading = false;
    applyConfiguration(
      readStorage(configKey()) || readStorage(configKey(true), true),
    );
    updateSummary();
    await loadRecent(version, platform);
  } catch (e) {
    if (version !== developerVersion) return;
    world = null;
    $("launchReadiness").className = "launch-readiness error";
    $("launchReadiness").textContent = "平台加载失败，请重新选择平台重试。";
    throw e;
  } finally {
    if (version === developerVersion) {
      developerLoading = false;
      if (world) updateSummary();
    }
  }
}
async function loadRecent(
  version = developerVersion,
  platform = selectedPlatform,
) {
  const [data, capabilities] = await Promise.all([
    api("/api/runs?platform=" + platform),
    api("/api/platforms"),
  ]);
  if (version !== developerVersion || platform !== selectedPlatform) return;
  capacity = capabilities.capacity || capacity;
  runList = data.runs;
  $("recentRuns").innerHTML =
    runList
      .slice(0, 8)
      .map(
        (r) =>
          `<div class="run-row"><div class="run-row-title">${logo(platform)}<div><strong title="${esc(r.name)}">${esc(r.name)}</strong><small>${new Date(r.created_at).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false })} · ${esc(r.run_id)}</small></div></div><span class="run-row-count">${r.config.user_ids.length} 个账号</span><div class="run-row-progress"><small>${r.completed_ticks} / ${r.config.ticks} 轮</small><div class="mini-progress"><span style="width:${Math.min(100, (r.completed_ticks / r.config.ticks) * 100)}%"></span></div></div>${status(r.status)}<div class="run-row-actions"><button type="button" class="text-button" data-reuse="${esc(r.run_id)}">复用配置</button><a class="text-button" href="${viewerUrl(r.run_id)}">打开回放 ${icon("arrow")}</a></div></div>`,
      )
      .join("") ||
    '<div class="empty-state compact">这个平台还没有实验。配置好账号后，启动第一场模拟。</div>';
  updateSummary();
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
  $("providerProxy").checked = p.trust_env;
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
    trust_env: $("providerProxy").checked,
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
function applyConfiguration(value) {
  if (!value) return;
  launchError = "";
  recommendationBase = { ...(value.recommendation || {}) };
  value = {
    ...value,
    agent_count: value.agent_count ?? value.user_ids?.length,
  };
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
    if (value[key] === undefined) continue;
    if (["focalUser", "focalModel", "backgroundModel"].includes(id))
      selectValue(id, value[key]);
    else $(id).value = value[key];
  }
  if (value.recommendation) {
    $("slateSize").value = value.recommendation.slate_size ?? 6;
    $("pageSize").value =
      value.recommendation.page_size ?? Math.min(6, number("slateSize"));
    $("exploration").value = value.recommendation.exploration_fraction ?? 0.2;
  }
  updateSummary();
}
function saveConfiguration() {
  const value = experimentConfig();
  const saved = writeStorage(configKey(true), value, true);
  rememberDraft();
  toast(
    saved
      ? "当前平台配置已保存到此浏览器"
      : "浏览器无法保存配置，请允许网站存储后重试",
  );
}
async function restoreConfiguration() {
  const legacy = readStorage("agora-experiment-config", true);
  if (
    !readStorage(configKey()) &&
    !readStorage(configKey(true), true) &&
    legacy?.platform === selectedPlatform
  )
    applyConfiguration(legacy);
  if (query.get("reuse")) await reuseConfiguration(query.get("reuse"));
}
async function reuseConfiguration(id) {
  const platform = selectedPlatform,
    version = developerVersion;
  try {
    const [metadata, metadataWorld] = await Promise.all([
      api("/api/runs/" + encodeURIComponent(id)),
      api("/api/run-world?run=" + encodeURIComponent(id)),
    ]);
    if (version !== developerVersion || platform !== selectedPlatform) return;
    if (metadataWorld.preset !== platform)
      throw Error("这场实验属于另一个平台，请切换到对应平台再复用。");
    applyConfiguration({ ...metadata.config, name: metadata.name + " · 副本" });
    rememberDraft();
    $("configOrigin").hidden = false;
    $("configOrigin").innerHTML =
      `<span>已复用：${esc(metadata.name)}</span><a class="text-button" href="${viewerUrl(id)}">返回原实验 ${icon("arrow")}</a>`;
    $("configNav").click();
    toast("配置已载入，启动时会创建新的独立实验");
  } catch (e) {
    toast(e.message);
  }
}
async function launch(event) {
  event.preventDefault();
  if (launching || developerLoading || !$("experimentForm").reportValidity())
    return;
  updateSummary();
  if ($("launchButton").disabled) return;
  launching = true;
  launchError = "";
  rememberDraft();
  const button = $("launchButton");
  button.disabled = true;
  button.innerHTML = icon("clock") + "正在准备沙盒…";
  try {
    const platform = selectedPlatform,
      job = await api("/api/runs?platform=" + platform, experimentConfig());
    location.href = viewerUrl(job.run_id, platform);
  } catch (e) {
    launching = false;
    button.innerHTML = icon("play") + "启动模拟" + icon("arrow");
    launchError = e.message;
    toast(e.message);
    updateSummary();
  }
}
function duration(ms) {
  const seconds = Math.floor((ms || 0) / 1000);
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}
function stopReplay() {
  clearTimeout(replayTimer);
  replayTimer = null;
  replayPlaying = false;
  replayGeneration++;
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
  const signature = JSON.stringify([
    selectedRun,
    selectedActor,
    users,
    run.actor_action_counts,
    run.events?.length,
  ]);
  if (signature !== actorSignature) {
    $("actorList").innerHTML = users
      .map((u) => {
        const count =
          run.actor_action_counts?.[u.user_id] ??
          run.events.filter(
            (e) =>
              e.user_id === u.user_id &&
              !["start_session", "end_session"].includes(e.action.action_type),
          ).length;
        return `<button type="button" class="actor-card ${u.user_id === selectedActor ? "selected" : ""}" aria-pressed="${u.user_id === selectedActor}" data-actor="${u.user_id}">${avatar(u)}<span><span class="actor-card-name">${esc(u.name)}</span><small>${u.user_id === run.config.focal_user_id ? '<span class="actor-role">受测</span>' : "背景"} · ${count} 次</small></span></button>`;
      })
      .join("");
    $("actorList").scrollTop = scrollTop;
    actorSignature = signature;
  }
  $("runProgress").textContent =
    `${run.completed_ticks} / ${run.config.ticks} 轮 · ${run.config.user_ids.length} 个账号`;
}
function renderRun() {
  if (!run) return;
  $("viewerEmpty").hidden = true;
  $("viewerWorkspace").hidden = false;
  $("viewerControls").hidden = false;
  $("reuseRun").hidden = false;
  setLinks();
  $("viewerTitle").textContent = run.name;
  $("viewerTitle").title = run.name;
  $("viewerSubtitle").textContent =
    `${platforms[selectedPlatform].name} · ${run.config.user_ids.length} 个账号 · seed ${run.config.seed} · 独立实验 ${run.run_id}`;
  $("viewerStatus").className = `run-status ${run.status}`;
  $("viewerStatus").textContent = states[run.status] || run.status;
  const option = Array.from($("viewerRun").options).find(
    (o) => o.value === run.run_id,
  );
  if (option)
    option.textContent = `${run.name} · ${states[run.status] || run.status}`;
  $("exportRun").disabled = ![
    "completed",
    "canceled",
    "failed",
    "interrupted",
    "paused",
  ].includes(run.status);
  $("runModelLabel").textContent =
    run.model === "persona-development" &&
    (!run.background_model || run.background_model === "persona-development")
      ? "规则驱动开发策略 · 模型调用 0"
      : `主 ${run.model === "persona-development" ? "开发策略" : run.model} · 背景 ${run.background_model === "persona-development" ? "开发策略" : run.background_model || run.model}`;
  $("runMetricsLabel").textContent =
    `${run.metrics?.created_posts || 0} 条发布 · ${(run.metrics?.comments || 0) + (run.metrics?.replies || 0)} 次评论/回复 · ${run.metrics?.exposures || 0} 次曝光 · ${run.metrics?.model_calls || 0} 次模型调用`;
  for (const id of ["pauseRun", "resumeRun", "stopRun"])
    $(id).disabled = controlPending;
  $("pauseRun").hidden = run.status !== "running";
  $("resumeRun").hidden = run.status !== "paused";
  $("stopRun").hidden = !["running", "paused", "queued", "pausing"].includes(
    run.status,
  );
  renderActors();
}
function renderTimeline(trajectory, index) {
  const nextSignature = JSON.stringify([
    selectedRun,
    selectedActor,
    trajectory.length,
    trajectory.at(-1)?.step,
    timelineFilter,
  ]);
  const timeline = $("actionTimeline"),
    wasAtEnd =
      timeline.scrollHeight - timeline.clientHeight - timeline.scrollTop < 24;
  const matches = (event) =>
    timelineFilter === "all" ||
    (timelineFilter === "failed"
      ? event.result?.success === false
      : actionGroup(event) === timelineFilter);
  const visible = trajectory
    .map((event, i) => ({ event, i }))
    .filter(({ event }) => matches(event));
  $("timelineCount").textContent =
    `${visible.length} / ${trajectory.length} 条`;
  if (nextSignature !== timelineSignature) {
    timeline.innerHTML =
      visible
        .map(
          ({ event: e, i }) =>
            `<button type="button" class="timeline-event ${e.result?.success === false ? "failed" : ""}" data-frame="${i}">${icon(actionIcon(e))}<span><strong>${esc(actions[e.action.action_type] || e.action.action_type)}</strong><small>tick ${e.tick} · ${duration(e.elapsed_ms)}</small></span><span>${String(e.step).padStart(2, "0")}</span></button>`,
        )
        .join("") ||
      '<div class="timeline-empty">没有此类记录。选择其他类型查看操作。</div>';
    timelineSignature = nextSignature;
  }
  timeline.querySelectorAll(".selected").forEach((el) => {
    el.classList.remove("selected");
    el.removeAttribute("aria-current");
  });
  const active = timeline.querySelector(`[data-frame="${index}"]`);
  if (active) {
    active.classList.add("selected");
    active.setAttribute("aria-current", "step");
  }
  if (replayIndex < 0 && wasAtEnd) timeline.scrollTop = timeline.scrollHeight;
  else if (active) {
    const rect = active.getBoundingClientRect(),
      bounds = timeline.getBoundingClientRect();
    if (rect.top < bounds.top || rect.bottom > bounds.bottom)
      timeline.scrollTop += rect.top - bounds.top - timeline.clientHeight / 2;
  }
}
function renderStats(trajectory) {
  const counts = Object.fromEntries(
    Object.keys(actionGroups).map((key) => [key, 0]),
  );
  trajectory.forEach((e) => {
    if (!["start_session", "end_session"].includes(e.action.action_type))
      counts[actionGroup(e)]++;
  });
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  $("actorStats").innerHTML = Object.entries(actionGroups)
    .filter(([key]) => key !== "system" || counts.system)
    .map(
      ([key, group]) =>
        `<div class="stat-row"><span>${group.name}</span><span class="stat-bar ${key}" role="meter" aria-label="${group.name}操作" aria-valuemin="0" aria-valuemax="${Math.max(1, total)}" aria-valuenow="${counts[key]}"><span style="width:${total ? (100 * counts[key]) / total : 0}%"></span></span><b>${counts[key]}</b></div>`,
    )
    .join("");
}
function renderFrame() {
  if (!actorData || !run) return;
  const trajectory = actorData.trajectory || [],
    event = currentEvent(),
    observation = replayIndex < 0 ? actorData.observation : frameObservation;
  const user = run.users.find((u) => u.user_id === selectedActor);
  const index =
    replayIndex < 0 ? Math.max(0, trajectory.length - 1) : replayIndex;
  const signature = JSON.stringify([
    selectedRun,
    selectedActor,
    replayIndex,
    event,
    observation,
    trajectory.length,
    timelineFilter,
    run.status,
  ]);
  if (signature === frameSignature) {
    sendFrame();
    return;
  }
  frameSignature = signature;
  const detailsOpen = $("decisionDetail").querySelector("details")?.open;
  $("stageActor").innerHTML =
    avatar(user) +
    `<div><strong>${esc(user?.name || "")}</strong><small>${selectedActor === run.config.focal_user_id ? "受测账号" : "背景账号"} · ${esc(platforms[selectedPlatform].name)}</small></div>`;
  $("screenBadge").textContent = screens[observation?.screen] || "等待行动";
  $("frameTime").textContent = duration(
    event?.elapsed_ms ?? observation?.elapsed_ms,
  );
  $("windowAddress").textContent =
    platforms[selectedPlatform].name +
    " · " +
    (user?.name || "账号 " + selectedActor);
  $("frameSlider").disabled = !trajectory.length;
  $("frameSlider").max = Math.max(0, trajectory.length - 1);
  $("frameSlider").value = index;
  $("stepCounter").textContent = trajectory.length
    ? `${index + 1} / ${trajectory.length}`
    : "0 / 0";
  $("liveButton").classList.toggle("active", replayIndex < 0);
  const active = [
    "queued",
    "running",
    "pausing",
    "paused",
    "stopping",
  ].includes(run.status);
  $("liveLabel").textContent = active ? "跟随最新" : "最新步骤";
  $("replayMode").textContent =
    replayIndex < 0 && active ? "跟随最新" : "历史回放";
  $("previousFrame").disabled = !trajectory.length || index === 0;
  $("nextFrame").disabled =
    !trajectory.length || index >= trajectory.length - 1;
  $("playReplay").disabled = !trajectory.length;
  $("decisionStep").textContent = "第 " + (event?.step || 0) + " 步";
  $("frameContext").textContent =
    `${event ? `tick ${event.tick} · ${duration(event.elapsed_ms)} · ` : ""}账号独立时间线；切换时恢复各自位置。画面只读。`;
  if (event) {
    const action = event.action,
      result = event.result,
      group = actionGroup(event),
      specs = Array.isArray(action.arguments?.assets)
        ? action.arguments.assets
        : [];
    const imageIds = specs.filter((s) => s.asset_id).slice(0, 6);
    const outcome =
      result?.success === false
        ? "执行失败" + (result.error_type ? " · " + result.error_type : "")
        : result?.success === true
          ? "执行成功"
          : "执行结果未记录";
    let observed = "";
    if (observation?.screen === "detail" && observation.post)
      observed =
        observation.post.title ||
        observation.post.body?.slice(0, 180) ||
        "内容详情";
    else if (Array.isArray(observation?.cards))
      observed = `${screens[observation.screen] || observation.screen} · 画面中 ${observation.cards.length} 条内容`;
    else if (observation?.screen)
      observed = screens[observation.screen] || observation.screen;
    $("decisionDetail").innerHTML =
      `<div class="decision-action"><span class="action-glyph ${group}">${icon(actionIcon(event))}</span><div><h3>${esc(actions[action.action_type] || action.action_type)}</h3><small>tick ${event.tick} · ${duration(event.elapsed_ms)}</small></div></div><div class="decision-outcome ${result?.success === false ? "failed" : result?.success === true ? "" : "unknown"}">${icon(result?.success === false ? "close" : result?.success === true ? "check" : "clock")}${esc(outcome)}</div>${observed ? `<div class="observation-summary"><span>动作后的实际画面</span>${esc(observed)}</div>` : ""}${action.rationale ? `<div class="rationale"><span class="rationale-label">公开选择理由</span><p>${esc(action.rationale)}</p></div>` : '<div class="inline-note">未记录公开选择理由。</div>'}${imageIds.length ? `<div class="selected-media">${imageIds.map((s) => `<img src="${route("/api/run-media?run=" + encodeURIComponent(selectedRun) + "&id=" + encodeURIComponent(s.asset_id))}" alt="本次选择的素材" loading="lazy"/>`).join("")}</div>` : ""}<details class="decision-details"><summary>查看动作参数与执行结果</summary><pre>${esc(JSON.stringify({ action: action.action_type, arguments: action.arguments, result }, null, 2))}</pre></details>`;
  } else
    $("decisionDetail").innerHTML =
      '<div class="empty-state compact">账号尚未生成操作记录。模拟开始后会自动更新。</div>';
  const details = $("decisionDetail").querySelector("details");
  if (details) details.open = !!detailsOpen;
  renderStats(trajectory);
  renderTimeline(trajectory, index);
  sendFrame();
  rememberPosition();
}
function resetActorFrame(message = "正在加载账号记录…") {
  actorData = null;
  actorSession = null;
  frameObservation = null;
  frameSignature = null;
  timelineSignature = null;
  observationCache.clear();
  frameFetchVersion++;
  $("accountFrame").hidden = true;
  $("accountFrame").removeAttribute("src");
  $("frameEmpty").hidden = false;
  $("frameEmpty").textContent = message;
  $("accountFrame").closest(".platform-window").classList.remove("loading");
  for (const id of ["playReplay", "previousFrame", "nextFrame", "frameSlider"])
    $(id).disabled = true;
  $("decisionDetail").innerHTML =
    '<div class="empty-state compact">' + esc(message) + "</div>";
  $("actionTimeline").innerHTML = "";
  $("actorStats").innerHTML = "";
  $("stepCounter").textContent = "0 / 0";
  $("decisionStep").textContent = "第 0 步";
  $("timelineCount").textContent = "0 条";
}
async function loadActor(userId, version = loadVersion) {
  stopReplay();
  selectedActor = userId;
  resetActorFrame();
  replayIndex = -1;
  renderActors();
  const position = actorPositions.get(userId),
    id = selectedRun;
  actorSession = runWorld.sessions.find(
    (s) => s.user_id === userId,
  )?.session_id;
  if (!actorSession) {
    $("frameEmpty").textContent = "这个账号尚未开始会话，运行后会自动更新。";
    return;
  }
  try {
    const data = await api(
      "/api/run-session?run=" +
        encodeURIComponent(id) +
        "&id=" +
        actorSession +
        "&compact=1",
    );
    if (
      version !== loadVersion ||
      selectedActor !== userId ||
      id !== selectedRun
    )
      return;
    actorData = data;
    if (position?.step) {
      const i = data.trajectory.findIndex((e) => e.step === position.step);
      if (i >= 0) await setFrame(i, false);
    }
    if (
      version !== loadVersion ||
      selectedActor !== userId ||
      id !== selectedRun
    )
      return;
    const frame = $("accountFrame");
    frame.src = route(
      "/account?run=" +
        encodeURIComponent(id) +
        "&actor=" +
        userId +
        "&embed=1",
    );
    frame.hidden = false;
    $("frameEmpty").hidden = true;
    renderFrame();
  } catch (e) {
    if (version !== loadVersion || selectedActor !== userId) return;
    resetActorFrame("账号记录加载失败，请重新点击该账号重试。");
    throw e;
  }
}
function viewerEmpty(title, message, retry = false) {
  $("viewerWorkspace").hidden = true;
  $("viewerControls").hidden = true;
  $("reuseRun").hidden = true;
  $("viewerEmpty").hidden = false;
  $("viewerEmptyTitle").textContent = title;
  $("viewerEmptyText").textContent = message;
  $("retryViewer").hidden = !retry;
}
async function loadRun(id, expectedVersion = null) {
  if (expectedVersion !== null && expectedVersion !== loadVersion) return;
  rememberPosition();
  const version = ++loadVersion;
  selectedRun = id;
  stopReplay();
  resetActorFrame();
  run = null;
  runWorld = null;
  selectedActor = null;
  actorSignature = null;
  $("exportRun").disabled = true;
  $("reuseRun").hidden = true;
  viewerEmpty(
    id ? "正在加载实验" : "选择一场实验，开始观察",
    id ? "正在读取账号和操作记录。" : "在开发者页面创建模拟，或选择已有实验。",
  );
  if (!id) return;
  try {
    const [metadata, metadataWorld] = await Promise.all([
      api("/api/runs/" + encodeURIComponent(id)),
      api("/api/run-world?run=" + encodeURIComponent(id)),
    ]);
    if (version !== loadVersion) return;
    if (metadataWorld.preset !== selectedPlatform) {
      selectedPlatform = metadataWorld.preset;
      if (!platforms[selectedPlatform])
        throw Error("实验平台不受当前页面支持。");
      $("viewerPlatform").value = selectedPlatform;
      rememberPlatform();
      const data = await api("/api/runs?platform=" + selectedPlatform);
      if (version !== loadVersion) return;
      runList = data.runs;
      if (!runList.some((r) => r.run_id === id)) runList.unshift(metadata);
      renderRunOptions();
      $("viewerRun").value = id;
    }
    run = metadata;
    runWorld = metadataWorld;
    const context =
      workspaceContext.runs[id] ||
      (workspaceContext.viewer[selectedPlatform]?.run === id
        ? workspaceContext.viewer[selectedPlatform]
        : null);
    actorPositions = new Map(
      context
        ? Object.entries(context.positions || {}).map(([actor, pos]) => [
            Number(actor),
            pos,
          ])
        : [],
    );
    selectedActor = [
      pendingInitialActor,
      context?.actor,
      run.config.focal_user_id,
      run.config.user_ids[0],
    ].find((actor) => run.config.user_ids.includes(actor));
    if (pendingInitialStep)
      actorPositions.set(selectedActor, { step: pendingInitialStep });
    pendingInitialActor = null;
    pendingInitialStep = null;
    renderRun();
    rememberPlatform();
    await loadActor(selectedActor, version);
  } catch (e) {
    if (version !== loadVersion) return;
    viewerEmpty(
      "实验加载失败",
      e.message + "。可以重新加载，或选择另一场实验。",
      true,
    );
    throw e;
  }
}
function renderRunOptions() {
  $("viewerRun").innerHTML =
    '<option value="">选择一个实验</option>' +
    runList
      .map(
        (r) =>
          `<option value="${esc(r.run_id)}">${esc(r.name)} · ${esc(states[r.status] || r.status)}</option>`,
      )
      .join("");
}
async function loadViewerPlatform() {
  const version = ++loadVersion,
    platform = selectedPlatform,
    id = selectedRun;
  stopReplay();
  resetActorFrame();
  run = null;
  runWorld = null;
  selectedActor = null;
  rememberPlatform();
  $("exportRun").disabled = true;
  viewerEmpty("正在读取实验", "正在加载当前平台的实验记录。");
  try {
    const data = await api("/api/runs?platform=" + platform);
    if (version !== loadVersion || platform !== selectedPlatform) return;
    runList = data.runs;
    if (id && !runList.some((r) => r.run_id === id)) {
      try {
        const archived = await api("/api/runs/" + encodeURIComponent(id));
        if (version !== loadVersion) return;
        runList.unshift(archived);
      } catch {}
    }
    if (version !== loadVersion) return;
    renderRunOptions();
    const initial = runList.some((r) => r.run_id === id)
      ? id
      : runList[0]?.run_id || "";
    $("viewerRun").value = initial;
    await loadRun(initial, version);
  } catch (e) {
    if (version !== loadVersion) return;
    viewerEmpty(
      "暂时无法读取实验",
      e.message + "。检查工作区连接后重新加载。",
      true,
    );
    throw e;
  }
}
async function pollViewer(force = false) {
  if (polling || !selectedRun || document.hidden) return;
  if (
    !force &&
    actorData &&
    ["completed", "canceled", "failed", "interrupted"].includes(run?.status)
  )
    return;
  polling = true;
  const version = loadVersion,
    id = selectedRun,
    actor = selectedActor,
    session = actorSession;
  try {
    const [next, nextWorld] = await Promise.all([
      api("/api/runs/" + encodeURIComponent(id)),
      api("/api/run-world?run=" + encodeURIComponent(id)),
    ]);
    if (version !== loadVersion || id !== selectedRun) return;
    run = next;
    runWorld = nextWorld;
    renderRun();
    if (!session || !actorData) {
      if (actor) await loadActor(actor, version);
      return;
    }
    const last = actorData.trajectory?.at(-1)?.step;
    const nextData = await api(
      "/api/run-session?run=" +
        encodeURIComponent(id) +
        "&id=" +
        session +
        "&compact=1" +
        (last ? "&after=" + last : ""),
    );
    if (
      version !== loadVersion ||
      actor !== selectedActor ||
      session !== actorSession
    )
      return;
    if (last && actorData)
      nextData.trajectory = [
        ...actorData.trajectory,
        ...nextData.trajectory.filter((e) => e.step > last),
      ];
    actorData = nextData;
    renderFrame();
    document.body.dataset.connection = "ready";
    $("workspaceHealth").textContent = "工作区已连接";
  } catch (e) {
    if (version === loadVersion) {
      document.body.dataset.connection = "error";
      $("workspaceHealth").textContent = "连接中断 · 保留当前画面";
    }
  } finally {
    polling = false;
  }
}
async function setFrame(index, stop = true) {
  if (stop) stopReplay();
  if (!actorData?.trajectory?.length) return;
  const target = Math.max(0, Math.min(index, actorData.trajectory.length - 1)),
    step = actorData.trajectory[target]?.step;
  if (!step) return;
  const version = ++frameFetchVersion,
    actor = selectedActor,
    id = selectedRun,
    session = actorSession;
  const windowEl = $("accountFrame").closest(".platform-window");
  try {
    if (!observationCache.has(step)) {
      windowEl.classList.add("loading");
      const value = await api(
        "/api/run-session?run=" +
          encodeURIComponent(id) +
          "&id=" +
          session +
          "&step=" +
          step,
      );
      if (
        version !== frameFetchVersion ||
        actor !== selectedActor ||
        id !== selectedRun
      )
        return;
      observationCache.set(step, value.observation);
      while (observationCache.size > 4)
        observationCache.delete(observationCache.keys().next().value);
    }
    if (
      version !== frameFetchVersion ||
      actor !== selectedActor ||
      id !== selectedRun
    )
      return;
    replayIndex = target;
    frameObservation = observationCache.get(step);
    renderFrame();
  } catch (e) {
    if (version === frameFetchVersion) {
      stopReplay();
      toast("历史画面加载失败，已保留当前步骤。" + e.message);
    }
    throw e;
  } finally {
    if (version === frameFetchVersion) windowEl.classList.remove("loading");
  }
}
async function chooseFrame(index) {
  return setFrame(index);
}
function playReplay() {
  if (replayPlaying) {
    stopReplay();
    return;
  }
  const length = actorData?.trajectory?.length || 0;
  if (!length) return;
  const initial =
    replayIndex < 0 || replayIndex === length - 1 ? 0 : replayIndex;
  replayPlaying = true;
  const generation = ++replayGeneration;
  $("playReplay").innerHTML = icon("pause");
  $("playReplay").setAttribute("aria-label", "暂停回放");
  const advance = async (index) => {
    try {
      await setFrame(index, false);
    } catch {
      return;
    }
    if (generation !== replayGeneration || !replayPlaying) return;
    if (replayIndex >= actorData.trajectory.length - 1) {
      stopReplay();
      return;
    }
    replayTimer = setTimeout(
      () => advance(replayIndex + 1),
      1200 / Number($("replaySpeed").value),
    );
  };
  advance(initial);
}
async function controlRun(command) {
  if (controlPending || !run) return;
  const id = selectedRun,
    version = loadVersion;
  controlPending = true;
  renderRun();
  try {
    await api("/api/runs/" + encodeURIComponent(id) + "/control", { command });
    if (version !== loadVersion || id !== selectedRun) return;
    await pollViewer(true);
    toast(
      {
        pause: "已请求暂停模拟",
        resume: "已请求继续模拟",
        stop: "已请求停止模拟",
      }[command],
    );
  } catch (e) {
    toast(e.message);
  } finally {
    controlPending = false;
    renderRun();
  }
}
async function exportRun() {
  if (
    !run ||
    !["completed", "canceled", "failed", "interrupted", "paused"].includes(
      run.status,
    )
  )
    return toast("请暂停或结束模拟后导出完整记录。");
  const link = document.createElement("a");
  link.href = route("/api/runs/" + encodeURIComponent(selectedRun) + "/export");
  link.download = "agora-" + selectedRun + ".json";
  link.click();
}
function wireDeveloper() {
  const configurationChanged = () => {
    launchError = "";
    updateSummary();
    rememberDraft();
  };
  $("platformCards").onclick = async (e) => {
    const card = e.target.closest("[data-platform]");
    if (
      !card ||
      launching ||
      (card.dataset.platform === selectedPlatform && world)
    )
      return;
    rememberDraft();
    selectedPlatform = card.dataset.platform;
    try {
      await loadDeveloperPlatform();
    } catch (e) {
      toast(e.message);
    }
  };
  $("experimentForm").addEventListener("input", configurationChanged);
  $("experimentForm").addEventListener("change", configurationChanged);
  $("runName").addEventListener("input", configurationChanged);
  $("recentRuns").onclick = (e) => {
    const button = e.target.closest("[data-reuse]");
    if (button) reuseConfiguration(button.dataset.reuse);
  };

  $("lessAgents").onclick = () => {
    $("agentCount").value = Math.max(1, number("agentCount") - 1);
    launchError = "";
    updateSummary();
    rememberDraft();
  };
  $("moreAgents").onclick = () => {
    $("agentCount").value = Math.min(
      Number($("agentCount").max),
      number("agentCount") + 1,
    );
    launchError = "";
    updateSummary();
  };
  $("moreAgents").addEventListener("click", rememberDraft);
  $("experimentForm").onsubmit = launch;
  $("saveConfig").onclick = saveConfiguration;
  $("addModel").onclick = openModels;
  $("mobileModels").onclick = openModels;
  $("modelsNav").onclick = openModels;
  const scrollBehavior = () =>
    matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
  $("configNav").onclick = () => {
    window.scrollTo({ top: 0, behavior: scrollBehavior() });
    $("configNav").classList.add("active");
    $("runsNav").classList.remove("active");
  };
  $("runsNav").onclick = () => {
    $("recentSection").scrollIntoView({ behavior: scrollBehavior() });
    $("runsNav").classList.add("active");
    $("configNav").classList.remove("active");
  };
  $("closeModels").onclick = () => {
    $("providerKey").value = "";
    $("modelDialog").close();
  };
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
  $("modelDialog").addEventListener("cancel", () => {
    $("providerKey").value = "";
  });
  protocolFields();
}
function wireViewer() {
  $("expandStage").onclick = () => {
    const expanded = $("viewerWorkspace").classList.toggle("stage-expanded");
    $("expandStage").setAttribute("aria-pressed", String(expanded));
    $("expandStage").setAttribute(
      "aria-label",
      expanded ? "恢复平台画面大小" : "放大平台画面",
    );
    $("expandStage").innerHTML =
      icon(expanded ? "compress" : "expand") +
      `<span>${expanded ? "恢复布局" : "放大画面"}</span>`;
  };
  $("viewerPlatform").innerHTML = Object.entries(platforms)
    .map(([key, p]) => `<option value="${key}">${p.name}</option>`)
    .join("");
  $("viewerPlatform").value = selectedPlatform;
  $("viewerPlatform").onchange = async () => {
    rememberPosition();
    selectedPlatform = $("viewerPlatform").value;
    selectedRun = workspaceContext.viewer[selectedPlatform]?.run || null;
    pendingInitialActor = null;
    pendingInitialStep = null;
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
      rememberPosition();
      loadVersion++;
      loadActor(Number(b.dataset.actor)).catch((e) => toast(e.message));
    }
  };
  $("actionTimeline").onclick = (e) => {
    const b = e.target.closest("[data-frame]");
    if (b) chooseFrame(Number(b.dataset.frame)).catch(() => {});
  };
  $("frameSlider").oninput = () =>
    chooseFrame(number("frameSlider")).catch(() => {});
  $("timelineFilter").onchange = () => {
    timelineFilter = $("timelineFilter").value;
    frameSignature = null;
    renderFrame();
  };
  $("retryViewer").onclick = () =>
    loadViewerPlatform().catch((e) => toast(e.message));
  $("previousFrame").onclick = () =>
    chooseFrame(
      (replayIndex < 0 ? actorData.trajectory.length - 1 : replayIndex) - 1,
    ).catch(() => {});
  $("nextFrame").onclick = () =>
    chooseFrame(
      (replayIndex < 0 ? actorData.trajectory.length - 1 : replayIndex) + 1,
    ).catch(() => {});
  $("playReplay").onclick = playReplay;
  $("replaySpeed").onchange = () => {
    if (replayPlaying) {
      stopReplay();
      playReplay();
    }
  };
  $("liveButton").onclick = () => {
    stopReplay();
    frameFetchVersion++;
    $("accountFrame").closest(".platform-window").classList.remove("loading");
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
  $("mobileLaunchBar").hidden = true;
  try {
    if (mode === "developer") {
      wireDeveloper();
      await loadProviders();
      await loadDeveloperPlatform();
      await restoreConfiguration();
      setInterval(() => {
        if (!document.hidden) loadRecent().catch((e) => toast(e.message));
      }, 5000);
    } else {
      wireViewer();
      await loadViewerPlatform();
      setInterval(pollViewer, 1600);
    }
    rememberPlatform();
    document.body.dataset.connection = "ready";
    $("workspaceHealth").textContent = "工作区已连接";
  } catch (e) {
    document.body.dataset.connection = "error";
    $("workspaceHealth").textContent = "连接暂不可用";
    toast(e.message);
  }
}
main();
