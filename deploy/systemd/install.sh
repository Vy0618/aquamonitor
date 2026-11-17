#!/usr/bin/env bash
# Instala os servicos; nao inicia processos nem altera o banco de dados.
set -euo pipefail

if [[ $# -eq 1 && "$1" == --camera ]]; then
    exec bash "$(dirname -- "${BASH_SOURCE[0]}")/install-camera.sh"
fi
if [[ $# -ne 0 ]]; then
    echo 'Uso: sudo bash deploy/systemd/install.sh [--camera]' >&2
    exit 2
fi
if [[ $EUID -ne 0 ]]; then
    echo 'Execute com sudo bash deploy/systemd/install.sh.' >&2
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
if [[ "$service_user" == root ]]; then
    echo "Execute por sudo a partir do usuario que deve executar a API." >&2
    exit 1
fi
if [[ ! -f /etc/aquamonitor/api.env && ! -f "$unit_dir/.env.api" ]]; then
    echo 'Crie deploy/systemd/.env.api a partir de .env.example e configure a conexao.' >&2
    exit 1
fi

install -d -m 0755 /etc/aquamonitor
# Reinstalar nao sobrescreve credenciais ja configuradas.
if [[ ! -f /etc/aquamonitor/api.env ]]; then
    install -o root -g root -m 0600 "$unit_dir/.env.api" /etc/aquamonitor/api.env
fi
# Renderiza usuario e caminho da instalacao sem modificar os arquivos do clone.
render_dir="$(mktemp -d)"
trap 'rm -rf -- "$render_dir"' EXIT
"$project_dir/.venv/bin/python" - "$unit_dir" "$render_dir" "$project_dir" "$service_user" <<'PYRENDER'
from pathlib import Path
import sys
source, destination, project, user = sys.argv[1:]
for name in ("aquamonitor-api.service", "aquamonitor-dashboard.service",
             "aquamonitor.target", "aquamonitor-backend.target"):
    text = (Path(source) / name).read_text()
    text = text.replace("/home/projetos-maker/aquamonitor", project.replace("%", "%%"))
    text = text.replace("User=projetos-maker", f"User={user}")
    (Path(destination) / name).write_text(text)
PYRENDER
for unit in aquamonitor-api.service aquamonitor-dashboard.service aquamonitor.target aquamonitor-backend.target; do
    install -o root -g root -m 0644 "$render_dir/$unit" "/etc/systemd/system/$unit"
done
systemctl daemon-reload
printf '%s\n' 'Backend e banco: sudo systemctl start aquamonitor-backend.target'
printf '%s\n' 'Servicos instalados. Inicie com: sudo systemctl start aquamonitor.target'
printf '%s\n' 'Para iniciar tambem no boot: sudo systemctl enable --now aquamonitor.target'
