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


class WidthTest(unittest.TestCase):
    def test_text_width(self):
        self.assertEqual(panel.text_width("abc"), 3)
        self.assertEqual(panel.text_width("한글"), 4)
        self.assertEqual(panel.text_width("日本"), 4)

    def test_fit_pads_and_truncates(self):
        self.assertEqual(panel.fit("ab", 4), "ab  ")
        self.assertEqual(panel.fit("abcdef", 4), "abc…")
        self.assertEqual(panel.text_width(panel.fit("가나다라", 5)), 5)
        self.assertEqual(panel.fit("x", 0), "")


class DashboardTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        config_path = Path(self.folder.name) / ".herdr-devrun.json"
        services = [{"name": f"서비스{i:02d}", "command": "x", "port": 8000 + i} for i in range(20)]
        config_path.write_text(json.dumps({"tab": "demo", "services": services}, ensure_ascii=False), encoding="utf-8")
        self.panel = panel.Panel(config_path, None)
        self.panel.reload_config()
        self.panel.statuses = {each["name"]: Status.RUNNING for each in self.panel.services}

    def tearDown(self):
        self.folder.cleanup()
        i18n.set_language("en")

    def render(self, width, height):
        output = []
        with mock.patch.object(term, "size", return_value=(width, height)), \
                mock.patch.object(term, "write", side_effect=output.append):
            self.panel.draw()
        return ANSI.sub("", output[0]).split("\r\n")

    def test_selected_row_stays_visible_when_scrolling(self):
        for selected in (0, 10, 19):
            self.panel.selected = selected
            self.render(60, 18)
            self.assertIn(selected, self.panel.rows.values())
            self.assertLess(len(self.panel.rows), 20)

    def test_row_coordinates_match_drawn_lines(self):
        self.panel.selected = 19
        lines = self.render(60, 18)
        y = next(y for y, index in self.panel.rows.items() if index == 19)
        self.assertIn("서비스19", lines[y])

    def test_no_line_exceeds_width(self):
        for language in ("en", "ko", "ru", "fr", "es", "de", "ja"):
            i18n.set_language(language)
            for width in (10, 12, 20, 29, 30, 39, 40, 60, 100):
                with self.subTest(language=language, width=width):
                    widest = max(panel.text_width(line) for line in self.render(width, 18))
                    self.assertLessEqual(widest, width)

    def test_buttons_are_clickable_where_drawn(self):
        lines = self.render(80, 30)
        for y, x1, x2, command in self.panel.buttons:
            label = i18n.t("panel.button." + command)
            self.assertIn(label.split()[-1], lines[y][x1:x2 + 1 + 4])

    def test_hangul_keys(self):
        for key, command in (("ㄱ", "restart"), ("ㅁ", "start_all"), ("ㅌ", "stop_all"),
                             ("ㅐ", "browser"), ("ㄷ", "config"), ("ㅂ", "quit"), ("R", "restart")):
            self.assertEqual(self.panel.command_for(term.Event("key", key=key)), command)
        self.assertIsNone(self.panel.command_for(term.Event("key", key="ㅋ")))

    def test_every_status_has_a_view(self):
        self.assertEqual(set(panel.STATUS_VIEW), set(Status))


if __name__ == "__main__":
    unittest.main()
