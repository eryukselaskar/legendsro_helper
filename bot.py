"""
Legend Online (Silkroad Online private sunucu) için ekran okuyan bot.
Oyun client'ına müdahale etmez, paket okumaz; sadece ekranı yakalar, tuş ve fare girdisi gönderir.

VARSAYIMLAR
- Pencere başlığı "Legends Online" (oyun penceresi "KarakterAdı [Legends Online]"). Farklıysa config.json'da
  "window_title" değerini değiştir. Başlığın bir parçası yeterli.
- Bütün koordinatlar oyunun İÇ alanına (başlık çubuğu ve kenarlık hariç) göredir. Oyunun
  arayüzü bu alanın köşelerine sabit piksellerle bağlı; bu yüzden pencere taşınsa, kenarlıksız
  moda geçse ya da büyüse de karakter HP barı aynı yerde kalır. Ölçüm 2560x1440 kenarlıksız
  pencerede yapıldı.
- Hedef penceresinin yeri sabit değil (oyunda yer değiştiriyor). Bot her yeni hedefte üst
  şeritte ("target_search" bölgesi) hedef penceresinin kapatma (X) düğmesini arar
  (templates/target_close.png); bar düğmeye göre sabit yerdedir ("target_close" dx/dy). Bar
  kırmızıyla başlayıp koyu griyle devam ediyorsa mob'dur (canı az da olsa); oyuncu/pet
  pencerelerinde bar yoktur. Düğme bulunamazsa eski yöntem: en az 40 px kırmızı çizgi.
  config'deki target_bar'dan sadece "width" kullanılır.
- Windows ölçekleme (DPI) %100 değilse de doğru piksel okunsun diye süreç DPI-aware yapılır.
- Hedef HP barı ve karakter HP barı kırmızıdır; ikisi de aynı renk eşiğiyle okunur
  (R>150, G<70, B<70). Farklıysa "red_color" ayarını değiştir.
- Oyunda en yakın mobu seçen tuş yok. Mob'ların üstünde adları beyaz yazıyla durur. Bot
  ekrandaki beyaz isim etiketlerini bulur, karaktere en yakından başlayarak etiketin altındaki
  gövdeye fareyi getirir; imleç saldırı imlecine dönerse tıklar ve hedef barını doğrular.
- Karakter pencerenin ortasında durur (oyun kamerası karakteri ortalar). Kendi adı ortanın
  "self_label" kadar ötesindedir (ölçülen: 22 px sağ, 66 px yukarı); oraya en yakın TEK etiket
  atlanır (kendine tıklamak "Invalid target" verir). Dibe gelen mob'lar atlanmaz.
- Arayüz bölgeleri ("ui_margins": paneller, minimap, chat, skill barları) etiket aramasından
  çıkarılır; böylece chat yazıları mob sanılmaz.
- "Normal" imleç, fare karakter HP barının (arayüz) üzerindeyken okunan imleçtir.
- Mob'a tek sol tıklama onu seçer; oyunun otomatik saldırısı açık, karakter kendi saldırır.
- Oyunun otomatik HP/MP pot sistemi açık. Bot pot basmaz, loot almaz.
- skill_keys varsayılan boş: bot hiçbir tuşa basmaz. Doldurursan (ör. ["1", "2", "3"])
  her kontrol turunda sıradaki tuşa basılır.
- Ekranda isim etiketi yoksa ya da üst üste "misses_before_rotate" arama sonuçsuz kalırsa sağ tuş
  basılı sürüklenerek kamera döndürülür. 300 px sürüklemenin kaç
  derece döndürdüğü bilinmiyor; "camera_drag_px" ile ayarlanır.
- Alanda kalma ("area"): F11 ile başlatıldığı yer başlangıç noktasıdır. Konum minimap altındaki
  "X:.. Y:.." yazısından okunur ("coords_text", pencerenin SAĞ kenarına göre). Karakter "radius"
  birimden fazla uzaklaşınca ortadan "walk_click_px" uzağa yere tıklayarak geri yürür. Kamera
  açısı bilinmediği için ilk adımda karakterin gerçekte nereye gittiğine bakıp yönü düzeltir.
  Koordinat yazısı olmayan yerlerde (ör. mağara) bu özellik kendiliğinden devre dışı kalır.
- Takılma: seçilen hedefin HP'si "stuck_sec" içinde hiç düşmezse (duvar, yol yok, saldırılamayan
  hedef) bot onu bırakır, o mob'u kısa süre atlar; üst üste "stuck_before_rotate" kez olursa
  kamerayı döndürür.
- Zerk ("zerk"): dövüş sırasında portrenin üstündeki büyük zerk küresi belirince (5 küre
  dolunca çıkar) "key" tuşuna (varsayılan Tab) basılır.
- Saldırı imleci: oyuncu ve yerdeki item üstünde de imleç değişir. Bir mob öldürülünce onu
  seçerken görülen imleç öğrenilir ve sonra sadece o imleçte tıklanır. Üst üste sonuçsuz
  aramada kamera dönerken öğrenilenler unutulur (oyun imleci değiştirirse takılmasın).
- Boşa giden her mob tıklamasının 200x200 görüntüsü (tıklama noktası yeşil artı ile işaretli)
  "miss_shots" klasörüne (varsayılan "misses") kaydedilir; "max_files" dolunca durur.
- Bir aramada fare en fazla "max_hovers_per_search" noktaya götürülür (log'a göre başarılı
  aramaların %95'i ilk 12 noktada hedef buluyor); sonrası boşa giden arama sayılır.
- Her arama ve dövüş bot_log.jsonl'a yazılır (süre, fare gezdirme, tıklama, sonuç).
- Bot çalışırken fareyi kullanma; bot fareyi kendisi hareket ettirir.
- F11 / End kısayolları global olarak okunur (oyun ön plandayken de çalışır).
"""

import ctypes
import ctypes.wintypes as wt
import json
import math
import queue
import random
import re
import threading
import time
import types
import winsound
from pathlib import Path

import cv2
import mss
import numpy as np
import pydirectinput
import pygetwindow as gw

CONFIG_PATH = Path(__file__).with_name("config.json")
LOG_PATH = Path(__file__).with_name("bot_log.jsonl")

VK_F11 = 0x7A
VK_END = 0x23

# pydirectinput her çağrıdan sonra sabit 0.1 sn bekler; beklemeleri kendimiz yönetiyoruz.
pydirectinput.PAUSE = 0


# ---------------------------------------------------------------- ayarlar

