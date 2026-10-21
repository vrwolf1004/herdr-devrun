import unittest
from unittest import mock

import support  # noqa: F401  (src 경로 준비)
import core
import procs


class LinuxProcParsingTest(unittest.TestCase):
    """Linux 경로: /proc/<pid>/stat 를 가짜 파일로 읽는다."""

    def run_proc(self, entries, listed=()):
        def fake_open(path, *args, **kwargs):
            pid = path.split("/")[2]
            if pid not in entries:
                raise OSError("vanished")
            return mock.mock_open(read_data=entries[pid])()

        names = list(entries) + list(listed) + ["self", "net"]
        with mock.patch.object(procs.os, "listdir", return_value=names), \
                mock.patch("builtins.open", side_effect=fake_open):
            return procs._proc_processes()

    def test_reads_pairs_and_skips_vanished_and_non_numeric(self):
        # "300" 은 목록에는 있지만 읽는 사이 끝나서 파일이 없다 → OSError 로 건너뛴다
        pairs = self.run_proc({
            "100": "100 (bash) S 1 100 100 0 -1",
            "200": "200 (java) S 100 200 200 0 -1",
        }, listed=["300"])
        self.assertEqual(sorted(pairs), [(100, 1, "bash"), (200, 100, "java")])

    def test_comm_with_spaces_and_parens(self):
        self.assertEqual(procs.parse_proc_stat("42 (my (weird) name) S 7 42 42"), (42, 7, "my (weird) name"))

    def test_invalid_stat_is_none(self):
        self.assertIsNone(procs.parse_proc_stat("garbage"))


class MacPsParsingTest(unittest.TestCase):
    """macOS 경로: ps 출력 문자열을 가짜로 준다."""

    def test_parses_ps_output_and_uses_basename(self):
        output = "  100     1 /bin/bash\n  200   100 java\nxx yy zz\n"
        completed = mock.Mock(stdout=output)
        with mock.patch.object(procs.subprocess, "run", return_value=completed):
            pairs = procs._ps_processes()
        self.assertEqual(pairs, [(100, 1, "bash"), (200, 100, "java")])

    def test_parse_ps_line_rejects_non_numeric(self):
        self.assertIsNone(procs.parse_ps_line("abc def bash"))


class ChildMapTest(unittest.TestCase):
    def test_self_reference_is_excluded_and_map_is_built(self):
        pairs = [(0, 0, "System Idle Process"), (100, 1, "shell"), (101, 100, "java.exe")]
        with mock.patch.object(procs.sys, "platform", "win32"), \
                mock.patch.object(procs, "_windows_processes", return_value=pairs):
            child_map = procs.child_process_map()
        self.assertNotIn(0, child_map.get(0, []))
        self.assertEqual(child_map[100], [(101, "java.exe")])


class StopTimeoutTest(unittest.TestCase):
    def test_gives_up_at_timeout_when_process_never_ends(self):
        clock = {"now": 0.0}

        def fake_sleep(seconds):
            clock["now"] += seconds

        with mock.patch.object(core, "shell_pid", return_value=500), \
                mock.patch.object(core, "herdr", return_value={}), \
                mock.patch.object(core.procs, "child_process_map", return_value={500: [(501, "java")]}), \
                mock.patch.object(core.time, "monotonic", side_effect=lambda: clock["now"]), \
                mock.patch.object(core.time, "sleep", side_effect=fake_sleep):
            core.interrupt_and_wait([("p1", 2.0)])
        self.assertGreaterEqual(clock["now"], 2.0)
        self.assertLess(clock["now"], 3.0)

    def test_returns_early_when_children_finish(self):
        clock = {"now": 0.0}
        maps = [{500: [(501, "java")]}, {}]

        def fake_sleep(seconds):
            clock["now"] += seconds

        with mock.patch.object(core, "shell_pid", return_value=500), \
                mock.patch.object(core, "herdr", return_value={}), \
                mock.patch.object(core.procs, "child_process_map", side_effect=lambda: maps.pop(0) if maps else {}), \
                mock.patch.object(core.time, "monotonic", side_effect=lambda: clock["now"]), \
                mock.patch.object(core.time, "sleep", side_effect=fake_sleep):
            core.interrupt_and_wait([("p1", 10.0)])
        self.assertLess(clock["now"], 10.0)


if __name__ == "__main__":
    unittest.main()
