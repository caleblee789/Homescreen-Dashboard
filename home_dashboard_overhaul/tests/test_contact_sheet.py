from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "qa" / "build_contact_sheet.py"
SPEC = importlib.util.spec_from_file_location("build_contact_sheet", SCRIPT)
if SPEC is None or SPEC.loader is None:  # pragma: no cover
    raise RuntimeError("Unable to import contact-sheet builder")
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class ContactSheetOrderingTests(unittest.TestCase):
    def _image(self, path: Path) -> None:
        Image.new("RGB", (8, 8), "white").save(path)

    def test_stable_ids_sort_in_canonical_suite_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("NFS-01.png", "SET-20.png", "CAL-02.png", "RST-01.png", "INS-01.png"):
                self._image(root / name)
            self.assertEqual(
                [path.name for path in BUILDER.ordered_images(root)],
                ["CAL-02.png", "INS-01.png", "SET-20.png", "RST-01.png", "NFS-01.png"],
            )

    def test_manifest_order_is_authoritative_and_missing_capture_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps({"records": [{"stable_id": "INS-01"}, {"stable_id": "CAL-01"}]}),
                encoding="utf-8",
            )
            self._image(root / "CAL-01.png")
            with self.assertRaisesRegex(ValueError, "missing: INS-01"):
                BUILDER.ordered_images(root, manifest)
            self._image(root / "INS-01.png")
            self.assertEqual(
                [path.stem for path in BUILDER.ordered_images(root, manifest)],
                ["INS-01", "CAL-01"],
            )

    def test_manifest_titles_are_used_in_stable_id_captions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "records": [
                            {"stable_id": "CAL-01", "title": "Year Desktop Light Populated"},
                            {"stable_id": "NFS-04", "title": "Settings Populated Event Preview"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            captions = BUILDER.manifest_captions(manifest)
            self.assertEqual(
                BUILDER.caption_for(root / "CAL-01.png", captions),
                "CAL-01  Year Desktop Light Populated",
            )
            self.assertEqual(
                BUILDER.caption_for(root / "NFS-04.png", captions),
                "NFS-04  Settings Populated Event Preview",
            )
            self.assertNotEqual(
                BUILDER.caption_for(root / "CAL-01.png", captions),
                "CAL-01  CAL-01",
            )


if __name__ == "__main__":
    unittest.main()
