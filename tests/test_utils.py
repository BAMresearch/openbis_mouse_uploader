import pytest

from mouse_openbis_uploader.utils import (
    bam_person_identifier,
    read_token,
    split_name,
    validate_ymd,
)


def test_validate_ymd_accepts_eight_digits() -> None:
    assert validate_ymd("20251220") == "20251220"


@pytest.mark.parametrize(
    "value",
    ["2025", "2025-12-20", "abcdefghi", "1234567a"],
)
def test_validate_ymd_rejects_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        validate_ymd(value)


def test_read_token_strips_whitespace(tmp_path) -> None:
    token_path = tmp_path / "token.txt"
    token_path.write_text("  secret-token \n", encoding="utf-8")
    assert read_token(token_path) == "secret-token"


def test_read_token_empty_raises(tmp_path) -> None:
    token_path = tmp_path / "token.txt"
    token_path.write_text("   \n", encoding="utf-8")
    with pytest.raises(RuntimeError):
        read_token(token_path)


def test_read_token_missing_raises(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        read_token(tmp_path / "missing.txt")


def test_bam_person_identifier_uppercases() -> None:
    assert bam_person_identifier("abC123") == "/BAM_GLOBAL/BAM_DATA/ABC123"


def test_split_name_handles_multi_and_single() -> None:
    assert split_name("Ada Lovelace") == ("Ada", "Lovelace")
    assert split_name("Prince") == ("Prince", "")
    assert split_name("   ") == ("", "")
