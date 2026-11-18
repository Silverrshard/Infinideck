"""Infinideck's drawing: cards (with all 60 modifier looks), the card back, the casino chip, coloured number tags.
Everything is drawn in code with soft shading and shadows, so it reads as 3D on a 2D table."""
import math
import random
from pathlib import Path

import pygame
from _cards import BUFFS, DEBUFFS, FACE, SUIT_COLOR

# --- Look ---
CARD_W, CARD_H = 110, 154
RADIUS = 10
CREAM = (246, 239, 224)
CREAM_DARK = (222, 210, 186)
INK = (26, 24, 32)
FONT_NAME = "bahnschrift"
MONO_NAME = "consolas"
TAG_COLORS = {"chips": (48, 110, 220), "mult": (214, 52, 58), "tp": (128, 72, 220), "crit": (236, 130, 32),
              "buff": (40, 160, 80), "debuff": (130, 24, 32), "streak": (220, 180, 30)}
DUP_PURPLE = (150, 70, 230)
BACK_RED = (172, 34, 46)

_fonts = {}
_cache = {}


def font(size, bold=False, mono=False):
    key = (size, bold, mono)
    if key not in _fonts:
        _fonts[key] = pygame.font.SysFont(MONO_NAME if mono else FONT_NAME, size, bold=bold)
    return _fonts[key]


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def rounded(size, color, radius, alpha=255):
    s = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.rect(s, (*color, alpha), s.get_rect(), border_radius=radius)
    return s


