# bot.py
# Требуется: aiogram==3.0.0b7, aiosqlite

import asyncio
import os
import datetime as dt
import aiosqlite

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command, Text
from aiogram.types import Message, CallbackQuery
from aiogram import Bot, Dispatcher
from aiogram.utils.deep_linking import create_start_link
from aiogram.filters.command import CommandObject

from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    InputMediaPhoto,
)
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

# ===================== НАСТРОЙКИ =====================

BOT_TOKEN = os.getenv("8011648169:AAEHudcPizXPgNvYeWHOXgzKJRo3UMEkj4w") or "8011648169:AAEHudcPizXPgNvYeWHOXgzKJRo3UMEkj4w"
if not BOT_TOKEN:
    raise RuntimeError("Set BOT_TOKEN env var")

# Текст перед данными реферала в уведомлении админу/пригласившему
REF_NOTIFY_PREFIX = "🎉 По вашей реферальной ссылке зашел новый мамонт"

# админы (tg_id: метка)
ADMINS: dict[int, str] = {
    8095687296: "Основатель",
6592399633: "Оператор",
}

# username оператора для кнопки "Оператор"
OPERATOR_USERNAME = "HappyTimeOperator"

# Заглушка-фото для каталога (одно фото, чтобы редактировать в нём подпись/медиа)
CATALOG_PLACEHOLDER_FILE_ID = "AgACAgIAAxkBAAMqaQNOsRp8BJMS8gABMNNifAujuqHhAAIN-TEbjgIgSGszUidcImJUAQADAgADeAADNgQ"  # вставь свой file_id

# ===================== ДАННЫЕ =====================

CITIES = [
    "Екатеринбург", "Казань", "Москва", "Самара",
    "Санкт-Петербург", "Сочи", "Уфа", "Челябинск",
    "Нижний Новгород", "Астрахань",
]

CITY_DISTRICTS = {
    "Москва": ["Марьино", "Митино", "Люблино", "Отрадное", "Ясенево", "Новомосквовский", "Коптево", "Некрасовка","Центральный", "Чертаново", "Сокольники"],
    "Санкт-Петербург": ["Центральный", "Петроградский", "Василеостровский", "Московский", "Приморский"],
    "Екатеринбург": ["Академический", "Верх-Исетский", "Железнодорожный", "Кировский", "Ленинский", "Октябрьский","Чкаловский"],
    "Казань": ["Авиастроительный", "Вахитовский", "Кировский", "Московский", "Советский", "Приволжский","Ново-Савиновский"],
    "Самара": ["Октябрьский", "Советский", "Промышленный", "Кировский", "Куйбышевский", "Красноглинский"],
    "Сочи": ["Адлерский", "Лазаревский", "Хостинский", "Центральный"],
    "Уфа": ["Дёмский", "Калининский", "Кировский", "Ленинский", "Октябрьский", "Орджоникидзевский", "Советский"],
    "Нижний Новгород": ["Советский", "Автозаводский", "Приокский"],
    "Челябинск": ["Калининский", "Курчатовский", "Ленинский", "Металлургический", "Советский", "Тракторозаводский","Центральный"],
    "Астрахань": ["Кировский", "Ленинский", "Советский"]
}
DEFAULT_DISTRICTS = ["Скоро добавим районы"]
CITY_BY_ID = {str(i): name.strip() for i, name in enumerate(CITIES)}

WELCOME = (
    "⚡️ Добро пожаловать в магазин! ⚡️\n\n"
    "▪️ Хотите быстро получить нужный товар? Мы поможем!\n"
    "▪️ Работаем 24/7.\n"
    "▪️ Внимательно проверяйте юзернейм оператора. Мы не пишем первые.\n"
    "▪️ Если вашего города нет в каталоге — напишите оператору, поможем с предзаказом или доставкой."
)

