"""Offline regression tests for the recovered configuration launcher."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import exe_entry

class LauncherConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, {"YKT_HOME": self.tmp.name})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_defaults(self):
        self.assertEqual(exe_entry.read_cfg()["COMPLETION_THRESHOLD"], "90")

    def test_preserves_unknown_keys_and_comments(self):
        p = Path(self.tmp.name) / ".env"
        p.write_text("# personal config\nOTHER_SETTING=keep\nVIDEO_SPEED=1\n", encoding="utf-8")
        exe_entry.save_cfg({"COMPLETION_THRESHOLD":"95", "VIDEO_SPEED":"1.5"})
        value = p.read_text(encoding="utf-8")
        self.assertIn("# personal config", value)
        self.assertIn("OTHER_SETTING=keep", value)
        self.assertIn("VIDEO_SPEED=1.5", value)
        self.assertIn("COMPLETION_THRESHOLD=95", value)

    def test_settings_round_trip(self):
        with patch("builtins.input", side_effect=["4","95","0"]):
            exe_entry.settings()
        self.assertEqual(exe_entry.read_cfg()["COMPLETION_THRESHOLD"], "95")

    def test_invalid_percentage_not_saved(self):
        with patch("builtins.input", side_effect=["4","101","4","nan","0"]):
            exe_entry.settings()
        self.assertEqual(exe_entry.read_cfg()["COMPLETION_THRESHOLD"], "90")

    def test_main_menu_exit_does_not_import_backend(self):
        with patch("builtins.input", return_value="0"):
            exe_entry.main_menu()
        self.assertNotIn("main", __import__("sys").modules)

if __name__=="__main__":
    unittest.main()
