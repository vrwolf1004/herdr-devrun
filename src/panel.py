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
import devrun
import presets
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
HANGUL_KEYS = {"ㄱ": "r", "ㅁ": "a", "ㅌ": "x", "ㅐ": "o", "ㄷ": "e", "ㅂ": "q", "ㅛ": "y", "ㅜ": "n"}
DIALOG_BOX_HEIGHT = 7  # 확인 알림 창의 높이 (테두리 포함)
DIALOG_BOX_WIDTH = 52
# 서비스 줄 끝 버튼: (명령 id, 글자 키). 시작/중지는 상태에 따라 글자가 바뀐다.
LINE_BUTTON_KEYS = [("toggle", ("start", "stop")), ("edit", ("edit",)), ("delete", ("delete",)),
                    ("close_pane", ("close",))]
LINE_ICONS = {"start": "▶", "stop": "■", "edit": "✎", "delete": "✕", "close": "⊗"}
LINE_STYLES = {"start": "97;48;5;28", "stop": "97;48;5;124", "edit": "97;48;5;239", "delete": "97;48;5;124",
               "close": "97;48;5;239"}
LINE_ICON_ONLY = ("close",)  # 글자가 길어 줄 버튼 폭을 늘리므로 넓은 화면에서도 아이콘만 쓴다
# 확인 창 종류별 문구 키: (제목, 본문, 안내, 확인 버튼, 확인 버튼 색). 제목에는 서비스 이름이 들어간다.
DIALOG_TEXTS = {
    "delete": ("panel.dialog.delete_title", "panel.dialog.delete_body", "panel.dialog.delete_hint",
               "panel.dialog.delete_ok", LINE_STYLES["delete"]),
    "close": ("panel.dialog.close_title", "panel.dialog.close_body", "panel.dialog.close_hint",
              "panel.dialog.close_ok", LINE_STYLES["close"]),
}
LINE_LABEL_MIN_WIDTH = 72  # 이보다 좁으면 서비스 줄 버튼은 아이콘만 쓴다 (글자 버튼 네 개면 이름 열이 좁아진다)
ROW_NAME_MIN = 4           # 줄 버튼을 넣고도 서비스 이름 열이 이만큼은 남아야 버튼을 그린다
LOG_NAME = "panel.log"
LOG_MAX_BYTES = 64 * 1024
CHOICE_FIELDS = ("category", "tech")  # 목록에서 고르는 칸 (↑↓ 선택, Enter 다음)
FORM_FIELDS = ("name", "cwd", "command", "port", "url", "depends_on")
ADD_FIELDS = CHOICE_FIELDS + FORM_FIELDS

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