# GUI'nin gösterdiği mesaj kuyruğu
messages = queue.Queue()


def say(text):
    """Mesajı konsola yazar ve GUI için kuyruğa koyar."""
    print(text)
    messages.put(text)


def load_config(path=CONFIG_PATH):
    """config.json dosyasını okuyup sözlük döndürür."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg, path=CONFIG_PATH):
    """Ayar sözlüğünü config.json dosyasına yazar."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def log_event(kind, **data):
    """Ölçüm için bot_log.jsonl'a bir satır ekler (arama süresi, boşa tıklama, dövüş sonucu)."""
    record = {"t": round(time.time(), 2), "event": kind, **data}
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def make_dpi_aware():
    """Windows ölçeklemesinde koordinatların fiziksel piksel olmasını sağlar."""
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


# ---------------------------------------------------------------- rastgelelik

def jitter(base, ratio):
    """base değerine ±ratio oranında rastgele sapma ekler."""
    return base * random.uniform(1 - ratio, 1 + ratio)


def wait(state, seconds, cfg):
    """Rastgele sapmalı bekler; End'e basılırsa beklemeyi hemen keser."""
    state.stop_event.wait(jitter(seconds, cfg["jitter_ratio"]))


# ---------------------------------------------------------------- tuş gönderme

def press_key(key, hold_sec):
    """Tek bir tuşa basıp bırakır. Tuş gönderen TEK yer burası.

    pydirectinput oyunda çalışmazsa Interception'a geçmek için sadece bu fonksiyonun
    gövdesini değiştir (ör. interception-python ile key_down / key_up).
    """
    pydirectinput.keyDown(key)
    time.sleep(hold_sec)
    pydirectinput.keyUp(key)


def send_key(key, cfg):
    """Basma süresine rastgele sapma ekleyip tuşu gönderir."""
    press_key(key, jitter(cfg["key_hold_sec"], cfg["jitter_ratio"]))


def move_mouse(x, y):
    """Fareyi ekran koordinatına taşır. Fare hareketi gönderen TEK yer burası."""
    pydirectinput.moveTo(int(x), int(y))


def click_mouse(hold_sec):
    """Sol tık. Fare tıklaması gönderen TEK yer burası."""
    pydirectinput.mouseDown()
    time.sleep(hold_sec)
    pydirectinput.mouseUp()


def right_drag(dx, step_px, step_sleep):
    """Sağ tuş basılıyken fareyi yatayda dx kadar küçük adımlarla kaydırır (kamera döner)."""
    pydirectinput.mouseDown(button="right")
    moved = 0
    while abs(moved) < abs(dx):
        part = int(math.copysign(min(step_px, abs(dx) - abs(moved)), dx))
        pydirectinput.moveRel(part, 0, relative=True)
        moved += part
        time.sleep(step_sleep)
    pydirectinput.mouseUp(button="right")


# ---------------------------------------------------------------- imleç

class CURSORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("flags", wt.DWORD),
                ("hCursor", wt.HANDLE), ("ptScreenPos", wt.POINT)]


def cursor_handle():
    """Şu anki imlecin kimliğini döndürür (mob üzerindeyken değişir)."""
    info = CURSORINFO(cbSize=ctypes.sizeof(CURSORINFO))
    ctypes.windll.user32.GetCursorInfo(ctypes.byref(info))
    return info.hCursor or 0


# ---------------------------------------------------------------- pencere

def find_game_window(title):
    """Başlığında title geçen ilk pencereyi döndürür, yoksa None."""
    windows = gw.getWindowsWithTitle(title)
    return windows[0] if windows else None


def game_area(window):
    """Pencerenin başlık çubuğu ve kenarlığı hariç İÇ alanı (ekran koordinatında).
    Oyunun arayüzü iç alanın köşelerine sabit piksellerle bağlı olduğu için bütün
    koordinatlar buna göredir; pencere modu değişse de kaymaz."""
    rect = wt.RECT()
    ctypes.windll.user32.GetClientRect(window._hWnd, ctypes.byref(rect))
    origin = wt.POINT(0, 0)
    ctypes.windll.user32.ClientToScreen(window._hWnd, ctypes.byref(origin))
    return types.SimpleNamespace(left=origin.x, top=origin.y,
                                 width=rect.right, height=rect.bottom)


def is_game_foreground(title):
    """Ön plandaki pencere oyun penceresi mi?"""
    active = gw.getActiveWindow()
    return active is not None and title in active.title


# ---------------------------------------------------------------- ekran okuma

def grab_strip(sct, window, bar):
    """Bar bölgesini 1 piksel yüksekliğinde şerit olarak yakalar (BGRA dizi)."""
    region = {
        "left": window.left + bar["x"],
        "top": window.top + bar["y"],
        "width": bar["width"],
        "height": 1,
    }
    return np.array(sct.grab(region))


def red_ratio(strip, color):
    """Şeritteki kırmızı piksellerin şerit genişliğine oranı. mss çıktısı BGRA sırasındadır."""
    red = red_mask(strip, color)
    return red.sum() / red.size


def read_bar(sct, window, bar, cfg):
    """Bir barın doluluk oranını (0..1) döndürür."""
    return red_ratio(grab_strip(sct, window, bar), cfg["red_color"])


def track_ratio(strip, cfg):
    """Şeritte barın boş (koyu gri) zeminine benzeyen piksellerin oranı."""
    pixels = strip[..., :3].astype(int)
    diff = np.abs(pixels - np.array(cfg["bar_track_color"])).max(axis=-1)
    return (diff < cfg["bar_track_tolerance"]).mean()


def red_mask(pixels, color):
    """BGRA görüntüde kırmızı bar pikselleri için True/False maskesi."""
    b = pixels[..., 0].astype(int)
    g = pixels[..., 1].astype(int)
    r = pixels[..., 2].astype(int)
    return (r > color["r_min"]) & (g < color["g_max"]) & (b < color["b_max"])


def longest_run(row):
    """Bir satırdaki en uzun kesintisiz True dizisi -> (başlangıç, uzunluk)."""
    padded = np.concatenate(([0], row.astype(np.int8), [0]))
    edges = np.diff(padded)
    starts, ends = np.where(edges == 1)[0], np.where(edges == -1)[0]
    if len(starts) == 0:
        return 0, 0
    i = int(np.argmax(ends - starts))
    return int(starts[i]), int(ends[i] - starts[i])


_close_template = None


def close_template(cfg):
    """Hedef penceresinin kapatma (X) düğmesi şablonu (bir kez yüklenir)."""
    global _close_template
    if _close_template is None:
        path = Path(__file__).parent / cfg["target_close"]["template"]
        _close_template = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    return _close_template


