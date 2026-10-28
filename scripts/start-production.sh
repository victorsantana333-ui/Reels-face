#!/usr/bin/env bash
set -euo pipefail
: "${REELS_ACCESS_TOKEN:?Configure REELS_ACCESS_TOKEN before exposing the service}"
: "${REELS_DATA_DIR:?Configure a persistent REELS_DATA_DIR}"
# Render terminates HTTPS at its reverse proxy. Trust forwarded headers only
# when running behind the hosting provider's proxy, never on an exposed VM.
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 --proxy-headers --forwarded-allow-ips '*'
