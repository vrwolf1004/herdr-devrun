"""대시보드용 터미널 입출력. OS 마다 입력 방법이 다르다.

  Windows : ReadConsoleInputW (ctypes). herdr pane 은 ConPTY 위에서 돌고, 앱이 ENABLE_MOUSE_INPUT 을
            켜면 ConPTY 가 터미널 쪽 마우스 입력을 MOUSE_EVENT 로 바꿔 준다.
  Unix    : termios 로 raw 모드, xterm SGR 마우스(1000/1006)를 켜고 바이트를 직접 해석한다.

이벤트는 Event 하나로 통일한다.
  kind  : "key" | "mouse" | "resize"
  key   : "up" "down" "home" "end" "enter" "esc" "ctrl+c" 또는 글자 하나
  mouse : "down" | "double" | "wheelup" | "wheeldown",  x/y 는 0 부터
"""

import os
import shutil
import sys
import time
from dataclasses import dataclass

ESC = "\x1b"
DOUBLE_CLICK_SECONDS = 0.4


@dataclass
class Event:
    kind: str
    key: str = ""
    mouse: str = ""
    x: int = 0
    y: int = 0


def size():
    columns, lines = shutil.get_terminal_size((80, 24))
    return columns, lines


def write(text):
    sys.stdout.write(text)
    sys.stdout.flush()


def open_terminal():
    return _WindowsTerminal() if sys.platform == "win32" else _UnixTerminal()


class _Screen:
    """대체 화면 + 커서 숨김. with 블록을 벗어나면 원래대로 돌린다."""

    def __enter__(self):
        self._enter_input()
        write(f"{ESC}[?1049h{ESC}[?25l{ESC}[2J")
        return self

    def __exit__(self, *exc):
        write(f"{ESC}[0m{ESC}[?25h{ESC}[?1049l")
        self._leave_input()
        return False

    def _enter_input(self):
        raise NotImplementedError

    def _leave_input(self):
        raise NotImplementedError


# ---------------------------------------------------------------- Windows


