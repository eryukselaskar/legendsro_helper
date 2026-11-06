"""
Kalibrasyon aracı: oyun penceresinin ekran görüntüsünü alır, fareyle iki barın yerini
seçtirir, ortalama rengi yazdırır ve config.json'u günceller.

VARSAYIMLAR
- Çalıştırmadan önce oyunda bir mob seçili olmalı (hedef HP barı görünsün) ve karakterin
  HP'si dolu olmalı. Yoksa barlar ekran görüntüsünde görünmez.
- Görüntü 1:1 gösterilir (ölçeklenmez); tıklanan piksel = pencere içindeki piksel.
- Her bar için iki tıklama: barın SOL ucu (başlangıç noktası, y buradan alınır) ve
  SAĞ ucu (genişlik = sağ x - sol x).
- Koordinatlar oyunun İÇ alanının (başlık çubuğu hariç) sol üst köşesine göre kaydedilir (bot.py ile aynı).
"""

import json

import cv2
import mss
import numpy as np

from bot import CONFIG_PATH, find_game_window, game_area, load_config, make_dpi_aware, red_ratio

BARS = [
    ("target_bar", "HEDEF bari (ust ortadaki, secili mobun kirmizi bari)"),
    ("player_hp_bar", "KARAKTER HP bari (sol ustteki KIRMIZI bar, mavi MP degil)"),
]
WINDOW_NAME = "Kalibrasyon"


def capture_window(window):
    """Oyun penceresinin BGRA ekran görüntüsünü alır."""
    region = {"left": window.left, "top": window.top,
              "width": window.width, "height": window.height}
    with mss.mss() as sct:
        return np.array(sct.grab(region))


def prompts():
    """Sırasıyla kullanıcıya gösterilecek tıklama talimatları."""
    out = []
    for _, label in BARS:
        out.append(f"{label}: SOL ucuna tikla")
        out.append(f"{label}: SAG ucuna tikla")
    return out


def draw_overlay(image_bgr, clicks, message):
    """Talimat metnini ve seçilen noktaları/çizgileri görüntüye çizer."""
    canvas = image_bgr.copy()
    cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 30), (0, 0, 0), -1)
    cv2.putText(canvas, message, (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
    for x, y in clicks:
        cv2.circle(canvas, (x, y), 4, (0, 255, 0), 1)
    for i in range(0, len(clicks) - 1, 2):
        (x1, y1), (x2, _) = clicks[i], clicks[i + 1]
        cv2.line(canvas, (x1, y1), (x2, y1), (0, 255, 0), 1)
    return canvas


def collect_clicks(image_bgr):
    """Kullanıcıdan 4 tıklama toplar. ESC ile iptal edilirse None döner."""
    clicks = []
    steps = prompts()

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and len(clicks) < len(steps):
            clicks.append((x, y))

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(WINDOW_NAME, on_mouse)
    while True:
        done = len(clicks) == len(steps)
        message = "Tamam. Kaydetmek icin ENTER, iptal icin ESC" if done else steps[len(clicks)]
        cv2.imshow(WINDOW_NAME, draw_overlay(image_bgr, clicks, message))
        key = cv2.waitKey(20) & 0xFF
        if key == 27:
            cv2.destroyAllWindows()
            return None
        if done and key == 13:
            cv2.destroyAllWindows()
            return clicks


def clicks_to_bar(left_click, right_click):
    """İki tıklamadan bar bölgesi (x, y, width) üretir."""
    x1, y = left_click
    x2 = right_click[0]
    return {"x": min(x1, x2), "y": y, "width": max(abs(x2 - x1), 1)}


def average_rgb(image_bgra, bar):
    """Bar şeridindeki ortalama rengi (R, G, B) döndürür."""
    strip = image_bgra[bar["y"]:bar["y"] + 1, bar["x"]:bar["x"] + bar["width"]]
    b, g, r = strip[..., 0].mean(), strip[..., 1].mean(), strip[..., 2].mean()
    return int(r), int(g), int(b)


def report_bar(label, image_bgra, bar, cfg):
    """Seçilen bar için konum, ortalama renk ve kırmızı oranını yazdırır."""
    r, g, b = average_rgb(image_bgra, bar)
    strip = image_bgra[bar["y"]:bar["y"] + 1, bar["x"]:bar["x"] + bar["width"]]
    ratio = red_ratio(strip, cfg["red_color"])
    print(f"{label}: x={bar['x']} y={bar['y']} width={bar['width']} | "
          f"ortalama renk R={r} G={g} B={b} | kırmızı oranı={ratio:.2f}")


def save_config(cfg):
    """Ayarları config.json'a yazar."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def main():
    make_dpi_aware()
    cfg = load_config()
    window = find_game_window(cfg["window_title"])
    if window is None:
        print(f"'{cfg['window_title']}' başlıklı pencere bulunamadı. "
              "config.json'daki window_title değerini kontrol et.")
        return

    print("Oyunda bir mob seçili ve karakterin HP'si dolu olsun. Görüntü alınıyor...")
    image_bgra = capture_window(game_area(window))
    clicks = collect_clicks(cv2.cvtColor(image_bgra, cv2.COLOR_BGRA2BGR))
    if clicks is None:
        print("İptal edildi, config.json değişmedi.")
        return

    for i, (key, label) in enumerate(BARS):
        bar = clicks_to_bar(clicks[2 * i], clicks[2 * i + 1])
        cfg[key] = bar
        report_bar(label, image_bgra, bar, cfg)

    save_config(cfg)
    print(f"Kaydedildi: {CONFIG_PATH}")
    print("İpucu: kırmızı oranı 0.9'un altındaysa y'yi barın tam ortasına denk getir "
          "veya red_color eşiklerini ortalama renge göre ayarla.")


if __name__ == "__main__":
    main()
