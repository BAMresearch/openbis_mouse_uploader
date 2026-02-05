from __future__ import annotations

from pathlib import Path


def validate_ymd(ymd: str) -> str:
    """Validate YMD as an 8-digit string (e.g. 20251220)."""
    ymd = ymd.strip()
    if len(ymd) != 8 or not ymd.isdigit():
        raise ValueError("YMD must be 8 digits like 20251220")
    return ymd


def read_token(path: Path) -> str:
    """Read a non-empty token from a file."""
    if not path.is_file():
        raise FileNotFoundError(f"Token file not found: {path}")
    token = path.read_text(encoding="utf-8").strip()
    if not token:
        raise RuntimeError(f"Token file is empty: {path}")
    return token


def bam_person_identifier(username: str) -> str:
    """OpenBIS identifier for BAM persons: /BAM_GLOBAL/BAM_DATA/<USERNAME> (uppercased)."""
    return f"/BAM_GLOBAL/BAM_DATA/{username}".upper()


def split_name(full_name: str) -> tuple[str, str]:
    """Best-effort name split: first token -> given name, remainder -> family name."""
    parts = full_name.strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])
