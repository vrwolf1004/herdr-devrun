import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  (src 경로 준비)
import i18n
import panel


class OpenConfigTest(unittest.TestCase):
    def setUp(self):
        i18n.set_language("en")
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / ".herdr-devrun.json"
        self.path.write_text(json.dumps({"services": [{"name": "web", "command": "x"}]}), encoding="utf-8")
        self.panel = panel.Panel(self.path, None)
        self.panel.reload_config()

    def test_windows_opens_notepad_and_never_uses_startfile(self):
        with mock.patch.object(panel.core, "IS_WINDOWS", True), \
                mock.patch.object(panel.subprocess, "Popen") as popen, \
                mock.patch("os.startfile", create=True) as startfile:
            self.panel.open_config()
        popen.assert_called_once()
        self.assertEqual(popen.call_args.args[0], ["notepad.exe", str(self.path)])
        startfile.assert_not_called()
        self.assertEqual(self.panel.message, i18n.t("panel.opened_config"))

    def test_windows_uses_notepad_even_when_startfile_would_work(self):
        with mock.patch.object(panel.core, "IS_WINDOWS", True), \
                mock.patch.object(panel.subprocess, "Popen") as popen, \
                mock.patch("os.startfile", create=True) as startfile:
            startfile.return_value = None
            self.panel.open_config()
        startfile.assert_not_called()
        self.assertEqual(popen.call_args.args[0][0], "notepad.exe")

    def test_other_systems_keep_the_system_opener(self):
        with mock.patch.object(panel.core, "IS_WINDOWS", False), \
                mock.patch.object(panel.sys, "platform", "linux"), \
                mock.patch.object(panel.subprocess, "Popen") as popen:
            self.panel.open_config()
        self.assertEqual(popen.call_args.args[0], ["xdg-open", str(self.path)])

    def test_macos_uses_open(self):
        with mock.patch.object(panel.core, "IS_WINDOWS", False), \
                mock.patch.object(panel.sys, "platform", "darwin"), \
                mock.patch.object(panel.subprocess, "Popen") as popen:
            self.panel.open_config()
        self.assertEqual(popen.call_args.args[0], ["open", str(self.path)])


if __name__ == "__main__":
    unittest.main()
