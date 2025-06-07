# Distributed AI Platform

A fully open-source, distributed AI platform combining Open-WebUI, LiteLLM, Ollama, and OpenAPI servers across multiple machines in a home lab environment.

## 🚀 Quick Start

1. **Clone this repository** to all machines:
   ```bash
   git clone <repository-url> /opt/ai-platform
   cd /opt/ai-platform
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   nano .env
   ```

3. **Deploy on each machine**:
   ```bash
   # On Erebus (Primary Database)
   ./scripts/deploy.sh erebus

   # On other machines
   ./scripts/deploy.sh <machine-name>
   ```

4. **Access the platform**:
   - Open-WebUI: http://orpheus.local:3000
   - LiteLLM API: http://orpheus.local:4000
   - Grafana: http://moros.local:3001

## 📋 Architecture Overview

### Infrastructure Layout

| Machine | Type | Specs | Primary Role |
|---------|------|-------|--------------|
| **Erebus** | CPU | 8C/32GB | PostgreSQL, Redis, Qdrant |
| **Thanatos** | CPU | 8C/32GB | OpenAPI servers, monitoring |
| **Zelus** | CPU | 8C/32GB | Additional OpenAPI servers |
| **Orpheus** | NVIDIA GPU | 8C/32GB/12GB | Open-WebUI, LiteLLM |
| **Kratos** | NVIDIA GPU | 8C/32GB/12GB | Ollama instance |
| **Nyx** | NVIDIA GPU | 8C/32GB/12GB | Ollama instance |
| **Hades** | AMD GPU | 24C/128GB/48GB | Heavy Ollama workloads |
| **Hephaestus** | Small | 6C/8GB | Traefik, service registry |
| **Moros** | Small | 6C/8GB | Grafana, monitoring UI |
| **Workstation** | Local | Variable | Local-only OpenAPI servers |

### Service Distribution

```
┌─────────────────────────────────────────────────────────────┐
│                        OPNsense (DNS)                        │
└─────────────────────────────────────────────────────────────┘
                               │
┌──────────────────────────────┴──────────────────────────────┐
│                     TrueNAS (Storage)                        │
│  • /models - Shared AI models                                │
│  • /shared - Common data                                     │
└─────────────────────────────────────────────────────────────┘
                               │
┌──────────────────┬───────────┴───────────┬──────────────────┐
│   Data Tier      │    Application Tier   │  Edge Services   │
├──────────────────┼───────────────────────┼──────────────────┤
│ • PostgreSQL     │ • Open-WebUI          │ • Traefik        │
│ • Redis          │ • LiteLLM             │ • Monitoring     │
│ • Qdrant         │ • Ollama (4x)         │ • Registry       │
│                  │ • OpenAPI Servers     │                  │
└──────────────────┴───────────────────────┴──────────────────┘
```

## 🛠️ Key Features

- **Load Balanced Inference**: Multiple Ollama instances with intelligent routing via LiteLLM
- **Centralized Storage**: All models stored on NAS, no duplication
- **High Availability**: No single point of failure for critical services
- **Comprehensive Monitoring**: Prometheus + Grafana + Loki for full observability
- **Security First**: Internal Docker networks, reverse proxy authentication
- **Tool Ecosystem**: 20+ OpenAPI servers + MCP proxy support

## 📦 Service Components

### Core AI Services
- **Open-WebUI**: Primary user interface with RAG support
- **LiteLLM**: Unified API proxy with load balancing
- **Ollama**: Local LLM inference (distributed across GPU nodes)

### Data Services
- **PostgreSQL**: Primary database with replication
- **Redis**: Caching and session management
- **Qdrant**: Vector database for embeddings

### OpenAPI Servers
- **Local Only**: filesystem, git, docker, time, get_user_info
- **Network**: weather, brave_search, memory, graphiti, sql
- **MCP Proxy**: Bridge any MCP server to OpenAPI format

### Monitoring Stack
- **Prometheus**: Metrics collection
- **Grafana**: Visualization dashboards
- **Loki**: Log aggregation
- **Node Exporter**: System metrics

## 🔧 Management Scripts

- `deploy.sh <machine>` - Deploy services on specific machine
- `backup.sh` - Backup databases and configurations
- `health-check.sh` - Check all service health
- `update-models.sh` - Sync models from NAS
- `logs.sh <service>` - View service logs

## 📚 Documentation

- [Architecture Guide](docs/ARCHITECTURE.md) - Detailed system design
- [Deployment Guide](docs/DEPLOYMENT.md) - Step-by-step setup
- [Service Configuration](docs/SERVICES.md) - Individual service details
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions
- [Security Guide](docs/SECURITY.md) - Security best practices

## 🚨 Important Notes

1. **DNS Setup**: Ensure all machines can resolve `.local` domains via OPNsense
2. **NFS Mounts**: Configure NFS shares before deploying GPU services
3. **Secrets**: Never commit `.env` or `secrets/` directory
4. **GPU Drivers**: Ensure NVIDIA/AMD drivers are installed on GPU nodes
5. **Firewall**: Only expose services through Traefik reverse proxy

## 🔄 Deployment Order

1. **Erebus** - Database services must start first
2. **Hephaestus** - Traefik and service registry
3. **GPU Nodes** - Ollama instances
4. **Orpheus** - Open-WebUI and LiteLLM
5. **CPU Nodes** - OpenAPI servers
6. **Moros** - Monitoring UI
7. **Workstation** - Local services

## 🆘 Quick Troubleshooting

```bash
# Check service status
./scripts/health-check.sh

# View logs for a service
docker logs <service-name>

# Restart a service
docker-compose -f docker-compose.<machine>.yml restart <service>

# Check network connectivity
docker network ls
docker network inspect ai-network
```

## 📈 Performance Tuning

See [Performance Guide](docs/PERFORMANCE.md) for:
- Model loading optimization
- GPU memory management
- Network performance tuning
- Database optimization
- Caching strategies

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.
