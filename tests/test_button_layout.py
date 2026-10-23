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

# 하단 버튼 줄 (위에서 아래, 왼쪽에서 오른쪽). 서비스 제어는 각 서비스 줄에 있다.
BOTTOM = ["start_all", "stop_all", "browser", "config", "add", "quit"]


class ButtonLayoutTest(unittest.TestCase):
    def setUp(self):
        i18n.set_language("en")
        self.folder = tempfile.TemporaryDirectory()
        config_path = Path(self.folder.name) / ".herdr-devrun.json"
        services = [{"name": "web", "command": "x", "port": 8000}, {"name": "api", "command": "y", "port": 8001}]
        config_path.write_text(json.dumps({"services": services}), encoding="utf-8")
        self.panel = panel.Panel(config_path, None)
        self.panel.reload_config()
        self.panel.statuses = {"web": Status.RUNNING, "api": Status.STOPPED}

    def tearDown(self):
        self.folder.cleanup()

    def render(self, width, height=30):
        output = []
        with mock.patch.object(term, "size", return_value=(width, height)), \
                mock.patch.object(term, "write", side_effect=output.append):
            self.panel.draw()
        return ANSI.sub("", output[0]).split("\r\n")

    def bottom_commands(self, width):
        return [command for _, spans in self.panel.layout_buttons(width) for _, _, command in spans]

    def test_bottom_bar_has_only_global_commands_in_order(self):
        self.assertEqual(self.bottom_commands(100), BOTTOM)
        self.assertEqual(self.bottom_commands(40), BOTTOM)

    def test_bottom_bar_wraps_by_width_only(self):
        rows = self.panel.layout_buttons(30)
        self.assertGreater(len(rows), 1)
        self.assertEqual([command for _, spans in rows for _, _, command in spans], BOTTOM)

    def test_restart_is_not_a_button_but_still_a_key(self):
        self.assertNotIn("restart", self.bottom_commands(100))
        self.assertEqual(self.panel.command_for(term.Event("key", key="r")), "restart")

    def test_each_service_row_has_toggle_edit_delete_at_wide_width(self):
        self.render(100)
        for index in (0, 1):
            commands = [command for _, _, _, command, row_index in self.panel.row_buttons if row_index == index]
            self.assertEqual(commands, ["toggle", "edit", "delete", "close_pane"])

    def test_row_buttons_sit_at_the_end_of_their_service_line(self):
        lines = self.render(100)
        for y, x1, x2, command, index in self.panel.row_buttons:
            with self.subTest(command=command, index=index):
                self.assertIn(self.panel.services[index]["name"], lines[y])
                self.assertTrue(lines[y][x1:x2 + 1].strip())
                self.assertGreater(x1, lines[y].index(self.panel.services[index]["name"]))

    def test_wide_labels_are_drawn_in_the_row(self):
        lines = self.render(100)
        web_row = next(y for y, index in self.panel.rows.items() if index == 0)
        self.assertIn(i18n.t("panel.button.stop"), lines[web_row])
        self.assertIn(i18n.t("panel.button.edit"), lines[web_row])
        self.assertIn(i18n.t("panel.button.delete"), lines[web_row])

    def test_narrow_width_uses_icons_in_the_row(self):
        lines = self.render(40)
        web_row = next(y for y, index in self.panel.rows.items() if index == 0)
        self.assertIn("■", lines[web_row])
        self.assertIn("✎", lines[web_row])
        self.assertIn("✕", lines[web_row])

    def test_toggle_label_follows_status(self):
        lines = self.render(100)
        api_row = next(y for y, index in self.panel.rows.items() if index == 1)
        self.assertIn(i18n.t("panel.button.start"), lines[api_row])

    def test_row_button_click_selects_that_service_and_returns_its_command(self):
        self.render(100)
        for y, x1, x2, command, index in self.panel.row_buttons:
            with self.subTest(command=command, index=index):
                self.panel.selected = 0 if index else 1  # 다른 서비스를 먼저 골라 둔다
                event = term.Event("mouse", mouse="down", x=x1, y=y)
                self.assertEqual(self.panel.command_for(event), command)
                self.assertEqual(self.panel.selected, index)

    def test_edit_and_delete_clicks_return_their_commands(self):
        for width in (100, 40):
            with self.subTest(width=width):
                self.render(width)
                for command in ("edit", "delete"):
                    y, x1, x2, _, index = next(each for each in self.panel.row_buttons if each[3] == command)
                    event = term.Event("mouse", mouse="down", x=x2, y=y)
                    self.assertEqual(self.panel.command_for(event), command)
                    self.assertEqual(self.panel.selected, index)

    def test_click_on_service_name_selects_without_command(self):
        self.render(100)
        y = next(y for y, index in self.panel.rows.items() if index == 1)
        self.assertIsNone(self.panel.command_for(term.Event("mouse", mouse="down", x=6, y=y)))
        self.assertEqual(self.panel.selected, 1)

    def test_bottom_buttons_still_clickable_where_drawn(self):
        lines = self.render(100)
        for y, x1, x2, command in self.panel.buttons:
            self.assertEqual(lines[y][x1:x2 + 1].strip(), i18n.t("panel.button." + command), command)

    def test_very_narrow_width_drops_row_buttons_without_overflow(self):
        lines = self.render(12)
        self.assertEqual(self.panel.row_buttons, [])
        self.assertTrue(all(panel.text_width(line) <= 12 for line in lines[:10]))


if __name__ == "__main__":
    unittest.main()
