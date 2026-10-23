import unittest
from unittest import mock

import support  # noqa: F401  (src 경로 준비)
import core


class StopPromptTest(unittest.TestCase):
    """Ctrl+C 뒤 pane 에 Y/N 질문이 나오면 Y 와 Enter 로 답한다 (.bat 의 일괄 작업 종료 확인)."""

    def setUp(self):
        self.herdr_calls = []
        self.screens = []           # herdr_text 가 차례로 돌려줄 화면 (다 쓰면 last_screen)
        self.last_screen = ""
        self.alive_iterations = 0   # 이 반복 번호까지 프로세스가 살아 있다고 본다
        self.iteration = 0          # 기다리는 루프의 반복 번호 (child_process_map 호출마다 올라간다)
        self.wrapper_iterations = 0  # 이 반복 번호까지 셸 아래 cmd.exe (.bat 래퍼) 가 남아 있다
        self.prompt_after = None    # 이 시각 (가짜 시계) 이후의 화면에는 질문이 있다
        self.clock = [0.0]
        patches = [
            mock.patch.object(core, "herdr", side_effect=self.fake_herdr),
            mock.patch.object(core, "herdr_text", side_effect=self.fake_text),
            mock.patch.object(core, "shell_pid", return_value=10),
            mock.patch.object(core.procs, "child_process_map", side_effect=self.fake_map),
            mock.patch.object(core.procs, "has_running_children",
                              side_effect=lambda child_map, pid: self.iteration <= self.alive_iterations),
            mock.patch.object(core.time, "sleep"),
            mock.patch.object(core.time, "monotonic", side_effect=self.fake_clock),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def fake_herdr(self, *args, check=True):
        self.herdr_calls.append(args)
        return {}

    def fake_text(self, *args):
        if self.prompt_after is not None and self.clock[0] > self.prompt_after:
            return "(Y/N)?"
        return self.screens.pop(0) if self.screens else self.last_screen

    def fake_map(self):
        self.iteration += 1
        if self.iteration <= self.wrapper_iterations:
            return {10: [(29176, "cmd.exe")]}
        return {}

    def fake_clock(self):
        self.clock[0] += 0.1
        return self.clock[0]

    def answers(self):
        return [call for call in self.herdr_calls if call[:2] == ("pane", "send-text")]

    def test_prompt_is_answered_with_y_and_enter(self):
        self.alive_iterations = 1
        self.screens = ["배치 작업을 끝내시겠습니까 (Y/N)?"]
        core.interrupt_and_wait([("p1", 30)])
        self.assertEqual(self.answers(), [("pane", "send-text", "p1", "Y")])
        self.assertIn(("pane", "send-keys", "p1", "enter"), self.herdr_calls)

    def test_no_prompt_means_no_answer(self):
        self.alive_iterations = 1
        self.screens = ["Stopping..."]
        core.interrupt_and_wait([("p1", 30)])
        self.assertEqual(self.answers(), [])
        self.assertNotIn(("pane", "send-keys", "p1", "enter"), self.herdr_calls)

    def test_same_prompt_is_not_answered_twice(self):
        self.alive_iterations = 3
        self.screens = ["(Y/N)?", "(Y/N)?", "(Y/N)?"]
        core.interrupt_and_wait([("p1", 30)])
        self.assertEqual(len(self.answers()), 1)

    def test_each_new_prompt_is_answered(self):
        self.alive_iterations = 2
        self.screens = ["(Y/N)?", "(Y/N)?\n(Y/N)?"]
        core.interrupt_and_wait([("p1", 30)])
        self.assertEqual(len(self.answers()), 2)

    def test_lowercase_and_bracket_forms_are_detected(self):
        self.alive_iterations = 1
        self.screens = ["Continue? [y/n]"]
        core.interrupt_and_wait([("p1", 30)])
        self.assertEqual(len(self.answers()), 1)

    def test_cmd_wrapper_waiting_for_yn_is_answered(self):
        # Ctrl+C 뒤 cmd.exe 만 남아 질문을 기다리는 경우: 자식이 없다고 끝난 것으로 보지 않고 답한다.
        self.wrapper_iterations = 2
        self.screens = ["일괄 작업을 끝내시겠습니까 (Y/N)?"]
        core.interrupt_and_wait([("p1", 30)])
        self.assertEqual(len(self.answers()), 1)
        self.assertIn(("pane", "send-keys", "p1", "enter"), self.herdr_calls)

    def test_question_that_appears_when_the_wait_ends_is_still_answered(self):
        self.wrapper_iterations = 10 ** 9  # 래퍼가 계속 남는다
        self.prompt_after = 1.05           # 기다리는 동안에는 질문이 없고, 기다림이 끝나는 순간에 나온다
        core.interrupt_and_wait([("p1", 1)])
        self.assertEqual(len(self.answers()), 1)

    def test_cmd_wrapper_without_prompt_is_not_answered(self):
        self.wrapper_iterations = 1
        self.screens = ["Stopping..."]
        core.interrupt_and_wait([("p1", 30)])
        self.assertEqual(self.answers(), [])

    def test_live_process_counts_a_waiting_cmd_wrapper(self):
        with mock.patch.object(core.procs, "has_running_children", return_value=False), \
                mock.patch.object(core.procs, "child_process_map", return_value={10: [(29176, "cmd.exe")]}):
            self.assertTrue(core._has_live_process({"pane_id": "p1"}))
        with mock.patch.object(core.procs, "has_running_children", return_value=False), \
                mock.patch.object(core.procs, "child_process_map", return_value={}):
            self.assertFalse(core._has_live_process({"pane_id": "p1"}))

    def test_still_running_after_timeout_returns(self):
        self.alive_iterations = 10 ** 9  # 끝나지 않는다
        self.last_screen = "(Y/N)?"
        core.interrupt_and_wait([("p1", 1)])  # 1초 뒤에는 기다리지 않고 돌아온다
        self.assertEqual(len(self.answers()), 1)

    def test_pane_without_shell_pid_is_only_interrupted(self):
        with mock.patch.object(core, "shell_pid", return_value=None):
            core.interrupt_and_wait([("p1", 30)])
        self.assertEqual([call for call in self.herdr_calls if call[:2] == ("pane", "send-keys")],
                         [("pane", "send-keys", "p1", "ctrl+c")])
        self.assertEqual(self.answers(), [])


if __name__ == "__main__":
    unittest.main()
