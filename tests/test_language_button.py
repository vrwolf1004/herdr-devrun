import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  (src 경로 준비)
import i18n
import panel
from i18n import t


class LanguageButtonTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.config_dir = Path(self.folder.name) / "plugin-config"
        path = Path(self.folder.name) / ".herdr-devrun.json"
        path.write_text(json.dumps({"services": [{"name": "api", "command": "x"}]}), encoding="utf-8")
        self.panel = panel.Panel(path, None)
        self.panel.reload_config()
        self.addCleanup(i18n.set_language, "en")

    def choose(self, code):
        self.panel.form["cursor"] = i18n.SUPPORTED.index(code)
        self.panel.form_submit()

    def test_language_button_is_in_the_bottom_row(self):
        self.assertIn("language", [command for command, _, _ in self.panel.button_specs()])

    def test_button_opens_a_list_with_the_current_language_selected(self):
        i18n.set_language("ko")
        self.panel.execute("language")
        self.assertEqual(self.panel.form["mode"], "language")
        self.assertEqual([value for value, _ in self.panel.form_options()], list(i18n.SUPPORTED))
        self.assertEqual(self.panel.form["cursor"], i18n.SUPPORTED.index("ko"))

    def test_choosing_a_language_applies_it_and_saves_it(self):
        with mock.patch.dict(os.environ, {"HERDR_PLUGIN_CONFIG_DIR": str(self.config_dir)}):
            self.panel.execute("language")
            self.choose("ja")
            saved = json.loads((self.config_dir / "config.json").read_text(encoding="utf-8"))
        self.assertIsNone(self.panel.form)
        self.assertEqual(i18n.language(), "ja")
        self.assertEqual(saved["lang"], "ja")
        self.assertEqual(self.panel.message, t("panel.language_changed", name="日本語"))

    def test_choosing_without_config_dir_applies_for_this_run_only(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("HERDR_PLUGIN_CONFIG_DIR", None)
            self.panel.execute("language")
            self.choose("de")
        self.assertEqual(i18n.language(), "de")
        self.assertEqual(self.panel.message, t("panel.language_not_saved", name="Deutsch"))

    def test_escape_keeps_the_current_language(self):
        self.panel.execute("language")
        self.panel.form_input(mock.Mock(key="esc"))
        self.assertIsNone(self.panel.form)
        self.assertEqual(i18n.language(), "en")

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
