#!/bin/bash
# Backup script for PostgreSQL databases
# Usage: ./backup-postgres.sh

set -e

# Configuration
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"
RETENTION_DAYS=7

# Database configuration from environment
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGPASSWORD="${PGPASSWORD}"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to backup a database
backup_database() {
    local db_name=$1
    local backup_file="$BACKUP_DIR/${db_name}_${TIMESTAMP}.sql.gz"
    
    log "Backing up database: $db_name"
    
    if PGPASSWORD="$PGPASSWORD" pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$db_name" | gzip > "$backup_file"; then
        log "Successfully backed up $db_name to $backup_file"
        # Calculate size
        size=$(du -h "$backup_file" | cut -f1)
        log "Backup size: $size"
    else
        log "ERROR: Failed to backup $db_name"
        return 1
    fi
}

# Function to cleanup old backups
cleanup_old_backups() {
    log "Cleaning up backups older than $RETENTION_DAYS days"
    find "$BACKUP_DIR" -name "*.sql.gz" -type f -mtime +$RETENTION_DAYS -delete
}

# Main backup process
main() {
    log "Starting PostgreSQL backup process"
    
    # Get list of databases (excluding templates)
    databases=$(PGPASSWORD="$PGPASSWORD" psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -t -c "SELECT datname FROM pg_database WHERE datistemplate = false AND datname != 'postgres';" | grep -v '^$')
    
    # Always backup main postgres database
    backup_database "postgres"
    
    # Backup each database
    for db in $databases; do
        backup_database "$db"
    done
    
    # Cleanup old backups
    cleanup_old_backups
    
    log "Backup process completed"
}

# Run main function
main
