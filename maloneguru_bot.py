import os
import requests
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackContext, filters
)
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PARTICIPANTS_URL = "https://malone.guru/api/lunch/participants/"
FEEDBACK_URL = "https://malone.guru/api/feedback/"
API_TOKEN = os.getenv("API_TOKEN")
ALLOWED_USERS = list(map(int, os.getenv("ALLOWED_USERS", "").split(",")))

def access_control(func):
    async def wrapper(update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        if user_id not in ALLOWED_USERS:
            await update.message.reply_text("У вас нет доступа к этому боту.")
            return
        return await func(update, context)
    return wrapper

@access_control
async def start_command(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "Добро пожаловать! Этот бот поможет вам управлять участниками обеда.\n"
        "Используйте /help, чтобы увидеть список доступных команд."
    )

@access_control
async def help_command(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "Доступные команды:\n\n"
        "/participants - Получить список участников обеда\n\n"
        "/register <имя>, <email>, <portions>, <date>, <comment> - Зарегистрировать нового участника*\n"
        "Например:\n/register Афанасий Петров, afonya@mail.ru, 3, 2026-09-26, Если можно, кофе на безлактозном молоке\n\n"
        "/delete <id> - Удалить участника по ID\n\n"
        "/feedbacks - Получить список из 3-х последних сообщений из формы обратной связи\n\n"
        "/feedback_delete <id> - Удалить фидбек по ID\n\n"
        "/start - Начать работу с ботом\n\n"
        "/help - Показать список доступных команд\n\n"
        "*Примечания:\n"
        "1. Поля <date> и <comment> являются необязательными.\n"
        "Если поле <date> не заполнено, запись возможна с воскресенья 04:00 "
        "до пятницы 22:00 по литовскому времени на ближайшую субботу. "
        "В другое время укажите дату явно.\n"
        "2. Перед тем, как заполнять поле <comment>, убедитесь, что заполнили поле <date>.\n"
        "Поле <comment> не может быть заполнено, если не заполнено поле <date>."
    )


@access_control
async def get_participants(update: Update, context: CallbackContext):
    headers = {"Authorization": f"Token {API_TOKEN}"}
    response = requests.get(PARTICIPANTS_URL, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data:
            participants_list = "\n\n".join(
                [
                    f"{p['id']}: {p['name']}\nemail: {p['email']}\nКоличество порций: {p['portions']}\n"
                    + (f"Комментарий: {p['comment']}\n" if p['comment'] else "")
                    + f"Дата: {datetime.fromisoformat(p['registration_date']).strftime('%Y-%m-%d %H:%M')}"
                    for p in data
                ]
            )
            await update.message.reply_text(f"Участники обеда:\n{participants_list}")
        else:
            await update.message.reply_text("Участников пока нет.")
    else:
        await update.message.reply_text("Ошибка при получении данных.")

@access_control
async def register_participant(update: Update, context: CallbackContext):
    try:
        # Разбиваем аргументы команды
        data = [item.strip() for item in " ".join(context.args).split(",")]

        # Проверяем минимальное количество аргументов
        if len(data) < 3:
            await update.message.reply_text(
                "Используйте: /register <имя>, <email>, <portions>, <date>, <comment>\n"
                "Примечания:\n"
                "1. Поля <date> и <comment> являются необязательными.\n"
                "2. Поле <comment> нельзя заполнить без заполненного поля <date>."
            )
            return

        # Инициализация переменных
        name, email, portions = data[:3]
        date = data[3] if len(data) >= 4 else None
        comment = ", ".join(data[4:]) if len(data) >= 5 else None

        # Формирование полезной нагрузки
        payload = {"name": name, "email": email, "portions": int(portions)}
        if date:
            payload["date"] = date
        if comment:
            payload["comment"] = comment

        # Выполняем POST-запрос
        headers = {"Authorization": f"Token {API_TOKEN}"}
        response = requests.post(PARTICIPANTS_URL, json=payload, headers=headers)

        # Обрабатываем ответ
        if response.status_code == 201:
            participant = response.json()
            await update.message.reply_text(
                f"Участник успешно зарегистрирован!\n"
                f"ID: {participant['id']}\n"
                f"Имя: {participant['name']}\n"
                f"Email: {participant['email']}\n"
                f"Порции: {participant['portions']}\n"
                + (f"Комментарий: {participant['comment']}\n" if participant.get("comment") else "")
                + f"Дата обеда: {participant.get('date', 'Не указана')}\n"
                + f"Дата регистрации: {datetime.fromisoformat(participant['registration_date']).strftime('%Y-%m-%d %H:%M')}"
            )
        else:
            await update.message.reply_text(
                f"Ошибка при регистрации участника: {response.text}"
            )
    except ValueError:
        await update.message.reply_text(
            "Используйте: /register <имя>, <email>, <portions>, <date>, <comment>\n"
            "Примечания:\n"
            "1. Поля <date> и <comment> являются необязательными.\n"
            "2. Поле <comment> нельзя заполнить без заполненного поля <date>."
        )


@access_control
async def delete_participant(update: Update, context: CallbackContext):
    try:
        headers = {"Authorization": f"Token {API_TOKEN}"}

        # Если ID указан, используем его
        if context.args:
            participant_id = int(context.args[0])
        else:
            # Получаем последнюю запись
            response = requests.get(PARTICIPANTS_URL, headers=headers)
            if response.status_code == 200:
                participants = response.json()
                if participants:
                    participant_id = max(participant["id"] for participant in participants)
                else:
                    await update.message.reply_text("В базе данных нет участников для удаления.")
                    return
            else:
                await update.message.reply_text(
                    f"Ошибка при получении участников: {response.text}"
                )
                return

        # Удаляем запись
        delete_response = requests.delete(f"{PARTICIPANTS_URL}{participant_id}/", headers=headers)
        if delete_response.status_code == 204:
            await update.message.reply_text(f"Участник с ID {participant_id} был удален.")
        else:
            await update.message.reply_text(f"Ошибка при удалении участника: {delete_response.text}")

    except ValueError:
        await update.message.reply_text("ID должен быть числом.")


@access_control
async def get_feedbacks(update: Update, context: CallbackContext):
    headers = {"Authorization": f"Token {API_TOKEN}"}
    response = requests.get(FEEDBACK_URL, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data:
            # Сортировка по дате и выбор последних трех фидбеков
            data_sorted = sorted(data, key=lambda x: datetime.fromisoformat(x['date']), reverse=True)[:3]
            feedbacks_list = "\n\n".join(
                [
                    f"{f['id']}: {f['name']}\nemail: {f['email']}\n"
                    + f"Текст фидбека:\n{f['text']}\n"
                    + f"Дата и время отправки:\n{datetime.fromisoformat(f['date']).strftime('%Y-%m-%d %H:%M')}"
                    for f in data_sorted
                ]
            )
            await update.message.reply_text(f"Последние фидбеки:\n\n{feedbacks_list}")
        else:
            await update.message.reply_text("Фидбеков пока нет.")
    else:
        await update.message.reply_text(f"Ошибка при получении данных: {response.text}")


@access_control
async def delete_feedback(update: Update, context: CallbackContext):
    try:
        headers = {"Authorization": f"Token {API_TOKEN}"}

        # Если ID указан, используем его
        if context.args:
            feedback_id = int(context.args[0])
        else:
            # Получаем последнюю запись
            response = requests.get(FEEDBACK_URL, headers=headers)
            if response.status_code == 200:
                feedbacks = response.json()
                if feedbacks:
                    feedback_id = max(feedback["id"] for feedback in feedbacks)
                else:
                    await update.message.reply_text("В базе данных нет фидбеков для удаления.")
                    return
            else:
                await update.message.reply_text(
                    f"Ошибка при получении фидбеков: {response.text}"
                )
                return

        # Удаляем запись
        delete_response = requests.delete(f"{FEEDBACK_URL}{feedback_id}/", headers=headers)
        if delete_response.status_code == 204:
            await update.message.reply_text(f"Фидбек с ID {feedback_id} был удален.")
        else:
            await update.message.reply_text(f"Ошибка при удалении фидбека: {delete_response.text}")

    except ValueError:
        await update.message.reply_text("ID должен быть числом.")


# Настройка приложения
application = Application.builder().token(BOT_TOKEN).build()

# Добавление обработчиков
application.add_handler(CommandHandler("start", start_command))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("participants", get_participants))
application.add_handler(CommandHandler("register", register_participant))
application.add_handler(CommandHandler("delete", delete_participant))
application.add_handler(CommandHandler("feedbacks", get_feedbacks))
application.add_handler(CommandHandler("feedback_delete", delete_feedback))

# Запуск приложения
if __name__ == "__main__":
    application.run_polling()
