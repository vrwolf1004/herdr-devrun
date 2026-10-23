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
import re
import subprocess
import sys
import time
from pathlib import Path

import procs
from i18n import t

CONFIG_NAME = ".herdr-devrun.json"
STOP_TIMEOUT_SECONDS = 10   # 서비스별 stop_timeout 이 없을 때 종료를 기다리는 최대 시간
STOP_POLL_SECONDS = 0.2
START_TIMEOUT_SECONDS = 120  # 서비스별 start_timeout 이 없을 때 depends_on 준비를 기다리는 최대 시간
START_POLL_SECONDS = 0.5
STARTUP_GRACE_SECONDS = 5   # 막 띄운 서비스가 '종료됨'이어도 실패로 보지 않는 시간
IS_WINDOWS = sys.platform == "win32"
HERDR = os.environ.get("HERDR_BIN_PATH") or "herdr"


class DevrunError(Exception):
    """사용자에게 그대로 보여 줄 오류."""


class PortInUseError(DevrunError):
    """시작하려는 서비스의 port 를 이미 다른 프로세스가 쓰고 있다."""


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


def load_raw(config_path):
    try:
        return json.loads(config_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise DevrunError(t("error.config_json", path=config_path, error=error)) from error


def read_config(config_path):
    return validate_config(load_raw(config_path), config_path)


def save_service(config_path, service, original_name=None):
    """서비스 하나를 넣거나(새 이름) 같은 이름을 바꾼다. 검증이 실패하면 파일을 건드리지 않는다."""
    config = load_raw(config_path)
    services = config.get("services") or []
    index = next((i for i, each in enumerate(services) if each.get("name") == original_name), None)
    if index is None:
        services.append(service)
    else:
        services[index] = service
    config["services"] = services
    validate_config(config, config_path)
    _write_config(config_path, config)


def remove_service(config_path, name):
    """서비스를 지우고, 다른 서비스의 depends_on 에서도 이름을 뺀다."""
    config = load_raw(config_path)
    services = [each for each in config.get("services") or [] if each.get("name") != name]
    for each in services:
        if name in each.get("depends_on", []):
            each["depends_on"] = [dependency for dependency in each["depends_on"] if dependency != name]
            if not each["depends_on"]:
                del each["depends_on"]
    config["services"] = services
    validate_config(config, config_path)
    _write_config(config_path, config)


def _write_config(config_path, config):
    temp = config_path.with_name(config_path.name + ".tmp")
    temp.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, config_path)


def command_key(service):
    """서비스의 명령이 적힌 키. 현재 OS 전용 키(command_windows / command_unix)가 있으면 그것, 없으면 command."""
    override = "command_windows" if IS_WINDOWS else "command_unix"
    return override if service.get(override) else "command"


def validate_config(config, config_path):
    if not isinstance(config, dict):
        raise DevrunError(t("error.config_not_object", path=config_path))
    services = config.get("services") or []
    if not isinstance(services, list):
        raise DevrunError(t("error.config_bad_services", path=config_path))
    if not services:
        raise DevrunError(t("error.config_no_services", path=config_path))
    names = set()
    for service in services:
        if not isinstance(service, dict) or not service.get("name") or not service_command(service):
            raise DevrunError(t("error.config_missing_fields", path=config_path))
        if "port" in service and not _is_port(service["port"]):
            raise DevrunError(t("error.config_bad_port", path=config_path, name=service["name"]))
        if service["name"] in names:
            raise DevrunError(t("error.config_duplicate_name", path=config_path, name=service["name"]))
        names.add(service["name"])
        if not _is_seconds(service.get("stop_timeout", STOP_TIMEOUT_SECONDS)):
            raise DevrunError(t("error.config_bad_stop_timeout", path=config_path, name=service["name"]))
        if not _is_seconds(service.get("start_timeout", START_TIMEOUT_SECONDS)):
            raise DevrunError(t("error.config_bad_start_timeout", path=config_path, name=service["name"]))
        depends_on = service.get("depends_on", [])
        if not isinstance(depends_on, list) or not all(isinstance(each, str) for each in depends_on):
            raise DevrunError(t("error.config_bad_depends_on", path=config_path, name=service["name"]))
    for service in services:
        for dependency in service.get("depends_on", []):
            if dependency not in names:  # 자기 자신에 의존하는 것은 아래 순환 검사가 잡는다
                raise DevrunError(t("error.config_unknown_dependency", path=config_path,
                                    name=service["name"], dependency=dependency))
    cycle = _dependency_cycle(services)
    if cycle:
        raise DevrunError(t("error.config_dependency_cycle", path=config_path, cycle=" → ".join(cycle)))
    return config


