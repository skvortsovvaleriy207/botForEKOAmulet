import logging
import asyncio
from telethon import TelegramClient, events
from telethon.tl.types import User, Chat, Channel
import config
import db

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

client = TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH)

async def list_chats():
    """Получает и выводит список доступных диалогов."""
    logging.info("Получение списка чатов...")
    dialogs = await client.get_dialogs()
    print("\n--- Список чатов ---")
    for i, dialog in enumerate(dialogs[:20]): # Показываем первые 20
        print(f"{i + 1}. {dialog.name} (ID: {dialog.id})")
    print("--------------------\n")
    return dialogs

async def dump_messages(chat, limit=100):
    """Собирает последние N сообщений из чата и сохраняет их в БД."""
    logging.info(f"Сбор {limit} сообщений из чата: {chat.name}...")
    count = 0
    async for message in client.iter_messages(chat, limit=limit):
        sender = await message.get_sender()
        sender_name = "Unknown"
        if sender:
             if isinstance(sender, User):
                 sender_name = f"{sender.first_name} {sender.last_name or ''}".strip()
             elif isinstance(sender, (Chat, Channel)):
                 sender_name = sender.title
        
        msg_data = {
            'id': message.id,
            'chat_id': chat.id,
            'sender': sender_name,
            'text': message.text or "",
            'date': str(message.date)
        }
        await db.save_message(msg_data)
        count += 1
    
    logging.info(f"Сохранено {count} сообщений из {chat.name}.")

@client.on(events.NewMessage)
async def handler(event):
    """Асинхронный обработчик новых сообщений."""
    chat = await event.get_chat()
    sender = await event.get_sender()
    
    sender_name = "Unknown"
    if sender:
            if isinstance(sender, User):
                sender_name = f"{sender.first_name} {sender.last_name or ''}".strip()
            elif isinstance(sender, (Chat, Channel)):
                sender_name = sender.title

    chat_title = chat.title if hasattr(chat, 'title') else "Private Chat"
    
    # Лог в консоль
    print(f"[{chat_title}] {sender_name}: {event.text[:50]}...") # Обрезаем длинные сообщения для лога

    # Сохранение в БД
    msg_data = {
        'id': event.id,
        'chat_id': chat.id,
        'sender': sender_name,
        'text': event.text or "",
        'date': str(event.date)
    }
    await db.save_message(msg_data)

async def main():
    # Инициализация БД
    await db.init_db()
    
    # Запуск клиента
    await client.start()
    print("Клиент запущен.")

    # 1. Получить список чатов
    dialogs = await list_chats()
    
    if not dialogs:
        print("Чаты не найдены.")
        return

    # Пример интерактивности для демонстрации (или можно захардкодить)
    try:
        choice = int(input("Введите номер чата для дампа сообщений (или 0 для пропуска): "))
        if 1 <= choice <= len(dialogs):
            selected_chat = dialogs[choice - 1]
            # 2. Собрать последние 100 сообщений
            await dump_messages(selected_chat, limit=100)
        else:
            print("Пропуск дампа сообщений.")
    except ValueError:
        print("Некорректный ввод. Пропуск дампа.")

    print("\nЗапущен live-слушатель новых сообщений. Нажмите Ctrl+C для остановки.")
    # 3. Запуск live-слушателя (client.run_until_disconnected() блокирует выполнение)
    await client.run_until_disconnected()

if __name__ == '__main__':
    # Telethon client.start() и run_until_disconnected() управляют своим event loop,
    # но так как мы используем async main, запускаем его через loop.
    # client.start() внутри async функции работает корректно.
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
