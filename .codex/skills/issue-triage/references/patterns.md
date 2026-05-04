# Triage Patterns

## Частые сценарии

- `@bot дай список открытых issue`
  - список existing issues по статусу
- `@bot найди issue про логин`
  - текстовый поиск existing issues
- `@bot закрой #42`
  - действие над существующим issue
- reply на preview + `@bot approve`
  - создание issue по уже готовому preview
- `@bot тут надо сделать ...`
  - обычно новый issue preview

## Что особенно проверять

- не перехватывает ли сообщение более ранняя ветка
- правильно ли очищается текст от служебных слов
- где должен сработать deterministic-path, а где LLM classifier
