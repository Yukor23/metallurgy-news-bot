"""Список источников новостей металлургии.

Прямые RSS используются там, где сайт отдаёт их без анти-бот защиты
(Qrator/JS-челленджи блокируют часть сайтов вроде Коммерсанта, РБК,
Metalinfo при запросе не из браузера). Для таких источников используется
Google News RSS с фильтром site:, который работает надёжно и не требует
обхода защиты конкретного сайта.
"""
from urllib.parse import quote


def google_news(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(query)}&hl=ru&gl=RU&ceid=RU:ru"


FEEDS = [
    ("Steelland", "https://steelland.ru/rss/news_rss.php"),
    ("Металлургия РФ — общее", google_news("металлургия Россия")),
    ("Цены и рынок металлов", google_news('"цены на металлы" OR "рынок металлов" Россия')),
    ("Коммерсантъ", google_news("металлургия site:kommersant.ru")),
    ("РБК", google_news("металлургия site:rbc.ru")),
    ("Металлоснабжение и сбыт (Metalinfo)", google_news("site:metalinfo.ru")),
    ("Metaldaily", google_news("site:metaldaily.ru")),
    (
        "Крупные компании (Северсталь, НЛМК, ММК, Мечел, РУСАЛ, РМК, "
        "Металлоинвест, ТМК, ВСМПО-АВИСМА, ЕВРАЗ, Норникель, Полюс)",
        google_news(
            '(Северсталь OR НЛМК OR ММК OR Мечел OR РУСАЛ OR "Русская медная компания" '
            'OR Металлоинвест OR ТМК OR "ВСМПО-АВИСМА" OR ЕВРАЗ OR Норникель OR Полюс) металлургия'
        ),
    ),
    ("Регулирование и пошлины", google_news('(пошлины OR регулирование OR санкции) металлургия Россия')),
]
