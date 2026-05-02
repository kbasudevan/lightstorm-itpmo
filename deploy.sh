#!/bin/bash
# ─────────────────────────────────────────────────────────────────
# ITPMO — Deploy to EC2
# Usage:  ./deploy.sh  ec2-user@<EC2-PUBLIC-IP>  [/path/to/key.pem]
#
# Example:
#   ./deploy.sh ec2-user@54.123.45.67 ~/.ssh/lightstorm-key.pem
# ─────────────────────────────────────────────────────────────────
set -e

REMOTE="${1:?Usage: $0 user@host [/path/to/key.pem]}"
KEY="${2}"
REMOTE_DIR="/opt/itpmo"

SSH_OPTS="-o StrictHostKeyChecking=no"
[[ -n "$KEY" ]] && SSH_OPTS="$SSH_OPTS -i $KEY"

echo "▶  Deploying ITPMO to $REMOTE ..."

# 1 — Install Docker + Compose on EC2 (idempotent, safe to re-run)
echo "▶  Ensuring Docker is installed on remote..."
ssh $SSH_OPTS "$REMOTE" bash << 'REMOTE_SETUP'
  set -e
  if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    echo "[setup] Docker installed."
  else
    echo "[setup] Docker already installed: $(docker --version)"
  fi
  if ! docker compose version &>/dev/null 2>&1; then
    sudo apt-get install -y docker-compose-plugin 2>/dev/null || \
    sudo yum install -y docker-compose-plugin 2>/dev/null || true
  fi
  sudo systemctl enable --now docker
REMOTE_SETUP

# 2 — Upload project files (exclude local-only artefacts)
echo "▶  Uploading project files..."
rsync -az --progress $SSH_OPTS \
  --exclude='.git' \
  --exclude='venv/' \
  --exclude='instance/' \
  --exclude='static/uploads/' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  ./ "$REMOTE:$REMOTE_DIR/"

# 3 — Ensure .env exists on server (won't overwrite if already there)
echo "▶  Checking .env on remote..."
ssh $SSH_OPTS "$REMOTE" bash << REMOTE_ENV
  set -e
  if [ ! -f "$REMOTE_DIR/.env" ]; then
    cp "$REMOTE_DIR/.env" "$REMOTE_DIR/.env" 2>/dev/null || true
    # Generate a real SECRET_KEY
    SK=\$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)
    cat > "$REMOTE_DIR/.env" << EOF
SECRET_KEY=\$SK
HOST_PORT=80
WEB_CONCURRENCY=2
EOF
    echo "[env] .env created with generated SECRET_KEY."
  else
    echo "[env] .env already exists — not overwritten."
  fi
REMOTE_ENV

# 4 — Build image and (re)start container
echo "▶  Building image and starting container..."
ssh $SSH_OPTS "$REMOTE" bash << REMOTE_RUN
  set -e
  cd "$REMOTE_DIR"
  docker compose pull --ignore-pull-failures 2>/dev/null || true
  docker compose build --no-cache
  docker compose up -d --remove-orphans
  echo ""
  docker compose ps
  echo ""
  echo "✅  ITPMO is live — http://\$(curl -sf http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo '<EC2-IP>')"
REMOTE_RUN

echo ""
echo "✅  Deployment complete."
