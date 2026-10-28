# Структура проекта после рефакторинга

## Организация utils/

```
utils/
├── common/                      # Общие утилиты
│   ├── __init__.py
│   ├── commands.py             # Команды бота и меню
│   ├── filters.py              # Фильтры для роутеров
│   └── messaging.py            # Отправка и редактирование сообщений
│
├── schedule/                    # Модуль расписания занятий
│   ├── __init__.py
│   ├── schedule_logic.py       # Парсинг, форматирование, логика
│   ├── schedule_render.py      # Рендеринг rich-сообщений
│   └── schedule_views.py       # Публичные представления
│
├── replacements/                # Модуль замен расписания
│   ├── __init__.py
│   ├── replacements_logic.py   # Логика обработки замен
│   ├── replacements_render.py  # Рендеринг rich-сообщений
│   ├── replacements_cache.py   # Кэширование данных
│   ├── replacements_service.py # Сервис уведомлений
│   └── replacements_source.py  # Источник данных (shapt.ru)
│
├── __init__.py
└── panels.py                    # Панели администратора
```

## Настройка emoji через .env

Все иконки теперь настраиваются через переменные окружения:

```bash
# Основные иконки
ICON_BELLS=5242628160297641831          # 🔔 Звонки
ICON_LESSONS=5373098009640836781        # 📚 Занятия
ICON_SETTINGS=5818705028424141605       # ⚙️ Настройки
ICON_REPLACEMENTS=5264727218734524899   # 🔄 Замены
ICON_CALENDAR=5431897022456145283       # 📆 Календарь
ICON_TIME=5451732530048802485           # ⏳ Время
ICON_WARNING=5213181173026533794        # ⚠️ Предупреждение

# Иконки действий
ICON_EDIT=5334673106202010226           # ✏️ Редактирование
ICON_CANCEL=5834629976883732083         # ❌ Отмена
ICON_DISABLE=5244807637157029775        # 🚫 Отключить
ICON_PANEL=5449428597922079323          # 🧰 Панель

# Иконки изменений (опционально)
ICON_ADDED=                             # ➕ Добавлено
ICON_REMOVED=                           # ➖ Удалено
ICON_CHANGED=5334673106202010226        # ✏️ Изменено
```

## Использование в коде

### Импорты

```python
# Было
from utils import schedule_logic as lg
from utils.messaging import send_html

# Стало
from utils.schedule.schedule_logic import week_parity, UPPER, LOWER
from utils.common.messaging import send_html
```

### Emoji в HTML

```python
from config import config

# HTML сообщения (для fallback)
html = f"<tg-emoji emoji-id=\"{config.icons['bells']}\">🔔</tg-emoji> Расписание звонков"
```

### Emoji в Rich Messages

```python
from aiogram.types import RichTextCustomEmoji
from config import config

# Rich сообщения (для правильного отображения)
rich_title = [
    RichTextCustomEmoji(
        custom_emoji_id=config.icons['bells'], 
        alternative_text="🔔"
    ), 
    " Расписание звонков"
]
```

## Статистика

- **Файлов Python в utils/**: 16
- **Использований config.icons**: 31+
- **Подмодулей**: 3 (common, schedule, replacements)
- **Настраиваемых иконок**: 14

## Преимущества

1. **Модульность** - чёткое разделение по функциональности
2. **Настраиваемость** - все иконки через .env
3. **Корректность** - правильное отображение rich messages
4. **Читаемость** - явные импорты
5. **Масштабируемость** - легко расширять
