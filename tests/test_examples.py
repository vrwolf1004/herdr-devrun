import json
import unittest
from pathlib import Path

import support  # noqa: F401  (src 경로 준비)
import core

EXAMPLES = Path(__file__).resolve().parents[1] / "docs" / "examples"


class ExampleConfigTest(unittest.TestCase):
    def examples(self):
        files = sorted(EXAMPLES.glob("ex_*.json"))
        self.assertTrue(files)
        return files

    def test_every_example_passes_validation(self):
        for path in self.examples():
            with self.subTest(path=path.name):
                core.read_config(path)

    def test_examples_use_placeholder_paths_only(self):
        # 사용자가 자기 경로만 고치도록 cwd 는 C:/path/to/ 자리표시자이거나 비워 둔다.
        for path in self.examples():
            config = json.loads(path.read_text(encoding="utf-8"))
            for service in config["services"]:
                with self.subTest(path=path.name, service=service["name"]):
                    self.assertTrue(service.get("cwd", "C:/path/to/").startswith("C:/path/to/"))


if __name__ == "__main__":
    unittest.main()
