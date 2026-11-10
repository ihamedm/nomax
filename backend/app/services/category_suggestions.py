"""Probabilistic category suggestions backed by an optional Laya sidecar.

A high-precision Persian alias layer resolves the obvious cases first. When
it cannot separate two candidates, Laya makes a two-stage decision:

1. choose one of the 17 real top-level categories;
2. choose a subcategory inside that category.

Laya documents accuracy degradation with large choice sets, while the product
taxonomy has 188 subcategories. Splitting the decision keeps each request at
18 or fewer options and also gives the UI a useful category-only fallback when
the second stage is uncertain. The alias layer exists because the live Persian
benchmark showed that zero-shot Laya alone was not reliable enough on 17-way
business category decisions.

Nothing here imports torch or talks to a model in-process. The API calls the
separate ``laya-serve`` HTTP service, so the normal backend image stays small
and a missing/unavailable classifier only removes suggestions.
"""

from __future__ import annotations

import logging
import re
import time
import unicodedata
from dataclasses import dataclass, field

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.category import Category, Subcategory

logger = logging.getLogger(__name__)

MAX_STATE_CHARS = 900

# High-precision Persian terms used only as a shortlist/override layer. The
# live Laya benchmark showed that the 17-way category decision is unreliable
# on noisy Persian shop names, while these terms are stable. Laya still makes
# the category decision when two or more aliases tie, and always makes the
# subcategory decision when no subcategory rule is decisive.
CATEGORY_ALIASES: dict[str, tuple[str, ...]] = {
    "automotive": (
        "خودرو", "ماشین", "اتومبیل", "موتورسیکلت", "تعمیرگاه", "مکانیک",
        "صافکاری", "نقاشی خودرو", "لاستیک", "باتری", "قطعات یدکی", "آژانس",
        "تاکسی", "حمل و نقل", "حمل‌ونقل", "پمپ بنزین", "اجاره خودرو",
        "برق خودرو", "شیشه اتومبیل", "شیشه خودرو",
    ),
    "building": (
        "لوله کشی", "لوله‌کشی", "برقکاری", "برق کاری", "نقاشی ساختمان",
        "بنایی", "کاشی کاری", "کاشی‌کاری", "درب و پنجره", "کولر", "اسپلیت",
        "نجاری", "کابینت", "پیمانکاری", "کلیدسازی", "شیشه بری", "شیشه‌بری",
        "ایزوگام", "عایق", "آسانسور", "تاسیسات", "تأسیسات",
    ),
    "digital": (
        "موبایل", "کامپیوتر", "لپ تاپ", "لپ‌تاپ", "چاپ", "پرینت", "عکاسی",
        "فیلمبرداری", "شبکه", "اینترنت", "ماهواره", "آنتن", "طراحی سایت",
        "گیم نت", "گیم‌نت", "کافی نت", "کافی‌نت", "دیجیتال",
    ),
    "food": (
        "رستوران", "فست فود", "فست‌فود", "پیتزا", "ساندویچ", "برگر", "کافه",
        "کافی شاپ", "کافی‌شاپ", "قنادی", "شیرینی", "نانوایی", "نان",
        "آبمیوه", "آبلیمو", "بستنی", "کباب", "غذای خانگی", "کیترینگ",
        "لبنیات", "صبحانه", "قهوه",
    ),
    "agriculture": (
        "دامپزشکی", "دامپزشک", "کلینیک دامپزشکی", "بیمارستان دامپزشکی",
        "کشاورزی", "بذر", "کود", "نخل", "خرما", "باغداری", "باغ",
        "مرکبات", "دامداری", "مرغداری", "زنبور", "عسل", "آبیاری", "گلخانه",
    ),
    "beauty": (
        "آرایشگاه", "آرایش", "سالن زیبایی", "ناخن", "مانیکور", "میکاپ",
        "گریم", "ماساژ", "اسپا", "اپیلاسیون", "پوست", "کاشت مو",
        "لوازم آرایشی",
    ),
    "retail": (
        "فروشگاه", "پوشاک", "لباس", "شال", "روسری", "کفش", "کیف", "چرم",
        "طلا", "جواهر", "هدیه", "کادو", "سوپرمارکت", "خشکبار", "آجیل",
        "عطر", "ادکلن", "پارچه", "خیاطی", "فرش", "موکت", "لوازم خانگی",
        "پلاسکو", "چینی", "بلور", "مانتو", "بوتیک",
    ),
    "repairs": (
        "تعمیر لوازم خانگی", "تعمیر تلویزیون", "تلویزیون", "خشکشویی",
        "اتوشویی", "قالیشویی", "باربری", "اسباب کشی", "اسباب‌کشی", "قفل",
        "سمپاشی", "کارواش", "آبگرمکن", "پکیج", "ساعت سازی", "ساعت‌سازی",
        "کفاشی",
    ),
    "education": (
        "مدرسه", "دبیرستان", "هنرستان", "دانشگاه", "آموزشگاه", "آموزش",
        "کنکور", "موسیقی", "مهدکودک", "پیش دبستانی", "کلاس خصوصی",
        "فنی و حرفه ای", "فنی و حرفه‌ای",
    ),
    "medical": (
        "دندان", "داروخانه", "بیمارستان", "درمانگاه", "آزمایشگاه",
        "تصویربرداری", "قلب", "اطفال", "ارتوپدی", "چشم پزشکی", "چشم‌پزشکی",
        "گوش و حلق", "پوست و مو", "زنان و زایمان", "فیزیوتراپی", "متخصص", "کلینیک",
    ),
    "sports": (
        "باشگاه", "استخر", "شنا", "فوتبال", "فوتسال", "رزمی", "یوگا",
        "پیلاتس", "دوچرخه", "شهربازی", "بیلیارد", "بولینگ", "کمپینگ",
        "طبیعت گردی", "طبیعت‌گردی",
    ),
    "arts": (
        "سینما", "تئاتر", "نقاشی", "طراحی", "صنایع دستی", "سرگرمی",
        "مراسم", "عکاسی حرفه ای", "عکاسی حرفه‌ای",
    ),
    "pets": (
        "پت شاپ", "پت‌شاپ", "حیوانات خانگی", "آرایش حیوانات",
        "پانسیون حیوانات", "آموزش حیوانات", "سگ", "گربه",
    ),
    "books": (
        "کتاب", "کتابفروشی", "نوشت افزار", "نوشت‌افزار", "لوازم اداری",
        "دفتر", "کاغذ", "لوازم هنری", "کوله",
    ),
    "office-services": (
        "پیشخوان", "دولت", "اسناد رسمی", "وکیل", "حقوقی", "بیمه",
        "حسابداری", "بانک", "خودپرداز", "ATM", "دفتر تاکسی", "مشاور املاک",
        "املاک", "آژانس مسافرتی", "مسافرتی",
    ),
    "accommodation": (
        "هتل", "مسافرخانه", "اقامتگاه", "بوم گردی", "بوم‌گردی",
        "تور گردشگری", "تور مسافرتی", "گردشگری", "جاذبه", "مسافرت",
    ),
    "tools": (
        "ابزار", "پیچ", "مهره", "یراق", "جوشکاری", "کمپرسور", "ابزار بادی",
        "باغبانی", "اندازه گیری", "اندازه‌گیری", "ایمنی", "لباس کار",
        "تیز کردن", "ابزار تعمیرگاه",
    ),
}

