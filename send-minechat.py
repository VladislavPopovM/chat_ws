#!/usr/bin/env python3
"""
Скрипт для отправки сообщений в minechat с автоматической авторизацией
"""

import asyncio
import json
import os
import sys
import argparse
import aiofiles
from typing import Optional


class MinechatSender:
    def __init__(self, host: str, port: int, hash_file: str = "account.hash"):
        self.host = host
        self.port = port
        self.hash_file = hash_file
        self.account_hash: Optional[str] = None
        self.nickname: Optional[str] = None
        
    async def load_hash(self) -> bool:
        """Загружаем сохраненный hash из файла"""
        try:
            if os.path.exists(self.hash_file):
                async with aiofiles.open(self.hash_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    if content.strip():
                        self.account_hash = content.strip()
                        print(f"Загружен hash: {self.account_hash}")
                        return True
        except Exception as e:
            print(f"Ошибка загрузки hash: {e}")
        return False
    
    async def save_hash(self, hash_value: str):
        """Сохраняем hash в файл"""
        try:
            async with aiofiles.open(self.hash_file, 'w', encoding='utf-8') as f:
                await f.write(hash_value)
            print(f"Hash сохранен в {self.hash_file}")
        except Exception as e:
            print(f"Ошибка сохранения hash: {e}")
    
    async def register_account(self, reader, writer) -> tuple[str, str]:
        """Регистрируем новый аккаунт"""
        print("Регистрация нового аккаунта...")
        
        # Читаем приветствие
        greeting = await reader.readline()
        print(greeting.decode('utf-8').strip())
        
        # Отправляем пустой hash для регистрации
        writer.write(b'\n')
        await writer.drain()
        
        # Читаем запрос никнейма
        nickname_prompt = await reader.readline()
        print(nickname_prompt.decode('utf-8').strip())
        
        # Вводим никнейм
        nickname = input("Введите никнейм: ").strip()
        if not nickname:
            nickname = "Anonymous"
        
        writer.write(f"{nickname}\n".encode('utf-8'))
        await writer.drain()
        
        # Читаем ответ с данными аккаунта
        response = await reader.readline()
        account_data = json.loads(response.decode('utf-8').strip())
        
        account_hash = account_data['account_hash']
        nickname = account_data['nickname']
        
        print(f"Аккаунт создан: {nickname}")
        print(f"Hash: {account_hash}")
        
        # Сохраняем hash
        await self.save_hash(account_hash)
        
        return account_hash, nickname
    
    async def login_with_hash(self, reader, writer) -> bool:
        """Авторизуемся с существующим hash"""
        print("Авторизация с существующим hash...")
        
        # Читаем приветствие
        greeting = await reader.readline()
        print(greeting.decode('utf-8').strip())
        
        # Отправляем hash
        writer.write(f"{self.account_hash}\n".encode('utf-8'))
        await writer.drain()
        
        # Читаем ответ
        response = await reader.readline()
        try:
            account_data = json.loads(response.decode('utf-8').strip())
            self.nickname = account_data['nickname']
            print(f"Авторизация успешна: {self.nickname}")
            return True
        except json.JSONDecodeError:
            print("Ошибка авторизации, возможно hash неверный")
            return False
    
    async def connect_and_auth(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Подключаемся и авторизуемся"""
        print(f"Подключение к {self.host}:{self.port}...")
        
        reader, writer = await asyncio.open_connection(self.host, self.port)
        print("Соединение установлено")
        
        # Пытаемся авторизоваться с существующим hash
        if self.account_hash and await self.login_with_hash(reader, writer):
            return reader, writer
        
        # Если авторизация не удалась, регистрируемся
        writer.close()
        await writer.wait_closed()
        
        print("Переподключение для регистрации...")
        reader, writer = await asyncio.open_connection(self.host, self.port)
        
        self.account_hash, self.nickname = await self.register_account(reader, writer)
        
        return reader, writer
    
    async def send_message(self, reader, writer, message: str):
        """Отправляем сообщение"""
        writer.write(f"{message}\n".encode('utf-8'))
        await writer.drain()
        
        # Читаем подтверждение
        response = await reader.readline()
        print(response.decode('utf-8').strip())
    
    async def interactive_mode(self):
        """Интерактивный режим отправки сообщений"""
        try:
            reader, writer = await self.connect_and_auth()
            
            # Читаем приветствие чата
            welcome = await reader.readline()
            print(welcome.decode('utf-8').strip())
            
            print("\nДобро пожаловать в чат!")
            print("Введите сообщение и нажмите Enter для отправки")
            print("Введите пустую строку для завершения")
            print("=" * 50)
            
            while True:
                try:
                    message = input("> ").strip()
                    if not message:
                        break
                    
                    await self.send_message(reader, writer, message)
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"Ошибка отправки сообщения: {e}")
                    break
            
        except Exception as e:
            print(f"Ошибка подключения: {e}")
        finally:
            if 'writer' in locals() and not writer.is_closing():
                writer.close()
                await writer.wait_closed()
            print("Соединение закрыто")


def parse_arguments():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description='Отправка сообщений в minechat с автоматической авторизацией',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python3 send-minechat.py --host ... --port ... --hash-file account.hash
  python3 send-minechat.py --host ... --port ... --hash-file ~/.minechat_hash

Переменные окружения:
  MINECHAT_HOST     - хост сервера
  MINECHAT_PORT     - порт сервера
  MINECHAT_HASH     - файл с hash аккаунта
        """
    )
    
    parser.add_argument(
        '--host',
        default=os.getenv('MINECHAT_HOST_WRITER', ''),
        help='Хост сервера minechat'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=int(os.getenv('MINECHAT_PORT', '0')),
        help='Порт сервера minechat'
    )
    
    parser.add_argument(
        '--hash-file',
        default=os.getenv('MINECHAT_HASH', ''),
        help='Файл для сохранения hash аккаунта'
    )
    
    args = parser.parse_args()
    
    # Валидация обязательных параметров
    if not args.host:
        parser.error("Хост обязателен. Используйте --host или переменную MINECHAT_HOST")
    if not args.port:
        parser.error("Порт обязателен. Используйте --port или переменную MINECHAT_PORT")
    if not args.hash_file:
        parser.error("Файл hash обязателен. Используйте --hash-file или переменную MINECHAT_HASH")
    
    return args


async def main():
    """Главная функция"""
    args = parse_arguments()
    
    print("Запуск отправителя сообщений:")
    print(f"  Хост: {args.host}")
    print(f"  Порт: {args.port}")
    print(f"  Файл hash: {args.hash_file}")
    print("=" * 50)
    
    sender = MinechatSender(args.host, args.port, args.hash_file)
    
    # Загружаем существующий hash
    await sender.load_hash()
    
    # Запускаем интерактивный режим
    await sender.interactive_mode()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nПрограмма завершена пользователем")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        sys.exit(1)
