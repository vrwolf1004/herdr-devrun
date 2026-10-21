import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  (src 경로 준비)
import core


def service(name, **extra):
    return dict({"name": name, "command": "run"}, **extra)


def write_config(directory, data):
    path = Path(directory) / core.CONFIG_NAME
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class ConfigShapeTest(unittest.TestCase):
    def check(self, data):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(core.DevrunError):
                core.read_config(write_config(directory, data))

    def test_top_level_must_be_object(self):
        self.check([{"name": "a", "command": "run"}])

    def test_services_must_be_list(self):
        self.check({"services": {"name": "a", "command": "run"}})

    def test_service_must_be_object(self):
        self.check({"services": ["a"]})

    def test_port_must_be_integer_in_range(self):
        for port in (0, 65536, "8080", True, 80.5):
            with self.subTest(port=port):
                self.check({"services": [{"name": "a", "command": "run", "port": port}]})

    def test_valid_port_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            config = core.read_config(write_config(directory, {"services": [
                {"name": "a", "command": "run", "port": 8080},
            ]}))
        self.assertEqual(config["services"][0]["port"], 8080)


class StateRecoveryTest(unittest.TestCase):
    def test_corrupt_state_is_dropped_and_read_as_none(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(core, "state_dir", return_value=Path(directory)):
            project = Path(directory) / "proj"
            path = core.state_path(project)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{not json", encoding="utf-8")
            self.assertIsNone(core.read_state(project))
            self.assertFalse(path.exists())

    def test_non_object_state_is_dropped(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(core, "state_dir", return_value=Path(directory)):
            project = Path(directory) / "proj"
            path = core.state_path(project)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("[1, 2]", encoding="utf-8")
            self.assertIsNone(core.read_state(project))

    def test_write_state_is_atomic_and_round_trips(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(core, "state_dir", return_value=Path(directory)):
            project = Path(directory) / "proj"
            core.write_state(project, {"tab_id": "t1", "panes": [{"name": "a", "pane_id": "p1"}]})
            self.assertEqual(core.read_state(project)["panes"], [{"name": "a", "pane_id": "p1"}])
            self.assertFalse(core.state_path(project).with_name(core.state_path(project).name + ".tmp").exists())


class StartFailureCleanupTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.patch_state = mock.patch.object(core, "state_dir", return_value=Path(self.directory.name))
        self.patch_state.start()
        self.project = Path(self.directory.name) / "proj"
        self.project.mkdir()

    def tearDown(self):
        self.patch_state.stop()
        self.directory.cleanup()

    def test_failed_run_in_new_tab_closes_tab_and_removes_state(self):
        calls = []

        def fake_herdr(*args, check=True):
            calls.append(args)
            if args[:2] == ("tab", "create"):
                return {"tab": {"tab_id": "t1"}, "root_pane": {"pane_id": "p1"}}
            return {}

        with mock.patch.object(core, "live_pane_ids", return_value=set()), \
                mock.patch.object(core, "procs") as procs, \
                mock.patch.object(core, "herdr", side_effect=fake_herdr), \
                mock.patch.object(core, "run_in_pane", side_effect=core.DevrunError("run failed")):
            procs.is_listening.return_value = False
            with self.assertRaises(core.DevrunError):
                core.start_service(self.project, {}, service("a"))
        self.assertIn(("tab", "close", "t1"), calls)
        self.assertIsNone(core.read_state(self.project))


if __name__ == "__main__":
    unittest.main()
