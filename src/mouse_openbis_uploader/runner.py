from __future__ import annotations

import logging

from pybis import Openbis
from logbook2mouse.logbook_reader import Logbook2MouseReader

from .config import UploadConfig
from .logging_utils import setup_logger
from .uploader import OpenBISUploader
from .utils import read_token


def run_upload(config: UploadConfig, *, log_level: int = logging.INFO, dry_run: bool = False) -> None:
    """Programmatic entry point (useful for notebooks)."""
    logger = setup_logger(level=log_level)

    reader = Logbook2MouseReader(
        config.logbook_path,
        project_base_path=config.proposal_base_path,
        load_all=True,
    )

    token = read_token(config.datastore_token_path)
    ds = Openbis(url=config.server_url, verify_certificates=True)
    ds.set_token(token)
    logger.info("Connected to OpenBIS at %s as %s", config.server_url, config.ds_username)

    uploader = OpenBISUploader(ds=ds, config=config, logger=logger, dry_run=dry_run)
    uploader.process_entries(reader)