INFO_TEXT = (
    "ℹ️ Информация ℹ️\n\n"
    "▪️ Мы заботимся о безопасности! Наши сотрудники проходят \n"
    "строгий отбор и обучение, чтобы обеспечить вам \n"
    "максимальную защиту.\n"
    "▪️ Надежные клады: Мы используем проверенные методы для \n"
    "размещения кладов, и риск их обнаружения сводится к \n"
    "минимуму (кроме форс-мажорных ситуаций, таких как \n"
    "перекопка земли).\n"
    "▪️ Качественная продукция: Каждый товар проходит двойную \n"
    "проверку - наши тестеры проверяют его перед покупкой, а \n"
    "затем еще раз после получения. Вы можете быть уверены в \n"
    "высочайшем качестве! \n"
    "▪️ Контроль качества: Работа каждого сотрудника находится \n"
    "под контролем.\n"
    "▪️ Удобное расположение: Клады в городе размещаются на \n"
    "магнитах, как правило, рядом с метро или крупными \n"
    "остановками общественного транспорта. В парках или \n"
    "малонаселенных районах клады закапываются.\n"
    "▪️ Быстрое исполнение: Персональные, комбинированные и \n"
    "оптовые заказы обрабатываются в течение 24 часов после \n"
    "оплаты. \n"
)

MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Каталог"), KeyboardButton(text="Оператор")],
        [KeyboardButton(text="Профиль"), KeyboardButton(text="Информация")],
    ],
    resize_keyboard=True
)

# ===================== БД =====================

DB_PATH = "shop.db"

CREATE_USERS_SQL = """
CREATE TABLE IF NOT EXISTS users (
    tg_id INTEGER PRIMARY KEY,
    username TEXT,
    first_seen TEXT,
    orders_count INTEGER DEFAULT 0,
    disputes_count INTEGER DEFAULT 0,
    balance INTEGER DEFAULT 0,
    inviter_id INTEGER DEFAULT NULL,
    ref_count INTEGER DEFAULT 0,
    has_ref_access INTEGER DEFAULT 0
);
"""


CREATE_PRODUCTS_SQL = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city_id TEXT NOT NULL,
    district TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    photo_file_id TEXT NOT NULL,
    created_by INTEGER,
    created_at TEXT
);
"""

async def db_init():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_USERS_SQL)
        await db.execute(CREATE_PRODUCTS_SQL)
        # Миграции (если таблички уже были, но без колонок)
        cols = [row[1] for row in await (await db.execute("PRAGMA table_info(products)")).fetchall()]
        if "description" not in cols:
            await db.execute("ALTER TABLE products ADD COLUMN description TEXT DEFAULT ''")
        cols_u = [row[1] for row in await (await db.execute("PRAGMA table_info(users)")).fetchall()]
        if "inviter_id" not in cols_u:
            await db.execute("ALTER TABLE users ADD COLUMN inviter_id INTEGER DEFAULT NULL")
        if "ref_count" not in cols_u:
            await db.execute("ALTER TABLE users ADD COLUMN ref_count INTEGER DEFAULT 0")
            # Добавляем новую колонку для доступа к реферальной системе
            if "has_ref_access" not in cols:
                await db.execute("ALTER TABLE users ADD COLUMN has_ref_access INTEGER DEFAULT 0")

        await db.commit()

async def upsert_user(tg_id: int, username: str | None):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT tg_id FROM users WHERE tg_id=?", (tg_id,))
        row = await cur.fetchone()
        if row is None:
            first_seen = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await db.execute(
                "INSERT INTO users (tg_id, username, first_seen) VALUES (?,?,?)",
                (tg_id, username or "", first_seen)
            )
        else:
            await db.execute("UPDATE users SET username=? WHERE tg_id=?", (username or "", tg_id))
        await db.commit()
async def get_user(tg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT
                username,
                first_seen,
                orders_count,
                disputes_count,
                balance,
                inviter_id,
                COALESCE(ref_count, 0) AS ref_count,
                COALESCE(has_ref_access, 0) AS has_ref_access
            FROM users
            WHERE tg_id = ?
        """, (tg_id,))
        return await cur.fetchone()

def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

# ===================== КЛАВИАТУРЫ КАТАЛОГА =====================

