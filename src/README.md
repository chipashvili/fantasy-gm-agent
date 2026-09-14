# Fantasy GM Agent Setup

## Telegram Bot Configuration
1. Open the Telegram app and search for `@BotFather`.
2. Send the command `/newbot` and follow the instructions to choose a name and username.
3. BotFather will give you an **API Token** (e.g., `123456789:ABCdefGHIjklMNOpqrSTUvwxYZ`).
4. Next, you need your personal Chat ID so the bot only talks to you. Search for `@userinfobot` in Telegram, send it `/start`, and copy the `Id` (e.g., `987654321`).

## Running the Agent
Set your environment variables before running the agent on your Mac Mini:

```bash
export TELEGRAM_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
export ESPN_S2="your_espn_s2_cookie"
export SWID="{your_swid_cookie}"

# Run it using the environment Python
/Users/o/miniconda3/envs/fantasy-agent/bin/python src/gm_agent.py
```
