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

    def test_key_names_lowercased(self):
        self.assertEqual(bot.normalize_keys(["F1"])[0]["key"], "f1")
        self.assertEqual(bot.normalize_keys([{"key": "F1", "every_sec": 5, "when": "always"}]),
                         [{"key": "f1", "every_sec": 5, "when": "always"}])

    def test_gui_save_failure_is_reported(self):
        import gui
        said = []
        fake = mock.Mock(cfg={"a": 1}, config_path=Path("yok_dizin_xyz") / "config.json")
        with mock.patch.object(bot, "say", said.append):
            gui.App.apply(fake, lambda: None)
        self.assertEqual(len(said), 1)
        self.assertTrue(said[0].startswith("[Uyarı] Ayar kaydedilemedi"))


class DeathSpeechTests(unittest.TestCase):
    def setUp(self):
        self._speak, self._alarm = bot.speak, bot.death_alarm
        self._play = bot.play_sound

    def tearDown(self):
        bot.speak, bot.death_alarm = self._speak, self._alarm
        bot.play_sound = self._play

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

    def test_death_plays_sound_instead_of_speaking(self):
        said, played = [], []
        bot.speak, bot.death_alarm = said.append, lambda: None
        bot.play_sound = lambda p: played.append(p) or True
        with tempfile.TemporaryDirectory() as d:
            mp3 = Path(d) / "ses.mp3"
            mp3.write_bytes(b"x")
            bot.handle_death(bot.BotState(), {"death_sound": str(mp3), "death_say": "x"})
        self.assertEqual(played, [mp3])
        self.assertEqual(said, [])

    def test_missing_sound_falls_back_to_speech(self):
        said, played = [], []
        bot.speak, bot.death_alarm = said.append, lambda: None
        bot.play_sound = lambda p: played.append(p) or True
        with tempfile.TemporaryDirectory() as d:
            bot.handle_death(bot.BotState(), {"death_sound": str(Path(d) / "yok.mp3"),
                                              "death_say": "x"})
        self.assertEqual(said, ["x"])
        self.assertEqual(played, [])

    def test_sound_command_survives_turkish_path(self):
        path = Path("C:/Başlangıç Aşamasında/ses.mp3")
        cmd = bot.sound_command(path)
        self.assertNotIn("Başlangıç", " ".join(cmd))
        b64 = cmd[-1].split("'")[1]
        self.assertEqual(base64.b64decode(b64).decode("utf-8"), str(path))

    def test_play_sound_failure_is_reported(self):
        said = []
        err = subprocess.CalledProcessError(1, "powershell")
        with mock.patch.object(bot.subprocess, "run", side_effect=err),                 mock.patch.object(bot, "say", said.append):
            bot.play_sound(Path("ses.mp3"))
        self.assertEqual(len(said), 1)
        self.assertTrue(said[0].startswith("[Uyarı] Ses çalınamadı"))

    def test_play_sound_returns_false_on_failure(self):
        err = subprocess.CalledProcessError(1, "powershell")
        with mock.patch.object(bot.subprocess, "run", side_effect=err),                 mock.patch.object(bot, "say"):
            self.assertFalse(bot.play_sound(Path("ses.mp3")))

    def test_play_sound_returns_true_on_success(self):
        with mock.patch.object(bot.subprocess, "run"):
            self.assertTrue(bot.play_sound(Path("ses.mp3")))

    def test_unplayable_sound_falls_back_to_speech(self):
        said = []
        bot.speak, bot.death_alarm = said.append, lambda: None
        bot.play_sound = lambda p: False
        with tempfile.TemporaryDirectory() as d:
            mp3 = Path(d) / "ses.mp3"
            mp3.write_bytes(b"x")
            bot.handle_death(bot.BotState(), {"death_sound": str(mp3), "death_say": "x"})
        self.assertEqual(said, ["x"])

    def test_sound_script_exits_when_media_unopenable(self):
        script = bot.sound_command(Path("ses.mp3"))[-1]
        self.assertIn("if (-not $p.NaturalDuration.HasTimeSpan) { exit 1 };", script)
        self.assertLess(script.index("exit 1"), script.index("$p.Play()"))
        self.assertNotIn('"', script)
        self.assertEqual(len(script.split("'")[1]) % 4, 0)


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

    def test_main_loop_uses_new_window_title_next_turn(self):
        state = bot.BotState()
        state.running = True
        cfg = {"window_title": "Eski", "foreground_wait_sec": 0}
        titles = []

        def fake_find(title):
            titles.append(title)
            cfg["window_title"] = "Yeni"   # arayüzde pencere adı değişti
            if len(titles) == 2:
                state.stop_event.set()
            return None

        with mock.patch.object(bot, "find_game_window", side_effect=fake_find), \
                mock.patch.object(bot.mss, "mss"), mock.patch.object(bot, "log_event"), \
                mock.patch.object(bot, "say"):
            bot.main_loop(state, cfg)
        self.assertEqual(titles, ["Eski", "Yeni"])


KEYS =[{"key": "1", "every_sec": 2, "when": "fight"},
        {"key": "f1", "every_sec": 300, "when": "always"}]


if __name__ == "__main__":
    unittest.main()