def cities_inline_kb(page: int = 0, per_page: int = 25) -> InlineKeyboardMarkup:
    items = list(CITY_BY_ID.items())[page*per_page:page*per_page+per_page]
    rows = [[InlineKeyboardButton(text=name, callback_data=f"city#{cid}")]
            for cid, name in items]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="« Назад", callback_data=f"page#{page-1}"))
    if (page+1)*per_page < len(CITY_BY_ID):
        nav.append(InlineKeyboardButton(text="Вперёд »", callback_data=f"page#{page+1}"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)

def districts_kb(city_id: str) -> InlineKeyboardMarkup:
    city = CITY_BY_ID[city_id]
    districts = CITY_DISTRICTS.get(city, DEFAULT_DISTRICTS)
    rows = [[InlineKeyboardButton(text=d, callback_data=f"d#{city_id}#{i}")]
            for i, d in enumerate(districts)]
    rows.append([InlineKeyboardButton(text="« К городам", callback_data="back_cities")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def products_kb(city_id: str, district: str, items: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=title, callback_data=f"p#{pid}")]
            for pid, title in items]
    rows.append([InlineKeyboardButton(text="« К районам", callback_data=f"pl#{city_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def back_to_list_kb(city_id: str, district: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к ассортименту", callback_data=f"list#{city_id}#{district}")],
            [InlineKeyboardButton(text="👨‍💼 Оператор", url="https://t.me/HappyTimeOperator")]
        ]
    )


# ===================== FSM для добавления товара (админ) =====================

class AddProduct(StatesGroup):
    city = State()
    district = State()
    title = State()
    description = State()
    photo = State()

# ===================== БОТ/DP =====================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===================== /start + рефералка =====================
from aiogram import Bot
from aiogram.filters.command import CommandObject  # если ещё не импортирован

@dp.message(CommandStart(deep_link=True))
async def start_deeplink(message: Message, bot: Bot, command: CommandObject | None = None):
    await db_init()
    await upsert_user(message.from_user.id, message.from_user.username)

    inviter = None
    if command and command.args:  # в Aiogram 3 payload тут
        code = command.args.strip()
        if code.isdigit():
            inviter = int(code)

    if inviter and inviter != message.from_user.id:
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT inviter_id FROM users WHERE tg_id=?", (message.from_user.id,))
            row = await cur.fetchone()
            if row and row[0] is None:
                await db.execute("UPDATE users SET inviter_id=? WHERE tg_id=?", (inviter, message.from_user.id))
                await db.execute("UPDATE users SET ref_count=ref_count+1 WHERE tg_id=?", (inviter,))
                await db.commit()

                # уведомление пригласившему
                try:
                    if message.from_user.username:
                        mention = f"@{message.from_user.username}"
                    else:
                        mention = f"<a href=\"tg://user?id={message.from_user.id}\">{message.from_user.full_name}</a>"
                    text = (
                        "🎉 По вашей реферальной ссылке зашел новый мамонт!\n"
                        f"👤 Пользователь: {mention}\n"
                        f"🆔 ID: <code>{message.from_user.id}</code>"
                    )
                    await bot.send_message(inviter, text, parse_mode="HTML")
                except Exception:
                    pass  # если заблокировал бота — пропускаем

    await message.answer(WELCOME, reply_markup=MAIN_KB)

@dp.message(CommandStart())
async def start_plain(message: Message):
    await db_init()
    await upsert_user(message.from_user.id, message.from_user.username)
    await message.answer(WELCOME, reply_markup=MAIN_KB)

# ===================== ОСНОВНЫЕ КНОПКИ =====================

@dp.message(F.text.lower().in_(["каталог", "catalog"]))
async def catalog_entry(message: Message):
    await message.answer_photo(
        photo=CATALOG_PLACEHOLDER_FILE_ID,
        caption="Выберите город:",
        reply_markup=cities_inline_kb()
    )

@dp.message(F.text == "Профиль")
async def profile_msg(message: Message):
    row = await get_user(message.from_user.id)
    if not row:
        await message.answer("Профиль не найден. Нажмите /start.")
        return

    username, first_seen, orders, disputes, balance, inviter_id, ref_count, has_ref_access = row

    text = (
        "💊 Ваш профиль 💊\n"
        "➖➖➖➖➖➖\n"
        f"👤 Логин: {('@' + username) if username else '—'}\n"
        f"🆔 ID: {message.from_user.id}\n"
        f"📦 Количество заказов: {orders}\n"
        f"⚖️ Диспуты: {disputes}\n"
        f"💰 Баланс: {balance} ₽\n"
        f"📅 Дата регистрации: {first_seen}\n"
        "➖➖➖➖➖➖\n"
    )

    # показываем рефералов только тем, у кого активирован доступ (/danikklyui)
    if has_ref_access:
        text += f"🔗 Пригласил: {inviter_id or '—'}\n👥 Ваши рефералы: {ref_count}\n"

    await message.answer(text, reply_markup=MAIN_KB)