def looks_like_hp_bar(row, cfg):
    """Satır mob HP barı mı? Bar soldan kırmızıyla başlar, kalanı koyu gri boş zemindir.
    Oyuncu/pet pencerelerinde aynı yerde buff ikonları ya da oyun dünyası görünür."""
    close = cfg["target_close"]
    red = red_mask(row, cfg["red_color"])
    bright = row[..., :3].max(axis=-1).astype(int)
    dark = (bright < close["bar_dark_max"]) & (bright - row[..., :3].min(axis=-1) < 25)
    return red[:6].sum() >= 3 and (red | dark).mean() >= close["bar_fill_min"]


def find_target_bar(pixels, cfg):
    """Görüntüde mob hedef penceresini kapatma düğmesinden bulur; HP barının başlangıcını
    (x, y) olarak döndürür (görüntüye göre). Mob değilse ya da pencere yoksa None.
    Kırmızı uzunluğuna bakmadığı için canı az mob'lar da bulunur."""
    close = cfg["target_close"]
    image = np.ascontiguousarray(pixels[..., :3])
    template = close_template(cfg)
    if image.shape[0] < template.shape[0] or image.shape[1] < template.shape[1]:
        return None
    scores = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, (mx, my) = cv2.minMaxLoc(scores)
    if score < close["min_score"]:
        return None
    x, y = mx - close["dx"], my + close["dy"]
    width = cfg["target_bar"]["width"]
    if x < 0 or y >= image.shape[0] or x + width > image.shape[1]:
        return None
    return (x, y) if looks_like_hp_bar(image[y, x:x + width], cfg) else None


def locate_target_bar(sct, window, cfg):
    """Hedef penceresinin yeri sabit değil; üst şeritte kapatma düğmesini, bulamazsa uzun
    yatay kırmızı çizgiyi arar. Bulursa bar bölgesini (pencereye göre x, y, width) döndürür,
    yoksa None."""
    area = cfg["target_search"]
    x_max = min(area["x_max"], window.width - area["x_min"])   # küçük pencerede taşmasın
    region = {"left": window.left + area["x_min"], "top": window.top + area["y_min"],
              "width": x_max - area["x_min"], "height": area["y_max"] - area["y_min"]}
    pixels = np.array(sct.grab(region))
    found = find_target_bar(pixels, cfg)
    if found is not None:
        return {"x": area["x_min"] + found[0], "y": area["y_min"] + found[1],
                "width": cfg["target_bar"]["width"], "close": True}
    mask = red_mask(pixels, cfg["red_color"])
    best = (0, 0, 0)   # (uzunluk, satır, başlangıç)
    for row_index, row in enumerate(mask):
        start, length = longest_run(row)
        if length > best[0]:
            best = (length, row_index, start)
    if best[0] < cfg["target_bar_min_run_px"]:
        return None
    return {"x": area["x_min"] + best[2], "y": area["y_min"] + best[1],
            "width": cfg["target_bar"]["width"]}


def read_target(sct, window, bar, cfg):
    """Bulunmuş bar konumunda hedef penceresi açık mı ve HP oranı ne? -> (present, hp)
    HP çok düşükken kırmızı az kalır; barın boş zemini de sayılarak pencere tanınır."""
    if bar.get("close"):
        # Kapatma düğmesiyle bulunmuş bar: düğme ve bar hâlâ yerinde mi?
        close, margin = cfg["target_close"], 3
        patch = np.array(sct.grab({
            "left": window.left + bar["x"] - margin,
            "top": window.top + bar["y"] - close["dy"] - margin,
            "width": max(bar["width"], close["dx"] + close_template(cfg).shape[1]) + 2 * margin,
            "height": close["dy"] + 1 + 2 * margin}))
        row = patch[close["dy"] + margin, margin:margin + bar["width"]]
        return find_target_bar(patch, cfg) is not None, red_ratio(row, cfg["red_color"])
    strip = grab_strip(sct, window, bar)
    hp = red_ratio(strip, cfg["red_color"])
    present = (hp > cfg["target_present_ratio"]
               or hp + track_ratio(strip, cfg) >= cfg["target_window_ratio"])
    return present, hp


def target_present(sct, window, cfg):
    """Ekranda hedef HP barı var mı?"""
    return locate_target_bar(sct, window, cfg) is not None


def player_dead(sct, window, cfg):
    """Karakter HP barı sıfır ve hedef yok mu?"""
    hp = read_bar(sct, window, cfg["player_hp_bar"], cfg)
    return hp <= cfg["player_dead_ratio"] and not target_present(sct, window, cfg)


# ---------------------------------------------------------------- konum (minimap koordinatı)

