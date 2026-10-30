#!/usr/bin/env bash
# Instala os servicos; nao inicia processos nem altera o banco de dados.
set -euo pipefail

if [[ $# -ne 0 ]]; then
    echo 'Uso: sudo bash deploy/systemd/install.sh' >&2
    exit 2
fi
if [[ $EUID -ne 0 ]]; then
    echo 'Execute com sudo bash deploy/systemd/install.sh.' >&2
    exit 1
fi

project_dir=/home/vyzxc/aquamonitor
unit_dir="$project_dir/deploy/systemd"
if [[ ! -x "$project_dir/.venv/bin/python" ]]; then
    echo "Ambiente Python ausente em $project_dir/.venv." >&2
    exit 1
fi
getent passwd vyzxc >/dev/null
if [[ ! -f /etc/aquamonitor/api.env && ! -f "$unit_dir/.env.api" ]]; then
    echo 'Crie deploy/systemd/.env.api a partir de .env.example e configure a conexao.' >&2
    exit 1
fi

install -d -m 0755 /etc/aquamonitor
# Reinstalar nao sobrescreve credenciais ja configuradas.
if [[ ! -f /etc/aquamonitor/api.env ]]; then
    install -o root -g root -m 0600 "$unit_dir/.env.api" /etc/aquamonitor/api.env
fi
for unit in aquamonitor-api.service aquamonitor-dashboard.service aquamonitor.target; do
    install -o root -g root -m 0644 "$unit_dir/$unit" "/etc/systemd/system/$unit"
done
systemctl daemon-reload
printf '%s\n' 'Servicos instalados. Inicie com: sudo systemctl start aquamonitor.target'
printf '%s\n' 'Para iniciar tambem no boot: sudo systemctl enable --now aquamonitor.target'
