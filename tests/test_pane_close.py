import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  (src 경로 준비)
import core
import i18n
import panel
import term
from core import Status

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def make_state(*panes, control_box="cb"):
    state = {"tab_id": "t1", "panes": [dict(each) for each in panes], "workspace_id": "w1", "label": "app"}
    if control_box:
        state["control_box"] = control_box
    return state


class CoreStopCloseTest(unittest.TestCase):
    """중지는 프로세스만 끄고 pane 을 남긴다. 닫기는 pane 을 닫고 상태에서 뺀다."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.project = Path(self.folder.name)
        self.herdr = mock.Mock(return_value={})
        self.state = make_state({"name": "web", "pane_id": "p1"})
        self.alive = False  # 셸 아래 프로세스가 남아 있는지
        patches = [
            mock.patch.object(core, "live_state", side_effect=lambda *_: self.state),
            mock.patch.object(core, "live_pane_ids", return_value={"p1", "p2", "cb"}),
            mock.patch.object(core, "interrupt_and_wait"),
            mock.patch.object(core, "shell_pid", return_value=10),
            mock.patch.object(core.procs, "child_process_map", return_value={}),
            mock.patch.object(core.procs, "has_running_children", side_effect=lambda *_: self.alive),
            mock.patch.object(core, "herdr", self.herdr),
            mock.patch.object(core, "write_state"),
            mock.patch.object(core, "remove_state"),
            mock.patch.object(core, "run_in_pane"),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def calls(self, *prefix):
        return [call.args for call in self.herdr.call_args_list if call.args[:len(prefix)] == prefix]

    def test_stop_keeps_the_pane_at_the_prompt(self):
        self.assertTrue(core.stop_service(self.project, "web"))
        self.assertEqual(self.calls("pane", "close"), [])
        self.assertTrue(self.state["panes"][0]["stopped"])
        core.write_state.assert_called()

    def test_stop_closes_pane_when_the_process_is_still_alive(self):
        self.alive = True
        core.stop_service(self.project, "web")
        self.assertTrue(any(call[:2] == ("pane", "close") for call in self.calls("pane")))
        self.assertEqual(self.state["panes"], [])

    def test_stopped_pane_shows_as_stopped_not_exited(self):
        pane = {"name": "web", "pane_id": "p1", "stopped": True}
        self.assertEqual(core.service_status({"name": "web"}, {"panes": [pane]}, {}, {"p1": 10}), Status.STOPPED)
        plain = {"name": "web", "pane_id": "p1"}
        self.assertEqual(core.service_status({"name": "web"}, {"panes": [plain]}, {}, {"p1": 10}), Status.EXITED)

    def test_start_reuses_a_stopped_pane(self):
        self.state["panes"][0]["stopped"] = True
        started = core.start_service(self.project, {}, {"name": "web", "command": "run"})
        self.assertTrue(started)
        core.run_in_pane.assert_called_once_with("p1", {"name": "web", "command": "run"})
        self.assertNotIn("stopped", self.state["panes"][0])
        self.assertEqual(self.calls("pane", "split"), [])
        self.assertEqual(self.calls("tab", "create"), [])

    def test_start_does_nothing_for_a_running_pane(self):
        self.alive = True  # 프로세스가 살아 있는 pane
        self.assertFalse(core.start_service(self.project, {}, {"name": "web", "command": "run"}))
        core.run_in_pane.assert_not_called()

    def test_close_removes_the_pane_and_keeps_control_box_tab(self):
        self.assertTrue(core.close_service_pane(self.project, "web"))
        self.assertIn(("pane", "close", "p1"), self.calls("pane", "close"))
        self.assertEqual(self.state["panes"], [])
        self.assertEqual(self.calls("tab", "close"), [])
        core.remove_state.assert_not_called()

    def test_close_stops_a_live_process_first(self):
        self.alive = True
        core.close_service_pane(self.project, "web")
        core.interrupt_and_wait.assert_called_once()

    def test_close_last_pane_without_control_box_closes_tab(self):
        self.state = make_state({"name": "web", "pane_id": "p1"}, control_box=None)
        core.close_service_pane(self.project, "web")
        self.assertIn(("tab", "close", "t1"), self.calls("tab", "close"))
        core.remove_state.assert_called_once()

    def test_close_without_pane_returns_false(self):
        self.assertFalse(core.close_service_pane(self.project, "nope"))
        self.assertEqual(self.calls("pane", "close"), [])


class PaneCloseDialogTest(unittest.TestCase):
    def setUp(self):
        i18n.set_language("en")
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / ".herdr-devrun.json"
        services = [{"name": "web", "command": "x", "port": 8000}, {"name": "api", "command": "y", "port": 8001}]
        self.path.write_text(json.dumps({"services": services}), encoding="utf-8")
        self.panel = panel.Panel(self.path, None)
        self.panel.reload_config()
        self.panel.statuses = {"web": Status.STOPPED, "api": Status.STOPPED}
        patch = mock.patch.object(core, "close_service_pane", return_value=True)
        self.close = patch.start()
        self.addCleanup(patch.stop)
        refresh = mock.patch.object(panel.Panel, "refresh")
        refresh.start()
        self.addCleanup(refresh.stop)

    def frame(self, width=100, height=24):
        output = []
        with mock.patch.object(term, "size", return_value=(width, height)), \
                mock.patch.object(term, "write", side_effect=output.append):
            self.panel.draw()
        return ANSI.sub("", output[0]).split("\r\n")

    def close_button(self, index=1):
        self.frame()
        y, x1, x2, _, _ = next(each for each in self.panel.row_buttons if each[3] == "close_pane" and each[4] == index)
        return term.Event("mouse", mouse="down", x=(x1 + x2) // 2, y=y)

    def dialog_button(self, command):
        self.frame()
        y, x1, x2, _ = next(each for each in self.panel.dialog_buttons if each[3] == command)
        return term.Event("mouse", mouse="down", x=(x1 + x2) // 2, y=y)

    def open_close_dialog(self):
        self.panel.dispatch(self.close_button())

    def test_close_button_opens_confirmation_without_closing(self):
        self.open_close_dialog()
        self.assertEqual(self.panel.dialog["kind"], "close")
        self.assertEqual(self.panel.dialog["service"]["name"], "api")
        self.close.assert_not_called()
        text = "\n".join(self.frame())
        self.assertIn(i18n.t("panel.dialog.close_title", name="api"), text)

    def test_y_closes_the_pane(self):
        self.open_close_dialog()
        self.panel.dispatch(term.Event("key", key="y"))
        self.close.assert_called_once_with(self.panel.project_dir, "api", core.stop_timeout(self.panel.services[1]))
        self.assertIsNone(self.panel.dialog)

    def test_close_button_in_dialog_closes_the_pane(self):
        self.open_close_dialog()
        self.panel.dispatch(self.dialog_button("dialog_confirm"))
        self.close.assert_called_once()

    def test_n_esc_outside_and_cancel_do_not_close(self):
        for event in (term.Event("key", key="n"), term.Event("key", key="esc")):
            with self.subTest(event=event.key):
                self.open_close_dialog()
                self.panel.dispatch(event)
                self.assertIsNone(self.panel.dialog)
        self.open_close_dialog()
        self.panel.dispatch(self.dialog_button("dialog_cancel"))
        self.open_close_dialog()
        self.panel.dispatch(term.Event("mouse", mouse="down", x=0, y=0))
        self.close.assert_not_called()

    def test_dialog_text_fits_wide_and_narrow_screens(self):
        for width in (100, 50):
            with self.subTest(width=width):
                self.open_close_dialog()
                lines = self.frame(width=width)
                for line in lines[:24]:
                    self.assertLessEqual(panel.text_width(line), width)
                top, left, _ = self.panel.dialog_box
                self.assertEqual(lines[top][left], "┌")
                self.panel.dialog = None


class StopAllTest(unittest.TestCase):
    """대시보드 전체 중지는 pane 을 남기고, devrun down 은 기존대로 탭을 닫는다."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.project = Path(self.folder.name)
        self.herdr = mock.Mock(return_value={})
        self.state = make_state({"name": "web", "pane_id": "p1"}, {"name": "api", "pane_id": "p2"})
        self.alive = set()  # 프로세스가 아직 남아 있는 pane id
        self.config = {"services": [{"name": "web", "command": "x"}, {"name": "api", "command": "y"}]}
        patches = [
            mock.patch.object(core, "live_state", side_effect=lambda *_: self.state),
            mock.patch.object(core, "live_pane_ids", return_value={"p1", "p2", "cb"}),
            mock.patch.object(core, "interrupt_and_wait"),
            mock.patch.object(core, "shell_pid", side_effect=lambda pane_id: 10),
            mock.patch.object(core.procs, "child_process_map", return_value={}),
            mock.patch.object(core.procs, "has_running_children",
                              side_effect=lambda child_map, pid: pid in self.alive),
            mock.patch.object(core, "herdr", self.herdr),
            mock.patch.object(core, "write_state"),
            mock.patch.object(core, "remove_state"),
            mock.patch.object(core, "notify"),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def calls(self, *prefix):
        return [call.args for call in self.herdr.call_args_list if call.args[:len(prefix)] == prefix]

    def test_stop_all_keeps_every_pane_marked_stopped(self):
        self.alive = {10}  # 두 pane 모두 실행 중이었고, Ctrl+C 로 프로세스가 끝난다
        core.interrupt_and_wait.side_effect = lambda panes: self.alive.clear()
        self.assertEqual(core.stop_all_services(self.project, self.config), 2)
        self.assertEqual(self.calls("pane", "close"), [])
        self.assertEqual(self.calls("tab", "close"), [])
        self.assertTrue(all(pane.get("stopped") for pane in self.state["panes"]))
        self.assertEqual(self.state["panes"][0]["pane_id"], "p1")
        core.remove_state.assert_not_called()
        core.write_state.assert_called_once()
        self.assertEqual([pane_id for pane_id, _ in core.interrupt_and_wait.call_args.args[0]], ["p1", "p2"])

    def test_only_panes_that_do_not_end_in_time_are_closed(self):
        core.shell_pid.side_effect = lambda pane_id: 10 if pane_id == "p1" else 20
        self.alive = {10}  # p1 의 프로세스는 Ctrl+C 뒤에도 남는다. p2 는 이미 멈춰 있었다
        self.assertEqual(core.stop_all_services(self.project, self.config), 1)
        self.assertEqual(self.calls("pane", "close"), [("pane", "close", "p1")])
        self.assertEqual([pane["pane_id"] for pane in self.state["panes"]], ["p2"])
        self.assertTrue(self.state["panes"][0]["stopped"])
        self.assertEqual(self.calls("tab", "close"), [])  # 컨트롤 박스가 있으니 탭은 남긴다

    def test_panes_that_were_already_dead_are_marked_but_not_counted(self):
        core.shell_pid.side_effect = lambda pane_id: 10 if pane_id == "p1" else 20
        self.alive = {10}
        core.interrupt_and_wait.side_effect = lambda panes: self.alive.clear()
        self.assertEqual(core.stop_all_services(self.project, self.config), 1)
        self.assertEqual(self.calls("pane", "close"), [])
        self.assertTrue(all(pane.get("stopped") for pane in self.state["panes"]))

    def test_stop_all_with_control_box_never_closes_the_tab(self):
        self.alive = {10}
        core.stop_all_services(self.project, self.config)
        self.assertEqual(self.calls("tab", "close"), [])
        core.remove_state.assert_not_called()

    def test_stop_all_without_running_services_does_nothing(self):
        self.state = make_state({"name": "web", "pane_id": "p1", "stopped": True})
        self.assertEqual(core.stop_all_services(self.project, self.config), 0)
        self.assertEqual(self.calls("pane", "close"), [])
        core.interrupt_and_wait.assert_not_called()

    def test_stop_all_without_state_does_nothing(self):
        self.state = None
        self.assertEqual(core.stop_all_services(self.project, self.config), 0)
        self.assertEqual(self.herdr.call_args_list, [])

    def test_devrun_down_still_closes_the_tab(self):
        core.down(self.project, quiet=True, config=self.config)
        self.assertIn(("tab", "close", "t1"), self.calls("tab", "close"))
        core.remove_state.assert_called_once()


if __name__ == "__main__":
    unittest.main()
