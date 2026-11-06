"""GUI desteği testleri (say kuyruğu, save_config). Çalıştırma: python -m unittest discover tests"""

import base64
import sys
import tempfile
import subprocess
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bot  # noqa: E402
import settings_rules as rules  # noqa: E402


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


class DeathSpeechTests(unittest.TestCase):
    def setUp(self):
        self._speak, self._alarm = bot.speak, bot.death_alarm

    def tearDown(self):
        bot.speak, bot.death_alarm = self._speak, self._alarm

    def test_death_speaks_message(self):
        said = []
        bot.speak, bot.death_alarm = said.append, lambda: None
        s = bot.BotState()
        bot.handle_death(s, {"death_say": "Sen bir malsın Fethi"})
        self.assertEqual(said, ["Sen bir malsın Fethi"])
        self.assertTrue(s.dead and s.stop_event.is_set())

    def test_empty_message_is_silent(self):
        said = []
        bot.speak, bot.death_alarm = said.append, lambda: None
        s = bot.BotState()
        bot.handle_death(s, {"death_say": ""})
        bot.handle_death(s, {})
        self.assertEqual(said, [])

    def test_speech_command_survives_quotes(self):
        cmd = bot.speech_command("Fethi'nin \"malı\"")
        self.assertNotIn("Fethi", " ".join(cmd))
        b64 = cmd[-1].split("'")[1]
        self.assertEqual(base64.b64decode(b64).decode("utf-8"), "Fethi'nin \"malı\"")

    def test_speak_failure_is_reported(self):
        said = []
        err = subprocess.CalledProcessError(1, "powershell")
        with mock.patch.object(bot.subprocess, "run", side_effect=err),                 mock.patch.object(bot, "say", said.append):
            bot.speak("merhaba")
        self.assertEqual(len(said), 1)
        self.assertTrue(said[0].startswith("[Uyarı] Konuşma çalışmadı"))


class SettingsRulesTests(unittest.TestCase):
    def test_valid_values(self):
        self.assertEqual(rules.parse_seconds("2.5"), 2.5)
        self.assertEqual(rules.parse_seconds(" 0 "), 0.0)
        self.assertEqual(rules.parse_radius("50"), 50)
        self.assertEqual(rules.parse_key(" F1 "), "f1")
        self.assertEqual(rules.parse_key("TAB"), "tab")
        self.assertEqual(rules.parse_title("  Legends  "), "Legends")

    def test_invalid_values(self):
        for fn, bad in [(rules.parse_seconds, "-1"), (rules.parse_seconds, "abc"),
                        (rules.parse_seconds, "nan"), (rules.parse_seconds, "inf"),
                        (rules.parse_radius, "0"), (rules.parse_radius, "5.5"),
                        (rules.parse_radius, "nan"), (rules.parse_radius, "inf"),
                        (rules.parse_key, ""), (rules.parse_key, "uzay"),
                        (rules.parse_title, "  ")]:
            with self.subTest(bad):
                with self.assertRaises(ValueError):
                    fn(bad)


KEYS = [{"key": "1", "every_sec": 2, "when": "fight"},
        {"key": "f1", "every_sec": 300, "when": "always"}]


if __name__ == "__main__":
    unittest.main()
