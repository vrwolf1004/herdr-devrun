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


class FormClickTest(unittest.TestCase):
    """입력 폼이 열린 동안의 클릭: 폼을 취소하고 그 클릭을 평소처럼 처리한다."""

    def setUp(self):
        i18n.set_language("en")
        self.folder = tempfile.TemporaryDirectory()
        config_path = Path(self.folder.name) / ".herdr-devrun.json"
        services = [{"name": "web", "command": "x", "port": 8000}, {"name": "api", "command": "y", "port": 8001}]
        config_path.write_text(json.dumps({"services": services}), encoding="utf-8")
        self.panel = panel.Panel(config_path, None)
        self.panel.reload_config()
        self.panel.statuses = {"web": Status.RUNNING, "api": Status.STOPPED}
        # 명령이 실제로 실행되지 않게 가로채서 어떤 명령이 나왔는지만 본다.
        patch = mock.patch.object(panel.Panel, "execute")
        self.execute = patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self.folder.cleanup)

    def render(self, width=100):
        output = []
        with mock.patch.object(term, "size", return_value=(width, 30)), \
                mock.patch.object(term, "write", side_effect=output.append):
            self.panel.draw()
        return ANSI.sub("", output[0]).split("\r\n")

    def click(self, command, index=None):
        """그려진 버튼을 찾아 그 가운데를 누른다 (줄 버튼은 index 줄, 하단 버튼은 y 기준)."""
        if index is None:
            y, x1, x2, _ = next(each for each in self.panel.buttons if each[3] == command)
        else:
            y, x1, x2, _, _ = next(each for each in self.panel.row_buttons
                                   if each[3] == command and each[4] == index)
        return term.Event("mouse", mouse="down", x=(x1 + x2) // 2, y=y)

    def open_form(self, mode, index=0):
        self.panel.start_form(mode, self.panel.services[index])

    def test_edit_form_closes_on_bottom_button_and_runs_it(self):
        self.render()
        self.open_form("edit")
        self.panel.dispatch(self.click("start_all"))
        self.assertIsNone(self.panel.form)
        self.execute.assert_called_once_with("start_all")
        self.assertEqual(self.panel.message, panel.t("panel.form.cancelled"))

    def test_add_form_closes_on_browser_and_runs_it(self):
        self.render()
        self.open_form("add")
        self.panel.dispatch(self.click("browser"))
        self.assertIsNone(self.panel.form)
        self.execute.assert_called_once_with("browser")

    def test_add_form_closes_on_row_toggle_and_selects_that_service(self):
        self.render()
        self.open_form("add")
        self.panel.dispatch(self.click("toggle", index=1))
        self.assertIsNone(self.panel.form)
        self.assertEqual(self.panel.selected, 1)
        self.execute.assert_called_once_with("toggle")

    def test_edit_form_closes_on_row_delete_and_runs_it(self):
        self.render()
        self.open_form("edit")
        self.panel.dispatch(self.click("delete", index=0))
        self.assertIsNone(self.panel.form)
        self.execute.assert_called_once_with("delete")

    def test_add_form_closes_on_row_edit_and_runs_it(self):
        self.render()
        self.open_form("add")
        self.panel.dispatch(self.click("edit", index=1))
        self.assertIsNone(self.panel.form)
        self.assertEqual(self.panel.selected, 1)
        self.execute.assert_called_once_with("edit")

    def test_add_form_closes_on_quit_button(self):
        self.render()
        self.open_form("add")
        self.panel.dispatch(self.click("quit"))
        self.assertIsNone(self.panel.form)
        self.execute.assert_called_once_with("quit")

    def test_click_on_blank_area_only_cancels_the_form(self):
        self.render()
        self.open_form("edit")
        self.panel.dispatch(term.Event("mouse", mouse="down", x=99, y=29))
        self.assertIsNone(self.panel.form)
        self.execute.assert_not_called()

    def test_wheel_is_ignored_while_form_is_open(self):
        self.render()
        self.open_form("edit")
        self.panel.dispatch(term.Event("mouse", mouse="wheeldown", x=5, y=5))
        self.assertIsNotNone(self.panel.form)
        self.execute.assert_not_called()

    def test_keys_inside_form_still_go_to_the_form(self):
        self.open_form("edit")
        before = self.panel.form["text"]
        self.panel.dispatch(term.Event("key", key="x"))
        self.assertEqual(self.panel.form["text"], before + "x")
        self.execute.assert_not_called()

    def test_escape_still_cancels_form_from_keyboard(self):
        self.open_form("edit")
        self.panel.dispatch(term.Event("key", key="esc"))
        self.assertIsNone(self.panel.form)
        self.execute.assert_not_called()

    def test_without_form_click_runs_the_button_directly(self):
        self.render()
        self.panel.dispatch(self.click("start_all"))
        self.execute.assert_called_once_with("start_all")


if __name__ == "__main__":
    unittest.main()