class _WindowsTerminal(_Screen):
    _KEY_EVENT = 0x0001
    _MOUSE_EVENT = 0x0002
    _WINDOW_BUFFER_SIZE_EVENT = 0x0004
    _VIRTUAL_KEYS = {0x26: "up", 0x28: "down", 0x24: "home", 0x23: "end", 0x0D: "enter", 0x1B: "esc", 0x08: "backspace"}

    def __init__(self):
        import ctypes
        from ctypes import wintypes

        class InputRecord(ctypes.Structure):
            # INPUT_RECORD (20 bytes). KEY_EVENT_RECORD 와 MOUSE_EVENT_RECORD 가 offset 4 부터 겹치므로
            # 공용 영역을 바이트로 받아 두고 필요한 위치만 꺼낸다.
            _fields_ = [("EventType", wintypes.WORD), ("_padding", wintypes.WORD), ("Event", ctypes.c_byte * 16)]

        self._ctypes = ctypes
        self._wintypes = wintypes
        self._record_type = InputRecord
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        # 64비트에서 HANDLE 이 int 로 잘리지 않도록 인자 형식을 모두 지정한다.
        self._kernel32.GetStdHandle.restype = wintypes.HANDLE
        self._kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
        self._kernel32.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        self._kernel32.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self._kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self._kernel32.WaitForSingleObject.restype = wintypes.DWORD
        self._kernel32.ReadConsoleInputW.argtypes = [wintypes.HANDLE, ctypes.POINTER(InputRecord),
                                                     wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        self._input = self._kernel32.GetStdHandle(wintypes.DWORD(-10 & 0xFFFFFFFF))
        self._output = self._kernel32.GetStdHandle(wintypes.DWORD(-11 & 0xFFFFFFFF))
        self._saved_input = wintypes.DWORD()
        self._saved_output = wintypes.DWORD()

    def _enter_input(self):
        kernel32 = self._kernel32
        kernel32.GetConsoleMode(self._input, self._ctypes.byref(self._saved_input))
        kernel32.GetConsoleMode(self._output, self._ctypes.byref(self._saved_output))
        # WINDOW_INPUT | MOUSE_INPUT | EXTENDED_FLAGS(QUICK_EDIT 끔). PROCESSED_INPUT 을 빼서 Ctrl+C 도 키로 받는다.
        kernel32.SetConsoleMode(self._input, 0x0008 | 0x0010 | 0x0080)
        # PROCESSED_OUTPUT | VIRTUAL_TERMINAL_PROCESSING
        kernel32.SetConsoleMode(self._output, self._saved_output.value | 0x0001 | 0x0004)

    def _leave_input(self):
        self._kernel32.SetConsoleMode(self._input, self._saved_input.value)
        self._kernel32.SetConsoleMode(self._output, self._saved_output.value)

    def read(self, timeout):
        ctypes = self._ctypes
        if self._kernel32.WaitForSingleObject(self._input, int(timeout * 1000)) != 0:
            return []
        records = (self._record_type * 64)()
        count = self._wintypes.DWORD()
        if not self._kernel32.ReadConsoleInputW(self._input, records, 64, ctypes.byref(count)):
            return []
        events = []
        for record in records[:count.value]:
            event = self._to_event(record)
            if event:
                events.append(event)
        return events

    def _to_event(self, record):
        data = bytes(record.Event)
        if record.EventType == self._KEY_EVENT:
            key_down = int.from_bytes(data[0:4], "little", signed=True)
            if not key_down:
                return None
            virtual_key = int.from_bytes(data[6:8], "little")
            char = data[10:12].decode("utf-16-le")
            control_state = int.from_bytes(data[12:16], "little")
            if control_state & 0x000C and virtual_key == 0x43:  # Ctrl+C
                return Event("key", key="ctrl+c")
            if virtual_key in self._VIRTUAL_KEYS:
                return Event("key", key=self._VIRTUAL_KEYS[virtual_key])
            if char and char != "\x00":
                return Event("key", key=char)
            return None
        if record.EventType == self._MOUSE_EVENT:
            x = int.from_bytes(data[0:2], "little", signed=True)
            y = int.from_bytes(data[2:4], "little", signed=True)
            button_state = int.from_bytes(data[4:8], "little", signed=True)
            flags = int.from_bytes(data[12:16], "little")
            # dwEventFlags: 0 = 버튼 누름/뗌, 1 = 이동, 2 = 더블클릭, 4 = 휠
            if flags == 0 and button_state & 0x0001:
                return Event("mouse", mouse="down", x=x, y=y)
            if flags == 2:
                return Event("mouse", mouse="double", x=x, y=y)
            if flags == 4:
                return Event("mouse", mouse="wheeldown" if button_state < 0 else "wheelup", x=x, y=y)
            return None
        if record.EventType == self._WINDOW_BUFFER_SIZE_EVENT:
            return Event("resize")
        return None


# ---------------------------------------------------------------- Unix


class _UnixTerminal(_Screen):
    _SEQUENCES = {
        "[A": "up", "[B": "down", "[H": "home", "[F": "end",
        "OA": "up", "OB": "down", "OH": "home", "OF": "end",
        "[1~": "home", "[4~": "end", "[7~": "home", "[8~": "end",
    }

    def __init__(self):
        self._fd = sys.stdin.fileno()
        self._saved = None
        self._buffer = ""
        self._last_click = (0.0, -1, -1)
        self._resized = False

    def _enter_input(self):
        import signal
        import termios
        import tty

        self._saved = termios.tcgetattr(self._fd)
        tty.setraw(self._fd)
        signal.signal(signal.SIGWINCH, self._on_resize)
        # 버튼 누름/뗌 보고(1000) + SGR 좌표 형식(1006)
        write(f"{ESC}[?1000h{ESC}[?1006h")

    def _leave_input(self):
        import termios

        write(f"{ESC}[?1006l{ESC}[?1000l")
        if self._saved is not None:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)

    def _on_resize(self, *_args):
        self._resized = True

    def read(self, timeout):
        import select

        events = []
        if self._resized:
            self._resized = False
            events.append(Event("resize"))
        # SIGWINCH 가 와도 Python 3.5+ 는 select 를 자동으로 다시 실행한다(PEP 475).
        # 크기 변경은 핸들러가 세운 _resized 로 다음 read 때 알린다.
        ready, _, _ = select.select([self._fd], [], [], timeout)
        if ready:
            self._buffer += os.read(self._fd, 4096).decode("utf-8", errors="replace")
        events += self._parse()
        return events

    def _parse(self):
        events = []
        while self._buffer:
            consumed, event = self._parse_one(self._buffer)
            if consumed == 0:
                break  # 시퀀스가 아직 덜 들어옴
            self._buffer = self._buffer[consumed:]
            if event:
                events.append(event)
        return events

    def _parse_one(self, text):
        """(소비한 글자 수, Event 또는 None). 덜 들어온 시퀀스면 (0, None)."""
        first = text[0]
        if first != ESC:
            if first in "\r\n":
                return 1, Event("key", key="enter")
            if first == "\x03":
                return 1, Event("key", key="ctrl+c")
            if first in "\x08\x7f":
                return 1, Event("key", key="backspace")
            if first.isprintable():
                return 1, Event("key", key=first)
            return 1, None
        if len(text) == 1:
            return 1, Event("key", key="esc")  # ESC 단독
        if text.startswith(f"{ESC}[<"):
            return self._parse_mouse(text)
        for sequence, key in self._SEQUENCES.items():
            if text[1:].startswith(sequence):
                return 1 + len(sequence), Event("key", key=key)
        # 모르는 CSI/SS3 시퀀스는 끝 글자까지 버린다.
        if text[1] in "[O":
            for index in range(2, len(text)):
                if "@" <= text[index] <= "~":
                    return index + 1, None
            return 0, None
        return 1, Event("key", key="esc")

    def _parse_mouse(self, text):
        # ESC [ < button ; x ; y (M = 누름 | m = 뗌), 좌표는 1 부터
        end = next((index for index in range(3, len(text)) if text[index] in "Mm"), -1)
        if end < 0:
            return 0, None
        try:
            button, x, y = (int(part) for part in text[3:end].split(";"))
        except ValueError:
            return end + 1, None
        if text[end] == "m":
            return end + 1, None
        x, y = x - 1, y - 1
        if button == 64:
            return end + 1, Event("mouse", mouse="wheelup", x=x, y=y)
        if button == 65:
            return end + 1, Event("mouse", mouse="wheeldown", x=x, y=y)
        if button & 0b11 != 0:  # 왼쪽 버튼만
            return end + 1, None
        now = time.monotonic()
        last_time, last_x, last_y = self._last_click
        if now - last_time < DOUBLE_CLICK_SECONDS and (x, y) == (last_x, last_y):
            self._last_click = (0.0, -1, -1)
            return end + 1, Event("mouse", mouse="double", x=x, y=y)
        self._last_click = (now, x, y)
        return end + 1, Event("mouse", mouse="down", x=x, y=y)
