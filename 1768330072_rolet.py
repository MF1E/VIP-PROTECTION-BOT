import json
import os
import logging
import asyncio
import random
import time
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import aiohttp
from aiohttp import web
import hashlib
import string

API_KEY = "7620878759:AAH42QLQnFUjjgfaBZGJwi4b7Clsb5d7EHc" 
IDBot = API_KEY.split(":")[0]
sudo = 7779413908 
admin_username = "zizfif" 

BASE_DIR = Path("RSHQ/ALLS")
DB_DIR = BASE_DIR / IDBot
DB_FILE = DB_DIR / "raffles_db.json"

DB_DIR.mkdir(parents=True, exist_ok=True)

BACK_BTN = [{"text": "رجوع 🔙", "callback_data": "main_menu"}]

class Database:
    def __init__(self):
        self.data = self.load_data()
    
    def load_data(self):
        if not DB_FILE.exists():
            default = {
                'users': {},
                'channels': {},
                'raffles': {},
                'temp': {},
                'verified': {},
                'temp_ref': {}
            }
            self.save_data(default)
            return default
        
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def save_data(self, data=None):
        if data is None:
            data = self.data
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4, default=str)
    
    def get(self):
        return self.data
    
    def set(self, data):
        self.data = data
        self.save_data()

db = Database()

def get_boost_link(chat_id: str) -> str:
    if chat_id.startswith('@'):
        return f"https://t.me/boost/{chat_id[1:]}"
    if chat_id.startswith('-100'):
        return f"https://t.me/boost?c={chat_id[4:]}"
    return "https://t.me/boost"

async def bot(method: str, data: Dict = None) -> Dict:
    url = f"https://api.telegram.org/bot{API_KEY}/{method}"
    
    async with aiohttp.ClientSession() as session:
        if data:
            form_data = aiohttp.FormData()
            for key, value in data.items():
                if value is not None:
                    form_data.add_field(key, str(value))
            
            async with session.post(url, data=form_data) as response:
                return await response.json()
        else:
            async with session.get(url) as response:
                return await response.json()

def get_raffle_text(settings: Dict, bot_user: str) -> str:
    cond = settings.get('condition')
    cond_text = "بدون شروط"
    target_display = "مفتوح للجميع"
    
    if cond:
        if cond['type'] == 'channel': 
            cond_text = "الإشتراك في القناة" 
            target_display = ' '.join(cond['targets'])
        elif cond['type'] == 'comment': 
            word = cond['extra'].get('btn_word', '')
            link = cond['extra'].get('post_link', '')
            cond_text = f"التعليق بـ {word}"
            if link:
                cond_text += f" <a href='{link}'>هنا</a>"
            target_display = ""
        elif cond['type'] == 'boost': 
            cond_text = "تعزيز القناة" 
            link = cond['extra'].get('boost_link', '')
            target_display = f"<a href='{link}'>إضغط هنا 👆</a>"
    
    footer = "\n\n"
    if cond:
        if cond['type'] == 'comment':
            footer += f"الشرط ↼ {cond_text}"
        else:
            footer += f"الشرط ↼ {cond_text} >> {target_display} ‹"
    else:
        footer += "الشرط ↼ بدون شروط"
    
    footer += f"\n<a href='https://t.me/{bot_user}'>روليت سراب</a> > <a href='https://t.me/nkrm_bot'>جميع السحوبات</a>"
    
    if settings.get('auto_limit', 0) > 0:
        footer += f"\n\n<blockquote>🎯 يُسحب تلقائيًا عند {settings['auto_limit']} مشارك</blockquote>"
    if settings.get('premium_only', False):
        footer += "\n\n<blockquote>🔒 هذا السحب مخصص لمستخدمي تيليجرام (المميز) فقط.</blockquote>"
    
    return settings.get('cliche_text', '') + footer

