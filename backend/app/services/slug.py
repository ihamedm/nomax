"""ASCII slugs for public business URLs.

Persian names are transliterated so `/businesses/<slug>` stays URL-safe and
readable: «کافه ستاره» becomes `kafe-stare`.
"""
from __future__ import annotations

import re

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business

_LETTERS = str.maketrans(
    {
        "آ": "a", "ا": "a", "أ": "a", "إ": "e", "ٱ": "a",
        "ب": "b", "پ": "p", "ت": "t", "ث": "s", "ج": "j", "چ": "ch",
        "ح": "h", "خ": "kh", "د": "d", "ذ": "z", "ر": "r", "ز": "z",
        "ژ": "zh", "س": "s", "ش": "sh", "ص": "s", "ض": "z", "ط": "t",
        "ظ": "z", "ع": "a", "غ": "gh", "ف": "f", "ق": "gh", "ک": "k",
        "ك": "k", "گ": "g", "ل": "l", "م": "m", "ن": "n", "و": "u",
        "ؤ": "o", "ه": "h", "ة": "h", "ی": "i", "ي": "i", "ئ": "y",
        "ء": "",
        "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
        "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
        "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
        "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    }
)
_NON_SLUG = re.compile(r"[^a-z0-9]+")
# Persian short vowels are unwritten, so some letters double as vowels:
# final ه (کافه → kafe), ی/و at word end or before a consonant (امید → amid).
# Before another vowel they stay consonants (دنیا → dnya).
_FINAL_H = re.compile(r"(?<![اآ])ه(?=$|[^آ-ی])")
_Y_VOWEL_WORD = re.compile(r"ی(?=[آاویه])")
_W_VOWEL_WORD = re.compile(r"و(?=[آاویه])")


def slugify(value: str) -> str:
    text = _FINAL_H.sub("e", value)
    text = _Y_VOWEL_WORD.sub("y", text)
    text = _W_VOWEL_WORD.sub("v", text)
    return _NON_SLUG.sub("-", text.translate(_LETTERS).lower()).strip("-")


async def unique_business_slug(session: AsyncSession, name: str) -> str:
    """Slug from the business name; `-2`, `-3`… when the base is taken."""
    # shortcut: check-then-insert means two concurrent creates of the same name
    # can still collide on the unique index; add an IntegrityError retry if that
    # ever shows up in practice.
    base = slugify(name)[:80].strip("-") or "business"
    slug, suffix = base, 2
    while (
        await session.execute(sa.select(Business.id).where(Business.slug == slug))
    ).first() is not None:
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug
