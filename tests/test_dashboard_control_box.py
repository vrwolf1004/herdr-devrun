import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  (src 경로 준비)
import core
import i18n
import panel
from core import Status
from test_control_box import FakeHerdr


class DashboardStartControlBoxTest(unittest.TestCase):
    """대시보드의 시작 (줄 버튼, 전체 시작) 도 CLI up 과 같이 컨트롤 박스를 먼저 만든다."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.project = Path(self.folder.name)
        config_path = self.project / ".herdr-devrun.json"
        config_path.write_text(json.dumps({"tab": "app", "services": [
            {"name": "api", "command": "x", "port": 8001},
        ]}), encoding="utf-8")
        self.herdr = FakeHerdr(spaces=[])
        self.saved_state = None  # write_state 로 쓴 state 를 live_state 가 돌려준다
        self.start_calls = []    # start_service 가 불린 순서 (herdr 호출과 한 목록에 기록)
        self.start_states = []   # start_service 가 불렸을 때 보이던 state

        def write_state(project_dir, state):
            self.saved_state = state

        def live_state(project_dir, pane_ids):
            return self.saved_state

        def fake_start_service(project_dir, config, service, focus=False):
            self.herdr.calls.append(("start_service", service["name"]))
            self.start_states.append(dict(self.saved_state) if self.saved_state else None)
            return True

        patches = [
            mock.patch.object(core, "panel_marker_path", return_value=self.project / "panel.marker"),
            mock.patch.object(core, "live_pane_ids", return_value=set()),
            mock.patch.object(core, "live_state", side_effect=live_state),
            mock.patch.object(core, "herdr", side_effect=self.herdr),
            mock.patch.object(core, "write_state", side_effect=write_state),
            mock.patch.object(core, "remove_state"),
            mock.patch.object(core, "run_in_pane"),
            mock.patch.object(core, "start_service", side_effect=fake_start_service),
            mock.patch.object(panel.term, "write"),  # 화면 그리기는 테스트에서 실제 콘솔에 내보내지 않는다
            mock.patch.object(panel.term, "size", return_value=(120, 40)),
            mock.patch.dict(os.environ, {"HERDR_PANE_ID": "cur"}),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

        self.panel = panel.Panel(self.project / ".herdr-devrun.json", None)
        self.panel.reload_config()
        self.panel.statuses = {"api": Status.STOPPED}

    def tearDown(self):
        i18n.set_language("en")

    def position(self, *call):
        return self.herdr.calls.index(call)

    def test_start_all_creates_the_control_box_before_any_service_starts(self):
        self.panel.execute("start_all")
        while self.panel.plan:
            self.panel.advance_plan()
        create = ("workspace", "create", "--cwd", str(self.project), "--label", "devrun", "--focus")
        self.assertLess(self.position(*create), self.position("start_service", "api"))
        # 서비스가 떠 있는 시점의 state 는 방금 만든 devrun space / 탭이다
        self.assertEqual(self.start_states[0]["workspace_id"], "w9")
        self.assertEqual(self.start_states[0]["tab_id"], "t9")
        self.assertEqual(self.start_states[0]["control_box"], "cb")

    def test_single_start_creates_the_control_box_first_too(self):
        self.panel.selected = 0
        self.panel.execute("start")
        create = ("workspace", "create", "--cwd", str(self.project), "--label", "devrun", "--focus")
        self.assertLess(self.position(*create), self.position("start_service", "api"))
        self.assertEqual(self.start_states[0]["workspace_id"], "w9")

    def test_existing_control_box_is_reused_not_recreated(self):
        self.saved_state = {"project": str(self.project), "label": "app", "workspace_id": "w5",
                            "tab_id": "t5", "panes": [], "control_box": "cb5"}
        self.panel.execute("start_all")
        while self.panel.plan:
            self.panel.advance_plan()
        self.assertFalse(any(call[:2] == ("workspace", "create") for call in self.herdr.calls))
        self.assertFalse(any(call[:2] == ("tab", "create") for call in self.herdr.calls))
        self.assertEqual(self.start_states[0]["workspace_id"], "w5")

    def test_failure_to_make_the_control_box_starts_nothing_and_shows_the_error(self):
        def failing(*args, check=True):
            if args[:2] == ("workspace", "create"):
                raise core.DevrunError("boom")
            return self.herdr(*args, check=check)

        with mock.patch.object(core, "herdr", side_effect=failing):
            self.panel.execute("start_all")
        self.assertIsNone(self.panel.plan)
        self.assertEqual(self.start_states, [])
        self.assertTrue(self.panel.message.startswith("Error:"), self.panel.message)


if __name__ == "__main__":
    unittest.main()
