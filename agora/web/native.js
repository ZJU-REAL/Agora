/* Native platform pages share the same session state and social actions as agents. */
function pi(name) {
  return `<svg class="p-icon" aria-hidden="true"><use href="#p-${name}"/></svg>`;
}
function nb(name, args, text, classes = "") {
  return actionButton(name, args, text, classes);
}
function av(name, id = 0, large = false) {
  const colors = ["#dfebe1", "#ede0d5", "#dfe5f2", "#f1e0e5", "#e5e0ef"];
  return `<span class="p-avatar ${large ? "large" : ""}" style="background:${colors[Math.abs(id) % colors.length]}">${esc((name || "A").slice(0, 2))}</span>`;
}
function age(tick, o) {
  const minutes = Math.max(
    0,
    Math.floor(
      ((o.tick - Number(tick)) * (o.tick_duration_ms || 60000)) / 60000,
    ),
  );
  if (minutes < 1) return o.platform === "xiaohongshu" ? "刚刚" : "now";
  if (minutes < 60)
    return minutes + (o.platform === "xiaohongshu" ? " 分钟前" : "m");
  if (minutes < 1440)
    return (
      Math.floor(minutes / 60) +
      (o.platform === "xiaohongshu" ? " 小时前" : "h")
    );
  return (
    Math.floor(minutes / 1440) + (o.platform === "xiaohongshu" ? " 天前" : "d")
  );
}
function nativeMediaUrl(asset) {
  return agoraPath(
    runId
      ? "/api/run-media?run=" +
          encodeURIComponent(runId) +
          "&id=" +
          encodeURIComponent(asset.asset_id)
      : "/media/" +
          encodeURIComponent(asset.asset_id) +
          "?platform=" +
          encodeURIComponent(
            selectedPlatform || current()?.platform || "xiaohongshu",
          ),
  );
}
function nativeMedia(asset, classes = "") {
  return asset.media_type === "video"
    ? `<video class="${classes}" src="${nativeMediaUrl(asset)}" ${editable() && current()?.screen === "detail" ? "controls" : ""} preload="metadata" playsinline></video>`
    : `<img class="${classes}" src="${nativeMediaUrl(asset)}" alt="${esc(asset.alt_text || asset.caption || "")}" loading="lazy" decoding="async" ${asset.width && asset.height ? `width="${asset.width}" height="${asset.height}"` : ""}/>`;
}
function bodyText(text) {
  return String(text ?? "")
    .split(/(#[\p{L}\p{N}_]+)/gu)
    .map((part) =>
      part.startsWith("#")
        ? '<span class="p-hashtag">' + esc(part) + "</span>"
        : esc(part),
    )
    .join("")
    .replace(/\n/g, "<br/>");
}
function searchbar(o, placeholder, classes = "") {
  return `<form class="p-search ${classes}" data-search>${pi("search")}<input aria-label="${esc(placeholder)}" placeholder="${esc(placeholder)}" value="${o.screen === "search" ? esc(o.query) : ""}" ${!editable() ? "readonly" : ""}/><button aria-label="搜索" ${!editable() ? "disabled" : ""}>${pi("search")}</button></form>`;
}
function brand(o) {
  return o.platform === "xiaohongshu"
    ? '<span class="brand-xhs">小红书</span>'
    : o.platform === "x"
      ? '<span class="brand-x" aria-label="X"><svg viewBox="0 0 24 24"><path d="M18.9 2H22l-6.8 7.8L23.2 22h-6.3l-5-7.6L5.2 22H2.1l8.3-9.6L1 2h6.5l4.6 7Zm-1.1 18h1.7L6.5 3.9H4.7Z" fill="currentColor" stroke="none"/></svg></span>'
      : '<span class="brand-reddit"><svg viewBox="0 0 32 32"><path d="m17 11 2-7 6 1"/><circle cx="26" cy="5" r="2"/><ellipse cx="16" cy="20" rx="11" ry="8" fill="currentColor"/><circle cx="4" cy="16" r="3"/><circle cx="28" cy="16" r="3"/><circle cx="12" cy="19" r="1.5" class="alien-eye"/><circle cx="20" cy="19" r="1.5" class="alien-eye"/><path d="M11 23q5 4 10 0" class="alien-smile"/></svg><b>reddit</b></span>';
}
function empty(text) {
  return `<div class="p-empty">${pi("search")}<h3>${esc(text)}</h3><p>${current()?.platform === "xiaohongshu" ? "试试浏览其他内容，或发布你的第一篇笔记。" : "Try another feed or share your first post."}</p></div>`;
}
function followButton(p, o) {
  if (p.author_id === o.user_id) return "";
  return nb(
    p.following_author ? "unfollow_user" : "follow_user",
    { followee_id: p.author_id },
    p.following_author
      ? o.platform === "xiaohongshu"
        ? "已关注"
        : "Following"
      : o.platform === "xiaohongshu"
        ? "关注"
        : "Follow",
    "p-follow " + (p.following_author ? "following" : ""),
  );
}
function postMenu(p, o) {
  const owned = (p.owner_id ?? p.author_id) === o.user_id;
  return `<details class="p-post-menu"><summary aria-label="${o.platform === "xiaohongshu" ? "更多操作" : "More actions"}" title="${o.platform === "xiaohongshu" ? "更多操作" : "More actions"}">${pi("more")}</summary><div>${owned ? (o.available_actions.edit_post ? nb("edit_post", { post_id: p.post_id }, o.platform === "xiaohongshu" ? "编辑笔记" : "Edit") : "") + nb("delete_post", { post_id: p.post_id }, o.platform === "xiaohongshu" ? "删除" : "Delete", "p-danger") : nb("not_interested", { post_id: p.post_id }, o.platform === "xiaohongshu" ? "不感兴趣" : "Show fewer posts like this")}${o.platform === "x" && o.available_actions.quote_post ? nb("quote_post", { post_id: p.post_id }, "Quote") : ""}<button type="button" data-copy-link="${p.post_id}" ${!editable() ? "disabled" : ""}>${pi("share")}${o.platform === "xiaohongshu" ? "复制链接" : "Copy link"}</button>${o.available_actions.remove_post ? nb("remove_post", { post_id: p.post_id }, "Remove as moderator") : ""}</div></details>`;
}
function xhsNav(o) {
  return `<aside class="xhs-sidebar">${brand(o)}<nav>${nb("refresh", { feed_type: "discover" }, pi("home") + "<span>发现</span>", "p-nav " + (o.screen === "feed" ? "active" : ""))}${nb("open_studio", {}, pi("plus") + "<span>发布</span>", "p-nav " + (o.screen === "studio" ? "active" : ""))}${nb("open_notifications", {}, pi("bell") + "<span>通知</span>", "p-nav " + (o.screen === "notifications" ? "active" : ""))}${nb("view_profile", {}, av(o.account.name, o.user_id) + "<span>我</span>", "p-nav " + (o.screen === "profile" ? "active" : ""))}</nav><div class="xhs-nav-footer">${nb("view_saved", {}, pi("bookmark") + "<span>我的收藏</span>", "p-nav")}<span>社区 · 生活 · 兴趣</span></div></aside>`;
}
function xhsCard(p, o) {
  return `<article class="xhs-card" data-post="${p.post_id}" tabindex="0"><div class="xhs-cover">${p.assets?.length ? nativeMedia(p.assets[0]) : '<div class="text-cover">' + esc(p.body.slice(0, 100)) + "</div>"}${p.post_type === "gallery" ? '<span class="cover-badge">' + pi("image") + "</span>" : ""}${p.post_type === "video" ? '<span class="cover-badge">' + pi("video") + "</span>" : ""}</div><div class="xhs-card-info"><h3>${esc(p.title || p.body.slice(0, 36))}</h3><div class="xhs-card-meta">${nb("view_profile", { user_id: p.author_id }, av(p.author_name, p.author_id) + `<span>${esc(p.author_name)}</span>`, "p-author-link")}${nb(p.liked ? "unlike_post" : "like_post", { post_id: p.post_id }, pi("heart") + `<span>${p.num_likes || "赞"}</span>`, "p-like " + (p.liked ? "on" : ""))}</div></div></article>`;
}
function commentItems(items, o, level = 0) {
  return (items || [])
    .map(
      (c) =>
        `<div class="p-comment ${level > 2 ? "flat-reply" : ""} ${c.deleted ? "deleted" : ""}">${av(c.author_name, c.author_id)}<div class="p-comment-main"><div class="comment-identity"><span>${o.platform === "reddit" ? "u/" : ""}${esc(c.author_name || c.author_handle || c.author_id)}</span>${c.is_pinned ? "<b>置顶</b>" : ""}${c.author_id === o.post?.author_id && o.platform === "reddit" ? "<b>OP</b>" : ""}</div><div class="comment-body">${bodyText(c.deleted ? "[deleted]" : c.content)}</div><div class="comment-meta"><span>${age(c.created_at, o)}</span>${!c.deleted ? nb("create_comment", { post_id: o.post.post_id, parent_comment_id: c.comment_id }, o.platform === "xiaohongshu" ? "回复" : "Reply") : ""}${o.platform === "reddit" ? nb(c.vote === 1 ? "clear_comment_vote" : "upvote_comment", { comment_id: c.comment_id }, pi("arrow"), "comment-vote " + (c.vote === 1 ? "on" : "")) + `<span>${c.score}</span>` + nb(c.vote === -1 ? "clear_comment_vote" : "downvote_comment", { comment_id: c.comment_id }, pi("down"), "comment-vote " + (c.vote === -1 ? "down" : "")) : nb(c.liked ? "unlike_comment" : "like_comment", { comment_id: c.comment_id }, pi("heart") + (c.num_likes || ""), "comment-like " + (c.liked ? "on" : ""))}${c.author_id === o.user_id && !c.deleted ? nb("delete_comment", { comment_id: c.comment_id }, o.platform === "xiaohongshu" ? "删除" : "Delete") : ""}${o.platform === "xiaohongshu" && o.post.author_id === o.user_id && !c.deleted ? nb(c.is_pinned ? "unpin_comment" : "pin_comment", { comment_id: c.comment_id }, c.is_pinned ? "取消置顶" : "置顶") : ""}</div>${c.replies?.length ? '<div class="comment-replies">' + commentItems(c.replies, o, level + 1) + "</div>" : ""}</div></div>`,
    )
    .join("");
}
function commentForm(o) {
  return `<form class="p-comment-form" data-comment>${av(o.account.name, o.user_id)}<textarea name="reply" aria-label="${o.platform === "xiaohongshu" ? "评论内容" : "Reply text"}" rows="1" placeholder="${o.platform === "xiaohongshu" ? "说点什么…" : o.platform === "x" ? "Post your reply" : "Join the conversation"}" ${!editable() ? "readonly" : ""}></textarea><button class="p-primary" ${!editable() ? "disabled" : ""}>${o.platform === "xiaohongshu" ? "发送" : o.platform === "x" ? "Reply" : "Comment"}</button></form>`;
}
function xhsNote(o) {
  const p = o.post,
    visible = p.assets.filter(
      (a) => !p.visible_asset_ids || p.visible_asset_ids.includes(a.asset_id),
    ),
    gallery = p.post_type === "gallery";
  return `<div class="xhs-note-overlay" role="dialog" aria-modal="true" aria-label="笔记详情"><div class="xhs-note"><div class="note-media">${visible.length ? visible.map((a) => nativeMedia(a)).join("") : '<div class="note-text-media">' + esc(p.title || p.body) + "</div>"}${gallery ? `<div class="note-carousel">${nb("view_media", { index: Math.max(0, (p.media_index || 0) - 1) }, pi("back"), (p.media_index || 0) === 0 ? "carousel-end" : "")}<span>${(p.media_index || 0) + 1} / ${p.assets.length}</span>${nb("view_media", { index: Math.min(p.assets.length - 1, (p.media_index || 0) + 1) }, pi("forward"), (p.media_index || 0) === p.assets.length - 1 ? "carousel-end" : "")}</div>` : ""}</div><div class="note-panel"><div class="note-author">${nb("view_profile", { user_id: p.author_id }, av(p.author_name, p.author_id) + `<span>${esc(p.author_name)}</span>`, "p-author-link")}${followButton(p, o)}${postMenu(p, o)}</div><div class="note-scroll"><h1>${esc(p.title || "")}</h1><div class="note-content">${bodyText(p.body)}</div><div class="note-topics">${p.topics.map((t) => nb("search", { query: t }, "#" + esc(t))).join(" ")}</div><div class="note-location">${age(p.created_at, o)}${p.location ? " · " + esc(p.location) : ""}${p.edited_at_tick !== null ? " · 已编辑" : ""}</div><div class="note-comments-title">共 ${p.num_comments} 条评论</div>${commentItems(p.comments, o)}${commentPaging(o, "查看更多评论")}</div><div class="note-bottom"><div class="note-reactions">${nb(p.liked ? "unlike_post" : "like_post", { post_id: p.post_id }, pi("heart") + p.num_likes, "p-like " + (p.liked ? "on" : ""))}${nb(p.saved ? "uncollect_post" : "collect_post", { post_id: p.post_id }, pi("star") + p.num_collections, "p-save " + (p.saved ? "on" : ""))}<span>${pi("comment")}${p.num_comments}</span>${nb("dwell", { duration_ms: 10000 }, "阅读", "note-read")}${o.collections.length ? nb("add_to_collection", { post_id: p.post_id }, pi("bookmark"), "folder-action") : ""}<button type="button" data-copy-link="${p.post_id}" aria-label="复制链接" title="复制链接" ${!editable() ? "disabled" : ""}>${pi("share")}</button></div>${commentForm(o)}</div></div></div>${nb("back", {}, pi("close"), "note-close")}</div>`;
}
function nativeComposer(o) {
  const d = o.draft || {},
    library = o.asset_library || [];
  return `<section class="native-composer ${o.platform}"><div class="composer-title">${nb("refresh", { feed_type: o.contract.feeds[0] }, pi("back"), "p-back")}<h1>${o.platform === "xiaohongshu" ? "发布笔记" : o.platform === "x" ? "Compose a post" : "Create a post"}</h1></div>${o.platform === "xiaohongshu" ? '<div class="composer-tabs"><span class="active">发布图文</span><span>视频素材也可在下方上传</span></div>' : ""}<form id="composeForm"><div class="composer-fields">${o.platform === "reddit" ? `<label class="community-picker">${pi("person")}<select name="community" aria-label="Community">${o.communities.map((c) => `<option value="${esc(c.name)}" ${d.community === c.name ? "selected" : ""}>${esc(c.name)} · ${esc(c.title)}</option>`).join("")}</select></label>` : ""}${o.platform !== "x" ? `<input aria-label="${o.platform === "xiaohongshu" ? "笔记标题" : "Post title"}" class="composer-post-title" name="title" placeholder="${o.platform === "xiaohongshu" ? "填写标题会有更多赞哦" : "Title"}" value="${esc(d.title || "")}" maxlength="${o.contract.title_limit}" required/>` : ""}<textarea aria-label="${o.platform === "xiaohongshu" ? "笔记正文" : "Post text"}" class="composer-body" name="body" placeholder="${o.platform === "x" ? "What's happening?!" : o.platform === "reddit" ? "Body text (optional)" : "添加正文，分享你的体验…"}" ${!editable() ? "readonly" : ""}>${esc(d.body || "")}</textarea>${o.platform === "xiaohongshu" ? `<div class="composer-subfields"><input aria-label="话题" name="topics" placeholder="#添加话题（逗号分隔）" value="${esc((d.topics || []).join(", "))}"/><input aria-label="地点" name="location" placeholder="添加地点" value="${esc(d.location || "")}"/></div>` : o.platform === "reddit" ? `<input aria-label="Link URL" name="url" type="url" placeholder="URL for a link post (optional)" value="${esc(d.url || "")}"/>` : ""}</div><div class="composer-media-heading"><span>${o.platform === "xiaohongshu" ? "图片与视频" : o.platform === "x" ? "Media" : "Images & video"}</span><label class="p-upload">${pi("plus")}${o.platform === "xiaohongshu" ? "上传素材" : "Upload"}<input aria-label="${o.platform === "xiaohongshu" ? "上传素材" : "Upload media"}" id="nativeUpload" type="file" accept="image/jpeg,image/png,image/webp,video/mp4,video/webm" ${!editable() ? "disabled" : ""}/></label></div><div id="selectedAssets" class="composer-selected"></div><div class="composer-library">${library.map((a) => `<button class="library-asset ${(d.assets || []).some((s) => s.asset_id === a.asset_id) ? "selected" : ""}" type="button" aria-label="${esc(a.alt_text || a.caption || "Select media")}" data-pick="${esc(a.asset_id)}" ${!editable() ? "disabled" : ""}>${nativeMedia(a)}<span>✓</span></button>`).join("") || '<div class="upload-placeholder">' + pi("image") + "<span>" + (o.platform === "xiaohongshu" ? "上传图片或视频，开始创作" : "Add media to your account library") + "</span></div>"}</div><div class="library-paging">${o.library_offset ? nb("view_asset_library", { offset: Math.max(0, o.library_offset - 20) }, pi("back")) : ""}<span>${o.library_total} ${o.platform === "xiaohongshu" ? "份素材" : "assets"}</span>${o.library_offset + 20 < o.library_total ? nb("view_asset_library", { offset: o.library_offset + 20 }, pi("forward")) : ""}</div><div class="composer-footer"><output data-character-count class="character-count" aria-label="Character count"></output><span>${o.platform === "xiaohongshu" ? "已选素材顺序会保存在草稿中" : "Your draft keeps the selected media order."}</span><button type="submit" ${!editable() ? "disabled" : ""}>${o.platform === "xiaohongshu" ? "存草稿" : "Save draft"}</button><button type="submit" class="p-primary" data-publish="1" ${!editable() ? "disabled" : ""}>${o.platform === "xiaohongshu" ? "发布" : o.platform === "x" ? "Post" : "Post"}</button>${o.draft ? nb("publish_draft", {}, o.platform === "xiaohongshu" ? "发布已存草稿" : "Publish saved draft", "p-draft-publish") : ""}</div></form></section>`;
}
function notifications(o) {
  const labels = {
    like: "赞了你的内容",
    comment: "评论了你的内容",
    reply: "回复了你",
    follow: "关注了你",
    repost: "转发了你的内容",
    quote: "引用了你的内容",
  };
  return `<section class="notifications-page"><h1>${o.platform === "xiaohongshu" ? "通知" : o.platform === "x" ? "Notifications" : "Inbox"}</h1><div class="notification-tabs"><button type="button" class="active" data-notification-filter="all">${o.platform === "xiaohongshu" ? "全部" : "All"}</button><button type="button" data-notification-filter="comment,reply,quote">${o.platform === "xiaohongshu" ? "评论和回复" : "Replies"}</button><button type="button" data-notification-filter="like,repost">${o.platform === "xiaohongshu" ? "收到的赞" : "Likes & reposts"}</button><button type="button" data-notification-filter="follow">${o.platform === "xiaohongshu" ? "新增关注" : "Follows"}</button></div>${o.notifications.map((n) => `<div class="notification-row" data-notification-kind="${esc(n.kind)}">${av(n.actor_name, n.actor_id)}<div><b>${esc(n.actor_name || n.actor_handle || n.actor_id)}</b><span>${o.platform === "xiaohongshu" ? " " + (labels[n.kind] || n.kind) : " " + esc({ like: "liked your post", comment: "commented on your post", reply: "replied to you", follow: "followed you", repost: "reposted your post", quote: "quoted your post" }[n.kind] || n.kind)}</span><p>${esc(n.content)}</p><small>${age(n.tick, o)}</small></div>${n.post_id ? nb("open_notification", { notification_id: n.notification_id }, pi("comment")) : ""}</div>`).join("") || empty(o.platform === "xiaohongshu" ? "还没有通知" : "You’re all caught up")}</section>`;
}
function profileHeader(o) {
  const p = o.profile;
  if (!p) return "";
  const own = p.user_id === o.user_id;
  const tabs =
    o.platform === "xiaohongshu"
      ? ["notes", "saved"]
      : o.platform === "x"
        ? ["posts", "replies", "media"]
        : ["posts", "comments", "saved"];
  const labels = {
    notes: "笔记",
    saved: o.platform === "xiaohongshu" ? "收藏" : "Saved",
    posts: "Posts",
    replies: "Replies",
    media: "Media",
    comments: "Comments",
  };
  return `<div class="p-profile ${o.platform}">${o.platform !== "xiaohongshu" ? '<div class="profile-banner"></div>' : ""}<div class="profile-content">${av(p.name, p.user_id, true)}<div><h1>${esc(p.name)}</h1><span>${o.platform === "reddit" ? "u/" : o.platform === "xiaohongshu" ? "小红书号：" : "@"}${esc(p.handle)}</span><p>${esc(p.bio)}</p><div class="profile-stats"><b>${p.following}</b> ${o.platform === "xiaohongshu" ? "关注" : "Following"} <b>${p.followers}</b> ${o.platform === "xiaohongshu" ? "粉丝" : "Followers"}${o.platform === "xiaohongshu" ? ` <b>${p.received_likes + p.received_saves}</b> 获赞与收藏` : ""}</div></div>${own ? nb("edit_profile", {}, o.platform === "xiaohongshu" ? "编辑资料" : "Edit profile", "profile-edit") : nb(p.following_author ? "unfollow_user" : "follow_user", { followee_id: p.user_id }, p.following_author ? "Following" : "Follow", "p-follow")}</div><div class="profile-tabs">${tabs.map((tab) => nb("view_profile", { user_id: p.user_id, tab }, labels[tab], (p.tab === tab ? "active" : "") + (tab === "saved" && !own ? " private-tab" : ""))).join("")}</div></div>`;
}
function xhsPage(o) {
  let content;
  if (o.screen === "studio") content = nativeComposer(o);
  else if (o.screen === "notifications") content = notifications(o);
  else {
    const head =
      o.screen === "profile"
        ? profileHeader(o)
        : o.screen === "saved" || o.screen === "collection"
          ? `<div class="saved-heading"><h1>${o.screen === "collection" ? "收藏专辑" : "我的收藏"}</h1>${nb("create_collection", {}, "新建专辑", "p-follow")}</div><div class="collection-pills">${o.collections.map((f) => nb("view_collection", { folder_id: f.folder_id }, esc(f.name))).join("")}</div>`
          : "";
    const categories =
      o.screen === "feed"
        ? `<div class="xhs-discovery"><div class="xhs-feed-switch">${nb("refresh", { feed_type: "following" }, "关注", o.feed_type === "following" ? "active" : "")}${nb("refresh", { feed_type: "discover" }, "发现", o.feed_type === "discover" ? "active" : "")}${nb("refresh", { feed_type: "nearby" }, "附近", o.feed_type === "nearby" ? "active" : "")}</div><div class="xhs-categories"><span class="active">推荐</span>${["摄影", "咖啡", "数码", "城市漫游", "美食"].map((t) => nb("search", { query: t }, t)).join("")}</div></div>`
        : o.screen === "search"
          ? `<div class="search-heading"><span>搜索结果</span><h2>${esc(o.query)}</h2></div>`
          : "";
    content =
      head +
      categories +
      `<div class="xhs-masonry">${o.cards.map((p) => xhsCard(p, o)).join("") || empty("暂时没有笔记")}</div>${nb("scroll", {}, "继续浏览", "p-more-feed")}`;
  }
  return `<div class="xhs-page">${xhsNav(o)}<header class="xhs-header">${searchbar(o, "搜索小红书")}<span class="xhs-header-note">生活兴趣社区</span></header><div class="xhs-main">${content}</div>${o.screen === "detail" && o.post ? xhsNote(o) : ""}</div>`;
}
function xNav(o) {
  return `<aside class="x-sidebar">${brand(o)}<nav>${nb("refresh", { feed_type: "for_you" }, pi("home") + "<span>Home</span>", "p-nav " + (o.screen === "feed" ? "active" : ""))}${nb("search", { query: o.cards[0]?.topics?.[0] || "photography" }, pi("search") + "<span>Explore</span>", "p-nav")}${nb("open_notifications", {}, pi("bell") + "<span>Notifications</span>", "p-nav " + (o.screen === "notifications" ? "active" : ""))}${nb("view_saved", {}, pi("bookmark") + "<span>Bookmarks</span>", "p-nav " + (o.screen === "saved" ? "active" : ""))}${nb("view_profile", {}, pi("person") + "<span>Profile</span>", "p-nav " + (o.screen === "profile" ? "active" : ""))}</nav>${nb("open_studio", {}, "<span>Post</span>" + pi("plus"), "x-post-button")}<div class="x-account">${av(o.account.name, o.user_id)}<div><b>${esc(o.account.name)}</b><small>@${esc(o.account.handle)}</small></div>${pi("more")}</div></aside>`;
}
function xReference(p) {
  const ref = p.original_post;
  if (!ref || p.post_type === "repost") return "";
  return ref.unavailable
    ? '<blockquote class="x-reference">This post is unavailable.</blockquote>'
    : `<blockquote class="x-reference" data-post="${ref.post_id}"><b>${esc(ref.author_name)}</b><span> @${esc(ref.author_handle)}</span><p>${bodyText(ref.body)}</p>${(ref.assets || []).map((a) => nativeMedia(a)).join("")}</blockquote>`;
}
function xCard(p, o, detail = false) {
  return `<article class="x-post ${detail ? "x-post-detail" : ""}" data-post="${p.post_id}" tabindex="0">${p.post_type === "repost" ? `<div class="x-reposted">${pi("repost")}${esc(p.reposted_by || p.author_name)} reposted</div>` : ""}<div class="x-post-layout">${av(p.author_name, p.author_id)}<div class="x-post-main"><div class="x-author">${nb("view_profile", { user_id: p.author_id }, `<b>${esc(p.author_name)}</b>`, "p-author-link")}<span>@${esc(p.author_handle)} · ${age(p.created_at, o)}</span>${postMenu(p, o)}</div><div class="x-post-text">${bodyText(p.quote_body || p.body)}</div>${xReference(p)}${p.assets?.length ? `<div class="x-media-grid images-${p.assets.length}">${p.assets.map((a) => nativeMedia(a)).join("")}</div>` : ""}${detail ? `<div class="x-post-time">${age(p.created_at, o)} · ${p.num_replies || 0} replies</div>` : ""}<div class="x-reactions">${nb("open_post", { post_id: p.post_id }, pi("comment") + `<span>${p.num_replies || p.num_comments || ""}</span>`)}${nb(p.reposted ? "undo_repost" : "repost", { post_id: p.post_id }, pi("repost") + `<span>${p.num_shares || ""}</span>`, p.reposted ? "reposted" : "")}${nb(p.liked ? "unlike_post" : "like_post", { post_id: p.post_id }, pi("heart") + `<span>${p.num_likes || ""}</span>`, "p-like " + (p.liked ? "on" : ""))}${nb(p.saved ? "unbookmark_post" : "bookmark_post", { post_id: p.post_id }, pi("bookmark"), p.saved ? "bookmarked" : "")}${detail ? nb("quote_post", { post_id: p.post_id }, pi("share"), "p-quote") : ""}</div></div></div></article>`;
}
function xRight(o) {
  const authors = [
    ...new Map(
      o.cards
        .filter((p) => p.author_id !== o.user_id)
        .map((p) => [p.author_id, p]),
    ).values(),
  ].slice(0, 3);
  const topics = [...new Set(o.cards.flatMap((p) => p.topics))].slice(0, 4);
  return `<aside class="x-right">${searchbar(o, "Search")}<div class="x-right-box"><h2>What’s happening</h2>${topics.map((t) => `<div class="x-topic"><small>From your feed</small>${nb("search", { query: t }, "<b>#" + esc(t) + "</b>")}</div>`).join("") || "<p>Follow people to see more conversations.</p>"}</div><div class="x-right-box"><h2>Who to follow</h2>${authors.map((p) => `<div class="x-suggest">${av(p.author_name, p.author_id)}<div><b>${esc(p.author_name)}</b><small>@${esc(p.author_handle)}</small></div>${followButton(p, o)}</div>`).join("")}</div><div class="x-right-footer">About · Accessibility · Community</div></aside>`;
}
function xPage(o) {
  let content;
  if (o.screen === "studio") content = nativeComposer(o);
  else if (o.screen === "notifications") content = notifications(o);
  else if (o.screen === "detail" && o.post)
    content = `<div class="x-timeline-header"><div class="x-sticky-heading">${nb("back", {}, pi("back"))}<h1>Post</h1></div></div>${xCard(o.post, o, true)}${commentForm(o)}${(o.post.replies || []).map((p) => xCard(p, o)).join("")}${nb("dwell", { duration_ms: 10000 }, "Read this conversation", "p-more-feed")}`;
  else {
    const head =
      o.screen === "profile"
        ? profileHeader(o)
        : `<div class="x-sticky-heading"><h1>${o.screen === "saved" ? "Bookmarks" : o.screen === "search" ? "Search" : "Home"}</h1></div>`;
    const tabs =
      o.screen === "feed"
        ? `<div class="x-feed-tabs">${nb("refresh", { feed_type: "for_you" }, "For you", o.feed_type === "for_you" ? "active" : "")}${nb("refresh", { feed_type: "following" }, "Following", o.feed_type === "following" ? "active" : "")}</div>`
        : "";
    const inline =
      o.screen === "feed"
        ? `<form class="x-inline-compose" data-inline-post>${av(o.account.name, o.user_id)}<div><textarea name="inline_body" aria-label="Post text" placeholder="What’s happening?!" ${!editable() ? "readonly" : ""}></textarea><div>${nb("open_studio", {}, pi("image"))}<output data-character-count class="character-count"></output><button type="submit" class="p-primary" ${!editable() ? "disabled" : ""}>Post</button></div></div></form>`
        : "";
    content =
      (o.screen === "profile"
        ? head
        : `<div class="x-timeline-header">${head}${tabs}</div>`) +
      inline +
      o.cards.map((p) => xCard(p, o)).join("") +
      (!o.cards.length ? empty("No posts yet") : "") +
      nb("scroll", {}, "Show more", "p-more-feed");
  }
  return `<div class="x-page">${xNav(o)}<div class="x-main">${content}</div>${xRight(o)}${nb("open_studio", {}, pi("plus"), "x-mobile-post")}</div>`;
}
function redditNav(o) {
  return `<aside class="reddit-sidebar"><div>${nb("refresh", { feed_type: "for_you" }, pi("home") + "<span>Home</span>", "p-nav " + (o.screen === "feed" && o.feed_type === "for_you" ? "active" : ""))}${nb("refresh", { feed_type: "popular" }, pi("arrow") + "<span>Popular</span>", "p-nav " + (o.feed_type === "popular" ? "active" : ""))}${nb("refresh", { feed_type: "latest" }, pi("search") + "<span>Latest</span>", "p-nav")}</div><div class="reddit-nav-section"><h3>COMMUNITIES</h3>${o.communities
    .filter((c) => c.joined)
    .map((c) =>
      nb(
        "view_community",
        { community: c.name },
        `<span class="community-avatar">${esc(c.name.slice(2, 3).toUpperCase())}</span><span>${esc(c.name)}</span>`,
        "p-nav " +
          (o.community?.name === c.name && o.screen === "community"
            ? "active"
            : ""),
      ),
    )
    .join(
      "",
    )}${nb("list_communities", {}, pi("search") + "<span>Explore communities</span>", "p-nav")}${nb("create_community", {}, pi("plus") + "<span>Create a community</span>", "p-nav")}</div><div class="reddit-nav-section">${nb("view_profile", {}, pi("person") + "<span>Profile</span>", "p-nav")}${nb("view_saved", {}, pi("bookmark") + "<span>Saved</span>", "p-nav")}</div><span class="reddit-copyright">Community · Guidelines · Help</span></aside>`;
}
function redditCard(p, o, detail = false) {
  return `<article class="reddit-post ${detail ? "reddit-detail" : ""}" data-post="${p.post_id}" tabindex="0"><div class="reddit-post-top"><span class="community-avatar">${esc((p.community || "r/a").slice(2, 3).toUpperCase())}</span>${nb("view_community", { community: p.community }, `<b>${esc(p.community)}</b>`, "p-community-link")}<span>· ${age(p.created_at, o)}</span>${postMenu(p, o)}</div>${detail ? `<div class="reddit-author-line">${nb("view_profile", { user_id: p.author_id }, "u/" + esc(p.author_handle))}</div>` : ""}<h2>${esc(p.title || "")}</h2>${p.original_post ? `<div class="reddit-crosspost"><small>Crossposted from ${esc(p.original_post.community || "another community")}</small><p>${esc(p.original_post.title || p.original_post.body || "Original post unavailable")}</p></div>` : ""}${p.body ? '<div class="reddit-body">' + bodyText(p.body) + "</div>" : ""}${p.url ? '<a class="reddit-link" href="' + esc(p.url) + '" target="_blank" rel="noreferrer">' + esc(p.url) + "</a>" : ""}${
    p.assets?.length
      ? `<div class="reddit-post-media">${p.assets
          .filter(
            (a) =>
              !detail ||
              !p.visible_asset_ids ||
              p.visible_asset_ids.includes(a.asset_id),
          )
          .map((a) => nativeMedia(a))
          .join(
            "",
          )}${detail && p.post_type === "gallery" ? `<div class="reddit-carousel">${nb("view_media", { index: Math.max(0, (p.media_index || 0) - 1) }, pi("back"), (p.media_index || 0) === 0 ? "carousel-end" : "")}<span>${(p.media_index || 0) + 1} / ${p.assets.length}</span>${nb("view_media", { index: Math.min(p.assets.length - 1, (p.media_index || 0) + 1) }, pi("forward"), (p.media_index || 0) === p.assets.length - 1 ? "carousel-end" : "")}</div>` : ""}</div>`
      : ""
  }<div class="reddit-reactions"><span class="vote-pill ${p.vote === 1 ? "upvoted" : p.vote === -1 ? "downvoted" : ""}">${nb(p.vote === 1 ? "clear_post_vote" : "upvote_post", { post_id: p.post_id }, pi("arrow"))}<b>${p.score}</b>${nb(p.vote === -1 ? "clear_post_vote" : "downvote_post", { post_id: p.post_id }, pi("down"))}</span>${nb("open_post", { post_id: p.post_id }, pi("comment") + `<b>${p.num_comments}</b>`, "reddit-pill")}${nb(p.saved ? "unsave_post" : "save_post", { post_id: p.post_id }, pi("bookmark") + (p.saved ? "Saved" : "Save"), "reddit-pill")}${detail ? nb("crosspost", { post_id: p.post_id }, pi("share") + "Crosspost", "reddit-pill") : ""}</div></article>`;
}
function redditRight(o) {
  const c =
    o.community || o.communities.find((c) => c.joined) || o.communities[0];
  if (!c) return "";
  return `<aside class="reddit-right"><section class="reddit-about"><h2>${esc(c.name)}</h2><h3>${esc(c.title)}</h3><p>${esc(c.description || "Share experiences, ask questions, and participate in the community.")}</p><div class="community-stats"><b>${c.members}</b><span>Members</span></div>${nb(c.joined ? "leave_community" : "join_community", { community: c.name }, c.joined ? "Joined" : "Join", "p-community-join")}</section><section class="reddit-rules"><h2>COMMUNITY RULES</h2>${c.rules.map((r, i) => `<div><span>${i + 1}</span>${esc(r)}</div>`).join("")}</section><div class="reddit-right-foot">Respect the people behind the posts.</div></aside>`;
}
function redditSort(o) {
  if (
    o.screen === "feed" &&
    ["for_you", "home", "latest"].includes(o.feed_type)
  )
    return `<div class="reddit-sort"><span>${o.feed_type === "latest" ? "Latest posts" : "Recommended for you"}</span></div>`;
  return `<div class="reddit-sort"><label><select data-sort ${!editable() ? "disabled" : ""}>${["best", "hot", "new", "top"].map((sort) => `<option value="${sort}" ${o.feed_sort === sort ? "selected" : ""}>${sort[0].toUpperCase() + sort.slice(1)}</option>`).join("")}</select>${pi("down")}</label>${o.feed_sort === "top" ? `<select data-time-range ${!editable() ? "disabled" : ""}>${["hour", "day", "week", "month", "year", "all"].map((t) => `<option value="${t}" ${o.time_range === t ? "selected" : ""}>${t === "all" ? "All time" : "Past " + t}</option>`).join("")}</select>` : ""}<span>${pi("image")} Card</span></div>`;
}
function redditPage(o) {
  let content;
  if (o.screen === "studio") content = nativeComposer(o);
  else if (o.screen === "notifications") content = notifications(o);
  else if (o.screen === "profile") {
    content =
      profileHeader(o) +
      (o.profile?.tab === "comments"
        ? (o.profile.comments || [])
            .map(
              (c) =>
                `<article class="profile-comment" data-post="${c.post_id}"><small>${esc(c.community)} · ${esc(c.post_title)}</small><p>${esc(c.content)}</p><span>${c.score} points · ${age(c.created_at, o)}</span></article>`,
            )
            .join("")
        : o.cards.map((p) => redditCard(p, o)).join(""));
  } else if (o.screen === "detail" && o.post) {
    content = `<div class="reddit-back">${nb("back", {}, pi("back"))}</div>${redditCard(o.post, o, true)}<div class="reddit-comments">${commentForm(o)}<div class="reddit-comment-sort"><span>Sort by:</span>${["best", "top", "new"].map((sort) => nb("load_comments", { sort }, sort[0].toUpperCase() + sort.slice(1), (o.comment_sort || "best") === sort ? "active" : "")).join("")}</div>${commentItems(o.post.comments, o)}${commentPaging(o, "View more comments")}${nb("dwell", { duration_ms: 10000 }, "Read discussion", "p-more-feed")}</div>`;
  } else if (o.screen === "communities") {
    content = `<section class="reddit-explore"><h1>Explore communities</h1>${o.communities.map((c) => `<article><div class="community-avatar">${esc(c.name.slice(2, 3).toUpperCase())}</div><div><h2>${esc(c.name)}</h2><p>${esc(c.description || c.title)}</p><small>${c.members} members</small></div>${nb("view_community", { community: c.name }, "Explore", "p-community-join")}</article>`).join("")}</section>`;
  } else {
    let head = "";
    if (o.screen === "community" && o.community) {
      const c = o.community;
      head = `<div class="reddit-community-header"><div class="community-banner"></div><div><span class="community-avatar big">${esc(c.name.slice(2, 3).toUpperCase())}</span><h1>${esc(c.name)}</h1>${nb("open_studio", {}, pi("plus") + "Create post", "reddit-pill")}${nb(c.joined ? "leave_community" : "join_community", { community: c.name }, c.joined ? "Joined" : "Join", "p-community-join")}</div></div>`;
    } else if (o.screen === "feed")
      head = `<div class="reddit-home-tabs">${nb("refresh", { feed_type: "for_you" }, "For You", ["for_you", "home"].includes(o.feed_type) ? "active" : "")}${nb("refresh", { feed_type: "following" }, "Following", o.feed_type === "following" ? "active" : "")}${nb("refresh", { feed_type: "popular" }, "Popular", o.feed_type === "popular" ? "active" : "")}</div>`;
    else
      head = `<h1 class="reddit-page-title">${o.screen === "saved" ? "Saved" : o.screen === "search" ? "Search results for “" + esc(o.query) + "”" : "Latest"}</h1>`;
    content =
      head +
      redditSort(o) +
      o.cards.map((p) => redditCard(p, o)).join("") +
      (!o.cards.length ? empty("No posts in this feed") : "") +
      nb("scroll", {}, "View more posts", "p-more-feed");
  }
  return `<div class="reddit-page"><header class="reddit-header"><button type="button" class="reddit-menu-toggle" data-toggle-nav aria-label="Open navigation" aria-expanded="false">${pi("menu")}</button>${brand(o)}${searchbar(o, o.screen === "community" ? "Search in " + o.community.name : "Search Reddit")}${nb("open_studio", {}, pi("plus") + "<span>Create</span>", "reddit-header-create")}${nb("open_notifications", {}, pi("bell"), "reddit-inbox")}${nb("view_profile", {}, av(o.account.name, o.user_id), "reddit-header-profile")}</header>${redditNav(o)}<button type="button" class="reddit-nav-scrim" data-toggle-nav aria-label="Close navigation"></button><div class="reddit-center"><div class="reddit-main">${content}</div>${o.screen === "studio" ? "" : redditRight(o)}</div></div>`;
}
function commentPaging(o, label) {
  const count = o.post?.comments?.length || 0;
  return `${o.comment_offset ? nb("load_comments", { offset: Math.max(0, o.comment_offset - 20) }, o.platform === "xiaohongshu" ? "上一页评论" : "Previous comments", "p-load-comments") : ""}${count >= 20 ? nb("load_comments", { offset: (o.comment_offset || 0) + 20 }, label, "p-load-comments") : ""}`;
}
function nativeRender(o) {
  const key = viewKey(o),
    signature = JSON.stringify([key, frame >= 0, editable(), o]);
  if (signature === renderedSignature) return;
  const previous = renderedView;
  rememberView();
  const noteOpen =
    o.platform === "xiaohongshu" && o.screen === "detail" && !!o.post;
  document.body.classList.toggle("note-open", noteOpen);
  if (key !== previous) document.body.classList.remove("nav-open");
  document.body.dataset.platform = o.platform;
  document.body.dataset.screen = o.screen;
  $("platformRoot").innerHTML =
    o.platform === "xiaohongshu"
      ? xhsPage(o)
      : o.platform === "x"
        ? xPage(o)
        : redditPage(o);
  wireNative(o);
  if (noteOpen)
    for (const selector of [".xhs-sidebar", ".xhs-header", ".xhs-main"]) {
      const el = $("platformRoot").querySelector(selector);
      if (el) el.inert = true;
    }
  restoreView(o, key, previous);
  renderedView = key;
  renderedSignature = signature;
}
