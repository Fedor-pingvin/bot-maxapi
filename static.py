import sqlite3
import datetime
import matplotlib.pyplot as plt
import pandas as pd
from collections import defaultdict
import database 
import os

CONSOLE_BAR_WIDTH = 5

def display_console_graph(user_id):
    stats = database.get_user_statistics(user_id)
    chart_data = {
        "Сделано": stats['done'],
        "В работе": stats['in_progress'],
        "Просрочено": stats['overdue']
    }
    # Исключаем нулевые значения из расчета масштаба
    values_ = [v for v in chart_data.values() if v > 0]

    if not values_:
        return "Нет данных для отображения."

    max_value = max(values_)

    # Расчет масштаба
    # (обработка деления на ноль, если max_value = 0)
    scale = CONSOLE_BAR_WIDTH / max_value if max_value > 0 else 0

    msg = ''
    # Отрисовка
    for label, value in chart_data.items():
        # Рассчитываем длину полосы
        bar_length = int(value * scale)
        # Создаем "тело" полосы
        bar = '█' * bar_length
        # Вывод: Метка | График | Значение
        msg += f"{label:<12} | {bar} {value}\n"
    return msg


'''def display_activity_timeline(user_id):
    stats = database.get_user_statistics(user_id)
    # Готовим данные
    chart_data = {
        "Сделано": stats.get('done', 0),
        "В работе": stats.get('in_progress', 0),
        "Просрочено": stats.get('overdue', 0),
    }
    categories = list(chart_data.keys())
    values = list(chart_data.values())

    # Проверка пустых данных
    if not any(v > 0 for v in values):
        return None

    # Рисуем bar chart
    plt.figure(figsize=(6, 4), dpi=150)
    bars = plt.bar(categories, values, color=["#2ecc71", "#f1c40f", "#e74c3c"])
    plt.title("Статистика задач")
    plt.ylabel("Количество")
    plt.grid(axis="y", linestyle="--", alpha=0.3)

    # Подписи над столбцами
    for b in bars:
        h = b.get_height()
        plt.text(b.get_x() + b.get_width()/2, h + 0.05, str(int(h)),
                 ha="center", va="bottom", fontsize=9)


    folder_path = 'pictures'

    # Создаем папку, если ее нет
    os.makedirs(folder_path, exist_ok=True)
    # Формируем полный путь к файлу
    filename = os.path.join(folder_path, f"statistics_{user_id}.png")


    plt.tight_layout()
    plt.savefig(filename, format="png")
    plt.close()
    return filename  
'''
