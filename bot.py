# bot.py - ВЕРСИЯ ДЛЯ RENDER.COM

import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id
from vk_api.upload import VkUpload
import sqlite3
from datetime import datetime
import requests
import os
import time
import json

# =============== НАСТРОЙКИ ===============
VK_TOKEN = "vk1.a.QQWB180nLf9tYPVKIFJkmdV1XaPLVSCQpvJ2qXC893iyPWxudhbllTn5LUZ_ORFShWEAusglHkbFcwsERImCmFyDKKjMJhc-IF8qNBse4-6dzxukbLBORxU2W6BZEVr22IGpiISf1XHB22nZccW0qtzb_4TAWp0rKKbnwVQA6hZhNyxyCWxVD6jSv7lEdMCoxoJMR2uX_ajPDvtZY_nGYg"
GROUP_ID = "2000000105"  # Например "-123456789"

TASKS = {
    "Понедельник": ["Огнетушители", "Тележки", "Коробки", "Ножи"],
    "Вторник": ["Холодильники", "Полки", "Инвентарь"],
    "Среда": ["Окна", "Двери", "Освещение"],
    "Четверг": ["Склад", "Мусор", "Документы"],
    "Пятница": ["Оборудование", "Столы", "Стулья"],
    "Суббота": ["Генеральная уборка"],
    "Воскресенье": ["Отдых"]
}

USER_STATES = {}

