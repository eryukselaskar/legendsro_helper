"""Alanda kalma testleri. Çalıştırma: python -m unittest discover tests"""

import math
import time
import sys
import unittest
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bot  # noqa: E402

FIXTURES = Path(__file__).with_name("fixtures")


def load(path):
    """cv2.imread Türkçe karakterli yolları açamaz; byte olarak okuyup çözer."""
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)


class ReadCoordsTest(unittest.TestCase):
    def test_reads_minimap_coordinates(self):
        # Dosya adı beklenen değeri taşır: coords_<x>_<y>.png
        files = [p for p in FIXTURES.glob("coords_*.png") if p.stem != "coords_none"]
        self.assertGreater(len(files), 0)
        for path in files:
            x, y = path.stem.split("_")[1:]
            with self.subTest(path.name):
                pixels = load(path)
                self.assertEqual(bot.parse_coords(pixels), (int(x), int(y)))

    def test_no_coordinates_returns_none(self):
        # Mağara gibi yerlerde minimap altında koordinat yazmaz.
        pixels = load(FIXTURES / "coords_none.png")
        self.assertIsNone(bot.parse_coords(pixels))


class WalkOffsetTest(unittest.TestCase):
    def test_learns_camera_rotation(self):
        # Ekranda sağa (0 rad) tıklandı, karakter dünyada kuzeye (+Y) yürüdü:
        # kamera 90 derece dönmüş demektir.
        offset = bot.learned_offset((0, 0), (0, 10), screen_angle=0.0)
        self.assertAlmostEqual(offset, math.pi / 2)


class StuckTest(unittest.TestCase):
    CFG = {"stuck_sec": 6, "kill_min_damage": 0.02}

    def test_no_damage_for_too_long_is_stuck(self):
        # Karakter duvara takıldı: 7 sn geçti, mob'un HP'si hiç düşmedi.
        self.assertTrue(bot.is_stuck(1.0, 1.0, 7, self.CFG))

    def test_damage_dealt_is_not_stuck(self):
        self.assertFalse(bot.is_stuck(1.0, 0.9, 7, self.CFG))

    def test_still_running_to_mob_is_not_stuck(self):
        self.assertFalse(bot.is_stuck(1.0, 1.0, 3, self.CFG))


class FightStallTest(unittest.TestCase):
    def test_hp_drops_then_stalls_is_stuck(self):
        # Logdaki 40 sn'lik timeout: mob'un HP'si önce düştü, sonra hiç değişmedi.
        readings = iter([1.0, 0.8] + [0.8] * 1000)
        originals = (bot.read_target, bot.is_game_foreground)
        bot.read_target = lambda *a: (True, next(readings))
        bot.is_game_foreground = lambda title: True
        try:
            cfg = bot.load_config()
            cfg.update(stuck_sec=0.2, check_interval_sec=0.01, fight_timeout_sec=3,
                       skill_keys=[])
            cfg["zerk"]["enabled"] = False
            state = bot.BotState()
            state.running = True
            self.assertEqual(bot.fight(state, None, None, cfg), "stuck")
        finally:
            bot.read_target, bot.is_game_foreground = originals


class SlowKillTest(unittest.TestCase):
    def test_hp_keeps_dropping_is_not_abandoned(self):
        # 01:49'daki durum: güçlü mob'un HP'si sürekli düşüyordu ama 40 sn'de bitmedi,
        # bot %8,7'de bıraktı. HP düştüğü sürece dövüş sürmeli.
        readings = iter([1.0 - i * 0.05 for i in range(21)] + [0.0])
        originals = (bot.read_target, bot.is_game_foreground)
        bot.read_target = lambda *a: (True, max(next(readings), 0.0))
        bot.is_game_foreground = lambda title: True
        try:
            cfg = bot.load_config()
            cfg.update(stuck_sec=1, check_interval_sec=0.02, skill_keys=[])
            cfg["zerk"]["enabled"] = False
            cfg["fight_timeout_sec"] = 0.1   # eski süre sınırı; artık dövüşü kesmemeli
            state = bot.BotState()
            state.running = True
            self.assertEqual(bot.fight(state, None, None, cfg), "killed")
        finally:
            bot.read_target, bot.is_game_foreground = originals


