#!/usr/bin/env bash

# Cross-platform Launcher untuk YouTube-like Local Player (Linux, macOS, Git Bash)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${1:-8888}"

if command -v python3 &>/dev/null; then
    PY_CMD="python3"
elif command -v python &>/dev/null; then
    PY_CMD="python"
else
    echo "❌ Python tidak ditemukan. Harap install Python terlebih dahulu."
    exit 1
fi

if ! command -v ffprobe &>/dev/null; then
    echo "⚠️  ffprobe tidak ditemukan di PATH. Install ffmpeg terlebih dahulu."
    exit 1
fi

echo "🎬 Menjalankan YouTube Local Player di http://localhost:$PORT ..."
"$PY_CMD" "$SCRIPT_DIR/server.py" "$PORT"
