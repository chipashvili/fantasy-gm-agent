#!/bin/bash

# Ensure the API key is set
if [ -z "$GEMINI_API_KEY" ]; then
    echo "⚠️  Error: GEMINI_API_KEY environment variable is not set."
    echo ""
    echo "Please set it before running the copilot, for example:"
    echo "export GEMINI_API_KEY='your_api_key_here'"
    echo "./run.sh"
    exit 1
fi

# Run the Draft Copilot using the fantasy-agent conda environment
echo "Starting Draft Copilot..."
/Users/o/miniconda3/envs/fantasy-agent/bin/python draft_copilot.py