_GENERIC_SUBCATEGORY_TOKENS = frozenset(
    {"خدمات", "فروشگاه", "سایر", "عمومی", "انواع", "لوازم", "تعمیر", "مراسم"}
)

_LOCATION_NOISE = re.compile(
    r"(?:و\s+)?از\s+نظر\s+موقعیت\s+جغرافیایی.*$|"
    r"\s+در\s+(?:بهبهان|شهرستان\s+بهبهان).*$|"
    r"\s+واقع\s+شده\s+است\.?$",
    re.IGNORECASE | re.DOTALL,
)
_URL = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_SPACE = re.compile(r"\s+")


class LayaUnavailable(Exception):
    """Raised when the optional sidecar cannot answer."""


@dataclass
class SuggestionTrace:
    """Structured in-memory trace used by the admin diagnostics modal.

    Normal suggestion requests pass ``trace=None`` and pay almost no cost. The
    diagnostics request gets a readable timeline of normalization, taxonomy,
    rule scores, Laya probabilities and threshold decisions.
    """

    events: list[dict] = field(default_factory=list)
    taxonomy: dict = field(default_factory=dict)
    categories: list["TaxonomyCategory"] = field(default_factory=list, repr=False)
    state: str = ""
    laya_successes: int = 0
    laya_failures: int = 0
    probe: dict | None = None

    def log(
        self,
        stage: str,
        level: str,
        message: str,
        *,
        duration_ms: float | None = None,
        data: dict | None = None,
    ) -> dict:
        event: dict = {"stage": stage, "level": level, "message": message}
        if duration_ms is not None:
            event["duration_ms"] = round(duration_ms)
        if data is not None:
            event["data"] = data
        self.events.append(event)
        return event


@dataclass
class TaxonomyCategory:
    id: int
    slug: str
    name: str
    icon: str
    sort_order: int
    subcategories: list["TaxonomySubcategory"] = field(default_factory=list)


@dataclass
class TaxonomySubcategory:
    id: int
    category_id: int
    slug: str
    name: str
    icon: str
    sort_order: int
    standard_tags: list[str]


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", value)
    text = (
        text.replace("ي", "ی")
        .replace("ى", "ی")
        .replace("ك", "ک")
        .replace("ۀ", "ه")
        .replace("أ", "ا")
        .replace("إ", "ا")
        .replace("ؤ", "و")
        .replace("ئ", "ی")
    )
    text = text.replace("\u200c", " ").replace("\u200d", " ")
    text = text.casefold()
    text = _URL.sub(" ", text)
    text = _LOCATION_NOISE.sub(" ", text)
    return _SPACE.sub(" ", text).strip(" .،,;")


def build_state(title: str, description: str | None) -> str:
    """The text Laya sees. Keep the title first and trim location boilerplate."""
    title = _normalize_text(title)[:180]
    description = _normalize_text(description)[:MAX_STATE_CHARS]
    parts = [f"عنوان کسب‌وکار: {title}"]
    if description:
        parts.append(f"توضیحات: {description}")
    return "\n".join(parts)


def _category_criteria(categories: list[TaxonomyCategory]) -> dict[str, str]:
    # Keep criteria to the category name. In the live Persian benchmark,
    # appending keyword lists made Laya much less accurate (for example it
    # started choosing «کتاب» for a restaurant), while plain names kept the
    # obvious category decisions correct.
    return {
        str(category.id): category.name
        for category in categories
        if category.slug != "other"
    }


def _subcategory_criteria(subcategories: list[TaxonomySubcategory]) -> dict[str, str]:
    criteria: dict[str, str] = {}
    for subcategory in subcategories:
        if subcategory.slug == "other":
            continue
        # Same finding at the second stage: tags made an already narrow
        # choice worse. The subcategory name itself is the strongest signal.
        criteria[str(subcategory.id)] = subcategory.name
    return criteria


def _category_rule_hits(text: str, category: TaxonomyCategory) -> list[str]:
    return [
        alias
        for alias in CATEGORY_ALIASES.get(category.slug, ())
        if _normalize_text(alias) in text
    ]


def _category_rule_score(text: str, category: TaxonomyCategory) -> float:
    hits = _category_rule_hits(text, category)
    if not hits:
        return 0.0
    # Specific multi-word terms beat a single generic hit, and several
    # independent hits are stronger than one.
    return len(hits) + max(len(hit) for hit in hits) / 20.0


