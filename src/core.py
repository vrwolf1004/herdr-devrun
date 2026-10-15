"""herdr-devrun 공통 기능. devrun.py(액션)와 panel.py(대시보드)가 함께 쓴다.

  herdr   : CLI 호출, 알림, pane/tab 조회
  config  : .herdr-devrun.json 탐색·검증
  state   : 프로젝트별 실행 상태(탭 id, 서비스별 pane id)
  service : 서비스 하나 시작/중지/재시작, 상태 판정
  project : 전체 시작/중지, init
"""

import enum
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import procs
from i18n import t

CONFIG_NAME = ".herdr-devrun.json"
STOP_WAIT_SECONDS = 1.5
IS_WINDOWS = sys.platform == "win32"
HERDR = os.environ.get("HERDR_BIN_PATH") or "herdr"


class DevrunError(Exception):
    """사용자에게 그대로 보여 줄 오류."""


# ---------------------------------------------------------------- herdr


def herdr(*args, check=True):
    """herdr CLI 를 실행하고 JSON 응답의 result 를 돌려준다. check=False 면 실패 시 None."""
    completed = subprocess.run(
        [HERDR, *[str(arg) for arg in args]],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        if not check:
            return None
        detail = (completed.stdout + completed.stderr).strip()
        raise DevrunError(t("error.herdr_failed", command=" ".join(map(str, args)), detail=detail))
    output = completed.stdout.strip()
    if not output:
        return {}
    return json.loads(output).get("result", {})


def herdr_text(*args):
    """JSON 이 아닌 출력(pane read)을 그대로 돌려준다. 실패 시 빈 문자열."""
    completed = subprocess.run(
        [HERDR, *[str(arg) for arg in args]],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout if completed.returncode == 0 else ""


def notify(title, body):
    # 알림 실패가 본래 작업 결과를 가리지 않도록 결과는 보지 않는다.
    herdr("notification", "show", title, "--body", body, check=False)


def pane_id_of(result):
    """tab create 는 root_pane, pane split 은 pane 으로 돌려준다."""
    for key in ("pane", "root_pane"):
        pane = result.get(key)
        if isinstance(pane, dict) and pane.get("pane_id"):
            return pane["pane_id"]
    if result.get("pane_id"):
        return result["pane_id"]
    raise DevrunError(t("error.pane_id_missing", result=json.dumps(result, ensure_ascii=False)))


def tab_exists(tab_id):
    return bool(tab_id) and herdr("tab", "get", tab_id, check=False) is not None


def live_pane_ids():
    """살아 있는 pane id 집합. 상태 판정마다 pane 별로 조회하지 않도록 한 번에 가져온다."""
    return {pane["pane_id"] for pane in herdr("pane", "list").get("panes", [])}


# ---------------------------------------------------------------- config


def start_dir(explicit_dir=None):
    if explicit_dir:
        return Path(explicit_dir).resolve()
    pane_id = os.environ.get("HERDR_PANE_ID")
    if pane_id:
        return Path(herdr("pane", "get", pane_id)["pane"]["cwd"]).resolve()
    raise DevrunError(t("error.start_dir_unknown"))


def find_config_path(start):
    for folder in (start, *start.parents):
        candidate = folder / CONFIG_NAME
        if candidate.is_file():
            return candidate
    raise DevrunError(t("error.config_not_found", config=CONFIG_NAME, start=start))


def read_config(config_path):
    try:
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise DevrunError(t("error.config_json", path=config_path, error=error)) from error
    services = config.get("services") or []
    if not services:
        raise DevrunError(t("error.config_no_services", path=config_path))
    names = set()
    for service in services:
        if not service.get("name") or not service_command(service):
            raise DevrunError(t("error.config_missing_fields", path=config_path))
        if service["name"] in names:
            raise DevrunError(t("error.config_duplicate_name", path=config_path, name=service["name"]))
        names.add(service["name"])
    return config


def service_command(service):
    """OS 별 명령(command_windows / command_unix)이 있으면 그것을, 없으면 command 를 쓴다."""
    override = service.get("command_windows" if IS_WINDOWS else "command_unix")
    return override or service.get("command")


def tab_label(project_dir, config):
    return config.get("tab") or project_dir.name


def service_dir(project_dir, service):
    path = (project_dir / service["cwd"]) if service.get("cwd") else project_dir
    if not path.is_dir():
        raise DevrunError(t("error.service_dir_missing", name=service["name"], path=path))
    return path.resolve()


def env_args(service):
    args = []
    for key, value in (service.get("env") or {}).items():
        args += ["--env", f"{key}={value}"]
    return args


# ---------------------------------------------------------------- state
#
# 상태는 { project, label, tab_id, panes: [{ name, pane_id }] } 이다.


def state_dir():
    configured = os.environ.get("HERDR_PLUGIN_STATE_DIR")
    if configured:
        return Path(configured)
    if IS_WINDOWS:
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "herdr-devrun"
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "herdr-devrun"


def state_path(project_dir):
    key = str(project_dir).lower() if IS_WINDOWS else str(project_dir)
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return state_dir() / f"{digest}.json"


def read_state(project_dir):
    path = state_path(project_dir)
    if not path.is_file():
        return None
    state = json.loads(path.read_text(encoding="utf-8"))
    state["panes"] = [pane for pane in state.get("panes", []) if pane]
    return state


def write_state(project_dir, state):
    path = state_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def remove_state(project_dir):
    state_path(project_dir).unlink(missing_ok=True)


def live_state(project_dir, alive_pane_ids):
    """탭이 사라졌으면 None, 사라진 pane 은 목록에서 뺀 상태를 돌려준다."""
    state = read_state(project_dir)
    if not state:
        return None
    if not tab_exists(state.get("tab_id")):
        remove_state(project_dir)
        return None
    alive = [pane for pane in state["panes"] if pane["pane_id"] in alive_pane_ids]
    if len(alive) != len(state["panes"]):
        state["panes"] = alive
        write_state(project_dir, state)
    return state


def find_pane(state, name):
    if not state:
        return None
    return next((pane for pane in state["panes"] if pane["name"] == name), None)


# ---------------------------------------------------------------- service


class Status(enum.Enum):
    STOPPED = "stopped"    # pane 없음
    EXITED = "exited"      # pane 은 있지만 셸만 남음 (서비스가 끝났거나 실패)
    STARTING = "starting"  # 프로세스는 돌지만 port 가 아직 안 열림
    RUNNING = "running"    # 프로세스가 돌고 port 가 열림 (port 미지정이면 프로세스만으로 판단)
    WORKING = "working"    # 대시보드가 시작·중지를 처리하는 중 (화면 표시용)


def run_in_pane(pane_id, service):
    herdr("pane", "rename", pane_id, service["name"])
    herdr("pane", "run", pane_id, service_command(service))


def start_service(project_dir, config, service, focus=False):
    """서비스 하나를 띄운다. 이미 떠 있으면 아무것도 하지 않고 False.

    탭이 없으면 이 서비스로 탭을 만들고, 있으면 pane 을 나눈다.
    배치: 첫 pane 왼쪽, 두 번째 오른쪽, 이후는 마지막 pane 아래로 쌓는다.
    """
    state = live_state(project_dir, live_pane_ids())
    if find_pane(state, service["name"]):
        return False

    folder = service_dir(project_dir, service)
    # 서비스 pane 을 모두 손으로 닫아 다른 플러그인 pane 만 남은 탭은 버리고 새로 만든다.
    if state and not state["panes"]:
        herdr("tab", "close", state["tab_id"])
        remove_state(project_dir)
        state = None

    if state is None:
        label = tab_label(project_dir, config)
        created = herdr("tab", "create", "--cwd", folder, "--label", label,
                        "--focus" if focus else "--no-focus", *env_args(service))
        state = {"project": str(project_dir), "label": label, "tab_id": created["tab"]["tab_id"], "panes": []}
        pane_id = pane_id_of(created)
    else:
        last = state["panes"][-1]
        direction = "right" if len(state["panes"]) == 1 else "down"
        pane_id = pane_id_of(herdr("pane", "split", last["pane_id"], "--direction", direction,
                                   "--cwd", folder, "--no-focus", *env_args(service)))

    state["panes"].append({"name": service["name"], "pane_id": pane_id})
    write_state(project_dir, state)
    run_in_pane(pane_id, service)
    return True


def stop_service(project_dir, name):
    """Ctrl+C 로 정상 종료 기회를 준 뒤 pane 을 닫는다. 마지막 서비스면 탭도 닫는다.

    떠 있지 않으면 False.
    """
    state = live_state(project_dir, live_pane_ids())
    pane = find_pane(state, name)
    if not pane:
        return False

    herdr("pane", "send-keys", pane["pane_id"], "ctrl+c", check=False)
    time.sleep(STOP_WAIT_SECONDS)
    state["panes"] = [each for each in state["panes"] if each["name"] != name]
    if state["panes"]:
        herdr("pane", "close", pane["pane_id"])
        write_state(project_dir, state)
    else:
        herdr("tab", "close", state["tab_id"])
        remove_state(project_dir)
    return True


def restart_service(project_dir, config, service):
    """같은 pane 에서 다시 실행하지 않고 pane 을 새로 연다.

    Windows 의 .bat(gradlew 등)는 Ctrl+C 후 "일괄 작업을 끝내시겠습니까 (Y/N)?" 를 물어
    입력 상태가 불확실해지기 때문이다.
    """
    stop_service(project_dir, service["name"])
    start_service(project_dir, config, service)


def service_status(service, state, child_map):
    pane = find_pane(state, service["name"])
    if not pane:
        return Status.STOPPED
    # herdr process-info 의 foreground 는 Windows 에서 셸만 돌려주므로, 셸의 자식으로 실행 여부를 본다.
    info = herdr("pane", "process-info", "--pane", pane["pane_id"], check=False) or {}
    shell_pid = (info.get("process_info") or {}).get("shell_pid")
    if not shell_pid or not procs.has_children(child_map, int(shell_pid)):
        return Status.EXITED
    port = service.get("port")
    if port and not procs.is_listening(int(port)):
        return Status.STARTING
    return Status.RUNNING


def service_log(state, name, lines):
    pane = find_pane(state, name)
    if not pane:
        return []
    text = herdr_text("pane", "read", pane["pane_id"], "--lines", lines, "--source", "recent")
    return [line for line in text.splitlines() if line.strip()]


# ---------------------------------------------------------------- project


def up(project_dir, config):
    started = 0
    for index, service in enumerate(config["services"]):
        if start_service(project_dir, config, service, focus=index == 0):
            started += 1
    state = read_state(project_dir)
    if started == 0:
        herdr("tab", "focus", state["tab_id"])
        notify(t("notice.title"), t("notice.already_running", label=state["label"]))
        return
    notify(t("notice.title"), t("notice.started", label=state["label"], count=started))


def down(project_dir, quiet=False):
    state = live_state(project_dir, live_pane_ids())
    if not state:
        if not quiet:
            notify(t("notice.title"), t("notice.nothing_running"))
        return
    # Ctrl+C 로 정상 종료 기회를 준 뒤 탭을 닫아 남은 프로세스를 정리한다.
    for pane in state["panes"]:
        herdr("pane", "send-keys", pane["pane_id"], "ctrl+c", check=False)
    time.sleep(STOP_WAIT_SECONDS)
    herdr("tab", "close", state["tab_id"])
    remove_state(project_dir)
    if not quiet:
        notify(t("notice.title"), t("notice.stopped", label=state["label"]))


def _node_runner(folder):
    if (folder / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (folder / "yarn.lock").exists():
        return "yarn"
    return "npm"


def _service_candidate(project_dir, folder):
    """폴더 하나를 보고 실행 가능한 서비스 후보를 만든다. 없으면 None."""
    relative = "." if folder == project_dir else folder.name
    if (folder / "gradlew.bat").exists() or (folder / "gradlew").exists():
        command = r".\gradlew.bat bootRun" if IS_WINDOWS else "./gradlew bootRun"
        return {"name": f"{folder.name} (gradle)", "cwd": relative, "command": command,
                "port": 8080, "url": "http://localhost:8080"}
    if (folder / "mvnw.cmd").exists() or (folder / "mvnw").exists():
        command = r".\mvnw.cmd spring-boot:run" if IS_WINDOWS else "./mvnw spring-boot:run"
        return {"name": f"{folder.name} (maven)", "cwd": relative, "command": command,
                "port": 8080, "url": "http://localhost:8080"}
    package_json = folder / "package.json"
    if package_json.exists():
        scripts = json.loads(package_json.read_text(encoding="utf-8-sig")).get("scripts") or {}
        for script in ("dev", "start", "serve"):
            if scripts.get(script):
                return {"name": f"{folder.name} ({script})", "cwd": relative,
                        "command": f"{_node_runner(folder)} run {script}"}
    return None


_SKIP_FOLDERS = {"node_modules", "build", "dist", "target"}


def init(project_dir):
    config_path = project_dir / CONFIG_NAME
    if config_path.exists():
        notify(t("notice.title"), t("notice.config_exists", path=config_path))
        return

    folders = [project_dir] + sorted(
        child for child in project_dir.iterdir()
        if child.is_dir() and not child.name.startswith(".") and child.name not in _SKIP_FOLDERS
    )
    services = [candidate for candidate in (_service_candidate(project_dir, folder) for folder in folders) if candidate]
    found = len(services)
    if not services:
        services = [
            {"name": "backend", "cwd": "backend",
             "command": r".\gradlew.bat bootRun" if IS_WINDOWS else "./gradlew bootRun",
             "port": 8080, "url": "http://localhost:8080", "env": {"SPRING_PROFILES_ACTIVE": "local"}},
            {"name": "frontend", "cwd": "frontend", "command": "npm run dev",
             "port": 5173, "url": "http://localhost:5173"},
        ]

    config = {"tab": project_dir.name, "services": services}
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    detail = t("notice.init_detected", count=found) if found else t("notice.init_example")
    notify(t("notice.title"), t("notice.init_created", path=config_path, detail=detail))