# =============== БАЗА ДАННЫХ ===============
def init_database():
    conn = sqlite3.connect('bot_database.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            vk_id INTEGER PRIMARY KEY,
            name TEXT,
            register_date TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS completed_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vk_id INTEGER,
            task_name TEXT,
            task_date TEXT,
            completed_at TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ База данных готова")

# =============== ОТПРАВКА СООБЩЕНИЙ ===============
def send_message(vk, user_id, message, keyboard=None):
    try:
        params = {
            'user_id': user_id,
            'message': message,
            'random_id': get_random_id()
        }
        
        if keyboard:
            params['keyboard'] = keyboard.get_keyboard()
        
        vk.messages.send(**params)
        print(f"✅ Отправлено {user_id}: {message[:30]}...")
        return True
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        return False

# =============== ОТПРАВКА ФОТО В ГРУППУ ===============
def send_photos_to_group(vk, photo_paths, caption):
    try:
        upload = VkUpload(vk)
        attachments = []
        
        for photo_path in photo_paths:
            if os.path.exists(photo_path):
                photo = upload.photo_messages(photo_path)
                attachments.append(f"photo{photo[0]['owner_id']}_{photo[0]['id']}")
        
        if attachments:
            vk.messages.send(
                peer_id=int(GROUP_ID),
                message=caption,
                attachment=','.join(attachments),
                random_id=get_random_id()
            )
            print(f"✅ Фото отправлены в группу")
            return True
    except Exception as e:
        print(f"❌ Ошибка отправки фото в группу: {e}")
        return False

# =============== СОХРАНЕНИЕ ФОТО ===============
def save_photo_from_event(event, user_id, task_name, photo_type):
    try:
        if not os.path.exists('photos'):
            os.makedirs('photos')
        
        if not hasattr(event, 'attachments') or not event.attachments:
            return None
        
        photo_url = None
        
        for att in event.attachments:
            if isinstance(att, dict) and att.get('type') == 'photo':
                photo_data = att.get('photo', {})
                
                if 'sizes' in photo_data:
                    sizes = photo_data['sizes']
                    if sizes:
                        max_size = max(sizes, key=lambda x: x.get('height', 0))
                        photo_url = max_size['url']
                        break
                elif 'url' in photo_data:
                    photo_url = photo_data['url']
                    break
        
        if not photo_url:
            return None
        
        response = requests.get(photo_url, timeout=10)
        if response.status_code != 200:
            return None
        
        timestamp = int(time.time())
        safe_task_name = task_name.replace(' ', '_')
        filename = f"photos/{user_id}_{safe_task_name}_{photo_type}_{timestamp}.jpg"
        
        with open(filename, 'wb') as f:
            f.write(response.content)
        
        print(f"✅ Фото сохранено: {filename}")
        return filename
        
    except Exception as e:
        print(f"❌ Ошибка сохранения фото: {e}")
        return None

# =============== КЛАВИАТУРА ===============
def get_main_keyboard(day, completed_tasks=None):
    keyboard = VkKeyboard(inline=True)
    tasks = TASKS.get(day, ["Отдых"])
    
    if completed_tasks is None:
        completed_tasks = []
    
    for i, task in enumerate(tasks):
        if task in completed_tasks:
            keyboard.add_button(f"✅ {task}", color=VkKeyboardColor.POSITIVE)
        else:
            keyboard.add_button(f"🔴 {task}", color=VkKeyboardColor.NEGATIVE)
        
        if (i + 1) % 2 == 0 and i != len(tasks) - 1:
            keyboard.add_line()
    
    return keyboard

def get_weekday():
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    return days[datetime.now().weekday()]

# =============== РАБОТА С БД ===============
def get_completed_tasks(user_id, day):
    try:
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT task_name FROM completed_tasks 
            WHERE vk_id = ? AND task_date = ?
        ''', (user_id, day))
        completed = [row[0] for row in cursor.fetchall()]
        conn.close()
        return completed
    except Exception as e:
        print(f"Ошибка БД: {e}")
        return []

def save_completed_task(user_id, task_name, task_date):
    try:
        conn = sqlite3.connect('bot_database.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO completed_tasks (vk_id, task_name, task_date, completed_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, task_name, task_date, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка сохранения: {e}")
        return False

# =============== ОСНОВНАЯ ФУНКЦИЯ ===============
def main():
    print("=" * 50)
    print("🚀 ЗАПУСК БОТА")
    print("=" * 50)
    
    init_database()
    
    # Несколько попыток подключения
    max_retries = 5
    for attempt in range(max_retries):
        try:
            vk_session = vk_api.VkApi(token=VK_TOKEN)
            vk = vk_session.get_api()
            vk.users.get()
            print(f"✅ Токен работает")
            
            longpoll = VkLongPoll(vk_session)
            print("✅ БОТ ГОТОВ К РАБОТЕ!")
            print("=" * 50)
            break
        except Exception as e:
            print(f"⚠️ Попытка {attempt + 1}/{max_retries} не удалась: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                print("❌ Не удалось подключиться после всех попыток")
                return
    
    # Основной цикл с обработкой ошибок
    while True:
        try:
            for event in longpoll.listen():
                if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                    user_id = event.user_id
                    text = event.text.lower().strip()
                    
                    print(f"\n📨 Сообщение от {user_id}: {text}")
                    
                    # ПРИВЕТСТВИЕ
                    if text in ["начать", "привет", "меню", "start"]:
                        day = get_weekday()
                        
                        try:
                            user_info = vk.users.get(user_ids=user_id)
                            user_name = user_info[0]['first_name'] if user_info else "друг"
                        except:
                            user_name = "друг"
                        
                        completed = get_completed_tasks(user_id, day)
                        keyboard = get_main_keyboard(day, completed)
                        
                        send_message(vk, user_id, f"👋 Привет, {user_name}!\n📋 Задания на {day}:", keyboard)
                    
                    # ВЫБОР ЗАДАНИЯ
                    elif any(task.lower() in text.replace('🔴', '').replace('✅', '').strip() 
                            for day_tasks in TASKS.values() for task in day_tasks):
                        
                        clean_text = text.replace('🔴', '').replace('✅', '').strip()
                        
                        task_name = None
                        for day_tasks in TASKS.values():
                            for task in day_tasks:
                                if task.lower() == clean_text:
                                    task_name = task
                                    break
                        
                        if task_name:
                            day = get_weekday()
                            completed = get_completed_tasks(user_id, day)
                            
                            if task_name in completed:
                                send_message(vk, user_id, f"❌ '{task_name}' уже выполнено сегодня!")
                            else:
                                USER_STATES[user_id] = {
                                    'task': task_name,
                                    'step': 'waiting_before',
                                    'photo_before': None
                                }
                                send_message(vk, user_id, f"📸 Отправь фото ДО уборки '{task_name}'")
                    
                    # ОБРАБОТКА ФОТО
                    elif user_id in USER_STATES:
                        state = USER_STATES[user_id]
                        
                        if not event.attachments:
                            send_message(vk, user_id, "❌ Отправь фото!")
                            continue
                        
                        if state['step'] == 'waiting_before':
                            photo_path = save_photo_from_event(event, user_id, state['task'], 'before')
                            
                            if photo_path:
                                state['photo_before'] = photo_path
                                state['step'] = 'waiting_after'
                                send_message(vk, user_id, f"✅ Фото ДО получено!\n📸 Теперь отправь фото ПОСЛЕ уборки '{state['task']}'")
                            else:
                                send_message(vk, user_id, "❌ Не удалось сохранить фото. Попробуй еще раз.")
                        
                        elif state['step'] == 'waiting_after':
                            photo_path = save_photo_from_event(event, user_id, state['task'], 'after')
                            
                            if photo_path:
                                try:
                                    user_info = vk.users.get(user_ids=user_id)
                                    user_name = f"{user_info[0]['first_name']} {user_info[0]['last_name']}"
                                except:
                                    user_name = f"id{user_id}"
                                
                                caption = (f"✅ Выполнено: {state['task']}\n"
                                          f"Исполнитель: {user_name}\n"
                                          f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
                                
                                send_photos_to_group(vk, [state['photo_before'], photo_path], caption)
                                
                                day = get_weekday()
                                save_completed_task(user_id, state['task'], day)
                                
                                task_name = state['task']
                                del USER_STATES[user_id]
                                
                                completed = get_completed_tasks(user_id, day)
                                keyboard = get_main_keyboard(day, completed)
                                
                                if len(completed) == len(TASKS.get(day, [])):
                                    send_message(vk, user_id, "🎉 Поздравляю! Все задания на сегодня выполнены!", keyboard)
                                else:
                                    send_message(vk, user_id, f"✅ '{task_name}' выполнено! Можешь делать следующее:", keyboard)
                            else:
                                send_message(vk, user_id, "❌ Не удалось сохранить фото. Попробуй еще раз.")
                    
                    # НЕИЗВЕСТНАЯ КОМАНДА
                    else:
                        send_message(vk, user_id, "❌ Напиши 'Привет' чтобы начать")
        
        except Exception as e:
            print(f"⚠️ Ошибка в цикле: {e}")
            print("🔄 Переподключаюсь через 10 секунд...")
            time.sleep(10)
            
            # Переподключение
            try:
                vk_session = vk_api.VkApi(token=VK_TOKEN)
                vk = vk_session.get_api()
                longpoll = VkLongPoll(vk_session)
                print("✅ Переподключение успешно!")
            except:
                print("❌ Ошибка переподключения")

# =============== ЗАПУСК ===============
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
