"""Infinideck: pull cards from an endless deck for chips, stack wild modifiers and grow huge numbers (game).

The table, pulling, 60 modifiers, crits, rarity, chips flying to the counter, the "beyond rarity" cutscene, the
menu, 5 profiles with crash-safe autosave, the tutorial, the Skill Tree (Main 550, Decks 50, Transcend 144),
Transcending, the Index, Deck and Stats pages, 100 perks with Shatter and perk slots, and 100 achievements.
"""
import array
import ctypes
import json
import math
import os
import random
import sys
import time
from collections import deque
from pathlib import Path

import pygame

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _art as art
import _ui as ui
from _achievements import SECRET_NAMES
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
SAVE_DIR = Path(os.environ.get("INFINIDECK_SAVES") or Path(os.environ.get("APPDATA", str(Path.home()))) / "Infinideck")
PROFILES = 5
AUTOSAVE_SECONDS = 360
FLIGHT = 0.5                    # seconds from the deck to the table
FLIP_FRAMES = 22                # the flip at the end of the flight
CINEMATIC = 3.0                 # flight time for a card rarer than 1 in a million
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
MENU_COLORS = {"Home": "red", "Stats": "blue", "Index": "orange", "Skill Tree": "green", "Deck": "purple",
               "Perks": "pink", "Achievements": "cyan"}
FULL_PAGES = ("Skill Tree", "Index", "Deck", "Stats", "Perks", "Achievements")
CUTSCENE_GAP = 45.0             # seconds between "beyond rarity" cutscenes (late game rolls lots of them)
MENU_ITEMS = ["Home", "Stats", "Index", "Skill Tree", "Deck", "Perks", "Achievements"]
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


# --- Sound (made in code, no files) ---
class Sound:
    def __init__(self):
        self.ok = False
        self.on = True
        if MUTE:
            return
        try:
            pygame.mixer.init(44100, -16, 1, 512)
        except pygame.error:
            return
        self.ok = True
        rnd = random.Random(4)
        self.sounds = {}
        self.sounds = {
            "flip": [self.make(lambda t, f=f: rnd.uniform(-1, 1) * math.exp(-t * 60) * 0.5 +
                               math.sin(t * f) * math.exp(-t * 40) * 0.3, 0.08) for f in (2400, 2900, 3300)],
            "land": [self.make(lambda t, f=f: (math.sin(2 * math.pi * (f - 160 * t) * t) * 0.7 +
                                               rnd.uniform(-1, 1) * 0.25 * math.exp(-t * 60)) * math.exp(-t * 28),
                               0.16) for f in (110, 135, 160)],
            "squish": [self.make(lambda t: (rnd.uniform(-1, 1) * 0.35 + math.sin(2 * math.pi * 240 * t) * 0.4) *
                                 math.exp(-t * 45), 0.09)],
            "pop": [self.make(lambda t, f=f: math.sin(2 * math.pi * (f + 2400 * t) * t) * math.exp(-t * 55) * 0.3,
                              0.07) for f in (900, 1100)],
            "boom": [self.make(lambda t: (math.sin(2 * math.pi * (70 - 25 * t) * t) * 0.8 * math.exp(-t * 2.2)
                                          + rnd.uniform(-1, 1) * 0.35 * math.exp(-t * 9)
                                          + sum(math.sin(2 * math.pi * f * (1 + 0.15 * t) * t) for f in
                                                (523, 659, 784, 1047)) * 0.08 * min(1, t * 2) * math.exp(-t * 1.1)),
                               2.6)],
            "chip": [self.make(lambda t, f=f: (math.sin(t * f) + 0.4 * math.sin(t * f * 2.7)) *
                               math.exp(-t * 55) * 0.25, 0.09) for f in (9000, 9800, 10600, 11500)],
            "crit": [self.make(lambda t: math.sin(t * 2600 + 8 * math.sin(t * 40)) * math.exp(-t * 6) * 0.4, 0.5)],
            "bad": [self.make(lambda t: math.sin(t * (900 - t * 1200)) * math.exp(-t * 8) * 0.4, 0.35)],
            "rare": [self.make(lambda t: sum(math.sin(t * f) for f in (1650, 2080, 2470, 3300)) * 0.12 *
                               min(1, t * 8) * math.exp(-t * 1.2), 2.2)],
            "click": [self.make(lambda t: math.sin(t * 5200) * math.exp(-t * 90) * 0.4, 0.04)],
            "whoosh": [self.make(lambda t: rnd.uniform(-1, 1) * math.sin(t * math.pi / 0.25) * 0.25, 0.25)],
            "buy": [self.make(lambda t: (math.sin(t * 2 * math.pi * (660 if t < 0.07 else 990)) * 0.35 +
                                         math.sin(t * 2 * math.pi * 1980) * 0.1) * math.exp(-t * 9), 0.3)],
            "tick": [self.make(lambda t: math.sin(t * 7000) * math.exp(-t * 160) * 0.3, 0.03)],
            "sparkle": [self.make(lambda t, f=f: sum(math.sin(t * 2 * math.pi * f * k) for k in (1, 1.5, 2)) * 0.1 *
                                  math.exp(-t * 7), 0.4) for f in (1760, 2093)],
            "swish": [self.make(lambda t: rnd.uniform(-1, 1) * math.sin(t * math.pi / 0.18) ** 2 * 0.18, 0.18)],
            "equip": [self.make(lambda t: (math.sin(t * 2 * math.pi * 520) * 0.3 + math.sin(t * 2 * math.pi * 780)
                                           * 0.25 * (t > 0.06)) * math.exp(-t * 10), 0.35)],
            "achieve": [self.make(lambda t: sum(math.sin(t * 2 * math.pi * f) for f in
                                                (784 if t < 0.12 else 1047, 1568)) * 0.18 * math.exp(-t * 4), 0.9)],
            "shatter": [self.make(lambda t: (rnd.uniform(-1, 1) * 0.6 + math.sin(t * 9000 * (1 - t * 0.5)) * 0.3) *
                                  math.exp(-t * 3.5), 1.4)],
            "transcend": [self.make(lambda t: sum(math.sin(t * 2 * math.pi * f * (1 + t * 0.4)) for f in
                                                  (220, 330, 440, 660)) * 0.1 * min(1, t * 3) * math.exp(-t * 0.9),
                                    3.0)],
        }

    @staticmethod
    def make(fn, seconds):
        rate = 44100
        data = array.array("h", (int(clamp(fn(i / rate), -1, 1) * 30000) for i in range(int(rate * seconds))))
        return pygame.mixer.Sound(buffer=data.tobytes())

    def play(self, name, volume=1.0):
        if not self.ok or not self.on:
            return
        snd = random.choice(self.sounds[name])
        snd.set_volume(volume)
        snd.play()


