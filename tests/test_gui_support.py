"""GUI desteği testleri (say kuyruğu, save_config). Çalıştırma: python -m unittest discover tests"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bot  # noqa: E402


class GuiSupportTests(unittest.TestCase):
    def test_say_prints_and_queues(self):
        while not bot.messages.empty():
            bot.messages.get_nowait()
        bot.say("Mob öldü #1")
        self.assertEqual(bot.messages.get_nowait(), "Mob öldü #1")

    def test_save_config_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "c.json"
            bot.save_config({"death_say": "Sen bir malsın Fethi"}, path)
            self.assertEqual(bot.load_config(path), {"death_say": "Sen bir malsın Fethi"})
            self.assertIn("malsın", path.read_text(encoding="utf-8"))  # ensure_ascii=False


if __name__ == "__main__":
    unittest.main()
