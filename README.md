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
/survey – короткий опрос по питанию
/menu – меню
/order – оформить заказ для клиента
/tip – ИИ-совет по питанию
/log_food – логирование еды (пример: `/log_food курица 200 г`)
/log_meal – alias для логирования еды
/today – дневная сводка КБЖУ, клетчатки, воды, витаминов
/advice – рекомендации по рациону за день
/parse_meal – разбор свободного текстового описания еды
/remember – сохранить факт в AI памяти (`/remember key=value`)
/remind – добавить напоминание
/reminders – список напоминаний
/timezone – часовой пояс для напоминаний

## Что добавлено в архитектуру

- Новые таблицы: `products`, `meal_logs`, `daily_summary`, `ai_memory`, `conversations`.
- Расширены `users` и `dishes` для nutrition-ready полей и daily targets.
- В `init_db()` добавлена безопасная additive-миграция для SQLite (без Alembic): новые таблицы создаются через `create_all`, недостающие колонки в legacy-таблицах добавляются через `ALTER TABLE`.
- Добавлены сервисы: расчет таргетов, парсинг meal text, логирование приемов пищи, агрегация дневной сводки, AI-memory и conversation log.

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
