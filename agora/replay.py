"""Small trajectory metadata and separately fetched exact observations."""

import copy


def preview_action(action, result):
    action, result = copy.deepcopy(action), copy.deepcopy(result)
    shortened = False
    for key, value in action.get("arguments", {}).items():
        if isinstance(value, str) and len(value) > 1000:
            action["arguments"][key] = value[:1000]
            shortened = True
        elif key == "assets" and isinstance(value, list):
            action["arguments"][key] = [
                {
                    k: v[:120] if isinstance(v, str) and k == "caption" else v
                    for k, v in item.items()
                    if k in {"asset_id", "role", "caption"}
                }
                for item in value[:20]
            ]
    if "creation" in result:
        result.pop("creation")
        shortened = True
    return action, result, shortened
