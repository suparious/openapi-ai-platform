#!/bin/bash
# Deployment script for Distributed AI Platform
# Usage: ./deploy.sh <machine-name> [options]

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
MACHINE_NAME=""
ACTION="deploy"
COMPOSE_FILE=""
ENV_FILE=".env"
FORCE=false
SKIP_PULL=false
SKIP_BUILD=false
VERBOSE=false

# Function to print colored output
print_color() {
    local color=$1
    shift
    echo -e "${color}$@${NC}"
}

# Function to print usage
usage() {
    cat << EOF
Usage: $0 <machine-name> [options]

Deploy services to a specific machine in the distributed AI platform.

Arguments:
    machine-name    Name of the machine (erebus, orpheus, hades, etc.)

Options:
    -a, --action    Action to perform (deploy|stop|restart|status|logs) [default: deploy]
    -e, --env       Environment file to use [default: .env]
    -f, --force     Force deployment even if services are running
    -s, --skip-pull Skip pulling latest images
    -b, --skip-build Skip building local images
    -v, --verbose   Enable verbose output
    -h, --help      Show this help message

Examples:
    $0 erebus                    # Deploy to erebus
    $0 orpheus --action restart  # Restart services on orpheus
    $0 hades --action logs       # View logs on hades
    $0 local --skip-pull         # Deploy local without pulling images

Supported machines:
    - erebus (Primary database)
    - thanatos (Secondary services)
    - zelus (Additional services)
    - orpheus (Primary GPU - Open-WebUI, LiteLLM)
    - kratos (NVIDIA GPU - Ollama)
    - nyx (NVIDIA GPU - Ollama)
    - hades (AMD GPU - Heavy Ollama)
    - hephaestus (Edge services - Traefik)
    - moros (Monitoring - Grafana)
    - local (Workstation - Local OpenAPI servers)
EOF
}

# Parse command line arguments
parse_args() {
    if [ $# -eq 0 ]; then
        usage
        exit 1
    fi

    MACHINE_NAME=$1
    shift

    while [[ $# -gt 0 ]]; do
        case $1 in
            -a|--action)
                ACTION="$2"
                shift 2
                ;;
            -e|--env)
                ENV_FILE="$2"
                shift 2
                ;;
            -f|--force)
                FORCE=true
                shift
                ;;
            -s|--skip-pull)
                SKIP_PULL=true
                shift
                ;;
            -b|--skip-build)
                SKIP_BUILD=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                print_color $RED "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
}

# Validate machine name
validate_machine() {
    local valid_machines=("erebus" "thanatos" "zelus" "orpheus" "kratos" "nyx" "hades" "hephaestus" "moros" "local")
    
    if [[ ! " ${valid_machines[@]} " =~ " ${MACHINE_NAME} " ]]; then
        print_color $RED "Error: Invalid machine name: ${MACHINE_NAME}"
        print_color $YELLOW "Valid machines: ${valid_machines[*]}"
        exit 1
    fi
    
    COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.${MACHINE_NAME}.yml"
    
    if [ ! -f "$COMPOSE_FILE" ]; then
        print_color $RED "Error: Compose file not found: $COMPOSE_FILE"
        exit 1
    fi
}

# Check prerequisites
check_prerequisites() {
    print_color $BLUE "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_color $RED "Error: Docker is not installed"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_color $RED "Error: Docker Compose is not installed"
        exit 1
    fi
    
    # Check environment file
    if [ ! -f "${PROJECT_ROOT}/${ENV_FILE}" ]; then
        print_color $RED "Error: Environment file not found: ${PROJECT_ROOT}/${ENV_FILE}"
        print_color $YELLOW "Please copy .env.example to .env and configure it"
        exit 1
    fi
    
    # Check if running as root (not recommended)
    if [ "$EUID" -eq 0 ]; then
        print_color $YELLOW "Warning: Running as root is not recommended"
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    print_color $GREEN "Prerequisites check passed"
}

