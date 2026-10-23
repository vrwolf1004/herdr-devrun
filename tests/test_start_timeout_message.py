import itertools
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  (src 경로 준비)
import core
import i18n
import procs


class StartTimeoutMessageTest(unittest.TestCase):
    """시간 초과 메시지는 프론트 이름과 함께 기다린 의존 서비스 이름을 보여 준다."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.project = Path(self.folder.name)
        self.config = {"tab": "app", "services": [
            {"name": "backend", "command": "x"},
            {"name": "frontend", "command": "y", "depends_on": ["backend"], "start_timeout": 5},
        ]}
        # 처음 호출 (계획 시작) 은 0초, 그 뒤는 1000초 (frontend 의 start_timeout 5초를 넘긴다)
        clock = itertools.chain([0.0], itertools.repeat(1000.0))
        patches = [
            mock.patch.object(core, "live_state", return_value=None),
            mock.patch.object(core, "live_pane_ids", return_value=set()),
            mock.patch.object(procs, "child_process_map", return_value={}),
            mock.patch.object(core, "is_ready", return_value=False),  # backend 는 끝내 준비되지 않는다
            mock.patch.object(core, "start_service", return_value=True),
            mock.patch.object(core.time, "monotonic", side_effect=lambda: next(clock)),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_timeout_names_the_dependency_that_was_not_ready(self):
        plan = core.StartPlan(self.project, self.config)
        plan.step()
        self.assertEqual(plan.failed, [("frontend", "reason.timeout")])
        self.assertEqual(plan.failure_text(),
                         f"frontend ({i18n.t('reason.timeout_waiting', names='backend')})")
        self.assertIn("frontend", plan.failure_text())
        self.assertIn("backend", plan.failure_text())

    def test_dependency_failed_text_is_unchanged(self):
        plan = core.StartPlan(self.project, self.config)
        plan.failed = [("frontend", "reason.dependency_failed")]
        self.assertEqual(plan.failure_text(), f"frontend ({i18n.t('reason.dependency_failed')})")

    def test_port_in_use_text_is_unchanged(self):
        plan = core.StartPlan(self.project, self.config)
        plan.failed = [("api", "reason.port_in_use")]
        self.assertEqual(plan.failure_text(), f"api ({i18n.t('reason.port_in_use')})")

    def test_timeout_without_waiting_names_falls_back_to_the_plain_reason(self):
        plan = core.StartPlan(self.project, self.config)
        plan.failed = [("frontend", "reason.timeout")]
        self.assertEqual(plan.failure_text(), f"frontend ({i18n.t('reason.timeout')})")


if __name__ == "__main__":
    unittest.main()
