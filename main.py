import asyncio
import logging
import maxapi
import maxapi.types as maxtypes
import sqlite3
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from maxapi.context import MemoryContext, State, StatesGroup
from datetime import datetime, timedelta, date, timezone
import re
import database, reminder_worker
import rt
import static
import aiohttp
import os
from typing import Optional
from dotenv import load_dotenv  # если используешь .env
import time

logging.basicConfig(level=logging.INFO)

load_dotenv()  # можно убрать, если не используешь .env

TOKEN = os.getenv("BOT_TOKEN")
if TOKEN is None:
    raise RuntimeError("BOT_TOKEN env var is not set")

bot = maxapi.Bot(TOKEN)
dp = maxapi.Dispatcher()
bot_start_time: datetime | None = None


@dp.bot_started()
async def bot_started(event: maxtypes.BotStarted):
    await event.bot.send_message(
    chat_id=event.chat_id,
    text=f"🚀 Привет, продуктивный гений! Я — твой личный 'анти-хаос' ассистент:  "
    "могу помочь тебе разложить задачи по полочкам, напомню о дедлайнах и даже подкину мотивацию, чтобы ты не унывал от большего количества дел."
    "Что планируем первым — список дел или тайм-блок на неделю? Давай завоюем этот день! 😎\nМои команды:\n/start\n/help\n/info"
 )



@dp.message_created(maxtypes.Command("start"))
async def start(event: maxtypes.MessageCreated):
    #await event.message.answer(f"Привет!")
    #print(event)
    buttons = [
        [maxtypes.CallbackButton(text="Создать список дел", payload="todo_list")],
        [maxtypes.CallbackButton(text="Посмотреть список дел", payload="view_plan_list")],
        [maxtypes.CallbackButton(text="Отредактировать список дел", payload="edit_todo_list")],
        [maxtypes.CallbackButton(text="Посмотреть статистику", payload="view_statistics")]
        #[maxtypes.CallbackButton(text="Создать заметку", payload="pass1")],
        #[maxtypes.CallbackButton(text="Посмотреть заметку", payload="pass2")]
    ]
    start_buttons = maxtypes.ButtonsPayload(buttons=buttons).pack()
    await event.message.answer(text = f"Привет!\nМои функции:\nС чего начнём?", attachments=[start_buttons])


@dp.message_created(maxtypes.Command("view_static"))
async def view_static(event: maxtypes.MessageCreated):
    user_id = event.from_user.user_id
    database.check_has_overdue_tasks(user_id)
    msg = static.display_console_graph(user_id)
    # При необходимости можно отредактировать текст
    await event.message.answer(f"Твоя статистика:\n\n{msg}")  # [web:24]



@dp.message_created(maxtypes.Command("note"))
async def note(event: maxtypes.MessageCreated):
    user_id = event.from_user.user_id

    rows = database.get_tasks_by_user_note(user_id) or []

    if not rows:
        await event.message.answer("Записей не найдено.")
        return

    def to_text(item):
        # Нормализуем к строке с поддержкой tuple/list/dict
        if isinstance(item, (list, tuple)):
            if len(item) == 1:
                return str(item[0])
            return ", ".join(str(x) for x in item)
        if isinstance(item, dict):
            for key in ("text", "note", "title", "name"):
                if key in item:
                    return str(item[key])
            return ", ".join(f"{k}: {v}" for k, v in item.items())
        return str(item)

    # Нумерованный список заметок
    lines = [f"{i}. Запись: {to_text(row)}." for i, row in enumerate(rows, start=1)]
    msg = "\n".join(lines)

    # Кнопки: мягкое удаление (flag=0) и редактирование
    buttons = [
        [maxtypes.CallbackButton(text="Удалить заметку", payload="delete_note")],
        [maxtypes.CallbackButton(text="Отредактировать заметку", payload="edit_note")],
    ]
    start_buttons = maxtypes.ButtonsPayload(buttons=buttons).pack()

    await event.message.answer(msg, attachments=[start_buttons])


