"""
Safe Data Persistence Module
Provides atomic write operations to prevent file corruption during unexpected crashes or interrupts.
"""
import os
import json
from pathlib import Path
from typing import Any


def atomic_save_json(file_path: Path, data: Any, indent: int = 2) -> None:
    """
    Atomically writes data to a target JSON file.
    Writes to a sibling .tmp file first, flushes and fsyncs to disk,
    then atomically renames to the destination file.
    If an error occurs, the .tmp file is removed and the original file is left intact.
    """
    path = Path(file_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")

    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception as e:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        raise IOError(f"Atomic write to {path} failed: {e}") from e