def _is_seconds(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and value >= 0


def _is_port(value):
    return not isinstance(value, bool) and isinstance(value, int) and 1 <= value <= 65535


def _dependency_cycle(services):
    """depends_on 순환이 있으면 순환 경로(이름 목록), 없으면 None."""
    graph = {service["name"]: service.get("depends_on", []) for service in services}
    visiting, done = [], set()

    def visit(name):
        if name in done:
            return None
        if name in visiting:
            return visiting[visiting.index(name):] + [name]
        visiting.append(name)
        for dependency in graph.get(name, []):
            cycle = visit(dependency)
            if cycle:
                return cycle
        visiting.pop()
        done.add(name)
        return None

    for name in graph:
        cycle = visit(name)
        if cycle:
            return cycle
    return None


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


def _project_key(project_dir):
    key = str(project_dir).lower() if IS_WINDOWS else str(project_dir)
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def state_path(project_dir):
    return state_dir() / f"{_project_key(project_dir)}.json"


def panel_marker_path(project_dir):
    """프로젝트의 대시보드 pane id 를 적어 두는 파일. 서비스 상태와 수명이 달라 따로 둔다."""
    return state_dir() / f"{_project_key(project_dir)}.panel"


def read_state(project_dir):
    path = state_path(project_dir)
    if not path.is_file():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # 손상된 상태는 버린다. 살아 있는 pane 은 다음 시작에서 다시 만들어진다.
        path.unlink(missing_ok=True)
        return None
    if not isinstance(state, dict):
        path.unlink(missing_ok=True)
        return None
    state["panes"] = [pane for pane in state.get("panes", []) if isinstance(pane, dict) and pane]
    return state


def write_state(project_dir, state):
    path = state_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    # 임시 파일에 쓰고 바꿔 끼운다. 중간에 멈춰도 부분 JSON 이 남지 않는다.
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


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
    WAITING = "waiting"    # 전체 시작에서 depends_on 이 준비되기를 기다리는 중 (화면 표시용)


def run_in_pane(pane_id, service):
    herdr("pane", "rename", pane_id, service["name"])
    herdr("pane", "run", pane_id, service_command(service))


def start_service(project_dir, config, service, focus=False):
    """서비스 하나를 띄운다. 이미 떠 있으면 아무것도 하지 않고 False.

    탭이 없으면 이 서비스로 탭을 만들고, 있으면 pane 을 나눈다.
    배치: 첫 pane 왼쪽, 두 번째 오른쪽, 이후는 마지막 pane 아래로 쌓는다.
    """
    state = live_state(project_dir, live_pane_ids())
    pane = find_pane(state, service["name"])
    if pane and _pane_busy(pane):
        if not _release_wrapper(pane):  # 서비스 프로세스가 살아 있거나 질문이 없으면 건드리지 않는다
            return False
        if not _wait_until_idle(pane, RELEASE_WAIT_SECONDS):  # 답한 뒤에도 래퍼가 남으면 pane 을 닫고 새로 만든다
            herdr("pane", "close", pane["pane_id"], check=False)
            state["panes"] = [each for each in state["panes"] if each is not pane]
            write_state(project_dir, state)
            pane = None
    # 다른 프로세스가 이미 port 를 쓰고 있으면, 띄워도 충돌로 실패하는데 상태는 "실행 중"으로 보이므로 막는다.
    port = service.get("port")
    if port and procs.is_listening(int(port)):
        raise PortInUseError(t("error.port_in_use", name=service["name"], port=port))
    if pane:  # 끝났거나 중지한 pane 은 셸 프롬프트에서 명령만 다시 입력한다
        run_in_pane(pane["pane_id"], service)
        pane.pop("stopped", None)
        write_state(project_dir, state)
        return True

    folder = service_dir(project_dir, service)
    # 서비스 pane 을 모두 손으로 닫아 다른 플러그인 pane 만 남은 탭은 버리고 새로 만든다.
    # 컨트롤 박스가 있는 탭은 서비스 pane 이 없어도 그대로 쓴다.
    if state and not state["panes"] and not state.get("control_box"):
        herdr("tab", "close", state["tab_id"])
        remove_state(project_dir)
        state = None

    made_tab = state is None
    if state is None:
        label = tab_label(project_dir, config)
        created = herdr("tab", "create", "--cwd", folder, "--label", label,
                        "--focus" if focus else "--no-focus", *env_args(service))
        state = {"project": str(project_dir), "label": label, "tab_id": created["tab"]["tab_id"], "panes": []}
        pane_id = pane_id_of(created)
    else:
        # 컨트롤 박스 바로 오른쪽, 그다음 서비스 오른쪽, 이후는 마지막 pane 아래로 쌓는다.
        last = state["panes"][-1]["pane_id"] if state["panes"] else state["control_box"]
        direction = "right" if len(state["panes"]) <= 1 else "down"
        pane_id = pane_id_of(herdr("pane", "split", last, "--direction", direction,
                                   "--cwd", folder, "--no-focus", *env_args(service)))

    state["panes"].append({"name": service["name"], "pane_id": pane_id})
    write_state(project_dir, state)
    try:
        run_in_pane(pane_id, service)
    except DevrunError:
        # 명령을 입력하지 못했으면 방금 만든 것만 되돌린다. 상태에 없는 pane 이 남지 않게 한다.
        if made_tab:
            herdr("tab", "close", state["tab_id"], check=False)
            remove_state(project_dir)
        else:
            herdr("pane", "close", pane_id, check=False)
            state["panes"] = [pane for pane in state["panes"] if pane["pane_id"] != pane_id]
            write_state(project_dir, state)
        raise
    return True


def stop_timeout(service):
    return float(service.get("stop_timeout", STOP_TIMEOUT_SECONDS)) if service else STOP_TIMEOUT_SECONDS


def shell_pid(pane_id):
    info = herdr("pane", "process-info", "--pane", pane_id, check=False) or {}
    pid = (info.get("process_info") or {}).get("shell_pid")
    return int(pid) if pid else None


def interrupt_and_wait(panes):
    """[(pane_id, 최대 대기 초)] 에 Ctrl+C 를 보내고, 셸 아래 프로세스가 끝날 때까지 기다린다.

    기다리는 동안 pane 에 "(Y/N)" 질문이 보이면 Y 와 Enter 로 답한다 (.bat 의 "일괄 작업을 끝내시겠습니까?" 등).
    pane 마다 최대 시간이 지나면 더 기다리지 않는다. 끝나지 않은 프로세스는 pane/탭을 닫을 때 함께 종료된다.
    """
    now = time.monotonic()
    pending = {}   # 셸 pid → (끝나야 할 시각, pane id)
    answered = {}  # pane id → 지금까지 답한 질문 수
    for pane_id, timeout in panes:
        pid = shell_pid(pane_id)
        herdr("pane", "send-keys", pane_id, "ctrl+c", check=False)
        if pid:
            pending[pid] = (now + timeout, pane_id)
    while pending:
        time.sleep(STOP_POLL_SECONDS)
        child_map = procs.child_process_map()
        now = time.monotonic()
        still = {}
        for pid, (deadline, pane_id) in pending.items():
            if deadline <= now:  # 기다림이 끝나는 순간 래퍼가 남아 있으면 질문이 막 나온 것일 수 있어 한 번 더 본다
                if _has_wrapper(child_map, pid):
                    answer_prompt(pane_id, answered)
                continue
            answer_prompt(pane_id, answered)
            if procs.has_running_children(child_map, pid) or _has_wrapper(child_map, pid):
                still[pid] = (deadline, pane_id)
        pending = still


PROMPT_PATTERN = re.compile(r"\bY/N\b", re.IGNORECASE)  # "(Y/N)" "[Y/N]" 등 언어와 상관없이 Y/N 질문
PROMPT_LINES = 40
RELEASE_WAIT_SECONDS = 5  # 래퍼에 답한 뒤 래퍼가 사라지기를 기다리는 최대 시간


def answer_prompt(pane_id, answered):
    """pane 에 새 Y/N 질문이 나왔으면 Y 와 Enter 로 답한다. 이미 답한 질문은 다시 답하지 않는다. 답했으면 True."""
    text = herdr_text("pane", "read", pane_id, "--lines", PROMPT_LINES, "--source", "recent-unwrapped")
    count = len(PROMPT_PATTERN.findall(text))
    sent = count > answered.get(pane_id, 0)
    if sent:
        herdr("pane", "send-text", pane_id, "Y", check=False)
        herdr("pane", "send-keys", pane_id, "enter", check=False)
    answered[pane_id] = count  # 화면에서 밀려난 질문은 세지 않는다 (줄어들면 맞춰 준다)
    return sent


def stop_service(project_dir, name, timeout=STOP_TIMEOUT_SECONDS):
    """Ctrl+C 로 프로세스만 끈다. pane 은 셸 프롬프트 상태로 남기고 '중지'로 표시한다.

    끝나지 않으면 (예: .bat 의 종료 확인에 걸림) pane 을 닫아 확실히 끈다. 떠 있지 않으면 False.
    """
    state = live_state(project_dir, live_pane_ids())
    pane = find_pane(state, name)
    if not pane:
        return False

    interrupt_and_wait([(pane["pane_id"], timeout)])
    if _has_live_process(pane):
        _drop_pane(project_dir, state, pane)
    else:
        pane["stopped"] = True
        write_state(project_dir, state)
    return True


def stop_all_services(project_dir, config):
    """대시보드의 전체 중지. 실행 중인 서비스를 단일 중지와 같이 끈다: pane 은 남기고 '중지'로 표시한다.
    제 시간에 끝나지 않은 pane 은 닫는다. 탭과 컨트롤 박스는 남긴다 (탭 전체를 닫는 것은 down 이다).

    중지한 서비스 수를 돌려준다. 실행 중인 것이 없으면 0 이고 아무것도 하지 않는다.
    """
    state = live_state(project_dir, live_pane_ids())
    if not state:
        return 0
    candidates = [pane for pane in state["panes"] if not pane.get("stopped")]
    # 중지 전에 실제로 프로세스가 돌고 있던 pane 만 Ctrl+C 를 보내고 센다. 이미 죽어 있던 pane 은 표시만 바꾼다.
    running = [pane for pane in candidates if _has_live_process(pane)]
    services = {service["name"]: service for service in (config or {}).get("services", [])}
    if running:
        interrupt_and_wait([(pane["pane_id"], stop_timeout(services.get(pane["name"]))) for pane in running])
    closed = []
    for pane in candidates:
        if pane in running and _has_live_process(pane):
            herdr("pane", "close", pane["pane_id"], check=False)
            closed.append(pane["name"])
        else:
            pane["stopped"] = True
    state["panes"] = [pane for pane in state["panes"] if pane["name"] not in closed]
    if state["panes"] or state.get("control_box"):
        write_state(project_dir, state)  # 탭과 컨트롤 박스는 남긴다
    else:
        herdr("tab", "close", state["tab_id"], check=False)
        remove_state(project_dir)
    return len(running)


def close_service_pane(project_dir, name, timeout=STOP_TIMEOUT_SECONDS):
    """서비스 pane 을 닫는다. 프로세스가 살아 있으면 먼저 끈다. 컨트롤 박스가 있는 탭은 남긴다.

    떠 있지 않던 pane 도 닫는다. pane 이 없으면 False.
    """
    state = live_state(project_dir, live_pane_ids())
    pane = find_pane(state, name)
    if not pane:
        return False
    interrupt_and_wait([(pane["pane_id"], timeout)])
    _drop_pane(project_dir, state, pane)
    return True


def _has_live_process(pane):
    """셸 아래에 아직 돌고 있는 프로세스가 있는지. 셸 pid 를 모르면 있다고 본다 (안전하게 닫는 쪽)."""
    pid = shell_pid(pane["pane_id"])
    if not pid:
        return True
    child_map = procs.child_process_map()
    return procs.has_running_children(child_map, pid) or _has_wrapper(child_map, pid)


def _release_wrapper(pane):
    """서비스 프로세스 없이 cmd.exe 래퍼만 남은 pane 에서, 화면에 Y/N 질문이 있으면 답한다. 답했으면 True.

    서비스 프로세스가 살아 있거나 질문이 없으면 아무것도 보내지 않고 False.
    """
    pid = shell_pid(pane["pane_id"])
    if not pid:
        return False
    child_map = procs.child_process_map()
    if procs.has_running_children(child_map, pid) or not _has_wrapper(child_map, pid):
        return False
    return answer_prompt(pane["pane_id"], {})


def _wait_until_idle(pane, seconds):
    """pane 에 살아 있는 프로세스가 없어질 때까지 기다린다. 제 시간에 안 없어지면 False."""
    deadline = time.monotonic() + seconds
    while _pane_busy(pane):
        if time.monotonic() >= deadline:
            return False
        time.sleep(STOP_POLL_SECONDS)
    return True


def _pane_busy(pane):
    """pane 셸 아래에 서비스 프로세스가 살아 있는지. 셸 pid 를 모르면 '안 돌고 있음'으로 보고 다시 쓴다."""
    pid = shell_pid(pane["pane_id"])
    if not pid:
        return False
    child_map = procs.child_process_map()
    return procs.has_running_children(child_map, pid) or _has_wrapper(child_map, pid)


def _has_wrapper(child_map, pid):
    """셸 아래 cmd.exe (.bat 래퍼)가 남아 있는지. Ctrl+C 뒤 Y/N 질문에서 기다리는 중일 수 있어, 끝난 것으로 보지 않는다."""
    return any(name.lower() == "cmd.exe" for _, name in child_map.get(pid, []))


def _drop_pane(project_dir, state, pane):
    """pane 을 닫고 상태에서 뺀다. 마지막 pane 이고 컨트롤 박스가 없는 탭이면 탭도 닫는다."""
    herdr("pane", "close", pane["pane_id"], check=False)
    state["panes"] = [each for each in state["panes"] if each["name"] != pane["name"]]
    if state["panes"] or state.get("control_box"):
        write_state(project_dir, state)
    else:
        herdr("tab", "close", state["tab_id"], check=False)
        remove_state(project_dir)


def restart_service(project_dir, config, service):
    """중지한 뒤 다시 시작한다. 프로세스가 깨끗이 끝났으면 pane 을 그대로 쓰고, 끝나지 않아 pane 을 닫았으면 새로 연다.

    Windows 의 .bat(gradlew 등)는 Ctrl+C 후 "일괄 작업을 끝내시겠습니까 (Y/N)?" 를 물어
    입력 상태가 불확실해질 수 있어서, 끝나지 않은 경우는 pane 을 닫는다.
    """
    stop_service(project_dir, service["name"], stop_timeout(service))
    start_service(project_dir, config, service)


def service_status(service, state, child_map, pid_cache=None):
    """pid_cache(pane id → 셸 pid)를 주면 pane 마다 herdr process-info 를 다시 묻지 않는다.

    pane 이 살아 있는 동안 셸 pid 는 바뀌지 않는다.
    """
    pane = find_pane(state, service["name"])
    if not pane:
        return Status.STOPPED
    # herdr process-info 의 foreground 는 Windows 에서 셸만 돌려주므로, 셸의 자식으로 실행 여부를 본다.
    pane_id = pane["pane_id"]
    pid = pid_cache.get(pane_id) if pid_cache is not None else None
    if pid is None:
        pid = shell_pid(pane_id)
        if pid_cache is not None and pid:
            pid_cache[pane_id] = pid
    if not pid or not procs.has_running_children(child_map, pid):
        return Status.STOPPED if pane.get("stopped") else Status.EXITED
    port = service.get("port")
    if port and not procs.is_listening(int(port)):
        return Status.STARTING
    return Status.RUNNING


def service_log(state, name, lines):
    """서비스 pane 의 최근 출력. pane 폭에서 접힌 줄은 원래 한 줄로 받는다(자르는 것은 화면 쪽 몫)."""
    pane = find_pane(state, name)
    if not pane:
        return []
    text = herdr_text("pane", "read", pane["pane_id"], "--lines", lines, "--source", "recent-unwrapped")
    return [line for line in text.splitlines() if line.strip()]


# ---------------------------------------------------------------- project


def start_timeout(service):
    return float(service.get("start_timeout", START_TIMEOUT_SECONDS))


def is_ready(service, state, child_map, pid_cache=None):
    """depends_on 대상으로서 준비됐는지. port 가 열려 있으면 다른 곳에서 띄운 서버여도 준비된 것으로 본다."""
    port = service.get("port")
    if port and procs.is_listening(int(port)):
        return True
    return service_status(service, state, child_map, pid_cache) == Status.RUNNING


class StartPlan:
    """여러 서비스를 depends_on 순서대로 띄우는 계획. step() 을 반복해 호출하면 조금씩 진행한다.

    한 번에 끝까지 기다리지 않는 것은 대시보드가 기다리는 동안에도 입력과 화면 갱신을 계속하기 위해서다.
    결과
      started : 새로 띄운 수
      skipped : 이미 살아 있어서 건드리지 않은 서비스 이름 (실패가 아님)
      failed  : [(이름, 이유 키)] — reason.port_in_use / reason.dependency_failed / reason.timeout
    """

    def __init__(self, project_dir, config, focus=False):
        self.project_dir = project_dir
        self.config = config
        self.focus = focus
        self.by_name = {service["name"]: service for service in config["services"]}
        self.pending = list(config["services"])
        self.begin = time.monotonic()
        self.started = 0
        self.started_at = {}   # 이 계획에서 띄운 서비스 이름 → 띄운 시각
        self.skipped = []      # 이미 살아 있어서 건너뛴 서비스 이름
        self.failed = []
        self.waiting_on = {}   # 시간 초과로 실패한 서비스 이름 → 그때 준비되지 않았던 의존 서비스 이름들

    @property
    def done(self):
        return not self.pending

    def waiting_names(self):
        return {service["name"] for service in self.pending}

    def cancel(self):
        self.pending = []

    def step(self, pid_cache=None):
        state = live_state(self.project_dir, live_pane_ids())
        child_map = procs.child_process_map()
        failed_names = {name for name, _ in self.failed}
        now = time.monotonic()
        for service in list(self.pending):
            dependencies = [self.by_name[name] for name in service.get("depends_on", [])]
            if any(dependency["name"] in failed_names or self._exited(dependency, state, child_map, pid_cache, now)
                   for dependency in dependencies):
                self._fail(service, "reason.dependency_failed")
            elif all(is_ready(dependency, state, child_map, pid_cache) for dependency in dependencies):
                self.pending.remove(service)
                try:
                    if start_service(self.project_dir, self.config, service, focus=self.focus):
                        self.started += 1
                        self.started_at[service["name"]] = time.monotonic()
                    else:  # 이미 살아 있어서 건드리지 않았다 (실패가 아니다)
                        self.skipped.append(service["name"])
                except PortInUseError:
                    self.failed.append((service["name"], "reason.port_in_use"))
            elif now - self.begin > start_timeout(service):
                # 시간 초과 시점에 아직 준비되지 않은 의존 서비스 이름을 남겨, 메시지에서 무엇을 기다렸는지 보이게 한다.
                self.waiting_on[service["name"]] = [dependency["name"] for dependency in dependencies
                                                    if not is_ready(dependency, state, child_map, pid_cache)]
                self._fail(service, "reason.timeout")

    def _exited(self, dependency, state, child_map, pid_cache, now):
        """의존 서비스가 끝나 버렸는지. 막 띄운 서비스는 셸이 명령을 실행하기 전이라 잠깐 '종료됨'으로 보이므로
        STARTUP_GRACE_SECONDS 동안은 실패로 보지 않는다."""
        started_at = self.started_at.get(dependency["name"])
        if started_at is not None and now - started_at < STARTUP_GRACE_SECONDS:
            return False
        return service_status(dependency, state, child_map, pid_cache) == Status.EXITED

    def _fail(self, service, reason):
        self.pending.remove(service)
        self.failed.append((service["name"], reason))

    def failure_text(self):
        return ", ".join(f"{name} ({self._reason_text(name, reason)})" for name, reason in self.failed)

    def _reason_text(self, name, reason):
        waiting = self.waiting_on.get(name)
        if reason == "reason.timeout" and waiting:
            return t("reason.timeout_waiting", names=", ".join(waiting))
        return t(reason)


def up(project_dir, config):
    plan = StartPlan(project_dir, config, focus=True)
    plan.step()
    while not plan.done:
        time.sleep(START_POLL_SECONDS)
        plan.step()
    if plan.failed:
        notify(t("notice.title"), t("notice.not_started", details=plan.failure_text()))
    state = read_state(project_dir)
    if plan.started:
        notify(t("notice.title"), t("notice.started", label=state["label"], count=plan.started))
    elif state and not plan.failed:
        herdr("tab", "focus", state["tab_id"])
        notify(t("notice.title"), t("notice.already_running", label=state["label"]))


def _workspace_is_empty(workspace_id):
    """남은 탭이 없을 때만 space 를 닫는다. 목록을 못 얻으면(이미 닫혔거나 실패) 닫지 않아 다른 탭을 지키지 않는다."""
    listed = herdr("tab", "list", "--workspace", workspace_id, check=False)
    return listed is not None and not listed.get("tabs")


def down(project_dir, quiet=False, config=None):
    state = live_state(project_dir, live_pane_ids())
    if not state:
        if not quiet:
            notify(t("notice.title"), t("notice.nothing_running"))
        return
    # Ctrl+C 로 정상 종료 기회를 주고 끝나기를 기다린 뒤, 탭을 닫아 남은 프로세스를 정리한다.
    services = {service["name"]: service for service in (config or {}).get("services", [])}
    interrupt_and_wait([(pane["pane_id"], stop_timeout(services.get(pane["name"]))) for pane in state["panes"]])
    herdr("tab", "close", state["tab_id"])
    if state.get("workspace_id") and _workspace_is_empty(state["workspace_id"]):
        herdr("workspace", "close", state["workspace_id"], check=False)
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
