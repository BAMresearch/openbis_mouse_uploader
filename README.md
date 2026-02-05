# MOUSE OpenBIS Uploader

A small CLI tool to upload MOUSE SAXS measurement batches to OpenBIS based on a **YMD** day code
(e.g. `20251220`). It reads the measurement metadata from the Excel logbook and uploads/updates
OpenBIS objects and datasets (RAW and PROCESSED).

## Install (editable)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

## Token-based authentication

The CLI uses a token stored in a file (default: `~/.datastore_token`).

- Make sure the token file exists and contains a non-empty token string.
- Override the path via `--datastore-token-path`.

## Usage

Minimal (only required argument is the YMD code):

```bash
openbis-mouse-uploader 20251220
```

More verbose logging:

```bash
openbis-mouse-uploader 20251220 --log-level DEBUG
```

Continue from a later row in the logbook:

```bash
openbis-mouse-uploader 20251220 --start-row 50
```

Dry-run (no writes; logs intended actions):

```bash
openbis-mouse-uploader 20251220 --dry-run
```

## Notes on behavior

- **People collections are grouped by proposal year**: `PEOPLE_<proposal-year>`.
- **Duplicate objects should not exist**. If they do, the uploader logs a warning and deletes
  duplicates permanently until a single object remains.
- If the project-leader BAM record is not found, the `project_leader_bam` property is **omitted**.

## Development

- Formatting/linting: `ruff`
- Typing: `mypy` (configured to ignore missing third-party stubs)
- Pre-commit: `pre-commit`

Setup:

```bash
pip install -e ".[dev]"
pre-commit install
```

Example:

```bash
ruff format .
ruff check .
mypy src
pytest
```
