#!/bin/bash
# Quick setup script for platform domain configuration

set -e

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}=== Platform Domain Configuration Helper ===${NC}"
echo

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env from .env.example...${NC}"
    cp .env.example .env
fi

# Ask for domain
echo -e "${BLUE}What domain suffix does your network use?${NC}"
echo "Examples: .local, .lan, .home, .internal"
read -p "Enter domain (including the dot): " domain

# Update .env
echo -e "${YELLOW}Updating PLATFORM_DOMAIN in .env...${NC}"
sed -i "s/^PLATFORM_DOMAIN=.*/PLATFORM_DOMAIN=${domain}/" .env

# Make scripts executable
echo -e "${YELLOW}Making scripts executable...${NC}"
chmod +x scripts/*.sh
chmod +x setup.sh

# Process templates
echo -e "${YELLOW}Processing configuration templates...${NC}"
./scripts/process-templates.sh

echo
echo -e "${GREEN}✓ Configuration complete!${NC}"
echo -e "${BLUE}Your platform is now configured to use '${domain}' domains.${NC}"
echo
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Review and complete other settings in .env"
echo "2. Deploy services: ./scripts/deploy.sh <machine-name>"
echo
echo -e "${BLUE}Example machine names with your domain:${NC}"
echo "  - erebus${domain}"
echo "  - orpheus${domain}"
echo "  - hades${domain}"
echo "  - etc."