# Minimap altındaki "X:-1383 Y:2201" yazısının 5x9 piksel fontu. Oyun ekran görüntülerinden
# çıkarıldı; "#" beyaz piksel.
GLYPHS = {
    "-": ("...", "...", "...", "...", "...", "###", "...", "...", "..."),
    ":": (".", ".", "#", ".", ".", ".", ".", ".", "#"),
    "0": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "1": ("..#", ".##", "#.#", "..#", "..#", "..#", "..#", "..#", "..#"),
    "2": (".###.", "#...#", "....#", "....#", "...#.", "...#.", "..#..", ".#...", "#####"),
    "3": (".###.", "#...#", "....#", "....#", "..##.", "....#", "....#", "#...#", ".###."),
    "4": ("...#.", "..##.", "..##.", ".#.#.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": (".####", ".#...", "#....", "####.", "#...#", "....#", "....#", "#...#", ".###."),
    "6": (".###.", "#...#", "#....", "#.##.", "##..#", "#...#", "#...#", "#...#", ".###."),
    "7": ("#####", "...#.", "...#.", "..#..", "..#..", "..#..", ".#...", ".#...", ".#..."),
    "8": (".###.", "#...#", "#...#", "#...#", ".###.", "#...#", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", "#...#", "#..##", ".##.#", "....#", "#...#", ".###."),
    "X": ("#.....#", ".#...#.", ".#...#.", "..#.#..", "...#...", "..#.#..", ".#...#.", ".#...#.", "#.....#"),
    "Y": ("#.....#", ".#...#.", ".#...#.", "..#.#..", "...#...", "...#...", "...#...", "...#...", "...#..."),
}
GLYPH_ARRAYS = {ch: np.array([[c == "#" for c in row] for row in rows]) for ch, rows in GLYPHS.items()}
GLYPH_MAX_MISMATCH = 3   # yazının altından geçen çerçeve çizgisi birkaç piksel ekleyebilir


def split_glyphs(white):
    """Beyaz piksel maskesini boş sütunlardan bölüp karakter bitmap'lerine ayırır."""
    white = white.copy()
    # Alt satırda, üstünde başka beyaz olmayan pikseller çerçeve çizgisidir; sil.
    white[-1] &= white[:-1].any(axis=0)
    cols = white.any(axis=0)
    glyphs, start = [], None
    for x, filled in enumerate(list(cols) + [False]):
        if filled and start is None:
            start = x
        elif not filled and start is not None:
            glyphs.append(white[:, start:x])
            start = None
    return glyphs


def match_glyph(glyph):
    """Bitmap'e en çok benzeyen karakteri döndürür; hiçbiri yeterince benzemezse "?"."""
    best, best_diff = "?", GLYPH_MAX_MISMATCH + 1
    for ch, template in GLYPH_ARRAYS.items():
        width = max(glyph.shape[1], template.shape[1])
        a = np.pad(glyph, ((0, 0), (0, width - glyph.shape[1])))
        b = np.pad(template, ((0, 0), (0, width - template.shape[1])))
        diff = int((a != b).sum())
        if diff < best_diff:
            best, best_diff = ch, diff
    return best


def parse_coords(pixels):
    """Koordinat yazısı bölgesinin görüntüsünden (BGR/BGRA) (x, y) okur; okunamazsa None."""
    white = pixels[..., :3].min(axis=-1) > 200
    text = "".join(match_glyph(g) for g in split_glyphs(white))
    match = re.fullmatch(r"X:(-?\d+)Y:(-?\d+)", text)
    return (int(match.group(1)), int(match.group(2))) if match else None


def read_coords(sct, window, cfg):
    """Minimap altındaki karakter koordinatını okur. Minimap sağ üste bağlı olduğu için
    bölge pencerenin sağ kenarına göre tanımlıdır."""
    box = cfg["coords_text"]
    region = {"left": window.left + window.width - box["right"], "top": window.top + box["y"],
              "width": box["width"], "height": box["height"]}
    return parse_coords(np.array(sct.grab(region)))


# ---------------------------------------------------------------- durum

class BotState:
    """Threadler arasında paylaşılan bot durumu."""

    def __init__(self):
        self.running = False                  # F11 ile değişir
        self.stop_event = threading.Event()   # End ile set edilir
        self.kills = 0
        self.bad_spots = []                   # hedef vermeyen tıklamalar: (x, y, zaman)
        self.misses = 0                       # üst üste sonuçsuz hedef aramaları
        self.target_bar = None                # seçili hedefin bulunan bar konumu
        self.start_time = time.time()
        self.active_total = 0.0               # duraklatmalar hariç çalışma süresi (sn)
        self.run_since = None                 # son F11 başlatma zamanı
        self.home = None                      # alanda kalma: başlangıç koordinatı
        self.walk_offset = 0.0                # alanda kalma: öğrenilen kamera açısı (rad)
        self.normal_cursor = None             # önbellekteki normal imleç
        self.normal_cursor_at = 0.0
        self.last_click = None                # son başarılı mob tıklaması (pencereye göre)
        self.stuck_count = 0                  # üst üste ulaşılamayan hedef sayısı
        self.search_hovers = 0                # son aramadaki fare gezdirme sayısı (log için)
        self.search_clicks = 0                # son aramadaki tıklama sayısı (log için)
        self.fight_hp = None                  # son dövüşün HP özeti (log için)
        self.zerk_at = 0.0                    # son zerk açma zamanı
        self.attack_cursors = set()           # mob öldürülen tıklamalardaki imleçler
        self.selected_cursor = None           # seçili hedefe tıklarken görülen imleç


def set_running(state, running):
    """Botu başlatır/duraklatır ve aktif çalışma süresini biriktirir."""
    now = time.time()
    if running and not state.running:
        state.run_since = now
        state.home = None   # her F11 başlatışında o anki yer yeni başlangıç noktası olur
    elif not running and state.running and state.run_since is not None:
        state.active_total += now - state.run_since
        state.run_since = None
    if running != state.running:
        log_event("resume" if running else "pause")
    state.running = running


def active_seconds(state):
    """Duraklatmalar hariç toplam çalışma süresi."""
    extra = time.time() - state.run_since if state.running and state.run_since else 0
    return state.active_total + extra


def kills_per_minute(state):
    """Aktif çalışma süresine göre dakikada ortalama öldürülen mob."""
    minutes = active_seconds(state) / 60
    return state.kills / minutes if minutes > 0 else 0.0


# ---------------------------------------------------------------- kısayollar

def key_pressed(vk):
    """Tuş son kontrolden beri basıldı mı? (global, oyun ön plandayken de çalışır)"""
    return ctypes.windll.user32.GetAsyncKeyState(vk) & 0x0001


def hotkey_loop(state):
    """F11 başlat/duraklat, End tamamen durdur. Ayrı thread'de çalışır."""
    key_pressed(VK_F11)   # önceki basışları temizle
    key_pressed(VK_END)
    while not state.stop_event.is_set():
        if key_pressed(VK_F11):
            set_running(state, not state.running)
            say("[F11] Bot BAŞLADI" if state.running else "[F11] Bot DURAKLATILDI")
        if key_pressed(VK_END):
            say("[End] Bot durduruluyor...")
            state.stop_event.set()
        time.sleep(0.05)


# ---------------------------------------------------------------- istatistik

def format_uptime(seconds):
    """Saniyeyi SS:DD:ss biçimine çevirir."""
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def stats_text(state):
    """Toplam mob, aktif süre ve dakikada ortalama mob metni."""
    return (f"Öldürülen mob: {state.kills} | Aktif süre: "
            f"{format_uptime(active_seconds(state))} | Ortalama: {kills_per_minute(state):.2f} mob/dk")


def stats_loop(state, cfg):
    """Belirli aralıklarla öldürülen mob sayısını ve çalışma süresini yazar."""
    while not state.stop_event.wait(cfg["stats_interval_sec"]):
        say(f"[İstatistik] {stats_text(state)}")


# ---------------------------------------------------------------- ölüm

def death_alarm():
    """Sesli uyarı verir."""
    for _ in range(5):
        winsound.Beep(1000, 400)
        time.sleep(0.15)


def handle_death(state):
    """Karakter öldüğünde botu durdurur ve uyarı verir."""
    say("[!] Karakter öldü. Bot durduruluyor.")
    state.stop_event.set()
    death_alarm()


# ---------------------------------------------------------------- dövüş

def fight_outcome(present, hp, start_hp, min_hp, cfg):
    """Dövüş bitti mi? Bitmediyse None, bittiyse "killed" veya "lost".
    Ölüm sayılması için: hedef penceresi HP 0 gösteriyor ya da pencere kapandığında
    mob'un HP'si dövüş sırasında gerçekten düşmüştü."""
    if present and hp > cfg["dead_hp_ratio"]:
        return None
    if present:   # pencere açık, HP sıfır
        return "killed"
    damaged = start_hp - min_hp >= cfg["kill_min_damage"]
    return "killed" if damaged else "lost"


def zerk_ready(pixels, cfg):
    """Zerk dolu mu? Dolunca portrenin üstünde büyük renkli küre belirir (pembe ya da mavi).
    pixels: sol üst köşesi oyun alanının sol üst köşesi olan görüntü (BGR/BGRA)."""
    orb = cfg["zerk"]["orb"]
    r = orb["radius"]
    patch = pixels[orb["y"] - r:orb["y"] + r + 1, orb["x"] - r:orb["x"] + r + 1, :3].astype(int)
    colored = (patch.max(axis=-1) - patch.min(axis=-1) > 90) & (patch.max(axis=-1) > 150)
    return colored.mean() >= cfg["zerk"]["min_ratio"]


def try_zerk(state, sct, window, cfg):
    """Zerk doluysa zerk tuşuna basar (aynı zerk için tekrar basmamak için bekleme süreli)."""
    zerk = cfg["zerk"]
    if not zerk["enabled"] or time.time() - state.zerk_at < zerk["cooldown_sec"]:
        return
    orb = zerk["orb"]
    region = {"left": window.left, "top": window.top,
              "width": orb["x"] + orb["radius"] + 1, "height": orb["y"] + orb["radius"] + 1}
    if zerk_ready(np.array(sct.grab(region)), cfg):
        send_key(zerk["key"], cfg)
        state.zerk_at = time.time()
        log_event("zerk")
        say("Zerk doldu, zerk açıldı.")


def is_stuck(start_hp, min_hp, elapsed, cfg):
    """Son ilerlemeden (start_hp) "stuck_sec" sonra mob'un HP'si hâlâ düşmediyse karakter
    ona ulaşamıyor demektir (duvar, yol yok) ya da seçilen şey saldırılamayan bir hedeftir."""
    return elapsed >= cfg["stuck_sec"] and start_hp - min_hp < cfg["kill_min_damage"]


def fight(state, sct, window, cfg):
    """Hedef ölene ya da kaybolana kadar bekler.
    Dönüş: "killed", "lost" (ölmeden kayboldu), "stuck" (HP "stuck_sec" boyunca düşmedi)
    veya "interrupted". Süre sınırı yok: HP düştüğü sürece güçlü mob'larda da dövüş sürer.
    """
    skills = cfg["skill_keys"]
    skill_index = 0
    start_hp = min_hp = None
    state.fight_hp = None
    while True:
        if state.stop_event.is_set() or not state.running:
            return "interrupted"
        if not is_game_foreground(cfg["window_title"]):
            return "interrupted"
        present, hp = read_target(sct, window, state.target_bar, cfg)
        if start_hp is None:
            start_hp = min_hp = progress_hp = hp
            progress_at = time.time()
            rises = 0
        elif present and hp > min_hp + cfg["kill_min_damage"]:
            rises += 1   # HP geri yükseldi: bar okuması titriyor ya da mob iyileşiyor
        if present:
            min_hp = min(min_hp, hp)
        # log için: başlangıç, en düşük, son HP ve kaç kez geri yükseldiği
        state.fight_hp = (round(start_hp, 3), round(min_hp, 3), round(hp, 3), rises)
        outcome = fight_outcome(present, hp, start_hp, min_hp, cfg)
        if outcome:
            return outcome
        if progress_hp - min_hp >= cfg["kill_min_damage"]:   # HP düşüyor, ilerleme var
            progress_hp, progress_at = min_hp, time.time()
        if is_stuck(progress_hp, min_hp, time.time() - progress_at, cfg):
            return "stuck"
        try_zerk(state, sct, window, cfg)
        if skills:
            send_key(skills[skill_index % len(skills)], cfg)
            skill_index += 1
        wait(state, cfg["check_interval_sec"], cfg)


# ---------------------------------------------------------------- hedef seçme

def ring_points(cx, cy, max_radius, step):
    """(cx, cy) etrafında içten dışa halka halka, rastgele sapmalı noktalar üretir."""
    for radius in range(step, max_radius + 1, step):
        count = max(6, int(2 * math.pi * radius / step))
        offset = random.uniform(0, 2 * math.pi)
        for i in range(count):
            angle = offset + 2 * math.pi * i / count
            yield (cx + radius * math.cos(angle) + random.uniform(-step / 4, step / 4),
                   cy + radius * math.sin(angle) + random.uniform(-step / 4, step / 4))


def grab_area(sct, area):
    """Oyun alanının tamamını BGRA dizi olarak yakalar."""
    return np.array(sct.grab({"left": area.left, "top": area.top,
                              "width": area.width, "height": area.height}))


def mask_ui(mask, cfg):
    """Arayüz bölgelerini (paneller, minimap, chat, skill barları) maskeden siler."""
    ui = cfg["ui_margins"]
    h, w = mask.shape
    mask[:ui["top"], :] = 0
    mask[h - ui["bottom"]:, :] = 0
    mask[:ui["top_left_h"], :ui["top_left_w"]] = 0
    mask[:ui["top_right_h"], w - ui["top_right_w"]:] = 0


def find_name_labels(frame, cfg):
    """Ekrandaki beyaz isim etiketlerini bulur -> [(x, y, w, h), ...] (oyun alanına göre)."""
    lab = cfg["label"]
    b, g, r = (frame[..., i].astype(int) for i in range(3))
    white = ((r > lab["white_min"]) & (g > lab["white_min"]) & (b > lab["white_min"])
             & (np.abs(r - b) < 40) & (np.abs(r - g) < 40))
    mask = white.astype(np.uint8) * 255
    mask_ui(mask, cfg)
    merged = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 3)))
    count, _, stats, _ = cv2.connectedComponentsWithStats(merged)
    labels = []
    for i in range(1, count):
        x, y, w, h, _ = stats[i]
        fill = (mask[y:y + h, x:x + w] > 0).mean()
        if (lab["min_w"] <= w <= lab["max_w"] and lab["min_h"] <= h <= lab["max_h"]
                and lab["min_fill"] <= fill <= lab["max_fill"]):
            labels.append((int(x), int(y), int(w), int(h)))
    return labels


