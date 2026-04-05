# healthy-food-bot

Telegram bot for healthy meal ordering, nutrition tracking, and lifestyle support.

## MVP функции

- онбординг (цели, ограничения)
- каталог еды
- заказ наборов
- инструкции приготовления
- дневник питания
- напоминания

## команды

/start – старт
/onboarding – настройка профиля
/menu – меню
/order – оформить заказ для клиента
/tip – ИИ-совет по питанию
/remind – добавить напоминание
/reminders – список напоминаний
/timezone – часовой пояс для напоминаний

## запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Заполни `BOT_TOKEN` в `.env`, затем запусти:

```bash
python bot.py
```

Если у тебя Homebrew Python на macOS, не ставь зависимости через системный `python3 -m pip install ...`: используй виртуальное окружение.
