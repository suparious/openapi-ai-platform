#!/bin/bash
# Generate secrets for the AI platform

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SECRETS_DIR="${SCRIPT_DIR}/../secrets"

echo -e "${GREEN}=== Generating Secrets for AI Platform ===${NC}"

# Create secrets directory if it doesn't exist
mkdir -p "$SECRETS_DIR"

# Function to generate a secure password
generate_password() {
    openssl rand -base64 32 | tr -d '\n'
}

# Function to create a secret file
create_secret() {
    local filename="$1"
    local value="$2"
    local filepath="${SECRETS_DIR}/${filename}"
    
    if [ -f "$filepath" ]; then
        echo -e "${YELLOW}Warning: ${filename} already exists. Skipping...${NC}"
    else
        echo "$value" > "$filepath"
        chmod 600 "$filepath"
        echo -e "${GREEN}Created: ${filename}${NC}"
    fi
}

# Generate database passwords
create_secret "db_password.txt" "$(generate_password)"
create_secret "redis_password.txt" "$(generate_password)"
create_secret "admin_password.txt" "$(generate_password)"

# PostgreSQL replication password
create_secret "postgres_replication_password.txt" "$(generate_password)"

# Service registry API key
create_secret "service_registry_api_key.txt" "$(generate_password)"

# Monitoring passwords
create_secret "grafana_admin_password.txt" "$(generate_password)"

# LiteLLM master key
create_secret "litellm_master_key.txt" "$(generate_password)"

# OpenWebUI secret key
create_secret "openwebui_secret_key.txt" "$(generate_password)"

# Qdrant API key
create_secret "qdrant_api_key.txt" "$(generate_password)"

# Traefik dashboard password (bcrypt hash)
TRAEFIK_PASSWORD=$(generate_password | head -c 16)
TRAEFIK_HASH=$(docker run --rm httpd:2.4-alpine htpasswd -nbB admin "$TRAEFIK_PASSWORD" | cut -d ":" -f 2)
echo "admin:$TRAEFIK_HASH" > "${SECRETS_DIR}/traefik_users.txt"
echo "$TRAEFIK_PASSWORD" > "${SECRETS_DIR}/traefik_password.txt"
chmod 600 "${SECRETS_DIR}/traefik_users.txt"
chmod 600 "${SECRETS_DIR}/traefik_password.txt"
echo -e "${GREEN}Created: traefik_users.txt and traefik_password.txt${NC}"

# Portainer agent secret
create_secret "portainer_agent_secret.txt" "$(generate_password)"

# Create placeholder files for external API keys
touch "${SECRETS_DIR}/openai_api_key.txt"
touch "${SECRETS_DIR}/anthropic_api_key.txt"
touch "${SECRETS_DIR}/google_api_key.txt"
touch "${SECRETS_DIR}/groq_api_key.txt"
touch "${SECRETS_DIR}/together_api_key.txt"
touch "${SECRETS_DIR}/brave_api_key.txt"
touch "${SECRETS_DIR}/openweather_api_key.txt"
touch "${SECRETS_DIR}/context7_api_key.txt"
chmod 600 "${SECRETS_DIR}"/*_api_key.txt

echo -e "${YELLOW}Note: External API key files created but empty. Add your keys if needed.${NC}"

# Create a secure JWT secret
create_secret "jwt_secret.txt" "$(openssl rand -hex 64)"

# Summary
echo
echo -e "${GREEN}=== Secrets Generation Complete ===${NC}"
echo "Generated secrets in: ${SECRETS_DIR}"
echo
echo -e "${YELLOW}Important:${NC}"
echo "1. Keep these secrets secure and never commit them to git"
echo "2. Add your external API keys to the respective files if needed"
echo "3. The Traefik admin password is in traefik_password.txt"
echo "4. Back up these secrets to a secure location"
echo
echo -e "${GREEN}Next steps:${NC}"
echo "1. Review and update .env file with any custom values"
echo "2. Deploy services using ./deploy.sh <machine-name>"
