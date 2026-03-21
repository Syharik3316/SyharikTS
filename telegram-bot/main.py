import asyncio
import json
import logging
import os
from io import BytesIO

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import BufferedInputFile, Message

from backend_client import BackendClient
from keyboards import main_menu_keyboard
from state import get_state, parse_schema_payload, reset_state

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("telegram_bot")

BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
if not BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

client = BackendClient()
dp = Dispatcher()


async def _animate_loading(message: Message) -> asyncio.Task:
    async def _runner() -> None:
        frames = ["Генерирую", "Генерирую.", "Генерирую..", "Генерирую..."]
        idx = 0
        while True:
            await asyncio.sleep(1.0)
            idx = (idx + 1) % len(frames)
            try:
                await message.edit_text(f"{frames[idx]}\nПожалуйста, подождите.")
            except Exception:
                return

    return asyncio.create_task(_runner())


async def _require_linked_or_explain(message: Message) -> bool:
    try:
        await client.get_profile(chat_id=str(message.chat.id))
        return True
    except Exception:
        await message.answer(
            "Генерация доступна только после авторизации на сайте и привязки Telegram.\n"
            "1) Войдите на сайт\n"
            "2) В профиле нажмите «Получить код привязки»\n"
            "3) Отправьте в боте: /link XXXXXX"
        )
        return False


@dp.message(CommandStart())
async def handle_start(message: Message) -> None:
    await message.answer(
        "Привет! Я помогу с генерацией TS и просмотром профиля.\n"
        "Сначала свяжите аккаунт через команду /link XXXXXX из сайта.",
        reply_markup=main_menu_keyboard(),
    )


@dp.message(Command("link"))
async def handle_link(message: Message, command: CommandObject) -> None:
    code = (command.args or "").strip().upper()
    if not code:
        await message.answer("Отправьте команду в формате: /link XXXXXX")
        return
    try:
        payload = await client.consume_link(
            code=code,
            chat_id=str(message.chat.id),
            username=message.from_user.username if message.from_user else None,
            first_name=message.from_user.first_name if message.from_user else None,
        )
    except Exception as e:
        await message.answer(f"Не удалось привязать аккаунт: {e}")
        return

    username = payload.get("telegram_username")
    first_name = payload.get("telegram_first_name")
    suffix = f" (@{username})" if username else ""
    name = f"{first_name or 'Пользователь'}{suffix}"
    await message.answer(f"Готово! Telegram привязан: {name}", reply_markup=main_menu_keyboard())


@dp.message(Command("profile"))
@dp.message(F.text == "Профиль")
async def handle_profile(message: Message) -> None:
    try:
        payload = await client.get_profile(chat_id=str(message.chat.id))
    except Exception as e:
        await message.answer(
            "Профиль недоступен. Убедитесь, что Telegram привязан к сайту через /link XXXXXX.\n"
            f"Ошибка: {e}"
        )
        return

    recent = payload.get("recent_generations") or []
    usage = payload.get("token_usage") or {}
    recent_lines = []
    for item in recent[:3]:
        recent_lines.append(f"- {item.get('created_at', '')}: {item.get('main_file_name', 'unknown')}")
    if not recent_lines:
        recent_lines = ["- Пока нет генераций."]

    req_rows = usage.get("requests") or []
    req_lines = []
    for row in req_rows[:3]:
        req_lines.append(
            f"- {row.get('main_file_name', 'unknown')}: total={row.get('total_tokens', 0)} "
            f"(p={row.get('prompt_tokens', 0)}, c={row.get('completion_tokens', 0)})"
        )
    if not req_lines:
        req_lines = ["- Пока нет запросов."]

    text = (
        f"Профиль:\n"
        f"Имя: {payload.get('login', '-')}\n"
        f"Почта: {payload.get('email', '-')}\n\n"
        f"Последние 3 генерации:\n" + "\n".join(recent_lines) + "\n\n"
        f"Тех.информация:\n"
        f"- Кол-во запросов: {usage.get('requests_count', 0)}\n"
        f"- Всего токенов: {usage.get('total_tokens', 0)}\n"
        f"- Prompt токены: {usage.get('total_prompt_tokens', 0)}\n"
        f"- Completion токены: {usage.get('total_completion_tokens', 0)}\n"
        f"- Последние 3 записи по токенам:\n" + "\n".join(req_lines)
    )
    await message.answer(text, reply_markup=main_menu_keyboard())