def own_label_index(labels, area, cfg):
    """Karakterin kendi adı olan TEK etiketin sırası (yoksa None).
    Kendi adı ortanın sabit bir noktasındadır; oraya en yakın etiket seçilir. Dibe gelen
    mob'ların etiketleri bu yüzden atlanmaz."""
    own = cfg["self_label"]
    ox, oy = area.width / 2 + own["dx"], area.height / 2 + own["dy"]
    best, best_dist = None, own["max_dist_px"]
    for i, (x, y, w, h) in enumerate(labels):
        dist = math.hypot(x + w / 2 - ox, y + h / 2 - oy)
        if dist < best_dist:
            best, best_dist = i, dist
    return best


def label_hover_points(labels, area, cfg):
    """Etiketlerden gövde noktaları üretir; karaktere en yakın etiket önce.
    -> [[(x, y), ...], ...] her etiket için ekran koordinatında deneme noktaları"""
    cx, cy = area.width / 2, area.height / 2
    own = own_label_index(labels, area, cfg)
    groups, seen = [], []
    for i, (x, y, w, h) in enumerate(labels):
        if i == own:
            continue
        lx, ly = x + w / 2, y + h
        if any(math.hypot(lx - sx, ly - sy) < cfg["label_merge_px"] for sx, sy in seen):
            continue   # aynı etiketin parçası (ör. "Dark" + "Sandman")
        seen.append((lx, ly))
        groups.append((math.hypot(lx - cx, ly - cy),
                       [(area.left + lx, area.top + ly + off) for off in cfg["body_offsets_px"]]))
    groups.sort(key=lambda g: g[0])
    return [points for _, points in groups]