async def generate_captcha(chat_id: int, rid: str):
    emojis = ['🍎','🍌','🍒','🍉','🍇','🎱','⚽','🏀','🚗','🚕','🎯','🎲','🎮']
    target = random.choice(emojis)
    options = []
    
    for _ in range(8):
        r = random.choice(emojis)
        while r == target:
            r = random.choice(emojis)
        options.append({"text": r, "callback_data": f"cp_wr_{rid}"})
    
    options.append({"text": target, "callback_data": f"cp_ok_{rid}"})
    random.shuffle(options)
    
    grid = [options[i:i+3] for i in range(0, len(options), 3)]
    
    await bot("sendMessage", {
        "chat_id": chat_id,
        "text": f"🛡 *التحقق الأمني*\nلتأكيد أنك لست روبوت، اضغط على الإيموجي: ({target})",
        "parse_mode": "Markdown",
        "reply_markup": json.dumps({"inline_keyboard": grid})
    })

async def perform_draw(rid: str):
    data = db.get()
    if rid not in data['raffles'] or data['raffles'][rid]['status'] != 'active':
        return
    
    raffle = data['raffles'][rid]
    pool = []
    
    for p in raffle['participants']:
        for _ in range(p.get('tickets', 1)):
            pool.append(p['id'])
    
    if not pool:
        await bot("sendMessage", {
            "chat_id": raffle['owner'],
            "text": "⚠️ لا يوجد مشتركين كافيين للسحب."
        })
        return
    
    random.shuffle(pool)
    winners_ids = []
    pool_list = list(pool)
    
    num_winners = raffle['settings'].get('winners_count', 1)
    final_winners = []
    
    while len(final_winners) < num_winners and pool_list:
        winner_id = random.choice(pool_list)
        if winner_id not in winners_ids:
            winners_ids.append(winner_id)
            final_winners.append(winner_id)
        pool_list.remove(winner_id)
    
    await bot("deleteMessage", {
        "chat_id": raffle['chat_id'],
        "message_id": raffle['message_id']
    })
    
    txt = "🎆 *تم السحب! الفائزون:* 🎁\n\n"
    for w in final_winners:
        user_info = await bot("getChat", {"chat_id": w})
        name = user_info.get('result', {}).get('first_name', 'مستخدم')
        txt += f"🏆 [{name}](tg://user?id={w})\n"
        
        if str(w) in data['users']:
            data['users'][str(w)]['wins'] = data['users'][str(w)].get('wins', 0) + 1
        
        if data['users'].get(str(w), {}).get('notify', False):
            ch_info = await bot("getChat", {"chat_id": raffle['chat_id']})
            ch_title = ch_info.get('result', {}).get('title', 'القناة')
            win_msg = f"🎉 *مبروك! لقد فزت في السحب!* 🎁\n\n*معلومات السحب:*\n📺 اسم القناة: {ch_title}\n👤 المالك للتواصل: [تواصل](tg://user?id={raffle['owner']})"
            await bot("sendMessage", {
                "chat_id": w,
                "text": win_msg,
                "parse_mode": "Markdown"
            })
    
    await bot("sendMessage", {
        "chat_id": raffle['chat_id'],
        "text": txt,
        "parse_mode": "Markdown"
    })
    
    data['raffles'][rid]['status'] = 'finished'
    db.set(data)
    
    await bot("sendMessage", {
        "chat_id": raffle['owner'],
        "text": "✅ تم انهاء السحب ونشر الفائزين."
    })

