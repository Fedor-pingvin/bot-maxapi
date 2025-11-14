import asyncio
from datetime import datetime, timedelta
import database

class ReminderWorker_day:
    def __init__(self, bot, user_id, chat_id):
        self.bot = bot
        self.user_id = user_id
        self.chat_id = chat_id
        self.active = True  # Для возможности остановки воркера
        self.reminder_hours = [9, 11, 13, 15, 17, 20]
        self.sent_today = set()  # Контроль уже отправленных напоминаний

    async def run(self):
        while self.active:
            now = datetime.now()
            if now.hour == 0:  # Новый день — сбрасываем трекер отправок
                self.sent_today.clear()

            for hour in self.reminder_hours:
                if not self.active:
                    break

                if hour in self.sent_today:
                    continue

                now = datetime.now()
                reminder_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
                if reminder_time < now:
                    continue  # Этот слот уже прошёл

                wait_sec = (reminder_time - now).total_seconds()
                if wait_sec > 0:
                    try:
                        await asyncio.wait_for(self._wait_or_stop(wait_sec), timeout=wait_sec + 5)
                    except asyncio.TimeoutError:
                        pass  # Просто идём дальше

                # Перед отправкой проверяем снова задачи
                today = datetime.now().strftime('%Y-%m-%d')
                tasks = database.get_tasks_by_user(self.user_id)
                today_tasks = [t for t in tasks if t[3] == today]  # Индекс 3 = due_date

                if today_tasks and hour not in self.sent_today:
                    plan_msg = "План на сегодня:\n" + "".join(f"- {t[0]}\n" for t in today_tasks)
                    await self.bot.send_message(chat_id=self.chat_id, text=plan_msg)
                    self.sent_today.add(hour)

            # Ждём до завтрашнего дня
            next_day = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=1, second=0, microsecond=0)
            wait_to_next = (next_day - datetime.now()).total_seconds()
            if wait_to_next > 0:
                try:
                    await asyncio.wait_for(self._wait_or_stop(wait_to_next), timeout=wait_to_next + 5)
                except asyncio.TimeoutError:
                    pass
            self.sent_today.clear()

    async def _wait_or_stop(self, seconds):
        """Асинхронное ожидание, прерывающееся если self.active = False."""
        start = datetime.now()
        while self.active and (datetime.now() - start).total_seconds() < seconds:
            await asyncio.sleep(1)

    def stop(self):
        self.active = False
