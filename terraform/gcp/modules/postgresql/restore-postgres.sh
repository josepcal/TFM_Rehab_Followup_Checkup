#!/bin/bash
# restore-postgres.sh — Restore a pg_dump backup into the dev-postgresql VM
#
# Usage:
#   ./restore-postgres.sh <backup-file>
#   ./restore-postgres.sh ./backups/keycloak_20260518_223319.dump
#
# Restores the latest backup if no argument given:
#   ./restore-postgres.sh

set -e

# Configuration — adjust if needed
PROJECT_ID="${PROJECT_ID:-terraform-project-496514}"
ZONE="${ZONE:-us-central1-a}"
INSTANCE="${INSTANCE:-dev-postgresql}"
DB_NAME="${DB_NAME:-keycloak}"
DB_USER="${DB_USER:-keycloak}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"

# Pick backup file
if [ -n "$1" ]; then
  BACKUP_FILE="$1"
else
  # Use the most recent backup
  BACKUP_FILE=$(ls -t "$BACKUP_DIR"/*.dump 2>/dev/null | head -1)
  if [ -z "$BACKUP_FILE" ]; then
    echo "✗ No backup files found in $BACKUP_DIR"
    echo "  Usage: $0 <backup-file>"
    exit 1
  fi
  echo "Using most recent backup: $BACKUP_FILE"
fi

# Verify file exists
if [ ! -f "$BACKUP_FILE" ]; then
  echo "✗ Backup file not found: $BACKUP_FILE"
  exit 1
fi

# Verify file is not empty
if [ ! -s "$BACKUP_FILE" ]; then
  echo "✗ Backup file is empty: $BACKUP_FILE"
  exit 1
fi

BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "=========================================="
echo "PostgreSQL Restore"
echo "=========================================="
echo "  Backup file:  $BACKUP_FILE ($BACKUP_SIZE)"
echo "  Target VM:    $INSTANCE"
echo "  Zone:         $ZONE"
echo "  Project:      $PROJECT_ID"
echo "  Database:     $DB_NAME"
echo "=========================================="
echo ""

# Confirm
read -p "Continue with restore? This will OVERWRITE existing data. [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 0
fi

# Step 1 — Verify PostgreSQL is reachable
echo "[1/4] Verifying PostgreSQL is reachable..."
if ! gcloud compute ssh "$INSTANCE" \
    --zone="$ZONE" \
    --project="$PROJECT_ID" \
    --tunnel-through-iap \
    --command="sudo -u postgres psql -c 'SELECT 1' $DB_NAME" \
    >/dev/null 2>&1; then
  echo "✗ Cannot connect to PostgreSQL. Is the VM up and running?"
  exit 1
fi
echo "  ✓ PostgreSQL is reachable"

# Step 2 — Upload backup file to VM
echo "[2/4] Uploading backup file to VM..."
#gcloud compute scp "$BACKUP_FILE" \
#  "$INSTANCE:/tmp/restore.dump" \
#  --zone="$ZONE" \
#  --project="$PROJECT_ID" \
#  --tunnel-through-iap

                echo "uploading $BACKUP_FILE"
                # 1. Create a temporary bucket (required iam)
				gsutil mb -p terraform-project-496514 -l us-central1 gs://terraform-project-496514-restore-tmp

				# 2. Upload from local
				gsutil cp $BACKUP_FILE \
				  gs://terraform-project-496514-restore-tmp/

				# 3. (!!!!!!required iam!!!!) Download on the VM (uses internal Google network — fast) 
				gcloud compute ssh dev-postgresql --zone=us-central1-a --tunnel-through-iap -- \
				  'gsutil cp gs://terraform-project-496514-restore-tmp/'$(basename $BACKUP_FILE)' /tmp/restore.dump && sudo chown postgres:postgres /tmp/restore.dump'

				# 4. Restore
				gcloud compute ssh dev-postgresql --zone=us-central1-a --tunnel-through-iap -- \
				  'sudo -u postgres pg_restore --clean --if-exists --no-owner --no-privileges -d keycloak /tmp/restore.dump'

				# 5. Cleanup (IMPORTANT!!!)
				gsutil rm gs://terraform-project-496514-restore-tmp/$(basename $BACKUP_FILE)
				gsutil rb gs://terraform-project-496514-restore-tmp

echo "  ✓ Uploaded"

#gcloud compute ssh "$INSTANCE" \
#  --zone="$ZONE" \
#  --project="$PROJECT_ID" \
#  --tunnel-through-iap \
#  --command="cp ~/restore.dump /tmp/restore.dump" \
#  || echo "   restore.dmp moved to /tmp/restore.dump (may already exist)"

# Step 3 — Run pg_restore
echo "[3/4] Restoring database..."
gcloud compute ssh "$INSTANCE" \
  --zone="$ZONE" \
  --project="$PROJECT_ID" \
  --tunnel-through-iap \
  --command="sudo -u postgres pg_restore --clean --if-exists --no-privileges -d $DB_NAME /tmp/restore.dump" \
  || echo "  ⚠ pg_restore reported warnings (often expected with --clean)"

# Step 4 — Cleanup
echo "[4/4] Cleaning up..."
gcloud compute ssh "$INSTANCE" \
  --zone="$ZONE" \
  --project="$PROJECT_ID" \
  --tunnel-through-iap \
  --command="sudo rm -f /tmp/restore.dump"
echo "  ✓ Cleaned up"

echo ""
echo "=========================================="
echo "✓ Restore complete!"
echo "=========================================="
echo ""
echo "Verify the data:"
echo "  gcloud compute ssh $INSTANCE --zone=$ZONE --tunnel-through-iap -- \\"
echo "    sudo -u postgres psql -d $DB_NAME -c \"\\dt\""
echo ""
echo "Or restart Keycloak to pick up the restored data:"
echo "  gcloud compute ssh dev-keycloak --zone=$ZONE --tunnel-through-iap -- \\"
echo "    sudo systemctl restart keycloak"