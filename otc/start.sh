#!/data/data/com.termux/files/usr/bin/bash
# Premamulu OTC: start the local server in Termux.
cd "$(dirname "$0")"
command -v termux-wake-lock >/dev/null && termux-wake-lock   # keep running with the screen off
python server.py "$@"
