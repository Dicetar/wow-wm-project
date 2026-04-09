from __future__ import annotations

from pathlib import Path

from wm.sources.addon_log.models import AddonLogCursor
from wm.sources.addon_log.models import AddonLogLine
from wm.sources.addon_log.models import AddonLogTailResult
from wm.sources.addon_log.models import fingerprint_for_path


class AddonLogTailer:
    def __init__(self, *, path: Path) -> None:
        self.path = path

    def read(
        self,
        *,
        cursor: AddonLogCursor | None,
        max_lines: int,
    ) -> AddonLogTailResult:
        cursor = cursor or AddonLogCursor(path=str(self.path))
        path = Path(cursor.path or self.path)
        if not path.exists():
            return AddonLogTailResult(
                file_exists=False,
                path=str(path),
                cursor=AddonLogCursor(path=str(path), offset=0, fingerprint=None),
                lines=[],
            )

        fingerprint = fingerprint_for_path(path)
        starting_offset = int(cursor.offset)
        if cursor.fingerprint not in (None, fingerprint):
            starting_offset = 0

        file_size = path.stat().st_size
        if file_size < starting_offset:
            starting_offset = 0

        lines: list[AddonLogLine] = []
        with path.open("rb") as handle:
            handle.seek(starting_offset)
            while len(lines) < max(0, int(max_lines)):
                byte_offset = handle.tell()
                chunk = handle.readline()
                if chunk == b"":
                    break
                raw_line = chunk.decode("utf-8", errors="replace").rstrip("\r\n")
                lines.append(AddonLogLine(byte_offset=int(byte_offset), raw_line=raw_line))
            next_offset = handle.tell()

        return AddonLogTailResult(
            file_exists=True,
            path=str(path),
            cursor=AddonLogCursor(path=str(path), offset=int(next_offset), fingerprint=fingerprint),
            lines=lines,
        )
