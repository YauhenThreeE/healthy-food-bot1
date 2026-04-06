# AGENTS.md

## Cursor Cloud specific instructions

This is a Python Telegram bot (`aiogram 3.x`) for healthy meal ordering and nutrition tracking.

### Running the bot

```bash
source .venv/bin/activate
python bot.py
```

Requires `BOT_TOKEN` in `.env` (Telegram bot token from @BotFather). Without it, `bot.py` raises `ValueError` at import time. Copy `.env.example` to `.env` and fill in the token.

### Key caveats

- **Database**: SQLite by default (`./data/healthy_food.db`), auto-created on first run via `init_db()`. No migrations needed — uses `create_all()`.
- **Seeding**: 15 dishes are auto-seeded on startup if the `dishes` table is empty.
- **AI tips** (`/tip` command): Uses **Ollama** running locally at `http://localhost:11434`. The code uses `AsyncOpenAI` which is compatible with Ollama's `/v1` endpoint. Configured via Groq env vars: `GROQ_API_KEY=ollama`, `GROQ_BASE_URL=http://localhost:11434/v1`, `GROQ_MODEL=llama3`. Ollama must be running on the host for `/tip` to work. Gracefully degrades with a user-friendly message if no keys are set.
- **No test suite**: The repo has no automated tests. Verify changes by running `python bot.py` with a valid `BOT_TOKEN` and testing commands in Telegram.
- **Lint**: Run `ruff check .` for linting. There is one pre-existing unused import warning in `app/middlewares/db.py`. Run `pyright .` for type checking (pre-existing type errors exist due to aiogram nullable `from_user` patterns).
- **No Docker/Makefile/CI**: Single-process app, no build step.

### Environment variables (see `.env.example`)

| Variable | Required | Default |
|---|---|---|
| `BOT_TOKEN` | Yes | — |
| `GROQ_API_KEY` | No | — |
| `OPENAI_API_KEY` | No | — |
| `DATABASE_URL` | No | SQLite at `./data/healthy_food.db` |
