"""Источники новостей металлургии.

У каждого источника есть режим:
  "all"    — лента уже отраслевая, берём всё;
  "filter" — лента общая (ТАСС, Коммерсантъ, РБК, ЦБ, Правительство),
             берём только материалы, попадающие под отраслевые ключевые
             слова из KEYWORDS.

Прямые RSS используются там, где сайт отдаёт их без анти-бот защиты.
Часть сайтов недоступна с серверов GitHub: Коммерсантъ/РБК/Metalinfo при
прямом запросе закрыты Qrator, Росстат и Prometall отдают сертификаты
российских УЦ, Минпромторг и Минэк не отвечают на зарубежные IP. Для них
используется Google News RSS с фильтром site:, который работает стабильно.
"""
from urllib.parse import quote


def google_news(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(query)}&hl=ru&gl=RU&ceid=RU:ru"


def google_news_en(query: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"


# Ключевые слова для фильтрации общих лент. Совпадение ищется только с
# НАЧАЛА слова (см. is_relevant в bot.py), поэтому корни даны без окончаний.
# Короткие корни вроде "лом" или "олов" намеренно не используются: они
# ловят "ломбард", "уголовное", "Фролова" и прочий мусор.
KEYWORDS = [
    # отрасль и продукция
    "металлург", "металлопрок", "металлопрод", "металлоторг", "металлолом",
    "сталь", "стальн", "сталев", "сталелит", "прокат", "чугун", "домен",
    "арматур", "трубн", "трубопрок", "ферроспл", "руда", "руды", "рудн",
    "железоруд", "окатыш", "агломерат", "коксующ", "слитк", "сляб",
    "горно-металлург", "цветмет", "ломозагот",
    # металлы
    "алюмини", "медь", "медн", "никел", "титан", "цинк", "свинец", "оловян",
    "платин", "паллади", "золотодоб", "редкоземель", "драгметалл",
    # компании
    "северсталь", "нлмк", "ммк", "магнитогорский металлург", "евраз",
    "мечел", "русал", "норникель", "норильский никель", "металлоинвест",
    "тмк", "всмпо", "ависма", "угмк", "русская медная", "полюс",
    "распадская", "объединенная металлург", "новолипецк", "выксунск",
    # английские варианты для международных лент
    "steel", "metals", "metallurg", "aluminium", "aluminum", "nickel",
    "copper", "iron ore",
]

# Слова, которые начинаются как ключевые, но к отрасли не относятся:
# "Евразийский экономический союз" — не компания ЕВРАЗ, "полюс холода" —
# не золотодобытчик "Полюс".
STOPWORDS = [
    "евразий", "евразэс", "евразия", "полюсн",
]

COMPANIES_QUERY = (
    '(Северсталь OR НЛМК OR ММК OR Мечел OR РУСАЛ OR Норникель OR ЕВРАЗ '
    'OR Металлоинвест OR ТМК OR "ВСМПО-АВИСМА" OR УГМК OR "Русская медная компания" '
    'OR Полюс) металлургия'
)

# (название, url, режим)
FEEDS = [
    # ─── Отраслевые СМИ ─────────────────────────────────────────────────
    ("Steelland", "https://steelland.ru/rss/news_rss.php", "all"),
    ("Металлоснабжение и сбыт", google_news("site:metalinfo.ru"), "all"),
    ("MetalDaily", google_news("site:metaldaily.ru"), "all"),
    ("Prometall", google_news("site:prometall.info"), "all"),
    ("MetallPlace", google_news("site:metallplace.ru"), "all"),

    # ─── Деловые СМИ ────────────────────────────────────────────────────
    ("Коммерсантъ", "https://www.kommersant.ru/RSS/news.xml", "filter"),
    ("РБК", "https://rssexport.rbc.ru/rbcnews/news/30/full.rss", "filter"),
    ("Интерфакс", "https://www.interfax.ru/rss.asp", "filter"),
    ("ТАСС", "https://tass.ru/rss/v2.xml", "filter"),
    ("Эксперт", google_news("site:expert.ru металлургия OR сталь"), "all"),

    # ─── Пресс-релизы компаний ──────────────────────────────────────────
    ("Компании — сводно", google_news(COMPANIES_QUERY), "all"),
    ("Северсталь", google_news("site:severstal.com OR Северсталь"), "all"),
    ("НЛМК", google_news("site:nlmk.com OR НЛМК"), "all"),
    ("ММК", google_news("site:mmk.ru OR Магнитогорский металлургический"), "all"),
    ("ЕВРАЗ", google_news("site:evraz.com OR ЕВРАЗ металлург"), "all"),
    ("Металлоинвест", google_news("site:metalloinvest.com OR Металлоинвест"), "all"),
    ("Норникель", google_news("site:nornickel.com OR Норникель"), "all"),
    ("РУСАЛ", google_news("site:rusal.ru OR РУСАЛ"), "all"),
    ("ВСМПО-АВИСМА", google_news('site:vsmpo.ru OR "ВСМПО-АВИСМА"'), "all"),
    ("ТМК", google_news("site:tmk-group.com OR ТМК трубная"), "all"),
    ("УГМК", google_news("site:ugmk.com OR УГМК"), "all"),
    ("Мечел", google_news("site:mechel.com OR Мечел"), "all"),

    # ─── Государственные источники ──────────────────────────────────────
    ("Правительство России", "http://government.ru/all/rss/", "filter"),
    ("Банк России", "https://www.cbr.ru/rss/RssNews", "filter"),
    ("Росстат", google_news("Росстат производство стали OR металлургия"), "all"),
    ("Минпромторг", google_news("Минпромторг металлургия OR сталь"), "all"),
    ("Минэкономразвития", google_news("Минэкономразвития металлургия OR сталь"), "all"),
    ("ФАС России", google_news("ФАС металлургия OR цены на металл"), "all"),

    # ─── Международные источники ────────────────────────────────────────
    ("Reuters — металлы", google_news_en("site:reuters.com steel OR metals OR aluminium"), "all"),
    ("S&P Global", google_news_en("site:spglobal.com steel OR metals"), "all"),
    ("Fastmarkets", google_news_en("site:fastmarkets.com steel OR metals"), "all"),
    ("Argus Media", google_news_en("site:argusmedia.com metals OR steel"), "all"),
    ("SteelOrbis", google_news_en("site:steelorbis.com"), "all"),
    ("World Steel Association", "https://worldsteel.org/feed/", "all"),

    # ─── Тематические срезы ─────────────────────────────────────────────
    ("Металлургия РФ — общее", google_news("металлургия Россия"), "all"),
    ("Цены и рынок металлов", google_news('"цены на металлы" OR "рынок металлов" Россия'), "all"),
    ("Регулирование и пошлины", google_news("(пошлины OR регулирование OR санкции) металлургия Россия"), "all"),
]
