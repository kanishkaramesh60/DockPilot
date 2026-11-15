#!/usr/bin/env bash
# ==============================================================================
# DockPilot - Ubuntu Linux VM Provisioning Script
# ==============================================================================
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

echo "============================================================"
echo " Starting DockPilot Linux VM Provisioning..."
echo "============================================================"

# 1. Update package lists and install base dependencies
echo "[1/7] Installing base system dependencies..."
apt-get update -y
apt-get install -y --no-install-recommends \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    software-properties-common \
    python3 \
    python3-pip \
    python3-venv \
    net-tools

# 2. Set up official Docker repository and install Docker
echo "[2/7] Setting up official Docker repository..."
install -m 0755 -d /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
fi

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
    > /etc/apt/sources.list.d/docker.list

apt-get update -y
apt-get install -y --no-install-recommends \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin

# 3. Configure Docker permissions
echo "[3/7] Configuring Docker permissions..."
systemctl enable --now docker
usermod -aG docker vagrant

# 4. Set up Python virtual environment for DockPilot
echo "[4/7] Setting up Python virtual environment..."
VENV_DIR="/home/vagrant/dockpilot_venv"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
chown -R vagrant:vagrant "$VENV_DIR"

"$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel
if [ -f "/vagrant/requirements.txt" ]; then
    "$VENV_DIR/bin/pip" install -r /vagrant/requirements.txt
elif [ -f "/vagrant/manager/requirements.txt" ]; then
    "$VENV_DIR/bin/pip" install -r /vagrant/manager/requirements.txt
fi

# Ensure data and logs directories exist
mkdir -p /vagrant/data /vagrant/reports /vagrant/logs
chown -R vagrant:vagrant /vagrant/data /vagrant/reports /vagrant/logs || true

# 5. Set up systemd service for DockPilot Backend
echo "[5/7] Creating DockPilot systemd service..."
cat << 'EOF' > /etc/systemd/system/dockpilot.service
[Unit]
Description=DockPilot Container Management Dashboard
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=vagrant
Group=vagrant
WorkingDirectory=/vagrant
Environment="PATH=/home/vagrant/dockpilot_venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
ExecStart=/home/vagrant/dockpilot_venv/bin/python3 -m uvicorn main:app --app-dir manager --host 0.0.0.0 --port 8001
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now dockpilot.service

# 6. Launch monitoring stack via Docker Compose
echo "[6/7] Starting monitoring stack..."
if [ -f "/vagrant/monitoring-compose.yaml" ]; then
    docker compose -f /vagrant/monitoring-compose.yaml up -d
fi

# 7. Verification and status display
echo "[7/7] Verifying DockPilot VM services..."
sleep 5
echo "--- Docker Containers ---"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" || true

echo "--- DockPilot Service Status ---"
systemctl status dockpilot.service --no-pager || true

echo "============================================================"
echo " DockPilot Linux VM Provisioning Complete!"
echo " Web Dashboard:   http://localhost:8001"
echo " Grafana:         http://localhost:3000 (admin/admin)"
echo " Prometheus:      http://localhost:9090"
echo " Alertmanager:    http://localhost:9093"
echo " cAdvisor:        http://localhost:8085"
echo "============================================================"
