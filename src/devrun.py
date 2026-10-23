"""herdr-devrun 액션 진입점.

  up      : .herdr-devrun.json 의 services 중 안 떠 있는 것을 실행 (모두 떠 있으면 그 탭으로 이동)
  down    : 각 pane 에 Ctrl+C 를 보낸 뒤 탭을 닫는다
  restart : down 후 up
  init    : 현재 폴더(와 바로 아래 폴더)를 보고 .herdr-devrun.json 초안을 만든다
  panel   : 서비스 대시보드 pane 을 연다 (panel.py)

프로젝트 위치는 액션을 실행한 pane 의 cwd 에서 위로 올라가며 .herdr-devrun.json 을 찾는다.
수동 실행/테스트 시에는 --dir 로 시작 폴더를 지정한다.

    python src/devrun.py up --dir C:\\path\\to\\project
"""

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

import core
from i18n import t

PLUGIN_ID = "herdr-devrun"
CONTROL_BOX_NAME = "control-box"
WORKSPACE_LABEL = "devrun"
PANEL_SCRIPT = Path(__file__).resolve().parent / "panel.py"


def panel_command(project_dir):
    """pane 의 셸에 입력할 대시보드 명령. Windows 와 그 밖의 셸은 인용 규칙이 달라 OS 에 맞춰 만든다."""
    argv = [sys.executable, "-X", "utf8", str(PANEL_SCRIPT), "--dir", str(project_dir)]
    return subprocess.list2cmdline(argv) if core.IS_WINDOWS else shlex.join(argv)


def _service_anchor(state):
    """서비스 탭에서 대시보드를 붙일 pane. 서비스 pane 이 모두 닫혔으면 그 탭의 다른 pane 을 쓴다 (사이드바는 뺀다)."""
    if state["panes"]:
        return state["panes"][0]["pane_id"]
    panes = core.herdr("pane", "list").get("panes", [])
    return next((pane["pane_id"] for pane in panes
                 if pane.get("tab_id") == state["tab_id"] and pane.get("label") != "Sidebar"), None)


def open_panel(project_dir):
    """대시보드는 서비스가 있는 탭에서 서비스 pane 옆에 연다. 이미 그 탭에 열려 있으면 포커스만 옮긴다.
    서비스가 없으면 현재 pane 옆에 연다. 대시보드는 새 pane 의 셸에 명령을 입력해 실행한다.
    끝나면(Ctrl+C) 셸 프롬프트가 남고 표식 파일은 지워진다."""
    marker = core.panel_marker_path(project_dir)
    existing = marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""
    pane = (core.herdr("pane", "get", existing, check=False) or {}).get("pane") if existing else None
    state = core.live_state(project_dir, core.live_pane_ids())
    service_tab = state.get("tab_id") if state else None
    if pane and (service_tab is None or pane["tab_id"] == service_tab):
        core.herdr("tab", "focus", pane["tab_id"])  # 셸로 연 pane 은 plugin pane focus 로 찾을 수 없어 탭으로 옮긴다
        return
    if pane:  # 서비스와 다른 탭에 남은 대시보드는 치우고 서비스 탭에 새로 연다
        core.herdr("pane", "close", existing, check=False)

    anchor = (_service_anchor(state) if state else None) or os.environ.get("HERDR_PANE_ID")
    split = ["pane", "split", *([anchor] if anchor else []), "--direction", "right",
             "--cwd", str(project_dir), "--focus"]
    pane_id = core.pane_id_of(core.herdr(*split))
    core.herdr("pane", "run", pane_id, panel_command(project_dir))
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(pane_id, encoding="utf-8")