async def start_command(update: Dict):
    data = db.get()
    message = update.get('message', {})
    callback_query = update.get('callback_query', {})
    
    if message:
        chat_id = message['chat']['id']
        from_id = message['from']['id']
        text = message.get('text', '')
        message_id = message.get('message_id')
        first_name = message['from'].get('first_name', '')
        username = message['from'].get('username', '')
        is_premium = message['from'].get('is_premium', False)
        is_callback = False
    elif callback_query:
        chat_id = callback_query['message']['chat']['id']
        from_id = callback_query['from']['id']
        text = callback_query.get('data', '')
        message_id = callback_query['message']['message_id']
        first_name = callback_query['from'].get('first_name', '')
        username = callback_query['from'].get('username', '')
        is_premium = callback_query['from'].get('is_premium', False)
        is_callback = True
    else:
        return
    
   
    if str(from_id) not in data['users']:
        data['users'][str(from_id)] = {
            'joined_at': time.time(),
            'draws_joined': 0,
            'wins': 0,
            'notify': False
        }
        db.set(data)
    
   
    if str(from_id) in data['temp']:
        del data['temp'][str(from_id)]
        db.set(data)
    
    msg_text = "🎉 *أهلاً بك في \"روليت سراب\"!* \n🌟 استمتع بالسحوبات والمكافآت، وابدأ الآن بالاختيار من القائمة أدناه."
    
    bot_info = await bot("getMe")
    bot_username = bot_info.get('result', {}).get('username', '')
    
    menu = {
        'inline_keyboard': [
            [{"text": "أنشأ روليت 🎰", "callback_data": "create_roulette"}],
            [{"text": "الإحصائيات 📊", "callback_data": "stats"}, 
             {"text": "تبرع 💰", "url": "https://t.me/zizfif"}],
            [{"text": "الشروط والأحكام 📜", "callback_data": "terms"}, 
             {"text": "الخصوصية 🔐", "callback_data": "privacy"}],
            [{"text": "الدعم الفني 🛠", "url": f"https://t.me/{admin_username}"}, 
             {"text": "ذكرني اذا فزت 🔔", "url": f"https://t.me/{bot_username}?start=notify"}],
            [{"text": "أنشأ مسابقة 🎉", "callback_data": "create_contest"}]
        ]
    }
    
    if is_callback:
        await bot("editMessageText", {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": msg_text,
            "parse_mode": "Markdown",
            "reply_markup": json.dumps(menu)
        })
    else:
        await bot("sendMessage", {
            "chat_id": chat_id,
            "text": msg_text,
            "parse_mode": "Markdown",
            "reply_markup": json.dumps(menu)
        })

async def stats_command(update: Dict):
    data = db.get()
    callback_query = update.get('callback_query', {})
    
    if not callback_query:
        return
    
    chat_id = callback_query['message']['chat']['id']
    from_id = callback_query['from']['id']
    message_id = callback_query['message']['message_id']
    
    my_draws = data['users'].get(str(from_id), {}).get('draws_joined', 0)
    active_raffles = 0
    top_raffle = "لا يوجد"
    max_part = 0
    
    for rid, r in data['raffles'].items():
        if r.get('status') == 'active':
            active_raffles += 1
            count = len(r.get('participants', []))
            if count > max_part:
                max_part = count
                top_raffle = r.get('settings', {}).get('title', f"سحب رقم {rid[:4]}")
    
    stats_msg = f"""📊 *الإحصائيات الخاصة بك:*

عدد السحوبات الذي أنا مشترك فيها حاليا : *{my_draws}*

أكثر السحوبات الحالية من حيث عدد المشاركين :
*{top_raffle}* ({max_part} مشترك)"""
    
    await bot("editMessageText", {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": stats_msg,
        "parse_mode": "Markdown",
        "reply_markup": json.dumps({
            "inline_keyboard": [
                [{"text": "دفع نجوم تيلجرام (20) ⭐️", "url": "https://t.me/zizfif"}],
                BACK_BTN
            ]
        })
    })