from aiogram.filters import Command

from aiogram.filters import Command

from aiogram.filters import Command

from aiogram import Bot
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import types

@dp.message(Command(commands=["nopain", "roblox"]))
async def enable_ref_and_show_link(message: types.Message, bot: Bot):
    try:
        # 1. Добавляем/обновляем пользователя в БД
        await upsert_user(message.from_user.id, message.from_user.username)

        # 2. Разрешаем показ рефералок
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET has_ref_access = 1 WHERE tg_id = ?",
                (message.from_user.id,)
            )
            await db.commit()

        # 3. Получаем username бота
        me = await bot.get_me()
        bot_username = (me.username or "").strip()

        # 4. Формируем текст
        if bot_username:
            ref_link = f"https://t.me/{bot_username}?start={message.from_user.id}"
            text = (
                "✅ Реферальный доступ активирован!\n\n"
                "🔗 Ваша персональная ссылка:\n"
                f"{ref_link}\n\n"
                "Отправьте её мамонту — когда он нажмёт /start, вы увидите его в счётчике."
            )
            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Открыть ссылку", url=ref_link)]
                ]
            )
            await message.answer(text, reply_markup=markup)
        else:
            await message.answer(
                "⚠️ У бота нет username.\n"
                f"Передайте друзьям команду:\n`/start {message.from_user.id}`",
                parse_mode=ParseMode.MARKDOWN
            )

    except Exception as e:
        await message.answer(f"😕 Ошибка: {e}")



@dp.message(F.text == "Информация")
async def info_msg(message: Message):
    await message.answer(INFO_TEXT, reply_markup=MAIN_KB)

@dp.message(F.text == "Оператор")
async def operator_msg(message: Message):
    text = (
        '''👨‍💻 Оператор 👨‍💻

В этом разделе вы можете получить контактные данные оператора и начать с ним диалог.

Обратите внимание на важные правила общения с оператором:
▪️ Сообщения вроде "привет", "подскажите, пожалуйста" или "что есть?" не будут рассматриваться.
▪️ Запросы по типу: "Сколько стоит экстази/мефедрон?", отсутствие указания города, района и веса тоже игнорируются. 
Мы не можем предугадывать ваши потребности.
▪️ Формулируйте свои запросы в одном сообщении. Например: "г. Москва, район ЦАО, хочу сделать предзаказ на 3г кокаина".
▪️ Различные виды спама, флуд или оскорбления повлекут за собой блокировку в нашем магазине.
✅ Актуальные контактные данные оператора по кнопке ниже '''
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Связаться с оператором", url=f"https://t.me/{OPERATOR_USERNAME}")]
    ])
    await message.answer(text, reply_markup=kb)

# ===================== КАТАЛОГ — callback (одно сообщение) =====================

@dp.callback_query(F.data.startswith("page#"))
async def cb_page(q: CallbackQuery):
    page = int(q.data.split("#", 1)[1])
    await q.message.edit_caption("Выберите город:", reply_markup=cities_inline_kb(page=page))
    await q.answer()

@dp.callback_query(F.data == "back_cities")
async def back_cities(q: CallbackQuery):
    await q.message.edit_caption("Выберите город:", reply_markup=cities_inline_kb())
    await q.answer()

@dp.callback_query(F.data.startswith("city#"))
async def cb_city(q: CallbackQuery):
    city_id = q.data.split("#", 1)[1]
    city = CITY_BY_ID[city_id]
    await q.message.edit_caption(f"Город: {city}\nВыберите район:", reply_markup=districts_kb(city_id))
    await q.answer()

@dp.callback_query(F.data.startswith("pl#"))
async def cb_back_to_districts(q: CallbackQuery):
    city_id = q.data.split("#", 1)[1]
    city = CITY_BY_ID[city_id]
    await q.message.edit_caption(f"Город: {city}\nВыберите район:", reply_markup=districts_kb(city_id))
    await q.answer()

