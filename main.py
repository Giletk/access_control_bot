import asyncio
import logging
import os

import asyncpg
from aiogram import Bot, Dispatcher, types
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import ChatMemberUpdated
from dotenv import load_dotenv

load_dotenv()
API_TOKEN = os.getenv('bot_token')
DB_HOST = os.getenv('db_host')
DB_PORT = os.getenv('db_port')
DB_USER = os.getenv('db_user')
DB_PASSWORD = os.getenv('db_password')
DB_NAME = os.getenv('db_name')

CHECK_INTERVAL = 12  # Время в секундах

file_log = logging.FileHandler("bot.log")
stdout_log = logging.StreamHandler()
logging.basicConfig(
    handlers=(file_log, stdout_log),
    level=logging.DEBUG,
    format=' %(asctime)s:%(name)s:%(funcName)s:%(levelname)s:%(message)s',
    encoding="utf-8")
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Инициализация списка разрешённых пользователей
ALLOWED_USERNAMES = []


# Декоратор для отлова ошибок
def logging_exceptions(function):
    def wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception as e:
            logger.error(f"Failed launch {function.__name__} with {args}, {kwargs}: {e}", exc_info=True)

    return wrapper


# Подключение к базе данных
@logging_exceptions
async def get_db_connection():
    return await asyncpg.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )


# Создание таблиц в базе данных
@logging_exceptions
async def create_tables():
    conn = await get_db_connection()
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            username TEXT,
            full_name TEXT,
            chat_id BIGINT NOT NULL
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS allowed_users (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE
        )
    """)
    await conn.close()
    logger.info("Tables created")


# Получение списка разрешённых пользователей из базы данных
@logging_exceptions
async def get_allowed_usernames():
    logger.info("Getting allowed username list from DB")
    conn = await get_db_connection()
    rows = await conn.fetch("SELECT username FROM allowed_users")
    await conn.close()
    result = [row['username'] for row in rows]
    logger.debug(f"Extracted allowed usernames: {result}")
    return result


# Получение списка пользователей в группе из базы данных
@logging_exceptions
async def get_current_usernames(chat_id: int):
    logger.info("Getting current username list from DB")
    conn = await get_db_connection()
    rows = await conn.fetch(f"SELECT username FROM users WHERE chat_id={chat_id}")
    await conn.close()
    result = [row['username'] for row in rows]
    logger.debug(f"Extracted current usernames: {result}")
    return result


# Функция для изменения глобального списка разрешённых пользователей
@logging_exceptions
async def load_allowed_usernames():
    global ALLOWED_USERNAMES
    ALLOWED_USERNAMES = await get_allowed_usernames()


# Добавление пользователя в базу данных
@logging_exceptions
async def add_user_to_db(user_id, username, full_name, chat_id):
    logger.info(f"Добавляем пользователя @{username} в дб")
    conn = await get_db_connection()
    await conn.execute("""
        INSERT INTO users (user_id, username, full_name, chat_id)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id, chat_id) DO NOTHING
    """, user_id, username, full_name, chat_id)
    await conn.close()


# Удаление пользователя из базы данных
@logging_exceptions
async def remove_user_from_db(user_id, chat_id):
    logger.info(f"Удаляем пользователя с id={user_id} из дб")
    conn = await get_db_connection()
    await conn.execute("DELETE FROM users WHERE user_id = $1 AND chat_id = $2", user_id, chat_id)
    await conn.close()


# Функция проверки доступа пользователей в чате
async def check_users_in_chat(chat_id: int, admin: types.User):
    logger.info(f"Проверка участников группы с id={chat_id}")
    try:
        members = await get_current_usernames()
        for member in members:
            if member not in ALLOWED_USERNAMES:
                await bot.send_message(admin.id,
                                       f"Пользователь {member.user.full_name} (@{member.user.username})"
                                       f" не найден в списке разрешенных.")
                logger.info(f"Отчёт отправлен @{admin.username}")
    except TelegramAPIError as e:
        logger.error(f"Error checking chat members in chat {chat_id}: {e}")


# Функция автоматической проверки участников группы
async def periodic_check(chat_id: int, admin: types.User):
    logger.info(f"Запускаем цикл проверок для группы id={chat_id}. Отчёты направляются @{admin.username}")
    while True:
        await check_users_in_chat(chat_id, admin)
        await asyncio.sleep(CHECK_INTERVAL)


@dp.message(Command("dice"))
async def cmd_dice(message: types.Message):
    await message.answer_dice(emoji="🎲")


# Обработчик команды /start
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    logger.info(f"получена команда {message.text}")
    chat_type = message.chat.type  # Определим тип чата: ЛС или группа
    bot_info = await bot.get_me()
    logger.debug(f"Bot info: {bot_info}")
    logger.debug(f"Chat type: {chat_type}")
    if chat_type == "private":
        await message.answer(f"Добавьте меня в группу и отправьте в ней команду:\n/start @{bot_info.username}\n\n"
                             f"Отчёты проверок будут направлены администратору, запустившему бота.")
    else:
        # В группе бот будет обращать внимание только на команды с его никнеймом через пробел
        args = message.text.split()
        logger.debug(f"Command args: {args}")
        # Если нет обращения к боту, игнорируем команду, чтобы не конфликтовать с другими ботами группы
        if len(args) < 2:
            logger.warning(f"Недостаточно аргументов")
            return
        if args[1].lstrip('@') != bot_info.username:
            logger.warning(f"Вызов без прямого обращения к боту в группе")
            return

        # Проверяем админку бота, пытаясь достать информацию об участнике группы. Если админки нет, ничего не выйдет
        bot_is_admin = await bot.get_chat_member(message.chat.id, bot.id)
        logger.debug(f"Group chat_id: {message.chat.id}")
        if bot_is_admin:
            sender = await bot.get_chat_member(message.chat.id, message.from_user.id)
            logger.debug(f"Отправитель команды: @{message.from_user.username}")
            if not isinstance(sender, types.ChatMemberOwner) and not isinstance(sender, types.ChatMemberAdministrator):
                await message.reply("Бот может быть запущен только администратором группы")
                logger.debug("Non-admin tried to start the bot inside a group")
            else:
                await message.reply(
                    f"Бот запущен и будет проверять пользователей каждые {CHECK_INTERVAL // 60} минут.\n\n"
                    f"Отчёты будет направлены @{message.from_user.username}")
                logger.debug("Successful group /start")
                # Запускаем периодическую проверку
                asyncio.create_task(periodic_check(message.chat.id, message.from_user))
        else:
            await message.reply(f"Боту необходимы права администратора для просмотра участников чата.\n"
                                f"Выдайте боту права администратора и напишите /start @{bot_info.username}")
            logger.debug("Bot has no admin privileges")


# Обработка команды ручной проверки /check
@dp.message(Command("check"))
async def manual_check(message: types.Message):
    logger.debug("Manual check launched")
    await check_users_in_chat(message.chat.id, message.from_user)
    await message.reply("Проверка завершена.")


# Обработка добавления участника


# Обработка удаления участника


@dp.message()
async def all_messages_handler(message: types.Message):
    logger.info(f"Unhandled message: {message}")


@dp.chat_member()
async def all_chat_member_updates_handler(event: ChatMemberUpdated):
    logger.info(f"Unhandled chat member update: {event}")


# Главная функция
async def main():
    await create_tables()
    await load_allowed_usernames()
    await dp.start_polling(bot,
                           allowed_updates=["message", "chat_member"])
    logger.info("Tables created and bot started.")


if __name__ == "__main__":
    asyncio.run(main())
