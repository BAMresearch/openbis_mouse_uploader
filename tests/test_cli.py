from argparse import Namespace

import pytest

from mouse_openbis_uploader.cli import _validate_args


def _make_args(tmp_path) -> Namespace:
    logbook_path = tmp_path / "logbook.xlsx"
    logbook_path.write_text("dummy", encoding="utf-8")
    proposal_base_path = tmp_path / "proposals"
    proposal_base_path.mkdir()
    base_data_path = tmp_path / "data"
    base_data_path.mkdir()
    datastore_token_path = tmp_path / "token.txt"
    datastore_token_path.write_text("token", encoding="utf-8")
    return Namespace(
        start_row=0,
        sleep_seconds_between_ops=0.0,
        sleep_seconds_between_datasets=0.0,
        logbook_path=logbook_path,
        proposal_base_path=proposal_base_path,
        base_data_path=base_data_path,
        datastore_token_path=datastore_token_path,
    )


def test_validate_args_happy_path(tmp_path) -> None:
    args = _make_args(tmp_path)
    _validate_args(args)


def test_validate_args_rejects_negative_start_row(tmp_path) -> None:
    args = _make_args(tmp_path)
    args.start_row = -1
    with pytest.raises(SystemExit, match="--start-row"):
        _validate_args(args)


def test_validate_args_missing_logbook(tmp_path) -> None:
    args = _make_args(tmp_path)
    args.logbook_path = tmp_path / "missing.xlsx"
    with pytest.raises(SystemExit, match="Logbook file not found"):
        _validate_args(args)
