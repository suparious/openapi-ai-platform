#!/bin/bash
# Update all docker-compose files to use PLATFORM_DOMAIN variable

set -e

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Function to update a docker-compose file
update_compose_file() {
    local file=$1
    echo "Updating $file..."
    
    # Replace .local with ${PLATFORM_DOMAIN:-.local} in hostname fields
    sed -i 's/hostname: \([a-zA-Z0-9-]*\)\.local/hostname: \1${PLATFORM_DOMAIN:-.local}/g' "$file"
    
    # Replace hardcoded .local in environment variables and URLs
    sed -i 's/http:\/\/\([a-zA-Z0-9-]*\)\.local/http:\/\/\1${PLATFORM_DOMAIN:-.local}/g' "$file"
    sed -i 's/https:\/\/\([a-zA-Z0-9-]*\)\.local/https:\/\/\1${PLATFORM_DOMAIN:-.local}/g' "$file"
    sed -i 's/WEBUI_URL: http:\/\/orpheus\.local/WEBUI_URL: http:\/\/orpheus${PLATFORM_DOMAIN:-.local}/g' "$file"
    sed -i 's/DATABASE_URL: postgresql:\/\/\${POSTGRES_USER}:\${POSTGRES_PASSWORD}@erebus\.local/DATABASE_URL: postgresql:\/\/\${POSTGRES_USER}:\${POSTGRES_PASSWORD}@\${POSTGRES_HOST}/g' "$file"
    sed -i 's/REDIS_URL: redis:\/\/default:\${REDIS_PASSWORD}@erebus\.local/REDIS_URL: redis:\/\/default:\${REDIS_PASSWORD}@\${REDIS_HOST}/g' "$file"
    sed -i 's/QDRANT_URL: http:\/\/erebus\.local/QDRANT_URL: http:\/\/\${POSTGRES_HOST}/g' "$file"
}

# Update all docker-compose files
cd "$PROJECT_ROOT"

for compose_file in docker-compose.*.yml; do
    if [ "$compose_file" != "docker-compose.local.yml" ]; then
        update_compose_file "$compose_file"
    fi
done

echo "All docker-compose files updated successfully!"
echo "Note: The docker-compose.local.yml file was not modified as it doesn't contain machine-specific hostnames."
