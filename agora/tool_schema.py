"""Generate conventional function schemas from the current screen's tools."""


def tool_definitions(observation):
    result = []
    integer = {
        "post_id",
        "user_id",
        "comment_id",
        "parent_comment_id",
        "followee_id",
        "folder_id",
        "notification_id",
        "index",
        "offset",
        "limit",
        "duration_ms",
        "position_ms",
    }
    for name, spec in observation["available_actions"].items():
        fields = spec.get("required", []) + spec.get("optional", [])
        properties = {}
        for field in fields:
            if field in integer:
                properties[field] = {
                    "type": "integer",
                    "minimum": 0
                    if field in {"index", "offset", "duration_ms", "position_ms"}
                    else 1,
                }
            elif field == "assets":
                properties[field] = {
                    "type": "array",
                    "maxItems": observation["contract"]["max_images"],
                    "items": {
                        "type": "object",
                        "properties": {
                            "asset_id": {"type": "string"},
                            "role": {"type": "string", "enum": ["content", "cover"]},
                            "caption": {"type": "string"},
                        },
                        "required": ["asset_id"],
                        "additionalProperties": False,
                    },
                }
            elif field in {"topics", "rules"}:
                properties[field] = {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 20,
                }
            else:
                properties[field] = {"type": "string"}
            if field == "feed_type":
                properties[field]["enum"] = observation["contract"]["feeds"]
        result.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": f"{name} on {observation['platform']}. Use only account-visible objects and assets. Changes return an auditable receipt.",
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": spec.get("required", []),
                        "additionalProperties": False,
                    },
                },
            }
        )
    return result
