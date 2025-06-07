# Deployment Guide - Distributed AI Platform

## Prerequisites

### System Requirements
- Docker and Docker Compose installed on all machines
- NFS client configured for model storage access
- Network connectivity between all machines
- DNS resolution working (via OPNsense)
- Sufficient disk space for data directories
- GPU drivers installed (NVIDIA/AMD as appropriate)

### Required Software Versions
- Docker: 24.0+
- Docker Compose: 2.20+
- NVIDIA Driver: 525+ (for NVIDIA GPUs)
- ROCm: 5.7+ (for AMD GPUs)

## Pre-Deployment Setup

### 1. Clone Repository
On each machine:
```bash
git clone <repository-url> /opt/ai-platform
cd /opt/ai-platform
```

### 2. Configure Environment
```bash
cp .env.example .env
nano .env  # Edit with your specific values
```

Key variables to configure:
- Database passwords
- API keys (OpenAI, Anthropic, Brave, etc.)
- Domain name
- NFS paths
- Admin passwords

### 3. Create Data Directories
```bash
sudo mkdir -p /opt/ai-platform/{data,logs,tmp}
sudo chown -R $USER:$USER /opt/ai-platform
```

### 4. Configure NFS Mounts
Add to `/etc/fstab`:
```
poseidon.local:/mnt/tank/models /mnt/models nfs defaults,_netdev 0 0
poseidon.local:/mnt/tank/shared /mnt/shared nfs defaults,_netdev 0 0
```

Mount the shares:
```bash
sudo mkdir -p /mnt/{models,shared}
sudo mount -a
```

## Deployment Order

Deploy services in this specific order to ensure dependencies are met:

### Phase 1: Data Tier (Erebus)
```bash
cd /opt/ai-platform
./scripts/deploy.sh erebus
```

Wait for databases to be fully initialized:
```bash
./scripts/health-check.sh erebus
```

### Phase 2: Edge Services (Hephaestus)
```bash
./scripts/deploy.sh hephaestus
```

This starts:
- Traefik (reverse proxy)
- Service Registry
- Uptime Kuma

### Phase 3: Secondary Data Services (Thanatos, Zelus)
Deploy in parallel:
```bash
./scripts/deploy.sh thanatos &
./scripts/deploy.sh zelus &
wait
```

### Phase 4: GPU Nodes
Deploy Ollama instances:
```bash
# Can run in parallel
./scripts/deploy.sh orpheus &
./scripts/deploy.sh kratos &
./scripts/deploy.sh nyx &
./scripts/deploy.sh hades &
wait
```

### Phase 5: Monitoring (Moros)
```bash
./scripts/deploy.sh moros
```

### Phase 6: Local Workstation
On your workstation:
```bash
./scripts/deploy.sh local
```

## Post-Deployment Configuration

### 1. Initialize Databases

Connect to PostgreSQL and create application databases:
```bash
docker exec -it postgres-primary psql -U postgres
```

```sql
CREATE DATABASE openwebui;
CREATE DATABASE litellm;
CREATE DATABASE service_registry;
CREATE DATABASE model_registry;
CREATE DATABASE memory;
GRANT ALL PRIVILEGES ON DATABASE openwebui TO postgres;
GRANT ALL PRIVILEGES ON DATABASE litellm TO postgres;
-- Repeat for other databases
```

### 2. Configure Open-WebUI

1. Access Open-WebUI at http://orpheus.local:3000
2. Create admin account on first access
3. Configure model endpoints (already set to use LiteLLM)
4. Set up RAG collections if needed

### 3. Load Initial Models

Models are automatically loaded by the model-loader service, but you can manually trigger:
```bash
# On each GPU node
docker exec -it ollama-<node> ollama pull llama3.2
docker exec -it ollama-<node> ollama pull codellama:13b
# etc.
```

### 4. Configure Grafana

1. Access Grafana at http://moros.local:3001
2. Login with admin credentials from .env
3. Dashboards are auto-provisioned
4. Configure notification channels in Alerting

### 5. Set Up Backups

Enable automated backups:
```bash
# On Erebus
docker exec -it db-backup /backup.sh
```

## Verification Steps

### 1. Check All Services
```bash
./scripts/health-check.sh all
```

### 2. Test Model Inference
```bash
# Test Ollama directly
curl http://orpheus.local:11434/api/generate -d '{
  "model": "llama3.2",
  "prompt": "Hello, world!"
}'

# Test through LiteLLM
curl http://orpheus.local:4000/v1/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2",
    "prompt": "Hello, world!"
  }'
```

### 3. Verify Service Registry
```bash
curl http://hephaestus.local:8090/services | jq
```

### 4. Check Monitoring
- Prometheus targets: http://moros.local:9090/targets
- Grafana dashboards: http://moros.local:3001
- Uptime Kuma: http://hephaestus.local:3001

