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


class DeleteDialogTest(unittest.TestCase):
    def setUp(self):
        i18n.set_language("en")
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / ".herdr-devrun.json"
        services = [{"name": "web", "command": "x"}, {"name": "api", "command": "y"}]
        self.path.write_text(json.dumps({"services": services}), encoding="utf-8")
        self.panel = panel.Panel(self.path, None)
        self.panel.reload_config()
        self.panel.statuses = {"web": Status.RUNNING, "api": Status.STOPPED}
        self.panel.selected = 1

    def names(self):
        return [each["name"] for each in json.loads(self.path.read_text(encoding="utf-8"))["services"]]

    def frame(self, width=100, height=24):
        output = []
        with mock.patch.object(term, "size", return_value=(width, height)), \
                mock.patch.object(term, "write", side_effect=output.append):
            self.panel.draw()
        return ANSI.sub("", output[0]).split("\r\n")

    def open_dialog_by_button(self):
        self.frame()
        y, x1, _, _, _ = next(each for each in self.panel.row_buttons if each[3] == "delete" and each[4] == 1)
        self.panel.dispatch(term.Event("mouse", mouse="down", x=x1, y=y))

    def dialog_button(self, command):
        self.frame()
        y, x1, x2, _ = next(each for each in self.panel.dialog_buttons if each[3] == command)
        return term.Event("mouse", mouse="down", x=(x1 + x2) // 2, y=y)

    def test_delete_button_opens_dialog_without_removing(self):
        self.open_dialog_by_button()
        self.assertIsNotNone(self.panel.dialog)
        self.assertEqual(self.panel.dialog["service"]["name"], "api")
        self.assertEqual(self.names(), ["web", "api"])

    def test_dialog_shows_question_and_both_buttons(self):
        self.open_dialog_by_button()
        text = "\n".join(self.frame())
        self.assertIn(i18n.t("panel.dialog.delete_title", name="api"), text)
        self.assertIn(i18n.t("panel.dialog.delete_body"), text)
        self.assertEqual([each[3] for each in self.panel.dialog_buttons], ["dialog_confirm", "dialog_cancel"])

    def test_y_key_deletes_after_dialog(self):
        self.open_dialog_by_button()
        self.panel.dispatch(term.Event("key", key="y"))
        self.assertIsNone(self.panel.dialog)
        self.assertEqual(self.names(), ["web"])
        self.assertEqual(self.panel.message, i18n.t("panel.form.deleted", name="api"))

    def test_uppercase_y_and_hangul_key_also_delete(self):
        for key in ("Y", "ㅛ"):
            with self.subTest(key=key):
                self.path.write_text(json.dumps({"services": [{"name": "web", "command": "x"},
                                                              {"name": "api", "command": "y"}]}), encoding="utf-8")
                self.panel.config_mtime = None
                self.panel.reload_config()
                self.panel.selected = 1
                self.open_dialog_by_button()
                self.panel.dispatch(term.Event("key", key=key))
                self.assertEqual(self.names(), ["web"])

    def test_delete_button_in_dialog_deletes(self):
        self.open_dialog_by_button()
        self.panel.dispatch(self.dialog_button("dialog_confirm"))
        self.assertEqual(self.names(), ["web"])
        self.assertIsNone(self.panel.dialog)

    def test_n_esc_and_ctrl_c_cancel_without_deleting(self):
        for key in ("n", "esc", "ctrl+c"):
            with self.subTest(key=key):
                self.open_dialog_by_button()
                self.panel.dispatch(term.Event("key", key=key))
                self.assertIsNone(self.panel.dialog)
                self.assertEqual(self.names(), ["web", "api"])
                self.assertEqual(self.panel.message, i18n.t("panel.form.cancelled"))

    def test_cancel_button_in_dialog_does_not_delete(self):
        self.open_dialog_by_button()
        self.panel.dispatch(self.dialog_button("dialog_cancel"))
        self.assertIsNone(self.panel.dialog)
        self.assertEqual(self.names(), ["web", "api"])

    def test_click_outside_dialog_closes_it_without_deleting(self):
        self.open_dialog_by_button()
        self.panel.dispatch(term.Event("mouse", mouse="down", x=0, y=0))
        self.assertIsNone(self.panel.dialog)
        self.assertEqual(self.names(), ["web", "api"])

    def test_click_inside_dialog_text_keeps_it_open(self):
        self.open_dialog_by_button()
        self.frame()
        top, left, width = self.panel.dialog_box
        self.panel.dispatch(term.Event("mouse", mouse="down", x=left + 2, y=top + 1))
        self.assertIsNotNone(self.panel.dialog)
        self.assertEqual(self.names(), ["web", "api"])

    def test_other_keys_and_wheel_are_ignored_while_dialog_is_open(self):
        self.open_dialog_by_button()
        self.panel.dispatch(term.Event("key", key="x"))
        self.panel.dispatch(term.Event("key", key="enter"))
        self.panel.dispatch(term.Event("mouse", mouse="wheeldown", x=5, y=5))
        self.assertIsNotNone(self.panel.dialog)
        self.assertEqual(self.names(), ["web", "api"])

    def test_running_service_is_blocked_with_bottom_message_not_dialog(self):
        self.panel.statuses["api"] = Status.RUNNING
        self.frame()
        y, x1, _, _, _ = next(each for each in self.panel.row_buttons if each[3] == "delete" and each[4] == 1)
        self.panel.dispatch(term.Event("mouse", mouse="down", x=x1, y=y))
        self.assertIsNone(self.panel.dialog)
        self.assertEqual(self.panel.message, i18n.t("panel.form.running_block", name="api"))
        self.assertEqual(self.names(), ["web", "api"])
        lines = self.frame()
        self.assertIn(self.panel.message, lines[-1])
        self.assertNotIn(i18n.t("panel.dialog.delete_title", name="api"), "\n".join(lines))

    def test_service_started_after_dialog_opened_is_not_deleted(self):
        self.open_dialog_by_button()
        self.panel.statuses["api"] = Status.RUNNING
        self.panel.dispatch(term.Event("key", key="y"))
        self.assertEqual(self.names(), ["web", "api"])
        self.assertEqual(self.panel.message, i18n.t("panel.form.running_block", name="api"))

    def test_dialog_fits_wide_and_narrow_screens(self):
        for width in (100, 50, 30):
            with self.subTest(width=width):
                self.open_dialog_by_button()
                lines = self.frame(width=width)
                for line in lines[:24]:
                    self.assertLessEqual(panel.text_width(line), width)
                top, left, box_width = self.panel.dialog_box
                self.assertEqual(lines[top][left], "┌")
                self.assertEqual(lines[top + panel.DIALOG_BOX_HEIGHT - 1][left], "└")
                self.panel.dialog = None


if __name__ == "__main__":
    unittest.main()