class CursorResetTest(unittest.TestCase):
    def test_every_hover_clicked_and_failed_resets_cursor(self):
        # 01:23'teki durum: her noktada "mob var" denip tıklandı, hiçbiri hedef vermedi.
        # Önbellekteki normal imleç bozuk demektir; sıfırlanmalı.
        names = ("grab_area", "find_name_labels", "is_game_foreground", "move_mouse",
                 "stable_cursor", "click_mouse", "locate_target_bar", "log_event")
        originals = {n: getattr(bot, n) for n in names}
        bot.grab_area = lambda *a: None
        bot.find_name_labels = lambda *a: [(1000, 500, 60, 12), (1400, 700, 60, 12)]
        bot.is_game_foreground = lambda title: True
        bot.move_mouse = lambda x, y: None
        bot.stable_cursor = lambda cfg: 9   # normal imleçten (123) farklı: "mob var"
        bot.click_mouse = lambda *a: None
        bot.locate_target_bar = lambda *a: None
        bot.log_event = lambda *a, **k: None
        try:
            cfg = bot.load_config()
            cfg.update(after_click_wait_sec=0, bad_spot_radius_px=1)
            cfg["miss_shots"]["enabled"] = False
            state = bot.BotState()
            state.running = True
            state.normal_cursor, state.normal_cursor_at = 123, time.time()
            window = bot.types.SimpleNamespace(left=0, top=0, width=2560, height=1440)
            self.assertEqual(bot.select_target(state, None, window, cfg), "missed")
            self.assertIsNone(state.normal_cursor)
        finally:
            for n, f in originals.items():
                setattr(bot, n, f)


class WalkNoGroundTest(unittest.TestCase):
    def test_no_ground_resets_cursor_and_waits(self):
        # 01:32'deki durum: bayat imleç yüzünden her nokta "mob" göründü, geri yürüme
        # hemen vazgeçti ve bekleme olmadan 113 kez tekrarlandı.
        names = ("read_coords", "is_game_foreground", "hover_shows_mob", "log_event", "wait")
        originals = {n: getattr(bot, n) for n in names}
        waits = []
        bot.read_coords = lambda *a: (80, 0)
        bot.is_game_foreground = lambda title: True
        bot.hover_shows_mob = lambda *a: True
        bot.log_event = lambda *a, **k: None
        bot.wait = lambda state, seconds, cfg: waits.append(seconds)
        try:
            cfg = bot.load_config()
            state = bot.BotState()
            state.running = True
            state.home = (0, 0)
            state.normal_cursor, state.normal_cursor_at = 123, time.time()
            window = bot.types.SimpleNamespace(left=0, top=0, width=2560, height=1440)
            self.assertTrue(bot.keep_in_area(state, None, window, cfg))
            self.assertIsNone(state.normal_cursor)
            self.assertEqual(waits, [cfg["area"]["no_ground_wait_sec"]])
        finally:
            for n, f in originals.items():
                setattr(bot, n, f)


class ZerkTest(unittest.TestCase):
    # Zerk dolunca portrenin üstünde büyük küre belirir (karaktere göre pembe ya da mavi).
    def test_full_zerk_pink_and_blue(self):
        cfg = bot.load_config()
        for name in ("zerk_full_pink", "zerk_full_blue"):
            with self.subTest(name):
                self.assertTrue(bot.zerk_ready(load(FIXTURES / f"{name}.png"), cfg))

    def test_partial_zerk_is_not_ready(self):
        cfg = bot.load_config()
        self.assertFalse(bot.zerk_ready(load(FIXTURES / "zerk_partial.png"), cfg))


