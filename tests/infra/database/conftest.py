"""Keep legacy database tests independent of the shared checkout filesystem."""
import pytest


@pytest.fixture(autouse=True)
def isolated_database_path(request, tmp_path, monkeypatch):
    # Upstream tests reuse a module-level test.db beside their source files.
    # A fresh local path avoids sharing SQLite WAL/SHM files across tests and
    # avoids file-lock stalls when the repository lives on a network mount.
    if hasattr(request.module, "test_db_filepath"):
        monkeypatch.setattr(request.module, "test_db_filepath",
                            str(tmp_path / "test.db"))
