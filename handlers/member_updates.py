import logging

from aiogram import Router, types
from aiogram.filters import Command, ChatMemberUpdatedFilter, JOIN_TRANSITION, LEAVE_TRANSITION

from database import add_user_to_db, remove_user_from_db

router = Router(name=__name__)
logger = logging.getLogger(__name__)

# Обработка добавления участника
@router.chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def on_user_join(event: types.ChatMemberUpdated):
    await add_user_to_db(event.new_chat_member.user.id, event.new_chat_member.user.username,
                         event.new_chat_member.user.full_name, event.chat.id)
    logger.info(f"User {event.new_chat_member.user.full_name} added to chat {event.chat.id}")

# Обработка удаления участника
@router.chat_member(ChatMemberUpdatedFilter(LEAVE_TRANSITION))
async def on_user_leave(event: types.ChatMemberUpdated):
    await remove_user_from_db(event.new_chat_member.user.id, event.chat.id)
    logger.info(f"User {event.new_chat_member.user.full_name} removed from chat {event.chat.id}")


@router.message(Command("test_router"))
async def test_router(message: types.Message):
    await message.reply("Роутер работает")


@router.message()
async def all_messages_handler(message: types.Message):
    logger.info(f"Unhandled message: {message}")
    await message.reply("Говно")