async def process_message(update: Dict):
    data = db.get()
    
    if 'message' in update:
        msg = update['message']
        chat_id = msg['chat']['id']
        text = msg.get('text', '')
        from_id = msg['from']['id']
        first_name = msg['from'].get('first_name', '')
        username = msg['from'].get('username', '')
        message_id = msg.get('message_id')
        is_premium = msg['from'].get('is_premium', False)
        
       
        if msg.get('chat', {}).get('type') == 'supergroup' and 'reply_to_message' in msg:
            reply_msg = msg['reply_to_message']
            origin_id = 0
            
            if ('forward_from_chat' in reply_msg and 
                reply_msg['forward_from_chat'].get('type') == 'channel'):
                origin_id = reply_msg.get('forward_from_message_id', 0)
            elif ('sender_chat' in reply_msg and 
                  reply_msg['sender_chat'].get('type') == 'channel'):
                origin_id = reply_msg.get('message_id', 0)
            
            if origin_id > 0:
                for rid, raffle in data['raffles'].items():
                    if (raffle.get('status') == 'active' and
                        'settings' in raffle and
                        'condition' in raffle['settings'] and
                        raffle['settings']['condition'].get('type') == 'comment'):
                        
                        cond = raffle['settings']['condition']
                        saved_post_id = cond.get('extra', {}).get('post_id', 0)
                        
                        if abs(origin_id - saved_post_id) <= 100 or origin_id == saved_post_id:
                            required_word = cond.get('extra', {}).get('btn_word', '')
                            if not required_word or required_word in text:
                                if 'verified' not in data:
                                    data['verified'] = {}
                                if str(from_id) not in data['verified']:
                                    data['verified'][str(from_id)] = {}
                                data['verified'][str(from_id)][rid] = True
                                db.set(data)
                                
                                await bot("setMessageReaction", {
                                    "chat_id": chat_id,
                                    "message_id": message_id,
                                    "reaction": json.dumps([{"type": "emoji", "emoji": "👍"}])
                                })
    
   
    if str(from_id) in data['temp']:
        temp = data['temp'][str(from_id)]
        step = temp.get('step', '')
        
        if step == 'awaiting_cliche':
            temp['cliche_text'] = text
            temp['step'] = 'selecting_condition'
            data['temp'][str(from_id)] = temp
            db.set(data)
            
            msg_cond = """🎯 *إضافة شروط للسحب*
اختر شرطًا لتحسين السحب:

1️⃣ قناة شرط: الاشتراك في قناة محددة.
2️⃣ التصويت: التصويت لمتسابق معين.
3️⃣ تعزيز القناة: تعزيز قناتك.
4️⃣ ميزة جديدة: التصويت عبر التعليقات 🆕

🔰 متاح للنسخة المدفوعة فقط.
💳 الدفع باستخدام نجوم تيليجرام."""
            
            btns = {
                "inline_keyboard": [
                    [{"text": "تعزيز قناة 🚀", "callback_data": "cond_boost"}, 
                     {"text": "قناة شرط 📢", "callback_data": "cond_channel"}],
                    [{"text": "تعليق علي منشور 💬", "callback_data": "cond_comment"}, 
                     {"text": "تصويت مسابق 🗳", "callback_data": "cond_vote"}],
                    [{"text": "تخطي ⏩", "callback_data": "cond_none"}],
                    BACK_BTN
                ]
            }
            
            await bot("sendMessage", {
                "chat_id": chat_id,
                "text": msg_cond,
                "parse_mode": "Markdown",
                "reply_markup": json.dumps(btns)
            })
            return

