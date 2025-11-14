import sqlite3
from datetime import datetime, date


DB_FILENAME = 'basic_base.db'


# Функция для создания базы данных и таблицы задач
def create_database():
    conn = sqlite3.connect('basic_base.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            user_name TEXT,
            task TEXT NOT NULL,
            status TEXT CHECK(status IN ('в работе', 'выполнена', 'просрочена')),
            time TEXT,
            due_date TEXT, 
            flag BOOL NOT NULL DEFAULT TRUE, 
            flag_del INTEGER NOT NULL DEFAULT 1 )
    ''')

    conn.commit()
    conn.close()

# Функция для добавления задачи в базу
def add_task(user_id, user_name, chat_id, task, status, time, due_date):
    conn = sqlite3.connect('basic_base.db')
    cursor = conn.cursor()

    cursor.execute('INSERT INTO tasks (user_id, user_name, chat_id, task, status, time, due_date) VALUES (?, ?, ?, ?, ?,?, ?)',
                   (user_id, user_name, chat_id, task, status, time, due_date))

    conn.commit()
    conn.close()




def update_overdue_tasks():
    conn = sqlite3.connect('basic_base.db')
    cursor = conn.cursor()

    today = datetime.today().date()

    # Выбираем задачи, у которых дата меньше сегодняшней и статус не выполнена
    cursor.execute('''
        SELECT id, due_date, status FROM tasks
        WHERE status != 'выполнена'
    ''')

    tasks = cursor.fetchall()

    for task_id, due_date_str, status in tasks:
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        if due_date < today:
            # Обновляем статус на 'просрочена'
            cursor.execute('''
                UPDATE tasks SET status = 'просрочена' WHERE id = ?
            ''', (task_id,))

    conn.commit()
    conn.close()


def get_tasks_by_user(user_id):
    conn = sqlite3.connect(DB_FILENAME)  
    cursor = conn.cursor()
    cursor.execute('''
        SELECT task, status, time, due_date FROM tasks
        WHERE user_id = ? AND flag_del = 1 AND flag = TRUE
        ORDER BY due_date, time
    ''', (user_id,))
    tasks = cursor.fetchall()
    conn.close()
    return tasks


def get_active_users_for_reminders():
    conn = sqlite3.connect(DB_FILENAME)  
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT user_id, chat_id 
            FROM tasks
        """)
        active_users = cursor.fetchall()
        return active_users
    except sqlite3.Error as e:
        print(f"Ошибка при работе с базой данных: {e}")
        active_users = []
    finally:
        conn.close()


def get_user_statistics(user_id):
    """
    Рассчитывает статистику задач для конкретного пользователя.
    Возвращает словарь с метриками.
    """
    conn = sqlite3.connect(DB_FILENAME)
    cursor = conn.cursor()
    today_iso = date.today().isoformat()

    stats = {}

    try:
        # 1. Задач сделано (status = 'done')
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ? AND status = 'сделана' AND flag_del != 0", (user_id,))
        stats['done'] = cursor.fetchone()[0]

        # 2. Задач в работе (status = 'in_progress')
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE user_id = ? AND status = 'в работе' AND flag_del != 0", (user_id,))
        stats['in_progress'] = cursor.fetchone()[0]

        # 3. Задач просрочено
        # Просроченная задача - это любая задача, которая НЕ 'done'
        # и чья дата 'due_date' < сегодняшней даты.
        cursor.execute(
            "SELECT COUNT(*) FROM tasks WHERE user_id = ? AND status = 'просрочена' AND due_date < ? AND flag_del != 0",
            (user_id, today_iso)
        )
        stats['overdue'] = cursor.fetchone()[0]

    except Error as e:
        print(f"[ОШИБКА] При расчете статистики: {e}")
        return None

    return stats

def get_all_tasks_by_user(user_id):
    conn = sqlite3.connect(DB_FILENAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, task, status, time, due_date 
        FROM tasks  
        WHERE user_id = ? AND flag_del = 1 AND flag= TRUE''', (user_id,))
    tasks = cursor.fetchall()
    conn.close()
    return tasks

# Получить активные задачи (исключая выполненные)
def get_active_tasks_by_user(user_id):
    conn = sqlite3.connect(DB_FILENAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, task, status, time, due_date, flag
        FROM tasks
        WHERE user_id = ? AND status != 'выполнена' AND flag_del = 1 AND flag = TRUE
        ORDER BY due_date, time
    ''', (user_id,))
    tasks = cursor.fetchall()
    conn.close()
    return tasks

# Отметить задачу как выполненную
def mark_task_completed(task_id):
    conn = sqlite3.connect(DB_FILENAME)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE tasks 
        SET status = 'выполнена' 
        WHERE id = ?
    ''', (task_id,))
    conn.commit()
    conn.close()