def stable_cursor(cfg):
    """Oyun imleci gecikmeli günceller; iki ardışık okuma aynı olana kadar bekler."""
    previous = None
    for _ in range(4):
        time.sleep(jitter(cfg["hover_wait_sec"], cfg["jitter_ratio"]))
        current = cursor_handle()
        if current == previous:
            return current
        previous = current
    return previous


def normal_cursor(window, cfg):
    """Fareyi arayüz üzerine (karakter HP barı) götürüp normal imleci öğrenir."""
    bar = cfg["player_hp_bar"]
    move_mouse(window.left + bar["x"] + bar["width"] / 2, window.top + bar["y"])
    return stable_cursor(cfg)


def cached_normal_cursor(state, window, cfg):
    """Normal imleç değişmez; her aramada fareyi HP barına götürmemek için
    "normal_cursor_ttl_sec" boyunca aynı değeri kullanır."""
    if (state.normal_cursor is None
            or time.time() - state.normal_cursor_at > cfg["normal_cursor_ttl_sec"]):
        state.normal_cursor = normal_cursor(window, cfg)
        state.normal_cursor_at = time.time()
    return state.normal_cursor


def hover_shows_mob(x, y, normal, cfg):
    """Fareyi noktaya götürür; oturmuş imleç normalden farklıysa altında mob vardır."""
    move_mouse(x, y)
    return stable_cursor(cfg) != normal


def is_attack_cursor(cursor, normal, state):
    """Saldırı imleci öğrenildiyse sadece ona izin verir (oyuncu ve item imleçleri de
    normalden farklıdır). Henüz öğrenilmediyse normalden farklı her imleç kabul edilir."""
    if state.attack_cursors:
        return cursor in state.attack_cursors
    return cursor != normal


def learn_attack_cursor(state):
    """Mob öldü: onu seçerken görülen imleç saldırı imlecidir."""
    cursor = state.selected_cursor
    if cursor is not None and cursor not in state.attack_cursors:
        state.attack_cursors.add(cursor)
        log_event("attack_cursor", cursor=int(cursor), known=len(state.attack_cursors))


def forget_old_bad_spots(state, cfg):
    """Süresi dolan başarısız tıklama noktalarını siler."""
    now = time.time()
    state.bad_spots = [s for s in state.bad_spots if now - s[2] < cfg["bad_spot_ttl_sec"]]


def near_bad_spot(state, x, y, window, cfg):
    """Nokta yakın zamanda hedef vermeyen bir tıklamanın (ör. ceset) yakınında mı?"""
    rx, ry = x - window.left, y - window.top
    radius = cfg["bad_spot_radius_px"]
    return any(math.hypot(rx - bx, ry - by) < radius for bx, by, _ in state.bad_spots)


def wait_for_target_bar(state, sct, window, cfg):
    """Tıklamadan sonra hedef barını kısa aralıklarla arar; çıkar çıkmaz döndürür.
    En fazla "after_click_wait_sec" bekler; bar çıkmazsa None."""
    deadline = time.time() + jitter(cfg["after_click_wait_sec"], cfg["jitter_ratio"])
    while True:
        bar = locate_target_bar(sct, window, cfg)
        if bar is not None or time.time() >= deadline or state.stop_event.is_set():
            return bar
        time.sleep(cfg["target_poll_sec"])


MISS_SHOT_SIZE = 200


def grab_click_crop(sct, window, x, y):
    """Tıklama noktasının çevresinden kare parça alır (pencere dışına taşmadan).
    -> (BGRA görüntü, parçadaki tıklama noktası)"""
    size = MISS_SHOT_SIZE
    left = int(min(max(x - size / 2, window.left), window.left + window.width - size))
    top = int(min(max(y - size / 2, window.top), window.top + window.height - size))
    pixels = np.array(sct.grab({"left": left, "top": top, "width": size, "height": size}))
    return pixels, (int(x) - left, int(y) - top)


