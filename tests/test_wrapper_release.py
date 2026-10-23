import os
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

WRAPPER = [(29176, "cmd.exe")]
PROMPT = "일괄 작업을 끝내시겠습니까 (Y/N)?"


class ReleaseWrapperTest(unittest.TestCase):
    """시작할 때 pane 에 cmd.exe 래퍼만 남아 있으면: 질문이 보이면 Y 로 답하고 시작, 서비스가 살아 있으면 건드리지 않는다."""

    def setUp(self):
        self.state = {"tab_id": "t1", "control_box": "cb", "panes": [{"name": "backend", "pane_id": "p1"}]}
        self.children = {10: list(WRAPPER)}   # 셸 pid → 자식
        self.screen = PROMPT                  # pane 화면 (질문)
        self.clear_on_enter = True            # Enter 로 답하면 래퍼가 끝난다
        self.clock = [0.0]
        self.herdr = mock.Mock(side_effect=self.fake_herdr)
        patches = [
            mock.patch.object(core, "live_state", side_effect=lambda *_: self.state),
            mock.patch.object(core, "live_pane_ids", return_value={"p1", "cb"}),
            mock.patch.object(core, "shell_pid", return_value=10),
            mock.patch.object(core.procs, "child_process_map", side_effect=lambda: self.children),
            mock.patch.object(core.procs, "is_listening", return_value=False),
            mock.patch.object(core, "herdr", self.herdr),
            mock.patch.object(core, "herdr_text", side_effect=lambda *args: self.screen),
            mock.patch.object(core, "write_state"),
            mock.patch.object(core, "remove_state"),
            mock.patch.object(core, "run_in_pane"),
            mock.patch.object(core, "service_dir", side_effect=lambda project, service: project),
            mock.patch.object(core.time, "sleep"),
            mock.patch.object(core.time, "monotonic", side_effect=self.fake_clock),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.project = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: os.rmdir(self.project))
        self.service = {"name": "backend", "command": "run-backend"}

    def fake_clock(self):
        self.clock[0] += 1.0
        return self.clock[0]

    def fake_herdr(self, *args, check=True):
        if args[:2] == ("pane", "send-keys") and args[3] == "enter" and self.clear_on_enter:
            self.children = {}
        if args[:2] == ("pane", "split"):
            return {"pane": {"pane_id": "p9"}}
        return {}

    def calls(self, *prefix):
        return [call.args for call in self.herdr.call_args_list if call.args[:len(prefix)] == prefix]

    def test_wrapper_with_prompt_is_answered_then_pane_is_reused(self):
        self.assertTrue(core.start_service(self.project, {}, self.service))
        self.assertIn(("pane", "send-text", "p1", "Y"), self.calls("pane", "send-text"))
        core.run_in_pane.assert_called_once_with("p1", self.service)
        self.assertEqual(self.calls("pane", "split"), [])

    def test_wrapper_without_prompt_is_not_answered(self):
        self.screen = "Stopping..."
        self.assertFalse(core.start_service(self.project, {}, self.service))
        self.assertEqual(self.calls("pane", "send-text"), [])
        core.run_in_pane.assert_not_called()

    def test_live_service_under_the_wrapper_is_left_alone(self):
        self.children = {10: list(WRAPPER), 29176: [(30000, "java.exe")]}
        self.assertFalse(core.start_service(self.project, {}, self.service))
        self.assertEqual(self.calls("pane", "send-text"), [])
        core.run_in_pane.assert_not_called()

    def test_pane_is_replaced_when_the_wrapper_stays_after_answering(self):
        self.clear_on_enter = False  # 답해도 래퍼가 남는다
        self.assertTrue(core.start_service(self.project, {}, self.service))
        self.assertIn(("pane", "close", "p1"), self.calls("pane", "close"))
        self.assertEqual(self.calls("pane", "split")[0][2], "cb")
        core.run_in_pane.assert_called_once_with("p9", self.service)


class SkippedMessageTest(unittest.TestCase):
    """이미 실행 중이라 건너뛴 서비스는 완료 메시지에 보이고, 실패 목록과 구분된다."""

    def setUp(self):
        i18n.set_language("en")
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / ".herdr-devrun.json"
        path.write_text('{"services": [{"name": "backend", "command": "x"}]}', encoding="utf-8")
        self.panel = panel.Panel(path, None)
        self.panel.reload_config()
        step = mock.patch.object(core.StartPlan, "step")
        step.start()
        self.addCleanup(step.stop)
        self.plan = core.StartPlan(None, {"services": [{"name": "backend", "command": "x"}]})
        self.plan.pending = []
        self.panel.plan = self.plan

    def test_skipped_service_is_named_in_the_completion_message(self):
        self.plan.skipped = ["backend"]
        self.panel.advance_plan()
        self.assertEqual(self.panel.message, i18n.t("panel.started_all_skipped", names="backend"))
        self.assertIn("backend", self.panel.message)

    def test_failed_and_skipped_are_listed_separately(self):
        self.plan.skipped = ["backend"]
        self.plan.failed = [("frontend", "reason.dependency_failed")]
        self.panel.advance_plan()
        self.assertIn(i18n.t("panel.started_all_partial", details=self.plan.failure_text()), self.panel.message)
        self.assertIn(i18n.t("panel.already_running", names="backend"), self.panel.message)

    def test_plain_success_message_when_nothing_skipped(self):
        self.panel.advance_plan()
        self.assertEqual(self.panel.message, i18n.t("panel.started_all"))


if __name__ == "__main__":
    unittest.main()
