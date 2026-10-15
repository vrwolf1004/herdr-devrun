"""herdr-devrun 대시보드. 서비스 목록·상태·로그 미리보기와 클릭 가능한 버튼을 그린다.

herdr 플러그인 pane(entrypoint "panel" / "panel-windows")으로 실행되며, 프로젝트 폴더는
DEVRUN_PROJECT 로 받는다. 수동 실행/테스트 시에는 --dir 로 지정한다.

  키    : ↑↓ 선택, Enter 시작/중지, r 재시작, a 전체 시작, x 전체 중지, o 브라우저, e 설정, q/Esc 닫기
  마우스: 행 클릭 선택, 행 더블클릭 시작/중지, 버튼 클릭, 휠 선택 이동
"""

import argparse
import os
import subprocess
import sys
import time
import unicodedata
import webbrowser
from pathlib import Path

import core
import procs
import term
from core import Status

REFRESH_SECONDS = 1.0
INPUT_WAIT_SECONDS = 0.15
MESSAGE_SECONDS = 5
ESC = term.ESC

# 상태 → (아이콘, 이름, 색 SGR). 모든 Status 를 빠짐없이 적는다 (아래 검사로 누락을 막는다).
STATUS_VIEW = {
    Status.RUNNING: ("●", "실행 중", "32"),
    Status.STARTING: ("◐", "시작 중", "33"),
    Status.EXITED: ("✕", "종료됨", "31"),
    Status.STOPPED: ("○", "중지", "90"),
    Status.WORKING: ("…", "처리 중", "36"),
}
assert set(STATUS_VIEW) == set(Status), "STATUS_VIEW 에 빠진 Status 가 있습니다."

FOOTER_HELP = " ↑↓ 선택 · Enter 시작/중지 · r 재시작 · a/x 전체 시작/중지 · o 브라우저 · e 설정 · q 닫기"
KEY_COMMANDS = {"enter": "toggle", "esc": "quit", "ctrl+c": "quit",
                "r": "restart", "a": "start_all", "x": "stop_all", "o": "browser", "e": "config", "q": "quit"}

# ---------------------------------------------------------------- 글자 폭


def char_width(char):
    """한글·CJK·전각 문자는 터미널에서 2칸을 차지한다."""
    return 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1


def text_width(text):
    return sum(char_width(char) for char in text)


def fit(text, width):
    """폭에 맞춰 자르고(…) 남는 칸은 공백으로 채운다."""
    if width <= 0:
        return ""
    clean = "".join(char for char in text.replace("\t", "    ") if char.isprintable())
    if text_width(clean) <= width:
        return clean + " " * (width - text_width(clean))
    result, used = [], 0
    for char in clean:
        if used + char_width(char) > width - 1:
            break
        result.append(char)
        used += char_width(char)
    return "".join(result) + "…" + " " * (width - 1 - used)


def style(text, sgr):
    return f"{ESC}[{sgr}m{text}{ESC}[0m"


# ---------------------------------------------------------------- 대시보드