## Common Issues & Solutions

### Issue: Services fail to start
**Solution**: Check Docker logs
```bash
docker-compose -f docker-compose.<machine>.yml logs <service>
```

### Issue: Cannot connect to databases
**Solution**: Verify network connectivity
```bash
ping erebus.local
telnet erebus.local 5432
```

### Issue: Models not loading
**Solution**: Check NFS mount
```bash
df -h | grep models
ls -la /mnt/models
```

### Issue: GPU not detected
**Solution**: Verify driver and Docker GPU support
```bash
nvidia-smi  # For NVIDIA
rocm-smi    # For AMD
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

### Issue: Service registry not updating
**Solution**: Check service-registrar logs
```bash
docker logs service-registrar-<machine>
```

## Maintenance Tasks

### Daily
- Check service health status
- Monitor disk usage
- Review error logs in Grafana

### Weekly
- Review Prometheus alerts
- Check backup integrity
- Update model library

### Monthly
- Rotate logs
- Clean old Docker images
- Update software versions
- Performance review

## Scaling Operations

### Adding a New GPU Node

1. Prepare the machine with Docker and GPU drivers
2. Clone repository and configure
3. Create a new docker-compose.<machine>.yml based on existing GPU configs
4. Deploy services
5. Update LiteLLM config to include new Ollama endpoint

### Adding New OpenAPI Servers

1. Create server implementation in openapi-servers/
2. Add to appropriate machine's docker-compose file
3. Deploy with docker-compose up -d <service>
4. Service auto-registers with registry

### Expanding Storage

1. Add new volume to TrueNAS
2. Create NFS export
3. Mount on relevant machines
4. Update Docker volumes in compose files

## Security Hardening

### 1. Change Default Passwords
Update all default passwords in .env file before deployment

### 2. Configure Firewall
On OPNsense, create rules to:
- Allow internal traffic between nodes
- Block external access except through Traefik
- Whitelist management access

### 3. Enable TLS
Configure Traefik with Let's Encrypt:
```yaml
# In traefik dynamic config
http:
  routers:
    router-secure:
      rule: "Host(`open-webui.yourdomain.com`)"
      tls:
        certResolver: letsencrypt
```

### 4. Regular Updates
```bash
# Update all services
docker-compose -f docker-compose.<machine>.yml pull
docker-compose -f docker-compose.<machine>.yml up -d
```

## Backup and Recovery

### Backup Procedures

1. **Database Backups**
   - Automated via db-backup service
   - Stored in /opt/ai-platform/data/postgres-backups
   - 7-day retention by default

2. **Configuration Backup**
   ```bash
   tar -czf config-backup-$(date +%Y%m%d).tar.gz \
     /opt/ai-platform/.env \
     /opt/ai-platform/configs \
     /opt/ai-platform/docker-compose.*.yml
   ```

3. **Model Backup**
   - Models on NAS should be backed up separately
   - Keep checksums for verification

### Recovery Procedures

1. **Database Recovery**
   ```bash
   # Stop services
   docker-compose -f docker-compose.erebus.yml stop postgres
   
   # Restore from backup
   gunzip < /backups/postgres_20240315_120000.sql.gz | \
     docker exec -i postgres-primary psql -U postgres
   
   # Restart services
   docker-compose -f docker-compose.erebus.yml start postgres
   ```

2. **Full Platform Recovery**
   - Deploy infrastructure in order
   - Restore databases
   - Verify service registry
   - Test functionality

## Performance Tuning

### 1. GPU Memory Management
Edit Ollama environment variables:
```yaml
OLLAMA_GPU_OVERHEAD: 1073741824  # 1GB overhead
OLLAMA_CUDA_MEMORY_FRACTION: 0.90  # Use 90% of VRAM
```

### 2. Database Optimization
Tune PostgreSQL for your workload:
```sql
ALTER SYSTEM SET shared_buffers = '4GB';
ALTER SYSTEM SET effective_cache_size = '12GB';
ALTER SYSTEM SET maintenance_work_mem = '1GB';
SELECT pg_reload_conf();
```

### 3. Network Optimization
Enable jumbo frames if supported:
```bash
sudo ip link set dev eth0 mtu 9000
```

## Troubleshooting Commands

```bash
# View all running containers
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Check resource usage
docker stats --no-stream

# Inspect network
docker network inspect ai-network

# View recent logs
docker-compose -f docker-compose.<machine>.yml logs --tail=100 -f

# Clean up unused resources
docker system prune -a --volumes
```

## Support Resources

- Architecture Documentation: [ARCHITECTURE.md](ARCHITECTURE.md)
- Service Details: [SERVICES.md](SERVICES.md)
- Security Guide: [SECURITY.md](SECURITY.md)
- Community Forum: [Link to forum]
- Issue Tracker: [Link to issues]

Remember to always test changes in a non-production environment first!