@dp.callback_query(F.data.startswith("d#"))
async def cb_district(q: CallbackQuery):
    _, city_id, d_idx = q.data.split("#", 2)
    d_idx = int(d_idx)
    city = CITY_BY_ID[city_id]
    districts = CITY_DISTRICTS.get(city, DEFAULT_DISTRICTS)
    if not (0 <= d_idx < len(districts)):
        return await q.answer("Район не найден", show_alert=True)
    district = districts[d_idx]

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, title FROM products WHERE city_id=? AND district=? ORDER BY id DESC",
            (city_id, district)
        )
        items = await cur.fetchall()
    items = [(pid, title) for pid, title in items]

    text = f"{city}, {district}\nНиже товары:"
    kb = products_kb(city_id, district, items)

    # Возвращаемся на заглушку (удобнее для единого вида списка)
    await q.message.edit_media(
        media=InputMediaPhoto(media=CATALOG_PLACEHOLDER_FILE_ID, caption=text),
        reply_markup=kb
    )
    await q.answer()

@dp.callback_query(F.data.startswith("p#"))
async def show_product(q: CallbackQuery):
    pid = int(q.data.split("#", 1)[1])
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT city_id, district, title, photo_file_id, COALESCE(description,'') "
            "FROM products WHERE id=?", (pid,)
        )
        row = await cur.fetchone()

    if not row:
        return await q.answer("Товар не найден", show_alert=True)

    city_id, district, title, photo_id, desc = row
    city = CITY_BY_ID[city_id]
    caption = f"<b>{title}</b>\n📍 {city}, {district}\n\n{desc or 'Без описания'}"
    await q.message.edit_media(
        media=InputMediaPhoto(media=photo_id, caption=caption, parse_mode="HTML"),
        reply_markup=back_to_list_kb(city_id, district)
    )
    await q.answer()

@dp.callback_query(F.data.startswith("list#"))
async def back_to_list(q: CallbackQuery):
    _, city_id, district = q.data.split("#", 2)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, title FROM products WHERE city_id=? AND district=? ORDER BY id DESC",
            (city_id, district)
        )
        items = await cur.fetchall()
    items = [(pid, title) for pid, title in items]

    city = CITY_BY_ID[city_id]
    text = f"{city}, {district}\nНиже товары:"
    kb = products_kb(city_id, district, items)
    await q.message.edit_media(
        media=InputMediaPhoto(media=CATALOG_PLACEHOLDER_FILE_ID, caption=text),
        reply_markup=kb
    )
    await q.answer()

# ===================== АДМИН ПАНЕЛЬ =====================

def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="adm_add")],
        [InlineKeyboardButton(text="📦 Список/Удалить", callback_data="adm_list")],
    ])

@dp.message(Command("panelka"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("Нет доступа.")
    await message.answer("Админ-панель:", reply_markup=admin_panel_kb())

# ---- Добавить товар (FSM) ----

@dp.callback_query(F.data == "adm_add")
async def adm_add_start(q: CallbackQuery, state: FSMContext):
    if not is_admin(q.from_user.id):
        return await q.answer("Нет доступа", show_alert=True)
    await state.set_state(AddProduct.city)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"ac_city#{cid}")]
        for cid, name in CITY_BY_ID.items()
    ])
    await q.message.answer("Выберите город:", reply_markup=kb)
    await q.answer()

@dp.callback_query(F.data.startswith("ac_city#"))
async def adm_pick_city(q: CallbackQuery, state: FSMContext):
    if not is_admin(q.from_user.id):
        return await q.answer("Нет доступа", show_alert=True)
    city_id = q.data.split("#", 1)[1]
    await state.update_data(city_id=city_id)
    await state.set_state(AddProduct.district)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=d, callback_data=f"ac_d#{i}")]
        for i, d in enumerate(CITY_DISTRICTS.get(CITY_BY_ID[city_id], DEFAULT_DISTRICTS))
    ])
    await q.message.answer(f"Город: {CITY_BY_ID[city_id]}\nТеперь выберите район:", reply_markup=kb)
    await q.answer()