class Panel:
    def __init__(self, config_path, terminal):
        self.terminal = terminal
        self.config_path = config_path
        self.project_dir = config_path.parent
        self.config = None
        self.config_mtime = None
        self.services = []
        self.statuses = {}
        self.state = None
        self.log_lines = []
        self.selected = 0
        self.message = ""
        self.message_at = 0.0
        self.rows = {}      # 화면 y → 서비스 index
        self.buttons = []   # (y, x1, x2, 명령 id)
        self.last_refresh = 0.0
        self.running = True

    # ------------------------------------------------------------ 상태

    def set_message(self, text):
        self.message = text
        self.message_at = time.monotonic()

    def selected_service(self):
        return self.services[self.selected] if self.services else None

    def reload_config(self):
        """설정 파일이 바뀌었으면 다시 읽는다. 읽기 실패는 이전 설정을 유지하고 메시지로만 알린다."""
        mtime = self.config_path.stat().st_mtime
        if self.config is not None and mtime == self.config_mtime:
            return
        is_reload = self.config is not None
        self.config_mtime = mtime
        try:
            self.config = core.read_config(self.config_path)
        except core.DevrunError as error:
            self.set_message(f"설정 오류: {error}")
            return
        self.services = self.config["services"]
        self.selected = min(self.selected, max(0, len(self.services) - 1))
        if is_reload:
            self.set_message("설정을 다시 읽었습니다.")

    def refresh(self):
        self.reload_config()
        self.state = core.live_state(self.project_dir, core.live_pane_ids())
        child_map = procs.child_process_map() if self.state else {}
        for service in self.services:
            self.statuses[service["name"]] = core.service_status(service, self.state, child_map)
        service = self.selected_service()
        _, height = term.size()
        log_height = max(3, height - len(self.services) - 9)
        self.log_lines = core.service_log(self.state, service["name"], log_height) if service else []
        self.last_refresh = time.monotonic()

    # ------------------------------------------------------------ 그리기

    def button_specs(self):
        service = self.selected_service()
        status = self.statuses.get(service["name"], Status.STOPPED) if service else Status.STOPPED
        toggle = ("start", " ▶ 시작 ", "97;48;5;28") if status == Status.STOPPED else ("stop", " ■ 중지 ", "97;48;5;124")
        return [
            toggle,
            ("restart", " ↻ 재시작 ", "97;48;5;24"),
            ("start_all", " 전체 시작 ", "97;48;5;239"),
            ("stop_all", " 전체 중지 ", "97;48;5;239"),
            ("browser", " 브라우저 ", "97;48;5;239"),
            ("config", " 설정 ", "97;48;5;239"),
            ("quit", " 닫기 ", "97;48;5;239"),
        ]

    def draw(self):
        width, height = term.size()
        width, height = max(20, width), max(10, height)
        lines = []
        self.rows = {}
        self.buttons = []

        # 제목 줄
        running = sum(1 for service in self.services if self.statuses.get(service["name"]) == Status.RUNNING)
        label = core.tab_label(self.project_dir, self.config) if self.config else self.project_dir.name
        right = f" {running}/{len(self.services)} 실행 "
        lines.append(style(fit(f" ▣ devrun · {label}", width - text_width(right)), "1;97;48;5;25")
                     + style(right, "97;48;5;25"))
        lines.append("")

        # 서비스 목록
        name_width = max(6, width - 3 - 11 - 8)
        lines.append(style(fit("   상태       서비스", width - 8), "90") + style(fit("포트", 8), "90"))
        for index, service in enumerate(self.services):
            icon, status_label, color = STATUS_VIEW[self.statuses.get(service["name"], Status.STOPPED)]
            selected = index == self.selected
            background = ";48;5;236" if selected else ""
            port = f":{service['port']}" if service.get("port") else ""
            self.rows[len(lines)] = index
            lines.append(
                style(" ▸ " if selected else "   ", f"1;96{background}")
                + style(fit(f"{icon} {status_label}", 11), f"{color}{background}")
                + style(fit(service["name"], name_width), f"{'1;97' if selected else '97'}{background}")
                + style(fit(port, 8), f"90{background}")
            )
        lines.append("")

        # 버튼 (폭이 모자라면 다음 줄로)
        line, x = " ", 1
        for command, text, sgr in self.button_specs():
            button_width = text_width(text)
            if x + button_width > width:
                lines.append(line)
                line, x = " ", 1
            self.buttons.append((len(lines), x, x + button_width - 1, command))
            line += style(text, sgr) + " "
            x += button_width + 1
        lines.append(line)
        lines.append("")

        # 로그 미리보기
        service = self.selected_service()
        log_title = f"─ 로그 · {service['name']} " if service else "─ 로그 "
        lines.append(style(log_title + "─" * max(0, width - text_width(log_title)), "90"))
        log_height = max(0, height - len(lines) - 1)
        log_lines = self.log_lines[-log_height:] if log_height else []
        for log_line in log_lines or ["(실행 중이 아닙니다)"]:
            lines.append(style(fit(f" {log_line}", width), "37"))
        while len(lines) < height - 1:
            lines.append("")

        # 아래 안내 줄: 최근 메시지는 MESSAGE_SECONDS 동안, 그 외에는 키 안내
        if self.message and time.monotonic() - self.message_at < MESSAGE_SECONDS:
            lines.append(style(fit(f" {self.message}", width), "1;93"))
        else:
            lines.append(style(fit(FOOTER_HELP, width), "90"))

        frame = f"{ESC}[H" + "\r\n".join(f"{line}{ESC}[0m{ESC}[K" for line in lines[:height])
        term.write(frame)

    # ------------------------------------------------------------ 동작

    def busy(self, message, names, work):
        """오래 걸리는 동작 전에 상태를 '처리 중'으로 바꿔 먼저 그린다."""
        for name in names:
            self.statuses[name] = Status.WORKING
        self.set_message(message)
        self.draw()
        work()
        self.refresh()

    def execute(self, command):
        service = self.selected_service()
        all_names = [each["name"] for each in self.services]
        if command == "toggle":
            if service:
                self.execute("start" if self.statuses.get(service["name"]) == Status.STOPPED else "stop")
        elif command == "start":
            if service:
                self.busy(f"{service['name']} 시작 중…", [service["name"]],
                          lambda: core.start_service(self.project_dir, self.config, service))
                self.set_message(f"{service['name']} 시작")
        elif command == "stop":
            if service:
                self.busy(f"{service['name']} 중지 중…", [service["name"]],
                          lambda: core.stop_service(self.project_dir, service["name"]))
                self.set_message(f"{service['name']} 중지")
        elif command == "restart":
            if service:
                self.busy(f"{service['name']} 재시작 중…", [service["name"]],
                          lambda: core.restart_service(self.project_dir, self.config, service))
                self.set_message(f"{service['name']} 재시작")
        elif command == "start_all":
            self.busy("전체 시작 중…", all_names, self._start_all)
            self.set_message("전체 시작")
        elif command == "stop_all":
            self.busy("전체 중지 중…", all_names, lambda: core.down(self.project_dir, quiet=True))
            self.set_message("전체 중지")
        elif command == "browser":
            self.open_browser(service)
        elif command == "config":
            self.open_config()
        elif command == "quit":
            self.running = False
        else:
            raise core.DevrunError(f"알 수 없는 명령: {command}")

    def _start_all(self):
        for service in self.services:
            core.start_service(self.project_dir, self.config, service)

    def open_browser(self, service):
        if not service or not service.get("url"):
            self.set_message("이 서비스에는 url 이 없습니다 (.herdr-devrun.json 의 url).")
            return
        webbrowser.open(service["url"])
        self.set_message(f"{service['url']} 열기")

    def open_config(self):
        """OS 기본 프로그램으로 연다. Windows 에서 .json 연결 프로그램이 없으면 메모장."""
        path = str(self.config_path)
        if core.IS_WINDOWS:
            try:
                os.startfile(path)
            except OSError:
                subprocess.Popen(["notepad.exe", path])
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.Popen([opener, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.set_message("설정 파일을 열었습니다. 저장하면 자동으로 다시 읽습니다.")

    def move_selection(self, delta):
        if not self.services:
            return
        selected = min(max(0, self.selected + delta), len(self.services) - 1)
        if selected != self.selected:
            self.selected = selected
            self.refresh()

    def button_at(self, x, y):
        return next((command for row, x1, x2, command in self.buttons if row == y and x1 <= x <= x2), None)

    def command_for(self, event):
        """입력 이벤트를 명령 id 로 바꾼다. 선택 이동처럼 바로 끝나는 것은 여기서 처리하고 None."""
        if event.kind == "key":
            if event.key in ("up", "down", "home", "end"):
                deltas = {"up": -1, "down": 1, "home": -len(self.services), "end": len(self.services)}
                self.move_selection(deltas[event.key])
                return None
            return KEY_COMMANDS.get(event.key.lower() if len(event.key) == 1 else event.key)
        if event.kind == "mouse":
            if event.mouse in ("wheelup", "wheeldown"):
                self.move_selection(-1 if event.mouse == "wheelup" else 1)
                return None
            if event.mouse == "down":
                button = self.button_at(event.x, event.y)
                if button:
                    return button
                if event.y in self.rows:
                    self.selected = self.rows[event.y]
                    self.refresh()
                return None
            if event.mouse == "double" and event.y in self.rows:
                self.selected = self.rows[event.y]
                return "toggle"
            return None
        if event.kind == "resize":
            term.write(f"{ESC}[2J")
        return None

    def loop(self):
        self.refresh()
        self.draw()
        while self.running:
            dirty = False
            for event in self.terminal.read(INPUT_WAIT_SECONDS):
                dirty = True
                command = self.command_for(event)
                if not command:
                    continue
                try:
                    self.execute(command)
                except core.DevrunError as error:
                    self.set_message(f"오류: {error}")
                if not self.running:
                    break
            if time.monotonic() - self.last_refresh >= REFRESH_SECONDS:
                try:
                    self.refresh()
                except core.DevrunError as error:
                    self.set_message(f"상태 조회 오류: {error}")
                dirty = True
            if dirty and self.running:
                self.draw()


def main():
    parser = argparse.ArgumentParser(prog="devrun-panel")
    parser.add_argument("--dir", help="프로젝트 폴더 (기본: DEVRUN_PROJECT)")
    args = parser.parse_args()
    start = args.dir or os.environ.get("DEVRUN_PROJECT")
    if not start:
        print("DEVRUN_PROJECT 또는 --dir 가 필요합니다.", file=sys.stderr)
        return 1
    try:
        config_path = core.find_config_path(Path(start).resolve())
    except core.DevrunError as error:
        print(error, file=sys.stderr)
        return 1

    terminal = term.open_terminal()
    with terminal:
        Panel(config_path, terminal).loop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