def resolve_category_rule(
    text: str,
    categories: list[TaxonomyCategory],
    *,
    trace: SuggestionTrace | None = None,
) -> tuple[TaxonomyCategory | None, list[TaxonomyCategory], float]:
    """Use high-precision aliases to pick or narrow the category.

    Returns (winner, shortlist, score). ``winner`` is set only when the top
    score has a clear lead; otherwise ``shortlist`` is what Laya should decide
    between.
    """
    scored: list[tuple[float, int, TaxonomyCategory, list[str]]] = []
    for category in categories:
        if category.slug == "other":
            continue
        hits = _category_rule_hits(text, category)
        if not hits:
            continue
        score = len(hits) + max(len(hit) for hit in hits) / 20.0
        scored.append((score, category.sort_order, category, hits))
    scored.sort(key=lambda item: (-item[0], item[1], item[2].id))
    shortlist = [item[2] for item in scored[:4]]
    if not shortlist:
        if trace is not None:
            trace.log(
                "rules_category",
                "warning",
                "هیچ واژه‌ای از لایه قواعد فارسی با این متن هم‌خوان نبود.",
                data={"scored": [], "winner": None, "shortlist": []},
            )
        return None, [category for category in categories if category.slug != "other"], 0.0

    top_score = scored[0][0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0
    winner = scored[0][2] if top_score - second_score >= 0.35 else None
    if trace is not None:
        trace.log(
            "rules_category",
            "success" if winner is not None else "info",
            (
                f"لایه قواعد دسته «{winner.name}» را با اختلاف کافی انتخاب کرد."
                if winner is not None
                else "لایه قواعد چند دسته نزدیک پیدا کرد؛ انتخاب نهایی به Laya سپرده می‌شود."
            ),
            data={
                "scored": [
                    {
                        "category": _category_payload(item[2]),
                        "score": round(item[0], 3),
                        "hits": item[3],
                    }
                    for item in scored[:8]
                ],
                "winner": _category_payload(winner) if winner is not None else None,
                "shortlist": [_category_payload(item) for item in shortlist],
                "top_score": round(top_score, 3),
                "second_score": round(second_score, 3),
            },
        )
    if winner is not None:
        return winner, shortlist, top_score
    return None, shortlist, top_score


def _subcategory_aliases(
    subcategory: TaxonomySubcategory,
) -> tuple[str, list[tuple[str, float]]]:
    full = _normalize_text(subcategory.name)
    aliases: dict[str, float] = {}
    tokens_source = full.replace(" و ", " ")
    for token in re.split(r"[\s،,()/–-]+", tokens_source):
        token = token.strip()
        if len(token) >= 3 and token not in _GENERIC_SUBCATEGORY_TOKENS and token != full:
            aliases[token] = max(aliases.get(token, 0.0), 1.0)
    for tag in subcategory.standard_tags:
        tag_text = _normalize_text(tag)
        if (
            len(tag_text) >= 3
            and tag_text not in _GENERIC_SUBCATEGORY_TOKENS
            and tag_text != full
        ):
            aliases[tag_text] = max(aliases.get(tag_text, 0.0), 1.5)
    return full, list(aliases.items())


def _subcategory_rule_details(
    text: str, subcategory: TaxonomySubcategory
) -> tuple[float, list[dict]]:
    full, aliases = _subcategory_aliases(subcategory)
    score = 0.0
    matches: list[dict] = []
    if full and full in text:
        score += 3.0
        matches.append(
            {"term": full, "kind": "name", "weight": 3.0, "count": text.count(full)}
        )
    else:
        for alias, weight in aliases:
            occurrences = text.count(alias)
            if not occurrences:
                continue
            # Repeated name words are stronger; tags are supporting evidence
            # and are not multiplied by boilerplate repeats.
            if weight == 1.0:
                score += weight * min(3, occurrences)
                kind = "name_token"
            else:
                score += weight
                kind = "tag"
            matches.append(
                {"term": alias, "kind": kind, "weight": weight, "count": occurrences}
            )
    return score, matches


def resolve_subcategory_rule(
    text: str,
    subcategories: list[TaxonomySubcategory],
    *,
    trace: SuggestionTrace | None = None,
) -> tuple[TaxonomySubcategory | None, float]:
    """Pick a subcategory from an exact name, service tag, or name token."""
    scored: list[tuple[float, int, TaxonomySubcategory, list[dict]]] = []
    for subcategory in subcategories:
        if subcategory.slug == "other":
            continue
        score, matches = _subcategory_rule_details(text, subcategory)
        if score > 0:
            scored.append((score, subcategory.sort_order, subcategory, matches))
    if not scored:
        if trace is not None:
            trace.log(
                "rules_subcategory",
                "info",
                "لایه قواعد هیچ نشانه‌ای برای زیردسته پیدا نکرد.",
                data={"scored": [], "winner": None},
            )
        return None, 0.0
    scored.sort(key=lambda item: (-item[0], item[1], item[2].id))
    top = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0
    winner = top[2] if top[0] >= 1.0 and top[0] - second_score >= 0.5 else None
    if trace is not None:
        trace.log(
            "rules_subcategory",
            "success" if winner is not None else "info",
            (
                f"لایه قواعد زیردسته «{winner.name}» را انتخاب کرد."
                if winner is not None
                else "لایه قواعد بین چند زیردسته مردد است؛ انتخاب نهایی به Laya سپرده می‌شود."
            ),
            data={
                "scored": [
                    {
                        "subcategory": _subcategory_payload(item[2]),
                        "score": round(item[0], 3),
                        "matches": item[3],
                    }
                    for item in scored[:10]
                ],
                "winner": _subcategory_payload(winner) if winner is not None else None,
                "top_score": round(top[0], 3),
                "second_score": round(second_score, 3),
            },
        )
    if winner is not None:
        return winner, top[0]
    return None, top[0]


async def load_taxonomy(session: AsyncSession) -> list[TaxonomyCategory]:
    category_rows = (
        (
            await session.execute(
                select(Category)
                .where(Category.deleted_at.is_(None), Category.is_active.is_(True))
                .order_by(Category.sort_order, Category.id)
            )
        )
        .scalars()
        .all()
    )
    subcategory_rows = (
        (
            await session.execute(
                select(Subcategory)
                .where(Subcategory.deleted_at.is_(None))
                .order_by(Subcategory.sort_order, Subcategory.id)
            )
        )
        .scalars()
        .all()
    )

    categories = [
        TaxonomyCategory(
            id=row.id,
            slug=row.slug,
            name=row.name,
            icon=row.icon,
            sort_order=row.sort_order,
        )
        for row in category_rows
    ]
    by_id = {category.id: category for category in categories}
    for row in subcategory_rows:
        category = by_id.get(row.category_id)
        if category is None:
            continue
        category.subcategories.append(
            TaxonomySubcategory(
                id=row.id,
                category_id=row.category_id,
                slug=row.slug,
                name=row.name,
                icon=row.icon,
                sort_order=row.sort_order,
                standard_tags=list(row.standard_tags or []),
            )
        )
    return categories


def _laya_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.LAYA_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LAYA_API_KEY}"
    return headers


