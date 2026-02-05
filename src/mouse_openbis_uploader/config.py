from __future__ import annotations

from pathlib import Path

from attrs import define


@define(frozen=True, slots=True)
class UploadConfig:
    """Configuration for uploading a measurement batch to OpenBIS."""

    # Required (CLI positional)
    ymd_filter: str  # e.g. "20251220"

    # Optional
    ds_username: str = "bpauw"

    logbook_path: Path = Path("/mnt/vsi-db/Measurements/SAXS002/logbooks/Logbook_MOUSE_Dataprocessing.xlsx")
    proposal_base_path: Path = Path("/mnt/vsi-db/Proposals/SAXS002/")
    base_data_path: Path = Path("/mnt/vsi-db/Measurements/SAXS002/data")
    datastore_token_path: Path = Path.home() / ".datastore_token"

    space_name: str = "6.5_PROJECTS"
    projects_prepend: str = "MOUSE_PROJECTS_"

    start_row: int = 1

    server_url: str = "https://main.datastore.bam.de"
    sleep_seconds_between_ops: float = 0.5
    sleep_seconds_between_datasets: float = 1.0

    instrument_name_pattern: str = "MOUSE*"
    people_collection_prefix: str = "PEOPLE_"

    raw_dataset_type: str = "RAW_DATA"
    processed_dataset_type: str = "PROCESSED_DATA"
