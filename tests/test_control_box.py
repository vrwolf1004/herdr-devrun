import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  (src 경로 준비)
import core
import devrun


class FakeHerdr:
    """herdr 호출을 기록하고 응답을 흉내 낸다."""

    def __init__(self, workspace_tabs=(), spaces=()):
        self.calls = []
        self.workspace_tabs = workspace_tabs  # tab list --workspace 가 돌려줄 탭 (None 이면 실패)
        self.spaces = list(spaces)            # workspace list 가 돌려줄 space

    def __call__(self, *args, check=True):
        self.calls.append(args)
        if args[:2] == ("workspace", "create"):
            return {"workspace": {"workspace_id": "w9"}, "tab": {"tab_id": "t9"}, "root_pane": {"pane_id": "cb"}}
        if args[:2] == ("workspace", "list"):
            return {"workspaces": self.spaces}
        if args[:2] == ("tab", "create"):
            return {"tab": {"tab_id": "t7"}, "root_pane": {"pane_id": "cb7"}}
        if args[:2] == ("pane", "split"):
            return {"pane": {"pane_id": "new"}}
        if args[:2] == ("tab", "list"):
            return None if self.workspace_tabs is None else {"tabs": self.workspace_tabs}
        return {}

    def has(self, *args):
        return args in self.calls