async def _laya_choice(state: str, question: dict) -> dict:
    """Call one `choice` question on the Laya sidecar and return its answer."""
    headers = _laya_headers()

    payload = {
        "state": state,
        "questions": {"decision": question},
        "model": settings.LAYA_MODEL,
        "lang": "fa",
    }
    try:
        async with httpx.AsyncClient(
            base_url=settings.LAYA_BASE_URL,
            timeout=settings.LAYA_TIMEOUT_SECONDS,
            headers=headers,
        ) as client:
            response = await client.post("/v1/systemone", json=payload)
            response.raise_for_status()
            body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise LayaUnavailable(str(exc)) from exc

    answers = body.get("answers") if isinstance(body, dict) else None
    answer = answers.get("decision") if isinstance(answers, dict) else None
    if not isinstance(answer, dict) or answer.get("type") != "choice":
        raise LayaUnavailable("invalid_laya_response")
    if not isinstance(answer.get("probabilities"), dict):
        raise LayaUnavailable("invalid_laya_probabilities")
    return answer


async def _laya_health() -> dict:
    """Probe the sidecar's `/health` endpoint without failing the request."""
    started = time.perf_counter()
    if not settings.LAYA_ENABLED:
        return {
            "status": "skipped",
            "latency_ms": 0,
            "http_status": None,
            "detail": None,
            "error": None,
        }

    timeout = min(max(1.0, settings.LAYA_TIMEOUT_SECONDS), 4.0)
    try:
        async with httpx.AsyncClient(
            base_url=settings.LAYA_BASE_URL,
            timeout=timeout,
            headers=_laya_headers(),
        ) as client:
            response = await client.get("/health")
        try:
            detail = response.json()
        except ValueError:
            detail = response.text[:1200]
        return {
            "status": "ok" if response.is_success else "error",
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "http_status": response.status_code,
            "detail": detail,
            "error": None if response.is_success else f"HTTP {response.status_code}",
        }
    except (httpx.HTTPError, ValueError) as exc:
        return {
            "status": "unreachable",
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "http_status": None,
            "detail": None,
            "error": str(exc),
        }


def _probabilities(answer: dict, allowed: set[str]) -> dict[str, float]:
    raw = answer.get("probabilities")
    if not isinstance(raw, dict):
        raise LayaUnavailable("invalid_laya_probabilities")
    values: dict[str, float] = {}
    for key, value in raw.items():
        if str(key) not in allowed:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if 0.0 <= number <= 1.0:
            values[str(key)] = number
    if not values:
        raise LayaUnavailable("invalid_laya_probabilities")
    return values


def _ranked(probabilities: dict[str, float]) -> list[tuple[str, float]]:
    return sorted(probabilities.items(), key=lambda item: item[1], reverse=True)


def _quality(confidence: float) -> str:
    if confidence >= settings.LAYA_HIGH_CONFIDENCE:
        return "high"
    if confidence >= settings.LAYA_MEDIUM_CONFIDENCE:
        return "medium"
    return "low"


def _category_payload(category: TaxonomyCategory) -> dict:
    return {
        "id": category.id,
        "slug": category.slug,
        "name": category.name,
        "icon": category.icon,
        "sort_order": category.sort_order,
        "subcategory_count": len(category.subcategories),
    }


def _subcategory_payload(subcategory: TaxonomySubcategory) -> dict:
    return {
        "id": subcategory.id,
        "category_id": subcategory.category_id,
        "slug": subcategory.slug,
        "name": subcategory.name,
        "icon": subcategory.icon,
        "sort_order": subcategory.sort_order,
        "standard_tags": list(subcategory.standard_tags),
    }


def _suggestion(
    category: TaxonomyCategory,
    subcategory: TaxonomySubcategory | None,
    category_confidence: float,
    subcategory_confidence: float | None,
    category_source: str,
    subcategory_source: str | None,
) -> dict:
    if subcategory is None:
        confidence = category_confidence * 0.88
    else:
        confidence = (category_confidence * subcategory_confidence) ** 0.5
    confidence = round(min(max(confidence, 0.0), 1.0), 3)
    return {
        "category": _category_payload(category),
        "subcategory": _subcategory_payload(subcategory) if subcategory else None,
        "category_confidence": round(category_confidence, 3),
        "subcategory_confidence": (
            round(subcategory_confidence, 3) if subcategory_confidence is not None else None
        ),
        "confidence": confidence,
        "quality": _quality(confidence),
        "category_source": category_source,
        "subcategory_source": subcategory_source,
    }


def _empty(status: str, started: float, model: str | None = None) -> dict:
    return {
        "status": status,
        "enabled": settings.LAYA_ENABLED,
        "model": model or settings.LAYA_MODEL,
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
        "suggestions": [],
    }


def _category_only(
    category: TaxonomyCategory,
    category_confidence: float,
    category_source: str,
    started: float,
) -> dict:
    return {
        "status": "ok",
        "enabled": True,
        "model": settings.LAYA_MODEL,
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
        "suggestions": [
            _suggestion(
                category,
                None,
                category_confidence,
                None,
                category_source,
                None,
            )
        ],
    }


def _ok_result(suggestions: list[dict], started: float) -> dict:
    return {
        "status": "ok",
        "enabled": True,
        "model": settings.LAYA_MODEL,
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
        "suggestions": suggestions,
    }


def _ranking_payload(
    ranking: list[tuple[str, float]], criteria: dict[str, str]
) -> list[dict]:
    return [
        {
            "id": key,
            "name": criteria.get(key, key),
            "probability": round(probability, 4),
        }
        for key, probability in ranking
    ]


