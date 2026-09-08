#!/usr/bin/env bash
# Menjalankan backend OmniClip.
#
# Disarankan dijalankan di terminal SISTEM (bukan terminal VS Code): bila memori
# habis, OOM killer bekerja pada cgroup pemanggil, dan itulah sebabnya VS Code
# ikut tertutup pada percobaan sebelumnya.
set -euo pipefail
cd "$(dirname "$0")/backend"
exec venv/bin/python run.py
