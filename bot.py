#!/usr/bin/env python3
"""Telegram-бот новостей металлургии России.

Без сервера: запускается по расписанию через GitHub Actions.
Каждый запуск — короткий: собрать новые новости из RSS, ответить на
команды пользователей (/start, /stop, /news [период]) и, если наступило
время утренней сводки по Москве — разослать её подписчикам.
Состояние (архив новостей, подписчики, курсор апдейтов) хранится в
JSON-файлах в data/ и коммитится обратно в репозиторий workflow-шагом.
"""
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser
import requests

from feeds import FEEDS

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
ARTICLES_FILE = DATA_DIR / "articles.json"
SUBSCRIBERS_FILE = DATA_DIR / "subscribers.json"
STATE_FILE = DATA_DIR / "state.json"

MOSCOW_TZ = ZoneInfo("Europe/Moscow")
DIGEST_HOUR = 8          # час по Москве, после которого уходит утренняя сводка
ARCHIVE_DAYS = 60        # сколько дней хранить архив для поиска "за период"
MAX_ITEMS_PER_REPLY = 40
TELEGRAM_MSG_LIMIT = 3500

TELEGRAM_API = None  # задаётся в main() после чтения токена


# ─── Хранилище ──────────────────────────────────────────────────────────────

def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ─── Telegram API ───────────────────────────────────────────────────────────

