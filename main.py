import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from dotenv import load_dotenv

from database import create_tables, get_allowed_usernames, get_current_users
from handlers import router as main_router

load_dotenv()
API_TOKEN = os.getenv('bot_token')

CHECK_INTERVAL = 60  # Время между проверками пользователей в секундах

file_log = logging.FileHandler("bot.log")
stdout_log = logging.StreamHandler()
logging.basicConfig(
    handlers=(file_log, stdout_log),
    level=logging.INFO,
    format=' %(asctime)s:%(name)s:%(funcName)s:%(levelname)s:%(message)s',
    encoding="utf-8")
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
dp.include_router(main_router)

# Список разрешённых пользователей
ALLOWED_USERNAMES = []

# Множество админов, которым уже приходят отчёты
# член множества: (user_id, chat_id)
REPORT_RECIPIENTS = set()


# Функция для изменения глобального списка разрешённых пользователей
async def load_allowed_usernames():
    global ALLOWED_USERNAMES
    ALLOWED_USERNAMES = await get_allowed_usernames()


# Функция проверки доступа пользователей в чате
async def check_users_in_chat(chat_id: int, admin: types.User):
    await load_allowed_usernames()
    logger.info(f"Проверка участников группы с id={chat_id}")
    try:
        members = await get_current_users(chat_id)
        for member in members:
            if member['username'] not in ALLOWED_USERNAMES:
                await bot.send_message(admin.id,
                                       f"Пользователь {member['full_name']} (@{member['username']})"
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


# Обработчик команды /start
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    logger.info(f"получена команда {message.text}")
    chat_type = message.chat.type  # Определим тип чата: ЛС или группа
    bot_info = await bot.get_me()
    logger.debug(f"Bot info: {bot_info}")
    logger.debug(f"Chat type: {chat_type}")
    if chat_type == "private":
        await message.answer(
            f"Добавьте бота в группу, сделайте админом и отправьте в ней команду:\n/start@{bot_info.username}\n\n"
            f"Отчёты проверок будут направлены администратору, запустившему бота.")
    else:
        # В группе бот будет обращать внимание только на команды с его никнеймом через пробел
        if bot_info.username not in message.text:
            logger.debug("Command without bot username. Ignoring it.")
            return
        # Проверяем админку бота
        bot_member_type = await bot.get_chat_member(message.chat.id, bot.id)
        logger.debug(f"bot member type: {type(bot_member_type)}")
        logger.debug(f"Group chat_id: {message.chat.id}")
        if isinstance(bot_member_type, types.ChatMemberAdministrator):
            sender = await bot.get_chat_member(message.chat.id, message.from_user.id)
            logger.debug(f"Отправитель команды: @{message.from_user.username}")
            if not isinstance(sender, types.ChatMemberOwner) and not isinstance(sender, types.ChatMemberAdministrator):
                await message.reply("Бот может быть запущен только администратором группы")
                logger.debug("Non-admin tried to start the bot inside a group")
            else:
                if (message.from_user.id, message.chat.id) not in REPORT_RECIPIENTS:
                    REPORT_RECIPIENTS.add((message.from_user.id, message.chat.id))
                    await message.reply(
                        f"Бот запущен и будет проверять пользователей каждые {CHECK_INTERVAL // 60} минут.\n\n"
                        f"Отчёты будет направлены @{message.from_user.username}\n\n"
                        f"Если хотите выполнить проверку прямо сейчас, введите команду:\n"
                        f"/check@{bot_info.username}")
                    logger.debug("Successful group /start")
                    # Запускаем периодическую проверку
                    asyncio.create_task(periodic_check(message.chat.id, message.from_user))
                else:
                    await message.reply(
                        f"Вы уже получаете отчёты.\n\n Если хотите выполнить проверку прямо сейчас, введите команду:\n"
                        f"/check@{bot_info.username}")
        else:
            await message.reply(f"Боту необходимы права администратора для просмотра участников чата.\n\n"
                                f"Выдайте боту права администратора и повторите команду")
            logger.debug("Bot has no admin privileges")


# Обработка команды ручной проверки /check
@dp.message(Command("check"))
async def manual_check(message: types.Message):
    logger.info(f"получена команда {message.text}")
    chat_type = message.chat.type  # Определим тип чата: ЛС или группа
    bot_info = await bot.get_me()
    logger.debug(f"Bot info: {bot_info}")
    logger.debug(f"Chat type: {chat_type}")
    if chat_type == "private":
        await message.answer(f"Ручная проверка доступна только в группах.\n\n"
                             f"Используйте команду:\n"
                             f"/check@{bot_info.username}")
    else:
        # В группе бот будет обращать внимание только на команды с его никнеймом через пробел
        if bot_info.username not in message.text:
            logger.debug("Command without bot username. Ignoring it.")
            return
        # Проверяем админку бота
        bot_member_type = await bot.get_chat_member(message.chat.id, bot.id)
        sender_member_type = await bot.get_chat_member(message.chat.id, message.from_user.id)
        logger.debug(f"bot member type: {type(bot_member_type)}")
        logger.debug(f"Group chat_id: {message.chat.id}")
        if not isinstance(sender_member_type, types.ChatMemberAdministrator) \
                and not isinstance(sender_member_type, types.ChatMemberOwner):
            await message.reply("Запустить проверку может только администратор")
            return

        if isinstance(bot_member_type, types.ChatMemberAdministrator):
            # В группе бот будет обращать внимание только на команды с его никнеймом через пробел
            if bot_info.username not in message.text:
                logger.debug("Command without bot username. Ignoring it.")
                return
            print((message.from_user.id, message.chat.id), REPORT_RECIPIENTS)
            if (message.from_user.id, message.chat.id) in REPORT_RECIPIENTS:
                await check_users_in_chat(message.chat.id, message.from_user)
                await message.reply("Проверка завершена.")
            else:
                await message.reply(f"Вас нет в списке получателей отчётов.\n\n Чтобы это исправить,"
                                    f" выполните команду:\n/start@{bot_info.username}")
        else:
            await message.reply("Боту нужны права администратора")


# Главная функция
async def main():
    await create_tables()

    # Пропускаем все накопленные входящие
    await bot.delete_webhook(drop_pending_updates=True)
    # Запускаем бота
    await dp.start_polling(bot,
                           allowed_updates=["message", "chat_member"])
    logger.info("bot started")


if __name__ == "__main__":
    asyncio.run(main())
