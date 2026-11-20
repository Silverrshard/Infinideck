"""Infinideck: pull cards from an endless deck for chips, stack wild modifiers and grow huge numbers (game).

The table, pulling, 60 modifiers, crits, rarity, chips flying to the counter, the "beyond rarity" cutscene, the
menu, 5 profiles with crash-safe autosave, the tutorial, the Skill Tree (Main 550, Decks 50, Transcend 144),
Transcending, the Index, Deck and Stats pages, 100 perks with Shatter and perk slots, and 100 achievements.
"""
import ctypes
import json
import math
import os
import random
import struct
import sys
import threading
import time
import types
import zlib
from collections import deque
from pathlib import Path

import pygame

HERE = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
ASSETS = HERE / "assets"
sys.path.insert(0, str(ASSETS / "Core"))         # the game's other code lives in assets\Core
import _art as art

# --- UI kit (Balatro-like): chunky slab panels with thick dark outlines, bold coloured buttons with a darker lip
# that lift and wobble when hovered, and text with a drop shadow. The pages in assets\Core use it as `_ui`. ---
UI_PANEL = (19, 20, 27)         # near-black panel (black UI makes the colours pop)
UI_PANEL_IN = (8, 9, 13)        # sunken boxes inside panels
UI_EDGE = (0, 0, 0)             # thick outline
UI_TEXT = (246, 244, 238)
UI_MUTED = (168, 176, 180)
UI_COLORS = {                   # face, lip (the darker underside)
    "red": ((232, 72, 64), (150, 38, 34)),
    "blue": ((0, 140, 228), (0, 88, 156)),
    "orange": ((246, 156, 22), (168, 98, 8)),
    "green": ((60, 176, 124), (32, 110, 76)),
    "purple": ((142, 92, 224), (88, 52, 150)),
    "gold": ((236, 188, 70), (160, 118, 30)),
    "pink": ((236, 72, 153), (150, 28, 90)),
    "cyan": ((20, 200, 220), (8, 120, 140)),
    "teal": ((38, 166, 154), (18, 100, 92)),
    "gray": ((58, 60, 72), (32, 33, 42)),
    "dark": ((34, 35, 46), (16, 17, 24)),
}
UI_LIP = 6                      # how thick the slab edge is
_juice_state = {}               # key -> [hovering, time the hover changed]


def ui_juice(key, hovering, now):
    """A springy scale: a little bounce when the mouse arrives, then a small lift while it stays."""
    st = _juice_state.get(key)
    if st is None or st[0] != hovering:
        st = _juice_state[key] = [hovering, now]
    t = now - st[1]
    if hovering:
        return 1.04 + 0.05 * math.exp(-t * 9) * math.cos(t * 32)
    return 1.0 + 0.03 * math.exp(-t * 10) * math.cos(t * 30)


