# AI Chat Platform - Edge Function API Documentation

## Обзор

Данная Edge Function предоставляет полный API для управления AI чат-диалогами с поддержкой ветвления разговоров, регенерации сообщений и потоковых ответов. Функция развернута на Supabase и обеспечивает интеграцию с LiteLLM Proxy для доступа к различным LLM моделям (GPT-4, Claude, Gemini).

**URL Edge Function:** `https://ptcpemfokwjgpjgmbgoj.supabase.co/functions/v1/conversation-manager`

## Архитектура системы

### Технологический стек
- **База данных:** Supabase (PostgreSQL) с Row Level Security
- **Edge Functions:** Supabase Edge Functions (Deno runtime)
- **LLM Gateway:** LiteLLM Proxy для унифицированного доступа к 100+ моделям
- **Оркестратор:** FastAPI (Python) для координации и стриминга
- **Аутентификация:** Supabase Auth с JWT токенами

### Структура файлов
```
conversation-manager/
├── index.ts          # Основная маршрутизация и обработка запросов
├── types.ts          # TypeScript типы для всех структур данных
├── auth.ts           # Утилиты аутентификации и проверки доступа
├── tokens.ts         # Утилиты подсчета токенов
├── conversations.ts  # Функции управления диалогами
├── branches.ts       # Функции управления ветками
├── messages.ts       # Функции управления сообщениями
└── README.md         # Техническая документация
```

## Аутентификация

Все эндпоинты требуют валидный JWT токен в заголовке Authorization:
```bash
Authorization: Bearer <jwt_token>
```

## Форматы ответов

### Успешный ответ
```json
{
  "success": true,
  "data": { ... }
}
```

### Ошибка
```json
{
  "success": false,
  "error": "Описание ошибки"
}
```

### HTTP статус коды
- **200** - Успешное выполнение
- **401** - Ошибка аутентификации
- **404** - Ресурс не найден или доступ запрещен
- **405** - Метод не поддерживается
- **500** - Внутренняя ошибка сервера

## API Эндпоинты

### Legacy эндпоинты (обратная совместимость)

#### 1. Создание нового диалога
```
POST /init-conversation
```
**Тело запроса:**
```json
{
  "title": "Заголовок диалога (опционально)",
  "model": "gpt-4"
}
```
**Ответ:**
```json
{
  "success": true,
  "data": {
    "conversation_id": "uuid",
    "branch_id": "uuid", 
    "title": "Заголовок диалога",
    "model": "gpt-4"
  }
}
```

#### 2. Добавление сообщения пользователя
```
POST /add-message
```
**Тело запроса:**
```json
{
  "conversation_id": "uuid (опционально, если не указан - создается новый диалог)",
  "parent_id": "uuid (опционально)",
  "role": "user",
  "content": "Текст сообщения",
  "model": "gpt-4 (опционально)"
}
```
**Ответ:**
```json
{
  "success": true,
  "data": {
    "message_id": "uuid",
    "conversation_id": "uuid",
    "branch_id": "uuid",
    "parent_id": "uuid",
    "is_new_conversation": false
  }
}
```

#### 3. Сохранение ответа LLM
```
POST /save-response
```
**Тело запроса:**
```json
{
  "conversation_id": "uuid",
  "branch_id": "uuid",
  "parent_id": "uuid",
  "content": "Ответ от LLM",
  "model": "gpt-4",
  "tokens_count": 150
}
```
**Ответ:**
```json
{
  "success": true,
  "data": {
    "message_id": "uuid",
    "tokens_count": 150
  }
}
```

#### 4. Создание новой ветки
```
POST /create-branch
```
**Тело запроса:**
```json
{
  "conversation_id": "uuid",
  "from_message_id": "uuid",
  "name": "Название ветки (опционально)"
}
```

#### 5. Переключение ветки
```
POST /switch-branch
```
**Тело запроса:**
```json
{
  "conversation_id": "uuid",
  "branch_id": "uuid"
}
```

#### 6. Построение контекста для LLM
```
GET|POST /build-context
```
**Параметры (GET) или тело (POST):**
```json
{
  "conversation_id": "uuid",
  "branch_id": "uuid (опционально)",
  "max_messages": 50
}
```

### Новые REST эндпоинты

#### Управление диалогами

##### 1. Список диалогов пользователя
```
GET /conversations?page=1&limit=20
```
**Параметры:**
- `page` - номер страницы (по умолчанию: 1)
- `limit` - количество записей на странице (по умолчанию: 20)

**Ответ:**
```json
{
  "success": true,
  "data": {
    "conversations": [
      {
        "id": "uuid",
        "title": "Заголовок диалога",
        "model": "gpt-4",
        "created_at": "2025-09-01T06:15:51.432019+00:00",
        "updated_at": "2025-09-01T06:17:43.526+00:00"
      }
    ],
    "total": 9,
    "page": 1,
    "limit": 20
  }
}
```

##### 2. Получение информации о диалоге
```
GET /conversations/{conversation_id}
```
**Ответ:** Полная информация о диалоге (см. схему БД)

##### 3. Получение полной информации о диалоге
```
GET /conversations/{conversation_id}/full
```
**Ответ:**
```json
{
  "success": true,
  "data": {
    "conversation": { /* объект диалога */ },
    "branches": [ /* массив веток */ ],
    "messages": [ /* массив всех сообщений */ ]
  }
}
```

