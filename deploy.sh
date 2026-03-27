#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/okx-quant-agent}"
REPO_URL="${REPO_URL:-https://github.com/hooper-lee/okx-quant-agent.git}"
BRANCH="${BRANCH:-main}"
PORT="${PORT:-8010}"

echo "[1/6] installing system packages..."
sudo apt-get update
sudo apt-get install -y git python3 python3-pip python3-venv

if [ ! -d "$APP_DIR/.git" ]; then
  echo "[2/6] cloning repository..."
  sudo mkdir -p "$APP_DIR"
  sudo chown -R "$USER":"$USER" "$APP_DIR"
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
else
  echo "[2/6] updating repository..."
  git -C "$APP_DIR" fetch origin
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" pull origin "$BRANCH"
fi

cd "$APP_DIR"

echo "[3/6] preparing virtualenv..."
python3 -m venv .venv
source .venv/bin/activate

echo "[4/6] installing python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f ".env" ]; then
  echo "[5/6] creating .env from example..."
  cp .env.example .env
  echo "Please edit $APP_DIR/.env before production use."
fi

echo "[6/6] starting service..."
pkill -f "uvicorn app.main:app" || true
nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$PORT" > app.log 2>&1 &

echo "Deployment complete."
echo "Open: http://$(curl -s ifconfig.me):$PORT/"
