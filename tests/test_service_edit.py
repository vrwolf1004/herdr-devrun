import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  (src 경로 준비)
import core
import panel
from core import Status


def write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


class SaveRemoveTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / core.CONFIG_NAME
        write(self.path, {"tab": "app", "services": [{"name": "db", "command": "run-db"}]})

    def tearDown(self):
        self.folder.cleanup()

    def load(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def test_save_appends_new_service(self):
        core.save_service(self.path, {"name": "api", "command": "run-api", "depends_on": ["db"]})
        self.assertEqual([each["name"] for each in self.load()["services"]], ["db", "api"])

    def test_save_replaces_by_original_name(self):
        core.save_service(self.path, {"name": "db2", "command": "run-db2"}, original_name="db")
        self.assertEqual(self.load()["services"], [{"name": "db2", "command": "run-db2"}])

    def test_invalid_save_leaves_file_unchanged(self):
        before = self.path.read_text(encoding="utf-8")
        with self.assertRaises(core.DevrunError):
            core.save_service(self.path, {"name": "api", "command": "run", "port": 99999})
        self.assertEqual(self.path.read_text(encoding="utf-8"), before)

    def test_remove_strips_dependency(self):
        core.save_service(self.path, {"name": "api", "command": "run-api", "depends_on": ["db"]})
        core.remove_service(self.path, "db")
        self.assertEqual(self.load()["services"], [{"name": "api", "command": "run-api"}])

    def test_remove_last_service_is_rejected(self):
        before = self.path.read_text(encoding="utf-8")
        with self.assertRaises(core.DevrunError):
            core.remove_service(self.path, "db")
        self.assertEqual(self.path.read_text(encoding="utf-8"), before)


class FormTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / core.CONFIG_NAME
        write(self.path, {"services": [{"name": "web", "command": "npm run dev", "env": {"A": "1"},
                                        "stop_timeout": 3}]})
        self.panel = panel.Panel(self.path, None)
        self.panel.reload_config()

    def tearDown(self):
        self.folder.cleanup()

    def services(self):
        return json.loads(self.path.read_text(encoding="utf-8"))["services"]

    def type_text(self, text):
        for char in text:
            self.panel.form_input(FakeEvent(char))

    def enter(self):
        self.panel.form_input(FakeEvent("enter"))

    def press(self, key, times=1):
        for _ in range(times):
            self.panel.form_input(FakeEvent(key))

    def test_add_preset_fills_command_and_skips_optional(self):
        self.panel.start_form("add")
        self.enter()                # 분류: 프론트엔드 (기본)
        self.enter()                # 기술: React (Vite) (기본)
        self.type_text("api")
        self.enter()                # 이름
        self.enter()                # 폴더: 비움 (프로젝트 루트)
        self.enter()                # 명령: 프리셋 값 npm run dev
        self.enter()                # 포트: React 는 고정 포트가 없어 비움
        self.enter()                # URL
        self.enter()                # 의존 서비스
        self.assertIsNone(self.panel.form)
        self.assertEqual(self.services()[-1], {"name": "api", "command": "npm run dev"})

    def test_add_backend_writes_per_os_commands(self):
        with mock.patch.object(core, "IS_WINDOWS", False):
            self.panel.start_form("add")
            self.press("down")      # 분류: 프론트엔드 → 백엔드
            self.enter()
            self.enter()            # 기술: Spring Boot (Gradle)
            self.type_text("api")
            self.enter()
            self.enter()            # 폴더
            self.enter()            # 명령: ./gradlew bootRun (Unix)
            self.enter()            # 포트: 8080
            self.enter()
            self.enter()
        self.assertIsNone(self.panel.form)
        self.assertEqual(self.services()[-1], {"name": "api", "command_windows": "gradlew.bat bootRun",
                                               "command_unix": "./gradlew bootRun", "port": 8080})

    def test_add_other_with_blank_command_keeps_form_and_file(self):
        before = self.path.read_text(encoding="utf-8")
        self.panel.start_form("add")
        self.press("down", 4)       # 분류: 기타
        self.enter()
        self.enter()                # 기술: 직접 입력
        self.type_text("api")
        self.enter()
        self.enter()                # 폴더
        self.type_text("-")
        self.enter()                # 명령을 비움
        for _ in range(3):          # 포트·URL·의존: 마지막 항목 뒤에 검증하므로 끝까지 넘긴다
            self.enter()
        self.assertEqual(self.path.read_text(encoding="utf-8"), before)
        self.assertIsNotNone(self.panel.form)
        self.assertEqual(self.panel.form["index"], 0)
        self.assertEqual(self.panel.form["defaults"]["name"], "api")
        self.assertEqual(self.panel.form["defaults"]["category"], "other")

    def test_add_invalid_port_keeps_file(self):
        before = self.path.read_text(encoding="utf-8")
        self.panel.start_form("add")
        self.enter()
        self.enter()                # 기술: React (Vite)
        self.type_text("api")
        self.enter()
        self.enter()
        self.enter()                # 명령: 프리셋 값 유지
        self.type_text("99999")
        self.enter()                # 포트 99999 → 검증 실패
        self.enter()
        self.enter()
        self.assertEqual(self.path.read_text(encoding="utf-8"), before)
        self.assertIsNotNone(self.panel.form)
        self.assertEqual(self.panel.form["defaults"]["port"], "99999")
        self.assertIn("1 to 65535", self.panel.message)
        self.assertNotIn(str(self.path), self.panel.message)  # 경로는 뺀다 (좁은 안내 줄에서도 이유가 보이게)
        self.assertIn(self.panel.message, self.frame_text())

    def test_edit_defaults_keep_unchanged_fields(self):
        self.panel.start_form("edit", self.panel.services[0])
        self.assertEqual(self.panel.form["defaults"]["command"], "npm run dev")
        for _ in range(6):    # 전부 Enter: 현재 값 유지
            self.enter()
        self.assertIsNone(self.panel.form)
        self.assertEqual(self.services()[0], {"name": "web", "command": "npm run dev", "env": {"A": "1"},
                                              "stop_timeout": 3})

    def test_edit_port_becomes_integer(self):
        self.panel.start_form("edit", self.panel.services[0])
        for _ in range(3):
            self.enter()
        self.type_text("8080")
        self.enter()
        for _ in range(2):
            self.enter()
        self.assertEqual(self.services()[0]["port"], 8080)

    def test_edit_running_service_cannot_be_renamed(self):
        before = self.path.read_text(encoding="utf-8")
        self.panel.statuses["web"] = Status.RUNNING
        self.panel.start_form("edit", self.panel.services[0])
        self.type_text("web2")
        self.enter()
        for _ in range(5):
            self.enter()
        self.assertEqual(self.path.read_text(encoding="utf-8"), before)
        self.assertIsNotNone(self.panel.form)
        self.assertEqual(self.panel.message, panel.t("panel.form.rename_running", name="web"))
        self.assertIn(self.panel.message, self.frame_text())

    def test_notice_shows_above_prompt_while_form_is_open(self):
        self.panel.start_form("add")
        self.press("down", 4)          # 기타
        self.enter()
        self.enter()                   # 직접 입력
        self.type_text("api")
        self.enter()
        self.enter()
        self.type_text("-")
        self.enter()                   # 명령 비움 → 검증 실패
        self.press("enter", 3)
        lines = self.frame_lines()
        self.assertIn(self.panel.message, lines[-2])  # 메시지는 안내 줄 바로 위
        self.assertIn(panel.t("panel.field.category"), lines[-1])  # 맨 아래는 입력 안내

    def test_notice_expires_after_message_seconds(self):
        self.panel.set_message("expired")
        self.panel.message_at -= panel.MESSAGE_SECONDS + 1
        self.assertNotIn("expired", self.frame_text())

    def test_narrow_width_keeps_prompt_and_notice(self):
        self.panel.set_message(panel.t("panel.config_error", error="x" * 200))
        self.panel.start_form("add")
        lines = self.frame_lines(width=24)
        self.assertTrue(lines[-1].strip())

    def test_short_error_drops_config_path(self):
        error = core.DevrunError(f"{self.path} : services 가 없습니다.")
        self.assertEqual(panel.short_error(error, self.path), "services 가 없습니다.")

    def frame_lines(self, width=100):
        captured = []
        with mock.patch.object(panel.term, "size", return_value=(width, 24)), \
                mock.patch.object(panel.term, "write", side_effect=captured.append):
            self.panel.draw()
        text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", "".join(captured))
        return text.replace("\r", "").split("\n")

    def frame_text(self):
        return "\n".join(self.frame_lines())


class FakeEvent:
    kind = "key"

    def __init__(self, key):
        self.key = key


if __name__ == "__main__":
    unittest.main()