# --- Saving: 5 profiles, a backup of the last good save, and a marker that catches crashes mid-save ---
class Saves:
    def __init__(self):
        SAVE_DIR.mkdir(parents=True, exist_ok=True)

    def path(self, slot, kind="json"):
        return SAVE_DIR / f"profile_{slot}.{kind}"

    def meta(self):
        try:
            return json.loads((SAVE_DIR / "settings.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def write_meta(self, data):
        (SAVE_DIR / "settings.json").write_text(json.dumps(data), encoding="utf-8")

    def save(self, slot, data):
        main, bak, tmp, marker = (self.path(slot), self.path(slot, "bak"), self.path(slot, "tmp"),
                                  self.path(slot, "saving"))
        marker.write_text(str(time.time()), encoding="utf-8")      # if we crash before removing this, use the backup
        tmp.write_text(json.dumps(data), encoding="utf-8")
        if main.exists():
            os.replace(main, bak)
        os.replace(tmp, main)
        marker.unlink(missing_ok=True)

    def load(self, slot):
        """Returns (data or None, warning text or "")."""
        main, bak, marker = self.path(slot), self.path(slot, "bak"), self.path(slot, "saving")
        warning = ""
        data = None
        if marker.exists():
            warning = "The game closed while saving last time, so this profile was loaded from the save before it."
            marker.unlink(missing_ok=True)
        elif main.exists():
            try:
                data = json.loads(main.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                warning = "This profile's save was damaged, so it was loaded from the save before it."
        if data is None and bak.exists():
            try:
                data = json.loads(bak.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                warning = "This profile's saves were damaged, so it starts fresh."
        return data, warning

    def summary(self, slot):
        data, _ = self.load_quiet(slot)
        return data

    def load_quiet(self, slot):
        for p in (self.path(slot), self.path(slot, "bak")):
            try:
                return json.loads(p.read_text(encoding="utf-8")), ""
            except (OSError, ValueError):
                continue
        return None, ""

    def delete(self, slot):
        for kind in ("json", "bak", "tmp", "saving"):
            self.path(slot, kind).unlink(missing_ok=True)


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
        self.leaving = None             # time it started flying back into the deck
        self.pinned = False             # Card Lock perk
        self.flip_played = False
        self.hover_k = 0.0              # how lifted it is under the mouse
        self.fade = None                # when it started fading away
        self.burned = res.burned

    def progress(self, now):
        return clamp((now - self.born) / self.flight, 0, 1)

    def pos(self, now):
        if self.leaving is not None:
            t = ease_in_out(clamp((now - self.leaving) / 0.45, 0, 1))
            return (self.target[0] + (DECK_POS[0] - self.target[0]) * t,
                    self.target[1] + (DECK_POS[1] - self.target[1]) * t)
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


class Spark:
    def __init__(self, pos, vel, color, life, size, gravity=0.0):
        self.x, self.y = pos
        self.vx, self.vy = vel
        self.color, self.life, self.max_life, self.size = color, life, life, size
        self.gravity = gravity


SPARK_MODS = {"Golden": (255, 205, 70), "Explosive": (255, 130, 40), "Blessing": (255, 244, 210),
              "Wildcard": None, "Final": (255, 230, 150), "Flash": (255, 240, 120), "Jinx": (170, 90, 220),
              "Hexed": (110, 60, 140), "Blood": (190, 20, 30), "Overloaded": (255, 150, 40), "Void": (90, 40, 140),
              "Static": (240, 220, 60), "Shock": (90, 170, 255), "Siphon": (170, 20, 40)}


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
        self.fullscreen = False
        if not TEST_WINDOW and Saves().meta().get("fullscreen", True):
            self.toggle_fullscreen(save=False)
        self.clock = pygame.time.Clock()
        self.sound = Sound()
        self.sound.on = self.saves_sound_setting()
        self.saves = Saves()
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
        self.counter_rect = pygame.Rect(W - 400, 14, 380, 110)
        self.deck_back = {}
        meta = self.saves.meta()
        if not meta.get("launched"):                    # very first launch: straight into profile 1
            self.saves.write_meta({"launched": True, "last": 1})
            self.open_profile(1)

    def saves_sound_setting(self):
        try:
            return bool(Saves().meta().get("sound", True))
        except OSError:
            return True

    def toggle_fullscreen(self, save=True):
        try:
            pygame.display.toggle_fullscreen()
            self.fullscreen = not self.fullscreen
        except pygame.error:
            return
        if save:
            meta = self.saves.meta()
            meta["fullscreen"] = self.fullscreen
            self.saves.write_meta(meta)
            self.sound.play("click", 0.5)

    def intro(self, now, delay=0.0, dur=1.3):
        """0 -> 1 as things glide into place after opening the game or a save."""
        return ease_out(clamp((now - self.intro_t - delay) / dur, 0, 1))

    def toggle_sound(self):
        self.sound.on = not self.sound.on
        meta = self.saves.meta()
        meta["sound"] = self.sound.on
        self.saves.write_meta(meta)
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
        while len([t for t in self.table if t.leaving is None]) > MAX_TABLE:
            old = next((t for t in self.table if t.leaving is None and not t.pinned), None)
            if old is None:
                break
            old.leaving = now
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
            self.burst(pos, (255, 160, 50), 14, 160, 0.7)
        gained = self.engine.bank(tc.res)
        self.burst((pos[0], pos[1] + 60), (230, 225, 215), 6, 50, 0.45, size=(2.0, 2.4))   # a little dust puff
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
            for i in range(70):
                c = pygame.Color(0)
                c.hsva = (i * 360 / 70, 80, 100, 100)
                a = random.uniform(0, math.tau)
                v = random.uniform(150, 520)
                self.sparks.append(Spark(pos, (math.cos(a) * v, math.sin(a) * v - 220), (c.r, c.g, c.b),
                                         random.uniform(0.9, 1.8), random.uniform(2.6, 4.0), gravity=520))
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
            self.flash_t = now
            self.rainbow = (pos, now)

    @staticmethod
    def rarity_tag(rarity):
        n = 1 / max(rarity, 1e-300)
        text = f"1 in {Big(round(n) if n < 1e15 else n).fmt()}"
        kind = "crit" if rarity <= ULTRA_RARE else "buff" if rarity > 0.001 else "tp"
        return art.tag(text, kind, 15)

    def counter_anchor(self):
        return self.counter_rect.x + 28, self.counter_rect.y + 24

    def burst(self, pos, color, n, speed, life, size=(1.6, 3.2), gravity=0.0):
        """A small puff of soft particles."""
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = random.uniform(speed * 0.3, speed)
            self.sparks.append(Spark(pos, (math.cos(a) * v, math.sin(a) * v * 0.6), color,
                                     random.uniform(life * 0.6, life), random.uniform(*size), gravity))

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
        if (self.space_held or pygame.mouse.get_pressed()[0] and self.over_deck(pygame.mouse.get_pos())) \
                and self.can_pull(now):
            self.pull(now)
        for tc in list(self.table):
            if not tc.flip_played and now >= tc.born and \
                    tc.progress(now) >= 1 - FLIP_FRAMES / FPS / max(tc.flight, 0.01):
                tc.flip_played = True
                self.sound.play("flip", 0.3)
            if not tc.landed and tc.progress(now) >= 1:
                self.land(tc, now)
            if tc.leaving is not None and now - tc.leaving > 0.45:
                self.table.remove(tc)
                continue
            if tc.landed and tc.leaving is None and tc.fade is None and not tc.pinned:
                busy = now - self.last_pull_t < 0.9
                if now - tc.born - tc.flight > (FADE_BUSY if busy else FADE_IDLE):
                    tc.fade = now
            if tc.fade is not None and now - tc.fade > FADE_TIME:
                self.table.remove(tc)
                continue
            if tc.landed and tc.leaving is None:
                mods = tc.card.buffs + tc.card.debuffs
                for m in mods:
                    if m in SPARK_MODS and random.random() < 0.25:
                        col = SPARK_MODS[m]
                        if col is None:
                            c = pygame.Color(0)
                            c.hsva = (random.uniform(0, 360), 70, 100, 100)
                            col = (c.r, c.g, c.b)
                        x, y = tc.pos(now)
                        self.sparks.append(Spark((x + random.uniform(-60, 60), y + random.uniform(-80, 80)),
                                                 (random.uniform(-15, 15), random.uniform(-40, -10)), col,
                                                 random.uniform(0.6, 1.4), random.uniform(1.5, 3)))
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
                        self.burst(self.counter_anchor(), (255, 214, 110), 2, 70, 0.5, size=(2.6, 3.4))
                self.flyers.remove(f)
        if not self.flyers:
            self.shown = Big(p.balance)
        for s in list(self.sparks):
            s.life -= dt
            s.vy += s.gravity * dt
            s.x += s.vx * dt
            s.y += s.vy * dt
            if s.life <= 0:
                self.sparks.remove(s)
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
        self.draw_deck(world, now)
        self.draw_table(world, now)
        for s in self.sparks:
            a = clamp(s.life / s.max_life, 0, 1)
            tint = tuple(c // 32 * 32 for c in s.color)
            kind = "sparkle" if s.size > 2.4 else "glow"
            img = art.asset(kind, max(4, int(s.size * (7 if kind == "sparkle" else 9) * (0.5 + 0.5 * a))),
                            tint, int(a * 8) * 28 + 30)
            if img is None:
                pygame.draw.circle(world, art.mix(BG, s.color, a), (int(s.x), int(s.y)), max(1, int(s.size * a)))
            else:
                world.blit(img, img.get_rect(center=(int(s.x), int(s.y))))
        if cine is not None:                                  # camera zooms in on the rare card
            t = ease_in_out(clamp((now - cine.born) / cine.flight, 0, 1))
            zoom = 1 + 0.55 * t
            cx, cy = cine.pos(now)
            big = pygame.transform.smoothscale(world, (int(W * zoom), int(H * zoom)))
            ox = clamp(int(cx * zoom - W / 2), 0, big.get_width() - W)
            oy = clamp(int(cy * zoom - H / 2), 0, big.get_height() - H)
            self.screen.blit(big, (0, 0), (ox, oy, W, H))
        ui = self.ui_surf if cine is not None else self.screen
        if cine is not None:
            ui.fill((0, 0, 0, 0))
        self.draw_floaters(ui, now)
        self.draw_counter(ui, now)
        self.draw_flyers(ui, now)
        self.draw_menu_button(ui)
        self.draw_hint(ui, now)
        if cine is not None:                                  # blur the UI during the cutscene
            small = pygame.transform.smoothscale(ui, (W // 10, H // 10))
            self.screen.blit(pygame.transform.smoothscale(small, (W, H)), (0, 0))
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
            if tc.burned and face_up:
                img = img.copy()
                img.fill((90, 60, 50, 255), special_flags=pygame.BLEND_RGBA_MULT)
            scale = 1.0
            if "Shrink" in tc.card.debuffs and face_up:
                scale = 0.78
            if self.cinematic is tc:
                scale *= 1.25
            if tc.leaving is not None:
                scale *= 1 - 0.3 * clamp((now - tc.leaving) / 0.45, 0, 1)
            if not tc.landed:                                  # leaves the deck at the deck's size
                scale *= 1 + (DECK_SCALE - 1) * (1 - ease_out(prog))
            alpha = 255
            if tc.fade is not None:
                alpha = int(255 * clamp(1 - (now - tc.fade) / FADE_TIME, 0, 1))
                scale *= 0.92 + 0.08 * alpha / 255
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
            if tc.landed and tc.leaving is None and tc.fade is None and rect.collidepoint(mouse):
                self.hover_card = tc
        self.last_hover_card = self.hover_card

    def draw_floaters(self, surf, now):
        for f in self.floaters:
            t = (now - f.t0) / f.life
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

    def draw_menu_button(self, surf):
        r = pygame.Rect(18, 18, 54, 50).move(0, -int((1 - self.intro(time.time(), 0.25, 1.2)) * 110))
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
                lines.append((art.tag("Critical hit", "crit", 14), "x2.5 chips"))
        paid = "??? chips" if (pay.hidden or fog) else f"{pay.chips.fmt()} chips"
        lines.append((art.tag(paid, "chips", 15), None))
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

    def draw_rainbow(self, now):
        if not self.rainbow:
            return
        pos, t0 = self.rainbow
        t = now - t0
        if t > 3.2:
            self.rainbow = None
            return
        text = "A card beyond rarity reveals itself."
        f = art.font(34, bold=True)
        x = W // 2 - f.size(text)[0] // 2
        y = clamp(pos[1] - 190, 120, H - 200)
        alpha = int(255 * clamp(min(t / 0.4, (3.2 - t) / 0.6), 0, 1))
        for i, ch in enumerate(text):
            c = pygame.Color(0)
            c.hsva = ((i * 12 + now * 220) % 360, 75, 100, 100)
            g = f.render(ch, True, (c.r, c.g, c.b))
            g.set_alpha(alpha)
            self.screen.blit(g, (x, y + math.sin(now * 6 + i * 0.4) * 4))
            x += f.size(ch)[0]

    # --- Menu (slides in from the left) ---
    def menu_rects(self):
        return [pygame.Rect(30, 112 + i * 72, 280, 54) for i in range(len(MENU_ITEMS))]

    def draw_menu(self, now):
        target = 1.0 if self.menu_open else 0.0
        self.menu_t += (target - self.menu_t) * 0.25
        if self.menu_t < 0.01:
            return
        e = ease_out(self.menu_t)
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, int(140 * e)))
        self.screen.blit(dim, (0, 0))
        off = int(-380 * (1 - e))
        ui.panel(self.screen, pygame.Rect(off - 30, -20, 370, H + 40), radius=24)
        ui.label(self.screen, "INFINIDECK", 40, (off + 32, 36))
        for i, (name, r) in enumerate(zip(MENU_ITEMS, self.menu_rects())):
            r = r.move(off - int(60 * (1 - e) * (i + 1) / 4), 0)
            ui.button(self.screen, r, name, MENU_COLORS[name], now, key="menu-" + name, size=24,
                      selected=name == self.page)
        for label, rect in self.menu_footer(off):
            ui.button(self.screen, rect, label, "dark", now, key="foot-" + label[:6], size=16)

    def menu_footer(self, off=0):
        sound = "Sound: on (M)" if self.sound.on else "Sound: off (M)"
        full = "Fullscreen: on (Alt+Enter)" if self.fullscreen else "Fullscreen: off (Alt+Enter)"
        return [(full, pygame.Rect(off + 30, H - 222, 280, 38)),
                (sound, pygame.Rect(off + 30, H - 172, 280, 38)),
                ("Switch profile", pygame.Rect(off + 30, H - 122, 280, 38)),
                ("Save and quit", pygame.Rect(off + 30, H - 72, 280, 38))]

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
        e = ease_out(clamp((now - self.page_t) / 0.3, 0, 1))
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((4, 4, 10, int(225 * e)))
        self.screen.blit(dim, (0, 0))
        panel = pygame.Rect(0, 0, 900, 420)
        panel.center = (W // 2, H // 2 + int(30 * (1 - e)))
        self.screen.blit(art.rounded(panel.size, PANEL, 18, int(250 * e)), panel.topleft)
        pygame.draw.rect(self.screen, PANEL_EDGE, panel, 2, border_radius=18)
        t = art.font(48, bold=True).render(self.page, True, TEXT)
        t.set_alpha(int(255 * e))
        self.screen.blit(t, t.get_rect(center=(panel.centerx, panel.y + 90)))
        soon = {"Perks": "Permanent perks from Shattering.", "Achievements": "100 achievements, 50 of them secret."}
        for i, line in enumerate((soon.get(self.page, ""), "Coming in the next update of this build.")):
            s = art.font(22).render(line, True, MUTED if i else TEXT)
            s.set_alpha(int(255 * e))
            self.screen.blit(s, s.get_rect(center=(panel.centerx, panel.y + 180 + i * 44)))
        b = self.back_rect()
        hover = b.collidepoint(pygame.mouse.get_pos())
        self.screen.blit(art.rounded(b.size, (60, 30, 40) if hover else (40, 26, 34), 12), b.topleft)
        bt = art.font(22, bold=True).render("Back to the table", True, TEXT)
        self.screen.blit(bt, bt.get_rect(center=b.center))

    def back_rect(self):
        r = pygame.Rect(0, 0, 260, 54)
        r.center = (W // 2, H // 2 + 150)
        return r

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
            if tc.leaving is None:
                tc.leaving = now
                tc.pinned = False
        self.flyers.clear()
        self.shown = Big(self.profile.balance)

    def draw_toasts(self, now):
        """Achievement banners that slide down from the top."""
        alive = []
        y = 16
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
            r = pygame.Rect(0, 0, 520, 70)
            r.topright = (W - 24 + int(560 * (1 - k)), self.counter_rect.bottom + y - 2)   # slides in from the right
            ui.panel(self.screen, r.inflate(0, ui.LIP).move(0, ui.LIP // 2), (70, 52, 22) if not secret else (62, 40, 86),
                     radius=14)
            head = "Secret achievement" if secret else "Achievement unlocked"
            medal = art.asset("medal", 56)
            tx = r.x + 20
            if medal:
                self.screen.blit(medal, medal.get_rect(center=(r.x + 40, r.centery)))
                tx = r.x + 76
            ui.label(self.screen, head, 14, (tx, r.y + 10), GOLD)
            ui.label(self.screen, name, 22, (tx, r.y + 30))
            y += 80
        self.toasts = alive

    def do_transcend(self, now):
        gain = self.engine.transcend()
        if not gain:
            return
        self.sound.play("transcend", 0.6)
        self.tp_flash = now
        for tc in self.table:
            if tc.leaving is None:
                tc.leaving = now
        self.flyers.clear()
        self.shown = Big(0)
        text = f"+{gain:,}" if gain < 1_000_000 else "+" + Big(gain).fmt()
        self.floaters.append(Floater(art.tag(text + " Transcendent points", "tp", 28), (W // 2, H // 2 - 40), now,
                                     life=3.0, rise=30))
        self.save()

    def draw_tp_flash(self, now):
        t = now - self.tp_flash
        if t > 2.0:
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
        if pygame.Rect(18, 18, 52, 52).collidepoint(pos):
            self.menu_open = not self.menu_open
            self.sound.play("swish", 0.5)
            return
        if self.menu_open:
            for name, r in zip(MENU_ITEMS, self.menu_rects()):
                if r.collidepoint(pos):
                    self.set_page(name, now)
                    return
            for label, rect in self.menu_footer():
                if rect.collidepoint(pos):
                    if label.startswith("Sound"):
                        self.toggle_sound()
                        return
                    if label.startswith("Fullscreen"):
                        self.toggle_fullscreen()
                        return
                    self.save()
                    if label == "Switch profile":
                        self.mode = "profiles"
                        self.menu_open = False
                    else:
                        self.quit = True
                    return
            if pos[0] > 340:
                self.menu_open = False
            return
        if self.page != "Home":
            if self.page in ("Perks", "Achievements") and self.back_rect().collidepoint(pos):
                self.set_page("Home", now)
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
        self.shown = Big(self.profile.balance)

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
        if e.type == pygame.MOUSEBUTTONDOWN and pygame.Rect(18, 18, 52, 52).collidepoint(e.pos):
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
        return self.pages.handle(self.page, e, now)

    def pin_card(self, pos):
        """Card Lock perk: right-click a table card to pin it (up to 2)."""
        if "Card Lock" not in self.engine.perks.on:
            return False
        for tc in reversed(self.table):
            if tc.landed and tc.leaving is None and abs(pos[0] - tc.target[0]) < 60 and abs(pos[1] - tc.target[1]) < 80:
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
