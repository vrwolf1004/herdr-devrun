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
import traceback
import unicodedata
import webbrowser
from pathlib import Path

import core
import procs
import term
from core import Status
from i18n import t

REFRESH_SECONDS = 1.0
INPUT_WAIT_SECONDS = 0.15
MESSAGE_SECONDS = 5
MIN_LOG_LINES = 3
ESC = term.ESC

# 상태 → (아이콘, 번역 키, 색 SGR). 모든 Status 를 빠짐없이 적는다 (아래 검사로 누락을 막는다).
STATUS_VIEW = {
    Status.RUNNING: ("●", "status.running", "32"),
    Status.STARTING: ("◐", "status.starting", "33"),
    Status.EXITED: ("✕", "status.exited", "31"),
    Status.STOPPED: ("○", "status.stopped", "90"),
    Status.WORKING: ("…", "status.working", "36"),
    Status.WAITING: ("◔", "status.waiting", "35"),
}
assert set(STATUS_VIEW) == set(Status), "STATUS_VIEW is missing a Status"

KEY_COMMANDS = {"enter": "toggle", "esc": "quit", "ctrl+c": "quit",
                "r": "restart", "a": "start_all", "x": "stop_all", "o": "browser", "e": "config", "q": "quit"}
# 한/영 상태가 한글이면 같은 자리의 두벌식 자모가 들어오므로 영문 키로 바꿔 받는다.
HANGUL_KEYS = {"ㄱ": "r", "ㅁ": "a", "ㅌ": "x", "ㅐ": "o", "ㄷ": "e", "ㅂ": "q"}
LOG_NAME = "panel.log"
LOG_MAX_BYTES = 64 * 1024

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
        self.scroll = 0         # 서비스 목록에서 화면 맨 위에 보이는 index
        self.message = ""
        self.message_at = 0.0
        self.rows = {}          # 화면 y → 서비스 index
        self.buttons = []       # (y, x1, x2, 명령 id)
        self.pid_cache = {}     # pane id → 셸 pid (pane 이 살아 있는 동안 바뀌지 않는다)
        self.plan = None        # 진행 중인 전체 시작 (core.StartPlan)
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
            self.set_message(t("panel.config_error", error=error))
            return
        self.services = self.config["services"]
        self.selected = min(self.selected, max(0, len(self.services) - 1))
        if is_reload:
            self.set_message(t("panel.config_reloaded"))

    def refresh(self):
        self.reload_config()
        alive = core.live_pane_ids()
        self.pid_cache = {pane_id: pid for pane_id, pid in self.pid_cache.items() if pane_id in alive}
        self.state = core.live_state(self.project_dir, alive)
        child_map = procs.child_process_map() if self.state else {}
        waiting = self.plan.waiting_names() if self.plan else set()
        for service in self.services:
            status = core.service_status(service, self.state, child_map, self.pid_cache)
            if status == Status.STOPPED and service["name"] in waiting:
                status = Status.WAITING
            self.statuses[service["name"]] = status
        self.reload_log()
        self.last_refresh = time.monotonic()

    def reload_log(self):
        service = self.selected_service()
        _, height = term.size()
        self.log_lines = core.service_log(self.state, service["name"], max(MIN_LOG_LINES, height)) if service else []

    def advance_plan(self):
        """전체 시작을 한 단계 진행한다. 다 끝나면 결과를 메시지로 보여 준다."""
        if not self.plan:
            return
        self.plan.step(self.pid_cache)
        if self.plan.done:
            if self.plan.failed:
                self.set_message(t("panel.started_all_partial", details=self.plan.failure_text()))
            else:
                self.set_message(t("panel.started_all"))
            self.plan = None

    # ------------------------------------------------------------ 그리기

    def button_specs(self):
        service = self.selected_service()
        status = self.statuses.get(service["name"], Status.STOPPED) if service else Status.STOPPED
        toggle = ("start", "97;48;5;28") if status in (Status.STOPPED, Status.WAITING) else ("stop", "97;48;5;124")
        specs = [
            toggle,
            ("restart", "97;48;5;24"),
            ("start_all", "97;48;5;239"),
            ("stop_all", "97;48;5;239"),
            ("browser", "97;48;5;239"),
            ("config", "97;48;5;239"),
            ("quit", "97;48;5;239"),
        ]
        return [(command, f" {t('panel.button.' + command)} ", sgr) for command, sgr in specs]

    def layout_buttons(self, width):
        """버튼을 폭에 맞춰 줄로 나눈다. [(줄 문자열, [(x1, x2, 명령)])]"""
        rows, line, spans, x = [], " ", [], 1
        for command, text, sgr in self.button_specs():
            if text_width(text) > width - 2:  # 버튼 하나가 폭보다 넓으면 버튼 글자를 자른다 (앞뒤 공백 두 칸)
                text = fit(text, max(1, width - 2))
            button_width = text_width(text)
            if spans and x + button_width + 1 > width:  # 버튼 뒤 공백 한 칸까지 들어가야 한다
                rows.append((line, spans))
                line, spans, x = " ", [], 1
            spans.append((x, x + button_width - 1, command))
            line += style(text, sgr) + " "
            x += button_width + 1
        rows.append((line, spans))
        return rows

    def column_widths(self, width):
        """(상태 열, 서비스 열, 포트 열). 좁으면 포트 열을 숨기고, 더 좁으면 상태를 아이콘만 보인다."""
        port_width = max(8, text_width(t("panel.header.port")) + 2) if width >= 40 else 0
        if width >= 30:
            status_width = max(text_width(f"{icon} {t(key)}") for icon, key, _ in STATUS_VIEW.values()) + 2
        else:
            status_width = 2
        name_width = max(1, width - 3 - status_width - port_width)
        return status_width, name_width, port_width

    def visible_range(self, capacity):
        """목록에 보일 (시작 index, 개수, 위아래 표시 줄을 쓰는지). 선택한 행이 항상 보이게 scroll 을 맞춘다."""
        total = len(self.services)
        if total <= capacity:
            self.scroll = 0
            return 0, total, False
        count = max(1, capacity - 2)  # ▲ / ▼ 표시 줄 두 개
        if self.selected < self.scroll:
            self.scroll = self.selected
        elif self.selected >= self.scroll + count:
            self.scroll = self.selected - count + 1
        self.scroll = max(0, min(self.scroll, total - count))
        return self.scroll, count, True

    def draw(self):
        width, height = term.size()
        width, height = max(10, width), max(8, height)
        lines = []
        self.rows = {}
        self.buttons = []
        button_rows = self.layout_buttons(width)

        # 제목 줄 (오른쪽 실행 수는 폭이 모자라면 뺀다)
        running = sum(1 for service in self.services if self.statuses.get(service["name"]) == Status.RUNNING)
        label = core.tab_label(self.project_dir, self.config) if self.config else self.project_dir.name
        right = f" {t('panel.running_count', running=running, total=len(self.services))} "
        if text_width(right) > width // 2:
            right = ""
        lines.append(style(fit(f" ▣ devrun · {label}", width - text_width(right)), "1;97;48;5;25")
                     + style(right, "97;48;5;25"))
        lines.append("")

        # 서비스 목록. 열 폭은 언어마다 단어 길이가 달라 그때그때 계산한다.
        status_width, name_width, port_width = self.column_widths(width)
        header = "   " + fit(t("panel.header.status") if status_width > 2 else "", status_width) \
            + fit(t("panel.header.service"), name_width)
        lines.append(style(header, "90") + style(fit(t("panel.header.port"), port_width), "90"))

        # 고정 줄: 제목·빈 줄·머리글(3) + 목록 뒤 빈 줄(1) + 버튼 + 빈 줄(1) + 로그 제목(1) + 안내 줄(1)
        fixed = 3 + 1 + len(button_rows) + 1 + 1 + 1
        start, count, indicators = self.visible_range(max(1, height - fixed - MIN_LOG_LINES))
        if indicators:
            above = t("panel.more_above", count=start) if start else ""
            lines.append(style(fit(f"   {above}", width), "90"))
        for index in range(start, start + count):
            service = self.services[index]
            icon, label_key, color = STATUS_VIEW[self.statuses.get(service["name"], Status.STOPPED)]
            selected = index == self.selected
            background = ";48;5;236" if selected else ""
            status_text = f"{icon} {t(label_key)}" if status_width > 2 else icon
            port = f":{service['port']}" if service.get("port") else ""
            self.rows[len(lines)] = index
            lines.append(
                style(" ▸ " if selected else "   ", f"1;96{background}")
                + style(fit(status_text, status_width), f"{color}{background}")
                + style(fit(service["name"], name_width), f"{'1;97' if selected else '97'}{background}")
                + style(fit(port, port_width), f"90{background}")
            )
        if indicators:
            below = len(self.services) - start - count
            lines.append(style(fit(f"   {t('panel.more_below', count=below) if below else ''}", width), "90"))
        lines.append("")

        # 버튼
        for line, spans in button_rows:
            self.buttons += [(len(lines), x1, x2, command) for x1, x2, command in spans]
            lines.append(line)
        lines.append("")

        # 로그 미리보기 (원래 한 줄인 로그를 대시보드 폭에 맞춰 자른다)
        service = self.selected_service()
        log_title = f"─ {t('panel.log_title', name=service['name']) if service else t('panel.log_title_empty')} "
        lines.append(style(fit(log_title + "─" * max(0, width - text_width(log_title)), width), "90"))
        log_height = max(0, height - len(lines) - 1)
        log_lines = self.log_lines[-log_height:] if log_height else []
        for log_line in log_lines or [t("panel.not_running")]:
            lines.append(style(fit(f" {log_line}", width), "37"))
        while len(lines) < height - 1:
            lines.append("")

        # 아래 안내 줄: 최근 메시지는 MESSAGE_SECONDS 동안, 그 외에는 키 안내
        if self.message and time.monotonic() - self.message_at < MESSAGE_SECONDS:
            lines.append(style(fit(f" {self.message}", width), "1;93"))
        else:
            lines.append(style(fit(f" {t('panel.footer')}", width), "90"))

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
                stopped = self.statuses.get(service["name"]) in (Status.STOPPED, Status.WAITING)
                self.execute("start" if stopped else "stop")
        elif command == "start":
            # 하나만 시작할 때는 depends_on 을 기다리지 않는다 (사용자가 직접 고른 것이므로)
            if service:
                self.busy(t("panel.starting", name=service["name"]), [service["name"]],
                          lambda: core.start_service(self.project_dir, self.config, service))
                self.set_message(t("panel.started", name=service["name"]))
        elif command == "stop":
            if service:
                self.busy(t("panel.stopping", name=service["name"]), [service["name"]],
                          lambda: core.stop_service(self.project_dir, service["name"], core.stop_timeout(service)))
                self.set_message(t("panel.stopped", name=service["name"]))
        elif command == "restart":
            if service:
                self.busy(t("panel.restarting", name=service["name"]), [service["name"]],
                          lambda: core.restart_service(self.project_dir, self.config, service))
                self.set_message(t("panel.restarted", name=service["name"]))
        elif command == "start_all":
            # 기다리는 동안에도 입력·갱신이 되도록 루프에서 한 단계씩 진행한다 (advance_plan)
            self.plan = core.StartPlan(self.project_dir, self.config)
            self.set_message(t("panel.starting_all"))
            self.advance_plan()
            self.refresh()
        elif command == "stop_all":
            if self.plan:
                self.plan.cancel()
                self.plan = None
            self.busy(t("panel.stopping_all"), all_names,
                      lambda: core.down(self.project_dir, quiet=True, config=self.config))
            self.set_message(t("panel.stopped_all"))
        elif command == "browser":
            self.open_browser(service)
        elif command == "config":
            self.open_config()
        elif command == "quit":
            self.running = False
        else:
            raise core.DevrunError(t("error.unknown_command", command=command))

    def open_browser(self, service):
        if not service or not service.get("url"):
            self.set_message(t("panel.no_url"))
            return
        webbrowser.open(service["url"])
        self.set_message(t("panel.opened_url", url=service["url"]))

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
        self.set_message(t("panel.opened_config"))

    def select(self, index):
        """선택만 바꾸고 로그만 다시 읽는다. 상태는 주기 갱신에 맡겨 선택이 바로 따라오게 한다."""
        if not self.services:
            return
        index = min(max(0, index), len(self.services) - 1)
        if index != self.selected:
            self.selected = index
            self.reload_log()

    def button_at(self, x, y):
        return next((command for row, x1, x2, command in self.buttons if row == y and x1 <= x <= x2), None)

    def command_for(self, event):
        """입력 이벤트를 명령 id 로 바꾼다. 선택 이동처럼 바로 끝나는 것은 여기서 처리하고 None."""
        if event.kind == "key":
            if event.key in ("up", "down", "home", "end"):
                targets = {"up": self.selected - 1, "down": self.selected + 1,
                           "home": 0, "end": len(self.services) - 1}
                self.select(targets[event.key])
                return None
            key = HANGUL_KEYS.get(event.key, event.key)
            return KEY_COMMANDS.get(key.lower() if len(key) == 1 else key)
        if event.kind == "mouse":
            if event.mouse in ("wheelup", "wheeldown"):
                self.select(self.selected + (-1 if event.mouse == "wheelup" else 1))
                return None
            if event.mouse == "down":
                button = self.button_at(event.x, event.y)
                if button:
                    return button
                if event.y in self.rows:
                    self.select(self.rows[event.y])
                return None
            if event.mouse == "double" and event.y in self.rows:
                self.select(self.rows[event.y])
                return "toggle"
            return None
        if event.kind == "resize":
            term.write(f"{ESC}[2J")
        return None

    def guarded(self, work, *args, message_key):
        """예외가 나도 대시보드는 계속 돈다. 예상한 오류는 메시지만, 예상 못 한 오류는 panel.log 에도 남긴다."""
        try:
            return work(*args)
        except core.DevrunError as error:
            self.set_message(t(message_key, error=error))
        except Exception as error:  # 대시보드를 살려 두기 위한 마지막 안전망
            log_path = write_crash_log()
            self.set_message(t("panel.unexpected_error", error=f"{type(error).__name__}: {error}", log=log_path))
        return None

    def loop(self):
        self.guarded(self.refresh, message_key="panel.refresh_error")
        self.draw()
        while self.running:
            dirty = False
            for event in self.terminal.read(INPUT_WAIT_SECONDS):
                dirty = True
                command = self.guarded(self.command_for, event, message_key="panel.error")
                if not command:
                    continue
                self.guarded(self.execute, command, message_key="panel.error")
                if not self.running:
                    break
            if time.monotonic() - self.last_refresh >= REFRESH_SECONDS:
                # 실패해도 같은 오류로 매 루프 다시 시도하지 않도록 시각부터 갱신한다.
                self.last_refresh = time.monotonic()
                self.guarded(self.advance_plan, message_key="panel.error")
                self.guarded(self.refresh, message_key="panel.refresh_error")
                dirty = True
            if dirty and self.running:
                self.draw()