# Create required directories
create_directories() {
    print_color $BLUE "Creating required directories..."
    
    # Load environment variables
    source "${PROJECT_ROOT}/${ENV_FILE}"
    
    # Create base directories
    local dirs=(
        "${DATA_DIR:-/opt/ai-platform/data}"
        "${LOGS_DIR:-/opt/ai-platform/logs}"
        "${TEMP_DIR:-/opt/ai-platform/tmp}"
    )
    
    # Machine-specific directories
    case $MACHINE_NAME in
        erebus)
            dirs+=(
                "${DATA_DIR}/postgres"
                "${DATA_DIR}/redis"
                "${DATA_DIR}/qdrant"
                "${DATA_DIR}/postgres-backups"
                "${DATA_DIR}/qdrant-snapshots"
            )
            ;;
        orpheus)
            dirs+=(
                "${DATA_DIR}/open-webui"
                "${DATA_DIR}/litellm"
                "${DATA_DIR}/ollama-orpheus"
                "${DATA_DIR}/pipelines"
            )
            ;;
        hades)
            dirs+=(
                "${DATA_DIR}/ollama-hades"
            )
            ;;
        hephaestus)
            dirs+=(
                "${DATA_DIR}/uptime-kuma"
                "${LOGS_DIR}/traefik"
            )
            ;;
        moros)
            dirs+=(
                "${DATA_DIR}/prometheus"
                "${DATA_DIR}/grafana"
                "${DATA_DIR}/loki"
            )
            ;;
        kratos|nyx)
            dirs+=(
                "${DATA_DIR}/ollama-${MACHINE_NAME}"
            )
            ;;
    esac
    
    # Create directories
    for dir in "${dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            print_color $YELLOW "Creating directory: $dir"
            sudo mkdir -p "$dir"
            sudo chown -R $USER:$USER "$dir"
        fi
    done
    
    print_color $GREEN "Directories created successfully"
}

# Setup Docker networks
setup_networks() {
    print_color $BLUE "Setting up Docker networks..."
    
    # Create networks if they don't exist
    if ! docker network inspect ai-network &> /dev/null; then
        print_color $YELLOW "Creating ai-network..."
        docker network create --driver overlay --attachable \
            --subnet=10.10.0.0/16 \
            --ip-range=10.10.1.0/24 \
            ai-network
    fi
    
    if ! docker network inspect monitoring-network &> /dev/null; then
        print_color $YELLOW "Creating monitoring-network..."
        docker network create --driver overlay --attachable \
            monitoring-network
    fi
    
    print_color $GREEN "Networks setup completed"
}

# Pull latest images
pull_images() {
    if [ "$SKIP_PULL" = true ]; then
        print_color $YELLOW "Skipping image pull (--skip-pull specified)"
        return
    fi
    
    print_color $BLUE "Pulling latest images..."
    
    cd "$PROJECT_ROOT"
    docker-compose -f "$COMPOSE_FILE" --env-file "${ENV_FILE}" pull
    
    print_color $GREEN "Images pulled successfully"
}

# Build local images
build_images() {
    if [ "$SKIP_BUILD" = true ]; then
        print_color $YELLOW "Skipping image build (--skip-build specified)"
        return
    fi
    
    print_color $BLUE "Building local images if needed..."
    
    cd "$PROJECT_ROOT"
    
    # Check if there are any build contexts in the compose file
    if grep -q "build:" "$COMPOSE_FILE"; then
        docker-compose -f "$COMPOSE_FILE" --env-file "${ENV_FILE}" build
        print_color $GREEN "Images built successfully"
    else
        print_color $YELLOW "No images to build for ${MACHINE_NAME}"
    fi
}

# Process configuration templates
process_config_templates() {
    print_color $BLUE "Processing configuration templates..."
    
    if [ -x "${SCRIPT_DIR}/process-templates.sh" ]; then
        "${SCRIPT_DIR}/process-templates.sh"
    else
        print_color $YELLOW "Warning: Template processor not found or not executable"
    fi
}

