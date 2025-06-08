# Platform Domain Configuration Update

## Summary

I've successfully implemented a configurable domain solution for your OpenAPI AI Platform. The platform was previously hardcoded to use `.local` domains, which doesn't work with your network configuration. Now you can set any domain suffix you need.

## Changes Made

### 1. Environment Configuration
**File: `.env.example`**
- Added `PLATFORM_DOMAIN=.local` variable with a default of `.local`
- Updated all hardcoded `.local` references to use `${PLATFORM_DOMAIN:-.local}`
- Updated `NFS_SERVER`, `POSTGRES_HOST`, and `REDIS_HOST` to use the variable

### 2. Docker Compose Files
**Files: All `docker-compose.*.yml` files**
- Updated all hostname fields to use `${PLATFORM_DOMAIN:-.local}`
- Example: `hostname: ollama.hades.local` → `hostname: ollama.hades${PLATFORM_DOMAIN:-.local}`
- Updated environment variables that referenced `.local` domains to use proper variables

### 3. Configuration Templates
**New Files Created:**
- `/configs/litellm_config.yaml.template` - Template for LiteLLM configuration
- `/configs/traefik/dynamic/routes.yml.template` - Template for Traefik routes

These templates use `${PLATFORM_DOMAIN}` placeholders that get replaced during deployment.

### 4. Template Processing Script
**New File: `/scripts/process-templates.sh`**
- Processes configuration templates and replaces `${PLATFORM_DOMAIN}` with actual value
- Creates backups of existing configuration files
- Automatically run during deployment

### 5. Deployment Script Updates
**File: `/scripts/deploy.sh`**
- Added `process_config_templates()` function
- Integrated template processing into deployment workflow
- Updated service URLs in post-deployment messages to use `${PLATFORM_DOMAIN:-.local}`

### 6. Helper Script
**New File: `/scripts/update-compose-domains.sh`**
- Batch updates all docker-compose files to use the domain variable
- Useful for maintenance and updates

### 7. Documentation Updates
**File: `README.md`**
- Added instructions for setting `PLATFORM_DOMAIN`
- Updated example URLs to show the variable usage
- Added note about running template processor after domain changes

## How to Use

### Initial Setup
1. Copy `.env.example` to `.env`
2. Set your domain suffix:
   ```bash
   # Examples:
   PLATFORM_DOMAIN=.lan
   PLATFORM_DOMAIN=.home
   PLATFORM_DOMAIN=.mynet
   # Or leave it as .local if that works for you
   ```

### Deployment
The deployment script automatically handles everything:
```bash
./scripts/deploy.sh <machine-name>
```

### Changing Domain Later
If you need to change the domain after initial setup:
1. Update `PLATFORM_DOMAIN` in your `.env` file
2. Run: `./scripts/process-templates.sh`
3. Redeploy services: `./scripts/deploy.sh <machine-name>`

## Testing

To verify everything works:
1. Set your `PLATFORM_DOMAIN` in `.env`
2. Run `./scripts/process-templates.sh`
3. Check the generated files:
   - `/configs/litellm_config.yaml` should have your domain
   - `/configs/traefik/dynamic/routes.yml` should have your domain
4. Deploy a service and verify hostnames are correct

## Benefits

1. **Flexibility**: Works with any domain suffix (.local, .lan, .home, etc.)
2. **Backwards Compatible**: Defaults to `.local` if not specified
3. **Centralized Configuration**: Change domain in one place
4. **Automatic Processing**: Deployment script handles everything
5. **No Manual Editing**: All configuration files are generated correctly

## Notes

- The `PLATFORM_DOMAIN` variable includes the dot (e.g., `.lan` not `lan`)
- Docker Compose files support environment variable substitution natively
- Configuration files that don't support variables use the template system
- Always run `./scripts/process-templates.sh` after changing the domain

This solution makes your platform truly portable across different network configurations!
