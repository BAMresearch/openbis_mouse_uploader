from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logger(
    name: str = "openbis_upload_MOUSE",
    level: int = logging.INFO,
    *,
    log_file: Path | None = None,
) -> logging.Logger:
    logger = logging.getLogger(name)

    if not logger.handlers:
        date_fmt = "%Y%m%dT%H:%M:%S"
        fmt = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s: %(message)s",
            datefmt=date_fmt,
        )

        sh = logging.StreamHandler(stream=sys.stdout)
        sh.setFormatter(fmt)
        logger.addHandler(sh)

        if log_file is not None:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(fmt)
            logger.addHandler(fh)

    logger.setLevel(level)
    return logger
