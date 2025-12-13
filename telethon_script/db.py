import aiosqlite
import logging

DB_NAME = 'telegram_data.db'

async def init_db():
    """Инициализация базы данных: создание таблицы messages, если она не существует."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                chat_id INTEGER,
                sender TEXT,
                text TEXT,
                date TEXT
            )
        ''')
        await db.commit()
        logging.info("База данных инициализирована.")

async def save_message(message_data):
    """
    Сохраняет сообщение в базу данных.
    message_data: dict с ключами 'id', 'chat_id', 'sender', 'text', 'date'
    """
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            # Используем INSERT OR IGNORE для предотвращения дубликатов по id
            await db.execute('''
                INSERT OR IGNORE INTO messages (id, chat_id, sender, text, date)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                message_data['id'],
                message_data['chat_id'],
                message_data['sender'],
                message_data['text'],
                message_data['date']
            ))
            await db.commit()
            # logging.info(f"Сообщение {message_data['id']} сохранено.")
    except Exception as e:
        logging.error(f"Ошибка при сохранении сообщения: {e}")
