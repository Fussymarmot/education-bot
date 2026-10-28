# Сводка рефакторинга

## Выполненные изменения

### 1. Организация структуры utils/

Утилиты разделены на логические подпапки:

```
utils/
├── __init__.py
├── panels.py                    # Панели администратора (остались в корне)
├── common/                      # Общие утилиты
│   ├── __init__.py
│   ├── commands.py             # Команды бота
│   ├── filters.py              # Фильтры для роутеров
│   └── messaging.py            # Отправка и редактирование сообщений
├── schedule/                    # Утилиты расписания
│   ├── __init__.py
│   ├── schedule_logic.py       # Логика парсинга и форматирования
│   ├── schedule_render.py      # Рендеринг rich-сообщений
│   └── schedule_views.py       # Представления (звонки, день, неделя)
└── replacements/                # Утилиты замен
    ├── __init__.py
    ├── replacements_cache.py   # Кэширование
    ├── replacements_logic.py   # Логика обработки
    ├── replacements_render.py  # Рендеринг
    ├── replacements_service.py # Сервис уведомлений
    └── replacements_source.py  # Источник данных (shapt.ru)
```

### 2. Вынос emoji в конфигурацию

Все захардкоженные emoji ID перенесены в `config.py`:

**Было:**
```python
title = "<tg-emoji emoji-id='5242628160297641831'>🔔</tg-emoji> Расписание звонков"
```

**Стало:**
```python
html_title = f"<tg-emoji emoji-id=\"{config.icons['bells']}\">🔔</tg-emoji> {title}"
```

Все emoji настраиваются через переменные окружения в `.env`:
- `ICON_BELLS` - звонки
- `ICON_LESSONS` - занятия
- `ICON_SETTINGS` - настройки
- `ICON_REPLACEMENTS` - замены
- `ICON_EDIT` - редактирование
- `ICON_CANCEL` - отмена
- `ICON_DISABLE` - отключение
- `ICON_PANEL` - панель
- `ICON_CALENDAR` - календарь
- `ICON_TIME` - время
- `ICON_WARNING` - предупреждение
- `ICON_ADDED` - добавлено
- `ICON_REMOVED` - удалено
- `ICON_CHANGED` - изменено

### 3. Исправление отображения rich messages

**Проблема:** Rich messages использовали HTML-теги `<tg-emoji>` внутри rich-блоков, что не поддерживается.

**Решение:** Добавлено использование `RichTextCustomEmoji` для emoji в rich-сообщениях:

```python
from aiogram.types import RichTextCustomEmoji

# Для rich-сообщений
rich_title = [
    RichTextCustomEmoji(custom_emoji_id=config.icons["bells"], alternative_text="🔔"), 
    " Расписание звонков"
]

# Для HTML-fallback
html_title = f"<tg-emoji emoji-id=\"{config.icons['bells']}\">🔔</tg-emoji> Расписание звонков"
```

### 4. Обновление импортов

Все файлы обновлены для использования новой структуры:

**Было:**
```python
from utils import schedule_logic as lg
from utils.messaging import send_html
```

**Стало:**
```python
from utils.schedule.schedule_logic import week_parity, UPPER, LOWER
from utils.common.messaging import send_html
```

## Изменённые файлы

### Handlers
- `handlers/admin.py` - обновлены импорты
- `handlers/users.py` - обновлены импорты
- `handlers/start.py` - обновлены импорты

### Keyboards
- `keyboards/admin.py` - обновлены импорты, добавлена функция main_menu
- `keyboards/users.py` - обновлены импорты

### Utils
- `utils/panels.py` - обновлены импорты
- `utils/schedule/schedule_render.py` - исправлены rich messages
- `utils/schedule/schedule_views.py` - обновлены импорты
- `utils/replacements/replacements_render.py` - исправлены rich messages
- `utils/replacements/replacements_service.py` - обновлены импорты
- `utils/common/commands.py` - добавлены экспорты PUBLIC и admin_commands()

### Конфигурация
- `config.py` - все emoji ID вынесены в словарь icons
- `.env.example` - добавлены все переменные для настройки emoji

## Преимущества рефакторинга

1. **Лучшая организация кода** - утилиты логически сгруппированы по функциональности
2. **Упрощённая настройка** - все emoji настраиваются через .env без изменения кода
3. **Корректное отображение** - rich messages теперь корректно отображают emoji
4. **Улучшенная читаемость** - явные импорты вместо псевдонимов модулей
5. **Масштабируемость** - легко добавлять новые утилиты в соответствующие папки

## Проверка работоспособности

Все модули успешно импортируются без ошибок. Бот готов к запуску.