def line_button_text(key, wide):
    """서비스 줄 버튼 글자: 넓으면 이름, 좁으면 아이콘."""
    return t(f"panel.button.{key}") if wide and key not in LINE_ICON_ONLY else LINE_ICONS[key]


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
        self.buttons = []       # 하단 버튼: (y, x1, x2, 명령 id)
        self.row_buttons = []   # 서비스 줄 버튼: (y, x1, x2, 명령 id, 서비스 index)
        self.pid_cache = {}     # pane id → 셸 pid (pane 이 살아 있는 동안 바뀌지 않는다)
        self.plan = None        # 진행 중인 전체 시작 (core.StartPlan)
        self.dialog = None      # 삭제 확인 알림 창 {"service": 서비스} (떠 있는 동안만)
        self.dialog_box = None  # 그려진 알림 창 (top, left, width): 창 밖 클릭 판정용
        self.dialog_buttons = []  # 알림 창 버튼: (y, x1, x2, 명령 id)
        self.form = None        # 진행 중인 추가·수정·삭제 입력 (start_form)
        self.last_refresh = 0.0
        self.running = True

    # ------------------------------------------------------------ 상태

    def set_message(self, text):
        self.message = text
        self.message_at = time.monotonic()

    def selected_service(self):
        return self.services[self.selected] if self.services else None

    def is_running(self, name):
        return self.statuses.get(name, Status.STOPPED) not in (Status.STOPPED, Status.EXITED)

    def select_name(self, name):
        for index, service in enumerate(self.services):
            if service["name"] == name:
                self.selected = index
                self.reload_log()
                return

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
            self.set_message(self.plan_result_text(self.plan))
            self.plan = None

    def plan_result_text(self, plan):
        """전체 시작이 끝난 뒤의 안내. 실패한 서비스와 이미 실행 중이라 건너뛴 서비스를 구분해서 보인다."""
        if plan.failed:
            text = t("panel.started_all_partial", details=plan.failure_text())
            if plan.skipped:
                text += " · " + t("panel.already_running", names=", ".join(plan.skipped))
            return text
        if plan.skipped:
            return t("panel.started_all_skipped", names=", ".join(plan.skipped))
        return t("panel.started_all")

    # ------------------------------------------------------------ 그리기

    def button_specs(self):
        """하단 버튼 줄: 전체 기능만. 서비스 제어는 각 서비스 줄 끝에 있다."""
        specs = [
            ("start_all", "97;48;5;239"),
            ("stop_all", "97;48;5;239"),
            ("browser", "97;48;5;239"),
            ("config", "97;48;5;239"),
            ("add", "97;48;5;239"),
            ("quit", "97;48;5;239"),
        ]
        return [(command, f" {t('panel.button.' + command)} ", sgr) for command, sgr in specs]

    def layout_buttons(self, width):
        """하단 버튼을 폭에 맞춰 줄로 나눈다. [(줄 문자열, [(x1, x2, 명령)])]"""
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

    def line_button_cells(self, width):
        """서비스 줄 끝 버튼 칸 [(명령, 칸 폭)]. 글자가 바뀌어도 칸이 흔들리지 않도록 가장 긴 글자에 맞춘다."""
        wide = width >= LINE_LABEL_MIN_WIDTH
        return [(command, 2 + max(text_width(line_button_text(key, wide)) for key in keys))
                for command, keys in LINE_BUTTON_KEYS]

    def line_buttons_width(self, width, status_width, port_width):
        """서비스 줄 끝 버튼이 쓰는 폭 (앞 공백 한 칸 포함). 이름 열이 너무 좁아지면 0 으로 버튼을 생략한다."""
        total = 1 + sum(cell for _, cell in self.line_button_cells(width))
        return total if width - 3 - status_width - port_width - total >= ROW_NAME_MIN else 0

    def line_button_parts(self, service, width):
        """서비스 한 줄의 버튼 [(명령, 칸 글자, 색)]."""
        stopped = self.statuses.get(service["name"], Status.STOPPED) in (Status.STOPPED, Status.WAITING)
        keys = {"toggle": "start" if stopped else "stop", "edit": "edit", "delete": "delete", "close_pane": "close"}
        wide = width >= LINE_LABEL_MIN_WIDTH
        return [(command, f" {fit(line_button_text(keys[command], wide), cell - 2)} ", LINE_STYLES[keys[command]])
                for command, cell in self.line_button_cells(width)]

    def column_widths(self, width):
        """(상태 열, 서비스 열, 포트 열). 좁으면 포트 열을 숨기고, 더 좁으면 상태를 아이콘만 보인다.

        서비스 열은 머리글 글자 뒤에 최소 한 칸이 남아야 한다. 그렇지 못하면 포트 열을 먼저 숨겨
        "서비스"와 "포트" 머리글이 붙어 보이지 않게 한다."""
        port_width = max(8, text_width(t("panel.header.port")) + 2) if width >= 40 else 0
        if width >= 30:
            status_width = max(text_width(f"{icon} {t(key)}") for icon, key, _ in STATUS_VIEW.values()) + 2
        else:
            status_width = 2
        buttons_width = self.line_buttons_width(width, status_width, port_width)
        name_width = width - 3 - status_width - port_width - buttons_width
        if port_width and name_width < text_width(t("panel.header.service")) + 1:
            port_width = 0
            buttons_width = self.line_buttons_width(width, status_width, port_width)
            name_width = width - 3 - status_width - buttons_width
        return status_width, max(1, name_width), port_width

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
        self.row_buttons = []
        self.dialog_buttons = []
        self.dialog_box = None
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
        buttons_width = self.line_buttons_width(width, status_width, port_width)
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
            row = (style(" ▸ " if selected else "   ", f"1;96{background}")
                   + style(fit(status_text, status_width), f"{color}{background}")
                   + style(fit(service["name"], name_width), f"{'1;97' if selected else '97'}{background}")
                   + style(fit(port, port_width), f"90{background}"))
            if buttons_width:  # 줄 끝 버튼 (시작/중지 · 수정 · 삭제). 위치는 줄 기준으로 기록한다
                x = 3 + status_width + name_width + port_width + 1
                row += " "
                for command, text, sgr in self.line_button_parts(service, width):
                    row += style(text, sgr)
                    self.row_buttons.append((len(lines), x, x + text_width(text) - 1, command, index))
                    x += text_width(text)
            lines.append(row)
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
        # 입력 폼이 열린 동안 최근 메시지는 안내 줄 위에 한 줄 더 그린다 (검증 실패·차단 이유가 보이게)
        fresh = bool(self.message) and time.monotonic() - self.message_at < MESSAGE_SECONDS
        notice_rows = 1 if self.form and fresh else 0
        log_height = max(0, height - len(lines) - 1 - notice_rows)
        if self.form and self.form_field() in CHOICE_FIELDS:  # 목록에서 고르는 중이면 로그 자리에 선택지를 보인다
            for row, (_, label) in enumerate(self.form_options()[:log_height]):
                selected = row == self.form["cursor"]
                lines.append(style(fit(f" {'▸' if selected else ' '} {label}", width), "1;97" if selected else "37"))
        else:
            log_lines = self.log_lines[-log_height:] if log_height else []
            for log_line in log_lines or [t("panel.not_running")]:
                lines.append(style(fit(f" {log_line}", width), "37"))
        while len(lines) < height - 1 - notice_rows:
            lines.append("")

        # 아래 안내 줄: 입력 중이면 (위에 최근 메시지) 입력 칸, 최근 메시지는 MESSAGE_SECONDS 동안, 그 외에는 키 안내
        if self.form:
            if notice_rows:
                lines.append(style(fit(f" {self.message}", width), "1;93"))
            lines.append(style(fit(f" {self.form_prompt()}", width), "1;96"))
        elif fresh:
            lines.append(style(fit(f" {self.message}", width), "1;93"))
        else:
            lines.append(style(fit(f" {t('panel.footer')}", width), "90"))

        if self.dialog:
            self.draw_dialog(lines, width, height)

        frame = f"{ESC}[H" + "\r\n".join(f"{line}{ESC}[0m{ESC}[K" for line in lines[:height])
        term.write(frame)

    def draw_dialog(self, lines, width, height):
        """확인 알림 창을 화면 가운데에 덮어 그린다. 폭·높이에 맞춰 창 크기를 줄인다."""
        service = self.dialog["service"]
        title_key, body_key, hint_key, ok_key, ok_sgr = DIALOG_TEXTS[self.dialog["kind"]]
        box_width = max(12, min(width - 4, DIALOG_BOX_WIDTH))
        inner = box_width - 2
        top = max(0, (height - DIALOG_BOX_HEIGHT) // 2)
        left = max(0, (width - box_width) // 2)
        plain = {"ok": f" {t(ok_key)} ", "cancel": f" {t('panel.dialog.cancel')} "}
        gap = 4 if inner >= 40 else 2
        if text_width(plain["ok"]) + gap + text_width(plain["cancel"]) > inner:  # 좁으면 버튼 글자를 줄이고 간격을 좁힌다
            gap = 1
            plain["ok"] = fit(plain["ok"], inner // 2)
            plain["cancel"] = fit(plain["cancel"], inner - inner // 2 - gap)
        total = text_width(plain["ok"]) + gap + text_width(plain["cancel"])
        pad = (inner - total) // 2
        trailing = inner - pad - total

        body = [fit(f" {t(title_key, name=service['name'])}", inner),
                fit(f" {t(body_key)}", inner),
                fit(f" {t(hint_key)}", inner),
                " " * inner]
        frame_sgr, fill = "1;97;48;5;237", "48;5;237"
        rows = [style("┌" + "─" * inner + "┐", frame_sgr)]
        rows += [style("│" + text + "│", frame_sgr) for text in body]
        rows.append(style("│", frame_sgr) + style(" " * pad, fill)
                    + style(plain["ok"], ok_sgr) + style(" " * gap, fill)
                    + style(plain["cancel"], "97;48;5;239") + style(" " * trailing, fill) + style("│", frame_sgr))
        rows.append(style("└" + "─" * inner + "┘", frame_sgr))

        button_y = top + 1 + len(body)  # 버튼 줄 (위 테두리 + 본문 줄 수)
        ok_x = left + 1 + pad
        cancel_x = ok_x + text_width(plain["ok"]) + gap
        self.dialog_buttons = [
            (button_y, ok_x, ok_x + text_width(plain["ok"]) - 1, "dialog_confirm"),
            (button_y, cancel_x, cancel_x + text_width(plain["cancel"]) - 1, "dialog_cancel"),
        ]
        self.dialog_box = (top, left, box_width)
        while len(lines) < top + len(rows):
            lines.append("")
        for index, row in enumerate(rows):
            lines[top + index] = " " * left + row + " " * (width - left - box_width)

    # ------------------------------------------------------------ 동작

    def ensure_control_box(self):
        """서비스를 띄우기 전에 컨트롤 박스를 맞춘다 (CLI up 과 같은 규칙). 실패하면 메시지를 남기고 False."""
        try:
            devrun.ensure_control_box(self.project_dir, self.config)
        except core.DevrunError as error:
            self.set_message(t("panel.error", error=error))
            return False
        return True

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
            if service and self.ensure_control_box():
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
            if self.ensure_control_box():
                self.plan = core.StartPlan(self.project_dir, self.config)
                self.set_message(t("panel.starting_all"))
                self.advance_plan()
            self.refresh()
        elif command == "stop_all":
            if self.plan:
                self.plan.cancel()
                self.plan = None
            stopped = []  # busy 안에서 중지 수를 받아 메시지를 고른다
            self.busy(t("panel.stopping_all"), all_names,
                      lambda: stopped.append(core.stop_all_services(self.project_dir, self.config)))
            self.set_message(t("panel.stopped_count", count=stopped[0]) if stopped[0] else t("notice.nothing_running"))
        elif command == "add":
            self.start_form("add")
        elif command == "edit":
            if service:
                self.start_form("edit", service)
        elif command == "delete":
            if service:
                self.open_delete_dialog(service)
        elif command == "close_pane":
            if service:
                self.open_close_dialog(service)
        elif command == "dialog_confirm":
            if self.dialog["kind"] == "close":
                self.confirm_close()
            else:
                self.confirm_delete()
        elif command == "dialog_cancel":
            self.dialog = None
            self.set_message(t("panel.form.cancelled"))
        elif command == "browser":
            self.open_browser(service)
        elif command == "config":
            self.open_config()
        elif command == "quit":
            self.running = False
        else:
            raise core.DevrunError(t("error.unknown_command", command=command))

    # 추가·수정은 항목을 차례로 묻는다. Enter 는 칸의 기본값(대괄호 안)을 받고, "-" 는 값을 비운다.
    # 저장 전에 설정 전체를 검증하므로, 잘못된 값이면 파일은 그대로 두고 입력을 기본값으로 남겨 다시 묻는다.

    def start_form(self, mode, service=None):
        if mode == "add":
            fields = ADD_FIELDS
            defaults = dict(form_defaults(None), category=presets.CATEGORIES[0], tech="")
        else:
            fields, defaults = FORM_FIELDS, form_defaults(service)
        self.form = {"mode": mode, "service": service, "fields": fields, "defaults": defaults,
                     "values": {}, "index": 0, "text": "", "cursor": 0, "preset": None, "applied": None}
        self.start_step()

    def form_field(self):
        return self.form["fields"][self.form["index"]]

    def form_options(self):
        """목록 칸의 선택지 (값, 표시 이름). 기술 목록은 고른 분류의 프리셋이고, 기타는 직접 입력 하나다."""
        field = self.form_field()
        if field == "category":
            return [(each, t("panel.category." + each)) for each in presets.CATEGORIES]
        if field == "tech":
            items = presets.PRESETS[self.form["values"]["category"]]
            return [(each["id"], each["label"]) for each in items] or [("custom", t("panel.preset.custom"))]
        return []

    def start_step(self):
        """다음 칸을 연다. 목록 칸이면 기본값이 있는 항목에 커서를 둔다."""
        form = self.form
        form["text"] = ""
        options = [value for value, _ in self.form_options()]
        default = form["defaults"].get(self.form_field())
        form["cursor"] = options.index(default) if default in options else 0

    def form_prompt(self):
        form = self.form
        field = self.form_field()
        if field in CHOICE_FIELDS:
            _, label = self.form_options()[form["cursor"]]
            return f"{t('panel.field.' + field)}: {label}  {t('panel.form.choice_hint')}"
        default = form["defaults"][field]
        hint = f" [{default}]" if default else ""
        return f"{t('panel.field.' + field)}{hint}: {form['text']}_  {t('panel.form.hint')}"

    def form_input(self, event):
        form = self.form
        if event.key in ("esc", "ctrl+c"):
            self.form = None
            self.set_message(t("panel.form.cancelled"))
        elif event.key == "enter":
            self.form_submit()
        elif self.form_field() in CHOICE_FIELDS:
            if event.key in ("up", "down"):
                step = -1 if event.key == "up" else 1
                form["cursor"] = (form["cursor"] + step) % len(self.form_options())
        elif event.key == "backspace":
            form["text"] = form["text"][:-1]
        elif len(event.key) == 1 and event.key.isprintable():
            form["text"] += event.key

    def form_submit(self):
        form = self.form
        field = self.form_field()
        if field in CHOICE_FIELDS:
            value = self.form_options()[form["cursor"]][0]
            form["values"][field] = value
            if field == "tech":
                self.apply_preset(value)
        else:
            text = form["text"].strip()
            form["values"][field] = "" if text == "-" else (text or form["defaults"][field])
        form["index"] += 1
        if form["index"] == len(form["fields"]):
            self.finish_form()
        else:
            self.start_step()

    def apply_preset(self, tech):
        """기술을 새로 고르면 프리셋의 명령·포트를 기본값으로 채운다. 같은 기술이면 실패 뒤 고쳐 둔 값을 그대로 둔다."""
        form = self.form
        key = (form["values"]["category"], tech)
        if form["applied"] == key:
            return
        form["applied"] = key
        preset = presets.find(*key)
        form["preset"] = preset
        command, port = ("", None) if preset is None else (preset["windows" if core.IS_WINDOWS else "unix"], preset["port"])
        form["defaults"].update(command=command, port="" if port is None else str(port))

    def open_delete_dialog(self, service):
        """삭제는 확인 알림 창으로 묻는다. 실행 중인 서비스는 창 대신 하단 안내 줄에 막는 이유를 보인다."""
        if self.is_running(service["name"]):
            self.set_message(t("panel.form.running_block", name=service["name"]))
            return
        self.dialog = {"kind": "delete", "service": service}

    def open_close_dialog(self, service):
        """서비스 pane 닫기 확인 창. 떠 있는 프로세스는 확인 뒤에 먼저 끈다."""
        self.dialog = {"kind": "close", "service": service}

    def confirm_close(self):
        service = self.dialog["service"]
        self.dialog = None
        core.close_service_pane(self.project_dir, service["name"], core.stop_timeout(service))
        self.refresh()
        self.set_message(t("panel.pane_closed", name=service["name"]))

    def confirm_delete(self):
        service = self.dialog["service"]
        self.dialog = None
        if self.is_running(service["name"]):  # 창을 연 뒤 실행되었을 수도 있다
            self.set_message(t("panel.form.running_block", name=service["name"]))
            return
        try:
            core.remove_service(self.config_path, service["name"])
        except core.DevrunError as error:
            self.set_message(t("panel.config_error", error=short_error(error, self.config_path)))
            return
        self.config_mtime = None
        self.reload_config()
        self.set_message(t("panel.form.deleted", name=service["name"]))

    def finish_form(self):
        form = self.form
        original = form["service"]
        try:
            service = build_service(form)
            if original and service["name"] != original["name"] and self.is_running(original["name"]):
                self.reopen_form(t("panel.form.rename_running", name=original["name"]))
                return
            core.save_service(self.config_path, service, original["name"] if original else None)
        except core.DevrunError as error:
            self.reopen_form(t("panel.config_error", error=short_error(error, self.config_path)))
            return
        self.form = None
        self.config_mtime = None
        self.reload_config()
        self.select_name(service["name"])
        self.set_message(t("panel.form.saved", name=service["name"]))

    def reopen_form(self, message):
        """입력한 값을 기본값으로 남기고 처음 항목부터 다시 묻는다 (목록 칸은 고른 항목에 커서). 이유는 안내 줄에 보인다."""
        form = self.form
        form["defaults"], form["values"] = dict(form["values"]), {}
        form["index"] = 0
        self.start_step()
        self.set_message(message)

    def open_browser(self, service):
        if not service or not service.get("url"):
            self.set_message(t("panel.no_url"))
            return
        webbrowser.open(service["url"])
        self.set_message(t("panel.opened_url", url=service["url"]))

    def open_config(self):
        """설정 파일을 연다. Windows 는 항상 메모장, 그 밖의 OS 는 기본 프로그램 (xdg-open / open)."""
        path = str(self.config_path)
        if core.IS_WINDOWS:
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

    def row_button_at(self, x, y):
        """서비스 줄 버튼이면 (명령, 서비스 index), 아니면 None."""
        return next(((command, index) for row, x1, x2, command, index in self.row_buttons
                     if row == y and x1 <= x <= x2), None)

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
                row_button = self.row_button_at(event.x, event.y)
                if row_button:  # 줄 버튼은 그 줄의 서비스를 먼저 고른 뒤 명령을 낸다
                    command, index = row_button
                    self.select(index)
                    return command
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

    def dispatch(self, event):
        """입력 이벤트 하나를 처리한다. 폼이 열려 있으면 키는 폼이 받고, 클릭은 폼을 취소한 뒤 평소처럼 처리한다.
        휠은 폼 중에 무시한다."""
        if self.dialog:
            self.guarded(self.dialog_event, event, message_key="panel.error")
            return
        if self.form and event.kind == "key":
            self.guarded(self.form_input, event, message_key="panel.error")
            return
        if self.form and event.kind == "mouse":
            if event.mouse not in ("down", "double"):
                return
            self.form = None  # 입력 중에 버튼을 누르면 입력을 취소하고 그 버튼을 처리한다
            self.set_message(t("panel.form.cancelled"))
        command = self.guarded(self.command_for, event, message_key="panel.error")
        if command:
            self.guarded(self.execute, command, message_key="panel.error")

    def dialog_event(self, event):
        """삭제 확인 알림 창이 떠 있는 동안의 입력. y·[삭제] 는 삭제, n·Esc·[취소]·창 밖 클릭은 닫기. 휠은 무시."""
        if event.kind == "key":
            key = HANGUL_KEYS.get(event.key, event.key)
            key = key.lower() if len(key) == 1 else key
            if key == "y":
                self.execute("dialog_confirm")
            elif key in ("n", "esc", "ctrl+c"):  # 입력 폼과 같이 Ctrl+C 도 취소로 받는다
                self.execute("dialog_cancel")
            return
        if event.kind == "mouse" and event.mouse in ("down", "double"):
            command = self.dialog_button_at(event.x, event.y)
            if command:
                self.execute(command)
            elif not self.in_dialog_box(event.x, event.y):
                self.execute("dialog_cancel")

    def dialog_button_at(self, x, y):
        return next((command for row, x1, x2, command in self.dialog_buttons if row == y and x1 <= x <= x2), None)

    def in_dialog_box(self, x, y):
        if not self.dialog_box:
            return False
        top, left, width = self.dialog_box
        return top <= y < top + DIALOG_BOX_HEIGHT and left <= x < left + width

    def loop(self):
        self.guarded(self.refresh, message_key="panel.refresh_error")
        self.draw()
        while self.running:
            dirty = False
            for event in self.terminal.read(INPUT_WAIT_SECONDS):
                dirty = True
                self.dispatch(event)
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


def short_error(error, path):
    """설정 검증 오류 문구는 앞에 파일 경로가 붙는다. 좁은 안내 줄에서도 이유가 남도록 경로를 뺀다."""
    text = str(error)
    head = str(path)
    if text.startswith(head):
        text = text[len(head):].lstrip(" :")
    return text


def form_defaults(service):
    """추가 폼의 기본값. 추가할 때는 비워 두고(폴더는 프로젝트 루트), 수정할 때는 현재 값을 보인다."""
    if service is None:
        return {"name": "", "cwd": "", "command": "", "port": "", "url": "", "depends_on": ""}
    return {
        "name": service["name"],
        "cwd": service.get("cwd", ""),
        "command": core.service_command(service),
        "port": str(service.get("port", "")),
        "url": service.get("url", ""),
        "depends_on": ", ".join(service.get("depends_on", [])),
    }


def build_service(form):
    """입력 값을 설정의 서비스 항목으로 바꾼다. 수정이면 원래 항목(env, 시간 제한 등)을 그대로 두고 바뀐 칸만 고친다."""
    original, values = form["service"], form["values"]
    service = dict(original) if original else {}
    service["name"] = values["name"]
    _set_command(service, form, values["command"])
    _set_or_drop(service, "cwd", values["cwd"])
    _set_or_drop(service, "url", values["url"])
    port = values["port"]
    if port.isdigit():
        port = int(port)
    _set_or_drop(service, "port", port)
    depends_on = [name.strip() for name in values["depends_on"].split(",") if name.strip()]
    _set_or_drop(service, "depends_on", depends_on)
    return service


def _set_command(service, form, command):
    """명령을 적는다. 수정이면 원래 명령의 키에 적고, 추가면 프리셋의 OS 별 명령에 맞춘다 (다르면 command_windows / command_unix 둘 다)."""
    if form["service"]:
        service[core.command_key(form["service"])] = command
        return
    preset = form["preset"]
    if preset and preset["windows"] != preset["unix"]:
        current = "command_windows" if core.IS_WINDOWS else "command_unix"
        service.pop("command", None)
        service["command_windows"] = command if current == "command_windows" else preset["windows"]
        service["command_unix"] = command if current == "command_unix" else preset["unix"]
    else:
        service["command"] = command


def _set_or_drop(service, key, value):
    if value in ("", [], None):  # 0 같은 값은 남겨 두어야 검증이 잡는다
        service.pop(key, None)
    else:
        service[key] = value


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
    finally:
        # 대시보드가 끝나면 pane 을 다시 찾는 표식을 지운다. 다음 열기는 새 pane 을 만든다.
        core.panel_marker_path(config_path.parent).unlink(missing_ok=True)
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
