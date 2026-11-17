"""Mount the console under a reverse-proxy path without rewriting responses."""

import json
import re
from pathlib import Path
from urllib.parse import urlsplit


def validate_mount(base_path, public_origin=None):
    if base_path and not re.fullmatch(r"(?:/[A-Za-z0-9_-]+)+", base_path):
        raise ValueError("base_path must be an absolute path without a trailing slash")
    if public_origin:
        parts = urlsplit(public_origin)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.netloc
            or parts.path
            or parts.query
            or parts.fragment
        ):
            raise ValueError("public_origin must contain only scheme and host")


def page(name, base_path="", view="developer"):
    body = (Path(__file__).parent / "web" / name).read_text()
    script = (
        "<script>window.AGORA_BASE_PATH="
        + json.dumps(base_path)
        + ";window.agoraPath=(path)=>window.AGORA_BASE_PATH+path;</script>"
    )
    body = body.replace("<head>", "<head>" + script, 1)
    body = re.sub(
        r'(href|src)="/(?!/)', lambda match: match[1] + '="' + base_path + "/", body
    )
    return body.replace("__AGORA_VIEW__", view).encode()
