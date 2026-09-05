from __future__ import annotations

from pathlib import Path
import unittest

from home_dashboard_overhaul.tools import build_ankiaddon as build


ROOT = Path(__file__).resolve().parents[1]


class PackageReleaseContractTests(unittest.TestCase):
    def test_allowlist_is_the_exact_25_member_contract(self) -> None:
        self.assertEqual(
            tuple(build.PACKAGE_FILES),
            (
                "__init__.py", "analytics.py", "insights.py", "config.json",
                "config.md", "config_schema.py", "controller.py",
                "default_verses.json", "LICENSE.txt", "manifest.json",
                "migration.py", "models.py", "README.md", "CHANGELOG.md",
                "renderer.py", "settings.py", "settings_model.py", "themes.py",
                "THIRD_PARTY_NOTICES.md", "ui_primitives.py", "verse.py",
                "web/dashboard.css", "web/dashboard.js", "user_files/README.txt",
                "assets/buy_me_a_coffee.png",
            ),
        )
        self.assertEqual(len(build.PACKAGE_FILES), 25)
        self.assertFalse(set(build.PACKAGE_FILES) & build.DEFERRED_SOURCE_FILES)
        self.assertFalse(any(name.startswith("_vendor/") for name in build.PACKAGE_FILES))

    def test_packaged_inputs_compile_and_pass_legal_secret_and_link_gates(self) -> None:
        build._validate_package_inputs()

    def test_safe_path_gate_rejects_cross_platform_escape_forms(self) -> None:
        for unsafe in (
            "", "/absolute.py", "../escape.py", "dir/../escape.py",
            "dir//file.py", "dir/./file.py", "..\\escape.py",
            "C:/escape.py", "__pycache__/module.py", "dir/__pycache__/module.py",
        ):
            with self.subTest(path=unsafe):
                self.assertFalse(build._archive_path_is_safe(unsafe))
        self.assertTrue(build._archive_path_is_safe("web/dashboard.js"))

    def test_secret_gate_rejects_high_confidence_credentials_without_echoing_them(self) -> None:
        sample = "client_" + "secret = " + repr("s" * 24)
        with self.assertRaisesRegex(ValueError, "assigned credential.*fixture.py"):
            build._validate_no_packaged_secrets({"fixture.py": sample})

    def test_archive_metadata_and_installed_parity_hooks_are_locked(self) -> None:
        info = build._zip_info("settings.py")
        self.assertEqual(info.date_time, build.FIXED_TIMESTAMP)
        self.assertEqual(info.external_attr, 0o100644 << 16)
        base_probe = (ROOT / "qa" / "runtime_probe_release_1_8_4.py").read_text(
            encoding="utf-8"
        )
        assembler = (ROOT / "qa" / "assemble_release_evidence_1_8_7.py").read_text(
            encoding="utf-8"
        )
        for marker in (
            "hashlib.sha256(archive.read(member)).hexdigest() == _sha256(installed)",
            '"installed_member_parity": "passed"',
        ):
            self.assertIn(marker, base_probe)
        self.assertGreaterEqual(
            assembler.count('candidate.get("installed_member_parity") == "passed"'),
            1,
        )


if __name__ == "__main__":
    unittest.main()