# Deploy services
deploy_services() {
    print_color $BLUE "Deploying services to ${MACHINE_NAME}..."
    
    cd "$PROJECT_ROOT"
    
    # Check if services are already running
    if docker-compose -f "$COMPOSE_FILE" --env-file "${ENV_FILE}" ps -q | grep -q .; then
        if [ "$FORCE" = false ]; then
            print_color $YELLOW "Services are already running on ${MACHINE_NAME}"
            read -p "Stop and redeploy? (y/N) " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                print_color $YELLOW "Deployment cancelled"
                exit 0
            fi
        fi
        
        print_color $YELLOW "Stopping existing services..."
        docker-compose -f "$COMPOSE_FILE" --env-file "${ENV_FILE}" down
    fi
    
    # Start services
    print_color $YELLOW "Starting services..."
    if [ "$VERBOSE" = true ]; then
        docker-compose -f "$COMPOSE_FILE" --env-file "${ENV_FILE}" up -d
    else
        docker-compose -f "$COMPOSE_FILE" --env-file "${ENV_FILE}" up -d --quiet-pull
    fi
    
    print_color $GREEN "Services deployed successfully"
}

# Stop services
stop_services() {
    print_color $BLUE "Stopping services on ${MACHINE_NAME}..."
    
    cd "$PROJECT_ROOT"
    docker-compose -f "$COMPOSE_FILE" --env-file "${ENV_FILE}" down
    
    print_color $GREEN "Services stopped successfully"
}

# Restart services
restart_services() {
    print_color $BLUE "Restarting services on ${MACHINE_NAME}..."
    
    cd "$PROJECT_ROOT"
    docker-compose -f "$COMPOSE_FILE" --env-file "${ENV_FILE}" restart
    
    print_color $GREEN "Services restarted successfully"
}

# Show service status
show_status() {
    print_color $BLUE "Service status for ${MACHINE_NAME}:"
    
    cd "$PROJECT_ROOT"
    docker-compose -f "$COMPOSE_FILE" --env-file "${ENV_FILE}" ps
}

# Show service logs
show_logs() {
    print_color $BLUE "Showing logs for ${MACHINE_NAME}:"
    
    cd "$PROJECT_ROOT"
    docker-compose -f "$COMPOSE_FILE" --env-file "${ENV_FILE}" logs -f --tail=100
}

# Post-deployment checks
post_deployment_checks() {
    print_color $BLUE "Running post-deployment checks..."
    
    # Wait for services to start
    sleep 10
    
    # Check service health
    cd "$PROJECT_ROOT"
    local unhealthy=$(docker-compose -f "$COMPOSE_FILE" --env-file "${ENV_FILE}" ps | grep -E "(unhealthy|starting)" || true)
    
    if [ -n "$unhealthy" ]; then
        print_color $YELLOW "Warning: Some services may not be healthy yet:"
        echo "$unhealthy"
        print_color $YELLOW "Run '$0 ${MACHINE_NAME} --action status' to check again"
    else
        print_color $GREEN "All services appear to be running"
    fi
    
    # Machine-specific checks
    case $MACHINE_NAME in
        erebus)
            print_color $YELLOW "Database services deployed. Remember to:"
            echo "  - Initialize databases if this is first deployment"
            echo "  - Configure replication if using secondary database"
            ;;
        orpheus)
            print_color $YELLOW "Open-WebUI available at: http://orpheus${PLATFORM_DOMAIN:-.local}:3000"
            print_color $YELLOW "LiteLLM API available at: http://orpheus${PLATFORM_DOMAIN:-.local}:4000"
            ;;
        hephaestus)
            print_color $YELLOW "Traefik dashboard available at: http://traefik.${DOMAIN:-ai.local}"
            print_color $YELLOW "Uptime Kuma available at: http://uptime.${DOMAIN:-ai.local}"
            ;;
        moros)
            print_color $YELLOW "Grafana available at: http://moros${PLATFORM_DOMAIN:-.local}:3001"
            print_color $YELLOW "Prometheus available at: http://moros${PLATFORM_DOMAIN:-.local}:9090"
            ;;
    esac
}

# Main execution
main() {
    parse_args "$@"
    
    print_color $GREEN "=== Distributed AI Platform Deployment ==="
    print_color $BLUE "Machine: ${MACHINE_NAME}"
    print_color $BLUE "Action: ${ACTION}"
    echo
    
    validate_machine
    check_prerequisites
    
    case $ACTION in
        deploy)
            create_directories
            setup_networks
            process_config_templates
            pull_images
            build_images
            deploy_services
            post_deployment_checks
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs
            ;;
        *)
            print_color $RED "Unknown action: $ACTION"
            usage
            exit 1
            ;;
    esac
    
    print_color $GREEN "=== Deployment script completed ==="
}

# Run main function
main "$@"
