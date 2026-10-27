"""Descriptive feedback windows; these do not assert causal adaptation."""


def _comments(nodes):
    for node in nodes:
        yield node
        yield from _comments(node.get("replies", []))


def feedback_windows(records):
    steps = [row for row in records if row.get("record_type") == "step"]
    windows = []
    for row in steps:
        for event in row.get("events", []):
            if event["event_type"] != "scheduled_feedback":
                continue
            payload = event["payload"]
            if payload.get("valence") != "negative":
                continue
            post_id, comment_id = int(event["target_id"]), payload.get("comment_id")
            visible_steps = [
                step
                for step in steps
                if step["tick_before"] >= event["tick"]
                and any(
                    post["post_id"] == post_id
                    and any(
                        comment["comment_id"] == comment_id
                        for comment in _comments(post.get("comments", []))
                    )
                    for post in step["observation"]["feed"]
                )
            ]
            first = visible_steps[0]["step"] if visible_steps else None
            responses = [
                step
                for step in steps
                if first is not None
                and step["step"] >= first
                and step["action"]["action_type"]
                in {"create_comment", "reply_comment", "create_post", "quote_post"}
            ]
            windows.append(
                {
                    "feedback_tick": event["tick"],
                    "post_id": post_id,
                    "comment_id": comment_id,
                    "first_observed_step": first,
                    "response_action_ids": [step["action_id"] for step in responses],
                    "observer_trust_change_after_feedback": round(
                        sum(
                            transition["after"]["trust"] - transition["before"]["trust"]
                            for step in responses
                            for transition in step.get("state_transitions", [])
                        ),
                        6,
                    ),
                }
            )
    return {
        "status": "descriptive_not_causal",
        "negative_feedback_count": len(windows),
        "observed_feedback_count": sum(
            item["first_observed_step"] is not None for item in windows
        ),
        "windows": windows,
    }
