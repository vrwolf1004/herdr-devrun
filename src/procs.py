"""프로세스·포트 조회. OS 마다 방법이 다르다.

  child_process_map(): 부모 pid → [(자식 pid, 이름)]
    Windows : CreateToolhelp32Snapshot (ctypes)
    Linux   : /proc/<pid>/stat
    macOS   : ps -A -o pid=,ppid=,comm=
  has_running_children(child_map, pid): 셸 아래에서 서비스가 돌고 있는지
  is_listening(port): localhost 에 TCP 연결이 되는지 (IPv4, IPv6)
"""

import os
import socket
import subprocess
import sys

# 셸 아래에 늘 붙어 있어 "서비스가 돈다"는 근거가 되지 않는 프로세스
_IGNORED_CHILDREN = {"conhost.exe"}
# 자기 아래에 실제 프로세스가 있을 때만 "돈다"고 보는 래퍼.
# Windows 의 .bat(gradlew 등)는 Ctrl+C 후 cmd.exe 만 남아 "일괄 작업을 끝내시겠습니까 (Y/N)?" 를 기다린다.
_WRAPPERS = {"cmd.exe"}


def child_process_map():
    if sys.platform == "win32":
        pairs = _windows_processes()
    elif os.path.isdir("/proc"):
        pairs = _proc_processes()
    else:
        pairs = _ps_processes()
    children = {}
    for pid, parent_pid, name in pairs:
        if pid != parent_pid:  # Windows 의 System Idle Process(0 → 0) 같은 자기 참조 제외
            children.setdefault(parent_pid, []).append((pid, name))
    return children


def has_running_children(child_map, pid, _visited=None):
    visited = _visited if _visited is not None else set()
    visited.add(pid)
    for child_pid, name in child_map.get(pid, []):
        lowered = name.lower()
        if lowered in _IGNORED_CHILDREN or child_pid in visited:
            continue
        if lowered in _WRAPPERS and not has_running_children(child_map, child_pid, visited):
            continue
        return True
    return False


def is_listening(port):
    for host in ("127.0.0.1", "::1"):
        try:
            with socket.create_connection((host, port), timeout=0.05):
                return True
        except OSError:
            continue
    return False


def _windows_processes():
    import ctypes
    from ctypes import wintypes

    th32cs_snapprocess = 0x00000002
    invalid_handle_value = ctypes.c_void_p(-1).value

    class ProcessEntry32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_void_p),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32W)]
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry32W)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    snapshot = kernel32.CreateToolhelp32Snapshot(th32cs_snapprocess, 0)
    if not snapshot or snapshot == invalid_handle_value:
        return []
    pairs = []
    try:
        entry = ProcessEntry32W()
        entry.dwSize = ctypes.sizeof(ProcessEntry32W)
        has_entry = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while has_entry:
            pairs.append((entry.th32ProcessID, entry.th32ParentProcessID, entry.szExeFile))
            has_entry = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return pairs


def _proc_processes():
    pairs = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/stat", encoding="utf-8", errors="replace") as stat_file:
                stat = stat_file.read()
        except OSError:
            continue  # 읽는 사이 끝난 프로세스
        parsed = parse_proc_stat(stat)
        if parsed:
            pairs.append(parsed)
    return pairs


def parse_proc_stat(stat):
    """/proc/<pid>/stat 한 줄 → (pid, ppid, 이름). 형식이 아니면 None.

    형식: pid (comm) state ppid ... — comm 에 공백·괄호가 있을 수 있어 마지막 ')' 기준으로 자른다.
    """
    open_paren, close_paren = stat.find("("), stat.rfind(")")
    if open_paren < 0 or close_paren < open_paren:
        return None
    fields = stat[close_paren + 2:].split()
    pid = stat[:open_paren].strip()
    if not pid.isdigit() or len(fields) < 2 or not fields[1].isdigit():
        return None
    return int(pid), int(fields[1]), stat[open_paren + 1:close_paren]


def _ps_processes():
    output = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,comm="],
                            capture_output=True, text=True, check=False).stdout
    return [parsed for parsed in (parse_ps_line(line) for line in output.splitlines()) if parsed]


def parse_ps_line(line):
    """`ps -o pid=,ppid=,comm=` 한 줄 → (pid, ppid, 이름). 형식이 아니면 None."""
    parts = line.split(None, 2)
    if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
        return int(parts[0]), int(parts[1]), os.path.basename(parts[2])
    return None
