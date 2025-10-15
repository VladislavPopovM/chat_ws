import asyncio
import datetime
import os
import signal
import sys
import argparse
import aiofiles


class ChatLogger:
    def __init__(self, log_file="chat.txt"):
        self.log_file = log_file
        self._file_handle = None
    
    async def ensure_log_file(self):
        """Создаем файл лога если его нет (асинхронно)"""
        if not os.path.exists(self.log_file):
            async with aiofiles.open(self.log_file, 'w', encoding='utf-8') as f:
                await f.write("")
    
    async def log_message(self, message):
        """Асинхронно записываем сообщение в файл и выводим в консоль"""
        timestamp = datetime.datetime.now().strftime("[%d.%m.%y %H:%M]")
        log_entry = f"{timestamp} {message}"
        
        # Выводим в консоль
        print(log_entry)
        
        # Асинхронно записываем в файл в append режиме
        try:
            async with aiofiles.open(self.log_file, 'a', encoding='utf-8') as f:
                await f.write(log_entry + '\n')
        except Exception as e:
            print(f"Ошибка записи в файл: {e}")
    
    async def close(self):
        """Закрываем файловый дескриптор если он открыт"""
        if self._file_handle:
            await self._file_handle.close()


def parse_arguments():
    """Парсинг аргументов командной строки с поддержкой переменных окружения"""
    parser = argparse.ArgumentParser(
        description='Слушатель чата minechat с сохранением истории',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python3 listen-minechat.py --host example.com --port 5000 --history chat.txt
  python3 listen-minechat.py --host 192.168.0.1 --port 5001 --history ~/minechat.history
  
Переменные окружения:
  MINECHAT_HOST     - хост сервера
  MINECHAT_PORT     - порт сервера
  MINECHAT_HISTORY  - путь к файлу истории
        """
    )
    
    parser.add_argument(
        '--host',
        default=os.getenv('MINECHAT_HOST', ''),
        help='Хост сервера minechat'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=int(os.getenv('MINECHAT_PORT', '0')),
        help='Порт сервера minechat'
    )
    
    parser.add_argument(
        '--history',
        default=os.getenv('MINECHAT_HISTORY', ''),
        help='Путь к файлу с историей переписки'
    )
    
    args = parser.parse_args()
    
    # Валидация обязательных параметров
    if not args.host:
        parser.error("Хост обязателен. Используйте --host или переменную MINECHAT_HOST")
    if not args.port:
        parser.error("Порт обязателен. Используйте --port или переменную MINECHAT_PORT")
    if not args.history:
        parser.error("Файл истории обязателен. Используйте --history или переменную MINECHAT_HISTORY")
    
    return args


async def minechat_client(host, port, history_file):
    """
    Подключение к серверу minechat и обработка потока сообщений
    
    Args:
        host (str): Хост сервера
        port (int): Порт сервера
        history_file (str): Путь к файлу истории
    """
    logger = ChatLogger(history_file)
    await logger.ensure_log_file()  # Инициализируем файл асинхронно
    
    reader = None
    writer = None
    
    while True:  # Бесконечный цикл для переподключения
        try:
            await logger.log_message(f"Подключение к {host}:{port}...")
            
            # Устанавливаем таймаут для подключения
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=10.0
            )
            await logger.log_message(f"Соединение установлено с {host}:{port}")
            
            # Читаем сообщения из чата
            message_count = 0
            async for line in reader:
                message = line.decode('utf-8', errors='ignore').rstrip()
                if message:  # Игнорируем пустые строки
                    await logger.log_message(message)
                    message_count += 1
            
            # Если соединение закрылось без сообщений
            if message_count == 0:
                await logger.log_message("Соединение закрыто сервером без отправки данных")
                
        except asyncio.TimeoutError:
            await logger.log_message(f"Таймаут подключения к {host}:{port}")
            await logger.log_message("Попытка переподключения через 5 секунд...")
            await asyncio.sleep(5)
            continue
        except asyncio.IncompleteReadError as e:
            await logger.log_message(f"Неполное чтение: {e.partial.decode('utf-8', errors='ignore')}")
        except (ConnectionRefusedError, OSError) as e:
            await logger.log_message(f"Ошибка подключения: {e}")
            await logger.log_message("Попытка переподключения через 5 секунд...")
            await asyncio.sleep(5)
            continue
        except (ConnectionError, OSError) as e:
            await logger.log_message(f"Потеряно соединение: {e}")
            await logger.log_message("Попытка переподключения через 5 секунд...")
            await asyncio.sleep(5)
            continue
        except Exception as e:
            await logger.log_message(f"Неожиданная ошибка: {e}")
            await logger.log_message("Попытка переподключения через 5 секунд...")
            await asyncio.sleep(5)
            continue
        finally:
            if writer and not writer.is_closing():
                await logger.log_message("Закрытие соединения...")
                writer.close()
                await writer.wait_closed()
    
    # Закрываем логгер при завершении
    await logger.close()


def signal_handler(signum, frame):
    """Обработчик сигналов для корректного завершения"""
    print("\nЗавершение работы...")
    sys.exit(0)


def main():
    """Главная функция приложения"""
    # Парсим аргументы командной строки
    args = parse_arguments()
    
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print(f"Запуск слушателя чата:")
    print(f"  Хост: {args.host}")
    print(f"  Порт: {args.port}")
    print(f"  Файл истории: {args.history}")
    print("Нажмите Ctrl+C для завершения")
    print("=" * 50)
    
    try:
        asyncio.run(minechat_client(args.host, args.port, args.history))
    except KeyboardInterrupt:
        print("\nПрограмма завершена пользователем")
    except Exception as e:
        print(f"Критическая ошибка: {e}")


if __name__ == "__main__":
    main()