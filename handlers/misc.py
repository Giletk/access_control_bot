import logging

from aiogram import Router, types
from aiogram.filters import Command, BaseFilter


class IsPrivate(BaseFilter):
    async def __call__(self, message: types.Message) -> bool:
        return message.chat.type == "private"


router = Router(name=__name__)
# Команды этого модуля работают только в ЛС с ботом
router.message.filter(IsPrivate())
logger = logging.getLogger(__name__)


@router.message(Command("dice"))
async def cmd_dice(message: types.Message):
    await message.answer_dice(emoji="🎲")


@router.message(Command("signature"))
async def cmd_dice(message: types.Message):
    await message.answer_sticker(r"CAACAgIAAxkBAAKoX2Z0u-UBmgL4N-t5NfitPhn11NiXAAIgAANWgrgYmFG7IT0BOZ01BA")
    await message.answer("This bot is made by @CO1LED")
