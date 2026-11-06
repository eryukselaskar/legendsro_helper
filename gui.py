"""
Bot arayüzü (CustomTkinter). Botu konsol yerine bir pencereden kullanmak için:
başlat/duraklat, canlı istatistik, tuşlar, sık değişen ayarlar ve bot mesajları.

Çalıştırma: python gui.py   (bot.py tek başına eskisi gibi de çalışır)
Pencere ve bot aynı BotState ve aynı cfg sözlüğünü paylaşır; arayüz cfg'yi yerinde
değiştirip config.json'a kaydeder, bot bir sonraki turda yeni değeri kullanır.
"""

import queue
import threading
import time

try:
    import customtkinter as ctk
except ImportError:
    print("customtkinter yüklü değil. Şunu çalıştır: pip install -r requirements.txt")
    raise SystemExit(1)

import bot
import settings_rules as rules

# ---------------------------------------------------------------- görünüm

BG = "#0e0e10"         # pencere zemini
CARD = "#17171b"       # kartlar
CARD_2 = "#1f1f25"     # kart içi kutular
BORDER = "#2a2a31"     # kutu kenarlığı
TEXT = "#e8e8ec"
MUTED = "#8b8b96"
ACCENT = "#3b82f6"     # tek vurgu rengi (elektrik mavisi)
ACCENT_HOVER = "#2563eb"
RED = "#e5484d"        # geçersiz değer / ÖLDÜ
GREEN = "#30a46c"
YELLOW = "#f5a524"
GRAY = "#6b6b75"

FONT = "Segoe UI"
WHEN_LABELS = {"fight": "Dövüşte", "always": "Her zaman"}
WHEN_VALUES = {v: k for k, v in WHEN_LABELS.items()}
MAX_LINES = 200

ctk.set_appearance_mode("dark")


def font(size=13, weight="normal"):
    return ctk.CTkFont(family=FONT, size=size, weight=weight)


def entry(parent, width, **kw):
    return ctk.CTkEntry(parent, width=width, height=30, font=font(), fg_color=CARD_2,
                        border_color=BORDER, border_width=1, text_color=TEXT, **kw)


def mark(widget, ok):
    """Geçerli değerde normal, geçersizde kırmızı kenarlık."""
    widget.configure(border_color=BORDER if ok else RED)


# ---------------------------------------------------------------- tuş satırı

class KeyRow:
    """Tuşlar sekmesinde bir satır: tuş, "Her (sn)", Dövüşte/Her zaman, sil.
    value: kaydedilmiş geçerli değer ({"key", "every_sec", "when"}) ya da henüz geçerli
    değer girilmediyse None (cfg'ye yazılmaz)."""

    def __init__(self, app, item=None):
        self.app = app
        self.value = dict(item) if item else None
        self.frame = ctk.CTkFrame(app.keys_list, fg_color=CARD_2, corner_radius=8)
        self.frame.pack(fill="x", pady=3, padx=2)
        self.key_entry = entry(self.frame, 64, placeholder_text="tuş")
        self.key_entry.pack(side="left", padx=(8, 4), pady=6)
        self.sec_entry = entry(self.frame, 64, placeholder_text="sn")
        self.sec_entry.pack(side="left", padx=4, pady=6)
        self.when = ctk.CTkSegmentedButton(
            self.frame, values=list(WHEN_VALUES), font=font(12), height=28,
            selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
            fg_color=CARD, unselected_color=CARD, command=lambda _v: self.commit())
        self.when.pack(side="left", padx=4, pady=6)
        ctk.CTkButton(self.frame, text="✕", width=30, height=28, font=font(13),
                      fg_color="transparent", hover_color="#3a1d20", text_color=MUTED,
                      command=self.delete).pack(side="right", padx=(4, 8))
        item = self.value or {"key": "", "every_sec": 0, "when": "fight"}
        self.key_entry.insert(0, item["key"])
        self.sec_entry.insert(0, str(item["every_sec"]))
        self.when.set(WHEN_LABELS.get(item["when"], "Dövüşte"))
        for e in (self.key_entry, self.sec_entry):
            e.bind("<FocusOut>", lambda _e: self.commit())
            e.bind("<Return>", lambda _e: self.commit())

    def commit(self):
        """Kutulardaki değeri doğrular; geçerliyse kaydeder, değilse kırmızı yapar."""
        try:
            key = rules.parse_key(self.key_entry.get())
            others = {r.value["key"] for r in self.app.key_rows if r is not self and r.value}
            if key in others:   # aynı tuş iki satırda olursa tek zamanlayıcıyı paylaşırlar
                raise ValueError("Bu tuş listede zaten var")
            key_ok = True
        except ValueError:
            key_ok = False
        try:
            sec = rules.parse_seconds(self.sec_entry.get())
            sec_ok = True
        except ValueError:
            sec_ok = False
        mark(self.key_entry, key_ok)
        mark(self.sec_entry, sec_ok)
        if not (key_ok and sec_ok):
            return False
        self.value = {"key": key, "every_sec": sec, "when": WHEN_VALUES[self.when.get()]}
        self.app.save_keys()
        return True

    def delete(self):
        self.frame.destroy()
        self.app.key_rows.remove(self)
        self.app.save_keys()


