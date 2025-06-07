#!/bin/bash
# Quick setup script for Distributed AI Platform
# Run this after configuring .env file

set -e

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Distributed AI Platform Setup ===${NC}"

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file from template...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}Please edit .env file with your configuration and run this script again${NC}"
    exit 1
fi

# Source environment
source .env

# Create necessary directories
echo -e "${BLUE}Creating data directories...${NC}"
sudo mkdir -p ${DATA_DIR}/{postgres,redis,qdrant,postgres-backups,qdrant-snapshots}
sudo mkdir -p ${DATA_DIR}/{open-webui,litellm,ollama-orpheus,ollama-kratos,ollama-nyx,ollama-hades}
sudo mkdir -p ${DATA_DIR}/{uptime-kuma,prometheus,grafana,loki,alertmanager}
sudo mkdir -p ${DATA_DIR}/{postgres-replica,memory,context7-cache,neo4j/data,graphiti}
sudo mkdir -p ${DATA_DIR}/{stable-diffusion,comfyui,text-generation-webui,whisper-models,embeddings-cache}
sudo mkdir -p ${LOGS_DIR}/{traefik,neo4j}
sudo mkdir -p ${TEMP_DIR}
sudo mkdir -p /opt/ai-platform/secrets

# Set permissions
sudo chown -R $USER:$USER ${DATA_DIR} ${LOGS_DIR} ${TEMP_DIR}

# Create secrets directory
echo -e "${BLUE}Setting up secrets...${NC}"
touch secrets/{db_password.txt,redis_password.txt,admin_password.txt,openai_api_key.txt,anthropic_api_key.txt}
chmod 600 secrets/*.txt

# Make scripts executable
echo -e "${BLUE}Making scripts executable...${NC}"
chmod +x scripts/*.sh
chmod +x make-executable.sh

# Create Docker networks
echo -e "${BLUE}Creating Docker networks...${NC}"
docker network create --driver overlay --attachable --subnet=10.10.0.0/16 ai-network 2>/dev/null || true
docker network create --driver overlay --attachable monitoring-network 2>/dev/null || true

# Generate secure passwords if not set
if grep -q "changeme" .env; then
    echo -e "${YELLOW}Generating secure passwords...${NC}"
    # This is a simple example - in production use stronger generation
    sed -i "s/changeme_postgres_password/$(openssl rand -base64 32 | tr -d '=')/g" .env
    sed -i "s/changeme_redis_password/$(openssl rand -base64 32 | tr -d '=')/g" .env
    sed -i "s/changeme_grafana_password/$(openssl rand -base64 32 | tr -d '=')/g" .env
    sed -i "s/changeme_openwebui_secret_key/$(openssl rand -base64 48 | tr -d '=')/g" .env
    sed -i "s/changeme_litellm_master_key/$(openssl rand -base64 32 | tr -d '=')/g" .env
    sed -i "s/changeme_qdrant_api_key/$(openssl rand -base64 32 | tr -d '=')/g" .env
    sed -i "s/changeme_jwt_secret_key/$(openssl rand -base64 48 | tr -d '=')/g" .env
fi

echo -e "${GREEN}✓ Setup completed!${NC}"
echo
echo -e "${BLUE}Next steps:${NC}"
echo "1. Edit .env file with your API keys and configuration"
echo "2. Ensure NFS mounts are configured and accessible"
echo "3. Run deployment on each machine:"
echo "   ./scripts/deploy.sh erebus"
echo "   ./scripts/deploy.sh hephaestus"
echo "   ./scripts/deploy.sh <machine-name>"
echo
echo -e "${YELLOW}Remember to deploy in the correct order as per DEPLOYMENT.md${NC}"
