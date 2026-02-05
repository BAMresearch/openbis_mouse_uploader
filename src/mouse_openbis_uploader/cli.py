from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional, Sequence

from pybis import Openbis

from logbook2mouse.logbook_reader import Logbook2MouseReader

from .config import UploadConfig
from .logging_utils import setup_logger
from .uploader import OpenBISUploader
from .utils import read_token, validate_ymd
from .failures import FailureRecorder


def build_parser() -> argparse.ArgumentParser:
    d = UploadConfig(ymd_filter="19700101")  # dummy for defaults
    p = argparse.ArgumentParser(
        prog="openbis-mouse-uploader",
        description="Upload MOUSE measurement batches to OpenBIS using a YMD filter.",
    )

    p.add_argument("ymd", type=validate_ymd, help="Measurement day code, e.g. 20251220")

    p.add_argument("--ds-username", default=d.ds_username, help=f"Username label for logging (default: {d.ds_username})")
    p.add_argument("--logbook-path", type=Path, default=d.logbook_path, help=f"Excel logbook (default: {d.logbook_path})")
    p.add_argument("--proposal-base-path", type=Path, default=d.proposal_base_path, help=f"Proposal base path (default: {d.proposal_base_path})")
    p.add_argument("--base-data-path", type=Path, default=d.base_data_path, help=f"Base data path (default: {d.base_data_path})")
    p.add_argument("--datastore-token-path", type=Path, default=d.datastore_token_path, help=f"Token file path (default: {d.datastore_token_path})")

    p.add_argument("--space-name", default=d.space_name, help=f"Space name (default: {d.space_name})")
    p.add_argument("--projects-prepend", default=d.projects_prepend, help=f"Project prefix (default: {d.projects_prepend})")
    p.add_argument("--start-row", type=int, default=d.start_row, help=f"Start row index (default: {d.start_row})")

    p.add_argument("--server-url", default=d.server_url, help=f"OpenBIS URL (default: {d.server_url})")
    p.add_argument("--sleep-seconds-between-ops", type=float, default=d.sleep_seconds_between_ops, help=f"Sleep between ops (default: {d.sleep_seconds_between_ops})")
    p.add_argument("--sleep-seconds-between-datasets", type=float, default=d.sleep_seconds_between_datasets, help=f"Sleep between datasets (default: {d.sleep_seconds_between_datasets})")

    p.add_argument("--instrument-name-pattern", default=d.instrument_name_pattern, help=f"Instrument name pattern (default: {d.instrument_name_pattern})")
    p.add_argument("--people-collection-prefix", default=d.people_collection_prefix, help=f"People collection prefix (default: {d.people_collection_prefix})")

    p.add_argument("--raw-dataset-type", default=d.raw_dataset_type, help=f"Raw dataset type (default: {d.raw_dataset_type})")
    p.add_argument("--processed-dataset-type", default=d.processed_dataset_type, help=f"Processed dataset type (default: {d.processed_dataset_type})")
    p.add_argument("--log-file", type=Path, default=None, help="Log file path (default: None, logs to stdout only)")
    p.add_argument("--failure-file", type=Path, default=None, help="Failure records file (default: upload_failures.jsonl)")

    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity",
    )
    p.add_argument("--dry-run", action="store_true", help="No writes; log intended actions")

    return p


def _validate_args(args: argparse.Namespace) -> None:
    if args.start_row < 0:
        raise SystemExit("--start-row must be >= 0")
    if args.sleep_seconds_between_ops < 0:
        raise SystemExit("--sleep-seconds-between-ops must be >= 0")
    if args.sleep_seconds_between_datasets < 0:
        raise SystemExit("--sleep-seconds-between-datasets must be >= 0")

    if not args.logbook_path.is_file():
        raise SystemExit(f"Logbook file not found: {args.logbook_path}")
    if not args.proposal_base_path.exists():
        raise SystemExit(f"Proposal base path does not exist: {args.proposal_base_path}")
    if not args.base_data_path.exists():
        raise SystemExit(f"Base data path does not exist: {args.base_data_path}")
    if not args.datastore_token_path.is_file():
        raise SystemExit(f"Token file not found: {args.datastore_token_path}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _validate_args(args)

    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    logger = setup_logger(level=log_level, log_file=args.log_file)

    cfg = UploadConfig(
        ymd_filter=args.ymd,
        ds_username=args.ds_username,
        logbook_path=args.logbook_path,
        proposal_base_path=args.proposal_base_path,
        base_data_path=args.base_data_path,
        datastore_token_path=args.datastore_token_path,
        space_name=args.space_name,
        projects_prepend=args.projects_prepend,
        start_row=args.start_row,
        server_url=args.server_url,
        sleep_seconds_between_ops=args.sleep_seconds_between_ops,
        sleep_seconds_between_datasets=args.sleep_seconds_between_datasets,
        instrument_name_pattern=args.instrument_name_pattern,
        people_collection_prefix=args.people_collection_prefix,
        raw_dataset_type=args.raw_dataset_type,
        processed_dataset_type=args.processed_dataset_type,
    )

    token = read_token(cfg.datastore_token_path)
    ds = Openbis(url=cfg.server_url, verify_certificates=True)
    ds.set_token(token)
    logger.info("Connected to OpenBIS at %s as %s", cfg.server_url, cfg.ds_username)

    reader = Logbook2MouseReader(
        cfg.logbook_path,
        project_base_path=cfg.proposal_base_path,
        load_all=True,
    )

    failure_recorder = FailureRecorder(args.failure_file or Path(f"upload_failures_{args.ymd}.jsonl"))

    uploader = OpenBISUploader(ds=ds, config=cfg, logger=logger, dry_run=args.dry_run, failure_recorder=failure_recorder)
    uploader.process_entries(reader)
    logger.info("Upload run completed. Failures recorded (if any) to: %s", failure_recorder.path)
    return 0