def delete_f(user_id):
    conn = sqlite3.connect(DB_FILENAME)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE tasks
            SET flag_del = 1
            WHERE user_id = ? AND flag_del = 0
         ''', (user_id,))
        conn.commit()
        return cursor.rowcount
    except Exception as e:
        print(f"Ошибка при скрытии планов: {e}")
        return 0
    finally:
        conn.close()

# Удалить задачу физически (опционально)
def delete_task(task_id):
    conn = sqlite3.connect(DB_FILENAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()

# Получить одну задачу по ID
def get_task_by_id(task_id):
    conn = sqlite3.connect(DB_FILENAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id, task, status, time, due_date FROM tasks WHERE id = ? AND flag_del != 0', (task_id,))
    task = cursor.fetchone()
    conn.close()
    return task


def hide_overdue_tasks(user_id):
    """Скрыть просроченные задачи пользователя (установить flag=False)"""
    conn = sqlite3.connect(DB_FILENAME)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE tasks 
            SET flag = 0 
            WHERE user_id = ? AND status = 'просрочена'
        ''', (user_id,))
        hidden_count = cursor.rowcount
        conn.commit()
        return hidden_count
    except sqlite3.Error as e:
        print(f"Ошибка при скрытии просроченных задач: {e}")
        return 0
    finally:
        conn.close()


def check_has_overdue_tasks(user_id):
    """Проверить, есть ли у пользователя видимые просроченные задачи"""
    conn = sqlite3.connect(DB_FILENAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) FROM tasks 
        WHERE user_id = ? AND status = 'просрочена' AND flag = 1
    ''', (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0


def show_hidden_tasks(user_id):
    """Показать все скрытые задачи (flag=False -> flag=True)"""
    conn = sqlite3.connect(DB_FILENAME)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE tasks 
            SET flag = 1 
            WHERE user_id = ? AND flag = 0
        ''', (user_id,))
        shown_count = cursor.rowcount
        conn.commit()
        return shown_count
    except sqlite3.Error as e:
        print(f"Ошибка при показе скрытых задач: {e}")
        return 0
    finally:
        conn.close()


def mark_task_completed(task_id):
    """Отметить задачу как выполненную (изменить статус на 'выполнена')"""
    conn = sqlite3.connect(DB_FILENAME)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE tasks 
            SET status = 'выполнена' 
            WHERE id = ?
        ''', (task_id,))
        conn.commit()
        return cursor.rowcount  # возвращаем количество обновлённых строк
    except sqlite3.Error as e:
        print(f"Ошибка при обновлении статуса задачи: {e}")
        return 0
    finally:
        conn.close()


def create_database_note():
    conn = sqlite3.connect('note_base.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            user_name TEXT,
            note TEXT NOT NULL,
            flag INTEGER NOT NULL DEFAULT 1)
    ''')

    conn.commit()
    conn.close()


def add_task_note(user_id, user_name, chat_id, note, flag):
    conn = sqlite3.connect('note_base.db')
    cursor = conn.cursor()

    cursor.execute('INSERT INTO notes (user_id, user_name, chat_id, note, flag) VALUES (?, ?, ?, ?, ?)',
                   (user_id, user_name, chat_id, note, flag))

    conn.commit()
    conn.close()


def get_tasks_by_user_note(user_id):
    conn = sqlite3.connect('note_base.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT note
        FROM notes
        WHERE user_id = ? AND flag = 1
    ''', (user_id,))
    tasks = cursor.fetchall()
    conn.close()
    return tasks


def update_note_text(user_id: int, note_id: int, new_text: str) -> int:
    conn = sqlite3.connect('note_base.db')
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE notes
            SET note = ?
            WHERE id = ? AND user_id = ? AND flag = 1
        ''', (new_text, note_id, user_id))
        conn.commit()
        return cursor.rowcount
    except Exception as e:
        print(f"Ошибка при обновлении заметки: {e}")
        return 0
    finally:
        conn.close()



def del_f(user_id: int, note_id: int = None):
    conn = sqlite3.connect('note_base.db')
    cursor = conn.cursor()
    try:
        if note_id:
            cursor.execute('''
                UPDATE notes
                SET flag = 0
                WHERE user_id = ? AND id = ? AND flag = 1
            ''', (user_id, note_id))
        else:
            cursor.execute('''
                UPDATE notes
                SET flag = 0
                WHERE user_id = ? AND flag = 1
            ''', (user_id,))
        conn.commit()
        return cursor.rowcount
    except Exception as e:
        print(f"Ошибка при скрытии заметки: {e}")
        return 0
    finally:
        conn.close()



def delete_note(user_id: int, note_id: int = None):
    conn = sqlite3.connect('note_base.db')
    cursor = conn.cursor()
    
    try:
        if note_id:
            # Удаляем конкретную заметку по ID
            cursor.execute('''
                DELETE FROM notes 
                WHERE user_id = ? AND id = ?
            ''', (user_id, note_id))
        else:
            # Удаляем все заметки пользователя
            cursor.execute('''
                DELETE FROM notes 
                WHERE user_id = ?
            ''', (user_id,))
        
        conn.commit()
        deleted_count = cursor.rowcount
        conn.close()
        
        return deleted_count  # Возвращаем количество удаленных записей
        
    except Exception as e:
        conn.close()
        print(f"Ошибка при удалении заметки: {e}")
        return 0

def get_notes_with_ids(user_id: int):
    conn = sqlite3.connect('note_base.db')
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, note, flag FROM notes WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        return rows  # [(id, note), ...]
    finally:
        conn.close()