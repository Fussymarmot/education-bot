# Быстрый старт после рефакторинга

## Что изменилось

### Структура utils/ теперь организована:
```
utils/
├── common/          # Общие утилиты
├── schedule/        # Расписание
├── replacements/    # Замены
└── panels.py
```

### Все emoji теперь в конфиге

В `.env` файле можно настроить любые иконки:
```bash
ICON_BELLS=5242628160297641831
ICON_LESSONS=5373098009640836781
# ... и ещё 12 иконок
```

## Запуск бота

1. **Проверьте .env файл**
   ```bash
   cp .env.example .env
   # Отредактируйте .env, добавьте BOT_TOKEN и другие параметры
   ```

2. **Запустите бота**
   ```bash
   python main.py
   ```

## Миграция тестов

Если у вас есть тесты, обновите импорты:

**Было:**
```python
from utils import schedule_logic as lg
from utils.messaging import send_html
```

**Стало:**
```python
from utils.schedule.schedule_logic import week_parity, UPPER
from utils.common.messaging import send_html
```

## Частые вопросы

**Q: Нужно ли что-то менять в базе данных?**  
A: Нет, структура БД не изменилась.

**Q: Как изменить иконки?**  
A: Отредактируйте соответствующие `ICON_*` переменные в `.env`

**Q: Работает ли старая версия aiogram?**  
A: Да, есть HTML fallback для старых версий без rich messages.

**Q: Что делать, если бот не запускается?**  
A: Проверьте, что все зависимости установлены:
```bash
pip install -r requirements.txt
```

## Документация

- `REFACTORING_SUMMARY.md` - подробная сводка изменений
- `STRUCTURE.md` - документация новой структуры
- `.env.example` - пример конфигурации

## Проверка

Быстрая проверка, что всё работает:
```bash
python3 -c "from handlers import admin, users; print('✅ OK')"
```