def ui_label(s, text, size, pos, color=UI_TEXT, anchor="topleft", bold=True, shadow=True, alpha=255):
    f = art.font(size, bold=bold)
    t = f.render(str(text), True, color)
    r = t.get_rect(**{anchor: pos})
    if shadow:
        sh = f.render(str(text), True, (0, 0, 0))
        sh.set_alpha(int(150 * alpha / 255))
        s.blit(sh, r.move(max(1, size // 12), max(1, size // 12)))
    if alpha < 255:
        t.set_alpha(alpha)
    s.blit(t, r)
    return r


def ui_panel(s, rect, fill=UI_PANEL, radius=16, lip=UI_LIP, edge=UI_EDGE, alpha=255, outline=3):
    """A chunky slab: dark outline, a darker underside showing below, and a soft top highlight."""
    rect = pygame.Rect(rect)
    under = tuple(max(0, c - 22) for c in fill)
    body = rect.copy()
    body.height -= lip
    if alpha < 255:
        layer = pygame.Surface((rect.w + outline * 2, rect.h + outline * 2), pygame.SRCALPHA)
        ui_panel(layer, pygame.Rect(outline, outline, rect.w, rect.h), fill, radius, lip, edge, 255, outline)
        layer.set_alpha(alpha)
        s.blit(layer, (rect.x - outline, rect.y - outline))
        return body
    pygame.draw.rect(s, edge, rect.inflate(outline * 2, outline * 2), border_radius=radius + outline)
    pygame.draw.rect(s, under, rect, border_radius=radius)
    pygame.draw.rect(s, fill, body, border_radius=radius)
    hi = tuple(min(255, c + 16) for c in fill)
    pygame.draw.line(s, hi, (body.x + radius, body.y + 2), (body.right - radius, body.y + 2), 2)
    return body


def ui_inset(s, rect, fill=UI_PANEL_IN, radius=10):
    """A sunken box (where numbers live)."""
    rect = pygame.Rect(rect)
    pygame.draw.rect(s, fill, rect, border_radius=radius)
    pygame.draw.rect(s, (0, 0, 0), rect, 2, border_radius=radius)
    pygame.draw.line(s, tuple(max(0, c - 10) for c in fill), (rect.x + radius, rect.y + 3),
                     (rect.right - radius, rect.y + 3), 2)
    return rect


def ui_button(s, rect, text, color="red", now=0.0, key=None, enabled=True, size=22, sub=None, selected=False,
              icon=None):
    """A Balatro button. Returns True while the mouse is over it (and it's enabled)."""
    rect = pygame.Rect(rect)
    hover = enabled and rect.collidepoint(pygame.mouse.get_pos())
    pressed = hover and pygame.mouse.get_pressed()[0]
    face, lip = UI_COLORS["gray" if not enabled else color]
    if not enabled:
        face, lip = (60, 66, 70), (38, 42, 45)
    k = ui_juice(key or (text, rect.topleft), hover or selected, now) if enabled else 1.0
    r = rect.inflate(int(rect.w * (k - 1)), int(rect.h * (k - 1)))
    drop = UI_LIP if not pressed else 2
    pygame.draw.rect(s, UI_EDGE, r.inflate(6, 6 + UI_LIP).move(0, UI_LIP // 2), border_radius=14)
    pygame.draw.rect(s, lip, r.move(0, UI_LIP), border_radius=12)
    top = r.move(0, UI_LIP - drop)
    col = tuple(min(255, c + 22) for c in face) if hover else face
    pygame.draw.rect(s, col, top, border_radius=12)
    pygame.draw.line(s, tuple(min(255, c + 45) for c in col), (top.x + 12, top.y + 3), (top.right - 12, top.y + 3), 2)
    if selected:
        pygame.draw.rect(s, (255, 255, 255), top.inflate(-6, -6), 2, border_radius=10)
    cy = top.centery - (9 if sub else 0)
    tx = top.centerx
    if icon is not None:
        tx += icon.get_width() // 2 + 4
        s.blit(icon, icon.get_rect(midright=(tx - art.font(size, bold=True).size(str(text))[0] // 2 - 8, cy)))
    ui_label(s, text, size, (tx, cy), UI_TEXT if enabled else (150, 154, 158), "center")
    if sub:
        ui_label(s, sub, 13, (top.centerx, top.centery + 13), (255, 255, 255) if enabled else (130, 134, 138),
                 "center", bold=False)
    return hover


def ui_tag(s, text, kind, pos, size=15, anchor="topleft"):
    """A coloured value chip with a darker lip (chips blue, mult red, TP purple...)."""
    img = art.tag(text, kind, size)
    r = img.get_rect(**{anchor: pos})
    under = tuple(max(0, c - 70) for c in (kind if isinstance(kind, tuple) else art.TAG_COLORS[kind]))
    pygame.draw.rect(s, under, r.move(0, 3), border_radius=6)
    s.blit(img, r)
    return r


def ui_pop(t, dur=0.28):
    """Scale for a popping-in element: overshoots, then settles at 1."""
    if t >= dur:
        return 1.0
    x = t / dur
    return 0.2 + 0.8 * (1 - (1 - x) ** 3) + 0.25 * math.sin(x * math.pi) * (1 - x)


def ui_blur(surf, amount=5):
    """A smooth blur (no blocky pixels): shrink in halves, soften the small copy, then grow back in halves."""
    w, h = surf.get_size()
    small = surf
    steps = max(1, int(amount).bit_length() - 1)              # 5 -> 2 halvings, 8 -> 3
    for _ in range(steps):
        small = pygame.transform.smoothscale(small, (max(1, small.get_width() // 2), max(1, small.get_height() // 2)))
    soft = small.copy()                                       # a little box blur on the small copy
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1)):
        shifted = small.copy()
        shifted.set_alpha(70)
        soft.blit(shifted, (dx, dy))
    for i in range(steps - 1, -1, -1):
        soft = pygame.transform.smoothscale(soft, (max(1, w >> i), max(1, h >> i)))
    return soft


ui = types.ModuleType("_ui")
ui.__dict__.update(PANEL=UI_PANEL, PANEL_IN=UI_PANEL_IN, EDGE=UI_EDGE, TEXT=UI_TEXT, MUTED=UI_MUTED, COLORS=UI_COLORS,
                   LIP=UI_LIP, juice=ui_juice, label=ui_label, panel=ui_panel, inset=ui_inset, button=ui_button,
                   tag=ui_tag, pop=ui_pop, blur=ui_blur)
sys.modules["_ui"] = ui

import _fx as fx
from _achievements import SECRET_NAMES
from _achievements import icon_name as achievement_icon
from _bignum import Big
from _cards import BUFFS, DEBUFFS
from _engine import Engine, Profile
from _pages import Pages
from _perkpages import PerkPages
from _treeview import TreeView

# --- Settings ---
W, H = 1600, 900
FPS = 60
TITLE = "Infinideck"
SAVE_DIR = Path(os.environ.get("INFINIDECK_SAVES") or ASSETS / "Saves")
PROFILES = 5
AUTOSAVE_SECONDS = 360
FLIGHT = 0.5                    # seconds from the deck to the table
FLIP_FRAMES = 22                # the flip at the end of the flight
CINEMATIC = 3.6                 # flight time for a card rarer than 1 in a million
MOD_STAY = 1.6                  # extra seconds on the table for each modifier on a card (up to 3)
ULTRA_RARE = 1e-6
MAX_TABLE = 24
DECK_POS = (W // 2, H // 2 + 10)
DECK_SCALE = 1.4                # the deck in the middle is bigger than the cards on the table
FADE_IDLE = 5.0                 # seconds a landed card stays when you stop pulling
FADE_BUSY = 3.0                 # ... and while you keep pulling
FADE_TIME = 0.6
INTRO_SECONDS = 2.0             # everything glides into place when the game or a save opens
BIG_PAYOUT = 3.0                # a payout 1,000x (10^3) bigger than your usual cards shakes the screen
TEST_WINDOW = (os.environ.get("SDL_VIDEO_WINDOW_POS", "").startswith("-")
               or bool(os.environ.get("INFINIDECK_WINDOWED")))     # tests: never go fullscreen
BG = (3, 3, 7)
PANEL = (16, 15, 22)
PANEL_EDGE = (52, 46, 62)
TEXT = (238, 234, 226)
MUTED = (150, 146, 160)
RED = (222, 64, 64)
GOLD = (255, 205, 90)
MUTE = bool(os.environ.get("INFINIDECK_MUTE"))
TOAST_SECONDS = 2.8
MENU_INFO = {                   # colour, icon (assets\Particles), a short line under the name
    "Home": ("red", "token", "Back to the table"),
    "Skill Tree": ("green", "sparkle6", "Upgrades, decks and Transcending"),
    "Index": ("orange", "gem", "Every card you've found"),
    "Deck": ("purple", "coin_1", "Duplicate, raise or delete cards"),
    "Perks": ("pink", "star5", "Equip perks from Shattering"),
    "Achievements": ("cyan", "crown", "171 to find, and some secrets"),
    "Stats": ("blue", "arrow", "Your records"),
    "Settings": ("gray", "gear", "Sound, music, screen, Discord"),
    "Developers": ("teal", "heart", "Who made Infinideck"),
}
MENU_ITEMS = list(MENU_INFO)
FULL_PAGES = ("Skill Tree", "Index", "Deck", "Stats", "Perks", "Achievements", "Settings", "Developers")
CUTSCENE_GAP = 45.0             # seconds between "beyond rarity" cutscenes (late game rolls lots of them)
DEVELOPERS = [                  # name, role, picture (assets\Developers), outline colour
    ("Silverrshard", "Owner", "silverrshard", (90, 140, 255)),
    ("JamJamGorilla", "Dev", "jamjamgorilla", (40, 220, 190)),
]
VERSION = "1.1.0"
TUTORIAL = [
    ("Welcome to Infinideck", ("An endless deck of cards. Every card you pull pays chips, and chips buy upgrades "
                              "that make every pull worth more."), None),
    ("Pull cards", ("Click the deck in the middle (or hold Space) to pull a card. 2 to 10 pay their number, J, Q and "
                   "K pay 10, and Aces pay 11. Cards go back into the deck, so it never runs out."), "deck"),
    ("Your chips", ("Your chips live here, top right. Below them are Transcendent Points, which you'll earn much "
                   "later. Big numbers shorten: 1M, 1B, 1T, 1Qd, 1Qt."), "counter"),
    ("Modifiers", ("Some cards roll modifiers. Buffs (green) pay more, debuffs (dark red) hurt. They stack, and "
                  "a card with modifiers shows how rare it is above it. Some are rarer than 1 in a million."), None),
    ("The menu", ("Open the menu here for the Skill Tree (Main, Decks and Transcend tabs), the Index of every card, "
                 "your Deck, Perks, Stats and Achievements."), "menu"),
    ("That's it", "The game saves every 6 minutes and when you quit. Pull your first cards!", None),
]


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def ease_out(t):
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    return 3 * t * t - 2 * t * t * t


# --- Sound effects (assets\Sound effects\<name>_<n>.wav) and background music (assets\Music\*.ogg) ---
SFX_DIR = ASSETS / "Sound effects"
MUSIC_DIR = ASSETS / "Music"
MUSIC_END = pygame.USEREVENT + 7            # a track finished: play the next one


class Sound:
    def __init__(self, settings):
        self.ok = False
        self.on = settings.get("sound", True)
        self.sfx_volume = settings.get("sfx_volume", 0.8)
        self.music_on = settings.get("music", True)
        self.music_volume = settings.get("music_volume", 0.45)
        self.track = settings.get("track", "Shuffle")
        self.sounds = {}
        self.tracks = sorted(MUSIC_DIR.glob("*.ogg")) + sorted(MUSIC_DIR.glob("*.wav"))
        self.playing = None
        if MUTE:
            return
        try:
            pygame.mixer.init(44100, -16, 2, 512)
            pygame.mixer.set_num_channels(32)
        except pygame.error:
            return
        self.ok = True
        for f in sorted(SFX_DIR.glob("*.wav")):
            name = f.stem.rsplit("_", 1)[0]
            try:
                self.sounds.setdefault(name, []).append(pygame.mixer.Sound(str(f)))
            except pygame.error:
                pass

    def play(self, name, volume=1.0):
        if not self.ok or not self.on or name not in self.sounds:
            return
        snd = random.choice(self.sounds[name])
        snd.set_volume(clamp(volume * self.sfx_volume, 0, 1))
        snd.play()

    # --- Music ---
    def track_names(self):
        return ["Shuffle"] + [t.stem for t in self.tracks]

    def start_music(self, pick=None):
        """Starts the chosen track (or a random one on Shuffle). Each track plays once, then the next one starts."""
        if not self.ok or not self.tracks:
            return
        if not self.music_on:
            pygame.mixer.music.stop()
            self.playing = None
            return
        names = {t.stem: t for t in self.tracks}
        if pick is None:
            if self.track in names:
                pick = names[self.track]
            else:
                choices = [t for t in self.tracks if t != self.playing] or self.tracks
                pick = random.choice(choices)
        try:
            pygame.mixer.music.load(str(pick))
            pygame.mixer.music.set_volume(self.music_volume)
            pygame.mixer.music.play(fade_ms=1500)
            pygame.mixer.music.set_endevent(MUSIC_END)
            self.playing = pick
        except pygame.error:
            self.playing = None

    def set_music_volume(self, v):
        self.music_volume = clamp(v, 0.0, 1.0)
        if self.ok:
            pygame.mixer.music.set_volume(self.music_volume)

    def now_playing(self):
        return self.playing.stem if self.playing else "Nothing"


# --- Discord Rich Presence: shows "Playing Infinideck" and your chips on your Discord profile. Talks to the Discord
# app over its local pipe, in a background thread, so a missing or slow Discord never freezes the game. ---
DISCORD_APP_ID = "1573174061545037854"     # the Application ID of an "Infinideck" app made at discord.com/developers (its name shows)
PRESENCE_EVERY = 15.0                      # Discord only accepts an update every 15 seconds


class Presence:
    def __init__(self, on):
        self.on = on and bool(DISCORD_APP_ID) and sys.platform == "win32" and not TEST_WINDOW
        self.want = None                    # (details, state) to show next
        self.started = int(time.time())
        self.status = "Off"
        self.lock = threading.Lock()
        self.thread = None
        if self.on:
            self.start()

    def start(self):
        if self.thread is None or not self.thread.is_alive():
            self.thread = threading.Thread(target=self.worker, daemon=True)
            self.thread.start()

    def set_on(self, on):
        self.on = on and bool(DISCORD_APP_ID) and sys.platform == "win32"
        if self.on:
            self.start()
        else:
            self.status = "Off"

    def update(self, details, state):
        with self.lock:
            self.want = (details, state)

    @staticmethod
    def frame(op, data):
        body = json.dumps(data).encode("utf-8")
        return struct.pack("<II", op, len(body)) + body

    @staticmethod
    def read(pipe):
        head = pipe.read(8)
        if len(head) < 8:
            raise OSError("closed")
        _op, size = struct.unpack("<II", head)
        return json.loads(pipe.read(size).decode("utf-8"))

    def connect(self):
        for i in range(10):
            try:
                pipe = open(rf"\\?\pipe\discord-ipc-{i}", "r+b", buffering=0)  # noqa: SIM115
            except OSError:
                continue
            try:
                pipe.write(self.frame(0, {"v": 1, "client_id": DISCORD_APP_ID}))
                self.read(pipe)
                return pipe
            except (OSError, ValueError):
                pipe.close()
        return None

    def worker(self):
        pipe, sent = None, None
        while self.on:
            if pipe is None:
                pipe = self.connect()
                self.status = "Connected" if pipe else "Discord isn't open"
                if pipe is None:
                    time.sleep(20)
                    continue
            with self.lock:
                want = self.want
            if want and want != sent:
                activity = {"details": want[0][:120], "state": want[1][:120], "timestamps": {"start": self.started},
                            "assets": {"large_image": "infinideck", "large_text": "Infinideck"}}
                msg = {"cmd": "SET_ACTIVITY", "args": {"pid": os.getpid(), "activity": activity},
                       "nonce": str(time.time())}
                try:
                    pipe.write(self.frame(1, msg))
                    self.read(pipe)
                    sent = want
                except (OSError, ValueError):
                    pipe.close()
                    pipe, sent = None, None
                    continue
            time.sleep(PRESENCE_EVERY)
        if pipe is not None:
            try:
                pipe.write(self.frame(1, {"cmd": "SET_ACTIVITY", "args": {"pid": os.getpid()}, "nonce": "off"}))
                pipe.close()
            except OSError:
                pass


# --- Saving: 5 profiles as .dat files in assets\Saves, a backup of the last good save, and a marker that catches
# crashes mid-save. A .dat file is a short header line plus the compressed save, and every version of the game reads
# every older one (missing things get their starting value), so saves can be copied between copies of the game. ---
SAVE_HEADER = b"INFINIDECK SAVE 1\n"
OLD_SAVE_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "Infinideck"     # where saves used to go


def pack(data):
    return SAVE_HEADER + zlib.compress(json.dumps(data).encode("utf-8"), 6)


def unpack(raw):
    """Reads a .dat save (or an old plain JSON one)."""
    if raw.startswith(b"INFINIDECK SAVE"):
        raw = zlib.decompress(raw.split(b"\n", 1)[1])
    return json.loads(raw.decode("utf-8"))


class Saves:
    def __init__(self):
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        self._meta = None
        self._summaries = {}
        self.bring_old_saves()

    def bring_old_saves(self):
        """Copies saves from the old %APPDATA%\\Infinideck folder the first time this version runs."""
        if os.environ.get("INFINIDECK_SAVES") or (SAVE_DIR / "settings.dat").exists() or not OLD_SAVE_DIR.is_dir():
            return
        for old in OLD_SAVE_DIR.glob("profile_*.json"):
            new = SAVE_DIR / (old.stem + ".dat")
            if not new.exists():
                try:
                    new.write_bytes(pack(json.loads(old.read_text(encoding="utf-8"))))
                except (OSError, ValueError):
                    pass
        try:
            self.write_meta(json.loads((OLD_SAVE_DIR / "settings.json").read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass

    def path(self, slot, kind="dat"):
        return SAVE_DIR / f"profile_{slot}.{kind}"

    def meta(self):
        if self._meta is None:
            try:
                self._meta = unpack((SAVE_DIR / "settings.dat").read_bytes())
            except (OSError, ValueError, zlib.error):
                self._meta = {}
        return dict(self._meta)

    def write_meta(self, data):
        self._meta = dict(data)
        try:
            (SAVE_DIR / "settings.dat").write_bytes(pack(data))
        except OSError:
            pass

    def setting(self, name, default):
        return self.meta().get(name, default)

    def set(self, name, value):
        m = self.meta()
        m[name] = value
        self.write_meta(m)

    def save(self, slot, data):
        main, bak, tmp, marker = (self.path(slot), self.path(slot, "bak"), self.path(slot, "tmp"),
                                  self.path(slot, "saving"))
        marker.write_text(str(time.time()), encoding="utf-8")      # if we crash before removing this, use the backup
        tmp.write_bytes(pack(data))
        if main.exists():
            os.replace(main, bak)
        os.replace(tmp, main)
        marker.unlink(missing_ok=True)
        self._summaries.pop(slot, None)

    @staticmethod
    def read(path):
        try:
            return unpack(path.read_bytes())
        except (OSError, ValueError, zlib.error, IndexError):
            return None

    def load(self, slot):
        """Returns (data or None, warning text or "")."""
        main, bak, marker = self.path(slot), self.path(slot, "bak"), self.path(slot, "saving")
        warning = ""
        data = None
        if marker.exists():
            warning = "The game closed while saving last time, so this profile was loaded from the save before it."
            marker.unlink(missing_ok=True)
        elif main.exists():
            data = self.read(main)
            if data is None:
                warning = "This profile's save was damaged, so it was loaded from the save before it."
        if data is None and bak.exists():
            data = self.read(bak)
            if data is None:
                warning = "This profile's saves were damaged, so it starts fresh."
        return data, warning

    def summary(self, slot):
        """The profile screen's info for a slot (read once, then kept until that slot changes)."""
        if slot not in self._summaries:
            data = None
            for p in (self.path(slot), self.path(slot, "bak")):
                if p.exists():
                    data = self.read(p)
                    if data is not None:
                        break
            self._summaries[slot] = data
        return self._summaries[slot]

    def delete(self, slot):
        for kind in ("dat", "bak", "tmp", "saving"):
            self.path(slot, kind).unlink(missing_ok=True)
        self._summaries.pop(slot, None)


# --- Settings page ---
PARTICLE_LEVELS = {"Low": 0.5, "Normal": 1.0, "Lots": 1.6}


class SettingsPage:
    def __init__(self, game):
        self.g = game
        self.drag = None                # the slider being dragged
        self.flash = (None, 0.0)

    def cards(self):
        return [("Sound and music", pygame.Rect(60, 110, 480, 640)), ("Screen and Discord", pygame.Rect(560, 110, 480, 640)),
                ("Game", pygame.Rect(1060, 110, 480, 640))]

    def layout(self):
        """Every control: (kind, key, rect, label)."""
        (_, a), (_, b), (_, c) = self.cards()
        out = []
        x, y = a.x + 28, a.y + 76
        out.append(("toggle", "sound", pygame.Rect(x, y, a.w - 56, 52), "Sound effects"))
        out.append(("slider", "sfx_volume", pygame.Rect(x, y + 70, a.w - 56, 56), "Effects volume"))
        out.append(("toggle", "music", pygame.Rect(x, y + 150, a.w - 56, 52), "Background music"))
        out.append(("slider", "music_volume", pygame.Rect(x, y + 220, a.w - 56, 56), "Music volume"))
        out.append(("picker", "track", pygame.Rect(x, y + 300, a.w - 56, 96), "Track"))
        out.append(("button", "next_track", pygame.Rect(x, y + 420, a.w - 56, 46), "Play another track now"))
        x, y = b.x + 28, b.y + 76
        out.append(("toggle", "fullscreen", pygame.Rect(x, y, b.w - 56, 52), "Fullscreen (Alt+Enter)"))
        out.append(("choice", "particles", pygame.Rect(x, y + 90, b.w - 56, 50), "Particles"))
        out.append(("toggle", "discord", pygame.Rect(x, y + 230, b.w - 56, 52), "Discord Rich Presence"))
        x, y = c.x + 28, c.y + 76
        out.append(("button", "tutorial", pygame.Rect(x, y, c.w - 56, 50), "Play the tutorial again"))
        out.append(("button", "save", pygame.Rect(x, y + 70, c.w - 56, 50), "Save now"))
        out.append(("button", "folder", pygame.Rect(x, y + 140, c.w - 56, 50), "Open the saves folder"))
        return out

    def value(self, key):
        g, s = self.g, self.g.sound
        return {"sound": s.on, "music": s.music_on, "fullscreen": g.fullscreen, "discord": g.discord.on,
                "sfx_volume": s.sfx_volume, "music_volume": s.music_volume}.get(key)

    # --- Input ---
    def handle(self, e, now):
        g, s = self.g, self.g.sound
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if g.back_rect().collidepoint(e.pos):
                g.set_page("Home", now)
                return True
            for kind, key, r, _label in self.layout():
                if kind == "slider" and r.inflate(0, 10).collidepoint(e.pos):
                    self.drag = (key, r)
                    self.set_slider(key, r, e.pos[0])
                    return True
                if kind == "choice" and r.collidepoint(e.pos):
                    names = list(PARTICLE_LEVELS)
                    i = min(len(names) - 1, (e.pos[0] - r.x) * len(names) // r.w)
                    g.saves.set("particles", names[i])
                    fx.EMIT_SCALE = PARTICLE_LEVELS[names[i]]
                    s.play("click", 0.5)
                    return True
                if kind == "picker" and r.collidepoint(e.pos):
                    names = s.track_names()
                    i = names.index(s.track) if s.track in names else 0
                    i = (i + (1 if e.pos[0] > r.centerx else -1)) % len(names)
                    s.track = names[i]
                    g.saves.set("track", s.track)
                    s.start_music()
                    s.play("click", 0.5)
                    g.profile.ach["track_changed"] = True
                    return True
                if r.collidepoint(e.pos) and kind in ("toggle", "button"):
                    self.press(key, now)
                    return True
            return True
        if e.type == pygame.MOUSEMOTION and self.drag:
            self.set_slider(self.drag[0], self.drag[1], e.pos[0])
            return True
        if e.type == pygame.MOUSEBUTTONUP and self.drag:
            self.drag = None
            s.play("click", 0.6)
            return True
        return e.type in (pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL)

    def set_slider(self, key, r, x):
        v = clamp((x - r.x - 10) / (r.w - 20), 0.0, 1.0)
        if key == "sfx_volume":
            self.g.sound.sfx_volume = v
        else:
            self.g.sound.set_music_volume(v)
        self.g.saves.set(key, round(v, 3))

    def press(self, key, now):
        g, s = self.g, self.g.sound
        self.flash = (key, now)
        if key == "sound":
            g.toggle_sound()
        elif key == "music":
            s.music_on = not s.music_on
            g.saves.set("music", s.music_on)
            s.start_music()
            s.play("click", 0.5)
        elif key == "fullscreen":
            g.toggle_fullscreen()
        elif key == "discord":
            g.discord.set_on(not g.discord.on)
            g.saves.set("discord", g.discord.on)
            g.update_presence()
            s.play("click", 0.5)
        elif key == "next_track" and s.tracks:
            i = s.tracks.index(s.playing) if s.playing in s.tracks else -1
            nxt = s.tracks[(i + 1) % len(s.tracks)]
            if s.track != "Shuffle":
                s.track = nxt.stem
                g.saves.set("track", s.track)
            s.music_on = True
            s.start_music(nxt)
            s.play("click", 0.5)
        elif key == "tutorial":
            g.set_page("Home", now)
            g.tutorial_step = 0
            g.tutorial_t = now
        elif key == "save":
            g.save()
            s.play("buy", 0.5)
        elif key == "folder":
            try:
                os.startfile(str(SAVE_DIR))          # opens Explorer on the saves folder
            except (OSError, AttributeError):
                s.play("bad", 0.3)

    # --- Drawing ---
    def draw(self, screen, now):
        g, s = self.g, self.g.sound
        ui_label(screen, "Settings", 44, (240, 18))
        ui_button(screen, g.back_rect(), "Back to the table", "orange", now, key="set-back", size=17)
        for i, (title, r) in enumerate(self.cards()):
            rr = r.move(0, int(40 * (1 - ease_out(clamp((now - g.page_t - i * 0.06) / 0.35, 0, 1)))))
            ui_panel(screen, rr, (16, 16, 22), radius=22)
            icon = art.asset("Particles/" + ("wave", "flare", "gear")[i], 34, (255, 214, 150))
            if icon is not None:
                screen.blit(icon, icon.get_rect(center=(rr.x + 44, rr.y + 38)))
            ui_label(screen, title, 24, (rr.x + 70, rr.y + 22))
        mouse = pygame.mouse.get_pos()
        for kind, key, r, label in self.layout():
            hover = r.collidepoint(mouse)
            if kind == "toggle":
                self.draw_toggle(screen, r, label, bool(self.value(key)), hover, now, key)
            elif kind == "slider":
                self.draw_slider(screen, r, label, self.value(key), hover or (self.drag and self.drag[0] == key))
            elif kind == "picker":
                ui_label(screen, label, 17, (r.x, r.y), UI_MUTED, bold=False)
                box = ui_inset(screen, pygame.Rect(r.x, r.y + 26, r.w, 48), radius=12)
                ui_label(screen, s.track, 20, box.center, anchor="center")
                for side, txt in ((-1, "<"), (1, ">")):
                    cx = box.x + 24 if side < 0 else box.right - 24
                    ui_label(screen, txt, 26, (cx, box.centery), (255, 214, 150) if hover else UI_TEXT, "center")
                ui_label(screen, f"Now playing: {s.now_playing()}", 14, (r.x, r.y + 80), UI_MUTED, bold=False)
            elif kind == "choice":
                ui_label(screen, label, 17, (r.x, r.y - 26), UI_MUTED, bold=False)
                names = list(PARTICLE_LEVELS)
                cur = g.saves.setting("particles", "Normal")
                w = r.w // len(names)
                for i, n in enumerate(names):
                    ui_button(screen, pygame.Rect(r.x + i * w + 4, r.y, w - 8, r.h - 6), n,
                              "purple" if n == cur else "dark", now, key=("part", n), size=17, selected=n == cur)
            elif kind == "button":
                ui_button(screen, r, label, "blue" if key != "folder" else "dark", now, key=("setbtn", key), size=17)
        (_, b), (_, c) = self.cards()[1], self.cards()[2]
        status = g.discord.status if DISCORD_APP_ID else "Needs a Discord app ID (see the README)"
        ui_label(screen, f"Status: {status}", 15, (b.x + 28, b.y + 380), UI_MUTED, bold=False)
        for i, line in enumerate(wrap("Shows 'Playing Infinideck', the page you're on and your chips on your Discord "
                                      "profile while the Discord app is open.", art.font(14), b.w - 56)):
            ui_label(screen, line, 14, (b.x + 28, b.y + 406 + i * 20), (150, 156, 166), bold=False, shadow=False)
        keys = [("Space or click the deck", "Pull a card"), ("Esc", "Menu / back"), ("M", "Sound on or off"),
                ("Alt+Enter", "Fullscreen"), ("Right-click a card", "Pin it (Card Lock perk)")]
        ui_label(screen, "Keys", 20, (c.x + 28, c.y + 300))
        for i, (k, what) in enumerate(keys):
            y = c.y + 336 + i * 36
            ui_tag(screen, k, "chips", (c.x + 28, y), 14)
            ui_label(screen, what, 15, (c.right - 28, y + 2), (210, 214, 222), "topright", bold=False)
        ui_label(screen, f"Infinideck {VERSION}   Saves: assets\\Saves", 14, (c.x + 28, c.bottom - 44), UI_MUTED,
                 bold=False)

    @staticmethod
    def draw_toggle(screen, r, label, on, hover, now, key):
        ui_label(screen, label, 19, (r.x, r.centery), UI_TEXT if hover else (226, 230, 236), "midleft", bold=False)
        track = pygame.Rect(r.right - 84, r.centery - 17, 84, 34)
        k = ui_juice(("tog", key), hover, now)
        face = UI_COLORS["green"][0] if on else (52, 54, 66)
        pygame.draw.rect(screen, (0, 0, 0), track.inflate(6, 6), border_radius=20)
        pygame.draw.rect(screen, face, track, border_radius=17)
        knob_x = track.right - 17 if on else track.x + 17
        pygame.draw.circle(screen, (0, 0, 0), (knob_x, track.centery + 2), int(14 * k))
        pygame.draw.circle(screen, (246, 244, 238), (knob_x, track.centery), int(13 * k))
        ui_label(screen, "On" if on else "Off", 13, (track.x - 12, track.centery), UI_MUTED, "midright", bold=False)

    @staticmethod
    def draw_slider(screen, r, label, v, active):
        ui_label(screen, label, 17, (r.x, r.y), UI_MUTED, bold=False)
        ui_label(screen, f"{round(v * 100)}%", 17, (r.right, r.y), UI_TEXT, "topright")
        bar = ui_inset(screen, pygame.Rect(r.x, r.y + 30, r.w, 16), radius=8)
        fill = bar.inflate(-4, -4)
        fill.width = max(6, int(fill.width * v))
        face, lip = UI_COLORS["orange"]
        pygame.draw.rect(screen, lip, fill, border_radius=6)
        pygame.draw.rect(screen, face, fill.inflate(0, -3).move(0, -1), border_radius=6)
        kx = bar.x + 10 + int((bar.w - 20) * v)
        pygame.draw.circle(screen, (0, 0, 0), (kx, bar.centery + 2), 14 if active else 12)
        pygame.draw.circle(screen, (246, 244, 238), (kx, bar.centery), 13 if active else 11)


# --- Developers page ---
class DevelopersPage:
    def __init__(self, game):
        self.g = game
        self.sparks = []                # this page's own particles (the table's stay on the table)
        self.last = time.time()

    def handle(self, e, now):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.g.back_rect().collidepoint(e.pos):
            self.g.set_page("Home", now)
            return True
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for i, r in enumerate(self.bars()):
                if r.collidepoint(e.pos):
                    self.g.sound.play("sparkle", 0.5)
                    for _ in range(30):
                        a = random.uniform(0, math.tau)
                        v = random.uniform(80, 260)
                        self.sparks.append(spark((r.x + 80, r.centery), (math.cos(a) * v, math.sin(a) * v),
                                                 DEVELOPERS[i][3], random.uniform(0.5, 0.9), random.uniform(12, 22), 0,
                                                 random.choice(("sparkle4", "star5", "heart"))))
        return e.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEWHEEL)

    @staticmethod
    def bars():
        return [pygame.Rect(W // 2 - 520, 300 + i * 190, 1040, 140) for i in range(len(DEVELOPERS))]

    def draw(self, screen, now):
        g = self.g
        ui_label(screen, "Developers", 44, (240, 18))
        ui_button(screen, g.back_rect(), "Back to the table", "orange", now, key="dev-back", size=17)
        ui_label(screen, "The people who made Infinideck", 22, (W // 2, 200), UI_MUTED, "center", bold=False)
        mouse = pygame.mouse.get_pos()
        for i, ((name, role, pic, col), r) in enumerate(zip(DEVELOPERS, self.bars())):
            k = ease_out(clamp((now - g.page_t - 0.1 - i * 0.12) / 0.45, 0, 1))
            rr = r.move(int((1 - k) * (300 if i % 2 else -300)), 0)
            hover = rr.collidepoint(mouse)
            glow = art.glow("glow", 360, col, 60 if not hover else 110)
            if glow is not None:
                screen.blit(pygame.transform.smoothscale(glow, (rr.w + 160, rr.h + 120)),
                            (rr.x - 80, rr.y - 60), special_flags=pygame.BLEND_RGB_ADD)
            body = pygame.Surface(rr.size, pygame.SRCALPHA)
            body.fill((8, 14, 38, int(235 * k)))
            for y in range(0, rr.h, 4):                         # faint scanlines
                pygame.draw.line(body, (255, 255, 255, 8), (0, y), (rr.w, y))
            screen.blit(body, rr.topleft)
            pulse = 0.6 + 0.4 * math.sin(now * 2.4 + i)
            line = art.mix((20, 30, 60), col, pulse)
            pygame.draw.rect(screen, line, rr, 3)
            for cx, cy, dx, dy in ((rr.x, rr.y, 1, 1), (rr.right - 1, rr.y, -1, 1), (rr.x, rr.bottom - 1, 1, -1),
                                   (rr.right - 1, rr.bottom - 1, -1, -1)):   # corner brackets
                pygame.draw.line(screen, col, (cx - dx * 6, cy - dy * 6), (cx + dx * 34, cy - dy * 6), 4)
                pygame.draw.line(screen, col, (cx - dx * 6, cy - dy * 6), (cx - dx * 6, cy + dy * 34), 4)
            sweep = (now * 0.35 + i * 0.5) % 1.4                 # a light sweep across the bar
            if sweep < 1:
                band = pygame.Surface((90, rr.h - 6), pygame.SRCALPHA)
                for j in range(90):
                    pygame.draw.line(band, (*col, int(26 * (1 - abs(j - 45) / 45))), (j, 0), (j, rr.h))
                clip = screen.get_clip()
                screen.set_clip(rr.inflate(-6, -6))
                screen.blit(band, (rr.x + int((rr.w + 90) * sweep) - 90, rr.y + 3))
                screen.set_clip(clip)
            avatar = art.asset(f"Developers/{pic}", 104)
            ac = (rr.x + 80, rr.centery)
            pygame.draw.circle(screen, (0, 0, 0), (ac[0], ac[1] + 3), 58)
            pygame.draw.circle(screen, col, ac, 57)
            if avatar is not None:
                screen.blit(avatar, avatar.get_rect(center=ac))
            ring_a = now * 1.5
            for j in range(3):
                a = ring_a + j * math.tau / 3
                pygame.draw.circle(screen, col, (ac[0] + math.cos(a) * 64, ac[1] + math.sin(a) * 64), 4)
            text = f"@{name} | {role}"
            f = art.font(46, bold=True)
            x = rr.x + 170
            sh = f.render(text, True, (0, 0, 0))
            screen.blit(sh, (x + 3, rr.centery - sh.get_height() // 2 + 3))
            screen.blit(f.render(text, True, art.mix(col, (255, 255, 255), 0.35)), (x, rr.centery - sh.get_height() // 2))
            if hover and random.random() < 0.3:
                self.sparks.append(spark((rr.x + random.uniform(0, rr.w), rr.bottom), (random.uniform(-20, 20), -80),
                                         col, 1.0, random.uniform(10, 16), 0, "sparkle4"))
        dt = min(0.05, now - self.last)
        self.last = now
        self.sparks = fx.update(self.sparks, dt)
        fx.draw(screen, self.sparks)
        ui_label(screen, "Thanks for playing!", 26, (W // 2, H - 110), (255, 214, 150), "center")
        ui_label(screen, f"Infinideck {VERSION}", 15, (W // 2, H - 72), UI_MUTED, "center", bold=False)


# --- Things on the table ---
class TableCard:
    def __init__(self, res, start, target, now, flight):
        self.res = res
        self.card = res.card
        self.payout = res.payout
        self.start = start
        self.target = target
        self.born = now
        self.flight = flight
        self.landed = False
        self.angle = random.uniform(-14, 14)
        self.phase = random.uniform(0, math.tau)
        self.pinned = False             # Card Lock perk
        self.flip_played = False
        self.hover_k = 0.0              # how lifted it is under the mouse
        self.fade = None                # when it started fading away (cards only ever fade out where they are)
        self.burned = res.burned
        mods = len(self.card.buffs) + len(self.card.debuffs)
        self.stay = MOD_STAY * min(mods, 3) if mods else 0.0    # cards with modifiers stay on the table longer

    def fading(self):
        return self.fade is not None

    def start_fade(self, now):
        if self.fade is None:
            self.fade = now
            self.pinned = False

    def progress(self, now):
        return clamp((now - self.born) / self.flight, 0, 1)

    def pos(self, now):
        t = ease_out(self.progress(now))
        x = self.start[0] + (self.target[0] - self.start[0]) * t
        y = self.start[1] + (self.target[1] - self.start[1]) * t - math.sin(t * math.pi) * 70     # a little arc
        if self.landed:
            since = now - self.born - self.flight
            y -= max(0.0, math.sin(since * 14) * 6 * math.exp(-since * 6))                          # tiny bounce
        return x, y


class Flyer:
    """A chip flying to (or from) the counter, carrying part of a payout."""

    def __init__(self, start, end, amount, now, delay, inbound=True):
        self.start, self.end = start, end
        self.amount = amount
        self.t0 = now + delay
        self.dur = random.uniform(0.45, 0.7)
        self.inbound = inbound
        self.bend = random.uniform(-120, 120)
        self.done = False
        self.departed = False


class Floater:
    def __init__(self, surf, pos, now, life=1.2, rise=40, rainbow=None):
        self.surf, self.pos, self.t0, self.life, self.rise = surf, pos, now, life, rise
        self.rainbow = rainbow          # text for a huge payout: animated rainbow letters that shake


def spark(pos, vel, color, life, size, gravity=0.0, sprite="glow", spin=0.0):
    """One particle (see assets\\Core\\_fx.py): a sprite from assets\\Particles, tinted, fading out."""
    return fx.Particle(pos[0], pos[1], vel[0], vel[1], sprite, color, life, size, gravity, spin,
                       sprite not in fx.SOLID)


# --- The game ---
class Game:
    def __init__(self, test=False):
        try:                                    # draw at the screen's real pixels (Windows display scaling made the
            ctypes.windll.shcore.SetProcessDpiAwareness(2)      # window too big for 1080p and 1440p screens)
        except (AttributeError, OSError):
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass
        pygame.init()
        pygame.display.set_caption(TITLE)
        try:
            pygame.display.set_icon(art.casino_chip(64))
        except pygame.error:
            pass
        flags = pygame.SCALED | pygame.RESIZABLE
        self.screen = pygame.display.set_mode((W, H), flags)
        self.saves = Saves()
        self.fullscreen = False
        if not TEST_WINDOW and self.saves.setting("fullscreen", True):
            self.toggle_fullscreen(save=False)
        self.clock = pygame.time.Clock()
        self.sound = Sound(self.saves.meta())
        self.sound.start_music()
        self.discord = Presence(self.saves.setting("discord", True))
        self.rng = random.Random()
        self.test = test
        self.stars = [[random.uniform(0, W), random.uniform(0, H), random.choice((0.3, 0.6, 1.0)),
                       random.uniform(0, math.tau)] for _ in range(230)]
        self.mode = "profiles"
        self.profile = None
        self.warning = ""
        self.warning_t = 0.0
        self.table = []
        self.flyers = []
        self.floaters = []
        self.sparks = []
        self.shown = Big(0)             # the counter's number (catches up as chips land)
        self.next_pull = 0.0
        self.last_autosave = time.time()
        self.menu_open = False
        self.menu_t = 0.0
        self.page = "Home"
        self.page_t = 0.0
        self.tutorial_step = 0
        self.tutorial_t = 0.0
        self.cinematic = None           # TableCard during a "beyond rarity" pull
        self.flash_t = -10.0
        self.rainbow = None             # (pos, start time)
        self.hover_card = None
        self.last_hover_card = None
        self.space_held = False
        self.counter_bump = 0.0
        self.deck_press = 0.0
        self.confirm_delete = None
        self.engine = None
        self.tree = TreeView(self)
        self.pages = Pages(self)
        self.perkpages = PerkPages(self)
        self.toasts = []                # (achievement name, secret, start time)
        self.toast_played = set()
        self.tp_flash = -10.0
        self.world_surf = pygame.Surface((W, H))
        self.covered = False
        self.ui_surf = pygame.Surface((W, H), pygame.SRCALPHA)
        self.last_cutscene = -1e9
        self.intro_t = time.time()
        self.last_pull_t = -10.0
        self.shake_t = -10.0
        self.recent_logs = deque(maxlen=40)    # log10 of recent payouts (to spot huge ones)
        self.waves = []                 # shockwave rings: (pos, start, colour)
        self.spot_img = None            # the cutscene's spotlight hole (made once)
        self.ray_layer = None           # ... and its reusable full-screen layers
        self.dark_layer = None
        self.beats_played = set()
        self.menu_opened = 0.0
        self.menu_blur = None
        self.settings = SettingsPage(self)
        self.devs = DevelopersPage(self)
        self.last_presence = 0.0
        fx.EMIT_SCALE = {"Low": 0.5, "Normal": 1.0, "Lots": 1.6}.get(self.saves.setting("particles", "Normal"), 1.0)
        self.counter_rect = pygame.Rect(W - 400, 14, 380, 110)
        self.deck_back = {}
        meta = self.saves.meta()
        if not meta.get("launched"):                    # very first launch: straight into profile 1
            self.saves.write_meta({"launched": True, "last": 1})
            self.open_profile(1)

    def toggle_fullscreen(self, save=True):
        try:
            pygame.display.toggle_fullscreen()
            self.fullscreen = not self.fullscreen
        except pygame.error:
            return
        if save:
            self.saves.set("fullscreen", self.fullscreen)
            self.sound.play("click", 0.5)

    def intro(self, now, delay=0.0, dur=1.3):
        """0 -> 1 as things glide into place after opening the game or a save."""
        return ease_out(clamp((now - self.intro_t - delay) / dur, 0, 1))

    def toggle_sound(self):
        self.sound.on = not self.sound.on
        self.saves.set("sound", self.sound.on)
        self.sound.play("click", 0.5)

    # --- Profiles ---
    def open_profile(self, slot):
        data, warning = self.saves.load(slot)
        self.profile = Profile.from_json(slot, data)
        self.engine = Engine(self.profile, self.rng)
        self.shown = Big(self.profile.balance)
        self.warning = warning
        self.warning_t = time.time()
        self.table, self.flyers, self.floaters = [], [], []
        self.mode = "play"
        self.page = "Home"
        self.tutorial_step = 0 if not self.profile.tutorial_done else -1
        self.last_autosave = time.time()
        self.intro_t = time.time()
        meta = self.saves.meta()
        meta.update(launched=True, last=slot)
        self.saves.write_meta(meta)

    def save(self):
        if self.profile:
            self.saves.save(self.profile.slot, self.profile.to_json())

    # --- Pulling ---
    def cooldown(self):
        return self.engine.cooldown()

    def can_pull(self, now):
        return (self.mode == "play" and self.page == "Home" and not self.menu_open and now >= self.next_pull
                and self.cinematic is None and self.tutorial_step not in (0, 2, 3, 4, 5))

    def pull(self, now):
        results = self.engine.pull()
        main = results[0]
        card = main.card
        ultra = card.rarity <= ULTRA_RARE and now - self.last_cutscene > CUTSCENE_GAP
        if ultra:
            self.last_cutscene = now
        normal = clamp(self.cooldown() * 1.5, 0.16, FLIGHT)      # faster pulls, faster cards
        flight = CINEMATIC if ultra else normal
        if "Flash" in card.buffs:
            flight = min(0.12, normal)
        elif any(m in card.buffs + card.debuffs for m in ("Heavy", "Weighed Down")):
            flight = normal * 1.8
        tc = TableCard(main, DECK_POS, self.centre_spot() if main.center else self.free_spot(), now, flight)
        self.table.append(tc)
        for i, res in enumerate(results[1:]):                # duplicates fan out next to the original
            spot = (clamp(tc.target[0] + (i + 1) * 34 * (1 if tc.target[0] < W / 2 else -1), 100, W - 100),
                    clamp(tc.target[1] + (i + 1) * 12, 120, H - 100))
            dup = TableCard(res, DECK_POS, spot, now + 0.08 * (i + 1), flight)
            self.table.append(dup)
        self.next_pull = now + self.cooldown() + main.payout.slow + self.engine.perks.take_wait()
        if "Flash" in card.buffs:                               # Flash: pull again straight away
            self.next_pull = now + 0.05
        if "spectrum" in self.engine.perks.events:            # Spectrum clears the debuffs on the table
            self.engine.perks.events.remove("spectrum")
            for other in self.table:
                if other.card.debuffs and other is not tc:
                    other.card.debuffs = []
        self.deck_press = now
        self.last_pull_t = now
        self.sound.play("squish", 0.18)
        self.sound.play("whoosh", 0.2)
        if ultra:
            self.cinematic = tc
            self.sound.play("rare", 0.8)
        while len([t for t in self.table if not t.fading()]) > MAX_TABLE:
            old = next((t for t in self.table if not t.fading() and not t.pinned), None)
            if old is None:
                break
            old.start_fade(now)
        if self.tutorial_step == 1:
            self.tutorial_step = 2

    def centre_spot(self):
        a = random.uniform(0, math.tau)
        return DECK_POS[0] + math.cos(a) * 250, DECK_POS[1] + math.sin(a) * 230

    def free_spot(self):
        """A random table spot away from the deck, the counter and other recent cards."""
        best, best_score = None, -1
        for _ in range(40):
            x, y = random.uniform(150, W - 150), random.uniform(150, H - 120)
            if abs(x - DECK_POS[0]) < 190 and abs(y - DECK_POS[1]) < 225:     # keep clear of the big deck
                continue
            if x > W - 480 and y < 230:                                          # and the counter
                continue
            score = min((math.hypot(x - t.target[0], y - t.target[1]) for t in self.table[-10:]), default=999)
            if score > best_score:
                best, best_score = (x, y), score
        return best or (random.uniform(200, W - 200), random.uniform(200, H - 200))

    def land(self, tc, now):
        tc.landed = True
        pay = tc.payout
        card = tc.card
        pos = tc.pos(now)
        self.sound.play("land", 0.22)
        if pay.crit:
            self.sound.play("crit", 0.45)
            self.burst(pos, (255, 160, 50), 18, 220, 0.7, sprite="sparkle4", size=(14, 24))
            self.burst(pos, (255, 120, 40), 8, 120, 0.5, sprite="flare", size=(30, 50))
        gained = self.engine.bank(tc.res)
        self.burst((pos[0], pos[1] + 60), (230, 225, 215), 6, 50, 0.45, sprite="dust", size=(10, 16))   # dust puff
        mods = card.buffs + card.debuffs
        if mods and "Fog" not in card.debuffs and self.cinematic is not tc:
            fx.burst(self, pos, mods, now, 10 + 6 * len(mods))
        huge = False
        if gained > 0 and not (pay.hidden or pay.fogged or tc.burned):
            lg = gained.log10()
            if len(self.recent_logs) >= 10 and gained > 10_000:
                avg = sum(self.recent_logs) / len(self.recent_logs)
                huge = lg - avg >= BIG_PAYOUT
            self.recent_logs.append(lg)
        # floating text: payout (hidden by Blind / Fog) and rarity
        if pay.hidden or pay.fogged:
            text = art.tag("??? chips", "chips", 20)
        elif tc.burned:
            text = art.tag("Burned", "debuff", 20)
        else:
            text = art.tag(("+" if gained >= 0 else "") + gained.fmt() + " chips", "chips" if gained >= 0 else "debuff",
                           22 if not pay.crit else 26)
        if huge:                                              # a huge payout: shake, boom, rainbow text, confetti
            self.floaters.append(Floater(None, (pos[0], pos[1] - 110), now, life=2.6, rise=60,
                                         rainbow="+" + gained.fmt() + " chips"))
            self.shake_t = now
            self.sound.play("boom", 0.7)
            for i in range(90):
                c = pygame.Color(0)
                c.hsva = (i * 360 / 90, 80, 100, 100)
                a = random.uniform(0, math.tau)
                v = random.uniform(150, 560)
                self.sparks.append(spark(pos, (math.cos(a) * v, math.sin(a) * v - 220), (c.r, c.g, c.b),
                                         random.uniform(0.9, 1.8), random.uniform(10, 16), 520,
                                         random.choice(("confetti_1", "confetti_2", "confetti_3", "sparkle4")),
                                         random.uniform(-500, 500)))
            self.burst(pos, (255, 230, 160), 6, 60, 0.6, sprite="flare", size=(80, 140))
        else:
            self.floaters.append(Floater(text, (pos[0], pos[1] - 100), now, life=1.3))
            self.sound.play("pop", 0.12)
        if pay.crit:
            crit = f"CRIT x{2.5 + self.engine.meta.crit_dmg:g}"
            self.floaters.append(Floater(art.tag(crit, "crit", 16), (pos[0], pos[1] - 128), now, life=1.3))
        if card.dup:
            self.floaters.append(Floater(art.tag("DUPLICATE", "tp", 14), (pos[0], pos[1] - 128), now, life=1.3))
        if card.buffs or card.debuffs:
            self.floaters.append(Floater(self.rarity_tag(card.rarity), (pos[0], pos[1] - 156), now, life=1.8, rise=20))
            if card.rarity <= 0.001 and not card.dup:
                self.sound.play("sparkle", 0.35)
        # chips fly to the counter (or away from it)
        target = self.counter_anchor()
        if gained > 0 and not (pay.hidden or pay.fogged):
            n = int(clamp(3 + gained.log10() * 1.4, 3, 16))
            for i in range(n):
                self.flyers.append(Flyer(pos, target, gained / n, now, i * 0.035))
        elif gained > 0:
            self.shown = self.shown + gained                    # hidden payouts arrive without a show
        loss = pay.balance_hit + (abs(gained) if gained < 0 else Big(0))
        if loss > 0:
            self.sound.play("bad", 0.5)
            n = int(clamp(3 + loss.log10(), 3, 10))
            for i in range(n):
                self.flyers.append(Flyer(target, pos, loss / n, now, i * 0.04, inbound=False))
        if self.cinematic is tc:
            self.cinematic = None
            self.reveal(tc, pos, now)

    @classmethod
    def rarity_tag(cls, rarity, size=15):
        kind = "crit" if rarity <= ULTRA_RARE else "buff" if rarity > 0.001 else "tp"
        return art.tag(cls.rarity_text(rarity), kind, size)

    def counter_anchor(self):
        return self.counter_rect.x + 28, self.counter_rect.y + 24

    def burst(self, pos, color, n, speed, life, size=(10, 18), gravity=0.0, sprite="glow"):
        """A puff of particles."""
        n = max(1, int(n * fx.EMIT_SCALE))
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = random.uniform(speed * 0.3, speed)
            self.sparks.append(spark(pos, (math.cos(a) * v, math.sin(a) * v * 0.6), color,
                                     random.uniform(life * 0.6, life), random.uniform(*size), gravity, sprite,
                                     random.uniform(-200, 200)))

    # --- Update ---
    def update(self, dt, now):
        if self.mode != "play":
            return
        p = self.profile
        self.engine.tick(dt)
        for name in self.engine.unlocked:                  # banners queue up and show one at a time
            start = max(now, self.toasts[-1][2] + TOAST_SECONDS) if self.toasts else now
            self.toasts.append((name, name in SECRET_NAMES, start))
        self.engine.unlocked.clear()
        # Holding Space is read straight from the keyboard every frame (a missed key event can't stop the pulling),
        # and holding the mouse button over the deck works the same way.
        keys = pygame.key.get_pressed()
        holding = (keys[pygame.K_SPACE] and pygame.key.get_focused() and self.space_held) or \
            (pygame.mouse.get_pressed()[0] and self.over_deck(pygame.mouse.get_pos()))
        if not keys[pygame.K_SPACE]:
            self.space_held = False
        if holding and self.can_pull(now):
            self.pull(now)
        for tc in list(self.table):
            if not tc.flip_played and now >= tc.born and \
                    tc.progress(now) >= 1 - FLIP_FRAMES / FPS / max(tc.flight, 0.01):
                tc.flip_played = True
                self.sound.play("flip", 0.3)
            if not tc.landed and tc.progress(now) >= 1:
                self.land(tc, now)
            if tc.landed and not tc.fading() and not tc.pinned:
                busy = now - self.last_pull_t < 0.9
                if now - tc.born - tc.flight > (FADE_BUSY if busy else FADE_IDLE) + tc.stay:
                    tc.start_fade(now)
            if tc.fading() and now - tc.fade > FADE_TIME:
                self.table.remove(tc)
                continue
            if tc.landed and not tc.fading():
                fx.emit(self, tc, now, dt)
        for f in list(self.flyers):
            if now < f.t0:
                continue
            if not f.inbound and not f.departed:
                f.departed = True
                self.shown = self.shown - f.amount
            if now - f.t0 >= f.dur:
                if f.inbound:
                    self.shown = self.shown + f.amount
                    self.counter_bump = now
                    self.sound.play("chip", 0.18)
                    if random.random() < 0.5:
                        self.burst(self.counter_anchor(), (255, 214, 110), 2, 70, 0.5, sprite="sparkle4",
                                   size=(12, 18))
                self.flyers.remove(f)
        if not self.flyers:
            self.shown = Big(p.balance)
        cine = self.cinematic
        if cine is not None and random.random() < 0.8:      # light streams into the rare card while it flies
            cx, cy = cine.pos(now)
            a = random.uniform(0, math.tau)
            d = random.uniform(380, 620)
            life = random.uniform(0.6, 0.9)
            self.sparks.append(spark((cx + math.cos(a) * d, cy + math.sin(a) * d),
                                     (-math.cos(a) * d / life, -math.sin(a) * d / life), self.rare_color(cine.card),
                                     life, random.uniform(10, 20), 0, random.choice(("sparkle4", "glow", "ember"))))
        self.sparks = fx.update(self.sparks, dt)
        self.floaters = [f for f in self.floaters if now - f.t0 < f.life]
        if time.time() - self.last_autosave > AUTOSAVE_SECONDS:
            self.save()
            self.last_autosave = time.time()
            self.floaters.append(Floater(art.tag("Saved", "buff", 13), (W - 80, H - 30), now, life=1.6, rise=8))
        for st in self.stars:
            st[0] -= st[2] * 6 * dt
            st[1] += st[2] * 1.5 * dt
            if st[0] < -2:
                st[0], st[1] = W + 2, random.uniform(0, H)
            if st[1] > H + 2:
                st[1] = -2

    def deck_rect(self):
        r = pygame.Rect(0, 0, int(art.CARD_W * DECK_SCALE), int(art.CARD_H * DECK_SCALE))
        r.center = DECK_POS
        return r

    def over_deck(self, pos):
        return self.deck_rect().inflate(16, 24).collidepoint(pos)

    # --- Drawing ---
    def draw(self, now):
        if self.mode == "profiles":
            self.draw_stars(now)
            self.draw_profiles(now)
            return
        covered = (self.page in FULL_PAGES and now - self.page_t > 0.32 and self.menu_t < 0.01
                   and now - self.tp_flash > 2.0)
        self.covered = covered
        if covered:                                           # a page hides the table: don't draw the table
            self.draw_stars(now)
            self.draw_page(now)
            self.draw_counter(self.screen, now)
            if self.page == "Skill Tree":
                self.draw_floaters(self.screen, now)
            self.draw_overlays(now)
            return
        self.draw_scene(now)
        if now - self.shake_t < 0.9:                          # a huge payout shakes the screen
            amt = 16 * (1 - (now - self.shake_t) / 0.9) ** 2
            frame = self.screen.copy()
            self.screen.fill(BG)
            self.screen.blit(frame, (random.uniform(-amt, amt), random.uniform(-amt, amt)))
        self.draw_overlays(now)

    def draw_scene(self, now):
        cine = self.cinematic
        world = self.world_surf if cine is not None else self.screen
        world.fill(BG)
        self.draw_stars(now, world)
        if cine is not None:
            self.draw_rays(world, cine, now)
        self.draw_deck(world, now)
        self.draw_table(world, now)
        fx.draw(world, self.sparks)
        self.draw_waves(world, now)
        if cine is not None:                                  # the room goes dark around the rare card
            self.draw_spotlight(world, cine, now)
            t = ease_in_out(clamp((now - cine.born) / cine.flight, 0, 1))
            beat = self.heartbeat(cine, now)
            zoom = 1 + 0.6 * t + 0.03 * beat                   # the camera pushes in, pulsing with each heartbeat
            cx, cy = cine.pos(now)
            vw, vh = int(W / zoom), int(H / zoom)              # cut out the part in view, then scale only that up
            ox = clamp(int(cx - vw / 2), 0, W - vw)
            oy = clamp(int(cy - vh / 2), 0, H - vh)
            self.screen.blit(pygame.transform.smoothscale(world.subsurface((ox, oy, vw, vh)), (W, H)), (0, 0))
        ui = self.ui_surf if cine is not None else self.screen
        if cine is not None:
            ui.fill((0, 0, 0, 0))
        self.draw_floaters(ui, now)
        self.draw_counter(ui, now)
        self.draw_flyers(ui, now)
        self.draw_menu_button(ui)
        self.draw_hint(ui, now)
        if cine is not None:                                  # blur the UI during the cutscene
            small = pygame.transform.smoothscale(ui, (W // 8, H // 8))
            blurred = pygame.transform.smoothscale(pygame.transform.smoothscale(small, (W // 4, H // 4)), (W, H))
            blurred.set_alpha(150)
            self.screen.blit(blurred, (0, 0))
        self.draw_rainbow(now)
        k = self.intro(now, 0.0, 1.2)
        if k < 1:                                             # opening: fade in from black
            veil = pygame.Surface((W, H))
            veil.fill(BG)
            veil.set_alpha(int(255 * (1 - k)))
            self.screen.blit(veil, (0, 0))
        if self.page != "Home":
            self.draw_page(now)
            if self.page in FULL_PAGES:
                self.draw_counter(self.screen, now)
                if self.page == "Skill Tree":
                    self.draw_floaters(self.screen, now)

    def draw_overlays(self, now):
        """Menu, flashes, tutorial, perk reveal, toasts and tooltips: everything drawn over the scene."""
        self.draw_menu(now)
        self.draw_tp_flash(now)
        if now - self.flash_t < 1.0:
            white = pygame.Surface((W, H))
            white.fill((255, 255, 255))
            white.set_alpha(int(255 * (1 - (now - self.flash_t))))
            self.screen.blit(white, (0, 0))
        if self.tutorial_step >= 0:
            self.draw_tutorial(now)
        if self.perkpages.reveal:
            self.perkpages.draw_reveal(self.screen, now)
        self.draw_toasts(now)
        if self.warning and time.time() - self.warning_t < 9:
            self.draw_warning()
        if self.hover_card is not None and self.page == "Home" and not self.menu_open and self.tutorial_step < 0:
            self.draw_card_info(self.hover_card, now)

    def draw_stars(self, now, surf=None):
        surf = surf or self.screen
        if surf is self.screen:
            surf.fill(BG)
        for x, y, depth, ph in self.stars:
            tw = 0.6 + 0.4 * math.sin(now * (1.5 + depth) + ph)
            v = int((60 + 150 * depth) * tw)
            if depth > 0.9:
                pygame.draw.circle(surf, (v, v, min(255, v + 20)), (int(x), int(y)), 1)
            else:
                surf.set_at((int(x), int(y)), (v, v, min(255, v + 25)))

    def draw_deck(self, surf, now):
        hover = self.over_deck(pygame.mouse.get_pos()) and self.page == "Home" and not self.menu_open
        lift = (6 if hover else 0) + math.sin(now * 2.2) * 1.5
        since = now - self.deck_press                          # a springy squish each time a card comes out
        squish = math.exp(-since * 11) * math.cos(since * 30) if since < 0.8 else 0.0
        w = int(art.CARD_W * DECK_SCALE * (1 + 0.07 * squish))
        h = int(art.CARD_H * DECK_SCALE * (1 - 0.07 * squish))
        k = self.intro(now, 0.15, 1.4)                        # the deck rises into place when a save opens
        base_y = DECK_POS[1] + int((1 - k) * 520)
        key = (self.profile.deck_style, w, h)
        if key not in self.deck_back:
            if len(self.deck_back) > 40:
                self.deck_back.clear()
            self.deck_back[key] = pygame.transform.smoothscale(art.card_back(self.profile.deck_style), (w, h))
        back = self.deck_back[key]
        bottom = base_y + int(art.CARD_H * DECK_SCALE) // 2           # squish keeps the deck sitting on the table
        sh = art.shadow((w, h), art.RADIUS + 4, 160, 12)
        surf.blit(sh, sh.get_rect(center=(DECK_POS[0] + 10, bottom - h // 2 + 16)))
        for i in range(6):
            x = DECK_POS[0] - w // 2
            y = bottom - h - i * 3 - (lift if i == 5 else 0)
            if i < 5:
                pygame.draw.rect(surf, (200, 192, 176), pygame.Rect(x, y + 3, w, h), border_radius=art.RADIUS + 3)
            surf.blit(back, (x, y))

    def draw_table(self, surf, now):
        mouse = pygame.mouse.get_pos()
        self.hover_card = None
        lifted = self.last_hover_card if self.last_hover_card in self.table else None
        order = [c for c in self.table if c is not lifted] + ([lifted] if lifted else [])   # hovered card on top
        for tc in order:
            x, y = tc.pos(now)
            prog = tc.progress(now)
            flip_window = FLIP_FRAMES / FPS / max(tc.flight, 0.01)
            q = clamp((prog - (1 - flip_window)) / flip_window, 0, 1) if tc.flight > 0.15 else 1.0
            face_up = q >= 0.5
            sx = abs(math.cos(q * math.pi))
            img = art.card_face(tc.card, hide="Fog" in tc.card.debuffs) if face_up else \
                art.card_back(self.profile.deck_style)
            mods = tc.card.buffs + tc.card.debuffs
            if tc.burned and face_up:
                img = img.copy()
                img.fill((90, 60, 50, 255), special_flags=pygame.BLEND_RGBA_MULT)
            elif face_up and mods:                             # the modifiers' moving looks, drawn into the card
                img = img.copy()
                img.blit(fx.overlay(tc.card, now, tc.phase), (0, 0))
            scale = 1.0
            if "Shrink" in tc.card.debuffs and face_up:
                scale = 0.78
            if self.cinematic is tc:
                scale *= 1.25
            if not tc.landed:                                  # leaves the deck at the deck's size
                scale *= 1 + (DECK_SCALE - 1) * (1 - ease_out(prog))
            alpha = 255
            if tc.fade is not None:                            # fading out: it just turns see-through where it is
                alpha = int(255 * clamp(1 - (now - tc.fade) / FADE_TIME, 0, 1))
            target_k = 1.0 if tc is self.last_hover_card else 0.0
            tc.hover_k += (target_k - tc.hover_k) * 0.22
            scale *= 1 + 0.12 * tc.hover_k
            angle = tc.angle * ease_out(prog) + (math.sin(now * 1.3 + tc.phase) * 1.4 if tc.landed else 0)
            if tc.hover_k > 0.01:
                angle = angle * (1 - tc.hover_k) + clamp((x - mouse[0]) * 0.12, -9, 9) * tc.hover_k
                y -= 14 * tc.hover_k
            w = max(1, int(art.CARD_W * sx * scale))
            h = int(art.CARD_H * scale)
            card = pygame.transform.smoothscale(img, (w, h))
            card = pygame.transform.rotate(card, angle)
            height = 0 if tc.landed else math.sin(prog * math.pi) * 18
            height += 10 * tc.hover_k
            sh = art.shadow((max(1, int(art.CARD_W * sx * scale)), h), art.RADIUS, 120, 8)
            sh = pygame.transform.rotate(sh, angle)
            if alpha < 255:
                card.set_alpha(alpha)
                sh = sh.copy()
                sh.set_alpha(alpha)
            if face_up and mods and not tc.burned:             # a glow under the card, one colour per modifier
                fx.under(surf, (x, y - height), ["Fog"] if "Fog" in tc.card.debuffs else mods, now, alpha, scale)
            surf.blit(sh, sh.get_rect(center=(x + 6 + height * 0.6, y + 9 + height)))
            if "Echo" in tc.card.buffs and face_up:
                ghost = card.copy()
                ghost.set_alpha(70)
                surf.blit(ghost, ghost.get_rect(center=(x + 7, y - 6)))
            rect = card.get_rect(center=(x, y - height))
            surf.blit(card, rect)
            if tc.pinned:                                     # Card Lock pin
                pygame.draw.line(surf, (200, 200, 210), (x, rect.top + 4), (x, rect.top + 18), 2)
                pygame.draw.circle(surf, (40, 10, 14), (x + 2, rect.top + 6), 9)
                pygame.draw.circle(surf, (220, 50, 60), (x, rect.top + 4), 8)
            if tc.landed and not tc.fading() and rect.collidepoint(mouse):
                self.hover_card = tc
        self.last_hover_card = self.hover_card

    def draw_floaters(self, surf, now):
        for f in self.floaters:
            t = clamp((now - f.t0) / f.life, 0.0, 1.0)
            a = 255 if t < 0.6 else int(255 * (1 - (t - 0.6) / 0.4))
            if f.rainbow:
                self.draw_rainbow_text(surf, f, now, t, clamp(a, 0, 255))
                continue
            k = ui.pop(now - f.t0)
            img = pygame.transform.rotozoom(f.surf, 0, k) if k != 1.0 else f.surf.copy()
            img.set_alpha(clamp(a, 0, 255))
            surf.blit(img, img.get_rect(center=(f.pos[0], f.pos[1] - f.rise * ease_out(t))))

    def draw_rainbow_text(self, surf, f, now, t, alpha):
        """A huge payout: big letters cycling through the rainbow, shaking a little, very fast."""
        size = int(40 * ui.pop(now - f.t0, 0.35))
        font = art.font(max(8, size), bold=True)
        text = f.rainbow
        width = font.size(text)[0]
        x = clamp(f.pos[0] - width / 2, 20, W - 20 - width)                      # always fully on screen
        y = max(self.counter_rect.bottom + 70, f.pos[1]) - f.rise * ease_out(t)   # and below the counter
        for i, ch in enumerate(text):
            c = pygame.Color(0)
            c.hsva = ((i * 26 + now * 420) % 360, 85, 100, 100)
            jx, jy = random.uniform(-1.6, 1.6), random.uniform(-1.6, 1.6)
            shadow = font.render(ch, True, (0, 0, 0))
            glyph = font.render(ch, True, (c.r, c.g, c.b))
            shadow.set_alpha(alpha * 3 // 4)
            glyph.set_alpha(alpha)
            surf.blit(shadow, (x + jx + 3, y + jy + 3))
            surf.blit(glyph, (x + jx, y + jy))
            x += font.size(ch)[0]

    def gold_chip(self, size):
        return art.asset("chip_gold", size) or art.casino_chip(size)

    def draw_flyers(self, surf, now):
        icon = self.gold_chip(20)
        for f in self.flyers:
            if now < f.t0:
                continue
            t = clamp((now - f.t0) / f.dur, 0, 1)
            e = ease_in_out(t)
            x = f.start[0] + (f.end[0] - f.start[0]) * e + math.sin(e * math.pi) * f.bend
            y = f.start[1] + (f.end[1] - f.start[1]) * e - math.sin(e * math.pi) * 60
            surf.blit(icon, icon.get_rect(center=(x, y)))

    def draw_counter(self, surf, now):
        """The chips counter (red number in a dark box, 'chips' after it) and Transcendent Points under it."""
        p = self.profile
        bump = math.exp(-(now - self.counter_bump) * 12) * 0.06
        num = self.shown.exact() if abs(self.shown.e) < 6 or self.shown < 1_000_000 else self.shown.fmt()
        f = art.font(int(28 * (1 + bump)), mono=True)
        t = f.render(num, True, (255, 96, 86))
        box = pygame.Rect(0, 0, t.get_width() + 50, 40)
        label = art.font(25, bold=True).render("chips", True, TEXT)
        tp_text = f"{p.tp:,}" if p.tp < 1_000_000 else Big(p.tp).fmt()
        tp = art.font(21, mono=True).render(tp_text, True, (236, 92, 92))
        tl = art.font(17, bold=True).render("Transcendent points", True, TEXT)
        tp_pad = 31 if art.asset("tp_crystal", 21) else 9
        total_w = max(box.width + 10 + label.get_width(), tp.get_width() + tp_pad + 17 + tl.get_width())
        slide = int((1 - self.intro(now, 0.35, 1.3)) * (total_w + 80))
        box.topleft = (W - 26 - total_w + slide, 20)
        panel = pygame.Rect(box.x - 9, box.y - 9, total_w + 18, 40 + 6 + 31 + 18 + ui.LIP)
        self.counter_rect = panel
        ui.panel(surf, panel, radius=14, lip=4)
        self.box(surf, box)
        chip = self.gold_chip(29)
        surf.blit(chip, chip.get_rect(center=(box.x + 22, box.centery)))
        surf.blit(t, (box.x + 40, box.centery - t.get_height() // 2))
        ui.label(surf, "chips", 25, (box.right + 10, box.centery), anchor="midleft")
        crystal = art.asset("tp_crystal", 21)
        pad = 31 if crystal else 9
        tbox = pygame.Rect(box.x, box.bottom + 6, tp.get_width() + pad + 9, 31)
        self.box(surf, tbox)
        if crystal:
            surf.blit(crystal, crystal.get_rect(center=(tbox.x + 16, tbox.centery)))
        surf.blit(tp, (tbox.x + pad, tbox.centery - tp.get_height() // 2))
        ui.label(surf, "Transcendent points", 17, (tbox.right + 9, tbox.centery), anchor="midleft")

    @staticmethod
    def box(surf, rect):
        ui.inset(surf, rect, radius=10)

    @staticmethod
    def menu_button_rect():
        return pygame.Rect(18, 18, 54, 50)

    def draw_menu_button(self, surf):
        if self.page != "Home":
            return
        r = self.menu_button_rect().move(0, -int((1 - self.intro(time.time(), 0.25, 1.2)) * 110))
        ui.button(surf, r, "", "red", time.time(), key="menu-button")
        for i in range(3):
            pygame.draw.rect(surf, (0, 0, 0), (r.x + 15, r.y + 15 + i * 9, 26, 4), border_radius=2)
            pygame.draw.rect(surf, TEXT, (r.x + 14, r.y + 13 + i * 9, 26, 4), border_radius=2)

    def draw_hint(self, surf, now):
        if self.profile.cards < 15 and self.tutorial_step < 0:
            ui.label(surf, "Click the deck, or hold Space", 18, (DECK_POS[0], self.deck_rect().bottom + 34),
                     anchor="center", alpha=int(170 + 80 * math.sin(now * 2)))

    def draw_card_info(self, tc, now):
        """Hovering a card on the table shows what it is and what it paid."""
        card, pay = tc.card, tc.payout
        fog = "Fog" in card.debuffs
        lines = []
        title = "???" if fog else card.name()
        if card.dup:
            title += "  (duplicate)"
        lines.append((art.font(20, bold=True).render(title, True, TEXT), None))
        if not fog:
            for b in card.buffs:
                lines.append((art.tag(b, "buff", 14), BUFFS[b][3]))
            for d in card.debuffs:
                lines.append((art.tag(d, "debuff", 14), DEBUFFS[d][1]))
            if card.crit:
                lines.append((art.tag("Critical hit", "crit", 14), f"x{2.5 + self.engine.meta.crit_dmg:g} chips"))
        paid = "??? chips" if (pay.hidden or fog) else f"{pay.chips.fmt()} chips"
        lines.append((art.tag(paid, "chips", 15), None))
        if card.buffs or card.debuffs:                          # how rare this exact card was
            lines.append((self.rarity_tag(card.rarity, 15), "chance of pulling this card"))
        w = max(200, 36 + max(img.get_width() + (8 + art.font(13).size(d)[0] if d else 0) for img, d in lines))
        h = 22 + sum(26 if d else 30 for _, d in lines)
        x, y = pygame.mouse.get_pos()
        x = clamp(x + 18, 10, W - w - 10)
        y = clamp(y + 18, 10, H - h - 10)
        panel = pygame.Rect(x, y, w, h + ui.LIP)
        ui.panel(self.screen, panel, radius=12)
        cy = y + 12
        for img, desc in lines:
            self.screen.blit(img, (x + 14, cy))
            if desc:
                d = art.font(13).render(desc, True, MUTED)
                self.screen.blit(d, (x + 22 + img.get_width(), cy + 2))
            cy += 26 if desc else 30

    # --- The "beyond rarity" cutscene ---
    @staticmethod
    def rare_color(card):
        mods = card.buffs + card.debuffs
        return fx.mod_color(mods[0], time.time()) if mods else GOLD

    def heartbeat(self, cine, now):
        """0..1 pulses that speed up as the rare card gets closer (and play a thump each)."""
        t = (now - cine.born) / cine.flight
        beats = [0.18, 0.42, 0.6, 0.74, 0.84, 0.91, 0.96]
        out = 0.0
        for b in beats:
            if t >= b:
                if (id(cine), b) not in self.beats_played:
                    self.beats_played.add((id(cine), b))
                    self.sound.play("thump", 0.55 + 0.4 * b)
                out = max(out, math.exp(-(t - b) * cine.flight * 9))
        return out

    def draw_rays(self, surf, cine, now):
        """Slowly turning light rays behind the rare card, brighter as it arrives."""
        t = clamp((now - cine.born) / cine.flight, 0, 1)
        cx, cy = cine.pos(now)
        col = self.rare_color(cine.card)
        if self.ray_layer is None:
            self.ray_layer = pygame.Surface((W, H))
        layer = self.ray_layer
        layer.fill((0, 0, 0))
        n = 14
        for i in range(n):
            a = now * 0.35 + i * math.tau / n
            spread = 0.07 + 0.03 * math.sin(now * 2 + i)
            length = 1300
            pts = [(cx, cy), (cx + math.cos(a - spread) * length, cy + math.sin(a - spread) * length),
                   (cx + math.cos(a + spread) * length, cy + math.sin(a + spread) * length)]
            k = (0.25 + 0.75 * t) * (0.6 + 0.4 * math.sin(now * 3 + i * 1.7))
            pygame.draw.polygon(layer, tuple(int(c * 0.22 * k) for c in col), pts)
        surf.blit(layer, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        glow = art.glow("glow", int(260 + 260 * t), col, int(120 + 120 * t))
        if glow is not None:
            surf.blit(glow, glow.get_rect(center=(int(cx), int(cy))), special_flags=pygame.BLEND_RGB_ADD)

    def draw_spotlight(self, surf, cine, now):
        """Darkness everywhere but a soft circle round the rare card."""
        t = ease_out(clamp((now - cine.born) / (cine.flight * 0.5), 0, 1))
        if self.spot_img is None:
            size = 900
            hole = pygame.Surface((size, size), pygame.SRCALPHA)
            for r in range(size // 2, 0, -6):
                a = int(255 * clamp((r / (size / 2) - 0.35) / 0.65, 0, 1) ** 1.5)
                pygame.draw.circle(hole, (0, 0, 0, a), (size // 2, size // 2), r)
            self.spot_img = hole
        cx, cy = cine.pos(now)
        if self.dark_layer is None:                       # made once: darkness twice the screen's size, a hole in the
            dark = pygame.Surface((W * 2, H * 2), pygame.SRCALPHA)          # middle; each frame just slides it
            dark.fill((0, 0, 0, 255))
            dark.blit(self.spot_img, self.spot_img.get_rect(center=(W, H)), special_flags=pygame.BLEND_RGBA_MIN)
            self.dark_layer = dark
        self.dark_layer.set_alpha(int(200 * t))
        surf.blit(self.dark_layer, (int(cx) - W, int(cy) - H))

    def draw_waves(self, surf, now):
        """Shockwave rings after a rare reveal."""
        alive = [w for w in self.waves if now - w[1] <= 1.4]
        self.waves = alive
        if not alive:
            return
        if self.ray_layer is None:
            self.ray_layer = pygame.Surface((W, H))
        layer = self.ray_layer
        layer.fill((0, 0, 0))
        for pos, t0, col in alive:
            t = now - t0
            for k in range(3):                                # three rings, one after another, as real circles
                tk = t - k * 0.12
                if tk <= 0:
                    continue
                f = min(1.0, tk / 1.2)
                r = int(40 + 900 * ease_out(f))
                fade = (1 - f) ** 1.5
                for width, dim in ((22, 0.25), (10, 0.55), (4, 1.0)):     # a soft edge, then a bright core
                    c = tuple(int(v * fade * dim) for v in art.mix(col, (255, 255, 255), 0.3))
                    pygame.draw.circle(layer, c, (int(pos[0]), int(pos[1])), r, width)
        surf.blit(layer, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def reveal(self, tc, pos, now):
        """The rare card lands: flash, shockwaves, a burst of its modifiers' particles and confetti."""
        col = self.rare_color(tc.card)
        self.flash_t = now
        self.rainbow = (pos, now, tc.card.rarity)
        self.waves.append((pos, now, col))
        self.shake_t = now
        self.sound.play("reveal", 0.8)
        fx.burst(self, pos, tc.card.buffs + tc.card.debuffs, now, 120)
        self.burst(pos, col, 10, 90, 1.0, sprite="flare", size=(90, 170))
        for i in range(70):
            c = pygame.Color(0)
            c.hsva = (i * 360 / 70, 70, 100, 100)
            a = random.uniform(0, math.tau)
            v = random.uniform(200, 650)
            self.sparks.append(spark(pos, (math.cos(a) * v, math.sin(a) * v - 260), (c.r, c.g, c.b),
                                     random.uniform(1.0, 2.2), random.uniform(10, 16), 480,
                                     random.choice(("confetti_1", "confetti_2", "confetti_3", "star5")),
                                     random.uniform(-500, 500)))

    def draw_rainbow(self, now):
        if not self.rainbow:
            return
        pos, t0, rarity = self.rainbow
        t = now - t0
        if t > 3.6:
            self.rainbow = None
            return
        alpha = int(255 * clamp(min(t / 0.4, (3.6 - t) / 0.6), 0, 1))
        y = clamp(pos[1] - 210, 110, H - 260)
        for line, size, delay in (("A card beyond rarity reveals itself.", 34, 0.0),
                                  (self.rarity_text(rarity), 54, 0.35)):
            if t < delay:
                continue
            k = ui_pop(t - delay, 0.4)
            f = art.font(max(8, int(size * k)), bold=True)
            x = W // 2 - f.size(line)[0] // 2
            for i, ch in enumerate(line):
                c = pygame.Color(0)
                c.hsva = ((i * 12 + now * 220) % 360, 75, 100, 100)
                sh = f.render(ch, True, (0, 0, 0))
                g = f.render(ch, True, (c.r, c.g, c.b))
                sh.set_alpha(alpha * 3 // 4)
                g.set_alpha(alpha)
                wob = math.sin(now * 6 + i * 0.4) * 4
                self.screen.blit(sh, (x + 3, y + wob + 3))
                self.screen.blit(g, (x, y + wob))
                x += f.size(ch)[0]
            y += size + 18

    @staticmethod
    def rarity_text(rarity):
        n = 1 / max(rarity, 1e-300)
        return f"1 in {Big(round(n) if n < 1e15 else n).fmt()}"

    # --- Menu (slides in from the left over a blurred table) ---
    def menu_rects(self):
        return [pygame.Rect(26, 150 + i * 64, 348, 56) for i in range(len(MENU_ITEMS))]

    def draw_menu(self, now):
        target = 1.0 if self.menu_open else 0.0
        self.menu_t += (target - self.menu_t) * 0.22
        if self.menu_t < 0.01:
            self.menu_blur = None
            return
        e = ease_out(self.menu_t)
        if self.menu_open and self.menu_blur is None:          # the table behind goes soft and dark
            self.menu_blur = ui_blur(self.screen, 6)
        if self.menu_blur is not None:
            self.menu_blur.set_alpha(int(255 * e))
            self.screen.blit(self.menu_blur, (0, 0))
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 4, int(120 * e)))
        self.screen.blit(dim, (0, 0))
        off = int(-440 * (1 - e))
        side = pygame.Rect(off - 40, -20, 440, H + 40)
        ui.panel(self.screen, side, (12, 12, 18), radius=28)
        glow = art.glow("glow", 420, (120, 40, 40), 255)        # a warm light at the top of the menu
        if glow is not None:
            self.screen.blit(glow, glow.get_rect(center=(off + 120, 40)), special_flags=pygame.BLEND_RGB_ADD)
        chip = self.gold_chip(58)                              # the gold chip spins (squashes) by the title
        squash = abs(math.cos(now * 1.4))
        spun = pygame.transform.smoothscale(chip, (max(2, int(chip.get_width() * (0.25 + 0.75 * squash))),
                                                   chip.get_height()))
        self.screen.blit(spun, spun.get_rect(center=(off + 58, 62)))
        title = "INFINIDECK"
        x = off + 100
        f = art.font(40, bold=True)
        for i, ch in enumerate(title):                          # each letter bobs on its own
            y = 40 + math.sin(now * 2.2 + i * 0.45) * 3
            ui.label(self.screen, ch, 40, (x, y), (255, 236, 200) if i % 2 else (255, 214, 150))
            x += f.size(ch)[0] + 1
        p = self.profile
        ui.label(self.screen, f"Profile {p.slot}   {self.shown.fmt()} chips", 16, (off + 102, 92), ui.MUTED,
                 bold=False)
        pygame.draw.line(self.screen, (40, 40, 52), (off + 26, 128), (off + 374, 128), 2)
        mouse = pygame.mouse.get_pos()
        for i, (name, r) in enumerate(zip(MENU_ITEMS, self.menu_rects())):
            delay = clamp((now - self.menu_opened - i * 0.03) / 0.3, 0, 1) if self.menu_open else 1
            r = r.move(off - int(80 * (1 - ease_out(delay))), 0)
            self.draw_menu_item(name, r, now, r.collidepoint(mouse), name == self.page, i)
        for label, rect, color in self.menu_footer(off):
            ui.button(self.screen, rect, label, color, now, key="foot-" + label[:6], size=16)

    def draw_menu_item(self, name, r, now, hover, current, i):
        """One menu row: an icon tile, the name and a short line about it. Hover lifts it and sweeps a shine."""
        color, icon, sub = MENU_INFO[name]
        face, lip = UI_COLORS[color]
        k = ui_juice(("menuitem", name), hover, now)
        rr = r.inflate(int(r.w * (k - 1)), int(r.h * (k - 1))).move(6 if hover else 0, 0)
        body = ui_panel(self.screen, rr, (30, 30, 42) if hover or current else (20, 20, 28), radius=14, lip=4)
        tile = pygame.Rect(body.x + 8, body.y + 6, body.h - 12, body.h - 12)
        pygame.draw.rect(self.screen, lip, tile.move(0, 3), border_radius=10)
        pygame.draw.rect(self.screen, face, tile, border_radius=10)
        img = art.asset("Particles/" + icon, int(tile.h * (0.7 + (0.08 * math.sin(now * 6) if hover else 0))),
                        (255, 255, 255))
        if img is not None:
            self.screen.blit(img, img.get_rect(center=tile.center))
        ui_label(self.screen, name, 22, (tile.right + 14, body.y + 6))
        ui_label(self.screen, sub, 13, (tile.right + 14, body.y + 31), (160, 166, 176), bold=False, shadow=False)
        if current:
            pygame.draw.circle(self.screen, face, (body.right - 18, body.centery), 6)
        if hover:                                               # a shine sweeps across
            t = (now * 1.6) % 1.6
            if t < 1:
                x = body.x + int((body.w + 80) * t) - 40
                band = pygame.Surface((40, body.h), pygame.SRCALPHA)
                for j in range(40):
                    pygame.draw.line(band, (255, 255, 255, int(40 * (1 - abs(j - 20) / 20))), (j, 0), (j, body.h))
                clip = self.screen.get_clip()
                self.screen.set_clip(body)
                self.screen.blit(band, (x, body.y))
                self.screen.set_clip(clip)

    def menu_footer(self, off=0):
        return [("Switch profile", pygame.Rect(off + 26, H - 112, 166, 40), "dark"),
                ("Save and quit", pygame.Rect(off + 208, H - 112, 166, 40), "red")]

    # --- Pages ---
    def draw_page(self, now):
        e = ease_out(clamp((now - self.page_t) / 0.3, 0, 1))
        if self.page in FULL_PAGES and (e < 1 or not self.covered):   # its own starry room over the table
            backdrop = self.world_surf
            backdrop.fill(BG)
            self.draw_stars(now, backdrop)
            backdrop.set_alpha(int(255 * e))
            self.screen.blit(backdrop, (0, 0))
            backdrop.set_alpha(None)
        if self.page == "Skill Tree":
            self.tree.draw(self.screen, now)
            if not self.tree.picker:
                self.perkpages.draw_shatter_button(self.screen, now)
            if self.perkpages.shatter_open:
                self.perkpages.draw_shatter(self.screen, now)
            return
        if self.page in ("Index", "Deck", "Stats"):
            self.pages.draw(self.page, self.screen, now)
            return
        if self.page in ("Perks", "Achievements"):
            self.perkpages.draw(self.page, self.screen, now)
            return
        if self.page == "Settings":
            self.settings.draw(self.screen, now)
        elif self.page == "Developers":
            self.devs.draw(self.screen, now)

    @staticmethod
    def back_rect():
        return pygame.Rect(18, 18, 190, 44)                  # where the menu button is on the table

    def update_presence(self):
        """What Discord shows: the page you're on and your chips."""
        if not self.discord.on or self.profile is None:
            return
        where = "At the table" if self.page == "Home" else f"In the {self.page}"
        self.discord.update(where, f"{self.profile.balance.fmt()} chips, {Big(self.profile.tp).fmt()} TP")

    def on_purchase(self, nid):
        self.counter_bump = time.time()
        self.shown = Big(self.profile.balance)

    def do_shatter(self, now):
        perk = self.engine.shatter()
        if perk is None:
            return
        self.sound.play("shatter", 0.7)
        self.perkpages.reveal = (perk, now)
        self.clear_table(now)
        self.save()

    def do_sacrifice(self, now):
        if not self.engine.sacrifice():
            return
        self.sound.play("shatter", 0.6)
        self.tp_flash = now
        self.clear_table(now)
        self.save()

    def clear_table(self, now):
        for tc in self.table:
            tc.start_fade(now)
        self.flyers.clear()
        self.shown = Big(self.profile.balance)

    def draw_toasts(self, now):
        """Achievement banners that slide in at the bottom right, each with its own icon."""
        alive = []
        y = H - 24
        for name, secret, t0 in self.toasts:
            t = now - t0
            if t > TOAST_SECONDS:
                continue
            alive.append((name, secret, t0))
            if t < 0:
                continue
            if t0 not in self.toast_played:
                self.toast_played.add(t0)
                self.sound.play("achieve", 0.5)
            k = ease_out(clamp(t / 0.35, 0, 1)) * (1 - ease_out(clamp((t - TOAST_SECONDS + 0.4) / 0.4, 0, 1)))
            r = pygame.Rect(0, 0, 520, 76)
            r.bottomright = (W - 24 + int(560 * (1 - k)), y)               # slides in from the right
            fill = (64, 48, 20) if not secret else (56, 36, 80)
            ui.panel(self.screen, r.inflate(0, ui.LIP).move(0, ui.LIP // 2), fill, radius=14)
            shine = (t * 1.4) % 2.0                                         # a light sweep across the banner
            if shine < 1:
                clip = self.screen.get_clip()
                self.screen.set_clip(r)
                x = r.x + int((r.w + 60) * shine) - 60
                band = pygame.Surface((60, r.h), pygame.SRCALPHA)
                for j in range(60):
                    pygame.draw.line(band, (255, 240, 200, int(36 * (1 - abs(j - 30) / 30))), (j, 0), (j, r.h))
                self.screen.blit(band, (x, r.y))
                self.screen.set_clip(clip)
            head = "Secret achievement" if secret else "Achievement unlocked"
            icon = art.asset(achievement_icon(name), int(60 * ui_pop(t, 0.4))) or art.asset("medal", 56)
            tx = r.x + 20
            if icon:
                self.screen.blit(icon, icon.get_rect(center=(r.x + 42, r.centery)))
                tx = r.x + 82
            ui.label(self.screen, head, 14, (tx, r.y + 12), GOLD)
            ui.label(self.screen, name, 22, (tx, r.y + 32))
            y -= 88
        self.toasts = alive

    def do_transcend(self, now):
        gain = self.engine.transcend()
        if not gain:
            return
        self.sound.play("transcend", 0.6)
        self.tp_flash = now
        self.clear_table(now)
        self.shown = Big(0)
        text = f"+{gain:,}" if gain < 1_000_000 else "+" + Big(gain).fmt()
        self.floaters.append(Floater(art.tag(text + " Transcendent points", "tp", 28), (W // 2, H // 2 - 40), now,
                                     life=3.0, rise=30))
        self.save()

    def draw_tp_flash(self, now):
        t = now - self.tp_flash
        if not 0.0 <= t <= 2.0:
            return
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        a = int(235 * (1 - t / 2.0) ** 1.5)
        veil.fill((150, 80, 220, a) if t > 0.15 else (255, 255, 255, a))
        self.screen.blit(veil, (0, 0))
        for i in range(3):
            r = int(t * 900 + i * 140)
            pygame.draw.circle(self.screen, (220, 190, 255), (W // 2, H // 2), r, 3)

    # --- Tutorial ---
    def tutorial_rect(self, focus):
        if focus == "deck":
            return self.deck_rect().inflate(36, 40)
        if focus == "counter":
            return self.counter_rect.inflate(18, 18)
        if focus == "menu":
            return pygame.Rect(18, 18, 54, 50 + ui.LIP).inflate(18, 18)
        return None

    def draw_tutorial(self, now):
        title, body, focus = TUTORIAL[self.tutorial_step]
        hole = self.tutorial_rect(focus)
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 175))
        if hole:
            pygame.draw.rect(dim, (0, 0, 0, 0), hole, border_radius=16)
        self.screen.blit(dim, (0, 0))
        if hole:
            pulse = 2 + int(2 * math.sin(now * 5))
            pygame.draw.rect(self.screen, GOLD, hole.inflate(pulse * 2, pulse * 2), 3, border_radius=18)
        box = self.tutorial_box()
        k = ui.pop(now - self.tutorial_t, 0.3)
        shown = box.inflate(int(box.w * (k - 1)), int(box.h * (k - 1)))
        ui.panel(self.screen, shown.inflate(0, ui.LIP).move(0, ui.LIP // 2), radius=18)
        ui.label(self.screen, title, 28, (box.x + 26, box.y + 18))
        y = box.y + 64
        for line in wrap(body, art.font(19), box.width - 52):
            ui.label(self.screen, line, 19, (box.x + 26, y), (226, 230, 232), bold=False)
            y += 26
        ui.label(self.screen, f"{self.tutorial_step + 1} / {len(TUTORIAL)}", 15, (box.x + 26, box.bottom - 34), ui.MUTED)
        if focus == "deck":
            ui.label(self.screen, "Pull a card to continue", 17, (box.right - 26, box.bottom - 24), GOLD,
                     anchor="midright")
        else:
            ui.button(self.screen, self.tutorial_next(box), "Done" if self.tutorial_step == len(TUTORIAL) - 1
                      else "Next", "red", now, key="tut-next", size=18)

    @staticmethod
    def tutorial_next(box):
        return pygame.Rect(box.right - 136, box.bottom - 56, 110, 38)

    def tutorial_box(self):
        focus = TUTORIAL[self.tutorial_step][2]
        box = pygame.Rect(0, 0, 620, 210)
        box.center = (W // 2, H - 170 if focus != "deck" else 180)
        return box

    def advance_tutorial(self):
        self.sound.play("click", 0.4)
        self.tutorial_step += 1
        self.tutorial_t = time.time()
        if self.tutorial_step >= len(TUTORIAL):
            self.tutorial_step = -1
            self.profile.tutorial_done = True
            self.save()

    # --- Profiles screen ---
    def profile_rects(self):
        return [pygame.Rect(W // 2 - 680 + i * 276, H // 2 - 170, 256, 340) for i in range(PROFILES)]

    def draw_profiles(self, now):
        bob = math.sin(now * 1.6) * 4
        drop = int((1 - self.intro(now, 0.0, 1.2)) * 260)            # opening: the title drops in, cards rise
        ui.label(self.screen, "INFINIDECK", 72, (W // 2, 140 + bob - drop), anchor="center")
        ui.label(self.screen, "Choose a profile. Each one is its own save.", 22, (W // 2, 205 - drop), ui.MUTED,
                 "center", bold=False)
        mouse = pygame.mouse.get_pos()
        for i, r in enumerate(self.profile_rects()):
            slot = i + 1
            data = self.saves.summary(slot)
            hover = r.collidepoint(mouse)
            k = ui.juice(("profile", slot), hover, now)
            rise = int((1 - self.intro(now, 0.3 + i * 0.12, 1.1)) * (H - r.y + 40))
            rr = r.inflate(int(r.w * (k - 1)), int(r.h * (k - 1))).move(0, (-10 if hover else 0) + rise)
            ui.panel(self.screen, rr, (58, 50, 74) if hover else ui.PANEL, radius=20)
            ui.label(self.screen, f"Profile {slot}", 30, (rr.x + 22, rr.y + 20))
            if data:
                bal = Big.from_json(data.get("balance", 0))
                box = ui.inset(self.screen, pygame.Rect(rr.x + 18, rr.y + 74, rr.w - 36, 46))
                chip = art.casino_chip(32)
                self.screen.blit(chip, chip.get_rect(center=(box.x + 24, box.centery)))
                shown = bal.exact() if bal < 1_000_000 else bal.fmt()
                num = art.font(26, mono=True).render(shown, True, (255, 96, 86))
                self.screen.blit(num, num.get_rect(midleft=(box.x + 46, box.centery)))
                hours = data.get("playtime", 0) / 3600
                n = data.get("cards", 0)
                info = [f"{n:,} card{'' if n == 1 else 's'} pulled", f"{hours:.1f} hours played",
                        f"{Big(data.get('tp', 0)).fmt()} Transcendent points"]
                for j, line in enumerate(info):
                    ui.label(self.screen, line, 17, (rr.x + 22, rr.y + 140 + j * 28), ui.MUTED, bold=False)
                confirm = self.confirm_delete == slot
                ui.button(self.screen, self.delete_rect(rr), "Click again to delete" if confirm else "Delete",
                          "red" if confirm else "dark", now, key=("del", slot), size=15)
            else:
                ui.label(self.screen, "Empty slot", 20, (rr.x + 22, rr.y + 84), ui.MUTED, bold=False)
                ui.button(self.screen, pygame.Rect(rr.x + 22, rr.bottom - 74, rr.w - 44, 46), "New game", "green",
                          now, key=("new", slot), size=20)
        if self.warning and time.time() - self.warning_t < 9:
            self.draw_warning()

    @staticmethod
    def delete_rect(card_rect):
        return pygame.Rect(card_rect.x + 22, card_rect.bottom - 62, card_rect.width - 44, 36)

    def draw_warning(self):
        w = art.font(18, bold=True).size(self.warning)[0] + 44
        r = pygame.Rect(0, 0, w, 44 + ui.LIP)
        r.center = (W // 2, H - 44)
        body = ui.panel(self.screen, r, ui.COLORS["orange"][1], radius=12)
        ui.label(self.screen, self.warning, 18, body.center, (255, 240, 220), "center")

    # --- Input ---
    def click(self, pos, now):
        if self.mode == "profiles":
            for i, r in enumerate(self.profile_rects()):
                slot = i + 1
                if self.saves.summary(slot) and self.delete_rect(r).collidepoint(pos):
                    if self.confirm_delete == slot:
                        self.saves.delete(slot)
                        self.confirm_delete = None
                    else:
                        self.confirm_delete = slot
                    self.sound.play("click", 0.4)
                    return
                if r.collidepoint(pos):
                    self.sound.play("click", 0.5)
                    self.open_profile(slot)
                    return
            self.confirm_delete = None
            return
        if self.tutorial_step >= 0:
            focus = TUTORIAL[self.tutorial_step][2]
            if focus == "deck":
                if self.over_deck(pos) and self.can_pull(now):
                    self.pull(now)
                return
            if self.tutorial_next(self.tutorial_box()).collidepoint(pos):
                self.advance_tutorial()
            return
        if self.page == "Home" and self.menu_button_rect().collidepoint(pos):    # the menu button is on the table only
            self.menu_open = not self.menu_open
            self.menu_opened = now
            self.sound.play("menu", 0.5)
            return
        if self.menu_open:
            for name, r in zip(MENU_ITEMS, self.menu_rects()):
                if r.collidepoint(pos):
                    self.set_page(name, now)
                    return
            for label, rect, _color in self.menu_footer():
                if rect.collidepoint(pos):
                    self.save()
                    if label == "Switch profile":
                        self.mode = "profiles"
                        self.menu_open = False
                        self.intro_t = time.time()
                    else:
                        self.quit = True
                    return
            if pos[0] > 400:
                self.menu_open = False
                self.sound.play("swish", 0.35)
            return
        if self.page != "Home":
            return
        if self.over_deck(pos) and self.can_pull(now):
            self.pull(now)

    def set_page(self, name, now):
        self.sound.play("swish", 0.45)
        self.page = name
        self.page_t = now
        self.menu_open = False
        if name == "Skill Tree":
            self.tree.open(now)
        if name == "Achievements":
            a = self.profile.ach
            a["menu_opens"] = a.get("menu_opens", 0) + 1
            self.engine.check_achievements()
            self.perkpages.search = ""
        self.shown = Big(self.profile.balance)
        self.update_presence()

    def routed(self, e, now):
        """Gives Skill Tree / Index / Deck / Stats their mouse events (the ☰ button still works)."""
        if self.mode == "play" and self.perkpages.reveal:
            if e.type == pygame.MOUSEBUTTONDOWN and time.time() - self.perkpages.reveal[1] > 1.0:
                self.perkpages.reveal = None
            return e.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.KEYDOWN, pygame.MOUSEWHEEL)
        if self.mode == "play" and self.page == "Home" and e.type == pygame.MOUSEBUTTONDOWN and e.button == 3:
            return self.pin_card(e.pos)
        if self.mode != "play" or self.page == "Home" or self.menu_open or self.tutorial_step >= 0:
            return False
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            if self.page == "Skill Tree" and self.tree.picker:
                self.tree.picker = False
                return True
            return False
        if self.page == "Skill Tree":
            if self.perkpages.shatter_open:
                return self.perkpages.shatter_event(e, now)
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and not self.tree.picker and \
                    self.perkpages.shatter_button().collidepoint(e.pos):
                self.perkpages.open_shatter(now)
                return True
            return self.tree.handle(e, now)
        if self.page in ("Perks", "Achievements"):
            return self.perkpages.handle(self.page, e, now)
        if self.page == "Settings":
            return self.settings.handle(e, now)
        if self.page == "Developers":
            return self.devs.handle(e, now)
        return self.pages.handle(self.page, e, now)

    def pin_card(self, pos):
        """Card Lock perk: right-click a table card to pin it (up to 2)."""
        if "Card Lock" not in self.engine.perks.on:
            return False
        for tc in reversed(self.table):
            if tc.landed and not tc.fading() and abs(pos[0] - tc.target[0]) < 60 and abs(pos[1] - tc.target[1]) < 80:
                if tc.pinned or sum(t.pinned for t in self.table) < 2:
                    tc.pinned = not tc.pinned
                    self.sound.play("click", 0.5)
                return True
        return False

    # --- Main loop ---
    def run(self, seconds=None, script=None):
        self.quit = False
        start = time.time()
        while not self.quit:
            dt = min(self.clock.tick(FPS) / 1000, 0.05)
            now = time.time()
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.quit = True
                    continue
                if e.type == MUSIC_END:                          # a track ended: the next one starts
                    self.sound.start_music()
                    continue
                if self.routed(e, now):
                    continue
                if e.type == pygame.QUIT:
                    self.quit = True
                elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    self.click(e.pos, now)
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_SPACE:
                        self.space_held = True
                        if self.tutorial_step >= 0 and TUTORIAL[self.tutorial_step][2] == "deck" and self.can_pull(now):
                            self.pull(now)
                    elif e.key == pygame.K_ESCAPE and self.mode == "play":
                        if self.page != "Home":
                            self.set_page("Home", now)
                        else:
                            self.menu_open = not self.menu_open
                            self.menu_opened = now
                            self.sound.play("menu", 0.45)
                    elif e.key == pygame.K_m:
                        self.toggle_sound()
                    elif e.key == pygame.K_RETURN and e.mod & pygame.KMOD_ALT:
                        self.toggle_fullscreen()
                elif e.type == pygame.KEYUP and e.key == pygame.K_SPACE:
                    self.space_held = False
            if script:
                script(self, now)
            self.update(dt, now)
            if self.page == "Skill Tree" and self.mode == "play":
                self.tree.update(dt, now)
            if self.mode == "play" and now - self.last_presence > PRESENCE_EVERY:
                self.last_presence = now
                self.update_presence()
            self.draw(now)
            pygame.display.flip()
            if seconds and time.time() - start > seconds:
                break
        self.save()
        pygame.quit()


def wrap(text, f, width):
    words, lines, line = text.split(), [], ""
    for w in words:
        test = (line + " " + w).strip()
        if f.size(test)[0] > width and line:
            lines.append(line)
            line = w
        else:
            line = test
    if line:
        lines.append(line)
    return lines


if __name__ == "__main__":
    Game().run()
