#!/usr/bin/env bash
set -euo pipefail

echo "[1/8] Stop Docker Desktop integration inside this distro if present"
if command -v docker >/dev/null 2>&1; then
  docker context use default >/dev/null 2>&1 || true
fi

echo "[2/8] Remove any old docker packages"
sudo apt-get remove -y docker docker-engine docker.io containerd runc || true

echo "[3/8] Update apt index"
sudo apt-get update

echo "[4/8] Install native Docker Engine packages from Ubuntu repo"
sudo apt-get install -y docker.io docker-compose-v2

echo "[5/8] Enable and start docker service"
sudo systemctl enable --now docker

echo "[6/8] Add current user to docker group"
sudo usermod -aG docker "$USER"

echo "[7/8] Show service status"
sudo systemctl --no-pager --full status docker | sed -n '1,20p'

echo "[8/8] Done"
echo
echo "Close this terminal and open a new Ubuntu terminal, then run:"
echo "  docker version"
echo "  docker compose version"

