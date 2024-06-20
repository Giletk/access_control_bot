import logging

from aiogram import Router
from aiogram.filters import ChatMemberUpdatedFilter, JOIN_TRANSITION, LEAVE_TRANSITION
from aiogram.types import ChatMemberUpdated

from main import add_user_to_db, remove_user_from_db

router = Router(name=__name__)
logger = logging.getLogger(__name__)


@router.chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def on_user_join(event: ChatMemberUpdated):
    await add_user_to_db(event.new_chat_member.user.id, event.new_chat_member.user.username,
                         event.new_chat_member.user.full_name, event.chat.id)
    logger.info(f"User {event.new_chat_member.user.full_name} added to chat {event.chat.id}")


@router.chat_member(ChatMemberUpdatedFilter(LEAVE_TRANSITION))
async def on_user_leave(event: ChatMemberUpdated):
    await remove_user_from_db(event.new_chat_member.user.id, event.chat.id)
    logger.info(f"User {event.new_chat_member.user.full_name} removed from chat {event.chat.id}")
