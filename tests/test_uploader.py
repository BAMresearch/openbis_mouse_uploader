import logging

from mouse_openbis_uploader.config import UploadConfig
from mouse_openbis_uploader.uploader import OpenBISUploader


class _Collector:
    def __init__(self) -> None:
        self.records = []

    def record(self, rec) -> None:
        self.records.append(rec)


class _DummyDS:
    def __init__(self, objects=None) -> None:
        self._objects = objects if objects is not None else []

    def get_space(self, _name: str):
        return object()

    def get_objects(self, *args, **kwargs):
        return list(self._objects)


class _DummyReader:
    def __init__(self, entries):
        self.entries = entries


class _DummyProject:
    def __init__(self, name: str):
        self.name = name
        self.email = "lead@example.org"
        self.organisation = "BAM"
        self.title = "Title"
        self.description = "Desc"


class _DummyEntry:
    def __init__(self):
        self.ymd = "20250101"
        self.batchnum = "1"
        self.proposal = "PROP1234"
        self.project = _DummyProject("Ada Lovelace")


class _GuardUploader(OpenBISUploader):
    def find_instrument(self):
        return object()

    def require_project(self, project_code: str):
        return object()

    def get_or_create_collection(self, project, project_code: str, code: str):
        return object()

    def people_collection_for_proposal_year(self, project, project_code: str, proposal_year: str):
        return object()

    def _find_bam_person_by_name(self, full_name: str):
        raise AssertionError("Should not be called when PERSON upsert fails")

    def upsert_object(self, *, object_type: str, **kwargs):
        if object_type == "PERSON":
            return None
        raise AssertionError(f"Unexpected upsert call for {object_type}")


def test_process_entries_short_circuits_on_person_failure() -> None:
    collector = _Collector()
    uploader = _GuardUploader(
        ds=_DummyDS(),
        config=UploadConfig(ymd_filter="20250101", start_row=0),
        logger=logging.getLogger("test"),
        dry_run=True,
        failure_recorder=collector,
    )
    reader = _DummyReader([_DummyEntry()])

    uploader.process_entries(reader)

    assert len(collector.records) == 1
    assert collector.records[0].stage == "entry.missing.PERSON"


def test_upload_entry_datasets_records_missing_measurement() -> None:
    collector = _Collector()
    uploader = OpenBISUploader(
        ds=_DummyDS(objects=[]),
        config=UploadConfig(ymd_filter="20250101", start_row=0),
        logger=logging.getLogger("test"),
        dry_run=True,
        failure_recorder=collector,
    )

    entry = _DummyEntry()
    uploader._upload_entry_datasets(entry, "20250101-1")

    assert len(collector.records) == 1
    assert collector.records[0].stage == "dataset.missing_measurement"