def shadow(size, radius, strength=110, blur=8):
    """A soft drop shadow (blurred by scaling down and back up)."""
    key = ("shadow", size, radius, strength, blur)
    if key in _cache:
        return _cache[key]
    w, h = size[0] + blur * 4, size[1] + blur * 4
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(s, (0, 0, 0, strength), (blur * 2, blur * 2, size[0], size[1]), border_radius=radius)
    small = pygame.transform.smoothscale(s, (max(1, w // blur), max(1, h // blur)))
    s = pygame.transform.smoothscale(small, (w, h))
    _cache[key] = s
    return s


# --- Suits ---
def suit(surf, name, cx, cy, size, color=None):
    """A suit symbol drawn with shapes (not font glyphs), centred on cx, cy."""
    c = color or SUIT_COLOR[name]
    s = size
    if name == "hearts":
        r = s * 0.27
        pygame.draw.circle(surf, c, (cx - r * 0.95, cy - s * 0.12), r)
        pygame.draw.circle(surf, c, (cx + r * 0.95, cy - s * 0.12), r)
        pygame.draw.polygon(surf, c, [(cx - s * 0.52, cy - s * 0.05), (cx + s * 0.52, cy - s * 0.05),
                                      (cx, cy + s * 0.5)])
    elif name == "diamonds":
        pygame.draw.polygon(surf, c, [(cx, cy - s * 0.52), (cx + s * 0.38, cy), (cx, cy + s * 0.52),
                                      (cx - s * 0.38, cy)])
    elif name == "spades":
        r = s * 0.25
        pygame.draw.polygon(surf, c, [(cx, cy - s * 0.52), (cx + s * 0.48, cy + s * 0.08),
                                      (cx - s * 0.48, cy + s * 0.08)])
        pygame.draw.circle(surf, c, (cx - r * 0.95, cy + s * 0.1), r)
        pygame.draw.circle(surf, c, (cx + r * 0.95, cy + s * 0.1), r)
        pygame.draw.polygon(surf, c, [(cx, cy + s * 0.1), (cx - s * 0.16, cy + s * 0.5), (cx + s * 0.16, cy + s * 0.5)])
    else:   # clubs
        r = s * 0.22
        pygame.draw.circle(surf, c, (cx, cy - s * 0.24), r)
        pygame.draw.circle(surf, c, (cx - s * 0.25, cy + s * 0.06), r)
        pygame.draw.circle(surf, c, (cx + s * 0.25, cy + s * 0.06), r)
        pygame.draw.polygon(surf, c, [(cx, cy), (cx - s * 0.16, cy + s * 0.5), (cx + s * 0.16, cy + s * 0.5)])


PIPS = {   # number-card pip layouts, in fractions of the card's middle area
    2: [(0.5, 0.1), (0.5, 0.9)], 3: [(0.5, 0.1), (0.5, 0.5), (0.5, 0.9)],
    4: [(0.25, 0.1), (0.75, 0.1), (0.25, 0.9), (0.75, 0.9)],
    5: [(0.25, 0.1), (0.75, 0.1), (0.5, 0.5), (0.25, 0.9), (0.75, 0.9)],
    6: [(0.25, 0.1), (0.75, 0.1), (0.25, 0.5), (0.75, 0.5), (0.25, 0.9), (0.75, 0.9)],
    7: [(0.25, 0.1), (0.75, 0.1), (0.5, 0.3), (0.25, 0.5), (0.75, 0.5), (0.25, 0.9), (0.75, 0.9)],
    8: [(0.25, 0.1), (0.75, 0.1), (0.5, 0.3), (0.25, 0.5), (0.75, 0.5), (0.5, 0.7), (0.25, 0.9), (0.75, 0.9)],
    9: [(0.25, 0.08), (0.75, 0.08), (0.25, 0.36), (0.75, 0.36), (0.5, 0.5), (0.25, 0.64), (0.75, 0.64),
        (0.25, 0.92), (0.75, 0.92)],
    10: [(0.25, 0.08), (0.75, 0.08), (0.5, 0.24), (0.25, 0.36), (0.75, 0.36), (0.25, 0.64), (0.75, 0.64),
         (0.5, 0.76), (0.25, 0.92), (0.75, 0.92)],
}


# --- Card faces ---
def card_face(card, hide=False):
    """The card's front (cached). hide=True draws the Fog look (nothing readable)."""
    key = ("face", tuple(card.ranks), card.suit, tuple(card.buffs), tuple(card.debuffs), card.dup, hide)
    if key in _cache:
        return _cache[key]
    w, h = CARD_W, CARD_H
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    final = "Final" in card.buffs
    base = INK if final else CREAM
    if "Steady" in card.buffs:
        base = (214, 218, 224)
    if "Rich" in card.buffs:
        base = mix(base, (120, 40, 110), 0.25)
    if "Heavy" in card.buffs or "Decayed" in card.debuffs:
        base = mix(base, (130, 125, 115), 0.35)
    pygame.draw.rect(s, base, (0, 0, w, h), border_radius=RADIUS)
    # soft shading: lighter top-left, darker bottom-right, like a lit card
    shade = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        t = y / h
        shade.fill((255, 255, 255, int(28 * (1 - t))) if t < 0.5 else (0, 0, 0, int(26 * (t - 0.5))),
                   (0, y, w, 1))
    s.blit(shade, (0, 0))
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, w, h), border_radius=RADIUS)
    s.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    pygame.draw.rect(s, mix(base, INK, 0.25), (0, 0, w, h), 2, border_radius=RADIUS)
    pygame.draw.rect(s, mix(base, (255, 255, 255), 0.4), (4, 4, w - 8, h - 8), 1, border_radius=RADIUS - 3)
    if hide:
        draw_fog(s)
        _cache[key] = s
        return s
    ink = (240, 236, 228) if final else SUIT_COLOR[card.suit]
    if final and card.suit == "spades":
        ink = (240, 236, 228)
    shrink = 0.72 if "Shrink" in card.debuffs else 1.0
    label = card.label()
    corner = font(int(20 * shrink) if len(label) < 3 else int(15 * shrink), bold=True).render(label, True, ink)
    s.blit(corner, (8, 6))
    suit(s, card.suit, 8 + corner.get_width() // 2, 14 + corner.get_height(), int(13 * shrink), ink)
    flipped = pygame.transform.rotate(corner, 180)
    s.blit(flipped, (w - 8 - flipped.get_width(), h - 6 - flipped.get_height()))
    suit(s, card.suit, w - 8 - flipped.get_width() // 2, h - 14 - flipped.get_height(), int(13 * shrink), ink)
    middle(s, card, ink, shrink, final)
    for name in card.buffs:
        buff_look(s, name, card, ink)
    for name in card.debuffs:
        debuff_look(s, name, card)
    if card.dup:
        tag = rounded((34, 16), DUP_PURPLE, 5)
        tag.blit(font(10, bold=True).render("DUP", True, (255, 255, 255)), (6, 1))
        s.blit(tag, (w - 40, 6))
    _cache[key] = s
    return s


def middle(s, card, ink, shrink, final):
    w, h = s.get_size()
    area = pygame.Rect(26, 26, w - 52, h - 52)
    ranks = card.ranks
    if final:
        glow = pygame.Surface((70, 70), pygame.SRCALPHA)
        for r in range(34, 0, -2):
            pygame.draw.circle(glow, (255, 230, 150, int(6 + (34 - r) * 1.5)), (35, 35), r)
        s.blit(glow, (w // 2 - 35, h // 2 - 35))
        suit(s, card.suit, w // 2, h // 2, int(46 * shrink), (255, 236, 180))
        return
    if len(ranks) > 1 or ranks[0] in ("AA", "AAA"):
        text = font(int((34 if len(card.label()) <= 2 else 26) * shrink), bold=True).render(card.label(), True, ink)
        s.blit(text, text.get_rect(center=(w // 2, h // 2 - 10)))
        suit(s, card.suit, w // 2, h // 2 + 26, int(26 * shrink), ink)
        return
    r = ranks[0]
    if r == "A":
        suit(s, card.suit, w // 2, h // 2, int(54 * shrink), ink)
        return
    if r in FACE:
        frame = pygame.Rect(22, 30, w - 44, h - 60)
        pygame.draw.rect(s, mix(CREAM, ink, 0.12), frame, border_radius=6)
        pygame.draw.rect(s, ink, frame, 2, border_radius=6)
        cx = w // 2
        crown_y = frame.top + 14
        points = {"K": 5, "Q": 4, "J": 3}[r]
        span = 34
        pts = [(cx - span // 2, crown_y + 10)]
        for i in range(points):
            x = cx - span // 2 + span * (i + 0.5) / points
            pts += [(x, crown_y - 6 if i % 2 == 0 or points == 3 else crown_y - 1), (x + span / points / 2, crown_y + 4)]
        pts.append((cx + span // 2, crown_y + 10))
        pygame.draw.polygon(s, (230, 180, 60), pts)
        pygame.draw.polygon(s, ink, pts, 1)
        letter = font(int(40 * shrink), bold=True).render(r, True, ink)
        s.blit(letter, letter.get_rect(center=(cx, frame.centery + 2)))
        suit(s, card.suit, cx, frame.bottom - 14, int(16 * shrink), ink)
        return
    n = int(r)
    size = int((19 if n <= 8 else 16) * shrink)
    for fx, fy in PIPS[n]:
        suit(s, card.suit, int(area.left + fx * area.width), int(area.top + fy * area.height), size, ink)


# --- Modifier looks (from the design's table) ---
def buff_look(s, name, card, ink):
    w, h = s.get_size()
    gold = (232, 186, 70)
    if name == "Double Pay" or name == "Triple Pay":
        n = 2 if name == "Double Pay" else 3
        for i in range(n):
            t = font(11, bold=True).render(card.label(), True, (60, 120, 220))
            s.blit(t, (8 + i * 12, h - 34))
    elif name == "Jackpot":
        crown(s, w - 30, 30, 18, (255, 205, 70), alpha=150)
    elif name == "Steady":
        for y in range(10, h - 10, 6):
            pygame.draw.line(s, (190, 196, 205), (6, y), (w - 6, y))
    elif name == "Greedy":
        for x, y in ((18, h - 40), (w - 22, 44)):
            pygame.draw.arc(s, (60, 170, 80), (x - 8, y - 8, 16, 16), 0.3, 3.0, 3)
    elif name == "Lucky":
        clover(s, 30, 42, 6)
        clover(s, w - 30, h - 42, 6)
    elif name == "Rich":
        for y in range(8, h - 8, 4):
            pygame.draw.line(s, (130, 60, 120, 40), (6, y), (w - 6, y + 2))
    elif name == "Golden":
        pygame.draw.rect(s, gold, (5, 5, w - 10, h - 10), 3, border_radius=RADIUS - 2)
    elif name == "Echo":
        ghost = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(ghost, (150, 160, 255, 60), (6, 6, w - 6, h - 6), 2, border_radius=RADIUS)
        s.blit(ghost, (0, 0))
    elif name == "Vampire":
        for cx in (26, w - 26):
            pygame.draw.polygon(s, (170, 20, 40), [(cx, h // 2 + 30), (cx - 12, h // 2 + 24), (cx - 6, h // 2 + 34)])
            pygame.draw.polygon(s, (170, 20, 40), [(cx, h // 2 + 30), (cx + 12, h // 2 + 24), (cx + 6, h // 2 + 34)])
    elif name == "Explosive":
        rnd = random.Random(7)
        for _ in range(6):
            x, y = rnd.randint(10, w - 10), rnd.randint(10, h - 10)
            pygame.draw.line(s, (255, 140, 40), (x, y), (x + rnd.randint(-14, 14), y + rnd.randint(-14, 14)), 2)
    elif name == "Safe":
        for x, y in ((9, 9), (w - 9, 9), (9, h - 9), (w - 9, h - 9)):
            pygame.draw.circle(s, (150, 155, 165), (x, y), 3)
            pygame.draw.circle(s, (230, 232, 236), (x - 1, y - 1), 1)
    elif name == "Blood":
        rnd = random.Random(3)
        for _ in range(7):
            pygame.draw.circle(s, (150, 10, 24), (rnd.randint(14, w - 14), rnd.randint(30, h - 30)), rnd.randint(2, 5))
    elif name == "Banker":
        for i in range(-h, w, 6):
            pygame.draw.line(s, (120, 170, 130), (i, h // 2 - 18), (i + 36, h // 2 + 18))
    elif name == "Flash":
        for x0, y0 in ((4, 30), (w - 4, h - 30)):
            pts = [(x0, y0), (x0 + (8 if x0 < w // 2 else -8), y0 + 8), (x0, y0 + 14), (x0 + (10 if x0 < w // 2 else -10), y0 + 24)]
            pygame.draw.lines(s, (255, 230, 90), False, pts, 2)
    elif name == "Heavy":
        pygame.draw.rect(s, (110, 105, 98), (8, h - 18, w - 16, 8), border_radius=3)
    elif name == "Jinx":
        pygame.draw.rect(s, (150, 70, 200), (1, 1, w - 2, h - 2), 2, border_radius=RADIUS)
    elif name == "Blessing":
        pygame.draw.ellipse(s, (255, 236, 170), (w // 2 - 22, 6, 44, 10), 2)
    elif name == "Pure":
        glow = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(glow, (255, 255, 255, 50), (8, 8, w - 16, h - 16), border_radius=RADIUS)
        s.blit(glow, (0, 0))
    elif name == "Tax":
        stamp = rounded((36, 16), (200, 40, 40), 2)
        stamp.blit(font(11, bold=True).render("TAX", True, (255, 240, 240)), (7, 1))
        s.blit(pygame.transform.rotate(stamp, 12), (w - 46, h - 44))
    elif name == "Wildcard":
        band = pygame.Surface((w, h), pygame.SRCALPHA)
        for x in range(w):
            hue = x / w
            c = pygame.Color(0)
            c.hsva = (hue * 360, 70, 100, 100)
            pygame.draw.line(band, (c.r, c.g, c.b, 55), (x, 0), (x, h))
        s.blit(band, (0, 0))
    elif name == "Crown":
        crown(s, w // 2, 9, 12, (255, 215, 90))
    elif name == "Iron":
        pygame.draw.rect(s, (70, 72, 80), (2, 2, w - 4, h - 4), 3, border_radius=RADIUS)
        for x, y in ((8, 8), (w - 8, 8), (8, h - 8), (w - 8, h - 8)):
            pygame.draw.circle(s, (90, 92, 100), (x, y), 3)
    elif name == "Overflow":
        for a in range(0, 360, 45):
            r = math.radians(a)
            pygame.draw.line(s, (200, 235, 255), (w // 2 + math.cos(r) * 20, h // 2 + math.sin(r) * 20),
                             (w // 2 + math.cos(r) * 34, h // 2 + math.sin(r) * 34), 2)
    elif name == "Shattered":
        cracks(s, (190, 215, 240), 11)
    elif name == "Royal":
        for x, y in ((10, 10), (w - 10, 10), (10, h - 10), (w - 10, h - 10)):
            pygame.draw.polygon(s, (130, 80, 255), [(x, y - 5), (x + 5, y), (x, y + 5), (x - 5, y)])
    elif name == "Cursed":
        pygame.draw.circle(s, (40, 20, 40), (w - 18, h - 18), 9)
        pygame.draw.circle(s, (90, 40, 80), (w - 18, h - 18), 9, 2)
    elif name == "Pristine":
        sheen = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.polygon(sheen, (255, 255, 255, 40), [(w * 0.2, 0), (w * 0.45, 0), (w * 0.05, h), (-w * 0.2, h)])
        s.blit(sheen, (0, 0))
    elif name == "Overloaded":
        pygame.draw.rect(s, (255, 140, 30), (0, 0, w, h), 3, border_radius=RADIUS)
    elif name == "Final":
        pygame.draw.rect(s, (255, 230, 150), (3, 3, w - 6, h - 6), 1, border_radius=RADIUS)


def debuff_look(s, name, card):
    w, h = s.get_size()
    if name == "Taxed":
        pygame.draw.polygon(s, (190, 40, 40), [(0, 22), (22, 0), (34, 0), (0, 34)])
    elif name == "Rust":
        rnd = random.Random(11)
        for _ in range(16):
            x, y = rnd.choice([(rnd.randint(2, w - 2), rnd.choice((4, h - 4))), (rnd.choice((4, w - 4)), rnd.randint(2, h - 2))])
            pygame.draw.circle(s, (150, 80, 30), (x, y), rnd.randint(2, 4))
    elif name == "Greed Penalty":
        padlock(s, w // 2, h - 12, (200, 40, 40))
    elif name == "Hexed":
        smoke(s, (80, 40, 110))
    elif name == "Leak":
        for x in range(12, w - 10, 14):
            pygame.draw.rect(s, (90, 200, 80), (x, h - 14, 6, 10 + (x * 7) % 9), border_radius=3)
    elif name == "Burn":
        for x in range(4, w - 4, 9):
            pygame.draw.circle(s, (60, 30, 20), (x, 3 + (x * 5) % 4), 4)
    elif name == "Blind":
        veil = pygame.Surface((w, h), pygame.SRCALPHA)
        veil.fill((30, 30, 40, 110))
        s.blit(veil, (0, 0))
    elif name == "Drain":
        for a in (20, 140, 260):
            r = math.radians(a)
            pygame.draw.line(s, (180, 20, 30), (w // 2, h // 2), (w // 2 + math.cos(r) * 40, h // 2 + math.sin(r) * 50), 2)
    elif name == "Static":
        rnd = random.Random(5)
        for _ in range(8):
            x, y = rnd.choice((4, w - 4)), rnd.randint(8, h - 8)
            pygame.draw.line(s, (240, 220, 60), (x, y), (x + rnd.randint(-6, 6), y + rnd.randint(-8, 8)), 2)
    elif name == "Shatter Risk":
        cracks(s, (255, 255, 255), 5, thin=True)
    elif name == "Jinxed":
        eye(s, w // 2, 26, (150, 60, 190))
    elif name == "Weighed Down":
        anvil(s, w // 2, h // 2 + 30, (90, 90, 100))
    elif name == "Void":
        for r in range(30, 4, -6):
            pygame.draw.circle(s, (50, 20, 80), (w // 2, h // 2), r, 2)
    elif name == "Slow":
        for x in range(4, w, 10):
            pygame.draw.ellipse(s, (130, 130, 140), (x, 2, 9, 6), 2)
            pygame.draw.ellipse(s, (130, 130, 140), (x, h - 8, 9, 6), 2)
    elif name == "Overcharge":
        pygame.draw.arc(s, (255, 120, 40), (6, 6, w - 12, h - 12), 0.2, 1.4, 2)
        pygame.draw.arc(s, (255, 120, 40), (6, 6, w - 12, h - 12), 3.3, 4.5, 2)
    elif name == "Silenced":
        pygame.draw.line(s, (110, 110, 120), (6, 6), (36, 40), 4)
        pygame.draw.line(s, (110, 110, 120), (36, 6), (6, 40), 4)
    elif name == "Envy":
        for cx in (w // 2 - 8, w // 2 + 8):
            pygame.draw.ellipse(s, (60, 200, 90), (cx - 4, h // 2 - 3, 8, 6))
    elif name == "Corrosion":
        rnd = random.Random(9)
        for _ in range(6):
            pygame.draw.ellipse(s, (110, 190, 70), (rnd.randint(10, w - 30), rnd.randint(20, h - 30), 18, 10), 2)
    elif name == "Toll":
        padlock(s, w // 2, 10, (210, 170, 50))
    elif name == "Brittle":
        cracks(s, (200, 230, 250), 13, thin=True)
    elif name == "Spiked":
        for y in range(14, h - 10, 14):
            pygame.draw.polygon(s, (140, 140, 150), [(0, y), (7, y + 4), (0, y + 8)])
            pygame.draw.polygon(s, (140, 140, 150), [(w, y), (w - 7, y + 4), (w, y + 8)])
    elif name == "Counterfeit":
        wash = pygame.Surface((w, h), pygame.SRCALPHA)
        wash.fill((200, 200, 190, 90))
        s.blit(wash, (0, 0))
        for x in range(0, w, 12):
            pygame.draw.line(s, (170, 170, 160), (x, 0), (x, h))
    elif name == "Glitch":
        for y in (30, 70, 110):
            pygame.draw.line(s, (255, 40, 120), (0, y), (w, y), 2)
            pygame.draw.line(s, (40, 255, 230), (0, y + 3), (w, y + 3), 1)
    elif name == "Heavy Weight":
        pygame.draw.rect(s, (70, 70, 80), (6, h - 22, 16, 14), border_radius=3)
    elif name == "Shock":
        pygame.draw.lines(s, (80, 160, 255), False, [(2, 20), (10, 40), (3, 60), (11, 80), (3, 100)], 2)
    elif name == "Siphon":
        smoke(s, (160, 20, 40), bottom=True)
    elif name == "Doom":
        skull(s, s.get_width() // 2, s.get_height() // 2, (60, 60, 60))


# --- Little shapes ---
def crown(s, cx, cy, size, color, alpha=255):
    pts = [(cx - size, cy + size * 0.5), (cx - size, cy - size * 0.3), (cx - size * 0.5, cy + size * 0.1),
           (cx, cy - size * 0.6), (cx + size * 0.5, cy + size * 0.1), (cx + size, cy - size * 0.3),
           (cx + size, cy + size * 0.5)]
    layer = pygame.Surface(s.get_size(), pygame.SRCALPHA)
    pygame.draw.polygon(layer, (*color, alpha), pts)
    s.blit(layer, (0, 0))


def clover(s, cx, cy, r):
    for dx, dy in ((-r, 0), (r, 0), (0, -r), (0, r)):
        pygame.draw.circle(s, (60, 170, 80), (cx + dx * 0.7, cy + dy * 0.7), r * 0.7)


def cracks(s, color, seed, thin=False):
    rnd = random.Random(seed)
    w, h = s.get_size()
    cx, cy = rnd.randint(30, w - 30), rnd.randint(40, h - 40)
    for _ in range(7):
        a = rnd.random() * math.tau
        x, y = cx, cy
        for _ in range(4):
            nx, ny = x + math.cos(a) * rnd.randint(8, 18), y + math.sin(a) * rnd.randint(8, 18)
            pygame.draw.line(s, color, (x, y), (nx, ny), 1 if thin else 2)
            x, y, a = nx, ny, a + rnd.uniform(-0.6, 0.6)


def padlock(s, cx, cy, color):
    pygame.draw.arc(s, color, (cx - 6, cy - 10, 12, 12), 0, math.pi, 2)
    pygame.draw.rect(s, color, (cx - 7, cy - 4, 14, 10), border_radius=2)


def smoke(s, color, bottom=False):
    layer = pygame.Surface(s.get_size(), pygame.SRCALPHA)
    w, h = s.get_size()
    rnd = random.Random(21)
    for _ in range(14):
        x = rnd.randint(0, w)
        y = rnd.randint(h - 30, h) if bottom else rnd.choice((rnd.randint(0, 20), rnd.randint(h - 20, h)))
        pygame.draw.circle(layer, (*color, 70), (x, y), rnd.randint(6, 12))
    s.blit(layer, (0, 0))


def eye(s, cx, cy, color):
    pygame.draw.ellipse(s, color, (cx - 9, cy - 5, 18, 10), 2)
    pygame.draw.circle(s, color, (cx, cy), 3)


def anvil(s, cx, cy, color):
    layer = pygame.Surface(s.get_size(), pygame.SRCALPHA)
    pygame.draw.polygon(layer, (*color, 90), [(cx - 22, cy - 8), (cx + 18, cy - 8), (cx + 24, cy - 2), (cx + 8, cy + 2),
                                              (cx + 10, cy + 12), (cx - 12, cy + 12), (cx - 8, cy + 2), (cx - 22, cy - 2)])
    s.blit(layer, (0, 0))


def skull(s, cx, cy, color):
    layer = pygame.Surface(s.get_size(), pygame.SRCALPHA)
    pygame.draw.circle(layer, (*color, 80), (cx, cy - 4), 18)
    pygame.draw.rect(layer, (*color, 80), (cx - 10, cy + 8, 20, 10), border_radius=3)
    pygame.draw.circle(layer, (0, 0, 0, 0), (cx - 7, cy - 4), 5)
    pygame.draw.circle(layer, (0, 0, 0, 0), (cx + 7, cy - 4), 5)
    s.blit(layer, (0, 0))


def draw_fog(s):
    w, h = s.get_size()
    layer = pygame.Surface((w, h), pygame.SRCALPHA)
    rnd = random.Random(2)
    for _ in range(40):
        pygame.draw.circle(layer, (235, 238, 245, 170), (rnd.randint(0, w), rnd.randint(0, h)), rnd.randint(12, 26))
    s.blit(layer, (0, 0))
    q = font(42, bold=True).render("?", True, (150, 155, 170))
    s.blit(q, q.get_rect(center=(w // 2, h // 2)))


# --- Card back and deck ---
# Deck looks (only the back changes): base, light, dark, pattern, emblem, rim
DECK_STYLES = {
    "classic": (BACK_RED, (205, 60, 70), (140, 22, 34), "diag", "spades", (246, 239, 224)),
    "midnight": ((24, 40, 92), (60, 90, 170), (12, 20, 52), "stars", "moon", (225, 230, 245)),
    "emerald": ((20, 110, 70), (60, 170, 110), (10, 64, 40), "scales", "clubs", (236, 244, 232)),
    "ember": ((190, 70, 20), (250, 150, 50), (110, 30, 10), "rays", "diamonds", (250, 236, 214)),
    "ivory": ((232, 226, 210), (250, 248, 240), (190, 180, 160), "grid", "hearts", (60, 56, 50)),
    "royal": ((80, 30, 130), (150, 90, 210), (44, 14, 76), "diamonds", "crown", (250, 222, 140)),
    "gold": ((200, 150, 40), (250, 215, 110), (130, 90, 20), "rings", "spades", (60, 40, 10)),
    "frost": ((120, 180, 220), (210, 238, 255), (70, 120, 170), "flakes", "diamonds", (245, 250, 255)),
    "obsidian": ((22, 20, 26), (70, 64, 84), (8, 8, 10), "waves", "spades", (190, 180, 210)),
    "prism": ((40, 40, 50), None, (20, 20, 26), "prism", "star", (250, 250, 255)),
    "starfield": ((10, 10, 24), (120, 120, 200), (4, 4, 10), "dots", "star", (200, 200, 240)),
}


def _star(s, cx, cy, r, color, points=5):
    pts = []
    for i in range(points * 2):
        a = -math.pi / 2 + i * math.pi / points
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    pygame.draw.polygon(s, color, pts)


def _pattern(p, kind, light, dark, w, h):
    if kind == "diag":
        for y in range(-h, h * 2, 12):
            pygame.draw.line(p, light, (0, y), (w, y + w), 3)
            pygame.draw.line(p, dark, (0, y + w), (w, y), 2)
    elif kind == "stars":
        rnd = random.Random(7)
        for _ in range(40):
            _star(p, rnd.uniform(0, w), rnd.uniform(0, h), rnd.uniform(1.5, 3.5), light)
    elif kind == "scales":
        for y in range(0, h + 12, 10):
            for x in range(-10 + (y // 10 % 2) * 7, w + 14, 14):
                pygame.draw.arc(p, light, (x, y, 14, 14), 0, math.pi, 2)
    elif kind == "rays":
        cx, cy = w / 2, h / 2
        for i in range(24):
            a = i * math.tau / 24
            col = light if i % 2 else dark
            pygame.draw.polygon(p, col, [(cx, cy), (cx + math.cos(a) * 200, cy + math.sin(a) * 200),
                                          (cx + math.cos(a + 0.13) * 200, cy + math.sin(a + 0.13) * 200)])
    elif kind == "grid":
        for x in range(0, w, 9):
            pygame.draw.line(p, dark, (x, 0), (x, h), 1)
        for y in range(0, h, 9):
            pygame.draw.line(p, dark, (0, y), (w, y), 1)
    elif kind == "diamonds":
        for y in range(0, h + 16, 16):
            for x in range(0, w + 16, 16):
                pygame.draw.polygon(p, light, [(x, y - 7), (x + 6, y), (x, y + 7), (x - 6, y)], 1)
    elif kind == "rings":
        for r in range(6, 140, 8):
            pygame.draw.circle(p, light if r // 8 % 2 else dark, (w // 2, h // 2), r, 2)
    elif kind == "flakes":
        rnd = random.Random(3)
        for _ in range(22):
            x, y, r = rnd.uniform(0, w), rnd.uniform(0, h), rnd.uniform(3, 7)
            for k in range(3):
                a = k * math.pi / 3
                pygame.draw.line(p, light, (x - math.cos(a) * r, y - math.sin(a) * r),
                                 (x + math.cos(a) * r, y + math.sin(a) * r), 1)
    elif kind == "waves":
        for y in range(0, h + 10, 9):
            pts = [(x, y + math.sin(x / 7) * 3) for x in range(0, w + 2, 2)]
            pygame.draw.lines(p, light, False, pts, 1)
    elif kind == "prism":
        for x in range(-h, w, 4):
            c = pygame.Color(0)
            c.hsva = ((x * 3) % 360, 70, 95, 100)
            pygame.draw.line(p, c, (x, h), (x + h, 0), 4)
    elif kind == "dots":
        rnd = random.Random(11)
        for _ in range(120):
            v = rnd.randint(90, 230)
            p.set_at((rnd.randrange(w), rnd.randrange(h)), (v, v, min(255, v + 25)))
        for _ in range(6):
            _star(p, rnd.uniform(0, w), rnd.uniform(0, h), 3, light, 4)


def card_back(style="classic"):
    key = ("back", style)
    if key in _cache:
        return _cache[key]
    base, light, dark, kind, emblem_kind, rim = DECK_STYLES.get(style, DECK_STYLES["classic"])
    w, h = CARD_W, CARD_H
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(s, rim, (0, 0, w, h), border_radius=RADIUS)
    inner = pygame.Rect(6, 6, w - 12, h - 12)
    pygame.draw.rect(s, base, inner, border_radius=RADIUS - 3)
    pattern = pygame.Surface(inner.size, pygame.SRCALPHA)
    _pattern(pattern, kind, light, dark, inner.w, inner.h)
    mask = pygame.Surface(inner.size, pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=RADIUS - 3)
    pattern.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    s.blit(pattern, inner.topleft)
    pygame.draw.rect(s, rim, inner.inflate(-14, -14), 2, border_radius=6)
    emblem = pygame.Rect(0, 0, 42, 42)
    emblem.center = (w // 2, h // 2)
    pygame.draw.ellipse(s, rim, emblem)
    if emblem_kind in SUIT_COLOR:
        suit(s, emblem_kind, w // 2, h // 2, 24, base)
    elif emblem_kind == "crown":
        crown(s, w // 2, h // 2 + 2, 26, base)
    elif emblem_kind == "moon":
        pygame.draw.circle(s, base, (w // 2, h // 2), 13)
        pygame.draw.circle(s, rim, (w // 2 + 6, h // 2 - 4), 11)
    else:
        _star(s, w // 2, h // 2, 15, base if style != "prism" else (40, 40, 50))
    edge = tuple(max(0, c - 70) for c in base)
    pygame.draw.rect(s, edge, (0, 0, w, h), 2, border_radius=RADIUS)
    _cache[key] = s
    return s


# --- Blender renders (assets\*.png, made by _claude_tools\infinideck_blender.py) ---
ASSET_DIR = Path(__file__).resolve().parent / "assets"
_raw = {}


def asset(name, size, tint=None, alpha=255):
    """A rendered asset scaled so its longest side is `size`, optionally tinted. None if the file is missing."""
    key = ("asset", name, size, tint, alpha)
    if key in _cache:
        return _cache[key]
    if name not in _raw:
        try:
            img = pygame.image.load(str(ASSET_DIR / f"{name}.png")).convert_alpha()
            _raw[name] = img.subsurface(img.get_bounding_rect()).copy()
        except (pygame.error, FileNotFoundError, OSError):
            _raw[name] = None
    raw = _raw[name]
    if raw is None:
        _cache[key] = None
        return None
    w, h = raw.get_size()
    k = size / max(w, h)
    img = pygame.transform.smoothscale(raw, (max(1, round(w * k)), max(1, round(h * k))))
    if tint is not None:
        img.fill((*tint, 255), special_flags=pygame.BLEND_RGBA_MULT)
    if alpha < 255:
        img.set_alpha(alpha)
    if len(_cache) > 4000:
        _cache.clear()
    _cache[key] = img
    return img


def casino_chip(size, value="100"):
    """The $100 casino chip icon (cached by size): the Blender render when it's there, else drawn in code."""
    key = ("chip", size, value)
    if key in _cache:
        return _cache[key]
    rendered = asset("chip", size)
    if rendered is not None:
        _cache[key] = rendered
        return rendered
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size / 2
    pygame.draw.circle(s, (20, 20, 26), (c, c + size * 0.04), c)                 # edge shadow
    pygame.draw.circle(s, (40, 70, 200), (c, c), c - 1)
    for i in range(8):                                                               # the white edge stripes
        a = i * math.tau / 8
        pts = []
        for da in (-0.17, 0.17):
            pts.append((c + math.cos(a + da) * (c - 1), c + math.sin(a + da) * (c - 1)))
        for da in (0.17, -0.17):
            pts.append((c + math.cos(a + da) * (c * 0.72), c + math.sin(a + da) * (c * 0.72)))
        pygame.draw.polygon(s, (240, 240, 245), pts)
    pygame.draw.circle(s, (32, 60, 180), (c, c), c * 0.66)
    pygame.draw.circle(s, (240, 240, 245), (c, c), c * 0.66, max(1, size // 18))
    if size >= 22:
        t = font(max(8, int(size * 0.3)), bold=True).render(f"${value}" if size >= 34 else value, True, (245, 245, 250))
        s.blit(t, t.get_rect(center=(c, c + 1)))
    _cache[key] = s
    return s


def tag(text, kind, size=16, pad=6):
    """A number with a coloured background (chips blue, multiplier red, TP purple, crit orange, buff green,
    debuff dark red, streak yellow)."""
    key = ("tag", text, kind, size)
    if key in _cache:
        return _cache[key]
    bg = kind if isinstance(kind, tuple) else TAG_COLORS[kind]          # a kind name, or any (r, g, b) colour
    bright = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2] > 150
    t = font(size, bold=True).render(text, True, (20, 20, 24) if kind == "streak" or bright else (250, 250, 252))
    s = rounded((t.get_width() + pad * 2, t.get_height() + 2), bg, 6)
    s.blit(t, (pad, 1))
    if len(_cache) > 4000:
        _cache.clear()
    _cache[key] = s
    return s


def mod_color(name):
    if name in BUFFS:
        return BUFFS[name][4]
    return DEBUFFS[name][2] if name in DEBUFFS else (200, 200, 200)