async def handle_callback_query(update: Dict):
    data = db.get()
    callback_query = update.get('callback_query', {})
    
    if not callback_query:
        return
    
    chat_id = callback_query['message']['chat']['id']
    from_id = callback_query['from']['id']
    text = callback_query.get('data', '')
    message_id = callback_query['message']['message_id']
    callback_id = callback_query['id']
    
   
    if text == 'create_roulette':
        kb = []
        if str(from_id) in data['channels']:
            for ch_id, ch_data in data['channels'][str(from_id)].items():
                icon = '📢' if ch_data.get('type') == 'channel' else '👥'
                kb.append([{"text": f"{icon} {ch_data.get('title', '')}", 
                           "callback_data": f"select_ch_{ch_id}"}])
        
        msg_top = """يجري تحديد القناة أو القروب للسحب.

<blockquote>تأكد أولا انك مشرف في القناة او القروب وان البوت أيضا مشرف</blockquote>
<blockquote>إذا لم تظهر القناة أو الجروب وتأكدت ان البوت بها كمشرف وأنت كمشرف إذا يمكنك تسجيله يدويا من الأسفل</blockquote>"""
        
        kb.append([{"text": "تسجيل القناة 📢", "callback_data": "add_new_channel"}, 
                   {"text": "تسجيل قروب 👥", "callback_data": "add_new_group"}])
        kb.append(BACK_BTN)
        
        await bot("editMessageText", {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": msg_top,
            "parse_mode": "HTML",
            "reply_markup": json.dumps({"inline_keyboard": kb})
        })
        return
    
   
    elif text in ['cond_channel', 'cond_boost', 'cond_vote', 'cond_comment', 'cond_none']:
        if text == 'cond_none':
            if str(from_id) in data['temp']:
                data['temp'][str(from_id)]['condition'] = None
                data['temp'][str(from_id)]['step'] = 'awaiting_winners_count'
                db.set(data)
                
                await bot("editMessageText", {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": "يرجي ادخال عدد الفائزين",
                    "reply_markup": json.dumps({"inline_keyboard": [BACK_BTN]})
                })
            return
        
        type_map = {
            'cond_channel': 'channel',
            'cond_boost': 'boost',
            'cond_vote': 'vote',
            'cond_comment': 'comment'
        }
        cond_type = type_map[text]
        
        if str(from_id) in data['temp']:
            data['temp'][str(from_id)]['cond_type'] = cond_type
            data['temp'][str(from_id)]['step'] = 'awaiting_condition_link'
            db.set(data)
            
            if cond_type == 'comment':
                prompt = """لقد اخترت التصويت عبر التعليقات كشرط للمشاركة في السحب!

💬 *الآن، ارسل لي الرابط الذي تريد من المشاركين التصويت له وسأقوم بتفعيل الشرط!*

⚠️ لن يُسمح لأي شخص بالمشاركة في السحب قبل أن يقوم بالتعليق أو التصويت للمتسابق المحدد!

<blockquote>📌 ملاحظة: يجب أن يكون هذا البوت مشرفًا في القناة لكي يتم تفعيل التصويت.</blockquote>"""
                
                await bot("editMessageText", {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": prompt,
                    "parse_mode": "HTML",
                    "reply_markup": json.dumps({"inline_keyboard": [BACK_BTN]})
                })
            else:
                prompt = "أرسل المعرف/الرابط"
                if cond_type == 'boost':
                    prompt = "🚀 *شرط التعزيز:*\nأرسل معرف القناة المراد تعزيزها."
                elif cond_type == 'vote':
                    prompt = "🗳 *شرط التصويت:*\nأرسل كود المتسابق."
                
                await bot("editMessageText", {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": prompt,
                    "parse_mode": "Markdown",
                    "reply_markup": json.dumps({"inline_keyboard": [BACK_BTN]})
                })
        return
    
   
    elif text.startswith('join_'):
        rid = text.replace('join_', '')
        await process_join(chat_id, from_id, rid, False, callback_id)
        return
    
   
    elif text.startswith('draw_') or text.startswith('stop_'):
        rid = text.replace('draw_', '').replace('stop_', '')
        
        if rid not in data['raffles']:
            await bot("answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "السحب غير موجود",
                "show_alert": True
            })
            return
        
        if data['raffles'][rid]['owner'] == from_id or from_id == sudo:
            if text.startswith('draw_'):
                await perform_draw(rid)
                await bot("answerCallbackQuery", {
                    "callback_query_id": callback_id,
                    "text": "جاري السحب...",
                    "show_alert": False
                })
            else:
                data['raffles'][rid]['status'] = 'stopped'
                db.set(data)
                await bot("deleteMessage", {
                    "chat_id": data['raffles'][rid]['chat_id'],
                    "message_id": data['raffles'][rid]['message_id']
                })
                await bot("sendMessage", {
                    "chat_id": chat_id,
                    "text": "🛑 تم إيقاف السحب وحذفه."
                })
        else:
            await bot("answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": "عذراً، هذا الخيار لمنشئ السحب فقط! 🚫",
                "show_alert": True
            })
        return
    
   
    elif text.startswith('cp_ok_'):
        rid = text.replace('cp_ok_', '')
        await bot("deleteMessage", {
            "chat_id": chat_id,
            "message_id": message_id
        })
        await process_join(chat_id, from_id, rid, True, callback_id)
        return
    
    elif text.startswith('cp_wr_'):
        await bot("answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "❌ خطأ! حاول مرة أخرى.",
            "show_alert": True
        })
        await bot("deleteMessage", {
            "chat_id": chat_id,
            "message_id": message_id
        })
        return

