import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  (src 경로 준비)
import core
import devrun


class OpenPanelTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.project = Path(self.directory.name)
        self.marker = self.project / "panel.marker"
        self.panes = {}         # pane get 으로 돌려줄 pane 정보
        self.live = []          # pane list 로 돌려줄 pane 정보
        self.calls = []
        self.state = None
        patches = [
            mock.patch.object(core, "panel_marker_path", return_value=self.marker),
            mock.patch.object(core, "live_pane_ids", side_effect=lambda: {each["pane_id"] for each in self.live}),
            mock.patch.object(core, "live_state", side_effect=lambda *_: self.state),
            mock.patch.object(core, "herdr", side_effect=self.herdr),
            mock.patch.dict(os.environ, {"HERDR_PANE_ID": "cur"}),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.addCleanup(self.directory.cleanup)

    def herdr(self, *args, check=True):
        self.calls.append(args)
        if args[:2] == ("pane", "get"):
            pane = self.panes.get(args[2])
            return {"pane": pane} if pane else None
        if args[:2] == ("pane", "list"):
            return {"panes": self.live}
        if args[:2] == ("pane", "split"):
            return {"pane": {"pane_id": "new"}}
        return {}

    def splits(self):
        return [call for call in self.calls if call[:2] == ("pane", "split")]

    def runs(self):
        return [call for call in self.calls if call[:2] == ("pane", "run")]

    def test_splits_next_to_first_service_pane(self):
        self.state = {"tab_id": "t1", "panes": [{"name": "web", "pane_id": "s1"}]}
        self.live = [{"pane_id": "s1", "tab_id": "t1"}]
        devrun.open_panel(self.project)
        self.assertEqual(self.splits()[0][2], "s1")
        self.assertEqual(self.runs()[0][2], "new")
        self.assertEqual(self.marker.read_text(encoding="utf-8"), "new")

    def test_without_services_splits_current_pane(self):
        devrun.open_panel(self.project)
        self.assertEqual(self.splits()[0][2], "cur")
        self.assertEqual(self.marker.read_text(encoding="utf-8"), "new")

    def test_other_tab_dashboard_is_closed_and_reopened_by_service_tab(self):
        self.marker.write_text("old", encoding="utf-8")
        self.panes = {"old": {"pane_id": "old", "tab_id": "t2"}}
        self.state = {"tab_id": "t1", "panes": [{"name": "web", "pane_id": "s1"}]}
        self.live = [{"pane_id": "s1", "tab_id": "t1"}]
        devrun.open_panel(self.project)
        self.assertIn(("pane", "close", "old"), self.calls)
        self.assertEqual(self.splits()[0][2], "s1")
        self.assertEqual(self.marker.read_text(encoding="utf-8"), "new")

    def test_dashboard_already_in_service_tab_is_focused(self):
        self.marker.write_text("old", encoding="utf-8")
        self.panes = {"old": {"pane_id": "old", "tab_id": "t1"}}
        self.state = {"tab_id": "t1", "panes": [{"name": "web", "pane_id": "s1"}]}
        self.live = [{"pane_id": "s1", "tab_id": "t1"}]
        devrun.open_panel(self.project)
        self.assertIn(("tab", "focus", "t1"), self.calls)
        self.assertEqual(self.splits(), [])
        self.assertNotIn(("pane", "close", "old"), self.calls)

    def test_service_tab_without_live_service_pane_splits_inside_that_tab(self):
        # 서비스 pane 이 모두 닫혔어도 탭이 남아 있으면 대시보드는 그 탭 안에 열린다.
        # 사이드바 pane 은 앞에 있어도 앵커로 쓰지 않는다.
        self.state = {"tab_id": "t1", "panes": []}
        self.live = [{"pane_id": "side", "tab_id": "t1", "label": "Sidebar"},
                     {"pane_id": "x1", "tab_id": "t1"}, {"pane_id": "cur", "tab_id": "t2"}]
        devrun.open_panel(self.project)
        self.assertEqual(self.splits()[0][2], "x1")


if __name__ == "__main__":
    unittest.main()
