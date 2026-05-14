# Git Commands

Этот файл нужен как короткая памятка по синхронизации проекта с репозиториями.

## Текущие remote

- `github` -> `https://github.com/YauhenThreeE/healthy-food-bot1.git`
- `origin` -> `https://gitlab.com/eugene3e/healthy-food-bot1.git`

## Проверить состояние

```bash
git status
git branch
git remote -v
```

## Подтянуть изменения

С GitHub:

```bash
git pull github main
```

С GitLab:

```bash
git pull origin main
```

## Подготовить и закоммитить изменения

Добавить все изменения:

```bash
git add .
git commit -m "your commit message"
```

Добавить только выбранные файлы:

```bash
git add bot.py app/ data/
git commit -m "your commit message"
```

## Отправить изменения

На GitHub:

```bash
git push github main
```

На GitLab:

```bash
git push origin main
```

Сразу в оба репозитория:

```bash
git push github main
git push origin main
```

## Полная рабочая последовательность

```bash
git status
git add .
git commit -m "update project"
git push github main
git push origin main
```

## Если нужно сначала забрать изменения

```bash
git pull github main
git pull origin main
git add .
git commit -m "update project"
git push github main
git push origin main
```

## Если появился конфликт

Посмотреть конфликтующие файлы:

```bash
git status
```

После ручного исправления:

```bash
git add .
git commit -m "resolve merge conflicts"
git push github main
git push origin main
```

## Полезные команды

История коммитов:

```bash
git log --oneline --decorate --graph -20
```

Что изменилось:

```bash
git diff
```

Что уже подготовлено к коммиту:

```bash
git diff --cached
```
