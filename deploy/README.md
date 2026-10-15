# Oracle Cloud Deployment Guide

## One-command deployment (run on Oracle VM):

```bash
curl -fsSL https://raw.githubusercontent.com/VishalRauto/flood-risk-ai/main/h2oai-flood-intelligence-agent-main/deploy/oracle-setup.sh | bash
```

## After deployment, your app is live at:
```
http://YOUR-ORACLE-IP:8000           → Main Dashboard
http://YOUR-ORACLE-IP:8000/luxury    → Luxury 3D
http://YOUR-ORACLE-IP:8000/public    → Public Portal
http://YOUR-ORACLE-IP:8000/register  → Register
http://YOUR-ORACLE-IP:8000/login     → Login
```

## Update the app after code changes:
```bash
cd /home/ubuntu/flood-risk-ai/h2oai-flood-intelligence-agent-main
git pull origin main
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```
