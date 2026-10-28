#!/usr/bin/env bash
set -euo pipefail
: "${REELS_ACCESS_TOKEN:?Configure REELS_ACCESS_TOKEN before exposing the service}"
if [[ -z "${DATABASE_URL:-}" && -z "${REELS_DATA_DIR:-}" ]]; then
  echo "Configure DATABASE_URL or an explicitly persistent REELS_DATA_DIR" >&2
  exit 1
fi
# Render terminates HTTPS at its reverse proxy. Trust forwarded headers only
# when running behind the hosting provider's proxy, never on an exposed VM.
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 --proxy-headers --forwarded-allow-ips '*'
