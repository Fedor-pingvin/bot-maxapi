# bot-maxapi
A hackathon bot from the Max messenger in Python using the maxapi library

# Запуск 

## Быстрый старт локально (Windows/Linux/MacOS)

### 1. Склонируйте репозиторий, перейди в папку с проектом

```bash
cd /путь/к/проекту
```

Внутри должны лежать:
- main.py
- requirements.txt
- Dockerfile
- все вспомогательные .py
- база (например, basic_base.db)
- и другие необходимые файлы.

### 2. Проверь файл requirements.txt

Файл должен содержать только сторонние библиотеки:

```
maxapi
aiohttp
matplotlib     
pandas
dotenv        
```

### 3. Сборка Docker-образа

Команда для сборки:

```bash
docker build -t max-bot .
```

- `-t max-bot` — имя образа
- `.` — использовать текущую директорию как контекст сборки

### 4. Запуск контейнера

Если бот требует токен Max (или другой секрет), передавай его через переменную окружения:

```bash
docker run --rm -e BOT_TOKEN=секретный_токен max-bot
```

- `--rm` — контейнер автоматически удаляется после остановки
- `-e` — передача переменных окружения
- `max-bot` — имя образа

### 5. Пример запуска из командной строки (Windows)

Открой **PowerShell** или **CMD** в папке с проектом и выполни:

```powershell
docker build -t max-bot .
docker run --rm -e MAX_BOT_TOKEN=ТОКЕН max-bot
```

### 6. Остановка контейнера

- Нажми `Ctrl + C` — контейнер завершит работу.
- Либо в отдельном терминале введи (если запуск без `--rm`):

```bash
docker ps    # получи имя или id контейнера
docker stop ИМЯ_ИЛИ_ID
```

### 7. Обновление зависимостей

Если добавил новые зависимости — отредактируй файл requirements.txt и пересобери образ через `docker build ...`.

***

## Запуск без Docker (альтернатива)

Если хочешь запустить проект локально без контейнера:

```bash
python -m venv venv
source venv/bin/activate    # или venv\Scripts\activate на Windows
pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

***

## Технические требования

- Docker 20+ (Desktop или CLI)
- Python 3.13 (для локального запуска)
- Max API токен (для работы бота)

