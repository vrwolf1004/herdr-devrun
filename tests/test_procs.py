import socket
import unittest

import support  # noqa: F401  (src 경로 준비)
import procs


class ParseTest(unittest.TestCase):
    def test_proc_stat_with_spaces_and_parens_in_name(self):
        self.assertEqual(procs.parse_proc_stat("4242 (my (odd) app) S 17 4242 4242 0 -1"), (4242, 17, "my (odd) app"))

    def test_proc_stat_invalid(self):
        self.assertIsNone(procs.parse_proc_stat("garbage"))
        self.assertIsNone(procs.parse_proc_stat("12 (x)"))

    def test_ps_line(self):
        self.assertEqual(procs.parse_ps_line("  501   1 /usr/bin/java"), (501, 1, "java"))
        self.assertIsNone(procs.parse_ps_line("PID PPID COMM"))


class RunningChildrenTest(unittest.TestCase):
    SHELL = 100

    def test_no_children(self):
        self.assertFalse(procs.has_running_children({}, self.SHELL))

    def test_conhost_only(self):
        self.assertFalse(procs.has_running_children({self.SHELL: [(101, "conhost.exe")]}, self.SHELL))

    def test_real_child(self):
        self.assertTrue(procs.has_running_children({self.SHELL: [(101, "java.exe")]}, self.SHELL))

    def test_bat_waiting_for_terminate_prompt(self):
        # gradlew.bat 에 Ctrl+C 후 cmd.exe 만 남아 Y/N 을 기다리는 상태
        self.assertFalse(procs.has_running_children({self.SHELL: [(101, "cmd.exe")]}, self.SHELL))

    def test_bat_still_running(self):
        child_map = {self.SHELL: [(101, "cmd.exe")], 101: [(102, "java.exe")]}
        self.assertTrue(procs.has_running_children(child_map, self.SHELL))

    def test_cycle_does_not_loop(self):
        child_map = {self.SHELL: [(101, "cmd.exe")], 101: [(self.SHELL, "cmd.exe")]}
        self.assertFalse(procs.has_running_children(child_map, self.SHELL))

    def test_vanished_child_is_not_running(self):
        # 목록을 모으는 사이 끝난 프로세스는 자식 목록에 없어도 안전하게 빈 결과로 본다.
        child_map = {self.SHELL: [(101, "cmd.exe")]}
        self.assertFalse(procs.has_running_children(child_map, self.SHELL))
        self.assertFalse(procs.has_running_children(child_map, 999))


class ListeningTest(unittest.TestCase):
    def test_listening_and_closed(self):
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen()
        port = server.getsockname()[1]
        try:
            self.assertTrue(procs.is_listening(port))
        finally:
            server.close()
        self.assertFalse(procs.is_listening(port))


class CurrentOsTest(unittest.TestCase):
    def test_child_process_map_runs(self):
        child_map = procs.child_process_map()
        self.assertTrue(child_map)
        self.assertTrue(all(isinstance(pid, int) and isinstance(name, str)
                            for children in child_map.values() for pid, name in children))


if __name__ == "__main__":
    unittest.main()
