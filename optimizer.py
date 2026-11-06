"""
Otomatik ayar optimizasyonu: botu farklı ayarlarla çalıştırıp dakikada öldürülen mob
sayısını ölçer, her denemeyi kaydeder ve en iyi ayarları config.json'a yazar.

Nasıl çalışır (tepe tırmanma):
- Her denemede en iyi ayarlardan bir (bazen iki) parametre 1-3 adım artırılır ya da azaltılır.
- Bot o ayarla "trial_minutes" dakika çalışır; sadece botun gerçekten çalıştığı süre ölçülür
  (duraklatma ve pencere arka plandayken geçen süre sayılmaz).
- Sonuç en iyiden en az "min_improvement" oranında iyiyse yeni en iyi olur.
- Mob yoğunluğu zamanla değiştiği için en iyi ayar her "recheck_every" denemede bir
  yeniden ölçülür ve skoru ölçümlerin ortalaması olur.
- Üst üste "patience" deneme iyileşme olmazsa durur.

Kayıtlar:
- trials.jsonl     : her deneme (parametre, değer, mob, süre, mob/dk, kabul edildi mi)
- config.backup.json: ilk çalıştırmada config.json'un yedeği
- config.json      : yeni en iyi bulununca ayarlanan parametreler güncellenir
Yeniden başlatınca trials.jsonl okunur ve kalınan yerden devam edilir.

VARSAYIMLAR
- Oyun ve bu script yönetici olarak çalışır (bot.py ile aynı).
- Aynı anda bot.py çalışmıyor.
- Parametre aralıkları güvenli sınırlarda tutuldu (aşağıdaki PARAMS). Spec'teki 0.5 sn kontrol
  aralığı da denenen parametrelerden biridir.
"""

import json
import random
import shutil
import threading
import time
from pathlib import Path

import mss

import bot

HERE = Path(__file__).parent
TRIALS_PATH = HERE / "trials.jsonl"
BACKUP_PATH = HERE / "config.backup.json"

# parametre: (en az, en çok, adım)
PARAMS = {
    "hover_wait_sec": (0.01, 0.05, 0.005),
    "after_click_wait_sec": (0.15, 0.6, 0.05),
    "after_kill_wait_sec": (0.1, 1.0, 0.1),
    "check_interval_sec": (0.2, 0.6, 0.1),
    "no_target_wait_sec": (0.2, 1.5, 0.1),
    "camera_drag_px": (150, 600, 50),
}


# ---------------------------------------------------------------- kayıt

