# Legends Bot

## Hazır paket (Python gerekmez)

GitHub'daki Releases sayfasından birini indir:

- **Setup.exe**: Kurar, masaüstüne ve Başlat menüsüne kısayol ekler. Güncellemede ayarların ve `ses.mp3` korunur.
- **portable.zip**: Bir klasöre aç, `LegendsRO Helper.exe`'ye çift tıkla.

Program açılırken yönetici izni ister. Windows "tanınmayan uygulama" derse "Ek bilgi" > "Yine de çalıştır" seç.
Ayarlar ve `ses.mp3` exe'nin yanındadır.

Paketleri yeniden üretmek için: `powershell -ExecutionPolicy Bypass -File build.ps1 -Version 1.0.0`
(PyInstaller ve Inno Setup 6 gerekir.)

## Kaynaktan kurulum

1. Python 3.12 kur (python.org'daki standart yükleyici; tkinter dahildir).
2. Bu klasörde: `pip install -r requirements.txt`

## Çalıştırma

1. `python gui.py` (gerekirse terminali yönetici olarak aç; bot yönetici yetkisi varsayar).
2. Pencerede **Başlat**'a bas, sonra oyun penceresine tıkla.
3. Oyundayken kısayollar: **F11** başlat/duraklat, **End** durdur.
4. Karakter ölünce ya da End'e basılınca bot durur; yeniden başlatmak için pencereyi kapatıp tekrar aç.

## Ses

- Ölünce `ses.mp3` çalınır. Dosyayı kendi sesinle değiştirebilirsin.
- `ses.mp3` yoksa ya da çalınamazsa, Ayarlar sekmesindeki "Ölünce söyle" cümlesi okunur.
- Türkçe ses yoksa: Windows Ayarlar > Zaman ve dil > Konuşma bölümünden Türkçe ses ekle.