@dp.message(Command("generate"))
@dp.message(F.text == "Генерация")
async def handle_generate_start(message: Message) -> None:
    if not await _require_linked_or_explain(message):
        return
    st = get_state(message.chat.id)
    st.waiting_file = True
    st.waiting_schema = False
    st.file_name = None
    st.file_bytes = None
    await message.answer("Отправьте входной файл для генерации (документом).", reply_markup=main_menu_keyboard())


@dp.message(F.document)
async def handle_document(message: Message, bot: Bot) -> None:
    st = get_state(message.chat.id)
    if not st.waiting_file:
        return
    if not await _require_linked_or_explain(message):
        reset_state(message.chat.id)
        return
    doc = message.document
    file = await bot.get_file(doc.file_id)
    data = await bot.download_file(file.file_path)
    st.file_bytes = data.read()
    st.file_name = doc.file_name or "input.bin"
    st.waiting_file = False
    st.waiting_schema = True
    await message.answer(
        "Файл получен. Теперь отправьте JSON пример схемы:\n"
        "- как текст,\n"
        "- или файлом .json."
    )


@dp.message(F.document)
async def handle_json_file(message: Message, bot: Bot) -> None:
    st = get_state(message.chat.id)
    if not st.waiting_schema:
        return
    doc = message.document
    if not (doc.file_name or "").lower().endswith(".json"):
        return
    file = await bot.get_file(doc.file_id)
    data = await bot.download_file(file.file_path)
    raw = data.read().decode("utf-8", errors="ignore")
    await _process_schema_and_generate(message, raw)


@dp.message(F.text)
async def handle_schema_text(message: Message) -> None:
    st = get_state(message.chat.id)
    if not st.waiting_schema:
        return
    await _process_schema_and_generate(message, message.text or "")


async def _process_schema_and_generate(message: Message, schema_text: str) -> None:
    if not await _require_linked_or_explain(message):
        reset_state(message.chat.id)
        return
    st = get_state(message.chat.id)
    if not st.file_bytes or not st.file_name:
        reset_state(message.chat.id)
        await message.answer("Сессия генерации сброшена. Нажмите «Генерация» и начните снова.")
        return
    try:
        schema_obj = parse_schema_payload(schema_text)
    except Exception as e:
        await message.answer(f"JSON не распознан: {e}")
        return

    wait_msg = await message.answer("Генерирую...\nПожалуйста, подождите.")
    animator = await _animate_loading(wait_msg)
    try:
        result = await client.generate(
            chat_id=str(message.chat.id),
            schema_obj=schema_obj,
            file_name=st.file_name,
            file_bytes=st.file_bytes,
        )
    except Exception as e:
        animator.cancel()
        await wait_msg.edit_text(f"Ошибка генерации: {e}")
        reset_state(message.chat.id)
        return
    animator.cancel()

    code = result.get("code") or ""
    cache_hit = bool(result.get("cache_hit"))
    ts_name = (st.file_name.rsplit(".", 1)[0] if "." in st.file_name else st.file_name) + ".ts"
    bio = BytesIO(code.encode("utf-8"))
    await message.answer_document(BufferedInputFile(bio.getvalue(), filename=ts_name), caption="Готово! TS-файл создан.")
    await message.answer(
        ("Использован готовый результат из кэша.\n" if cache_hit else "Код сгенерирован.\n")
        + "Быстрое копирование (код-блок ниже):\n"
        + f"```ts\n{code[:3500]}\n```",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
    reset_state(message.chat.id)


async def main() -> None:
    bot = Bot(BOT_TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