def load_trials():
    """Önceki denemeleri okur."""
    if not TRIALS_PATH.exists():
        return []
    with open(TRIALS_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def append_trial(record):
    """Bir denemeyi dosyaya ekler."""
    with open(TRIALS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def backup_config_once():
    """İlk çalıştırmada config.json'u yedekler."""
    if not BACKUP_PATH.exists():
        shutil.copy(bot.CONFIG_PATH, BACKUP_PATH)


def save_best_to_config(best_params):
    """En iyi parametreleri config.json'a yazar (diğer ayarlara dokunmaz)."""
    cfg = bot.load_config()
    cfg.update(best_params)
    with open(bot.CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------- arama

def tuned_params(cfg):
    """config içinden ayarlanan parametrelerin değerleri."""
    return {name: cfg[name] for name in PARAMS}


def shift_param(params, name, rng):
    """Bir parametreyi 1-3 adım yukarı/aşağı kaydırır (sınırlar içinde kırpar)."""
    low, high, step = PARAMS[name]
    value = params[name] + rng.choice((-1, 1)) * rng.randint(1, 3) * step
    value = round(min(high, max(low, value)), 4)
    return int(value) if isinstance(low, int) else value


def mutate(params, rng):
    """1 (bazen 2) parametreyi değiştirir. Tek adımın etkisi gürültüde kaybolduğu için
    değişiklikler 1-3 adımdır. -> (yeni parametreler, değişen adlar, yeni değerler)"""
    while True:
        names = rng.sample(list(PARAMS), 2 if rng.random() < 0.3 else 1)
        new = dict(params)
        for name in names:
            new[name] = shift_param(params, name, rng)
        if new != params:
            changed = [n for n in names if new[n] != params[n]]
            return new, ", ".join(changed), ", ".join(str(new[n]) for n in changed)


def restore_state(trials, start_params):
    """Kayıtlardan en iyi parametreleri, skor listesini ve sabırsızlık sayacını çıkarır."""
    best_params, best_scores, stale = start_params, [], 0
    for t in trials:
        if t["kind"] == "recheck" or t["accepted"]:
            if t["accepted"]:
                best_params, best_scores = t["params"], []
            best_scores.append(t["kpm"])
        if t["kind"] == "candidate":
            stale = 0 if t["accepted"] else stale + 1
    return best_params, best_scores, stale


# ---------------------------------------------------------------- ölçüm

def reset_counters(state):
    """Deneme başında mob sayacını ve aktif süreyi sıfırlar (ekrandaki istatistikler de)."""
    state.kills = 0
    state.misses = 0
    state.active_total = 0.0
    state.run_since = time.time() if state.running else None


def run_trial(state, sct, cfg, seconds):
    """Botu verilen ayarla 'seconds' aktif saniye çalıştırır -> (öldürülen, aktif süre)."""
    title = cfg["window_title"]
    reset_counters(state)
    kills_before = state.kills
    active = 0.0
    while active < seconds and not state.stop_event.is_set():
        if not state.running:
            state.stop_event.wait(0.2)
            continue
        window = bot.find_game_window(title)
        if window is None or not bot.is_game_foreground(title):
            print(f"[Uyarı] '{title}' penceresi ön planda değil, bekleniyor...")
            state.stop_event.wait(cfg["foreground_wait_sec"])
            continue
        started = time.time()
        bot.bot_step(state, sct, bot.game_area(window), cfg)
        active += time.time() - started
    return state.kills - kills_before, active


def kills_per_minute(kills, active_sec):
    """Aktif süreye göre dakikada mob."""
    return kills / (active_sec / 60) if active_sec > 0 else 0.0


def average(values):
    return sum(values) / len(values) if values else 0.0


# ---------------------------------------------------------------- ana akış

def measure(state, sct, base_cfg, params, opt):
    """Parametrelerle bir deneme koşturur -> (mob, aktif sn, mob/dk) ya da yarıda kaldıysa None."""
    cfg = {**base_cfg, **params}
    kills, active = run_trial(state, sct, cfg, opt["trial_minutes"] * 60)
    if active < opt["trial_minutes"] * 60 * 0.9:
        return None   # End / ölüm ile yarıda kaldı, sonuç güvenilmez
    return kills, active, kills_per_minute(kills, active)


def optimize(state, base_cfg, opt):
    """Durdurulana ya da iyileşme bitene kadar deneme yapar."""
    rng = random.Random()
    trials = load_trials()
    best_params, best_scores, stale = restore_state(trials, tuned_params(base_cfg))
    if stale >= opt["patience"]:
        print("Önceki arama bitmişti; en iyi ayardan yeni bir tur başlıyor.")
        stale = 0
    trial_no = len(trials)
    with mss.mss() as sct:
        while not state.stop_event.is_set() and stale < opt["patience"]:
            recheck = not best_scores or trial_no % opt["recheck_every"] == 0
            if recheck:
                params, name, value = best_params, None, None
            else:
                params, name, value = mutate(best_params, rng)
            label = "En iyi ayar ölçülüyor" if recheck else f"Deneme: {name} = {value}"
            print(f"\n=== #{trial_no + 1} {label} ({opt['trial_minutes']} dk) ===")

            result = measure(state, sct, base_cfg, params, opt)
            if result is None:
                print("Deneme yarıda kaldı, kaydedilmedi.")
                break
            kills, active, kpm = result
            best_now = average(best_scores)
            accepted = (not recheck and best_scores
                        and kpm >= best_now * (1 + opt["min_improvement"]))
            if recheck:
                best_scores.append(kpm)
            elif accepted:
                best_params, best_scores, stale = params, [kpm], 0
                save_best_to_config(best_params)
            else:
                stale += 1

            trial_no += 1
            append_trial({
                "trial": trial_no, "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "kind": "recheck" if recheck else "candidate",
                "param": name, "value": value, "params": params,
                "kills": kills, "active_sec": round(active, 1), "kpm": round(kpm, 3),
                "accepted": bool(accepted), "best_kpm": round(average(best_scores), 3),
            })
            verdict = "YENİ EN İYİ, config.json güncellendi" if accepted else (
                "en iyi yeniden ölçüldü" if recheck else "daha iyi değil")
            print(f"Sonuç: {kills} mob, {kpm:.2f} mob/dk -> {verdict} | "
                  f"en iyi ortalama: {average(best_scores):.2f} mob/dk | "
                  f"iyileşmesiz deneme: {stale}/{opt['patience']}")

    print(f"\nOptimizasyon bitti. En iyi: {average(best_scores):.2f} mob/dk")
    print("En iyi ayarlar:", json.dumps(best_params, ensure_ascii=False))


def main():
    bot.make_dpi_aware()
    backup_config_once()
    base_cfg = bot.load_config()
    opt = base_cfg["optimizer"]
    state = bot.BotState()
    threading.Thread(target=bot.hotkey_loop, args=(state,), daemon=True).start()
    print("Optimizasyon hazır. F11: başlat/duraklat | End: durdur")
    print(f"Her deneme {opt['trial_minutes']} dk. Kayıtlar: {TRIALS_PATH}")
    try:
        optimize(state, base_cfg, opt)
    except KeyboardInterrupt:
        state.stop_event.set()


if __name__ == "__main__":
    main()
