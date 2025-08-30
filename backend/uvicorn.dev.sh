#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
uvicorn app.asgi:app --reload --app-dir ./src

