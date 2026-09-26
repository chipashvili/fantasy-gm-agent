#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"
echo "Starting Fantasy GM Agent..."
if [ -d "$DIR/venv" ]; then
    "$DIR/venv/bin/python" "$DIR/src/gm_agent.py"
elif command -v conda &> /dev/null; then
    source "$(conda info --base)/bin/activate" fantasy-agent 2>/dev/null || true
    python "$DIR/src/gm_agent.py"
else
    python3 "$DIR/src/gm_agent.py"
fi