async def suggest_category(
    session: AsyncSession,
    title: str,
    description: str | None,
    *,
    rules_enabled: bool | None = None,
    trace: SuggestionTrace | None = None,
) -> dict:
    """Return ranked category/subcategory suggestions, or a safe empty result.

    ``rules_enabled`` and ``trace`` are used by the admin diagnostics tool.
    Production callers keep the default behavior from settings.
    """
    started = time.perf_counter()
    effective_rules = (
        settings.LAYA_RULES_ENABLED if rules_enabled is None else rules_enabled
    )

    if trace is not None:
        trace.log(
            "config",
            "info" if settings.LAYA_ENABLED else "error",
            (
                "Laya فعال است."
                if settings.LAYA_ENABLED
                else "Laya غیرفعال است (LAYA_ENABLED=false)."
            ),
            data={
                "enabled": settings.LAYA_ENABLED,
                "rules_enabled": effective_rules,
                "model": settings.LAYA_MODEL,
                "base_url": settings.LAYA_BASE_URL,
                "timeout_seconds": settings.LAYA_TIMEOUT_SECONDS,
            },
        )

    if not settings.LAYA_ENABLED:
        return _empty("disabled", started)

    state = build_state(title, description)
    if trace is not None:
        trace.state = state
        trace.log(
            "state",
            "debug",
            "متن ورودی پس از نرمال‌سازی آماده شد.",
            data={"normalized": state, "chars": len(state)},
        )
    if len(state) < 6:
        if trace is not None:
            trace.log(
                "state",
                "warning",
                "متن ورودی برای تصمیم‌گیری کوتاه است.",
            )
        return _empty("no_match", started)

    search_text = _normalize_text(f"{title} {description or ''}")
    taxonomy_started = time.perf_counter()
    categories = await load_taxonomy(session)
    choice_categories = [category for category in categories if category.slug != "other"]
    if trace is not None:
        trace.categories = categories
        trace.taxonomy = {
            "categories": len(categories),
            "choice_categories": len(choice_categories),
            "subcategories": sum(
                len(category.subcategories) for category in categories
            ),
        }
        trace.log(
            "taxonomy",
            "info" if choice_categories else "error",
            (
                f"{len(choice_categories)} دسته اصلی و "
                f"{trace.taxonomy['subcategories']} زیردسته بارگذاری شد."
            ),
            duration_ms=(time.perf_counter() - taxonomy_started) * 1000,
            data=trace.taxonomy,
        )
    if not choice_categories:
        return _empty("no_match", started)

    if effective_rules:
        rule_category, shortlist, _ = resolve_category_rule(
            search_text, choice_categories, trace=trace
        )
    else:
        rule_category, shortlist = None, choice_categories
        if trace is not None:
            trace.log(
                "rules_category",
                "info",
                "لایه قواعد فارسی خاموش است؛ Laya از میان همه دسته‌ها انتخاب می‌کند.",
            )

    if rule_category is not None:
        category = rule_category
        category_confidence = 0.95
        category_source = "rules"
        if trace is not None:
            trace.log(
                "category_decision",
                "success",
                f"لایه قواعد دسته «{category.name}» را انتخاب کرد.",
                data={
                    "category": _category_payload(category),
                    "confidence": category_confidence,
                },
            )
    else:
        # Laya's 17-way zero-shot category accuracy on the live Persian test
        # was weak. When the alias layer cannot pick a winner, give Laya the
        # narrowed shortlist (or all 17 when there were no hits) and require a
        # stronger confidence/margin before showing anything.
        category_criteria = _category_criteria(shortlist)
        category_question = {
            "type": "choice",
            "instructions": "این کسب‌وکار در کدام دسته اصلی قرار می‌گیرد؟",
            "criteria": category_criteria,
        }
        laya_started = time.perf_counter()
        try:
            category_answer = await _laya_choice(state, category_question)
            category_probs = _probabilities(category_answer, set(category_criteria))
            if trace is not None:
                trace.laya_successes += 1
        except LayaUnavailable as exc:
            if trace is not None:
                trace.laya_failures += 1
                trace.log(
                    "laya_category",
                    "error",
                    f"Laya برای دسته اصلی پاسخ نداد: {exc}",
                    duration_ms=(time.perf_counter() - laya_started) * 1000,
                    data={"error": str(exc)},
                )
            logger.warning("Laya category suggestion unavailable: %s", exc)
            return _empty("unavailable", started)

        category_ranking = _ranked(category_probs)
        top_category_key, category_confidence = category_ranking[0]
        margin = (
            category_ranking[0][1] - category_ranking[1][1]
            if len(category_ranking) > 1
            else 1.0
        )
        accepted = not (
            category_confidence < settings.LAYA_MIN_CATEGORY_CONFIDENCE
            or margin < settings.LAYA_MIN_CATEGORY_MARGIN
        )
        if trace is not None:
            trace.log(
                "laya_category",
                "success" if accepted else "warning",
                (
                    "پاسخ Laya برای دسته اصلی دریافت شد."
                    if accepted
                    else "پاسخ Laya برای دسته اصلی از آستانه عبور نکرد."
                ),
                duration_ms=(time.perf_counter() - laya_started) * 1000,
                data={
                    "criteria_count": len(category_criteria),
                    "ranking": _ranking_payload(category_ranking, category_criteria),
                    "confidence": round(category_confidence, 4),
                    "margin": round(margin, 4),
                    "min_confidence": settings.LAYA_MIN_CATEGORY_CONFIDENCE,
                    "min_margin": settings.LAYA_MIN_CATEGORY_MARGIN,
                    "accepted": accepted,
                },
            )
        if not accepted:
            if trace is not None:
                trace.log(
                    "category_decision",
                    "warning",
                    "Laya مطمئن نبود؛ برای جلوگیری از پیشنهاد اشتباه نتیجه‌ای نمایش داده نمی‌شود.",
                )
            return _empty("no_match", started)
        category = next(
            item for item in shortlist if str(item.id) == top_category_key
        )
        category_source = "laya"
        if trace is not None:
            trace.log(
                "category_decision",
                "success",
                f"Laya دسته «{category.name}» را انتخاب کرد.",
                data={
                    "category": _category_payload(category),
                    "confidence": round(category_confidence, 4),
                },
            )

    subcategories = [
        subcategory
        for subcategory in category.subcategories
        if subcategory.slug != "other"
    ]
    if not subcategories:
        if trace is not None:
            trace.log(
                "subcategory_decision",
                "info",
                "این دسته زیردسته ندارد؛ فقط دسته پیشنهاد می‌شود.",
            )
        return _category_only(
            category, category_confidence, category_source, started
        )

    if effective_rules:
        subcategory_rule, _ = resolve_subcategory_rule(
            search_text, subcategories, trace=trace
        )
    else:
        subcategory_rule = None
        if trace is not None:
            trace.log(
                "rules_subcategory",
                "info",
                "لایه قواعد زیردسته خاموش است؛ Laya انتخاب می‌کند.",
            )
    if subcategory_rule is not None:
        if trace is not None:
            trace.log(
                "subcategory_decision",
                "success",
                f"لایه قواعد زیردسته «{subcategory_rule.name}» را انتخاب کرد.",
                data={"subcategory": _subcategory_payload(subcategory_rule)},
            )
        return _ok_result(
            [
                _suggestion(
                    category,
                    subcategory_rule,
                    category_confidence,
                    0.92,
                    category_source,
                    "rules",
                )
            ],
            started,
        )

    subcategory_criteria = _subcategory_criteria(subcategories)
    subcategory_question = {
        "type": "choice",
        "instructions": (
            f"این کسب‌وکار در «{category.name}» کدام زیردسته را ارائه می‌دهد؟"
        ),
        "criteria": subcategory_criteria,
    }
    laya_started = time.perf_counter()
    try:
        subcategory_answer = await _laya_choice(state, subcategory_question)
        subcategory_probs = _probabilities(
            subcategory_answer, set(subcategory_criteria)
        )
        if trace is not None:
            trace.laya_successes += 1
    except LayaUnavailable as exc:
        if trace is not None:
            trace.laya_failures += 1
            trace.log(
                "laya_subcategory",
                "error",
                f"Laya برای زیردسته پاسخ نداد: {exc}",
                duration_ms=(time.perf_counter() - laya_started) * 1000,
                data={"error": str(exc)},
            )
        logger.warning("Laya subcategory suggestion unavailable: %s", exc)
        return _category_only(
            category, category_confidence, category_source, started
        )

    subcategory_by_id = {str(item.id): item for item in subcategories}
    suggestions: list[dict] = []
    for key, confidence in _ranked(subcategory_probs):
        subcategory = subcategory_by_id.get(key)
        if subcategory is None or confidence < settings.LAYA_MIN_SUBCATEGORY_CONFIDENCE:
            continue
        suggestions.append(
            _suggestion(
                category,
                subcategory,
                category_confidence,
                confidence,
                category_source,
                "laya",
            )
        )
        if len(suggestions) >= settings.LAYA_MAX_SUGGESTIONS:
            break

    if trace is not None:
        trace.log(
            "laya_subcategory",
            "success" if suggestions else "warning",
            (
                "پاسخ Laya برای زیردسته‌ها دریافت شد."
                if suggestions
                else "هیچ زیردسته‌ای از آستانه عبور نکرد."
            ),
            duration_ms=(time.perf_counter() - laya_started) * 1000,
            data={
                "criteria_count": len(subcategory_criteria),
                "ranking": _ranking_payload(
                    _ranked(subcategory_probs), subcategory_criteria
                ),
                "min_confidence": settings.LAYA_MIN_SUBCATEGORY_CONFIDENCE,
                "selected": [
                    suggestion["subcategory"]["name"] for suggestion in suggestions
                ],
            },
        )

    if not suggestions:
        if trace is not None:
            trace.log(
                "subcategory_decision",
                "warning",
                "زیردسته قطعی نشد؛ فقط دسته پیشنهاد می‌شود.",
            )
        return _category_only(
            category, category_confidence, category_source, started
        )

    if trace is not None:
        trace.log(
            "result",
            "success",
            "پیشنهاد نهایی آماده شد.",
            data={
                "suggestions": [
                    {
                        "category": suggestion["category"]["name"],
                        "subcategory": (
                            suggestion["subcategory"]["name"]
                            if suggestion["subcategory"]
                            else None
                        ),
                        "confidence": suggestion["confidence"],
                        "quality": suggestion["quality"],
                    }
                    for suggestion in suggestions
                ]
            },
        )
    return _ok_result(suggestions, started)