async def process_join(chat_id: int, from_id: int, rid: str, is_private: bool, callback_id: str = None):
    data = db.get()
    
    if rid not in data['raffles']:
        msg = "❌ السحب غير موجود أو تم حذفه."
        if is_private:
            await bot("sendMessage", {"chat_id": chat_id, "text": msg})
        else:
            await bot("answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": msg,
                "show_alert": True
            })
        return
    
    raffle = data['raffles'][rid]
    
   
    for p in raffle.get('participants', []):
        if p['id'] == from_id:
            msg = "⚠️ أنت مشترك بالفعل في هذا السحب."
            if is_private:
                await bot("sendMessage", {"chat_id": chat_id, "text": msg})
            else:
                await bot("answerCallbackQuery", {
                    "callback_query_id": callback_id,
                    "text": msg,
                    "show_alert": True
                })
            return
    
   
    user_info = await bot("getChat", {"chat_id": from_id})
    is_premium = user_info.get('result', {}).get('is_premium', False)
    
    if raffle['settings'].get('premium_only', False) and not is_premium:
        msg = "🚫 عذراً، هذا السحب مخصص لمشتركي Telegram Premium فقط!"
        if is_private:
            await bot("sendMessage", {"chat_id": chat_id, "text": msg})
        else:
            await bot("answerCallbackQuery", {
                "callback_query_id": callback_id,
                "text": msg,
                "show_alert": True
            })
        return
    
   
    settings = raffle['settings']
    if 'condition' in settings and settings['condition']:
        cond = settings['condition']
        
        if cond['type'] in ['channel', 'boost']:
            for ch in cond.get('targets', []):
                stat = await bot("getChatMember", {
                    "chat_id": ch,
                    "user_id": from_id
                })
                if not stat.get('ok') or stat['result']['status'] in ['left', 'kicked']:
                    msg = f"⚠️ يجب عليك الاشتراك في القناة: {ch}"
                    if is_private:
                        await bot("sendMessage", {"chat_id": chat_id, "text": msg})
                    else:
                        await bot("answerCallbackQuery", {
                            "callback_query_id": callback_id,
                            "text": msg,
                            "show_alert": True
                        })
                    return
        
        elif cond['type'] == 'comment':
            if not data.get('verified', {}).get(str(from_id), {}).get(rid, False):
                msg = "⚠️ لم تقم بالتعليق المطلوب!\nاضغط على رابط المهمة، اكتب التعليق، ثم عد واضغط مشاركة."
                if is_private:
                    await bot("sendMessage", {"chat_id": chat_id, "text": msg})
                else:
                    await bot("answerCallbackQuery", {
                        "callback_query_id": callback_id,
                        "text": msg,
                        "show_alert": True
                    })
                return
    
   
    tickets = 1
    if str(from_id) in data['temp_ref']:
       
        tickets = 1
        del data['temp_ref'][str(from_id)]
    
    user_data = await bot("getChat", {"chat_id": from_id})
    first_name = user_data.get('result', {}).get('first_name', '')
    
    if 'participants' not in raffle:
        raffle['participants'] = []
    
    raffle['participants'].append({
        'id': from_id,
        'tickets': tickets,
        'name': first_name
    })
    
    data['raffles'][rid] = raffle
    
    if str(from_id) in data['users']:
        data['users'][str(from_id)]['draws_joined'] = data['users'][str(from_id)].get('draws_joined', 0) + 1
    
    db.set(data)
    
   
    count = len(raffle['participants'])
    bot_info = await bot("getMe")
    bot_username = bot_info.get('result', {}).get('username', '')
    share_link = f"https://t.me/{bot_username}?start=join_{rid}_{from_id}"
    notify_link = f"https://t.me/{bot_username}?start=notify"
    
    join_btn = {
        "text": f"المشاركة في السحب [{count}]",
        "url": share_link
    } if settings.get('rshq', False) else {
        "text": f"المشاركة في السحب [{count}]",
        "callback_data": f"join_{rid}"
    }
    
    kb = {
        "inline_keyboard": [
            [join_btn],
            [{"text": "أوقف المشاركة", "callback_data": f"stop_{rid}"}, 
             {"text": "ابدأ السحب", "callback_data": f"draw_{rid}"}],
            [{"text": "🆕 إعادة النشر", "callback_data": f"repost_{rid}"}, 
             {"text": "مشاركة السحب ↗️", "url": f"https://t.me/share/url?url={share_link}"}],
            [{"text": "🔔 ذكرني إذا فزت", "url": notify_link}]
        ]
    }
    
    await bot("editMessageReplyMarkup", {
        "chat_id": raffle['chat_id'],
        "message_id": raffle['message_id'],
        "reply_markup": json.dumps(kb)
    })
    
   
    ch_title = settings.get('chat_title', 'القناة')
    success_text = f"✅ تم اشتراكك بنجاح في سحب قناة: {ch_title}\n\n🎁 نظام الدعوات مفعل في هذا السحب.\n👥 كل شخص يدخل السحب من خلال مشاركتك\n🎟 يمنحك: 1 تذكرة إضافية"
    
    if is_private:
        await bot("sendMessage", {
            "chat_id": chat_id,
            "text": success_text
        })
    else:
        await bot("answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": "✅ تم تسجيل اشتراكك بنجاح!",
            "show_alert": False
        })
    
   
    owner_msg = f"""🎟 *مشاركة جديدة في سحبك!*

👤 المستخدم: [{first_name}](tg://user?id={from_id})
🆔 المعرف: `{from_id}`
📅 تاريخ المشاركة: {datetime.now().strftime('%Y-%m-%d %H:%M')}
🔢 عدد المشاركين: {count}"""
    
    await bot("sendMessage", {
        "chat_id": raffle['owner'],
        "text": owner_msg,
        "parse_mode": "Markdown",
        "reply_markup": json.dumps({
            "inline_keyboard": [[{
                "text": "عرض الملف الشخصي 👤",
                "url": f"tg://user?id={from_id}"
            }]]
        })
    })
    
   
    if settings.get('auto_limit', 0) > 0 and count >= settings['auto_limit']:
        await perform_draw(rid)