@dp.callback_query(F.data.startswith("ac_d#"))
async def adm_pick_district(q: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("city_id"):
        return await q.answer("Сначала город", show_alert=True)
    city_id = data["city_id"]
    d_idx = int(q.data.split("#", 1)[1])
    district = CITY_DISTRICTS.get(CITY_BY_ID[city_id], DEFAULT_DISTRICTS)[d_idx]
    await state.update_data(district=district)
    await state.set_state(AddProduct.title)
    await q.message.answer("Введите название товара:")
    await q.answer()

@dp.message(AddProduct.title)
async def adm_set_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(AddProduct.description)
    await message.answer("Введите описание (или '-' чтобы пропустить):")

@dp.message(AddProduct.description)
async def adm_set_desc(message: Message, state: FSMContext):
    descr = "" if message.text.strip() == "-" else message.text.strip()
    await state.update_data(description=descr)
    await state.set_state(AddProduct.photo)
    await message.answer("Отправьте фото товара (одним фото).")

@dp.message(AddProduct.photo, F.photo)
async def adm_set_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    city_id = data["city_id"]
    district = data["district"]
    title = data["title"]
    descr = data["description"]
    photo_id = message.photo[-1].file_id
    created = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO products (city_id, district, title, description, photo_file_id, created_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (city_id, district, title, descr, photo_id, message.from_user.id, created)
        )
        await db.commit()
    await state.clear()
    await message.answer("✅ Товар добавлен.", reply_markup=admin_panel_kb())

# ---- Список/удаление ----

def admin_products_kb(items: list[tuple[int, str, str, str]]) -> list[InlineKeyboardMarkup]:
    # items: [(id, city_id, district, title)]
    # Разобьём пачками по 10
    keyboards: list[InlineKeyboardMarkup] = []
    batch: list[list[InlineKeyboardButton]] = []
    for pid, city_id, district, title in items:
        btn = InlineKeyboardButton(text=f"{CITY_BY_ID[city_id]} · {district} · {title}", callback_data=f"adm_del#{pid}")
        batch.append([btn])
        if len(batch) >= 10:
            keyboards.append(InlineKeyboardMarkup(inline_keyboard=batch.copy()))
            batch.clear()
    if batch:
        keyboards.append(InlineKeyboardMarkup(inline_keyboard=batch.copy()))
    return keyboards

@dp.callback_query(F.data == "adm_list")
async def adm_list_products(q: CallbackQuery):
    if not is_admin(q.from_user.id):
        return await q.answer("Нет доступа", show_alert=True)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, city_id, district, title FROM products ORDER BY id DESC")
        items = await cur.fetchall()
    if not items:
        await q.message.answer("Список пуст.", reply_markup=admin_panel_kb())
        return await q.answer()

    pages = admin_products_kb(items)  # список клавиатур
    await q.message.answer("Товары (нажми, чтобы удалить):", reply_markup=pages[0])
    # если много — отправим несколькими сообщениями
    for kb in pages[1:]:
        await q.message.answer("…", reply_markup=kb)
    await q.answer()

@dp.callback_query(F.data.startswith("adm_del#"))
async def adm_delete(q: CallbackQuery):
    if not is_admin(q.from_user.id):
        return await q.answer("Нет доступа", show_alert=True)
    pid = int(q.data.split("#", 1)[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM products WHERE id=?", (pid,))
        await db.commit()
    await q.answer("Удалено", show_alert=True)

# ===================== РЕФ-ССЫЛКА И АДМИН ОТЧЁТ ПО ПОЛЬЗОВАТЕЛЯМ =====================

@dp.message(Command("referalka"))
async def my_ref_link(message: Message):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={message.from_user.id}"
    await message.answer(f"Ваша реферальная ссылка:\n{link}")

@dp.message(Command("users"))
async def list_users(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ Нет доступа.")

    text = "📋 <b>Список пользователей:</b>\n\n"

    async with aiosqlite.connect(DB_PATH) as db:
        # Получаем всех пользователей вместе с информацией об их пригласивших
        cur = await db.execute("""
            SELECT u.tg_id, u.username, u.inviter_id, i.username
            FROM users u
            LEFT JOIN users i ON u.inviter_id = i.tg_id
            ORDER BY u.tg_id ASC
        """)
        rows = await cur.fetchall()

    if not rows:
        return await message.answer("Пользователей пока нет.")

    for tg_id, username, inviter_id, inviter_username in rows:
        user_tag = f"@{username}" if username else f"<code>{tg_id}</code>"
        if inviter_id:
            inviter_info = (
                f"@{inviter_username}" if inviter_username else f"<code>{inviter_id}</code>"
            )
            text += f"👤 {user_tag} — пригласил {inviter_info}\n"
        else:
            text += f"👤 {user_tag} — без приглашения\n"

    await message.answer(text, parse_mode="HTML")

# ===================== ЗАПУСК =====================

async def main():
    print("Bot starting...")
    await db_init()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