def open_control_box(project_dir, config):
    """컨트롤 박스(대시보드)를 서비스보다 먼저 만든다. 새 탭의 첫 pane 이 컨트롤 박스이고, 서비스는 그 옆에 나뉜다.
    탭이 이미 있으면 대시보드를 그 탭에서 연다."""
    if core.live_state(project_dir, core.live_pane_ids()):
        open_panel(project_dir)
        return
    label = core.tab_label(project_dir, config)
    # 같은 label 의 devrun space 가 있으면 그 안에 프로젝트 탭을 더한다. 없을 때만 space 를 새로 만든다.
    workspace_id = _devrun_workspace_id()
    new_space = workspace_id is None
    if new_space:
        created = core.herdr("workspace", "create", "--cwd", str(project_dir), "--label", WORKSPACE_LABEL, "--focus")
        workspace_id = created["workspace"]["workspace_id"]
    else:
        # 탭 목록을 읽지 못하면 새 space 를 만들지 않고 오류로 알린다 (check=True 라 실패 시 DevrunError).
        core.herdr("tab", "list", "--workspace", workspace_id)
        created = core.herdr("tab", "create", "--workspace", workspace_id, "--cwd", str(project_dir), "--focus")
    tab_id = created["tab"]["tab_id"]
    pane_id = created["root_pane"]["pane_id"]
    try:
        core.herdr("tab", "rename", tab_id, label)
        core.herdr("pane", "rename", pane_id, CONTROL_BOX_NAME)
        core.herdr("pane", "run", pane_id, panel_command(project_dir))
    except core.DevrunError:
        # state 는 아직 없다. 방금 만든 것만 되돌린다: 새 space 면 space 째, 기존 space 면 이 탭만 닫는다.
        if new_space:
            core.herdr("workspace", "close", workspace_id, check=False)
        else:
            core.herdr("tab", "close", tab_id, check=False)
        raise
    marker = core.panel_marker_path(project_dir)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(pane_id, encoding="utf-8")
    core.write_state(project_dir, {"project": str(project_dir), "label": label, "workspace_id": workspace_id,
                                   "tab_id": tab_id, "panes": [], "control_box": pane_id})


def ensure_control_box(project_dir, config):
    """서비스를 띄우기 전에 컨트롤 박스가 있는지 본다. 없으면 open_control_box 로 devrun space 에 만든다.
    CLI up 과 대시보드의 시작이 이 규칙을 같이 쓴다. 이미 있으면 아무것도 하지 않는다."""
    if not core.live_state(project_dir, core.live_pane_ids()):
        open_control_box(project_dir, config)


def _devrun_workspace_id():
    """label 이 devrun 인 space 의 id. 여러 개면 목록의 첫 번째 (없으면 None)."""
    spaces = core.herdr("workspace", "list").get("workspaces", [])
    return next((each["workspace_id"] for each in spaces if each.get("label") == WORKSPACE_LABEL), None)


def _config_or_none(config_path):
    """down 은 설정이 깨져 있어도 내릴 수 있어야 한다. stop_timeout 만 못 쓰고 기본값으로 기다린다."""
    try:
        return core.read_config(config_path)
    except core.DevrunError:
        return None


def run(action, explicit_dir):
    start = core.start_dir(explicit_dir)
    if action == "init":
        core.init(start)
        return

    config_path = core.find_config_path(start)
    project_dir = config_path.parent
    if action == "up":
        config = core.read_config(config_path)
        open_control_box(project_dir, config)
        core.up(project_dir, config)
    elif action == "down":
        core.down(project_dir, config=_config_or_none(config_path))
    elif action == "restart":
        config = core.read_config(config_path)
        core.down(project_dir, quiet=True, config=config)
        open_control_box(project_dir, config)
        core.up(project_dir, config)
    elif action == "panel":
        core.read_config(config_path)
        open_panel(project_dir)
    else:
        raise core.DevrunError(t("error.unknown_action", action=action))


def main():
    parser = argparse.ArgumentParser(prog="devrun")
    parser.add_argument("action", choices=["up", "down", "restart", "init", "panel"])
    parser.add_argument("--dir", help=t("cli.dir_help"))
    args = parser.parse_args()
    try:
        run(args.action, args.dir)
    except core.DevrunError as error:
        core.notify(t("notice.error_title"), str(error))
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
