from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class FailureRecord:
    stage: str  # e.g. "upsert.PROJECT", "upload.RAW_DATA"
    ymd: str
    batchnum: str
    proposal: str
    identifier: str | None  # openbis identifier if known
    message: str
    extra: dict[str, Any]


class FailureRecorder:
    """
    Appends one JSON object per failure to a .jsonl file.
    Designed for large batch runs (streaming write, no big memory use).
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, rec: FailureRecord) -> None:
        payload = {
            "stage": rec.stage,
            "ymd": rec.ymd,
            "batchnum": rec.batchnum,
            "proposal": rec.proposal,
            "identifier": rec.identifier,
            "message": rec.message,
            "extra": rec.extra,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