class ControlBoxTest(unittest.TestCase):
    def spaces(self):
        return []

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name)
        self.marker = self.project / "panel.marker"
        self.herdr = FakeHerdr(spaces=self.spaces())
        patches = [
            mock.patch.object(core, "panel_marker_path", return_value=self.marker),
            mock.patch.object(core, "live_pane_ids", return_value=set()),
            mock.patch.object(core, "live_state", return_value=None),
            mock.patch.object(core, "herdr", side_effect=self.herdr),
            mock.patch.object(core, "write_state"),
            mock.patch.object(core, "remove_state"),
            mock.patch.object(core, "run_in_pane"),
            mock.patch.dict(os.environ, {"HERDR_PANE_ID": "cur"}),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_open_control_box_creates_workspace_and_state(self):
        devrun.open_control_box(self.project, {"tab": "app", "services": []})
        self.assertTrue(self.herdr.has("workspace", "create", "--cwd", str(self.project), "--label", "devrun",
                                       "--focus"))
        self.assertTrue(self.herdr.has("tab", "rename", "t9", "app"))
        self.assertTrue(self.herdr.has("pane", "rename", "cb", devrun.CONTROL_BOX_NAME))
        self.assertEqual(self.marker.read_text(encoding="utf-8"), "cb")
        state = core.write_state.call_args[0][1]
        self.assertEqual(state["workspace_id"], "w9")
        self.assertEqual(state["tab_id"], "t9")
        self.assertEqual(state["control_box"], "cb")
        self.assertEqual(state["panes"], [])

    def test_failed_run_closes_workspace_and_writes_no_state(self):
        with mock.patch.object(core, "herdr", side_effect=self._fail_on_run):
            with self.assertRaises(core.DevrunError):
                devrun.open_control_box(self.project, {"services": []})
        self.assertTrue(self.herdr.has("workspace", "close", "w9"))
        core.write_state.assert_not_called()
        self.assertFalse(self.marker.exists())

    def _fail_on_run(self, *args, check=True):
        if args[:2] == ("pane", "run"):
            raise core.DevrunError("run failed")
        return self.herdr(*args, check=check)

    def test_open_control_box_reuses_panel_when_tab_exists(self):
        with mock.patch.object(core, "live_state", return_value={"tab_id": "t1", "panes": []}), \
                mock.patch.object(devrun, "open_panel") as open_panel:
            devrun.open_control_box(self.project, {"services": []})
        open_panel.assert_called_once_with(self.project)
        self.assertFalse(self.herdr.has("workspace", "create", "--cwd", str(self.project), "--label", "devrun",
                                        "--focus"))


class ReuseSpaceTest(unittest.TestCase):
    """label 이 devrun 인 space 가 이미 있을 때: 그 안에 탭만 더한다."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name)
        self.herdr = FakeHerdr(spaces=[{"workspace_id": "w5", "label": "devrun"}])
        patches = [
            mock.patch.object(core, "panel_marker_path", return_value=self.project / "panel.marker"),
            mock.patch.object(core, "live_pane_ids", return_value=set()),
            mock.patch.object(core, "live_state", return_value=None),
            mock.patch.object(core, "herdr", side_effect=self.herdr),
            mock.patch.object(core, "write_state"),
            mock.patch.object(core, "remove_state"),
            mock.patch.dict(os.environ, {"HERDR_PANE_ID": "cur"}),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_adds_tab_to_existing_space(self):
        devrun.open_control_box(self.project, {"tab": "app", "services": []})
        self.assertTrue(self.herdr.has("tab", "create", "--workspace", "w5", "--cwd", str(self.project), "--focus"))
        self.assertFalse(any(call[:2] == ("workspace", "create") for call in self.herdr.calls))
        self.assertTrue(self.herdr.has("tab", "rename", "t7", "app"))
        self.assertTrue(self.herdr.has("pane", "rename", "cb7", devrun.CONTROL_BOX_NAME))
        state = core.write_state.call_args[0][1]
        self.assertEqual((state["workspace_id"], state["tab_id"], state["control_box"]), ("w5", "t7", "cb7"))

    def test_failed_run_closes_only_the_new_tab(self):
        def fail_on_run(*args, check=True):
            if args[:2] == ("pane", "run"):
                raise core.DevrunError("run failed")
            return self.herdr(*args, check=check)

        with mock.patch.object(core, "herdr", side_effect=fail_on_run):
            with self.assertRaises(core.DevrunError):
                devrun.open_control_box(self.project, {"services": []})
        self.assertTrue(self.herdr.has("tab", "close", "t7"))
        self.assertFalse(any(call[:2] == ("workspace", "close") for call in self.herdr.calls))
        core.write_state.assert_not_called()

    def test_unreadable_space_is_an_error_and_nothing_is_created(self):
        def fail_on_tab_list(*args, check=True):
            if args[:2] == ("tab", "list"):
                raise core.DevrunError("tab list failed")
            return self.herdr(*args, check=check)

        with mock.patch.object(core, "herdr", side_effect=fail_on_tab_list):
            with self.assertRaises(core.DevrunError):
                devrun.open_control_box(self.project, {"services": []})
        self.assertFalse(any(call[:2] in (("tab", "create"), ("workspace", "create")) for call in self.herdr.calls))

    def test_space_with_other_label_is_not_reused(self):
        self.herdr.spaces = [{"workspace_id": "w5", "label": "other"}]
        devrun.open_control_box(self.project, {"services": []})
        self.assertTrue(self.herdr.has("workspace", "create", "--cwd", str(self.project), "--label", "devrun",
                                       "--focus"))


class StartServiceTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name)
        self.herdr = FakeHerdr()
        self.state = {"tab_id": "t9", "panes": [], "control_box": "cb", "workspace_id": "w9"}
        patches = [
            mock.patch.object(core, "live_state", side_effect=lambda *_: self.state),
            mock.patch.object(core, "live_pane_ids", return_value=set()),
            mock.patch.object(core, "herdr", side_effect=self.herdr),
            mock.patch.object(core, "write_state"),
            mock.patch.object(core, "remove_state"),
            mock.patch.object(core, "run_in_pane"),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def service(self, name):
        return {"name": name, "command": "run"}

    def splits(self):
        return [call for call in self.herdr.calls if call[:2] == ("pane", "split")]

    def test_first_service_splits_right_of_control_box(self):
        core.start_service(self.project, {}, self.service("api"))
        self.assertEqual(self.splits()[0][2:4], ("cb", "--direction"))
        self.assertEqual(self.splits()[0][4], "right")
        self.assertFalse(self.herdr.has("tab", "close", "t9"))

    def test_second_then_third_service_follow_layout(self):
        core.start_service(self.project, {}, self.service("api"))
        self.state["panes"] = [{"name": "api", "pane_id": "new"}]
        core.start_service(self.project, {}, self.service("web"))
        self.state["panes"].append({"name": "web", "pane_id": "new"})
        core.start_service(self.project, {}, self.service("worker"))
        directions = [call[4] for call in self.splits()]
        anchors = [call[2] for call in self.splits()]
        self.assertEqual(directions, ["right", "right", "down"])
        self.assertEqual(anchors, ["cb", "new", "new"])
        self.assertFalse(any(call[:2] == ("tab", "close") for call in self.herdr.calls))


class DownWorkspaceTest(unittest.TestCase):
    def run_down(self, workspace_tabs, state=None):
        herdr = FakeHerdr(workspace_tabs=workspace_tabs)
        state = state or {"tab_id": "t9", "panes": [], "control_box": "cb", "workspace_id": "w9", "label": "app"}
        with mock.patch.object(core, "live_state", return_value=state), \
                mock.patch.object(core, "live_pane_ids", return_value=set()), \
                mock.patch.object(core, "herdr", side_effect=herdr), \
                mock.patch.object(core, "remove_state"), \
                mock.patch.object(core, "notify"):
            core.down(Path("unused"))
        return herdr

    def test_closes_workspace_when_no_tabs_remain(self):
        herdr = self.run_down(workspace_tabs=[])
        self.assertTrue(herdr.has("tab", "close", "t9"))
        self.assertTrue(herdr.has("workspace", "close", "w9"))

    def test_keeps_workspace_when_other_tabs_remain(self):
        herdr = self.run_down(workspace_tabs=[{"tab_id": "other"}])
        self.assertTrue(herdr.has("tab", "close", "t9"))
        self.assertFalse(herdr.has("workspace", "close", "w9"))

    def test_keeps_workspace_when_tab_list_fails(self):
        herdr = self.run_down(workspace_tabs=None)
        self.assertFalse(herdr.has("workspace", "close", "w9"))

    def test_state_without_workspace_does_not_close_any_workspace(self):
        herdr = self.run_down(workspace_tabs=[], state={"tab_id": "t9", "panes": [], "label": "app"})
        self.assertFalse(any(call[:2] == ("workspace", "close") for call in herdr.calls))


if __name__ == "__main__":
    unittest.main()
