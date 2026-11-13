/* Product renderers share account state and the same AI tool contract. */
function nativeMediaUrl(asset) {
  return runId
    ? "/api/run-media?run=" +
        encodeURIComponent(runId) +
        "&id=" +
        encodeURIComponent(asset.asset_id)
    : "/media/" +
        encodeURIComponent(asset.asset_id) +
        "?platform=" +
        encodeURIComponent(
          selectedPlatform || current()?.platform || "xiaohongshu",
        );
}
function nativeButton(name, args, text) {
  return actionButton(name, args, text);
}
function nativeAvatar(name) {
  return '<span class="mini-avatar">' + esc((name || "A")[0]) + "</span>";
}
function nativeReference(post) {
  const ref = post.original_post;
  if (!ref) return "";
  if (ref.unavailable)
    return '<blockquote class="quoted">原内容已不可用</blockquote>';
  return `<blockquote class="quoted" data-post="${ref.post_id}"><b>${esc(ref.author_name)}</b><div>${esc(ref.body)}</div>${ref.assets?.length ? '<div class="native-media">' + ref.assets.map(media).join("") + "</div>" : ""}</blockquote>`;
}
function nativeXCard(p) {
  return `<article class="x-post" data-post="${p.post_id}" tabindex="0"><div class="native-author">${nativeAvatar(p.author_name)}<b>${esc(p.author_name)}</b><span>@${esc(p.author_handle)} · ${p.created_at}</span></div>${p.post_type === "repost" ? '<small class="hint">↻ 转发</small>' : ""}<div class="post-text">${esc(p.quote_body || p.body)}</div>${nativeReference(p)}<div class="native-media">${(p.assets || []).map(media).join("")}</div><div class="native-reactions">${nativeButton("open_post", { post_id: p.post_id }, "↩ 回复")}${nativeButton(p.reposted ? "undo_repost" : "repost", { post_id: p.post_id }, "↻ " + p.num_shares)}${nativeButton(p.liked ? "unlike_post" : "like_post", { post_id: p.post_id }, (p.liked ? "♥ " : "♡ ") + p.num_likes)}${nativeButton(p.saved ? "unbookmark_post" : "bookmark_post", { post_id: p.post_id }, p.saved ? "▣ 已保存" : "▢ 书签")}</div></article>`;
}
function nativeRedditCard(p) {
  return `<article class="reddit-post" data-post="${p.post_id}" tabindex="0"><div class="vote-rail">${nativeButton(p.vote === 1 ? "clear_post_vote" : "upvote_post", { post_id: p.post_id }, p.vote === 1 ? "▲" : "△")}<strong>${p.score ?? p.num_likes - p.num_dislikes}</strong>${nativeButton(p.vote === -1 ? "clear_post_vote" : "downvote_post", { post_id: p.post_id }, p.vote === -1 ? "▼" : "▽")}</div><div class="reddit-post-main"><div class="hint">${esc(p.community || "r/general")} · u/${esc(p.author_handle)} · ${p.created_at}</div><h3>${esc(p.title || p.body.slice(0, 80))}</h3><div class="post-text">${esc(p.body)}</div>${p.url ? `<a href="${esc(p.url)}" target="_blank" rel="noreferrer">${esc(p.url)} ↗</a>` : ""}${nativeReference(p)}<div class="native-media">${(p.assets || []).map(media).join("")}</div><div class="native-reactions">${nativeButton("open_post", { post_id: p.post_id }, "☷ " + (p.num_comments || 0) + " 评论")}${nativeButton(p.saved ? "unsave_post" : "save_post", { post_id: p.post_id }, p.saved ? "已保存" : "保存")}</div></div></article>`;
}
function nativeXhsCard(p) {
  return `<article class="post-card" data-post="${p.post_id}" tabindex="0"><div class="cover">${p.assets.length ? media(p.assets[0]) : "<span>" + esc(p.topics[0] || "笔记") + "</span>"}</div><div class="post-info"><div class="post-title">${esc(p.title || p.body.slice(0, 55))}</div><div class="post-meta"><span>${esc(p.author_name)}</span>${nativeButton(p.liked ? "unlike_post" : "like_post", { post_id: p.post_id }, (p.liked ? "♥ " : "♡ ") + p.num_likes)}</div><div class="tags">${p.topics.map((t) => "#" + esc(t)).join(" ")}</div></div></article>`;
}
function nativeComments(items, o) {
  return (items || [])
    .map(
      (c) =>
        `<div class="comment"><div class="hint">${o.platform === "reddit" ? "u/" : "用户 "}${c.author_id}${c.is_pinned ? " · 置顶" : ""}${c.edited_at_tick !== null && c.edited_at_tick !== undefined ? " · 已编辑" : ""}</div><div>${esc(c.content)}</div><div class="comment-actions">${!c.deleted ? (o.platform === "reddit" ? nativeButton(c.vote === 1 ? "clear_comment_vote" : "upvote_comment", { comment_id: c.comment_id }, c.vote === 1 ? "▲" : "△") + " " + c.score + " " + nativeButton(c.vote === -1 ? "clear_comment_vote" : "downvote_comment", { comment_id: c.comment_id }, c.vote === -1 ? "▼" : "▽") : nativeButton(c.liked ? "unlike_comment" : "like_comment", { comment_id: c.comment_id }, (c.liked ? "♥ " : "♡ ") + c.num_likes)) : " "}${!c.deleted ? nativeButton("create_comment", { post_id: o.post.post_id, parent_comment_id: c.comment_id }, "回复") : ""}${c.author_id === o.user_id && !c.deleted ? (o.platform !== "x" ? nativeButton("edit_comment", { comment_id: c.comment_id }, "编辑") : "") + nativeButton("delete_comment", { comment_id: c.comment_id }, "删除") : ""}${o.platform === "xiaohongshu" && o.post.author_id === o.user_id && !c.deleted ? nativeButton(c.is_pinned ? "unpin_comment" : "pin_comment", { comment_id: c.comment_id }, c.is_pinned ? "取消置顶" : "置顶") : ""}</div><div class="reply">${nativeComments(c.replies, o)}</div></div>`,
    )
    .join("");
}
function nativeRender(o) {
  document.body.dataset.platform = o.platform;
  const labels = {
    xiaohongshu: { discover: "发现", following: "关注", nearby: "同城" },
    x: { for_you: "For You", following: "Following" },
    reddit: { home: "Home", popular: "Popular", latest: "Latest" },
  };
  const feeds = o.contract?.feeds || Object.keys(labels[o.platform] || {});
  $("tabs").innerHTML =
    feeds
      .map(
        (f) =>
          `<button class="tab ${o.feed_type === f ? "active" : ""}" data-native-feed="${f}" ${!editable() ? "disabled" : ""}>${esc(labels[o.platform]?.[f] || f)}</button>`,
      )
      .join("") +
    `<button class="refresh" id="nativeRefresh" ${!editable() ? "disabled" : ""}>↻ 刷新</button>`;
  $("tabs").style.display = ["detail", "studio"].includes(o.screen)
    ? "none"
    : "flex";
  let extra = $("nativeNav");
  if (!extra) {
    extra = document.createElement("div");
    extra.id = "nativeNav";
    extra.className = "native-nav";
    $("tabs").after(extra);
  }
  extra.innerHTML =
    nativeButton(
      "view_saved",
      {},
      o.platform === "x"
        ? "Bookmarks"
        : o.platform === "reddit"
          ? "Saved"
          : "我的收藏",
    ) +
    (o.platform === "reddit"
      ? nativeButton("list_communities", {}, "Communities")
      : o.platform === "xiaohongshu"
        ? nativeButton("create_collection", {}, "新建收藏专辑")
        : "") +
    nativeButton("edit_profile", {}, "编辑资料");
  if (o.screen === "studio") {
    const d = o.draft;
    const visible = (d?.assets || [])
      .map((s) => o.asset_library.find((a) => a.asset_id === s.asset_id))
      .filter(Boolean);
    $("content").innerHTML =
      `<div class="detail"><h2>${o.platform === "x" ? "Compose a post" : o.platform === "reddit" ? "Create a post" : "发布笔记"}</h2><p class="hint">${o.platform === "x" ? "标准账号 · 280 加权字符 · 最多 4 张图片" : o.platform === "reddit" ? "选择社区，阅读规则，再发布文字、链接或媒体" : "选择图文或视频，整理素材顺序，保存草稿"}</p>${d ? `<h3>${esc(d.title || "")}</h3><div class="body">${esc(d.body)}</div><div class="gallery">${visible.map(media).join("")}</div><div class="actions">${nativeButton("publish_draft", {}, "发布草稿")}</div>` : '<p class="hint">还没有保存草稿。</p>'}<button id="editDraft" ${!editable() ? "disabled" : ""}>${d ? "编辑草稿" : "开始编辑"}</button><label class="upload-control">上传图片或视频<input type="file" id="nativeUpload" accept="image/jpeg,image/png,image/webp,video/mp4,video/webm" ${!editable() ? "disabled" : ""}></label><h3>账号素材库 · ${o.asset_library.length}</h3><div class="feed">${o.asset_library
        .slice(0, 20)
        .map(
          (a) =>
            `<div class="post-card"><div class="cover">${media(a)}</div><div class="post-info">${esc(a.alt_text || a.media_type)}</div></div>`,
        )
        .join("")}</div></div>`;
    $("editDraft").onclick = () => openEditor(o);
    $("nativeUpload").onchange = (e) => nativeUpload(e.target.files[0]);
  } else if (o.screen === "detail" && o.post) {
    const p = o.post,
      id = { post_id: p.post_id },
      platform = o.platform;
    const visible = p.assets.filter(
      (a) => !p.visible_asset_ids || p.visible_asset_ids.includes(a.asset_id),
    );
    const gallery =
      p.post_type === "gallery" && platform !== "x"
        ? `<div class="gallery-nav">${nativeButton("view_media", { index: Math.max(0, (p.media_index || 0) - 1) }, "←")}<span>${(p.media_index || 0) + 1}/${p.assets.length}</span>${nativeButton("view_media", { index: Math.min(p.assets.length - 1, (p.media_index || 0) + 1) }, "→")}</div>`
        : "";
    const reactions =
      platform === "reddit"
        ? nativeButton(
            p.vote === 1 ? "clear_post_vote" : "upvote_post",
            id,
            "△ " + p.score,
          ) +
          nativeButton(
            p.vote === -1 ? "clear_post_vote" : "downvote_post",
            id,
            "▽",
          ) +
          nativeButton(
            p.saved ? "unsave_post" : "save_post",
            id,
            p.saved ? "已保存" : "保存",
          ) +
          nativeButton("crosspost", id, "Repost / Crosspost")
        : nativeButton(
            p.liked ? "unlike_post" : "like_post",
            id,
            p.liked ? "♥ 已赞" : "♡ 点赞",
          ) +
          (platform === "x"
            ? nativeButton(
                p.reposted ? "undo_repost" : "repost",
                id,
                "↻ Repost",
              ) +
              nativeButton("quote_post", id, "Quote") +
              nativeButton(
                p.saved ? "unbookmark_post" : "bookmark_post",
                id,
                p.saved ? "已保存" : "Bookmark",
              )
            : nativeButton(
                p.saved ? "uncollect_post" : "collect_post",
                id,
                p.saved ? "★ 已收藏" : "☆ 收藏",
              ) + nativeButton("add_to_collection", id, "加入专辑"));
    const editing =
      (p.owner_id || p.author_id) === o.user_id
        ? (platform !== "x" ? nativeButton("edit_post", id, "编辑") : "") +
          nativeButton("delete_post", id, "删除")
        : "";
    const moderation = o.available_actions.remove_post
      ? nativeButton("remove_post", id, "版务移除")
      : "";
    const video = p.assets.some((a) => a.media_type === "video")
      ? `<div class="actions">${nativeButton("play_video", { duration_ms: 10000 }, "播放 10 秒")}${nativeButton("seek_video", {}, "跳转")}<span class="hint">位置 ${Math.round((p.video_position_ms || 0) / 1000)} 秒</span></div>`
      : "";
    $("content").innerHTML =
      `<div class="detail"><div class="detail-top">${nativeButton("back", {}, "← 返回")}<div class="native-author">${nativeAvatar(p.author_name)}<b>${esc(p.author_name)}</b></div>${p.author_id !== o.user_id ? nativeButton("follow_user", { followee_id: p.author_id }, "关注") : ""}</div>${platform === "reddit" ? '<p class="hint">' + esc(p.community) + "</p>" : ""}${p.title ? "<h2>" + esc(p.title) + "</h2>" : ""}<div class="body">${esc(p.quote_body || p.body)}</div>${p.url ? '<a href="' + esc(p.url) + '" target="_blank" rel="noreferrer">' + esc(p.url) + "</a>" : ""}${nativeReference(p)}<div class="gallery">${visible.map(media).join("")}</div>${gallery}${video}<div class="actions">${reactions}${nativeButton("dwell", { duration_ms: 10000 }, "阅读 10 秒")}${editing}${moderation}</div><div class="comments"><h3>${platform === "x" ? "Replies" : "评论"}</h3>${platform === "x" ? (p.replies || []).map(nativeXCard).join("") : nativeComments(p.comments, o)}${platform !== "x" ? '<div class="actions">' + nativeButton("load_comments", { sort: "best" }, "热门评论") + nativeButton("load_comments", { sort: "new" }, "最新评论") + nativeButton("load_comments", { offset: (o.comment_offset || 0) + 20 }, "更多评论") + "</div>" : ""}<form id="commentForm"><textarea id="commentText" placeholder="${platform === "x" ? "Post your reply" : "参与讨论…"}" ${!editable() ? "disabled" : ""}></textarea><button class="primary wide" ${!editable() ? "disabled" : ""}>${platform === "x" ? "Reply" : "发表评论"}</button></form></div></div>`;
    $("commentForm").onsubmit = (e) => {
      e.preventDefault();
      act(
        platform === "x" ? "reply_post" : "create_comment",
        platform === "x"
          ? { post_id: p.post_id, body: $("commentText").value }
          : { post_id: p.post_id, content: $("commentText").value },
      );
    };
  } else if (o.screen === "communities") {
    $("content").innerHTML =
      `<div class="detail"><h2>Explore communities</h2>${nativeButton("create_community", {}, "创建社区")}${o.communities.map((c) => `<div class="community-card"><h3>${esc(c.name)} · ${esc(c.title)}</h3><p>${esc(c.description)}</p><div class="hint">${c.members} 位成员 · ${esc(c.visibility)}${c.role === "moderator" ? " · 你是版主" : ""}</div><ul>${c.rules.map((r) => "<li>" + esc(r) + "</li>").join("")}</ul><div class="actions">${nativeButton("view_community", { community: c.name }, "打开")}${nativeButton(c.joined ? "leave_community" : "join_community", { community: c.name }, c.joined ? "Joined" : "Join")}${c.role === "moderator" ? nativeButton("approve_member", { community: c.name }, "批准成员") : ""}</div></div>`).join("")}</div>`;
  } else {
    let intro = "";
    if (o.screen === "profile" && o.profile)
      intro = `<div class="detail"><h2>${esc(o.profile.name)}</h2><p>${esc(o.profile.bio)}</p><span class="hint">${o.profile.followers} followers · ${o.profile.following} following</span></div>`;
    if (o.screen === "notifications")
      intro = `<div class="detail"><h2>通知与回复</h2>${o.notifications.map((n) => `<div class="comment">${esc(n.kind)} · 用户 ${n.actor_id}<p>${esc(n.content)}</p>${nativeButton("open_notification", { notification_id: n.notification_id }, "查看")}</div>`).join("") || '<p class="hint">暂无通知</p>'}</div>`;
    if (o.screen === "community" && o.community) {
      const c = o.community;
      intro = `<div class="detail"><h2>${esc(c.name)}</h2><p>${esc(c.description)}</p><ul>${c.rules.map((r) => "<li>" + esc(r) + "</li>").join("")}</ul><div class="actions">${nativeButton(c.joined ? "leave_community" : "join_community", { community: c.name }, c.joined ? "Joined" : "Join")}${["hot", "new", "top"].map((sort) => nativeButton("view_community", { community: c.name, sort }, sort)).join("")}</div></div>`;
    }
    if (o.screen === "collection")
      intro = '<div class="detail"><h2>收藏专辑</h2></div>';
    const cards =
      o.platform === "x"
        ? o.cards.map(nativeXCard)
        : o.platform === "reddit"
          ? o.cards.map(nativeRedditCard)
          : o.cards.map(nativeXhsCard);
    $("content").innerHTML =
      intro +
      `<div class="${o.platform === "xiaohongshu" ? "feed" : "native-timeline"}">${cards.join("") || '<div class="empty">暂无内容。试试刷新、搜索或加入社区。</div>'}</div><div class="feed-footer">${nativeButton("scroll", {}, "继续浏览 ↓")}</div>`;
  }
  if (o.screen === "detail" && o.post) {
    for (const video of $("content").querySelectorAll("video"))
      video.onloadedmetadata = () => {
        video.currentTime = Math.min(
          video.duration || 0,
          (o.post.video_position_ms || 0) / 1000,
        );
      };
  }
  $("tabs").onclick = (e) => {
    const b = e.target.closest("[data-native-feed]");
    if (b) {
      const args = { feed_type: b.dataset.nativeFeed };
      if (args.feed_type === "nearby") {
        const location = prompt("输入要浏览的城市，例如：上海");
        if (!location) return;
        args.location = location;
      }
      act("refresh", args);
    }
  };
  $("nativeRefresh").onclick = () =>
    act("refresh", { feed_type: o.contract?.feeds[0] || "discover" });
}
async function nativeAction(type, args) {
  if (!editable()) return;
  const value = { ...args };
  if (["create_collection", "create_community"].includes(type)) {
    const name = prompt(
      type === "create_community" ? "社区名称（如 r/photography）" : "专辑名称",
    );
    if (!name) return;
    value.name = name;
    if (type === "create_community")
      value.title = prompt("社区标题", name) || name;
  }
  if (type === "edit_profile") {
    const bio = prompt("个人简介", current().account.bio || "");
    if (bio === null) return;
    value.bio = bio;
  }
  if (
    ["edit_post", "quote_post", "edit_comment", "create_comment"].includes(
      type,
    ) &&
    !value.body &&
    !value.content &&
    !value.quote_body
  ) {
    const text = prompt(
      type === "quote_post" ? "引用时的文字" : "输入内容",
      type === "edit_post" ? current().post.body : "",
    );
    if (text === null) return;
    if (type === "edit_post") value.body = text;
    else if (type === "quote_post") value.quote_body = text;
    else value.content = text;
  }
  if (["crosspost", "approve_member"].includes(type)) {
    if (!value.community) value.community = prompt("目标社区（r/...）");
    if (!value.community) return;
    if (type === "approve_member") {
      value.user_id = Number(prompt("要批准的用户 ID"));
      if (!value.user_id) return;
    }
  }
  if (type === "add_to_collection") {
    const folders = current().collections || [];
    value.folder_id = Number(
      prompt(
        "专辑 ID：" + folders.map((f) => f.folder_id + " " + f.name).join("，"),
      ),
    );
    if (!value.folder_id) return;
  }
  if (type === "seek_video") {
    const seconds = prompt("跳转到第几秒？");
    if (seconds === null) return;
    value.position_ms = Math.round(Number(seconds) * 1000);
  }
  return act(type, value);
}
async function nativeUpload(file) {
  if (!file) return;
  if (file.size > 8 * 1024 * 1024) return toast("上传文件须小于 8 MiB");
  const data = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(",")[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
  try {
    await api("/api/assets", {
      user_id: current().user_id,
      filename: file.name,
      data_base64: data,
    });
    await loadSession(sessionId);
    toast("素材已加入账号素材库");
  } catch (e) {
    toast(e.message);
  }
}
