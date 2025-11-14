import re
from datetime import datetime, date

# Шаблон даты: d.m, d-m, d/m, опционально с годом d.m.yyyy
DATE_RE = re.compile(r'(?<!\d)(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{2,4}))?(?!\d)')

def parse_task_item(item: str):
    # Разбор времени по вашей логике
    parts = item.rsplit(' ', 1)
    if len(parts) == 2 and ':' in parts[1]:
        task_name, time_str = parts
    else:
        task_name = item
        time_str = ""

    # Значение по умолчанию — сегодня в формате YYYY-MM-DD
    due_date = datetime.now().strftime('%Y-%m-%d')

    # Пытаемся найти дату в тексте задачи
    m = DATE_RE.search(task_name)
    if m:
        day = int(m.group(1))
        month = int(m.group(2))
        year_str = m.group(3)
        if year_str:
            year = int(year_str)
            if year < 100:  # поддержка кратких годов типа 25 -> 2025
                year += 2000
        else:
            year = datetime.now().year  # если год не указан — текущий

        try:
            dt = datetime(year, month, day)
            # Формируем строку без ведущих нулей для месяца/дня: YYYY-M-D
            due_date = f"{dt.year}-{dt.month}-{dt.day}"
            # Удаляем найденный фрагмент даты из названия задачи
            task_name = (task_name[:m.start()] + task_name[m.end():]).strip()
        except ValueError:
            # Невалидная дата — оставляем due_date по умолчанию
            pass

    return task_name, time_str, due_date


def to_date_safe(d):
    # уже date без времени
    if isinstance(d, date) and not isinstance(d, datetime):
        return d
    # datetime -> date
    if isinstance(d, datetime):
        return d.date()
    # строка -> нормализованный ISO YYYY-MM-DD
    if isinstance(d, str):
        s = d.strip()
        parts = s.split('-')
        if len(parts) == 3 and all(parts):
            y, m, day = parts[0], parts[1].zfill(2), parts[2].zfill(2)
            return date.fromisoformat(f"{y}-{m}-{day}")  # строгий ISO после нормализации
        # если формат иной — попробуем строгий шаблон (ожидает уже нули)
        return datetime.strptime(s, "%Y-%m-%d").date()
    raise ValueError(f"Unsupported date value: {d!r}")