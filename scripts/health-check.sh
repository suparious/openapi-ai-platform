#!/bin/bash
# Health check script for all services
# Usage: ./health-check.sh [machine-name]

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
REGISTRY_URL="${REGISTRY_URL:-http://hephaestus.local:8090}"
MACHINE_NAME="${1:-all}"

# Function to print colored output
print_color() {
    local color=$1
    shift
    echo -e "${color}$@${NC}"
}

# Function to check service health
check_service() {
    local service_name=$1
    local service_url=$2
    
    if curl -sf "$service_url" > /dev/null 2>&1; then
        print_color $GREEN "✓ $service_name is healthy"
        return 0
    else
        print_color $RED "✗ $service_name is unhealthy"
        return 1
    fi
}

# Function to check machine services
check_machine() {
    local machine=$1
    print_color $BLUE "\n=== Checking $machine ==="
    
    case $machine in
        erebus)
            check_service "PostgreSQL" "tcp://erebus.local:5432"
            check_service "Redis" "tcp://erebus.local:6379"
            check_service "Qdrant" "http://erebus.local:6333/health"
            ;;
        orpheus)
            check_service "Open-WebUI" "http://orpheus.local:3000/health"
            check_service "LiteLLM" "http://orpheus.local:4000/health/liveliness"
            check_service "Ollama" "http://orpheus.local:11434/api/tags"
            ;;
        hades)
            check_service "Ollama (AMD)" "http://hades.local:11434/api/tags"
            ;;
        kratos)
            check_service "Ollama" "http://kratos.local:11434/api/tags"
            check_service "Automatic1111" "http://kratos.local:7860/"
            ;;
        nyx)
            check_service "Ollama" "http://nyx.local:11434/api/tags"
            check_service "Text Generation WebUI" "http://nyx.local:7860/"
            check_service "Whisper API" "http://nyx.local:9000/healthcheck"
            ;;
        hephaestus)
            check_service "Traefik" "http://hephaestus.local:8080/ping"
            check_service "Service Registry" "http://hephaestus.local:8090/health"
            check_service "Uptime Kuma" "http://hephaestus.local:3001/"
            ;;
        moros)
            check_service "Prometheus" "http://moros.local:9090/-/healthy"
            check_service "Grafana" "http://moros.local:3001/api/health"
            check_service "Loki" "http://moros.local:3100/ready"
            check_service "Alertmanager" "http://moros.local:9093/-/healthy"
            ;;
        thanatos)
            check_service "PostgreSQL Replica" "tcp://thanatos.local:5432"
            check_service "Sequential Thinking" "http://thanatos.local:8021/health"
            check_service "Memory" "http://thanatos.local:8022/health"
            check_service "Context7" "http://thanatos.local:8023/health"
            check_service "Calculator" "http://thanatos.local:8024/health"
            ;;
        zelus)
            check_service "Neo4j" "http://zelus.local:7474"
            check_service "Brave Search" "http://zelus.local:8031/health"
            check_service "Weather" "http://zelus.local:8032/health"
            check_service "Graphiti" "http://zelus.local:8033/health"
            check_service "SQL" "http://zelus.local:8034/health"
            check_service "Model Registry" "http://zelus.local:8040/health"
            ;;
        local)
            check_service "Filesystem" "http://localhost:8001/health"
            check_service "Git" "http://localhost:8002/health"
            check_service "Time" "http://localhost:8004/health"
            check_service "Get User Info" "http://localhost:8005/health"
            check_service "Fetch" "http://localhost:8006/health"
            ;;
        *)
            print_color $RED "Unknown machine: $machine"
            return 1
            ;;
    esac
}

# Function to check all services via registry
check_all_via_registry() {
    print_color $BLUE "\n=== Checking all services via Service Registry ==="
    
    if ! command -v jq &> /dev/null; then
        print_color $YELLOW "jq is not installed. Installing..."
        sudo apt-get update && sudo apt-get install -y jq
    fi
    
    # Get all services from registry
    response=$(curl -sf "$REGISTRY_URL/services" 2>/dev/null)
    
    if [ $? -ne 0 ]; then
        print_color $RED "Failed to connect to service registry at $REGISTRY_URL"
        return 1
    fi
    
    # Parse and display services
    echo "$response" | jq -r '.services[] | "\(.name)|\(.host):\(.port)|\(.status)|\(.response_time)"' | while IFS='|' read -r name endpoint status response_time; do
        case $status in
            healthy)
                print_color $GREEN "✓ $name ($endpoint) - ${response_time}ms"
                ;;
            unhealthy)
                print_color $RED "✗ $name ($endpoint) - UNHEALTHY"
                ;;
            *)
                print_color $YELLOW "? $name ($endpoint) - UNKNOWN"
                ;;
        esac
    done
    
    # Summary
    total=$(echo "$response" | jq '.services | length')
    healthy=$(echo "$response" | jq '.services | map(select(.status == "healthy")) | length')
    unhealthy=$(echo "$response" | jq '.services | map(select(.status == "unhealthy")) | length')
    unknown=$(echo "$response" | jq '.services | map(select(.status == "unknown" or .status == null)) | length')
    
    echo
    print_color $BLUE "Summary: Total: $total, Healthy: $healthy, Unhealthy: $unhealthy, Unknown: $unknown"
}

# Main execution
main() {
    print_color $GREEN "=== Distributed AI Platform Health Check ==="
    print_color $BLUE "Checking services..."
    
    if [ "$MACHINE_NAME" = "all" ]; then
        # Check via service registry
        if check_all_via_registry; then
            print_color $GREEN "\n✓ Health check completed"
        else
            # Fallback to direct checks
            print_color $YELLOW "\nFalling back to direct health checks..."
            
            machines=("erebus" "orpheus" "hades" "kratos" "nyx" "hephaestus" "moros" "thanatos" "zelus")
            for machine in "${machines[@]}"; do
                check_machine "$machine"
            done
        fi
    else
        # Check specific machine
        check_machine "$MACHINE_NAME"
    fi
    
    print_color $GREEN "\n=== Health check completed ==="
}

# Run main function
main
