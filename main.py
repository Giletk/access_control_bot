import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, ChatMemberUpdatedFilter
from aiogram.types import ChatMemberUpdated
from dotenv import load_dotenv

load_dotenv()
API_TOKEN = os.getenv('bot_token')
with open('allowed_usernames.txt', 'r') as f:
    ALLOWED_USERNAMES = [x.strip() for x in f.readlines()]
CHECK_INTERVAL = 300  # Время в секундах

file_log = logging.FileHandler("bot.log")
stdout_log = logging.StreamHandler()
logging.basicConfig(handlers=(file_log, stdout_log), level=logging.INFO)
logger = logging.getLogger(__name__)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()


async def check_users_in_chat(chat_id: int, admin: types.User):
    try:
        members = await bot.get_chat_administrators(chat_id)
        for member in members:
            if member.user.username not in ALLOWED_USERNAMES:
                admins = await bot.get_chat_administrators(chat_id)
                admin_ids = [admin.user.id for admin in admins]
                for admin_id in admin_ids:
                    await bot.send_message(admin_id,
                                           f"Пользователь {member.user.full_name} (@{member.user.username}) не найден в списке разрешенных.")
    except TelegramAPIError as e:
        logger.error(f"Error checking chat members in chat {chat_id}: {e}")


async def periodic_check(chat_id: int, admin: types.User):
    while True:
        await check_users_in_chat(chat_id, admin)
        await asyncio.sleep(CHECK_INTERVAL)


@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    logger.info(f"получена команда {message.text}")
    chat_type = message.chat.type
    bot_info = await bot.get_me()
    if chat_type == "private":
        await message.answer(f"Добавьте меня в группу и отправьте в ней команду:\n/start @{bot_info.username}\n\n"
                             f"Отчёты проверок будут направлены администратору, запустившему бота.")
    else:
        args = message.text.split()
        if len(args) < 2:
            logger.warning(f"Недостаточно аргументов")
            return
        if args[1].lstrip('@') != bot_info.username:
            logger.warning(f"Вызов без прямого обращения к боту в группе")
            return

        bot_is_admin = await bot.get_chat_member(message.chat.id, bot.id)
        if bot_is_admin:
            sender = await bot.get_chat_member(message.chat.id, message.from_user.id)
            logger.info(f"Отправитель команды: @{message.from_user.username}")
            if not isinstance(sender, types.ChatMemberOwner) and not isinstance(sender, types.ChatMemberAdministrator):
                await message.reply("Бот может быть запущен только администратором группы")
            else:
                await message.reply(
                    f"Бот запущен и будет проверять пользователей каждые {CHECK_INTERVAL // 60} минут.\n\n"
                    f"Отчёты будет направлены @{message.from_user.username}")
        else:
            await message.reply(f"Боту необходимы права администратора для просмотра участников чата.\n"
                                f"Выдайте боту права администратора и напишите /start @{bot_info.username}")


@dp.message(Command("check"))
async def manual_check(message: types.Message):
    await check_users_in_chat(message.chat.id)
    await message.reply("Проверка завершена.")


# @dp.chat_member(ChatMemberUpdatedFilter())
# async def handle_new_chat_member(event: ChatMemberUpdated):
#     if event.new_chat_member.status in {'member', 'administrator', 'creator'} and event.old_chat_member.status not in {
#             'member', 'administrator', 'creator'}:
#         dp["chat_id"] = event.chat.id
#         await bot.send_message(event.chat.id, "Бот добавлен в этот чат и начнет проверку пользователей каждые 5 минут.")


async def on_startup(dispatcher: Dispatcher):
    asyncio.create_task(periodic_check())


async def main():
    # dp.startup.register(on_startup)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
