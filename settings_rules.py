"""Ayar doğrulama kuralları (arayüzden bağımsız). Geçersiz girdi -> ValueError."""

import math

import pydirectinput


def parse_seconds(text):
    """Saniye: sonlu ve >= 0 sayı."""
    value = float(text.strip())
    if not math.isfinite(value) or value < 0:
        raise ValueError("Saniye sonlu ve >= 0 olmalı")
    return value


def parse_radius(text):
    """Yarıçap: >= 1 tam sayı."""
    value = int(text.strip())
    if value < 1:
        raise ValueError("Yarıçap >= 1 olmalı")
    return value


def parse_key(text):
    """Tuş: kırpılır, küçük harfe çevrilir, pydirectinput'ta tanımlı olmalı."""
    key = text.strip().lower()
    if key not in pydirectinput.KEYBOARD_MAPPING:
        raise ValueError(f"Bilinmeyen tuş: {key!r}")
    return key


def parse_title(text):
    """Pencere başlığı: kırpılmış, boş olmayan metin."""
    title = text.strip()
    if not title:
        raise ValueError("Başlık boş olamaz")
    return title