def save_miss_shot(pixels, cfg, point=None):
    """Boşa giden tıklamanın görüntüsünü tıklama noktası işaretli kaydeder.
    Klasörde "max_files" kadar dosya olunca yenisini yazmaz (disk dolmasın)."""
    shots = cfg["miss_shots"]
    folder = Path(shots["folder"])
    if not folder.is_absolute():
        folder = Path(__file__).parent / folder
    folder.mkdir(exist_ok=True)
    count = len(list(folder.glob("*.png")))
    if count >= shots["max_files"]:
        return
    image = cv2.cvtColor(pixels, cv2.COLOR_BGRA2BGR) if pixels.shape[-1] == 4 else pixels.copy()
    px, py = point or (image.shape[1] // 2, image.shape[0] // 2)
    cv2.drawMarker(image, (px, py), (0, 255, 0), cv2.MARKER_CROSS, 16, 1)
    name = f"{count + 1:03d}-{time.strftime('%H%M%S')}.png"
    ok, data = cv2.imencode(".png", image)
    if ok:
        data.tofile(str(folder / name))   # cv2.imwrite Türkçe karakterli yola yazamaz


def try_click_mob(state, sct, window, x, y, normal, cfg):
    """Noktada mob imleci varsa tıklar; hedef barı çıktıysa True."""
    if near_bad_spot(state, x, y, window, cfg):
        return False
    state.search_hovers += 1
    move_mouse(x, y)
    cursor = stable_cursor(cfg)
    if not is_attack_cursor(cursor, normal, state):
        return False
    crop = grab_click_crop(sct, window, x, y) if cfg["miss_shots"]["enabled"] else None
    click_mouse(jitter(cfg["click_hold_sec"], cfg["jitter_ratio"]))
    state.search_clicks += 1
    bar = wait_for_target_bar(state, sct, window, cfg)
    if bar is not None:
        state.target_bar = bar
        state.last_click = (x - window.left, y - window.top)
        state.selected_cursor = cursor
        return True
    state.bad_spots.append((x - window.left, y - window.top, time.time()))
    if crop is not None:
        save_miss_shot(crop[0], cfg, crop[1])
    return False


def select_target(state, sct, window, cfg):
    """Ekrandaki mob isimlerini bulur, en yakından başlayarak altındaki gövdeye tıklar.
    Dönüş: "selected" (hedef seçildi), "none" (ekranda etiket yok), "missed" (etiket var
    ama hiçbirinden hedef alınamadı)."""
    started = time.time()
    state.search_hovers = state.search_clicks = 0
    labels = find_name_labels(grab_area(sct, window), cfg)
    candidates = label_hover_points(labels, window, cfg)[:cfg["max_labels_per_search"]]
    result = pick_candidate(state, sct, window, candidates, cfg) if candidates else "none"
    log_event("search", result=result, ms=round((time.time() - started) * 1000),
              labels=len(candidates), hovers=state.search_hovers, clicks=state.search_clicks)
    if (result == "missed" and state.search_clicks >= cfg["cursor_reset_min_clicks"]
            and state.search_clicks == state.search_hovers):
        # Her noktada "mob var" denip hiçbiri hedef vermediyse önbellekteki normal imleç
        # bozuktur; bot aslında boş yere tıklıyordur. Bir sonraki aramada yeniden öğren.
        state.normal_cursor = None
        log_event("cursor_reset", clicks=state.search_clicks)
        say("Her tıklama boşa gitti, normal imleç yeniden öğrenilecek.")
    return result


def pick_candidate(state, sct, window, candidates, cfg):
    """Adayları sırayla dener -> "selected" veya "missed"."""
    normal = cached_normal_cursor(state, window, cfg)
    forget_old_bad_spots(state, cfg)
    for points in candidates:
        if any(near_bad_spot(state, x, y, window, cfg) for x, y in points):
            continue   # bu mob'un bir noktası yakın zamanda boşa çıktı ya da takıldı; atla
        for x, y in points:
            if state.stop_event.is_set() or not state.running:
                return "missed"
            if not is_game_foreground(cfg["window_title"]):
                return "missed"   # başka pencereye tıklamamak için
            if state.search_hovers >= cfg["max_hovers_per_search"]:
                return "missed"   # başarılı aramaların %95'i bu sınırdan önce hedef bulur
            if try_click_mob(state, sct, window, x, y, normal, cfg):
                return "selected"
    return "missed"


def rotate_camera(state, window, cfg):
    """Mob bulunamayınca sağ tuşla sürükleyip kamerayı döndürür."""
    started = time.time()
    normal = cached_normal_cursor(state, window, cfg)
    # Sağ tuşa bir mob/oyuncu üzerinde basmamak için boş bir nokta bul.
    for x, y in ring_points(window.left + window.width / 2,
                            window.top + window.height * 0.35, 200, 50):
        if not hover_shows_mob(x, y, normal, cfg):
            break
    else:
        log_event("rotate", result="no_spot", sec=round(time.time() - started, 1))
        return
    if not is_game_foreground(cfg["window_title"]):
        return
    dx = int(jitter(cfg["camera_drag_px"], cfg["jitter_ratio"]))
    right_drag(dx, cfg["camera_drag_step_px"], cfg["camera_drag_step_sec"])
    state.bad_spots = []   # kamera döndü, eski ekran konumları geçersiz
    log_event("rotate", result="ok", sec=round(time.time() - started, 1))


# ---------------------------------------------------------------- alanda kalma

def learned_offset(before, after, screen_angle):
    """Ekranda screen_angle yönüne tıklayınca karakter dünyada before'dan after'a yürüdü.
    Aradaki fark kameranın dönüş açısıdır: dünya açısı = ekran açısı + offset."""
    world_angle = math.atan2(after[1] - before[1], after[0] - before[0])
    return math.atan2(math.sin(world_angle - screen_angle), math.cos(world_angle - screen_angle))


def click_ground(state, window, screen_angle, normal, cfg):
    """Karakterin (ekran ortası) screen_angle yönünde boş bir yere tıklar.
    Ekran açısı: 0 = sağ, pi/2 = yukarı. Mob üstüne tıklamamak için açıyı biraz kaydırır.
    Saldırı imleci öğrenildiyse sadece o imleç noktayı engeller (oyuncu/item engellemez)."""
    radius = cfg["area"]["walk_click_px"]
    cx, cy = window.left + window.width / 2, window.top + window.height / 2
    for shift in (0, 0.25, -0.25, 0.5, -0.5):
        angle = screen_angle + shift
        x, y = cx + radius * math.cos(angle), cy - radius * math.sin(angle)
        move_mouse(x, y)
        if not is_attack_cursor(stable_cursor(cfg), normal, state):
            click_mouse(jitter(cfg["click_hold_sec"], cfg["jitter_ratio"]))
            return True
    return False


def walk_home(state, sct, window, cfg):
    """Başlangıç noktasına adım adım yürür. Kameranın açısı bilinmediği için her adımda
    karakterin gerçekte hangi yöne gittiğine bakıp sonraki tıklamanın yönünü düzeltir.
    Dönüş: (sonuç, adım sayısı). Sonuç: "arrived", "no_coords", "interrupted",
    "no_ground" (boş yer bulunamadı) veya "gave_up" (adımlar bitti)."""
    area = cfg["area"]
    normal = cached_normal_cursor(state, window, cfg)
    pos = read_coords(sct, window, cfg)
    for step in range(area["max_walk_steps"]):
        if pos is None:
            return "no_coords", step
        if state.stop_event.is_set() or not state.running:
            return "interrupted", step
        if not is_game_foreground(cfg["window_title"]):
            return "interrupted", step
        hx, hy = state.home
        if math.hypot(hx - pos[0], hy - pos[1]) <= area["arrive_radius"]:
            say("Başlangıç noktasına dönüldü.")
            return "arrived", step
        screen_angle = math.atan2(hy - pos[1], hx - pos[0]) - state.walk_offset
        if not click_ground(state, window, screen_angle, normal, cfg):
            return "no_ground", step
        wait(state, area["walk_wait_sec"], cfg)
        new = read_coords(sct, window, cfg)
        if new is not None and math.hypot(new[0] - pos[0], new[1] - pos[1]) >= area["min_move"]:
            state.walk_offset = learned_offset(pos, new, screen_angle)
        pos = new
    say("Başlangıç noktasına ulaşılamadı, avlanmaya devam.")
    return "gave_up", area["max_walk_steps"]


def keep_in_area(state, sct, window, cfg):
    """Karakter başlangıç noktasından "radius"tan fazla uzaklaştıysa geri yürütür.
    İlk okunan koordinat başlangıç noktası olur. Geri yürüdüyse True."""
    pos = read_coords(sct, window, cfg)
    if pos is None:   # koordinat yazısı yok (ör. mağara) ya da okunamadı
        return False
    if state.home is None:
        state.home = pos
        say(f"Başlangıç noktası: X:{pos[0]} Y:{pos[1]} (yarıçap {cfg['area']['radius']})")
        return False
    distance = math.hypot(state.home[0] - pos[0], state.home[1] - pos[1])
    if distance <= cfg["area"]["radius"]:
        return False
    say(f"Alan dışına çıkıldı ({distance:.0f} birim), geri dönülüyor.")
    started = time.time()
    result, steps = walk_home(state, sct, window, cfg)
    log_event("walk", result=result, steps=steps, distance=round(distance),
              sec=round(time.time() - started, 1))
    if result == "no_ground":
        # Her nokta "mob" göründü: önbellekteki normal imleç büyük ihtimalle bayat.
        # Yeniden öğren ve hemen tekrar denemek yerine biraz bekle.
        state.normal_cursor = None
        wait(state, cfg["area"]["no_ground_wait_sec"], cfg)
    state.bad_spots = []
    return True


# ---------------------------------------------------------------- ana döngü

def bot_step(state, sct, window, cfg):
    """Ana döngünün bir turu: hedef seç, varsa dövüş, sonucu işle."""
    if player_dead(sct, window, cfg):
        handle_death(state)
        return

    if cfg["area"]["enabled"] and keep_in_area(state, sct, window, cfg):
        return

    found = select_target(state, sct, window, cfg)
    if found != "selected":
        if not state.running or state.stop_event.is_set():
            return
        state.misses = 0 if found == "none" else state.misses + 1
        if found == "none" or state.misses >= cfg["misses_before_rotate"]:
            say("Yakında mob bulunamadı, kamera döndürülüyor.")
            if found == "missed" and state.attack_cursors:
                # Oyun imleci değiştirmiş olabilir; öğrenilenleri unut, sonraki öldürmede
                # yeniden öğrenilir. Yoksa bot hiçbir yere tıklamadan takılı kalabilir.
                state.attack_cursors = set()
                log_event("attack_cursor_reset")
            rotate_camera(state, window, cfg)
            state.misses = 0
        else:
            say(f"Mob'a tıklanamadı, tekrar deneniyor ({state.misses}/"
                  f"{cfg['misses_before_rotate']}).")
        wait(state, cfg["no_target_wait_sec"], cfg)
        return
    state.misses = 0
    say("Hedef seçildi, dövüş başladı.")

    fight_started = time.time()
    result = fight(state, sct, window, cfg)
    hp = dict(zip(("start_hp", "min_hp", "last_hp", "hp_rises"), state.fight_hp or ()))
    log_event("fight", result=result, sec=round(time.time() - fight_started, 1), **hp)
    if result != "stuck":
        state.stuck_count = 0
    if result == "stuck":
        # Mob'a ulaşılamıyor: o noktayı bir süre yasakla, başka mob seç.
        state.bad_spots.append((*state.last_click, time.time()))
        state.stuck_count += 1
        say(f"Hedefin HP'si {cfg['stuck_sec']} sn'de düşmedi (takıldı), başka mob aranıyor.")
        if state.stuck_count >= cfg["stuck_before_rotate"]:
            say("Üst üste takıldı, kamera döndürülüyor.")
            rotate_camera(state, window, cfg)
            state.stuck_count = 0
    elif result == "killed":
        if player_dead(sct, window, cfg):   # bar karakter öldüğü için kaybolmuş olabilir
            handle_death(state)
            return
        state.kills += 1
        learn_attack_cursor(state)
        say(f"Mob öldü #{state.kills} | {stats_text(state)}")
        wait(state, cfg["after_kill_wait_sec"], cfg)
    elif result == "lost":
        # Bizim hasarımız görülmeden kayboldu: sayılmaz.
        say("Hedef kayboldu, sayılmadı.")


def main_loop(state, cfg):
    """Durdurulana kadar bot turlarını çalıştırır."""
    title = cfg["window_title"]
    with mss.mss() as sct:
        while not state.stop_event.is_set():
            if not state.running:
                state.stop_event.wait(0.2)
                continue
            window = find_game_window(title)
            if window is None or not is_game_foreground(title):
                say(f"[Uyarı] '{title}' penceresi ön planda değil, bekleniyor...")
                state.stop_event.wait(cfg["foreground_wait_sec"])
                continue
            bot_step(state, sct, game_area(window), cfg)


def main():
    make_dpi_aware()
    cfg = load_config()
    state = BotState()

    threading.Thread(target=hotkey_loop, args=(state,), daemon=True).start()
    threading.Thread(target=stats_loop, args=(state, cfg), daemon=True).start()

    say("Bot hazır. F11: başlat/duraklat | End: tamamen durdur")
    try:
        main_loop(state, cfg)
    except KeyboardInterrupt:
        state.stop_event.set()
    set_running(state, False)
    say(f"Bot durdu. {stats_text(state)}")


if __name__ == "__main__":
    main()
