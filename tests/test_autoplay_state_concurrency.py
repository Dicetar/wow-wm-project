from concurrent.futures import ThreadPoolExecutor
import json

from wm.autoplay.state import AutoplayStateStore


def test_write_json_uses_unique_temporary_files_for_concurrent_writers(tmp_path):
    path = tmp_path / "status.json"

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda value: AutoplayStateStore.write_json(path, {"value": value}), range(40)))

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["value"] in range(40)
    assert list(tmp_path.glob("*.tmp")) == []
