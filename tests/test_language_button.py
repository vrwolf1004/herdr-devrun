import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  (src 경로 준비)
import i18n
import panel
import term
from i18n import t


class LanguageKeyTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.config_dir = Path(self.folder.name) / "plugin-config"
        self.path = Path(self.folder.name) / ".herdr-devrun.json"
        self.path.write_text(json.dumps({"services": [{"name": "api", "command": "x"}]}), encoding="utf-8")
        self.make_panel()
        self.addCleanup(i18n.set_language, "en")

    def make_panel(self):
        self.panel = panel.Panel(self.path, None)
        self.panel.reload_config()

    def saved(self):
        return json.loads((self.config_dir / "config.json").read_text(encoding="utf-8")).get("lang")

    def test_language_button_is_removed_from_the_bottom_row(self):
        self.assertNotIn("language", [command for command, _, _ in self.panel.button_specs()])

    def test_ctrl_l_is_the_language_command(self):
        self.assertEqual(self.panel.command_for(term.Event("key", key="\x0c")), "language")

    def test_ctrl_l_cycles_system_then_supported_order(self):
        seen = []
        with mock.patch.dict(os.environ, {"HERDR_PLUGIN_CONFIG_DIR": str(self.config_dir)}):
            for _ in range(len(i18n.CYCLE)):
                self.panel.execute("language")
                seen.append(i18n.saved_language())
        self.assertEqual(seen, list(i18n.SUPPORTED) + [None])
        self.assertIsNone(self.panel.form)

    def test_each_press_applies_and_saves_the_language(self):
        with mock.patch.dict(os.environ, {"HERDR_PLUGIN_CONFIG_DIR": str(self.config_dir)}):
            self.panel.execute("language")
            self.assertEqual(i18n.language(), "en")
            self.assertEqual(self.saved(), "en")
            self.panel.execute("language")
        self.assertEqual(i18n.language(), "ko")
        self.assertEqual(self.saved(), "ko")
        self.assertEqual(self.panel.message, t("panel.language_changed", name="한국어"))

    def test_system_removes_the_saved_value_and_starts_again_from_environment(self):
        self.config_dir.mkdir()
        (self.config_dir / "config.json").write_text(json.dumps({"lang": "ja", "other": 1}), encoding="utf-8")
        with mock.patch.dict(os.environ, {"HERDR_PLUGIN_CONFIG_DIR": str(self.config_dir), "HERDR_DEVRUN_LANG": "fr"}):
            self.make_panel()
            self.panel.execute("language")
            saved = json.loads((self.config_dir / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, {"other": 1})
        self.assertEqual(i18n.language(), "fr")

    def test_without_config_dir_cycles_for_this_run_only(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("HERDR_PLUGIN_CONFIG_DIR", None)
            self.panel.execute("language")
            self.panel.execute("language")
        self.assertEqual(i18n.language(), "ko")
        self.assertEqual(self.panel.message, t("panel.language_not_saved", name="한국어"))

    def test_save_keeps_other_keys_in_config(self):
        self.config_dir.mkdir()
        (self.config_dir / "config.json").write_text(json.dumps({"lang": "en", "other": 1}), encoding="utf-8")
        with mock.patch.dict(os.environ, {"HERDR_PLUGIN_CONFIG_DIR": str(self.config_dir)}):
            self.assertTrue(i18n.save_language("de"))
        saved = json.loads((self.config_dir / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, {"lang": "de", "other": 1})

    def test_save_does_not_overwrite_a_broken_config(self):
        self.config_dir.mkdir()
        broken = self.config_dir / "config.json"
        broken.write_text("{bad", encoding="utf-8")
        with mock.patch.dict(os.environ, {"HERDR_PLUGIN_CONFIG_DIR": str(self.config_dir)}):
            self.assertFalse(i18n.save_language("ko"))
        self.assertEqual(broken.read_text(encoding="utf-8"), "{bad")


if __name__ == "__main__":
    unittest.main()
