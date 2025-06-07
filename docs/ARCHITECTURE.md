# Architecture Guide - Distributed AI Platform

## Overview

This distributed AI platform combines multiple open-source technologies to create a comprehensive, scalable AI infrastructure across 10 machines in a home lab environment. The architecture prioritizes data sovereignty, cost efficiency, and flexibility while maintaining enterprise-grade reliability.

## Core Design Principles

1. **No Single Point of Failure**: Critical services are replicated or have fallback mechanisms
2. **Data Locality**: Models stored centrally on NAS, compute happens where the GPUs are
3. **Service Mesh Without Complexity**: Simple DNS-based discovery via OPNsense
4. **Open Source First**: No proprietary dependencies or licensing concerns
5. **Observability Built-In**: Comprehensive monitoring from day one

## Infrastructure Layout

### Network Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OPNsense Router (Prometheus)              │
│                         DNS + DHCP + Firewall                │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │   TrueNAS Scale (Poseidon) │
        │   • /models (AI Models)    │
        │   • /shared (Shared Data)  │
        └─────────────┬─────────────┘
                      │
    ┌─────────────────┼─────────────────┐
    │                 │                 │
┌───┴───┐      ┌──────┴──────┐   ┌─────┴─────┐
│ CPU   │      │   GPU       │   │   Small   │
│ Nodes │      │   Nodes     │   │   Nodes   │
└───────┘      └─────────────┘   └───────────┘
```

### Machine Roles

#### Data Tier (CPU Nodes)
- **Erebus** (Primary): PostgreSQL, Redis, Qdrant
- **Thanatos** (Secondary): PostgreSQL replica, CPU-based OpenAPI servers
- **Zelus** (Services): Neo4j, additional OpenAPI servers, model registry

#### Compute Tier (GPU Nodes)
- **Orpheus** (NVIDIA): Open-WebUI, LiteLLM, Ollama
- **Kratos** (NVIDIA): Ollama, Stable Diffusion
- **Nyx** (NVIDIA): Ollama, Text Generation, Whisper
- **Hades** (AMD): Large model inference with Ollama

#### Edge Services (Small Nodes)
- **Hephaestus**: Traefik, Service Registry, Uptime Kuma
- **Moros**: Prometheus, Grafana, Loki, Alertmanager

#### Local Workstation
- Local-only OpenAPI servers (filesystem, git, docker access)

## Service Architecture

### Core AI Services

```
┌─────────────────────────────────────────────────────────────┐
│                         Open-WebUI                           │
│                    (User Interface + RAG)                    │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────┴───────────────────────────────────────┐
│                         LiteLLM                              │
│              (Load Balancer + API Gateway)                   │
└─────┬───────────────┬───────────────┬───────────────┬───────┘
      │               │               │               │
┌─────┴─────┐   ┌─────┴─────┐   ┌─────┴─────┐   ┌─────┴─────┐
│  Ollama   │   │  Ollama   │   │  Ollama   │   │  Ollama   │
│ (Orpheus) │   │ (Kratos)  │   │  (Nyx)    │   │  (Hades)  │
└───────────┘   └───────────┘   └───────────┘   └───────────┘
```

### OpenAPI Tool Servers

The platform includes 20+ OpenAPI servers providing various capabilities:

- **Thinking & Memory**: Sequential thinking, memory storage, context management
- **Search & Information**: Brave search, weather, web fetching
- **Development**: Git operations, filesystem access, SQL queries
- **Knowledge Management**: Graphiti knowledge graphs, embeddings
- **Utility**: Calculator, time, user info

### Data Services

```
PostgreSQL (Primary) ──── Streaming Replication ──── PostgreSQL (Replica)
       │
       ├── Open-WebUI Database
       ├── LiteLLM Database  
       ├── Service Registry
       └── Application Databases

Redis ──── Session Storage
      └─── Cache Layer

Qdrant ──── Vector Embeddings
       └─── RAG Storage

Neo4j ──── Knowledge Graphs
      └─── Graphiti Backend
```

## Load Balancing Strategy

LiteLLM provides intelligent routing across Ollama instances:

1. **Model-Based Routing**: Large models (70B+) route to Hades
2. **Load Distribution**: Smaller models distributed across NVIDIA nodes
3. **Fallback Chains**: Local models → External APIs (if configured)
4. **Health-Based Routing**: Automatic failover for unhealthy instances

## Security Architecture

### Network Security
- All services communicate over Docker overlay networks
- External access only through Traefik reverse proxy
- Service-to-service authentication via API keys
- TLS termination at edge

### Access Control
- Basic auth for admin interfaces
- API key authentication for OpenAPI servers
- JWT tokens for user sessions
- Role-based access in Open-WebUI

### Data Protection
- Encrypted secrets management
- Database encryption at rest
- NFS with access controls
- Regular automated backups

## Monitoring & Observability

### Metrics Collection
```
Service → Node Exporter → Prometheus → Grafana
        ↘ Custom Metrics ↗
```

### Log Aggregation
```
Service → Docker → Promtail → Loki → Grafana
```

### Health Monitoring
- Uptime Kuma for visual status
- Prometheus alerts via Alertmanager
- Service Registry with health checks

## Deployment Architecture

### Docker Compose Structure
- Base `docker-compose.yml` with common configuration
- Machine-specific override files
- Environment-based configuration
- Automated deployment scripts

### Service Discovery
- OPNsense provides DNS resolution
- Service Registry for dynamic discovery
- Health checks at multiple levels
- Automatic service registration

## Scaling Patterns

### Horizontal Scaling
- Add more GPU nodes for inference
- Additional CPU nodes for tools
- Database read replicas
- Cached frequently accessed data

### Vertical Scaling
- Upgrade Hades for larger models
- Add RAM for more concurrent models
- NVMe storage for faster model loading
- GPU upgrades for better performance

## Disaster Recovery

### Backup Strategy
- Automated PostgreSQL backups
- Redis persistence with AOF
- Configuration in Git
- Model checksums for verification

### High Availability
- Database replication
- Multiple Ollama instances
- Stateless services where possible
- Health-based routing

## Performance Optimization

### Model Loading
- Shared model storage on NAS
- Pre-loaded popular models
- Model caching on local NVMe
- Lazy loading for rarely used models

### Request Routing
- Least-busy instance selection
- Model affinity for efficiency
- Connection pooling
- Response caching

## Integration Points

### MCP Bridge
The platform includes an MCP proxy that allows integration with Model Context Protocol servers, bridging the gap between Claude Desktop tools and OpenAPI format.

### External APIs
LiteLLM supports external providers (OpenAI, Anthropic, etc.) as fallbacks or for specific capabilities not available locally.

### Custom Tools
Easy addition of new OpenAPI servers following the established pattern, with automatic registration and discovery.

## Future Considerations

### Kubernetes Migration
The architecture is designed to be easily portable to Kubernetes:
- Services are already containerized
- Stateless where possible
- Clear separation of concerns
- Health checks and metrics ready

### Multi-Region Support
Could be extended across multiple sites:
- WireGuard for secure connectivity
- Geo-distributed replicas
- Edge caching strategies
- Federated learning capabilities

## Conclusion

This architecture provides a robust foundation for AI workloads while maintaining flexibility and control. The distributed design ensures no single point of failure while the open-source approach guarantees long-term sustainability and customization options.
