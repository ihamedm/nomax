from datetime import datetime, timedelta, timezone

import pytest

from app.core import security
from app.core.errors import AppError


def test_national_id_checksum_valid() -> None:
    assert security.validate_iranian_national_id("1234567891") is True


def test_national_id_checksum_invalid() -> None:
    assert security.validate_iranian_national_id("1234567892") is False


def test_national_id_rejects_short_input() -> None:
    assert security.validate_iranian_national_id("12345") is False


def test_normalize_phone_accepts_leading_zero_form() -> None:
    assert security.normalize_phone("09123456789") == "9123456789"


def test_normalize_phone_accepts_country_code_form() -> None:
    assert security.normalize_phone("989123456789") == "9123456789"


def test_normalize_phone_rejects_invalid() -> None:
    with pytest.raises(AppError) as exc_info:
        security.normalize_phone("12345")
    assert exc_info.value.status_code == 422


def test_otp_hash_roundtrip() -> None:
    hashed = security.hash_otp("123456")
    assert hashed != "123456"
    assert security.verify_otp("123456", hashed) is True
    assert security.verify_otp("654321", hashed) is False


def test_access_token_rejects_garbage() -> None:
    with pytest.raises(AppError) as exc_info:
        security.decode_access_token("garbage.token.here")
    assert exc_info.value.status_code == 401
