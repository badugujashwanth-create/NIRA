from __future__ import annotations

import json
import shutil
from pathlib import Path


class FineTuningTools:
    def export_lora_bundle(self, dataset_path: Path, output_dir: Path) -> Path:
        dataset_path = Path(dataset_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        copied_dataset = output_dir / dataset_path.name
        shutil.copy2(dataset_path, copied_dataset)
        manifest = {
            "dataset": copied_dataset.name,
            "format": "jsonl",
            "purpose": "local_lora_training",
        }
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8")
        return manifest_path