async def handle_update(request):
    try:
        update = await request.json()
        
        if 'message' in update:
           
            msg = update['message']
            text = msg.get('text', '')
            
            if text.startswith('/start'):
                if 'notify' in text:
                   
                    from_id = msg['from']['id']
                    data = db.get()
                    if str(from_id) in data['users']:
                        data['users'][str(from_id)]['notify'] = True
                        db.set(data)
                    
                    await bot("sendMessage", {
                        "chat_id": msg['chat']['id'],
                        "text": "✅ *تم تفعيل الاشعارات!*\nستتلقى اشعارات اذا فزت في السحب في اي قناه شاركت فيها، بشرط لا تحذف المحادثه مع البوت.",
                        "parse_mode": "Markdown"
                    })
                elif 'join_' in text:
                   
                    parts = text.replace('/start join_', '').split('_')
                    rid = parts[0]
                    referrer = parts[1] if len(parts) > 1 else None
                    
                    if referrer and int(referrer) != msg['from']['id']:
                        data = db.get()
                        data['temp_ref'][str(msg['from']['id'])] = referrer
                        db.set(data)
                    
                    await generate_captcha(msg['chat']['id'], rid)
                else:
                    await start_command(update)
            else:
                await process_message(update)
        
        elif 'callback_query' in update:
            await handle_callback_query(update)
        
        return web.Response(text='OK')
    
    except Exception as e:
        logging.error(f"Error handling update: {e}")
        return web.Response(text='ERROR', status=500)

async def main():
    app = web.Application()
    app.router.add_post(f'/{API_KEY}', handle_update)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    
    print("Bot is running on port 8080...")
    
   
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
   
    asyncio.run(main())