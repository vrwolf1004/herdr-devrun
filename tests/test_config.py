import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  (src 경로 준비)
import core


def service(name, **extra):
    return dict({"name": name, "command": "run"}, **extra)


class ReadConfigTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / core.CONFIG_NAME

    def tearDown(self):
        self.folder.cleanup()

    def read(self, data):
        self.path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
        return core.read_config(self.path)

    def assert_error(self, data, fragment):
        with self.assertRaises(core.DevrunError) as caught:
            self.read(data)
        self.assertIn(fragment, str(caught.exception))

    def test_valid(self):
        config = self.read({"services": [service("db"), service("api", depends_on=["db"], stop_timeout=3)]})
        self.assertEqual([each["name"] for each in config["services"]], ["db", "api"])

    def test_bom_is_allowed(self):
        self.path.write_text(json.dumps({"services": [service("a")]}), encoding="utf-8-sig")
        self.assertEqual(core.read_config(self.path)["services"][0]["name"], "a")

    def test_json_error(self):
        self.assert_error('{"services": [}', "JSON error")

    def test_no_services(self):
        self.assert_error({"services": []}, "no services")

    def test_missing_fields(self):
        self.assert_error({"services": [{"name": "a"}]}, "name and command")

    def test_duplicate_name(self):
        self.assert_error({"services": [service("a"), service("a")]}, "duplicate service name: a")

    def test_bad_timeouts(self):
        self.assert_error({"services": [service("a", stop_timeout="10")]}, "stop_timeout of a")
        self.assert_error({"services": [service("a", stop_timeout=True)]}, "stop_timeout of a")
        self.assert_error({"services": [service("a", start_timeout=-1)]}, "start_timeout of a")

    def test_depends_on_type(self):
        self.assert_error({"services": [service("db"), service("api", depends_on="db")]}, "depends_on of api")

    def test_unknown_dependency(self):
        self.assert_error({"services": [service("api", depends_on=["db"])]}, "unknown service: db")

    def test_self_dependency_is_cycle(self):
        self.assert_error({"services": [service("api", depends_on=["api"])]}, "api → api")

    def test_cycle(self):
        self.assert_error({"services": [service("a", depends_on=["c"]), service("b", depends_on=["a"]),
                                        service("c", depends_on=["b"])]}, "a → c → b → a")


class ServiceCommandTest(unittest.TestCase):
    def test_os_override(self):
        entry = service("a", command="./gradlew bootRun", command_windows=r".\gradlew.bat bootRun")
        with mock.patch.object(core, "IS_WINDOWS", True):
            self.assertEqual(core.service_command(entry), r".\gradlew.bat bootRun")
        with mock.patch.object(core, "IS_WINDOWS", False):
            self.assertEqual(core.service_command(entry), "./gradlew bootRun")

    def test_falls_back_to_command(self):
        with mock.patch.object(core, "IS_WINDOWS", True):
            self.assertEqual(core.service_command(service("a", command="npm run dev")), "npm run dev")


class SmallHelpersTest(unittest.TestCase):
    def test_pane_id_of(self):
        self.assertEqual(core.pane_id_of({"root_pane": {"pane_id": "w1:p1"}}), "w1:p1")
        self.assertEqual(core.pane_id_of({"pane": {"pane_id": "w1:p2"}}), "w1:p2")
        with self.assertRaises(core.DevrunError):
            core.pane_id_of({})

    def test_env_args(self):
        self.assertEqual(core.env_args(service("a", env={"A": "1", "B": "x y"})), ["--env", "A=1", "--env", "B=x y"])

    def test_timeouts_default(self):
        self.assertEqual(core.stop_timeout(None), core.STOP_TIMEOUT_SECONDS)
        self.assertEqual(core.stop_timeout(service("a", stop_timeout=3)), 3.0)
        self.assertEqual(core.start_timeout(service("a")), core.START_TIMEOUT_SECONDS)


if __name__ == "__main__":
    unittest.main()
