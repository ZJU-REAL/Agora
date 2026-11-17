#!/usr/bin/env bash
set -euo pipefail
AGORA_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ "$AGORA_REPO" != /data/project/Agora ]]; then
    echo "This deployment targets /data/project/Agora on the IAP workspace." >&2
    exit 1
fi
sudo -n install -m 0644 "$AGORA_REPO/deploy/iap/agora.service" /etc/systemd/system/agora.service
sudo -n python3 - <<'PY'
from pathlib import Path
from datetime import datetime
import subprocess
path = Path('/etc/nginx/conf.d/frontier-vlm-compare.conf')
body = path.read_text()
include = '    include /data/project/Agora/deploy/iap/agora.location.conf;\n'
if include.strip() not in body:
    anchor = '    location / {\n'
    if body.count(anchor) != 1:
        raise RuntimeError('Cannot identify the existing IAP server; configuration was not changed')
    backup = Path('/tmp/agora-nginx-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.conf')
    backup.write_text(body)
    path.write_text(body.replace(anchor, include + '\n' + anchor, 1))
    try:
        subprocess.run(['nginx', '-t'], check=True)
    except subprocess.CalledProcessError:
        path.write_text(body)
        raise
    print('Nginx backup:', backup)
PY
sudo -n nginx -t
sudo -n systemctl daemon-reload
sudo -n systemctl enable --now agora.service
sudo -n systemctl reload nginx
sudo -n systemctl --no-pager --full status agora.service
