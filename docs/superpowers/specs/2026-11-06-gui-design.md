# Bot arayüzü — tasarım

Tarih: 2026-11-06

## Amaç

Bot'u konsol yerine küçük bir masaüstü penceresinden kullanmak: başlat/durdur, canlı
istatistik, basılacak tuşları ve sık değişen ayarları seçmek, bot mesajlarını görmek.
Bot bir arkadaşa da kullandırılacak; config.json'u elle düzenlemek gerekmemeli.

## Kapsam

Var:
- Başlat/Dur, durum ışığı, canlı istatistik (mob, mob/dk, aktif süre)
- Tuşlar: her tuşa ayrı basma süresi ve "dövüşte / her zaman" seçimi
- Ayarlar: zerk (aç/kapat, tuş), alanda kalma (aç/kapat, yarıçap), pencere adı,
  kaçırma görüntüleri (aç/kapat), ölünce söylenecek cümle
- Canlı mesaj akışı
- Ölünce Windows'un Türkçe sesiyle cümle söyleme

Yok: optimizer'ı arayüzden çalıştırma, "hep üstte", diğer ince ayarlar (config.json'da kalır).

## Yapı

Tek program. `bot.py` tek başına eskisi gibi çalışmaya devam eder.

- `gui.py` (yeni): CustomTkinter penceresi. `bot.main_loop` ve `bot.hotkey_loop`'u ayrı
  thread'lerde başlatır. Pencere ve bot aynı `BotState` ve aynı `cfg` sözlüğünü paylaşır;
  arayüz `cfg`'yi yerinde değiştirir, bot bir sonraki turda yeni değeri kullanır.
- `bot.py` değişiklikleri:
  - `say(text)`: `print` çağrılarının yerini alır; konsola yazar ve mesajı
    `bot.messages` kuyruğuna (`queue.Queue`) koyar. Pencere kuyruğu 200 ms'de bir boşaltır.
  - `save_config(cfg)`: config.json'a yazar (UTF-8, girintili).
  - Tuş zamanlayıcı (aşağıda).
  - Ölüm: `handle_death` bip seslerinden sonra `cfg["death_say"]` doluysa cümleyi söyler.
  - `state.dead = True` ölünce set edilir (pencere durumu "ÖLDÜ" gösterir).

## Tuş zamanlayıcı

config.json:

```json
"skill_keys": [
  {"key": "1",  "every_sec": 2,   "when": "fight"},
  {"key": "F1", "every_sec": 300, "when": "always"}
]
```

- `when: "fight"`: sadece dövüş döngüsünde basılır. `"always"`: dövüşte ve dövüş dışında
  (her bot turunda) kontrol edilir.
- Eski biçim (`["1", "2"]`) okunurken `{"key": k, "every_sec": 0, "when": "fight"}` olur:
  her kontrolde basılmaya uygun; bugünkü davranışa yakın.
- `due_keys(state, keys, in_fight, now)`: zamanı gelen tuşları döndürür ve son basma
  zamanını `state.key_last` sözlüğünde günceller. Bir kontrolde birden fazla tuşun zamanı
  geldiyse hepsine basılır. Saf fonksiyon; testle doğrulanır.
- Dövüş döngüsündeki bugünkü sıralı basma (`skill_index`) bunun yerine geçer.

## Pencere

~420×640, koyu tema. Yukarıdan aşağıya:

1. Durum satırı: ışık (yeşil ÇALIŞIYOR / sarı DURAKLATILDI / kırmızı ÖLDÜ / gri DURDU) +
   Başlat/Dur düğmesi (F11 ile aynı: `set_running`).
2. İstatistik satırı: mob sayısı, mob/dk, aktif süre; 1 sn'de bir güncellenir.
3. Sekmeler:
   - Tuşlar: satır başına tuş kutusu, "Her (sn)" kutusu, "Dövüşte/Her zaman" seçimi, sil
     düğmesi; altta "+ Tuş ekle".
   - Ayarlar: zerk aç/kapat + tuş, alanda kalma aç/kapat + yarıçap, pencere adı,
     kaçırma görüntüleri aç/kapat, "Ölünce söyle" metin kutusu.
4. Mesaj kutusu: `SS:DD:ss metin`, son 200 satır, en alta kayar.

Davranış:
- Değişiklik kutudan çıkınca / düğme değişince `cfg`'ye uygulanır ve kaydedilir.
- Geçersiz değer (sayı olmayan süre/yarıçap, boş tuş): kutu kırmızı olur, kaydedilmez,
  eski değer kalır.
- Pencereyi kapatmak End ile aynı: `stop_event` set edilir, threadler biter.
- Bot sadece oyun ön plandayken çalışır; Başlat'a bastıktan sonra oyuna tıklamak gerekir.
  F11 oyun içindeyken de çalışır.

## Ölünce konuşma

- `cfg["death_say"]`, varsayılan "Sen bir malsın Fethi". Boşsa konuşmaz.
- PowerShell + `System.Speech` ile söylenir; kurulu `tr-TR` ses varsa o seçilir
  (bu bilgisayarda "Microsoft Tolga"), yoksa varsayılan ses. Ek Python paketi gerekmez.
- Metin PowerShell'e komut satırında değil standart girdiden verilir (tırnak/kaçış sorunu
  olmasın).
- Konuşma hata verirse bot yine durur; hata mesajı `say` ile yazılır.

## Bağımlılık

- `customtkinter` (pip). Sadece `gui.py` kullanır; `bot.py` ona bağımlı değil.

## Testler

- `due_keys`: süresi gelmeyen basılmaz, gelen basılır, "always" dövüş dışında da basılır,
  "fight" dövüş dışında basılmaz, eski liste biçimi çalışır.
- `save_config` / `load_config` gidiş-dönüş (geçici dosyada).
- Ayar doğrulama fonksiyonu (`gui.py` içinde arayüzden bağımsız): geçerli/geçersiz süre,
  yarıçap, tuş.
- `handle_death`: konuşma fonksiyonu sahte; `death_say` doluyken çağrılır, boşken çağrılmaz.
- Pencerenin kendisi elle denenir: açılış, Başlat/Dur, tuş ekleme/silme, kaydetme, kapanış.
