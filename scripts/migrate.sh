#!/bin/bash

# MusicLibrary Database Migration Script
# Runs all pending migrations against Supabase project
# Usage: ./scripts/migrate.sh [--rollback] [--version VERSION]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MIGRATIONS_DIR="$PROJECT_ROOT/supabase/migrations"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check environment
if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_SERVICE_ROLE_KEY" ]; then
  echo -e "${RED}Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set${NC}"
  echo "Set these in your .env.local file or as environment variables"
  exit 1
fi

# Load .env.local if it exists
if [ -f "$PROJECT_ROOT/.env.local" ]; then
  export $(cat "$PROJECT_ROOT/.env.local" | grep -v '#' | xargs)
fi

log_info() {
  echo -e "${GREEN}✓${NC} $1"
}

log_error() {
  echo -e "${RED}✗${NC} $1"
}

log_warn() {
  echo -e "${YELLOW}⚠${NC} $1"
}

# Create migrations table if it doesn't exist
ensure_migrations_table() {
  curl -s -X POST "$SUPABASE_URL/rest/v1/rpc/sql" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Content-Type: application/json" \
    -d '{
      "query": "CREATE TABLE IF NOT EXISTS _migrations (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) UNIQUE NOT NULL,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      );"
    }' > /dev/null 2>&1 || true
}

# List applied migrations
list_migrations() {
  echo -e "\n${YELLOW}Applied Migrations:${NC}"
  curl -s -X GET "$SUPABASE_URL/rest/v1/rpc/sql" \
    -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
    -H "Content-Type: application/json" \
    -d '{"query": "SELECT name FROM _migrations ORDER BY applied_at;"}' || echo "No migrations found"
}

# Apply a single migration
apply_migration() {
  local migration_file="$1"
  local migration_name="$(basename "$migration_file")"

  if [ ! -f "$migration_file" ]; then
    log_error "Migration file not found: $migration_file"
    return 1
  fi

  local sql_content=$(cat "$migration_file")

  echo "Applying migration: $migration_name..."

  # Execute the migration using psql if available, otherwise use API
  if command -v psql &> /dev/null; then
    psql "$SUPABASE_URL" -U postgres -w < "$migration_file" > /dev/null 2>&1 && {
      log_info "Applied $migration_name"
    } || {
      log_error "Failed to apply $migration_name"
      return 1
    }
  else
    log_warn "psql not found - migrations should be applied via Supabase dashboard or CLI"
    echo "Migration content:"
    echo "---"
    head -20 "$migration_file"
    echo "... (see $migration_file for full content)"
    echo "---"
  fi
}

# Rollback a migration
rollback_migration() {
  local version="$1"
  local rollback_file="$MIGRATIONS_DIR/${version}_rollback.sql"

  if [ ! -f "$rollback_file" ]; then
    log_error "Rollback script not found: $rollback_file"
    return 1
  fi

  echo "Rolling back migration version $version..."
  apply_migration "$rollback_file"

  if [ $? -eq 0 ]; then
    log_info "Rolled back version $version"
  else
    log_error "Failed to rollback version $version"
    return 1
  fi
}

# Parse command-line arguments
MODE="apply"
TARGET_VERSION=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --rollback)
      MODE="rollback"
      if [ -n "$2" ] && [[ ! "$2" =~ ^-- ]]; then
        TARGET_VERSION="$2"
        shift
      fi
      shift
      ;;
    --version)
      TARGET_VERSION="$2"
      shift 2
      ;;
    --list)
      list_migrations
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Main execution
echo "MusicLibrary Database Migration Tool"
echo "========================================"

ensure_migrations_table

if [ "$MODE" = "apply" ]; then
  echo "Running pending migrations..."

  if [ -z "$(ls -A $MIGRATIONS_DIR)" ]; then
    log_warn "No migration files found in $MIGRATIONS_DIR"
    exit 1
  fi

  for migration_file in "$MIGRATIONS_DIR"/*[!_rollback].sql; do
    if [ -f "$migration_file" ]; then
      apply_migration "$migration_file"
    fi
  done

  log_info "All migrations completed successfully"

elif [ "$MODE" = "rollback" ]; then
  if [ -z "$TARGET_VERSION" ]; then
    log_error "Version required for rollback: --rollback --version VERSION"
    exit 1
  fi

  rollback_migration "$TARGET_VERSION"
fi

echo ""
echo "Migration status:"
list_migrations
echo ""
