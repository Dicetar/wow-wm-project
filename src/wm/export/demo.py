from __future__ import annotations

from pathlib import Path

from wm.export.loader import load_export
from wm.export.models import ExportBundle, RowListExport


def main() -> None:
    sample_bundle_path = Path(r"D:\WOW\db_export\acore_world\creature_template.json")
    full_lookup_path = Path(r"D:\WOW\wm-project\data\lookup\creature_template_full.json")

    if sample_bundle_path.exists():
        loaded = load_export(sample_bundle_path)
        print("=== SAMPLE BUNDLE EXPORT ===")
        if isinstance(loaded, ExportBundle):
            print(f"table: {loaded.table}")
            print(f"row_count: {loaded.row_count}")
            print(f"sample_count: {loaded.sample_count}")
            print(f"schema_columns: {len(loaded.schema)}")
            print(f"first_sample_keys: {list(loaded.samples[0].keys())[:10] if loaded.samples else []}")
        print()

    if full_lookup_path.exists():
        loaded = load_export(full_lookup_path)
        print("=== FULL ROW LIST EXPORT ===")
        if isinstance(loaded, RowListExport):
            print(f"rows: {len(loaded.rows)}")
            print(f"first_row_keys: {list(loaded.rows[0].keys())[:10] if loaded.rows else []}")


if __name__ == "__main__":
    main()
