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

    def test_due_keys_respects_interval(self):
        s = bot.BotState()
        self.assertEqual(bot.due_keys(s, KEYS, True, 100.0), ["1", "f1"])
        self.assertEqual(bot.due_keys(s, KEYS, True, 101.0), [])
        self.assertEqual(bot.due_keys(s, KEYS, True, 102.0), ["1"])

    def test_fight_keys_not_pressed_outside_fight(self):
        s = bot.BotState()
        self.assertEqual(bot.due_keys(s, KEYS, False, 100.0), ["f1"])

    def test_zero_interval_always_due(self):
        s = bot.BotState()
        k = [{"key": "1", "every_sec": 0, "when": "fight"}]
        self.assertEqual(bot.due_keys(s, k, True, 100.0), ["1"])
        self.assertEqual(bot.due_keys(s, k, True, 100.0), ["1"])

    def test_old_list_format(self):
        self.assertEqual(bot.normalize_keys(["1", "2"]),
                         [{"key": "1", "every_sec": 0, "when": "fight"},
                          {"key": "2", "every_sec": 0, "when": "fight"}])
        self.assertEqual(bot.normalize_keys(KEYS), KEYS)


KEYS = [{"key": "1", "every_sec": 2, "when": "fight"},
        {"key": "f1", "every_sec": 300, "when": "always"}]


if __name__ == "__main__":
    unittest.main()
