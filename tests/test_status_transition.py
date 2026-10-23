import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  (src 경로 준비)
import core
import i18n
import panel
import procs
from core import Status

PORT = 5173


class PortState:
    """포트가 열렸는지 테스트 중에 바꿔 가며 본다 (procs.is_listening 대신)."""

    def __init__(self):
        self.open = False

    def is_listening(self, port):
        return self.open


class StatusTransitionTest(unittest.TestCase):
    """프로세스는 떠 있고 포트만 늦게 열리는 경우: 포트가 열린 뒤 한 번의 갱신에서 RUNNING 이 되어야 한다."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.project = Path(self.folder.name)
        config_path = self.project / ".herdr-devrun.json"
        config_path.write_text(json.dumps({"tab": "app", "services": [
            {"name": "web", "command": "npm run dev", "port": PORT},
        ]}), encoding="utf-8")
        self.port = PortState()
        self.state = {"project": str(self.project), "label": "app", "workspace_id": "w1", "tab_id": "t1",
                      "panes": [{"name": "web", "pane_id": "p1"}], "control_box": "cb"}
        patches = [
            mock.patch.object(core, "live_pane_ids", return_value={"p1", "cb"}),
            mock.patch.object(core, "live_state", return_value=self.state),
            mock.patch.object(core, "shell_pid", return_value=100),          # 셸 pid
            mock.patch.object(core, "service_log", return_value=[]),
            mock.patch.object(procs, "child_process_map", return_value={100: [(200, "node.exe")]}),
            mock.patch.object(procs, "is_listening", side_effect=self.port.is_listening),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.panel = panel.Panel(config_path, None)
        self.panel.reload_config()

    def tearDown(self):
        i18n.set_language("en")

    def test_process_running_and_port_open_is_running(self):
        self.port.open = True
        self.panel.refresh()
        self.assertEqual(self.panel.statuses["web"], Status.RUNNING)

    def test_process_running_and_port_closed_is_starting(self):
        self.port.open = False
        self.panel.refresh()
        self.assertEqual(self.panel.statuses["web"], Status.STARTING)

    def test_port_opening_switches_to_running_in_one_refresh(self):
        self.port.open = False
        self.panel.refresh()
        self.assertEqual(self.panel.statuses["web"], Status.STARTING)
        self.port.open = True  # 포트가 열린 뒤 다음 갱신 한 번
        self.panel.refresh()
        self.assertEqual(self.panel.statuses["web"], Status.RUNNING)

    def test_service_status_has_no_port_cache(self):
        """같은 pane 을 두 번 봐도 포트를 다시 확인한다 (pid_cache 는 셸 pid 만 캐시한다)."""
        cache = {}
        self.port.open = False
        self.assertEqual(core.service_status(self.panel.services[0], self.state, {100: [(200, "node.exe")]}, cache),
                         Status.STARTING)
        self.port.open = True
        self.assertEqual(core.service_status(self.panel.services[0], self.state, {100: [(200, "node.exe")]}, cache),
                         Status.RUNNING)
        self.assertEqual(cache, {"p1": 100})


if __name__ == "__main__":
    unittest.main()
