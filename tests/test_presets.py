import unittest

import support  # noqa: F401  (src 경로 준비)
import i18n
import presets


class PresetTableTest(unittest.TestCase):
    def test_every_category_has_a_list(self):
        self.assertEqual(set(presets.PRESETS), set(presets.CATEGORIES))

    def test_category_labels_exist(self):
        for category in presets.CATEGORIES:
            self.assertNotEqual(i18n.t("panel.category." + category), "panel.category." + category)

    def test_each_preset_has_commands_and_valid_port(self):
        for category, items in presets.PRESETS.items():
            ids = [each["id"] for each in items]
            self.assertEqual(len(ids), len(set(ids)), category)
            for each in items:
                with self.subTest(preset=each["id"]):
                    self.assertTrue(each["windows"].strip())
                    self.assertTrue(each["unix"].strip())
                    self.assertIn(each["source"], ("docs", "estimate"))
                    if each["port"] is not None:
                        self.assertIsInstance(each["port"], int)
                        self.assertTrue(1 <= each["port"] <= 65535)

    def test_react_has_no_fixed_port(self):
        self.assertIsNone(presets.find("frontend", "react")["port"])

    def test_find_returns_none_for_custom_or_unknown(self):
        self.assertIsNone(presets.find("other", "custom"))
        self.assertIsNone(presets.find("frontend", "nope"))


if __name__ == "__main__":
    unittest.main()