class AttackCursorTest(unittest.TestCase):
    """Oyuncu ve item üstünde imleç de normalden farklıdır. Mob öldürülünce o anki imleç
    saldırı imleci olarak öğrenilir; sonra sadece o imleçte tıklanır."""

    def setUp(self):
        names = ("move_mouse", "stable_cursor", "click_mouse", "locate_target_bar", "log_event")
        self.originals = {n: getattr(bot, n) for n in names}
        self.clicks = []
        bot.log_event = lambda *a, **k: None   # gerçek bot_log.jsonl'a yazmasın
        bot.move_mouse = lambda x, y: None
        bot.click_mouse = lambda *a: self.clicks.append(1)
        bot.locate_target_bar = lambda *a: {"x": 1, "y": 1, "width": 200}
        self.cfg = bot.load_config()
        self.cfg.update(after_click_wait_sec=0)
        self.cfg["miss_shots"]["enabled"] = False
        self.window = bot.types.SimpleNamespace(left=0, top=0, width=2560, height=1440)

    def tearDown(self):
        for n, f in self.originals.items():
            setattr(bot, n, f)

    def click_with_cursor(self, state, cursor):
        bot.stable_cursor = lambda cfg: cursor
        return bot.try_click_mob(state, None, self.window, 500, 500, 1, self.cfg)

    def test_other_cursor_is_not_clicked_once_attack_cursor_known(self):
        state = bot.BotState()
        state.attack_cursors = {7}
        self.assertFalse(self.click_with_cursor(state, 9))   # oyuncu / item imleci
        self.assertEqual(self.clicks, [])
        self.assertTrue(self.click_with_cursor(state, 7))    # saldırı imleci
        self.assertEqual(self.clicks, [1])

    def test_any_non_normal_cursor_clicked_until_learned(self):
        state = bot.BotState()
        self.assertTrue(self.click_with_cursor(state, 9))
        self.assertEqual(state.attack_cursors, set())        # seçmek yetmez, ölmesi lazım
        bot.learn_attack_cursor(state)                       # mob öldü
        self.assertEqual(state.attack_cursors, {9})


class TargetBarTest(unittest.TestCase):
    """Hedef penceresi kapatma (X) düğmesinden bulunur; canı az mob'lar da tanınmalı.
    Örnekler ekranın x=1000..1500, y=0..110 parçası; bar x=180, y=46'da."""

    def test_mob_bars_found_at_any_hp(self):
        cfg = bot.load_config()
        for name in ("target_full", "target_low16", "target_low8", "target_low5"):
            with self.subTest(name):
                self.assertEqual(bot.find_target_bar(load(FIXTURES / f"{name}.png"), cfg),
                                 (180, 46))

    def test_player_pet_and_empty_are_not_mobs(self):
        # Oyuncu ve pet pencerelerinde de X düğmesi var ama HP barı yok.
        cfg = bot.load_config()
        for name in ("target_player", "target_player_buffs", "target_trader", "target_pet",
                     "target_none"):
            with self.subTest(name):
                self.assertIsNone(bot.find_target_bar(load(FIXTURES / f"{name}.png"), cfg))


class PartyTest(unittest.TestCase):
    """Bizim hasarımız görülmeden kaybolan hedef sayılmaz. Canı az mob atlanmaz: kendi alan
    hasarımız da can düşürür."""

    def setUp(self):
        names = ("player_dead", "select_target", "read_target", "fight", "log_event", "wait")
        self.originals = {n: getattr(bot, n) for n in names}
        self.fights = []
        bot.player_dead = lambda *a: False
        bot.log_event = lambda *a, **k: None
        bot.wait = lambda *a: None
        self.cfg = bot.load_config()
        self.cfg["area"]["enabled"] = False
        self.window = bot.types.SimpleNamespace(left=0, top=0, width=2560, height=1440)
        self.state = bot.BotState()
        self.state.running = True

        def select(state, *a):
            state.target_bar, state.last_click = {"x": 1, "y": 1, "width": 200}, (500, 500)
            return "selected"
        bot.select_target = select

    def tearDown(self):
        for n, f in self.originals.items():
            setattr(bot, n, f)

    def test_low_hp_target_is_still_fought(self):
        bot.read_target = lambda *a: (True, 0.3)
        bot.fight = lambda *a: self.fights.append(1) or "killed"
        bot.bot_step(self.state, None, self.window, self.cfg)
        self.assertEqual(self.fights, [1])

    def test_lost_target_is_not_counted(self):
        bot.read_target = lambda *a: (True, 0.95)
        bot.fight = lambda *a: "lost"
        bot.bot_step(self.state, None, self.window, self.cfg)
        self.assertEqual(self.state.kills, 0)
        self.assertFalse(hasattr(self.state, "party_kills"))


class MissShotTest(unittest.TestCase):
    def test_saves_marked_crop_and_stops_at_limit(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            cfg = {"miss_shots": {"enabled": True, "folder": folder, "max_files": 2}}
            crop = np.zeros((200, 200, 4), dtype=np.uint8)
            for _ in range(3):
                bot.save_miss_shot(crop, cfg)
            files = sorted(Path(folder).glob("*.png"))
            self.assertEqual(len(files), 2)          # sınırdan fazla dosya yazılmaz
            img = load(files[0])
            self.assertEqual(img.shape[:2], (200, 200))
            self.assertTrue(img[100, 100].any())     # tıklama noktası işaretli


if __name__ == "__main__":
    unittest.main()
