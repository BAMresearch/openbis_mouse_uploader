def test_imports() -> None:
    import mouse_openbis_uploader  # noqa: F401
    from mouse_openbis_uploader.cli import build_parser  # noqa: F401
    from mouse_openbis_uploader.config import UploadConfig  # noqa: F401
