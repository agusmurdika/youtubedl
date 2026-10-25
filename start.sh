#!/usr/bin/env bash

# Cross-platform Launcher (Linux, macOS, Git Bash)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if command -v python3 &>/dev/null; then
    PY_CMD="python3"
elif command -v python &>/dev/null; then
    PY_CMD="python"
else
    echo "❌ Python tidak ditemukan. Harap install Python terlebih dahulu."
    exit 1
fi

# Cek apakah ffmpeg tersedia
if ! command -v ffmpeg &>/dev/null; then
    echo "⚠️  Peringatan: ffmpeg tidak ditemukan di PATH."
    echo "   Untuk menggabungkan resolusi tinggi (1080p/4K) dan audio/thumbnail,"
    echo "   silakan install ffmpeg (Linux: sudo apt/pacman install ffmpeg | Mac: brew install ffmpeg)."
fi

# Jalankan program utama
"$PY_CMD" "$SCRIPT_DIR/main.py" "$@"