def main():
    parser = argparse.ArgumentParser(prog="devrun-panel")
    parser.add_argument("--dir", help=t("cli.panel_dir_help"))
    args = parser.parse_args()
    start = args.dir or os.environ.get("DEVRUN_PROJECT")
    if not start:
        print(t("cli.panel_dir_required"), file=sys.stderr)
        return 1
    try:
        config_path = core.find_config_path(Path(start).resolve())
    except core.DevrunError as error:
        print(error, file=sys.stderr)
        return 1

    terminal = term.open_terminal()
    try:
        with terminal:
            Panel(config_path, terminal).loop()
    except Exception:  # 루프 밖(화면 준비·그리기)에서 난 예외. pane 이 닫히기 전에 원인을 남긴다.
        log_path = write_crash_log()
        core.notify(t("notice.error_title"), t("notice.panel_crashed", log=log_path))
        print(traceback.format_exc(), file=sys.stderr)
        return 1
    return 0


def write_crash_log():
    """현재 처리 중인 예외의 traceback 을 상태 폴더의 panel.log 에 덧붙이고 경로를 돌려준다.

    파일이 LOG_MAX_BYTES 를 넘으면 뒤쪽 절반만 남긴다.
    """
    path = core.state_dir() / LOG_NAME
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]\n{traceback.format_exc()}\n"
        previous = path.read_text(encoding="utf-8") if path.exists() else ""
        if len(previous.encode("utf-8")) > LOG_MAX_BYTES:
            previous = previous[len(previous) // 2:]
        path.write_text(previous + entry, encoding="utf-8")
    except OSError:
        pass  # 기록 실패가 대시보드를 멈추게 하지 않는다
    return path


if __name__ == "__main__":
    sys.exit(main())