def _config_snapshot(effective_rules: bool) -> dict:
    """Public configuration for the admin diagnostics panel (never the key)."""
    return {
        "enabled": settings.LAYA_ENABLED,
        "rules_enabled": effective_rules,
        "base_url": settings.LAYA_BASE_URL,
        "model": settings.LAYA_MODEL,
        "timeout_seconds": settings.LAYA_TIMEOUT_SECONDS,
        "api_key_configured": bool(settings.LAYA_API_KEY),
        "max_suggestions": settings.LAYA_MAX_SUGGESTIONS,
        "thresholds": {
            "min_category_confidence": settings.LAYA_MIN_CATEGORY_CONFIDENCE,
            "min_category_margin": settings.LAYA_MIN_CATEGORY_MARGIN,
            "min_subcategory_confidence": settings.LAYA_MIN_SUBCATEGORY_CONFIDENCE,
            "high_confidence": settings.LAYA_HIGH_CONFIDENCE,
            "medium_confidence": settings.LAYA_MEDIUM_CONFIDENCE,
        },
    }


async def _probe_laya(
    state: str,
    categories: list[TaxonomyCategory],
    trace: SuggestionTrace,
) -> dict:
    """Ask Laya directly, even when the alias layer already decided.

    This is the part that proves actual model inference works. The normal
    pipeline intentionally skips Laya for obvious alias matches, so a healthy
    `/health` response alone is not enough evidence for an admin test.
    """
    choices = [category for category in categories if category.slug != "other"]
    if not choices:
        trace.probe = {"status": "unavailable", "error": "no_choices"}
        return trace.probe

    criteria = _category_criteria(choices)
    question = {
        "type": "choice",
        "instructions": "این کسب‌وکار در کدام دسته اصلی قرار می‌گیرد؟",
        "criteria": criteria,
    }
    trace.log(
        "laya_probe",
        "info",
        "بررسی مستقیم Laya شروع شد؛ این اجرا مستقل از لایه قواعد است.",
        data={"criteria_count": len(criteria)},
    )
    probe_started = time.perf_counter()
    try:
        answer = await _laya_choice(state, question)
        probabilities = _probabilities(answer, set(criteria))
        trace.laya_successes += 1
    except LayaUnavailable as exc:
        trace.laya_failures += 1
        trace.probe = {"status": "unavailable", "error": str(exc)}
        trace.log(
            "laya_probe",
            "error",
            f"Laya در بررسی مستقیم پاسخ نداد: {exc}",
            duration_ms=(time.perf_counter() - probe_started) * 1000,
            data={"error": str(exc)},
        )
        return trace.probe

    ranking = _ranked(probabilities)
    top_key, top_confidence = ranking[0]
    category = next(item for item in choices if str(item.id) == top_key)
    trace.log(
        "laya_probe_category",
        "success",
        f"Laya در بررسی مستقیم دسته «{category.name}» را انتخاب کرد.",
        duration_ms=(time.perf_counter() - probe_started) * 1000,
        data={
            "criteria_count": len(criteria),
            "ranking": _ranking_payload(ranking, criteria),
            "confidence": round(top_confidence, 4),
            "min_confidence": settings.LAYA_MIN_CATEGORY_CONFIDENCE,
            "accepted": top_confidence >= settings.LAYA_MIN_CATEGORY_CONFIDENCE,
        },
    )

    subcategories = [
        item for item in category.subcategories if item.slug != "other"
    ]
    probe: dict = {
        "status": "ok",
        "category": _category_payload(category),
        "category_confidence": round(top_confidence, 4),
        "category_ranking": _ranking_payload(ranking, criteria),
        "subcategory": None,
        "subcategory_confidence": None,
        "subcategory_ranking": [],
    }
    if not subcategories:
        trace.probe = probe
        return probe

    sub_criteria = _subcategory_criteria(subcategories)
    sub_question = {
        "type": "choice",
        "instructions": (
            f"این کسب‌وکار در «{category.name}» کدام زیردسته را ارائه می‌دهد؟"
        ),
        "criteria": sub_criteria,
    }
    sub_started = time.perf_counter()
    try:
        sub_answer = await _laya_choice(state, sub_question)
        sub_probabilities = _probabilities(sub_answer, set(sub_criteria))
        trace.laya_successes += 1
    except LayaUnavailable as exc:
        trace.laya_failures += 1
        probe["status"] = "partial"
        probe["error"] = str(exc)
        trace.log(
            "laya_probe_subcategory",
            "error",
            f"Laya در بررسی مستقیم زیردسته پاسخ نداد: {exc}",
            duration_ms=(time.perf_counter() - sub_started) * 1000,
            data={"error": str(exc)},
        )
        trace.probe = probe
        return probe

    sub_ranking = _ranked(sub_probabilities)
    sub_key, sub_confidence = sub_ranking[0]
    subcategory = next(item for item in subcategories if str(item.id) == sub_key)
    probe["subcategory"] = _subcategory_payload(subcategory)
    probe["subcategory_confidence"] = round(sub_confidence, 4)
    probe["subcategory_ranking"] = _ranking_payload(sub_ranking, sub_criteria)
    trace.log(
        "laya_probe_subcategory",
        "success",
        f"Laya در بررسی مستقیم زیردسته «{subcategory.name}» را انتخاب کرد.",
        duration_ms=(time.perf_counter() - sub_started) * 1000,
        data={
            "criteria_count": len(sub_criteria),
            "ranking": probe["subcategory_ranking"],
            "confidence": round(sub_confidence, 4),
            "min_confidence": settings.LAYA_MIN_SUBCATEGORY_CONFIDENCE,
            "accepted": sub_confidence >= settings.LAYA_MIN_SUBCATEGORY_CONFIDENCE,
        },
    )
    trace.probe = probe
    return probe


