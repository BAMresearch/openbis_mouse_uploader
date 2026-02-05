import json

from mouse_openbis_uploader.failures import FailureRecord, FailureRecorder


def test_failure_recorder_writes_jsonl(tmp_path) -> None:
    path = tmp_path / "logs" / "failures.jsonl"
    recorder = FailureRecorder(path)
    rec = FailureRecord(
        stage="upsert.create.PROJECT",
        ymd="20251220",
        batchnum="7",
        proposal="PROP-123",
        identifier=None,
        message="boom",
        extra={"key": "value"},
    )

    recorder.record(rec)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["stage"] == rec.stage
    assert payload["ymd"] == rec.ymd
    assert payload["batchnum"] == rec.batchnum
    assert payload["proposal"] == rec.proposal
    assert payload["identifier"] is None
    assert payload["message"] == rec.message
    assert payload["extra"] == rec.extra
