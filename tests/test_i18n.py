import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  (src 경로 준비)
import i18n

PLACEHOLDER = re.compile(r"{(\w+)}")


def load(language):
    return json.loads((i18n.LOCALES_DIR / f"{language}.json").read_text(encoding="utf-8"))


class LocaleFilesTest(unittest.TestCase):
    def test_every_language_has_same_keys_and_placeholders(self):
        base = load(i18n.DEFAULT)
        for language in i18n.SUPPORTED:
            with self.subTest(language=language):
                messages = load(language)
                self.assertEqual(set(messages), set(base))
                for key, text in base.items():
                    self.assertEqual(set(PLACEHOLDER.findall(messages[key])), set(PLACEHOLDER.findall(text)), key)

    def test_keys_used_in_code_exist(self):
        base = load(i18n.DEFAULT)
        for path in i18n.LOCALES_DIR.parent.glob("*.py"):
            for key in re.findall(r"""\bt\(\s*["']([\w.]+)["']""", path.read_text(encoding="utf-8")):
                if not key.endswith("."):
                    self.assertIn(key, base, f"{path.name}: {key}")


class TranslateTest(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("en")

    def test_format_and_fallbacks(self):
        i18n.set_language("ko")
        self.assertEqual(i18n.t("panel.started", name="api"), "api 시작")
        self.assertEqual(i18n.t("panel.started"), "{name} 시작")  # 인자를 빠뜨려도 죽지 않는다
        self.assertEqual(i18n.t("no.such.key"), "no.such.key")

    def test_unsupported_language_is_english(self):
        i18n.set_language("zh")
        self.assertEqual(i18n.language(), "en")


class DetectTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        patcher = mock.patch.dict(os.environ, {}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in ("HERDR_DEVRUN_LANG", "HERDR_PLUGIN_CONFIG_DIR"):
            os.environ.pop(name, None)

    def tearDown(self):
        self.folder.cleanup()

    def plugin_config(self, language):
        Path(self.folder.name, "config.json").write_text(json.dumps({"lang": language}), encoding="utf-8")
        os.environ["HERDR_PLUGIN_CONFIG_DIR"] = self.folder.name

    def test_normalize(self):
        self.assertEqual(i18n.normalize("ko_KR.UTF-8"), "ko")
        self.assertEqual(i18n.normalize("pt-BR"), None)
        self.assertEqual(i18n.normalize("DE"), "de")

    def test_order_env_then_config_then_os_then_en(self):
        with mock.patch.object(i18n, "_from_os", return_value="ja"):
            self.assertEqual(i18n.detect(), "ja")
            self.plugin_config("fr")
            self.assertEqual(i18n.detect(), "fr")
            os.environ["HERDR_DEVRUN_LANG"] = "ru"
            self.assertEqual(i18n.detect(), "ru")
        os.environ.pop("HERDR_DEVRUN_LANG")
        os.environ.pop("HERDR_PLUGIN_CONFIG_DIR")
        with mock.patch.object(i18n, "_from_os", return_value=None):
            self.assertEqual(i18n.detect(), "en")

    def test_unix_locale_variables(self):
        with mock.patch.object(i18n.sys, "platform", "linux"):
            with mock.patch.dict(os.environ, {"LC_ALL": "", "LC_MESSAGES": "", "LANG": "de_DE.UTF-8"}):
                self.assertEqual(i18n._from_os(), "de")
            with mock.patch.dict(os.environ, {"LC_ALL": "fr_FR.UTF-8", "LANG": "de_DE.UTF-8"}):
                self.assertEqual(i18n._from_os(), "fr")


if __name__ == "__main__":
    unittest.main()
