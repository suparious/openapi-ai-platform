#!/bin/bash
# Process configuration templates with environment variables
# This script replaces ${PLATFORM_DOMAIN} placeholders in template files

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default domain if not set
PLATFORM_DOMAIN=${PLATFORM_DOMAIN:-.local}

# Function to print colored output
print_color() {
    local color=$1
    shift
    echo -e "${color}$@${NC}"
}

# Function to process a template file
process_template() {
    local template_file=$1
    local output_file=$2
    
    if [ ! -f "$template_file" ]; then
        print_color $RED "Template file not found: $template_file"
        return 1
    fi
    
    print_color $BLUE "Processing template: $template_file"
    print_color $YELLOW "  Platform domain: ${PLATFORM_DOMAIN}"
    
    # Create backup of existing file if it exists
    if [ -f "$output_file" ]; then
        cp "$output_file" "${output_file}.bak"
        print_color $YELLOW "  Backed up existing file to ${output_file}.bak"
    fi
    
    # Process the template
    # Replace ${PLATFORM_DOMAIN} with actual value
    sed "s/\${PLATFORM_DOMAIN}/${PLATFORM_DOMAIN}/g" "$template_file" > "$output_file"
    
    print_color $GREEN "  Generated: $output_file"
}

# Main processing
main() {
    print_color $GREEN "=== Configuration Template Processor ==="
    
    # Load environment file if it exists
    if [ -f "${PROJECT_ROOT}/.env" ]; then
        print_color $BLUE "Loading environment from ${PROJECT_ROOT}/.env"
        set -a
        source "${PROJECT_ROOT}/.env"
        set +a
    fi
    
    print_color $BLUE "Using platform domain: ${PLATFORM_DOMAIN}"
    echo
    
    # Process LiteLLM config
    process_template \
        "${PROJECT_ROOT}/configs/litellm_config.yaml.template" \
        "${PROJECT_ROOT}/configs/litellm_config.yaml"
    
    # Process Traefik routes
    process_template \
        "${PROJECT_ROOT}/configs/traefik/dynamic/routes.yml.template" \
        "${PROJECT_ROOT}/configs/traefik/dynamic/routes.yml"
    
    echo
    print_color $GREEN "=== Template processing completed ==="
    print_color $YELLOW "Note: If you change PLATFORM_DOMAIN, run this script again to update configs"
}

# Check if running directly
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi
