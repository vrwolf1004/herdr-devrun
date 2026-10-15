import sys
import unittest
from unittest import mock

import support  # noqa: F401  (src 경로 준비)
import term

ESC = "\x1b"


def parse(terminal, text):
    terminal._buffer += text
    return [(event.kind, event.key or event.mouse, event.x, event.y) for event in terminal._parse()]


class UnixInputParserTest(unittest.TestCase):
    """Linux/macOS 입력 해석. 순수 로직이라 어느 OS 에서든 돈다."""

    def setUp(self):
        self.terminal = term._UnixTerminal.__new__(term._UnixTerminal)
        self.terminal._buffer = ""
        self.terminal._last_click = (0.0, -1, -1)
        self.terminal._resized = False

    def test_arrow_and_navigation_keys(self):
        events = parse(self.terminal, f"{ESC}[A{ESC}[B{ESC}OA{ESC}[H{ESC}[4~")
        self.assertEqual([key for _, key, _, _ in events], ["up", "down", "up", "home", "end"])

    def test_plain_keys(self):
        events = parse(self.terminal, "rQ\r\x03한")
        self.assertEqual([key for _, key, _, _ in events], ["r", "Q", "enter", "ctrl+c", "한"])

    def test_escape_alone(self):
        self.assertEqual(parse(self.terminal, ESC), [("key", "esc", 0, 0)])

    def test_split_mouse_sequence_waits_for_rest(self):
        self.assertEqual(parse(self.terminal, f"{ESC}[<0;12"), [])
        self.assertEqual(parse(self.terminal, ";5M"), [("mouse", "down", 11, 4)])

    def test_release_is_ignored(self):
        self.assertEqual(parse(self.terminal, f"{ESC}[<0;12;5m"), [])

    def test_double_click_same_cell(self):
        with mock.patch.object(term.time, "monotonic", side_effect=[10.0, 10.2]):
            events = parse(self.terminal, f"{ESC}[<0;3;4M{ESC}[<0;3;4M")
        self.assertEqual([mouse for _, mouse, _, _ in events], ["down", "double"])

    def test_slow_second_click_is_not_double(self):
        with mock.patch.object(term.time, "monotonic", side_effect=[10.0, 11.0]):
            events = parse(self.terminal, f"{ESC}[<0;3;4M{ESC}[<0;3;4M")
        self.assertEqual([mouse for _, mouse, _, _ in events], ["down", "down"])

    def test_wheel(self):
        events = parse(self.terminal, f"{ESC}[<64;1;1M{ESC}[<65;1;1M")
        self.assertEqual([mouse for _, mouse, _, _ in events], ["wheelup", "wheeldown"])

    def test_right_button_is_ignored(self):
        self.assertEqual(parse(self.terminal, f"{ESC}[<2;1;1M"), [])

    def test_unknown_sequence_is_dropped(self):
        self.assertEqual(parse(self.terminal, f"{ESC}[1;5Ax"), [("key", "x", 0, 0)])


@unittest.skipUnless(sys.platform == "win32", "Windows 콘솔 입력 레코드")
class WindowsInputRecordTest(unittest.TestCase):
    def setUp(self):
        self.terminal = term._WindowsTerminal()

    def record(self, event_type, payload):
        record = self.terminal._record_type()
        record.EventType = event_type
        for index, value in enumerate(payload):
            record.Event[index] = value
        return record

    def key(self, virtual_key, char="\x00", control=0):
        payload = bytearray(16)
        payload[0:4] = (1).to_bytes(4, "little")
        payload[6:8] = virtual_key.to_bytes(2, "little")
        payload[10:12] = char.encode("utf-16-le")
        payload[12:16] = control.to_bytes(4, "little")
        return self.terminal._to_event(self.record(0x0001, [b - 256 if b > 127 else b for b in payload]))

    def mouse(self, x, y, buttons, flags):
        payload = bytearray(16)
        payload[0:2] = x.to_bytes(2, "little")
        payload[2:4] = y.to_bytes(2, "little")
        payload[4:8] = buttons.to_bytes(4, "little", signed=True)
        payload[12:16] = flags.to_bytes(4, "little")
        return self.terminal._to_event(self.record(0x0002, [b - 256 if b > 127 else b for b in payload]))

    def test_keys(self):
        self.assertEqual(self.key(0x26).key, "up")
        self.assertEqual(self.key(0x0D).key, "enter")
        self.assertEqual(self.key(0x52, "r").key, "r")
        self.assertEqual(self.key(0x43, "\x03", control=0x0008).key, "ctrl+c")

    def test_mouse(self):
        self.assertEqual((self.mouse(5, 7, 1, 0).mouse, self.mouse(5, 7, 1, 0).x), ("down", 5))
        self.assertEqual(self.mouse(5, 7, 0, 2).mouse, "double")
        self.assertEqual(self.mouse(0, 0, -(120 << 16), 4).mouse, "wheeldown")
        self.assertEqual(self.mouse(0, 0, 120 << 16, 4).mouse, "wheelup")
        self.assertIsNone(self.mouse(5, 7, 0, 1))  # 이동은 버린다


if __name__ == "__main__":
    unittest.main()
