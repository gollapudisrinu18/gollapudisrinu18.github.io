#!/usr/bin/env python3
"""Generate the synthetic dataset and its manifest for the Azure drill."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drlib  # noqa: E402

out = sys.argv[1] if len(sys.argv) > 1 else "drill-data"
cfg = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")))
drlib.generate_dataset(out, cfg["dataset_files"], cfg["records_per_file"])
vault = tempfile.mkdtemp()
_, manifest = drlib.take_backup(out, vault)
with open(out + ".manifest.json", "w") as fh:
    json.dump(manifest, fh, indent=2)
print(f"{out}/ ({manifest['records']} records) and {out}.manifest.json written")