@dp.message_callback(maxapi.F.callback.payload == "delete_note")
async def callback_delete_note(event: maxtypes.MessageCallback):
    user_id = event.from_user.user_id
    items = database.get_notes_with_ids(user_id) or []
    if not items:
        await event.message.edit("Видимых заметок нет.")
        return

    buttons = []
    c = 0
    for nid, note, f in items:
        if f == 0:
            continue
        if c <= 10:
            short = note[:40] + "…" if len(note) >40 else note
            buttons.append([maxtypes.CallbackButton(
                text=f"Удалить: {short}",
                payload=f"delete_note_one:{nid}"
            )])
            c += 1
    buttons.append([maxtypes.CallbackButton(
        text="Удалить все заметки",
        payload="delete_note_all"
    )])

    markup = maxtypes.ButtonsPayload(buttons=buttons).pack()
    await event.message.edit("Выберите заметку для удаления:", attachments=[markup])

@dp.message_callback(maxapi.F.callback.payload.startswith("delete_note_one:"))
async def callback_delete_note_one(event: maxtypes.MessageCallback):
    user_id = event.from_user.user_id
    note_id = int(event.callback.payload.split(":", 1)[1])
    deleted = database.del_f(user_id, note_id)
    await event.message.edit("Заметка удалена." if deleted > 0 else "Заметка не найдена или уже удалена.")

@dp.message_callback(maxapi.F.callback.payload == "delete_note_all")
async def callback_delete_note_all(event: maxtypes.MessageCallback):
    user_id = event.from_user.user_id
    deleted = database.del_f(user_id)
    await event.message.edit(f"Удалено заметок: {deleted}" if deleted else "Нет заметок для скрытия.")


# Удаление всех заметок этим пользователем
@dp.message_callback(maxapi.F.callback.payload == "delete_note_all")
async def callback_delete_note_all(event: maxtypes.MessageCallback):
    user_id = event.from_user.user_id
    deleted = database.del_f(user_id)
    await event.message.edit(f"Удалено заметок: {deleted}" if deleted else "Нет заметок для скрытия.")


@dp.message_callback(maxapi.F.callback.payload == "edit_note")
async def callback_edit_note(event: maxtypes.MessageCallback, context: MemoryContext):
    user_id = event.from_user.user_id
    items = database.get_notes_with_ids(user_id) or []
    if not items:
        await event.message.edit("Нет заметок для редактирования.")
        return

    # Кнопки для выбора заметки для редактирования
    buttons = []
    for nid, note, f in items:
        if f == 0:
            continue
        else:
            short = note[:40] + "…" if len(note) > 40 else note
            buttons.append([
                maxtypes.CallbackButton(
                    text=f"Редактировать: {short}", 
                    payload=f"edit_note_pick:{nid}"
                )
            ])
    markup = maxtypes.ButtonsPayload(buttons=buttons).pack()
    await event.message.edit("Выберите заметку для редактирования:", attachments=[markup])

# Обработчик выбора заметки для изменения, установка состояния
@dp.message_callback(maxapi.F.callback.payload.startswith("edit_note_pick:"))
async def callback_edit_note_pick(event: maxtypes.MessageCallback, context: MemoryContext):
    await context.set_state("wait_todo_list_data")
    note_id = int(event.callback.payload.split(":", 1)[1])
    await context.set_state("wait_edit_note")
    await context.set_data({"edit_note_id": note_id})
    await event.message.edit("Введите новый текст заметки одним сообщением:")


@dp.message_created(maxtypes.Command("delete"))
async def delete_1(event: maxtypes.MessageCreated):
    builder = InlineKeyboardBuilder()

    builder.row(
        maxtypes.CallbackButton(
            text='Да',
            payload='Yes'
        ),
        maxtypes.CallbackButton(
            text='Нет',
            payload='No'
        )
    )
    await event.message.answer(f"Ты уверен, что хочешь удалить все данные о себе? (Да/Нет)\nЕсли не уверен, то вызови команду /info", attachments=[builder.as_markup()]    ) 


@dp.message_callback(maxapi.F.callback.payload == 'Yes')
async def delete_2(event: maxtypes.MessageCreated):
    user_id = event.from_user.user_id
    deleted = database.del_f(user_id)
    deleted2 = database.delete_f(user_id)
    await event.message.answer(f"Твои данные удалены!") 


@dp.message_callback(maxapi.F.callback.payload == 'No')
async def delete_3(event: maxtypes.MessageCreated):
    await event.message.edit(f"Хорошо, тогда продолжим работать. Вызови команду /start или /help") 


