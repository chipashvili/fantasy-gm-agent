#!/bin/bash

echo "=========================================="
echo " Fantasy Football AI Agent Setup"
echo "=========================================="
echo "This script will help you configure your .env file."
echo ""

read -p "Enter your ESPN League ID: " league_id
read -p "Enter your ESPN Year (e.g. 2026): " espn_year
read -p "Enter your ESPN Team Name: " team_name
echo ""
echo "For private leagues, you need your ESPN_S2 and SWID cookies."
read -p "Enter your ESPN_S2 cookie: " espn_s2
read -p "Enter your SWID cookie: " swid
echo ""
read -p "Enter your Telegram Bot Token: " telegram_token
read -p "Enter your Telegram Chat ID: " telegram_chat_id
echo ""
read -p "Enter your Gemini API Key (or press Enter to skip): " gemini_api_key
read -p "Enter your Anthropic API Key (or press Enter to skip): " anthropic_api_key
read -p "Enter your OpenAI API Key (or press Enter to skip): " openai_api_key

cat << ENV_EOF > .env
ESPN_LEAGUE_ID=$league_id
ESPN_YEAR=$espn_year
ESPN_TEAM_NAME="$team_name"
ESPN_S2="$espn_s2"
SWID="$swid"
TELEGRAM_TOKEN="$telegram_token"
TELEGRAM_CHAT_ID="$telegram_chat_id"
GEMINI_API_KEY="$gemini_api_key"
ANTHROPIC_API_KEY="$anthropic_api_key"
OPENAI_API_KEY="$openai_api_key"
ENV_EOF

echo ""
echo "✅ .env file created successfully!"
echo "Installing python dependencies..."
pip install -r requirements.txt
echo "✅ Done! You can now run 'python src/gm_agent.py'"
