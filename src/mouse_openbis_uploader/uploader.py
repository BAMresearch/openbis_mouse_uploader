from __future__ import annotations

import filecmp
import logging
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Optional, Sequence

from pybis import Openbis

from logbook2mouse.logbook_reader import Logbook2MouseReader

from .config import UploadConfig
from .utils import bam_person_identifier, split_name
from .failures import FailureRecord, FailureRecorder


class OpenBISUploader:
    """
    Uploads MOUSE measurement batches to OpenBIS based on a YMD filter.

    Notes on policy:
    - People collections are grouped by proposal year: PEOPLE_<proposal-year>.
    - Duplicates should not exist. If they do, we log a warning and delete permanently.
    - If project-leader BAM record is not found, project_leader_bam is omitted.
    """

    def __init__(
        self,
        ds: Openbis,
        config: UploadConfig,
        logger: logging.Logger,
        *,
        dry_run: bool = False,
        failure_recorder: FailureRecorder | None = None,
    ) -> None:
        self.ds = ds
        self.cfg = config
        self.log = logger
        self.dry_run = dry_run
        self.failures = failure_recorder
        self.space = self.ds.get_space(self.cfg.space_name)

    # ---------- identifiers ----------

    def project_code_for_proposal(self, proposal: str) -> str:
        return f"{self.cfg.projects_prepend}{proposal[:4]}"

    def project_identifier(self, project_code: str) -> str:
        return f"/{self.cfg.space_name}/{project_code}"

    def collection_identifier(self, project_code: str, collection_code: str) -> str:
        return f"/{self.cfg.space_name}/{project_code}/{collection_code}"

    # ---------- ensure objects ----------

    def require_project(self, project_code: str) -> Any:
        project_id = self.project_identifier(project_code)
        try:
            return self.ds.get_project(project_id)
        except ValueError as e:
            raise RuntimeError(
                f"Project does not exist in OpenBIS: {project_id}. Create it first."
            ) from e

    def get_or_create_collection(self, project: Any, project_code: str, code: str) -> Any:
        identifier = self.collection_identifier(project_code, code)
        try:
            return self.ds.get_collection(identifier)
        except (KeyError, ValueError):
            if self.dry_run:
                self.log.info("[dry-run] Would create collection: %s", identifier)
                raise RuntimeError(f"[dry-run] Collection does not exist yet: {identifier}")

            col = self.ds.new_collection(code=code, type="COLLECTION", project=project)
            col.save()
            self._sleep(self.cfg.sleep_seconds_between_ops)
            self.log.info("Created new collection: %s", identifier)
            return col

    def people_collection_for_proposal_year(self, project: Any, project_code: str, proposal_year: str) -> Any:
        code = f"{self.cfg.people_collection_prefix}{proposal_year}"
        return self.get_or_create_collection(project, project_code, code)

    def find_instrument(self) -> Any:
        instruments = self.ds.get_objects(
            type="INSTRUMENT",
            where={"$name": self.cfg.instrument_name_pattern},
            props=["$name"],
        )
        if not instruments:
            raise RuntimeError(f"No INSTRUMENT found matching {self.cfg.instrument_name_pattern!r}")
        return instruments[0]

    # ---------- upsert ----------

    def upsert_object(
        self,
        *,
        object_type: str,
        where: Mapping[str, Any],
        props: Mapping[str, Any],
        project: Any,
        collection: Any,
        space: Any,
    ) -> Any:
        objs = self.ds.get_objects(type=object_type, where=dict(where), project=project.permId)

        if len(objs) > 1:
            self.log.warning(
                "Duplicates found (unexpected) for type=%s where=%s count=%d; deleting permanently.",
                object_type, where, len(objs),
            )
            if self.dry_run:
                self.log.info(
                    "[dry-run] Would delete %d duplicates for %s where=%s",
                    len(objs) - 1,
                    object_type,
                    where,
                )
            else:
                while len(objs) > 1:
                    victim = objs[0]
                    victim.delete(
                        reason="duplicate entry removed via upsert_object (unexpected duplicates)",
                        permanently=True,
                    )
                    objs = self.ds.get_objects(type=object_type, where=dict(where), project=project.permId)
                    self.log.info("Deleted one duplicate; remaining=%d", len(objs))

        if not objs:
            try:
                obj = self.ds.new_object(
                    type=object_type,
                    space=space,
                    project=project,
                    collection=collection,
                )
                obj.props = dict(props)
                if not self.dry_run:
                    obj.save()
                self.log.info("Created %s: %s", object_type, props.get("$name", "<no $name>"))
                self._sleep(self.cfg.sleep_seconds_between_ops)
                return obj
            except Exception as e:
                self.log.exception("Create failed for %s where=%s", object_type, where)
                self.failures.record(FailureRecord(
                    stage=f"upsert.create.{object_type}",
                    ymd=self.cfg.ymd_filter,
                    batchnum=str(props.get("$name", "")),
                    proposal=str(props.get("$name", "")),
                    identifier=None,
                    message=str(e),
                    extra={"where": dict(where), "props_keys": sorted(props.keys())},
                ))
                return None

        obj = objs[0]
        current: MutableMapping[str, Any] = obj.props.all()
        current.update(dict(props))
        obj.props = current

        if self.dry_run:
            self.log.info("[dry-run] Would update %s: %s", object_type, props.get("$name", "<no $name>"))
            return obj

        try:
            obj.save()
            self.log.info("Updated %s: %s", object_type, props.get("$name", "<no $name>"))
            return obj
        except Exception as e:
            self.log.exception("Update failed for %s where=%s", object_type, where)
            self.failures.record(FailureRecord(
                stage=f"upsert.update.{object_type}",
                ymd=self.cfg.ymd_filter,
                batchnum=str(props.get("$name", "")),
                proposal=str(props.get("$name", "")),
                identifier=getattr(obj, "identifier", None),
                message=str(e),
                extra={"where": dict(where), "props_keys": sorted(props.keys())},
            ))
            return None

    # ---------- dataset upload ----------

    def upload_dataset_if_needed(self, obj: Any, dataset_type: str, files: Sequence[Path]) -> None:
        if not files:
            return

        def files_match(local: Sequence[Path], downloaded: Sequence[Path]) -> bool:
            if len(local) != len(downloaded):
                return False
            by_name = {p.name: p for p in downloaded}
            for lf in local:
                rf = by_name.get(lf.name)
                if rf is None or not filecmp.cmp(lf, rf, shallow=False):
                    return False
            return True

        for dataset in obj.get_datasets(type=dataset_type):
            with tempfile.TemporaryDirectory() as tempdir:
                dataset.download(destination=tempdir)
                ds_files = [p for p in Path(tempdir).rglob("*") if p.is_file()]
                if files_match(files, ds_files):
                    self.log.info("Dataset %s already up-to-date; skipping.", dataset_type)
                    return
            self.log.info("Dataset %s needs update; deleting old dataset.", dataset_type)
            if self.dry_run:
                self.log.info("[dry-run] Would delete dataset %s", dataset_type)
            else:
                dataset.delete("Needs update")

        if not obj.get_datasets(type=dataset_type):
            if self.dry_run:
                self.log.info("[dry-run] Would upload dataset %s with %d files.", dataset_type, len(files))
                return
            ds_new = self.ds.new_dataset(
                type=dataset_type,
                collection=obj.collection,
                object=obj,
                files=list(files),
            )
            ds_new.save()
            self.log.info("Uploaded new dataset %s with %d files.", dataset_type, len(files))

    # ---------- orchestration ----------

    def process_entries(self, reader: Logbook2MouseReader) -> None:
        entries = reader.entries[self.cfg.start_row:]
        self.log.info("Entries available=%d; processing from start_row=%d", len(reader.entries), self.cfg.start_row)

        instrument = self.find_instrument()

        for idx, entry in enumerate(entries, start=self.cfg.start_row):
            if self.cfg.ymd_filter != str(entry.ymd):
                self.log.debug("Skipping idx=%d: ymd=%s (filter=%s)", idx, entry.ymd, self.cfg.ymd_filter)
                continue

            try:
                measurement_name = f"{entry.ymd}-{entry.batchnum}"
                self.log.info("Processing idx=%d: %s (proposal=%s)", idx, measurement_name, entry.proposal)

                project_code = self.project_code_for_proposal(entry.proposal)
                project = self.require_project(project_code)

                proposal_collection = self.get_or_create_collection(project, project_code, entry.proposal)
                people_collection = self.people_collection_for_proposal_year(project, project_code, entry.proposal[:4])

                given, family = split_name(entry.project.name)
                person_leader = self.upsert_object(
                    object_type="PERSON",
                    where={"$name": entry.project.name},
                    props={
                        "$name": entry.project.name,
                        "family_name": family,
                        "given_name": given,
                        "email": entry.project.email,
                        "affiliation": entry.project.organisation,
                    },
                    space=self.space,
                    project=project,
                    collection=people_collection,
                )

                user_bam = self._find_bam_person_by_name(entry.project.name)

                proposal_props: dict[str, Any] = {
                    "$name": entry.proposal,
                    "abstract": entry.project.title,
                    "description": entry.project.description,
                    "project_leader": entry.project.name,
                    "project_status": "IN_PROGRESS",
                    "bam_oe": "OE_6.5",
                }
                if user_bam is not None:
                    proposal_props["project_leader_bam"] = user_bam.permId

                proposal_obj = self.upsert_object(
                    object_type="PROJECT",
                    where={"$name": entry.proposal},
                    props=proposal_props,
                    space=self.space,
                    project=project,
                    collection=proposal_collection,
                )

                sample_name = f"{entry.proposal}-{entry.sampleid}"
                sample_obj = self.upsert_object(
                    object_type="SAMPLE",
                    where={"$name": sample_name},
                    props={
                        "$name": sample_name,
                        "alias": entry.sample.sample_name,
                        "description": entry.sample.composition,
                        "sample_id_number": entry.sample.sample_id,
                        "responsible_person": person_leader.permId,
                        "bam_room": "ROO_07_816B",
                        "bam_house": "HOU_30",
                        "bam_floor": "FLO_7",
                        "bam_location": "LOC_UE",
                        "bam_location_complete": "UE_30_7_07_816B",
                        "bam_oe": "OE_6.5",
                    },
                    space=self.space,
                    project=project,
                    collection=proposal_collection,
                )

                responsible_person = self.ds.get_object(bam_person_identifier(entry.user)).permId
                meas_obj = self.upsert_object(
                    object_type="EXPERIMENTAL_STEP.SAXS_MEASUREMENT.MOUSE_MEASUREMENT",
                    where={"$name": measurement_name},
                    props={
                        "$name": measurement_name,
                        "finished_flag": True,
                        "measurement_date": entry.date.date().isoformat(),
                        "exposure_time_in_seconds": 600.0,
                        "responsible_person": responsible_person,
                        "sample_position": entry.sampos,
                        "measurement_protocol_file": str(entry.protocol),
                        "measurement_protocol_options": str(entry.additional_parameters),
                        "size_thickness_in_millimeter": entry.samplethickness / 1e-3,
                        "processing_protocol_file": str(entry.procpipeline),
                    },
                    space=self.space,
                    project=project,
                    collection=proposal_collection,
                )

                if self.dry_run:
                    self.log.info("[dry-run] Would link parents for %s", measurement_name)
                else:
                    meas_obj.add_parents([sample_obj, proposal_obj, person_leader, instrument])
                    meas_obj.save()

                self._upload_entry_datasets(entry, measurement_name)
                self.log.info("Finished idx=%d: %s", idx, measurement_name)
            except Exception as e:
                self.log.exception("Unexpected entry failure idx=%d ymd=%s batch=%s", idx, entry.ymd, entry.batchnum)
                self.failures.record(FailureRecord(
                    stage="entry.unexpected",
                    ymd=str(entry.ymd),
                    batchnum=str(entry.batchnum),
                    proposal=str(entry.proposal),
                    identifier=None,
                    message=str(e),
                    extra={},
                ))
                continue

    # ---------- helpers ----------

    def _find_bam_person_by_name(self, full_name: str) -> Optional[Any]:
        search_string = f"*{full_name.replace(' ', '*')}*"
        matches = self.ds.get_objects(type="PERSON", where={"$name": search_string}, props=["$name"])
        if not matches:
            self.log.info("No BAM PERSON match for name=%r", full_name)
            return None
        try:
            return self.ds.get_object(matches[0].identifier)
        except Exception:
            self.log.exception("Failed to load BAM PERSON object for identifier=%s", matches[0].identifier)
            return None

    def _upload_entry_datasets(self, entry: Any, measurement_name: str) -> None:
        meas_obj = self.ds.get_objects(
            type="EXPERIMENTAL_STEP.SAXS_MEASUREMENT.MOUSE_MEASUREMENT",
            where={"$name": measurement_name},
            props=["$name"],
        )[0]

        ymd = str(entry.ymd)
        base = self.cfg.base_data_path / ymd[:4] / ymd

        raw_files = sorted(base.glob(f"MOUSE_{entry.ymd}_{entry.batchnum}_*stacked.nxs"))
        self.log.info("Raw files found=%d for %s", len(raw_files), measurement_name)
        if raw_files:
            self.upload_dataset_if_needed(meas_obj, self.cfg.raw_dataset_type, raw_files)
            self._sleep(self.cfg.sleep_seconds_between_datasets)
        else:
            self.log.warning("No raw files found for %s; skipping RAW_DATA upload.", measurement_name)

        processed_files = sorted(
            (base / "autoproc").glob(f"**/MOUSE_{entry.ymd}_{entry.batchnum}_*_stacked_processed.nxs")
        )
        self.log.info("Processed files found=%d for %s", len(processed_files), measurement_name)
        if processed_files:
            self.upload_dataset_if_needed(meas_obj, self.cfg.processed_dataset_type, processed_files)
            self._sleep(self.cfg.sleep_seconds_between_datasets)
        else:
            self.log.warning("No processed files found for %s; skipping PROCESSED_DATA upload.", measurement_name)

    def _sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)