def _verdict(
    result: dict, health: dict, trace: SuggestionTrace
) -> tuple[str, str]:
    if not settings.LAYA_ENABLED:
        return (
            "disabled",
            "Laya غیرفعال است؛ پیشنهاد خودکار در فرم ثبت کسب‌وکار اجرا نمی‌شود.",
        )
    if result["status"] == "unavailable":
        return (
            "unavailable",
            "Laya پاسخ نداد یا پاسخ معتبر برنگرداند؛ فرم به انتخاب دستی برمی‌گردد.",
        )
    if result["status"] == "no_match":
        return (
            "no_match",
            "Laya پاسخ داد اما با آستانه‌های فعلی از تصمیم‌گیری خودداری کرد.",
        )
    if result["status"] == "ok" and trace.laya_successes > 0:
        return (
            "working",
            "Laya پاسخ داد و خط لوله پیشنهاد کامل شد.",
        )
    if result["status"] == "ok" and health.get("status") == "ok":
        return (
            "rules_only",
            "لایه قواعد پاسخ داد؛ Laya در این اجرا فراخوانی نشد. "
            "برای تست خود مدل، «بررسی مستقیم Laya» را روشن کنید.",
        )
    if result["status"] == "ok":
        return (
            "degraded",
            "لایه قواعد کار کرد اما Laya در دسترس نیست؛ پیشنهادها ممکن است محدود بمانند.",
        )
    return ("unknown", "وضعیت مدل مشخص نشد؛ لاگ‌های پایین را بررسی کنید.")


def _event_data(trace: SuggestionTrace, stage: str) -> dict:
    for event in reversed(trace.events):
        if event.get("stage") == stage:
            data = event.get("data")
            return data if isinstance(data, dict) else {}
    return {}


