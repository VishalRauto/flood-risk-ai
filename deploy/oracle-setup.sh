#!/bin/bash
# =============================================================================
# Oracle Cloud Always Free — India Flood Intelligence System
# Full server setup + deployment script
# Run as: bash oracle-setup.sh
# =============================================================================

set -e
echo "🌊 India Flood Intelligence — Oracle Cloud Deployment"
echo "======================================================"

# ── 1. System update ──────────────────────────────────────────────────────────
echo "📦 Updating system packages..."
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install -y curl git wget unzip ca-certificates gnupg lsb-release

# ── 2. Install Docker ─────────────────────────────────────────────────────────
echo "🐳 Installing Docker..."
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add ubuntu user to docker group (no sudo needed)
sudo usermod -aG docker ubuntu
echo "✅ Docker installed"

# ── 3. Start Docker ───────────────────────────────────────────────────────────
sudo systemctl enable docker
sudo systemctl start docker

# ── 4. Clone the project ──────────────────────────────────────────────────────
echo "📥 Cloning flood-risk-ai from GitHub..."
cd /home/ubuntu
if [ -d "flood-risk-ai" ]; then
  cd flood-risk-ai && git pull origin main
else
  git clone https://github.com/VishalRauto/flood-risk-ai.git
  cd flood-risk-ai
fi

# Navigate to the actual project directory
cd h2oai-flood-intelligence-agent-main

# ── 5. Create .env from template ──────────────────────────────────────────────
echo "⚙️  Setting up environment..."
if [ ! -f "core/.env" ]; then
  cp core/.env.example core/.env
  echo "⚠️  Created core/.env from template — edit API keys later"
fi

# ── 6. Create docker-compose for production ───────────────────────────────────
echo "📝 Writing production docker-compose..."
cat > docker-compose.prod.yml << 'EOF'
version: "3.9"

services:
  redis:
    image: redis:7-alpine
    container_name: flood-redis
    restart: always
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  web:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: flood-web
    restart: always
    ports:
      - "8000:8000"
    environment:
      - REDIS_ENABLED=true
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_URL=redis://redis:6379
      - APP_REDIS_URL=redis://redis:6379
      - PORT=8000
    env_file:
      - core/.env
    depends_on:
      redis:
        condition: service_healthy
    volumes:
      - app_data:/app/data

volumes:
  redis_data:
  app_data:
EOF

# ── 7. Build and start ────────────────────────────────────────────────────────
echo "🔨 Building Docker image (this takes 10-15 minutes first time)..."
sudo docker compose -f docker-compose.prod.yml build

echo "🚀 Starting all services..."
sudo docker compose -f docker-compose.prod.yml up -d

# ── 8. Open firewall ──────────────────────────────────────────────────────────
echo "🔓 Configuring firewall..."
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT

# Save iptables rules
sudo apt-get install -y iptables-persistent
sudo netfilter-persistent save

# ── 9. Setup auto-start on reboot ─────────────────────────────────────────────
echo "⚡ Setting up auto-start service..."
cat > /tmp/flood-ai.service << 'SVCEOF'
[Unit]
Description=India Flood Intelligence System
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/ubuntu/flood-risk-ai/h2oai-flood-intelligence-agent-main
ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
SVCEOF

sudo mv /tmp/flood-ai.service /etc/systemd/system/flood-ai.service
sudo systemctl daemon-reload
sudo systemctl enable flood-ai.service

# ── 10. Health check ──────────────────────────────────────────────────────────
echo ""
echo "⏳ Waiting for server to start (30s)..."
sleep 30

STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000 || echo "000")
if [ "$STATUS" = "200" ]; then
  echo ""
  echo "✅ ============================================="
  echo "✅  DEPLOYMENT SUCCESSFUL!"
  echo "✅ ============================================="
  echo ""
  echo "🌊 Your app is live at:"
  echo "   http://$(curl -s ifconfig.me):8000"
  echo ""
  echo "📄 All routes:"
  echo "   http://$(curl -s ifconfig.me):8000           — Main Dashboard"
  echo "   http://$(curl -s ifconfig.me):8000/luxury    — Luxury 3D"
  echo "   http://$(curl -s ifconfig.me):8000/public    — Public Portal"
  echo "   http://$(curl -s ifconfig.me):8000/register  — Register"
  echo "   http://$(curl -s ifconfig.me):8000/login     — Login"
  echo ""
else
  echo "⚠️  Server returned status $STATUS — check logs:"
  echo "   docker compose -f docker-compose.prod.yml logs --tail 30"
fi
