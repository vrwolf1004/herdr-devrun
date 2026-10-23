import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  (src 경로 준비)
import i18n
import panel
import term
from core import Status

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


class HeaderLayoutTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        path = Path(self.folder.name) / ".herdr-devrun.json"
        path.write_text(json.dumps({"services": [{"name": "backend", "command": "x", "port": 8080}]}),
                        encoding="utf-8")
        self.panel = panel.Panel(path, None)
        self.panel.reload_config()
        self.panel.statuses = {"backend": Status.RUNNING}

    def tearDown(self):
        i18n.set_language("en")

    def header(self, width):
        output = []
        with mock.patch.object(term, "size", return_value=(width, 24)), \
                mock.patch.object(term, "write", side_effect=output.append):
            self.panel.draw()
        lines = ANSI.sub("", output[0]).split("\r\n")
        return lines[2]

    def test_service_header_never_touches_the_port_header(self):
        for language in i18n.SUPPORTED:
            i18n.set_language(language)
            service = i18n.t("panel.header.service")
            port = i18n.t("panel.header.port")
            for width in (40, 41, 50, 60):
                with self.subTest(language=language, width=width):
                    line = self.header(width)
                    at = line.index(service) + len(service)
                    self.assertTrue(line[at:at + 1] in (" ", ""), repr(line))
                    if port in line:
                        self.assertGreater(line.index(port), at, repr(line))

    def test_port_column_is_hidden_when_the_service_header_would_touch_it(self):
        i18n.set_language("en")
        self.assertNotIn("Port", self.header(40))
        self.assertIn("Port", self.header(50))

    def test_wide_layout_is_unchanged(self):
        for width in range(60, 121):
            with self.subTest(width=width):
                status, name, port = self.panel.column_widths(width)
                buttons = self.panel.line_buttons_width(width, status, port)
                self.assertEqual(port, max(8, panel.text_width(i18n.t("panel.header.port")) + 2))
                self.assertEqual(name, max(1, width - 3 - status - port - buttons))


if __name__ == "__main__":
    unittest.main()