@dp.message_created(maxtypes.Command("info"))
async def info(event: maxtypes.MessageCreated):
    with open("info.txt", "r", encoding="utf-8") as txt:
        await event.message.answer(txt.read()) 


@dp.message_created(maxtypes.Command("create_day"))
async def create_day(event: maxtypes.MessageCreated, context: MemoryContext):
    await context.set_state("wait_todo_list")
    await event.message.answer("Отлично! Создадим список дел на день.\nНапиши название дела и его срок выполнения, можно сразу несколько через запятую")
    await event.message.answer("*ПРИМЕР:*\nпомыть посуду, сделать презентацию, написать пост")


@dp.message_created(maxtypes.Command("create_data"))
async def create_data(event: maxtypes.MessageCreated, context: MemoryContext):
    await context.set_state("wait_todo_list_data")
    await event.message.answer("Отлично! Создадим список дел c датой (дедлайн).\nНапиши название дела и его срок выполнения, можно сразу несколько через запятую")
    await event.message.answer("*ПРИМЕР:*\nсделать презентацию 12.11, написать пост 4.12")


@dp.message_created(maxtypes.Command("view_plan"))
async def view_plan(event: maxtypes.MessageCreated, context: MemoryContext):
    user_id = event.from_user.user_id
    
    # Обновляем просроченные задачи перед показом
    database.update_overdue_tasks()
    
    # Получаем активные задачи (исключая выполненные и скрытые)
    tasks = database.get_active_tasks_by_user(user_id)

    if not tasks:
        await event.message.answer("У тебя пока нет активных задач.")
        return

    # Формируем сообщение
    msg = "📋 Твои активные дела:\n\n"
    has_overdue = False
    
    for task_id, task_name, status, time_str, due_date, flag in tasks:
        if status == "просрочена":
            status_emoji = "⚠️"
            has_overdue = True
        elif status == "в работе":
            status_emoji = "🛠️"
        else:
            status_emoji = "❓"
        date_obj = datetime.strptime(due_date, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%d.%m.%Y").lstrip('0').replace('.0', '.')
        if time_str:
            msg += f"{status_emoji} {task_name} (до {formatted_date} {time_str})\n"
        else:
            msg += f"{status_emoji} {task_name} (до {formatted_date})\n"
    
    # Если есть просроченные задачи, добавляем кнопку для их скрытия
    if has_overdue:
        buttons = [[
            maxtypes.CallbackButton(
                text="🗑 Удалить просроченные задачи",
                payload="hide_overdue"
            )
        ]]
        markup = maxtypes.ButtonsPayload(buttons=buttons).pack()
        await event.message.answer(msg, attachments=[markup])
    else:
        await event.message.answer(msg)


@dp.message_created(maxtypes.Command("edit_plan"))
async def edit_plan(event: maxtypes.MessageCreated):
    builder = InlineKeyboardBuilder()

    builder.row(
        maxtypes.CallbackButton(
            text='План на день',
            payload='day_edit'
        ),
        maxtypes.CallbackButton(
            text='План c датой',
            payload='data_edit'
        )
    )
    await event.message.answer(text="Что редактируем?", attachments=[builder.as_markup()])


async def todo_list(event: maxtypes.MessageCallback):
    builder = InlineKeyboardBuilder()

    builder.row(
        maxtypes.CallbackButton(
            text='План на день',
            payload='day'
        ),
        maxtypes.CallbackButton(
            text='План с датой',
            payload='data'
        )
    )
    await event.message.edit(text="Отлично! Создадим список дел.\nВыбери назначение", attachments=[builder.as_markup()])


@dp.message_callback(maxapi.F.callback.payload == 'day')
async def day(event: maxtypes.MessageCallback, context: MemoryContext):
    await context.set_state("wait_todo_list")
    await event.message.edit("Отлично! Создадим список дел на день.\nНапиши название дела, можно сразу несколько через запятую")
    await event.message.answer("*ПРИМЕР:*\nпомыть посуду, сделать презентацию, написать пост")


@dp.message_callback(maxapi.F.callback.payload == 'data')
async def data(event: maxtypes.MessageCallback, context: MemoryContext):
    await context.set_state("wait_todo_list_data")
    await event.message.edit("Отлично! Создадим список дел c датой (дедлайн).\nНапиши название дела и его срок выполнения, можно сразу несколько через запятую")
    await event.message.answer("*ПРИМЕР:*\nсделать презентацию 12.11, написать пост 4.12")



async def view_plan_list(event: maxtypes.MessageCallback):
    user_id = event.from_user.user_id
    
    # Обновляем просроченные задачи перед показом
    database.update_overdue_tasks()
    
    # Получаем активные задачи (исключая выполненные и скрытые)
    tasks = database.get_active_tasks_by_user(user_id)
    
    if not tasks:
        await event.message.edit("У тебя пока нет активных задач.")
        return
    
    # Формируем сообщение
    msg = "📋 Твои активные дела:\n\n"
    has_overdue = False
    
    for task_id, task_name, status, time_str, due_date, flag in tasks:
        if status == "просрочена":
            status_emoji = "⚠️"
            has_overdue = True
        elif status == "в работе":
            status_emoji = "🔄"
        else:
            status_emoji = "❓"
        date_obj = datetime.strptime(due_date, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%d.%m.%Y").lstrip('0').replace('.0', '.')
        if time_str:
            msg += f"{status_emoji} {task_name} (до {formatted_date} {time_str})\n"
        else:
            msg += f"{status_emoji} {task_name} (до {formatted_date})\n"
    
    # Если есть просроченные задачи, добавляем кнопку для их скрытия
    if has_overdue:
        buttons = [[
            maxtypes.CallbackButton(
                text="🗑 Удалить просроченные задачи",
                payload="hide_overdue"
            )
        ]]
        markup = maxtypes.ButtonsPayload(buttons=buttons).pack()
        await event.message.edit(msg, attachments=[markup])
    else:
        await event.message.edit(msg)



@dp.message_callback(maxapi.F.callback.payload == 'hide_overdue')
async def hide_overdue_handler(event: maxtypes.MessageCallback):
    user_id = event.from_user.user_id
    
    # Скрываем просроченные задачи (flag = 0)
    hidden_count = database.hide_overdue_tasks(user_id)
    
    if hidden_count > 0:
        # Обновляем список задач после скрытия
        tasks = database.get_active_tasks_by_user(user_id)
        
        if not tasks:
            await event.message.edit(
                f"✅ Скрыто просроченных задач: {hidden_count}\n\n"
                "У тебя больше нет активных задач."
            )
        else:
            msg = f"✅ Скрыто просроченных задач: {hidden_count}\n\n"
            msg += "📋 Твои оставшиеся активные дела:\n\n"
            
            for task_id, task_name, status, time_str, due_date, f in tasks:
                status_emoji = "🔄" if status == "в работе" else "❓"
                if time_str:
                    msg += f"{status_emoji} {task_name} (до {due_date} {time_str})\n"
                else:
                    msg += f"{status_emoji} {task_name} (до {due_date})\n"  # добавлен перенос строки
            
            await event.message.edit(msg)
    else:
        await event.message.edit("ℹ️ Нет просроченных задач для скрытия.")



async def edit_todo_list(event: maxtypes.MessageCallback):
    builder = InlineKeyboardBuilder()

    builder.row(
        maxtypes.CallbackButton(
            text='План на день',
            payload='day_edit'
        ),
        maxtypes.CallbackButton(
            text='План с датой',
            payload='data_edit'
        )
    )
    await event.message.edit(text="Что редактируем?", attachments=[builder.as_markup()])



@dp.message_callback(maxapi.F.callback.payload == 'day_edit')
async def edit_todo_list_day(event: maxtypes.MessageCallback):
    user_id = event.from_user.user_id
    tasks = database.get_active_tasks_by_user(user_id)

    if not tasks:
        await event.message.edit("У тебя пока нет активных задач для редактирования.")
        return

    today = date.today()
    #print(f"[DEBUG] Сегодня: {today}")
    #print(f"[DEBUG] Получено задач: {len(tasks)}")

    def to_date(d):
        try:
            return rt.to_date_safe(d)
        except Exception as e:
            #print(f"[DEBUG] Ошибка парсинга {d!r}: {e}")
            return None

    todays_tasks = []
    for task_id, task_name, status, time_str, due_date, flag in tasks:
        dd = to_date(due_date)
        is_today = dd == today if dd else False
        print(f"[DEBUG] Задача '{task_name}': due_date={due_date!r}, parsed={dd}, сегодня={is_today}")
        if is_today:
            todays_tasks.append((task_id, task_name, status, time_str, due_date))

    if not todays_tasks:
        await event.message.edit("На сегодня нет задач, доступных для редактирования.")
        return

    buttons = []
    for task_id, task_name, status, time_str, due_date in todays_tasks:
        button_text = f"✓ {task_name[:30]}"
        buttons.append([maxtypes.CallbackButton(text=button_text, payload=f"complete_{task_id}")])

    buttons.append([maxtypes.CallbackButton(text="➕ Добавить новую задачу", payload="data")])

    markup = maxtypes.ButtonsPayload(buttons=buttons).pack()
    await event.message.edit(
        text="Выбери сегодняшнюю задачу, чтобы отметить её выполненной, или добавь новую:",
        attachments=[markup]
    )


# Обработчик отметки задачи как выполненной
@dp.message_callback(maxapi.F.callback.payload.startswith('complete_'))
async def complete_task(event: maxtypes.MessageCallback):
    task_id = int(event.callback.payload.split('_')[1])
    
    # Получаем информацию о задаче перед обновлением
    task = database.get_task_by_id(task_id)
    
    if task:
        # Отмечаем задачу как выполненную (НЕ удаляем!)
        database.mark_task_completed(task_id)
        
        # Получаем обновлённый список активных задач
        user_id = event.from_user.user_id
        tasks = database.get_active_tasks_by_user(user_id)
        
        if not tasks:
            await event.message.edit(
                f"✅ Задача '{task[1]}' отмечена как выполненная!\n\n"
                "У тебя больше нет активных задач. Отличная работа! 🎉"
            )
        else:
            # Показываем обновлённый список задач
            msg = f"✅ Задача '{task[1]}' отмечена как выполненная!\n\n"
            msg += "📋 Твои оставшиеся активные дела:\n\n"
            
            has_overdue = False
            for t_id, task_name, status, time_str, due_date, flag in tasks:
                if status == "просрочена":
                    status_emoji = "⚠️"
                    has_overdue = True
                elif status == "в работе":
                    status_emoji = "🔄"
                else:
                    status_emoji = "❓"
                
                if time_str:
                    msg += f"{status_emoji} {task_name} (до {due_date} {time_str})\n"
                else:
                    msg += f"{status_emoji} {task_name}\n"
            
            # Если есть просроченные, добавляем кнопку скрытия
            if has_overdue:
                buttons = [[maxtypes.CallbackButton(
                    text="🗑 Скрыть просроченные задачи",
                    payload="hide_overdue"
                )]]
                markup = maxtypes.ButtonsPayload(buttons=buttons).pack()
                await event.message.edit(msg, attachments=[markup])
            else:
                await event.message.edit(msg)
    else:
        await event.message.edit("❌ Задача не найдена.")


# Обработчик добавления новой задачи через меню редактирования
@dp.message_callback(maxapi.F.callback.payload == 'add_new_task')
async def add_new_task_handler(event: maxtypes.MessageCallback, context: MemoryContext):
    await context.set_state("wait_new_task")
    await event.message.edit("Отлично! Напиши новую задачу (можно несколько через запятую).")
    await event.message.answer("*ПРИМЕР:*\nкупить продукты, позвонить маме")


@dp.message_callback(maxapi.F.callback.payload == 'data_edit')
async def edit_todo_list_data(event: maxtypes.MessageCallback):
    user_id = event.from_user.user_id
    tasks = database.get_active_tasks_by_user(user_id)
    if not tasks:
        await event.message.edit("У тебя нет активных задач для редактирования.")
        return

    # Список уникальных дат для задачи (“due_date”), игнорим выполненные
    unique_dates = sorted(set(
        t[4] for t in tasks if t[4]
    ))
    if not unique_dates:
        await event.message.edit("Нет задач с датой выполнения для редактирования.")
        return

    # Кнопки по датам
    buttons = [
        [maxtypes.CallbackButton(text=date, payload=f"edit_day_{date}")]
        for date in unique_dates
    ]
    markup = maxtypes.ButtonsPayload(buttons=buttons).pack()
    await event.message.edit(
        text="Выбери день для редактирования задач:",
        attachments=[markup]
    )


@dp.message_callback(maxapi.F.callback.payload.startswith('edit_day_'))
async def edit_day_tasks(event: maxtypes.MessageCallback):
    user_id = event.from_user.user_id
    date_str = event.callback.payload[len('edit_day_'):]
    # Получаем только задачи этого дня
    tasks = database.get_active_tasks_by_user(user_id)
    day_tasks = [t for t in tasks if t[4] == date_str]

    if not day_tasks:
        await event.message.edit(
            f"На {date_str} нет задач для редактирования."
        )
        return

    # Кнопки по задачам выбранного дня
    buttons = [
        [maxtypes.CallbackButton(text=f"✓ {t[1][:30]}", payload=f"complete_{t[0]}")]
        for t in day_tasks
    ]
    buttons.append(
        [maxtypes.CallbackButton(text="➕ Добавить новую задачу", payload=f"add_task_{date_str}")]
    )
    markup = maxtypes.ButtonsPayload(buttons=buttons).pack()
    await event.message.edit(
        text=f"Задачи на {date_str}:",
        attachments=[markup]
    )




async def view_statistics(event: maxtypes.MessageCallback):
    user_id = event.from_user.user_id
    database.check_has_overdue_tasks(user_id)
    msg  = static.display_console_graph(user_id)
    await event.message.edit('Твоя статистика:\n\n' + msg)



@dp.message_created(maxapi.F.message.body.text)
async def logic(event: maxtypes.MessageCreated, context: MemoryContext):
    state = await context.get_state()
    if state == "wait_todo_list":
        flag = True 
        todo_text = event.message.body.text
        user_id = event.from_user.user_id
        chat_id = event.chat.chat_id
        user_name = event.from_user.first_name or "нет имени"
        today = datetime.now().strftime('%Y-%m-%d')
        items = [x.strip() for x in todo_text.split(',')]
        for item in items:
            parts = item.rsplit(' ', 1)  
            if len(parts) == 2 and ':' in parts[1]:
                task_name, time_str = parts
            else:
                task_name = item
                time_str = ""
            
            database.add_task(
                user_id=user_id,
                user_name=user_name,
                chat_id=chat_id, 
                task=task_name,
                status='в работе',
                time=time_str,
                due_date=today
            )
        await context.set_state(None)
        await event.message.answer("Хорошо, список дел записан!")

        saved_tasks = "\n".join(items)
        await event.message.answer(f"Сохранено:\n{saved_tasks}")
        worker = reminder_worker.ReminderWorker_day(bot, user_id, chat_id)
        reminder_worker.asyncio.create_task(worker.run())
        #reminder_worker.asyncio.create_task(worker.run_test_minute())
        return
    if state == "wait_todo_list_data":
        flag = True
        todo_text = event.message.body.text
        user_id = event.from_user.user_id
        chat_id = event.chat.chat_id
        user_name = event.from_user.first_name or "нет имени"
        today = datetime.now().strftime('%Y-%m-%d')
    
        # Убираем ведущую нумерацию (1), 2., 3- и т.п.)
        items = [re.sub(r'^\s*\d+[\)\.\-:]?\s*', '', x).strip() for x in todo_text.split(',')]
    
        for item in items:
            task_name, time_str, due_date = rt.parse_task_item(item)
            database.add_task(
            user_id=user_id,
            user_name=user_name,
            chat_id=chat_id,
            task=task_name,
            status='в работе',
            time=time_str,
            due_date=due_date or today,
            )
    
        await context.set_state(None)
        await event.message.answer("Хорошо, список дел записан!")
        saved_tasks = "\n".join(items)
        await event.message.answer(f"Сохранено:\n{saved_tasks}")
        worker = reminder_worker.ReminderWorker_day(bot, user_id, chat_id)
        reminder_worker.asyncio.create_task(worker.run())
        return
    if state == "wait_edit_note":
        data = await context.get_data() or {}
        note_id = data.get("edit_note_id")
        new_text = event.message.body.text.strip()
        user_id = event.from_user.user_id
        updated = database.update_note_text(user_id, note_id, new_text)
        await context.set_state(None)
        if updated > 0:
            await event.message.answer("Заметка изменена.")
        else:
            await event.message.answer("Не удалось изменить заметку. Возможно, она скрыта или удалена.")
        return
    else:
        todo_text = event.message.body.text
        user_id = event.from_user.user_id
        chat_id = event.chat.chat_id
        user_name = event.from_user.first_name or "нет имени"
        flag = 1
        database.add_task_note(
                user_id=user_id,
                user_name=user_name,
                chat_id=chat_id, 
                note=todo_text, 
                flag = flag
            )
        await event.message.answer(f"{event.from_user.first_name}, заметка записана! Посмотреть заметки и отредактировать можно с помощью команды /note")




@dp.message_callback()
async def one_list(event: maxtypes.MessageCallback):
    if event.callback.payload == "todo_list":
        await todo_list(event)
    elif event.callback.payload == "view_plan_list":
        await view_plan_list(event)
    elif event.callback.payload == "edit_todo_list":
        await edit_todo_list(event)
    elif event.callback.payload == "view_statistics":
        await view_statistics(event)


async def on_message(event: maxtypes.MessageCreated):
    global bot_start_time
    # В MAX у сообщения есть timestamp/created_at (вью зависит от клиента). Часто это Unix time (UTC).
    # У maxapi в примерах используется event.message.body и метаданные, но конкретное поле даты может отличаться.
    # Пример универсальной выборки:
    msg_dt_utc = None
    if event.timestamp < time.time():
        return 
    # Попытка прочитать unix timestamp, если доступен (например, event.message.date или event.message.created_at)
    # Ниже две ветки на случай разных клиентов:
    if hasattr(event.message, "date") and isinstance(event.message.date, int):
        msg_dt_utc = datetime.fromtimestamp(event.message.date, tz=timezone.utc)  # [web:10][web:13]
    elif hasattr(event.message, "created_at") and isinstance(event.message.created_at, int):
        msg_dt_utc = datetime.fromtimestamp(event.message.created_at, tz=timezone.utc)  # [web:10][web:13]
    else:
        # Если нет явного времени — считаем, что сообщение свежее (или добавьте логику по умолчанию)
        msg_dt_utc = datetime.now(timezone.utc)  # [web:10]

    if bot_start_time is not None and msg_dt_utc >= bot_start_time:
        pass
    else:
        # Логируем пропуск старых сообщений
        logging.info("Пропущено старое сообщение")



async def main():
    await bot.set_my_commands(
        maxtypes.BotCommand(
            name='/start',
            description='Начало/Главная'
        ),
        maxtypes.BotCommand(
            name='/help',
            description='Если не разобрались в интерфейсе'
        ),
        maxtypes.BotCommand(
            name='/info',
            description='Хотите узнать подробнее о боте'
        ),
        maxtypes.BotCommand(
            name = '/create_day',
            description = 'Создать список на день'
        ),
        maxtypes.BotCommand(
            name = '/create_plan',
            description = 'Создать список по дням'
        ),
        maxtypes.BotCommand(
            name = '/view_plan',
            description = 'Посмотреть список'
        ),
        maxtypes.BotCommand(
            name = '/edit_plan',
            description = 'Отредактировать список дел'
        ),
        maxtypes.BotCommand(
            name = '/view_static',
            description = 'Посмотреть статистику'
        ),
        maxtypes.BotCommand(
            name = '/note',
            description = 'Посмотреть заметку'
        )
    )

    
    database.create_database()
    database.create_database_note()

    # Отмечаем точку старта бота в UTC
    bot_start_time = datetime.now(timezone.utc)


    try:
        active_users = database.get_active_users_for_reminders()
        for user_id, chat_id in active_users:
            worker = reminder_worker.ReminderWorker_day(bot, user_id, chat_id)
            asyncio.create_task(worker.run())
    except Exception as e:
        logging.exception("Ошибка при запуске воркеров напоминаний: %s", e)
    finally:
        # Старт поллинга событий MAX
        await dp.start_polling(bot)  


if __name__ == "__main__":
    asyncio.run(main())