def tg_call(method: str, **params):
    resp = requests.post(f"{TELEGRAM_API}{method}", json=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def chunk_text(text: str, limit: int) -> list[str]:
    lines = text.split("\n")
    chunks, cur = [], ""
    for line in lines:
        candidate = f"{cur}\n{line}" if cur else line
        if len(candidate) > limit:
            if cur:
                chunks.append(cur)
            cur = line
        else:
            cur = candidate
    if cur:
        chunks.append(cur)
    return chunks or [""]


def send_message(chat_id: int, text: str) -> None:
    for chunk in chunk_text(text, TELEGRAM_MSG_LIMIT):
        try:
            tg_call("sendMessage", chat_id=chat_id, text=chunk, disable_web_page_preview=True)
        except Exception as e:
            print(f"[WARN] send_message to {chat_id} failed: {e}")


def get_updates(offset: int) -> list[dict]:
    data = tg_call("getUpdates", offset=offset, timeout=0, allowed_updates=["message"])
    return data.get("result", [])


# ─── Сбор новостей ──────────────────────────────────────────────────────────

def make_id(link: str, title: str) -> str:
    return hashlib.sha256(f"{link}|{title}".encode("utf-8")).hexdigest()[:16]


def clean_title(raw_title: str, is_google: bool) -> str:
    title = (raw_title or "").strip()
    if is_google and " - " in title:
        base = title.rsplit(" - ", 1)[0].strip()
        if base:
            title = base
    return title


def parse_published(entry) -> datetime:
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            return datetime(*val[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def fetch_new_articles(existing_ids: set) -> list[dict]:
    new_items = []
    for source, url in FEEDS:
        is_google = "news.google.com" in url
        try:
            parsed = feedparser.parse(url)
        except Exception as e:
            print(f"[WARN] failed to fetch '{source}': {e}")
            continue
        if getattr(parsed, "bozo", False) and not parsed.entries:
            print(f"[WARN] '{source}' returned no entries (bozo={parsed.bozo})")
        for entry in parsed.entries:
            link = entry.get("link", "")
            title = clean_title(entry.get("title", ""), is_google)
            if not link or not title:
                continue
            item_id = make_id(link, title)
            if item_id in existing_ids:
                continue
            existing_ids.add(item_id)
            new_items.append({
                "id": item_id,
                "title": title,
                "link": link,
                "source": source,
                "published": parse_published(entry).isoformat(),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })
    return new_items


# ─── Дайджест / поиск за период ─────────────────────────────────────────────

PERIOD_ALIASES = {
    "сегодня": 1, "today": 1,
    "вчера": 2, "yesterday": 2,
    "неделя": 7, "week": 7,
    "месяц": 30, "month": 30,
}


def parse_period_days(arg: str) -> int:
    arg = arg.strip().lower()
    if not arg:
        return 1
    if arg in PERIOD_ALIASES:
        return PERIOD_ALIASES[arg]
    m = re.match(r"(\d+)", arg)
    if m:
        return max(1, min(ARCHIVE_DAYS, int(m.group(1))))
    return 1


def build_digest(articles: list[dict], days: int, title: str) -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    items = [a for a in articles if datetime.fromisoformat(a["published"]) >= cutoff]
    items.sort(key=lambda a: a["published"], reverse=True)
    if not items:
        return f"{title}\n\nЗа этот период новых материалов не найдено."
    lines = [f"{title} ({len(items)})"]
    for a in items[:MAX_ITEMS_PER_REPLY]:
        lines.append(f"\n• [{a['source']}] {a['title']}\n{a['link']}")
    if len(items) > MAX_ITEMS_PER_REPLY:
        lines.append(f"\n…и ещё {len(items) - MAX_ITEMS_PER_REPLY} материалов за этот период.")
    return "\n".join(lines)


# ─── Команды пользователей ──────────────────────────────────────────────────

HELP_TEXT = (
    "Команды:\n"
    "/news — новости за сегодня\n"
    "/news 3 — новости за 3 дня\n"
    "/news неделя — новости за неделю\n"
    "/start — подписаться на утреннюю сводку (каждый день ~08:00 МСК)\n"
    "/stop — отписаться от утренней сводки\n"
    "/help — эта справка"
)


def handle_commands(subscribers: list, articles: list, state: dict) -> None:
    offset = state.get("update_offset", 0)
    updates = get_updates(offset)
    for upd in updates:
        state["update_offset"] = upd["update_id"] + 1
        msg = upd.get("message")
        if not msg or "text" not in msg:
            continue
        chat_id = msg["chat"]["id"]
        text = msg["text"].strip()
        parts = text.split(maxsplit=1)
        cmd = parts[0].split("@")[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "/start":
            if chat_id not in subscribers:
                subscribers.append(chat_id)
            send_message(
                chat_id,
                "Готово! Буду присылать утреннюю сводку новостей металлургии России "
                "каждый день около 08:00 по Москве.\n\n" + HELP_TEXT,
            )
        elif cmd == "/stop":
            if chat_id in subscribers:
                subscribers.remove(chat_id)
            send_message(chat_id, "Вы отписались от утренней сводки. Снова подписаться — /start")
        elif cmd == "/news":
            days = parse_period_days(arg)
            label = arg.strip() if arg.strip() else "сегодня"
            reply = build_digest(articles, days=days, title=f"Новости металлургии за {label}")
            send_message(chat_id, reply)
        elif cmd == "/help":
            send_message(chat_id, HELP_TEXT)
        else:
            send_message(chat_id, "Не понял команду.\n\n" + HELP_TEXT)


def maybe_send_daily_digest(subscribers: list, articles: list, state: dict) -> None:
    now_msk = datetime.now(MOSCOW_TZ)
    today_str = now_msk.date().isoformat()
    if now_msk.hour < DIGEST_HOUR or state.get("last_digest_date") == today_str:
        return
    state["last_digest_date"] = today_str
    if not subscribers:
        return
    text = build_digest(
        articles, days=1,
        title=f"Утренняя сводка по металлургии — {now_msk.strftime('%d.%m.%Y')}",
    )
    for chat_id in subscribers:
        send_message(chat_id, text)


# ─── main ────────────────────────────────────────────────────────────────────

def main() -> None:
    global TELEGRAM_API
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set")
    TELEGRAM_API = f"https://api.telegram.org/bot{token}/"

    DATA_DIR.mkdir(exist_ok=True)
    articles = load_json(ARTICLES_FILE, [])
    subscribers = load_json(SUBSCRIBERS_FILE, [])
    state = load_json(STATE_FILE, {"update_offset": 0, "last_digest_date": ""})

    existing_ids = {a["id"] for a in articles}
    new_items = fetch_new_articles(existing_ids)
    articles.extend(new_items)
    print(f"Fetched {len(new_items)} new articles ({len(articles)} total in archive)")

    cutoff = datetime.now(timezone.utc) - timedelta(days=ARCHIVE_DAYS)
    articles = [a for a in articles if datetime.fromisoformat(a["published"]) >= cutoff]

    handle_commands(subscribers, articles, state)
    maybe_send_daily_digest(subscribers, articles, state)

    save_json(ARTICLES_FILE, articles)
    save_json(SUBSCRIBERS_FILE, subscribers)
    save_json(STATE_FILE, state)


if __name__ == "__main__":
    main()
