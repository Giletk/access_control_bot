__all__ = ("router",)

from aiogram import Router

from .member_updates import router as member_update_router
from .misc import router as misc_router

router = Router(name=__name__)
router.include_router(member_update_router)
router.include_router(misc_router)
