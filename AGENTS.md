# AGENTS.md

## Project

This is a Python Telegram bot (`aiogram 3.x`) for healthy meal ordering and nutrition tracking.

Main goals:
- help users choose healthy meals;
- track orders and nutrition-related preferences;
- support AI tips through local/Ollama-compatible API when available.

## Important safety rules

- Do not read, print, copy, modify, or expose `.env`.
- Do not reveal secrets, tokens, API keys, database URLs, cookies, or credentials.
- Use `.env.example` for examples instead of `.env`.
- Never hardcode real tokens into code.
- Do not delete the SQLite database or user/order data without explicit confirmation.
- Do not run destructive commands like `rm -rf`, database wipes, or mass file deletion without explicit confirmation.
- Before large refactoring, explain the plan briefly.

## Running the bot

```bash
source .venv/bin/activate
python bot.py       