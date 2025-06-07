# Secrets Directory

This directory contains sensitive configuration files for the AI platform.

## Required Secret Files

Create the following files with secure values:

1. **db_password.txt** - PostgreSQL database password
2. **redis_password.txt** - Redis password
3. **admin_password.txt** - Admin user password
4. **openai_api_key.txt** - OpenAI API key (optional)
5. **anthropic_api_key.txt** - Anthropic API key (optional)

## Security Notes

- **NEVER** commit these files to version control
- Use strong, randomly generated passwords
- Keep backups in a secure location
- Rotate passwords regularly
- Use proper file permissions (600)

## Generating Secrets

You can use the provided script to generate secure passwords:

```bash
../scripts/generate-secrets.sh
```

Or manually create each file:

```bash
# Generate a secure password
openssl rand -base64 32 > db_password.txt
```

## File Permissions

Ensure proper permissions:

```bash
chmod 600 *.txt
```