def _tuning_hints(
    *,
    effective_rules: bool,
    result: dict,
    health: dict,
    trace: SuggestionTrace,
    total_ms: int,
) -> list[dict]:
    hints: list[dict] = []

    def add(severity: str, title: str, detail: str) -> None:
        hints.append({"severity": severity, "title": title, "detail": detail})

    if not settings.LAYA_ENABLED:
        add(
            "critical",
            "Laya خاموش است",
            "برای تست، LAYA_ENABLED=true را در محیط API تنظیم و سرویس laya را اجرا کنید.",
        )
        return hints

    if health.get("status") == "unreachable":
        add(
            "critical",
            "سرویس Laya در دسترس نیست",
            "آدرس LAYA_BASE_URL، بالا بودن کانتینر laya و لاگ‌های آن را بررسی کنید.",
        )
    elif health.get("status") == "error":
        add(
            "warning",
            "health سرویس Laya خطا برگرداند",
            f"کد HTTP: {health.get('http_status')} — پاسخ سرویس را در لاگ health ببینید.",
        )

    if trace.laya_failures:
        add(
            "critical",
            "حداقل یک فراخوانی Laya ناموفق بود",
            "خطای دقیق در لاگ‌های laya_* آمده است. اگر timeout است، LAYA_TIMEOUT_SECONDS یا منابع CPU را بررسی کنید.",
        )

    if result["status"] == "ok" and not trace.laya_successes and effective_rules:
        add(
            "info",
            "همه تصمیم‌های این اجرا با لایه قواعد گرفته شد",
            "برای دیدن نظر خام مدل، «بررسی مستقیم Laya» را روشن کنید یا لایه قواعد را خاموش کنید.",
        )

    rules_data = _event_data(trace, "rules_category")
    if effective_rules and rules_data.get("scored") == []:
        add(
            "info",
            "هیچ alias فارسی با این متن هم‌خوان نبود",
            "اگر این نوع کسب‌وکار تکرار می‌شود، افزودن alias به CATEGORY_ALIASES دقت لایه قواعد را بالا می‌برد.",
        )

    laya_category = _event_data(trace, "laya_category")
    if laya_category:
        confidence = float(laya_category.get("confidence") or 0)
        margin = float(laya_category.get("margin") or 0)
        if not laya_category.get("accepted"):
            add(
                "warning",
                "دسته اصلی از آستانه عبور نکرد",
                f"confidence={confidence:.2f} و margin={margin:.2f}. "
                "اگر خروجی مدل درست ولی محافظه‌کارانه است، آستانه‌ها را اندکی پایین بیاورید.",
            )
        elif margin < settings.LAYA_MIN_CATEGORY_MARGIN + 0.08:
            add(
                "info",
                "حاشیه تصمیم دسته نزدیک آستانه است",
                f"margin={margin:.2f} در برابر حد {settings.LAYA_MIN_CATEGORY_MARGIN:.2f}. "
                "افزودن alias یا نمونه‌های آموزشی بیشتر به پایداری کمک می‌کند.",
            )

    laya_subcategory = _event_data(trace, "laya_subcategory")
    if laya_subcategory and not laya_subcategory.get("selected"):
        add(
            "warning",
            "هیچ زیردسته‌ای از آستانه عبور نکرد",
            "اگر مدل تقریباً درست است، LAYA_MIN_SUBCATEGORY_CONFIDENCE را کم‌کم پایین بیاورید؛ "
            "اگر کاملاً اشتباه است، برچسب‌های استاندارد همان زیردسته را تقویت کنید.",
        )

    if result["status"] == "ok" and result["suggestions"]:
        first = result["suggestions"][0]
        if first.get("subcategory") is None:
            add(
                "info",
                "فقط دسته پیشنهاد شد، نه زیردسته",
                "برای این متن زیردسته قطعی نبود. افزودن نام سرویس یا برچسب استاندارد به متن کسب‌وکار کمک می‌کند.",
            )

    probe = trace.probe
    if probe and probe.get("status") == "ok" and result["status"] == "ok" and result["suggestions"]:
        first = result["suggestions"][0]
        probe_category = probe.get("category") or {}
        if probe_category.get("id") != first["category"]["id"]:
            add(
                "warning",
                "لایه قواعد و Laya در دسته اختلاف دارند",
                f"نتیجه نهایی: «{first['category']['name']}» / نظر مستقیم Laya: «{probe_category.get('name')}». "
                "اگر Laya درست است، alias یا آستانه‌ها را بازبینی کنید.",
            )
        probe_subcategory = probe.get("subcategory") or {}
        result_subcategory = first.get("subcategory") or {}
        if (
            result_subcategory
            and probe_subcategory
            and result_subcategory.get("id") != probe_subcategory.get("id")
        ):
            add(
                "info",
                "زیردسته نهایی با نظر مستقیم Laya متفاوت است",
                f"نتیجه نهایی: «{result_subcategory.get('name')}» / نظر Laya: «{probe_subcategory.get('name')}». "
                "این اختلاف برای تنظیم آستانه یا برچسب‌ها مفید است.",
            )

    if not effective_rules:
        add(
            "info",
            "اجرای خام Laya (بدون لایه قواعد)",
            "برای مقایسه، همین متن را یک بار دیگر با لایه قواعد روشن اجرا کنید.",
        )

    if total_ms > 4000:
        add(
            "warning",
            "پاسخ‌دهی کند است",
            f"این اجرا {total_ms} میلی‌ثانیه طول کشید. LAYA_THREADS و منابع CPU کانتینر laya را بررسی کنید.",
        )

    return hints


async def diagnose_category(
    session: AsyncSession,
    title: str,
    description: str | None,
    *,
    rules_enabled: bool | None = None,
    probe_laya: bool = True,
) -> dict:
    """Run the production suggestion pipeline with diagnostics and a model probe.

    This is read-only and admin-only. It never changes settings or persisted
    data; the toggles affect this one diagnostic run only.
    """
    started = time.perf_counter()
    effective_rules = (
        settings.LAYA_RULES_ENABLED if rules_enabled is None else rules_enabled
    )
    trace = SuggestionTrace()

    health = await _laya_health()
    trace.log(
        "health",
        (
            "success"
            if health["status"] == "ok"
            else "warning"
            if health["status"] == "skipped"
            else "error"
        ),
        (
            "health سرویس Laya سالم است."
            if health["status"] == "ok"
            else "بررسی health انجام نشد چون Laya غیرفعال است."
            if health["status"] == "skipped"
            else f"health سرویس Laya ناموفق بود: {health.get('error')}"
        ),
        duration_ms=health["latency_ms"],
        data=health,
    )

    result = await suggest_category(
        session,
        title,
        description,
        rules_enabled=effective_rules,
        trace=trace,
    )

    if not settings.LAYA_ENABLED:
        pass
    elif probe_laya and not effective_rules:
        trace.log(
            "laya_probe",
            "info",
            "این اجرا خودش Laya خام است؛ بررسی مستقیم جداگانه لازم نیست.",
        )
    elif probe_laya and result["status"] != "unavailable" and trace.categories:
        await _probe_laya(trace.state, trace.categories, trace)
    elif probe_laya and result["status"] == "unavailable":
        trace.log(
            "laya_probe",
            "warning",
            "بررسی مستقیم انجام نشد چون خط لوله اصلی نتوانست به Laya وصل شود.",
        )

    total_ms = round((time.perf_counter() - started) * 1000)
    verdict, verdict_message = _verdict(result, health, trace)
    logger.info(
        "Laya diagnostics: verdict=%s status=%s model=%s health=%s "
        "laya_calls=%s failures=%s total_ms=%s",
        verdict,
        result["status"],
        settings.LAYA_MODEL,
        health.get("status"),
        trace.laya_successes,
        trace.laya_failures,
        total_ms,
    )
    hints = _tuning_hints(
        effective_rules=effective_rules,
        result=result,
        health=health,
        trace=trace,
        total_ms=total_ms,
    )

    return {
        "status": result["status"],
        "verdict": verdict,
        "verdict_message": verdict_message,
        "enabled": settings.LAYA_ENABLED,
        "model": settings.LAYA_MODEL,
        "elapsed_ms": total_ms,
        "pipeline_elapsed_ms": result["elapsed_ms"],
        "config": _config_snapshot(effective_rules),
        "health": health,
        "taxonomy": trace.taxonomy,
        "state": {"text": trace.state, "chars": len(trace.state)},
        "suggestions": result["suggestions"],
        "events": trace.events,
        "probe": trace.probe,
        "tuning": hints,
    }
