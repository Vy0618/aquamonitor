#!/usr/bin/env bash
# Instala somente o monitor da camera; nao inicia nem habilita o servico.
set -euo pipefail
if [[ $# -ne 0 || $EUID -ne 0 ]]; then
    echo 'Uso: sudo bash deploy/systemd/install.sh --camera' >&2
    exit 1
fi
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
service_user="${SUDO_USER:-$(stat -c %U "$project_dir")}"
unit_dir="$project_dir/deploy/systemd"
if [[ ! -x "$project_dir/.venv/bin/python" ]]; then
    echo "Ambiente Python ausente em $project_dir/.venv." >&2
    exit 1
fi
getent passwd "$service_user" >/dev/null
getent group video >/dev/null
if [[ "$service_user" == root ]]; then
    echo 'Execute por sudo a partir do usuario que deve executar a camera.' >&2
    exit 1
fi
if [[ ! -f /etc/aquamonitor/camera.env && ! -f "$unit_dir/.env.camera" ]]; then
    echo 'Copie camera.env.example para deploy/systemd/.env.camera e configure IP, estacao e detector.' >&2
    exit 1
fi
render_dir="$(mktemp -d)"
trap 'rm -rf -- "$render_dir"' EXIT
"$project_dir/.venv/bin/python" - "$unit_dir" "$render_dir" "$project_dir" "$service_user" <<'PYRENDER'
from pathlib import Path
import sys
source, destination, project, user = sys.argv[1:]
text = (Path(source) / 'aquamonitor-camera.service').read_text()
text = text.replace('/home/projetos-maker/aquamonitor', project.replace('%', '%%'))
text = text.replace('User=projetos-maker', f'User={user}')
(Path(destination) / 'aquamonitor-camera.service').write_text(text)
PYRENDER
install -d -m 0755 /etc/aquamonitor
if [[ ! -f /etc/aquamonitor/camera.env ]]; then
    install -o root -g root -m 0600 "$unit_dir/.env.camera" /etc/aquamonitor/camera.env
fi
install -o root -g root -m 0644 "$render_dir/aquamonitor-camera.service" /etc/systemd/system/aquamonitor-camera.service
systemctl daemon-reload
printf '%s\n' 'Camera instalada. Inicie com: sudo systemctl start aquamonitor-camera.service'
printf '%s\n' 'Para iniciar no boot: sudo systemctl enable --now aquamonitor-camera.service'