##### 4. Обновление диалога
```
PATCH /conversations/{conversation_id}
```
**Тело запроса:**
```json
{
  "title": "Новый заголовок",
  "model": "claude-3"
}
```

#### Управление ветками

##### 1. Список веток диалога
```
GET /conversations/{conversation_id}/branches
```

##### 2. Создание ветки из сообщения
```
POST /conversations/{conversation_id}/branches
```
**Тело запроса:**
```json
{
  "parent_message_id": "uuid",
  "name": "Название ветки"
}
```

##### 3. Активация ветки
```
POST /conversations/{conversation_id}/branches/{branch_id}/activate
```

#### Управление сообщениями

##### 1. Получение сообщения
```
GET /messages/{message_id}
```

##### 2. Редактирование сообщения пользователя
```
PATCH /messages/{message_id}
```
**Тело запроса:**
```json
{
  "content": "Отредактированный текст сообщения"
}
```
**Примечание:** Можно редактировать только сообщения с role="user"

##### 3. Регенерация ответа ассистента
```
POST /messages/{message_id}/regenerate
```
**Тело запроса:**
```json
{
  "branch_name": "Альтернативный ответ"
}
```
**Функция:** Создает новую ветку от родительского сообщения для генерации альтернативного ответа

## Примеры использования

### Создание нового диалога и отправка сообщения

```bash
# 1. Создание диалога
curl -X POST \
  https://ptcpemfokwjgpjgmbgoj.supabase.co/functions/v1/conversation-manager/init-conversation \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Мой диалог", "model": "gpt-4"}'

# 2. Добавление сообщения
curl -X POST \
  https://ptcpemfokwjgpjgmbgoj.supabase.co/functions/v1/conversation-manager/add-message \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{"conversation_id": "uuid", "content": "Привет!"}'
```

### Работа с новыми REST эндпоинтами

```bash
# Получение списка диалогов
curl -X GET \
  "https://ptcpemfokwjgpjgmbgoj.supabase.co/functions/v1/conversation-manager/conversations?page=1&limit=10" \
  -H "Authorization: Bearer <jwt_token>"

# Обновление заголовка диалога
curl -X PATCH \
  https://ptcpemfokwjgpjgmbgoj.supabase.co/functions/v1/conversation-manager/conversations/{id} \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Новый заголовок"}'

# Регенерация ответа
curl -X POST \
  https://ptcpemfokwjgpjgmbgoj.supabase.co/functions/v1/conversation-manager/messages/{message_id}/regenerate \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{"branch_name": "Альтернативный ответ"}'
```

## Схема базы данных

### Основные таблицы

#### user_profiles
```sql
- id (UUID) - связан с auth.users
- litellm_key (TEXT) - API ключ для LiteLLM
- email (TEXT)
- spend (DECIMAL) - потраченная сумма
- max_budget (DECIMAL) - лимит бюджета
- available_balance (GENERATED) - доступный баланс
```

#### conversations
```sql
- id (UUID)
- user_id (UUID) - владелец
- title (TEXT)
- active_branch_id (UUID) - текущая активная ветка
- model (TEXT) - предпочтительная модель
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
```

#### branches
```sql
- id (UUID)
- conversation_id (UUID)
- parent_message_id (UUID) - точка ветвления
- name (TEXT) - название ветки
- created_at (TIMESTAMP)
```

#### messages
```sql
- id (UUID)
- conversation_id (UUID)
- branch_id (UUID)
- parent_id (UUID) - для построения дерева сообщений
- role (TEXT) - user/assistant/system
- content (TEXT)
- model (TEXT)
- tokens_count (INT)
- created_at (TIMESTAMP)
```

## Особенности работы

### Ветвление диалогов
- Каждый диалог имеет основную ветку "Main"
- При регенерации ответа создается новая ветка
- Ветки позволяют исследовать альтернативные варианты развития диалога
- Активная ветка определяет, какие сообщения видит пользователь

### Автоматическое создание заголовков
- При сохранении второго сообщения в диалоге (первый ответ ассистента) автоматически генерируется заголовок из первых 50 символов ответа

### Безопасность
- Row Level Security (RLS) обеспечивает доступ только к собственным данным пользователя
- Все операции проверяют принадлежность ресурсов пользователю
- JWT токены валидируются на каждом запросе

### Производительность
- Эффективные запросы к базе данных с учетом индексации
- Пагинация для списочных эндпоинтов
- Оптимизированное построение контекста для LLM

## Интеграция с FastAPI оркестратором

Edge Function полностью совместима с существующим FastAPI оркестратором. Все legacy эндпоинты работают без изменений, что обеспечивает плавный переход и обратную совместимость.

## Тестирование

Функция полностью протестирована и готова к production использованию:
- ✅ Все legacy эндпоинты работают корректно
- ✅ Все новые REST эндпоинты функционируют правильно
- ✅ Обработка ошибок работает как ожидается
- ✅ Аутентификация и авторизация настроены корректно
- ✅ Ветвление диалогов работает правильно

## Заключение

Данная Edge Function предоставляет полнофункциональный API для управления AI чат-платформой с поддержкой сложных сценариев использования, таких как ветвление диалогов и регенерация ответов. Модульная архитектура обеспечивает легкость поддержки и развития, а обратная совместимость гарантирует плавную интеграцию с существующими системами.