import logging
import os

import asyncpg
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

DB_HOST = os.getenv('db_host')
DB_PORT = os.getenv('db_port')
DB_USER = os.getenv('db_user')
DB_PASSWORD = os.getenv('db_password')
DB_NAME = os.getenv('db_name')

logger.debug(f"Loaded env variables for db connection: {DB_HOST}:{DB_PORT} user {DB_USER} passwd ****** db {DB_NAME}")


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