# ---------------------------------------------------------------- pencere

class App(ctk.CTk):
    def __init__(self, state, cfg, start_threads=True, config_path=bot.CONFIG_PATH):
        super().__init__(fg_color=BG)
        self.bot_state, self.cfg, self.config_path = state, cfg, config_path
        self.bot_thread = None
        self.title("Legends Bot")
        self.geometry("420x640")
        self.minsize(420, 600)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.build_status()
        self.build_stats()
        self.build_tabs()
        self.build_messages()

        if start_threads:
            self.start_threads()
        self.poll_messages()
        self.tick()

    # ------------------------------------------------ bölümler

    def card(self, **pack):
        frame = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        frame.pack(fill="x", padx=14, **pack)
        return frame

    def build_status(self):
        row = self.card(pady=(14, 6))
        self.dot = ctk.CTkFrame(row, width=12, height=12, corner_radius=6, fg_color=GRAY)
        self.dot.pack(side="left", padx=(16, 10), pady=18)
        self.status = ctk.CTkLabel(row, text="HAZIR", font=font(15, "bold"), text_color=TEXT)
        self.status.pack(side="left")
        self.toggle = ctk.CTkButton(row, text="Başlat", width=110, height=36, font=font(14, "bold"),
                                    fg_color=ACCENT, hover_color=ACCENT_HOVER, corner_radius=8,
                                    command=self.toggle_running)
        self.toggle.pack(side="right", padx=12, pady=10)

    def build_stats(self):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=6)
        self.stat_labels = {}
        for i, name in enumerate(("Mob", "Mob/dk", "Aktif süre")):
            box = ctk.CTkFrame(row, fg_color=CARD, corner_radius=12)
            box.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 4, 0 if i == 2 else 4))
            row.grid_columnconfigure(i, weight=1, uniform="stat")
            ctk.CTkLabel(box, text=name, font=font(11), text_color=MUTED).pack(anchor="w", padx=12, pady=(8, 0))
            value = ctk.CTkLabel(box, text="0", font=font(18, "bold"), text_color=TEXT)
            value.pack(anchor="w", padx=12, pady=(0, 8))
            self.stat_labels[name] = value

    def build_tabs(self):
        self.tabs = ctk.CTkTabview(self, height=230, fg_color=CARD, corner_radius=12,
                                   segmented_button_selected_color=ACCENT,
                                   segmented_button_selected_hover_color=ACCENT_HOVER,
                                   segmented_button_fg_color=CARD_2,
                                   segmented_button_unselected_color=CARD_2)
        self.tabs.pack(fill="x", padx=14, pady=6)
        self.tabs._segmented_button.configure(font=font(13))
        self.build_keys_tab(self.tabs.add("Tuşlar"))
        self.build_settings_tab(self.tabs.add("Ayarlar"))

    def build_keys_tab(self, tab):
        head = ctk.CTkFrame(tab, fg_color="transparent")
        head.pack(fill="x")
        for text, width in (("Tuş", 72), ("Her (sn)", 72), ("Ne zaman", 0)):
            ctk.CTkLabel(head, text=text, width=width, anchor="w", font=font(11),
                         text_color=MUTED).pack(side="left", padx=(10 if text == "Tuş" else 0, 0))
        self.keys_list = ctk.CTkScrollableFrame(tab, fg_color="transparent", height=120)
        self.keys_list.pack(fill="both", expand=True)
        self.key_rows = [KeyRow(self, k) for k in bot.normalize_keys(self.cfg.get("skill_keys", []))]
        ctk.CTkButton(tab, text="+ Tuş ekle", height=32, font=font(13), fg_color=CARD_2,
                      hover_color=BORDER, border_color=ACCENT, border_width=1, text_color=TEXT,
                      command=self.add_key_row).pack(fill="x", pady=(6, 0))

    def add_key_row(self):
        row = KeyRow(self)
        self.key_rows.append(row)
        row.key_entry.focus_set()
        return row

    def build_settings_tab(self, tab):
        tab.grid_columnconfigure(1, weight=1)
        cfg = self.cfg
        self.settings = {}

        def switch(r, text, section):
            var = ctk.BooleanVar(value=cfg[section]["enabled"])
            sw = ctk.CTkSwitch(tab, text=text, variable=var, font=font(13), text_color=TEXT,
                               progress_color=ACCENT,
                               command=lambda: self.apply(lambda: cfg[section].update(enabled=var.get())))
            sw.grid(row=r, column=0, sticky="w", padx=8, pady=6)
            self.settings[section + ".enabled"] = sw

        def field(r, label, initial, parse, store, width=90):
            if label:
                ctk.CTkLabel(tab, text=label, font=font(13), text_color=TEXT).grid(
                    row=r, column=0, sticky="w", padx=8, pady=6)
            e = entry(tab, width)
            e.insert(0, str(initial))
            e.grid(row=r, column=1, sticky="e", padx=8, pady=6)
            commit = lambda _e=None: self.commit_field(e, parse, store)
            e.bind("<FocusOut>", commit)
            e.bind("<Return>", commit)
            return e

        switch(0, "Zerk", "zerk")
        self.settings["zerk.key"] = field(0, None, cfg["zerk"]["key"], rules.parse_key,
                                          lambda v: cfg["zerk"].update(key=v))
        switch(1, "Alanda kal", "area")
        self.settings["area.radius"] = field(1, None, cfg["area"]["radius"], rules.parse_radius,
                                             lambda v: cfg["area"].update(radius=v))
        self.settings["window_title"] = field(2, "Pencere adı", cfg["window_title"], rules.parse_title,
                                              lambda v: cfg.update(window_title=v), width=200)
        switch(3, "Kaçırma görüntüleri", "miss_shots")
        self.settings["death_say"] = field(4, "Ölünce söyle", cfg.get("death_say", ""), str.strip,
                                           lambda v: cfg.update(death_say=v), width=200)
        ctk.CTkLabel(tab, text="ses.mp3 varsa o çalınır; yoksa bu cümle söylenir (boşsa sessiz).",
                     font=font(11), wraplength=370, justify="left",
                     text_color=MUTED).grid(row=5, column=0, columnspan=2, sticky="w", padx=8)

    def build_messages(self):
        self.log = ctk.CTkTextbox(self, fg_color=CARD, corner_radius=12, font=font(12),
                                  text_color=TEXT, border_width=0, wrap="word")
        self.log.pack(fill="both", expand=True, padx=14, pady=(6, 14))
        self.log.configure(state="disabled")

    # ------------------------------------------------ kaydetme

    def apply(self, change):
        change()
        try:
            bot.save_config(self.cfg, self.config_path)
        except Exception as e:
            bot.say(f"[Uyarı] Ayar kaydedilemedi: {e}")

    def commit_field(self, widget, parse, store):
        """Kutudaki değeri doğrular; geçerliyse cfg'ye yazıp kaydeder, değilse kırmızı yapar."""
        try:
            value = parse(widget.get())
        except ValueError:
            mark(widget, False)
            return False
        mark(widget, True)
        self.apply(lambda: store(value))
        return True

    def save_keys(self):
        """Geçerli satırları sırayla cfg["skill_keys"]'e yazar ve kaydeder."""
        self.apply(lambda: self.cfg.update(skill_keys=[dict(r.value) for r in self.key_rows if r.value]))

    # ------------------------------------------------ bot

    def start_threads(self):
        threading.Thread(target=bot.hotkey_loop, args=(self.bot_state,), daemon=True).start()
        self.bot_thread = threading.Thread(target=self.run_bot, daemon=True)
        self.bot_thread.start()
        bot.say("Hazır. Başlat'a bas, sonra oyuna tıkla. Oyunda F11: başlat/duraklat, End: durdur.")

    def run_bot(self):
        """main_loop'u çalıştırır; beklenmeyen hata kaybolmasın diye yazılır ve bot durur."""
        try:
            bot.main_loop(self.bot_state, self.cfg)
        except Exception as e:
            bot.say(f"[Hata] {e}")
            self.bot_state.stop_event.set()

    def toggle_running(self):
        """F11 ile aynı."""
        bot.set_running(self.bot_state, not self.bot_state.running)
        bot.say("Bot BAŞLADI" if self.bot_state.running else "Bot DURAKLATILDI")
        self.update_status()

    def update_status(self):
        s = self.bot_state
        if s.dead:
            text, color = "ÖLDÜ", RED
        elif s.stop_event.is_set():
            text, color = "DURDU", GRAY
        elif s.running:
            text, color = "ÇALIŞIYOR", GREEN
        elif s.active_total > 0:
            text, color = "DURAKLATILDI", YELLOW
        else:
            text, color = "HAZIR", GRAY
        self.status.configure(text=text)
        self.dot.configure(fg_color=color)
        if s.stop_event.is_set():   # End ya da ölüm: yeniden başlatmak için pencere yeniden açılır
            self.toggle.configure(state="disabled", text="Durdu", fg_color=CARD_2)
        else:
            self.toggle.configure(text="Dur" if s.running else "Başlat")

    def poll_messages(self):
        """Bot mesajlarını 200 ms'de bir kutuya ekler (son 200 satır)."""
        lines = []
        while True:
            try:
                lines.append(f"{time.strftime('%H:%M:%S')} {bot.messages.get_nowait()}\n")
            except queue.Empty:
                break
        if lines:
            self.log.configure(state="normal")
            self.log.insert("end", "".join(lines))
            extra = int(self.log.index("end-1c").split(".")[0]) - 1 - MAX_LINES
            if extra > 0:
                self.log.delete("1.0", f"{extra + 1}.0")
            self.log.see("end")
            self.log.configure(state="disabled")
        self.update_status()
        self.after(200, self.poll_messages)

    def tick(self):
        """İstatistikleri saniyede bir günceller."""
        self.stat_labels["Mob"].configure(text=str(self.bot_state.kills))
        self.stat_labels["Mob/dk"].configure(text=f"{bot.kills_per_minute(self.bot_state):.2f}")
        self.stat_labels["Aktif süre"].configure(text=bot.format_uptime(bot.active_seconds(self.bot_state)))
        self.after(1000, self.tick)

    def on_close(self):
        """Pencereyi kapatmak End ile aynı."""
        self.bot_state.stop_event.set()
        if self.bot_thread is not None:
            self.bot_thread.join(timeout=2)
        self.destroy()


def main():
    bot.make_dpi_aware()   # bot fiziksel piksel okur; pencereden önce yapılmalı
    app = App(bot.BotState(), bot.load_config())
    app.mainloop()


if __name__ == "__main__":
    main()
