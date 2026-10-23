import unittest
from unittest import mock

import support  # noqa: F401  (src 경로 준비)
import core


class StartExitedPaneTest(unittest.TestCase):
    """프로세스가 없는 pane (EXITED 또는 중지) 은 같은 pane 에서 다시 시작하고, 살아 있는 pane 은 건드리지 않는다."""

    def setUp(self):
        self.state = {"tab_id": "t1", "control_box": "cb", "panes": [{"name": "backend", "pane_id": "p1"}]}
        self.children = {}  # 셸 pid → 자식 프로세스 목록
        self.herdr = mock.Mock(return_value={})
        patches = [
            mock.patch.object(core, "live_state", side_effect=lambda *_: self.state),
            mock.patch.object(core, "live_pane_ids", return_value={"p1", "cb"}),
            mock.patch.object(core, "shell_pid", return_value=10),
            mock.patch.object(core.procs, "child_process_map", side_effect=lambda: self.children),
            mock.patch.object(core.procs, "is_listening", return_value=False),
            mock.patch.object(core, "herdr", self.herdr),
            mock.patch.object(core, "write_state"),
            mock.patch.object(core, "remove_state"),
            mock.patch.object(core, "run_in_pane"),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.service = {"name": "backend", "command": "run-backend", "port": 8080}

    def calls(self, *prefix):
        return [call.args for call in self.herdr.call_args_list if call.args[:len(prefix)] == prefix]

    def test_exited_pane_restarts_in_the_same_pane(self):
        self.assertTrue(core.start_service(None, {}, self.service))
        core.run_in_pane.assert_called_once_with("p1", self.service)
        self.assertEqual(self.calls("pane", "split"), [])
        self.assertEqual(self.calls("tab", "create"), [])

    def test_live_pane_is_left_alone(self):
        self.children = {10: [(11, "java.exe")]}
        self.assertFalse(core.start_service(None, {}, self.service))
        core.run_in_pane.assert_not_called()

    def test_port_in_use_raises_without_touching_the_pane(self):
        with mock.patch.object(core.procs, "is_listening", return_value=True):
            with self.assertRaises(core.PortInUseError):
                core.start_service(None, {}, self.service)
        core.run_in_pane.assert_not_called()

    def test_stopped_flag_is_cleared_on_restart(self):
        self.state["panes"][0]["stopped"] = True
        core.start_service(None, {}, self.service)
        self.assertNotIn("stopped", self.state["panes"][0])


class StartPlanExitedTest(unittest.TestCase):
    """전체 시작에서 EXITED 백엔드는 다시 기동되고, 그 의존 프론트는 '의존 실패'가 되지 않는다."""

    def setUp(self):
        self.state = {"tab_id": "t1", "control_box": "cb",
                      "panes": [{"name": "backend", "pane_id": "p1"}]}
        self.children = {}
        self.config = {"services": [
            {"name": "backend", "command": "run-backend"},
            {"name": "frontend", "command": "run-frontend", "depends_on": ["backend"]},
        ]}
        patches = [
            mock.patch.object(core, "live_state", side_effect=lambda *_: self.state),
            mock.patch.object(core, "live_pane_ids", return_value={"p1", "cb"}),
            mock.patch.object(core, "shell_pid", return_value=10),
            mock.patch.object(core.procs, "child_process_map", side_effect=lambda: self.children),
            mock.patch.object(core.procs, "is_listening", return_value=False),
            mock.patch.object(core, "herdr", return_value={}),
            mock.patch.object(core, "write_state"),
            mock.patch.object(core, "remove_state"),
            mock.patch.object(core, "run_in_pane"),
            mock.patch.object(core, "service_dir", side_effect=lambda project, service: project),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_exited_backend_is_started_and_frontend_is_not_failed(self):
        plan = core.StartPlan(None, self.config)
        plan.step()
        self.assertEqual(plan.started, 1)
        self.assertEqual(plan.failed, [])
        self.assertEqual(plan.skipped, [])
        core.run_in_pane.assert_called_once_with("p1", self.config["services"][0])

    def test_live_backend_is_reported_as_skipped_not_failed(self):
        self.children = {10: [(11, "java.exe")]}
        config = {"services": [{"name": "backend", "command": "run-backend"}]}
        plan = core.StartPlan(None, config)
        plan.step()
        self.assertEqual(plan.skipped, ["backend"])
        self.assertEqual(plan.failed, [])
        self.assertEqual(plan.started, 0)


if __name__ == "__main__":
    unittest.main()
