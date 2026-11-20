"""Animated modifier effects: every buff and debuff gets its own moving look on the card (drawn into the card
each frame, so it turns with it), a glow under the card, and its own particles from assets\\Particles. Effects
stack, so a card with five modifiers shows all five."""
import math
import random

import _art as art
import pygame
from _cards import BUFFS, DEBUFFS

# --- Settings ---
MAX_SPARKS = 900                # particles alive at once (oldest go first)
EMIT_SCALE = 1.0                # Settings > Particles changes this (0.5 low, 1 normal, 1.6 lots)
ROT_STEP = 12                   # sprite rotations are cached every 12 degrees

# name: (particle sprite(s), colour, particles per second, motion, card look)
# motion: rise, fall, orbit, burst, drift, edge, spark, sink, swirl, rain
# look: shine, rainbow, rim, pulse, flicker, ghost, smoke, static, glitch, frost, drip, veil, runes, cracks, none
FX = {
    # buffs
    "Double Pay": (("coin_1", "coin_2"), (130, 200, 255), 3, "rise", "pulse"),
    "Triple Pay": (("coin_1", "coin_2", "coin_3"), (100, 170, 255), 5, "rise", "pulse"),
    "Jackpot": (("coin_1", "coin_2", "coin_3", "sparkle4"), (255, 210, 80), 10, "burst", "shine"),
    "Steady": (("dot",), (190, 200, 215), 2, "drift", "rim"),
    "Greedy": (("token", "coin_2"), (110, 230, 130), 4, "rise", "pulse"),
    "Lucky": (("clover", "sparkle4"), (90, 230, 120), 5, "swirl", "shine"),
    "Rich": (("gem", "sparkle4"), (200, 110, 220), 5, "rise", "shine"),
    "Golden": (("sparkle4", "sparkle6", "glow_hot"), (255, 205, 70), 12, "rise", "shine"),
    "Echo": (("ring",), (160, 170, 255), 2, "burst", "ghost"),
    "Vampire": (("drop", "fang"), (210, 30, 50), 4, "fall", "drip"),
    "Explosive": (("flame_1", "flame_2", "ember"), (255, 130, 40), 14, "rise", "flicker"),
    "Safe": (("lock", "dot"), (200, 205, 215), 2, "orbit", "rim"),
    "Blood": (("drop", "splat"), (190, 15, 30), 7, "fall", "drip"),
    "Banker": (("token", "coin_1"), (130, 210, 150), 5, "rain", "pulse"),
    "Flash": (("bolt_1", "bolt_2", "flare"), (255, 240, 120), 6, "spark", "flicker"),
    "Heavy": (("anvil", "dust"), (160, 150, 140), 2, "fall", "none"),
    "Jinx": (("rune_1", "rune_2"), (170, 90, 220), 3, "swirl", "runes"),
    "Blessing": (("feather", "halo", "sparkle6"), (255, 245, 210), 5, "fall", "shine"),
    "Pure": (("sparkle8", "glow"), (250, 250, 255), 6, "rise", "pulse"),
    "Tax": (("minus", "token"), (230, 70, 70), 3, "fall", "none"),
    "Wildcard": (("sparkle6", "star5", "confetti_1", "confetti_2"), None, 14, "swirl", "rainbow"),
    "Crown": (("crown", "sparkle4"), (255, 215, 90), 3, "orbit", "shine"),
    "Iron": (("gear", "dot"), (150, 155, 170), 2, "orbit", "rim"),
    "Overflow": (("bubble", "wave"), (200, 240, 255), 6, "rise", "pulse"),
    "Shattered": (("shard_1", "shard_2", "shard_3"), (210, 230, 250), 5, "burst", "cracks"),
    "Royal": (("gem", "crown"), (150, 100, 255), 4, "orbit", "shine"),
    "Cursed": (("smoke_1", "smoke_2", "skull"), (90, 50, 110), 5, "rise", "smoke"),
    "Pristine": (("sparkle4", "glow"), (240, 248, 255), 4, "drift", "shine"),
    "Overloaded": (("bolt_2", "bolt_3", "ember"), (255, 150, 40), 9, "spark", "flicker"),
    "Final": (("glow_hot", "sparkle8", "flare"), (255, 230, 150), 10, "swirl", "pulse"),
    # debuffs
    "Taxed": (("minus",), (210, 60, 60), 2, "fall", "none"),
    "Rust": (("dust", "splat"), (170, 95, 45), 3, "fall", "smoke"),
    "Greed Penalty": (("lock",), (220, 50, 50), 1, "fall", "none"),
    "Hexed": (("smoke_1", "rune_3"), (110, 50, 150), 5, "swirl", "smoke"),
    "Leak": (("drop",), (100, 210, 90), 6, "fall", "drip"),
    "Burn": (("flame_3", "flame_4", "ember", "smoke_3"), (240, 100, 30), 12, "rise", "flicker"),
    "Blind": (("smoke_2",), (70, 70, 85), 3, "drift", "veil"),
    "Drain": (("drop", "spiral"), (200, 30, 45), 3, "sink", "none"),
    "Static": (("static", "bolt_1"), (240, 225, 70), 6, "spark", "static"),
    "Shatter Risk": (("crack", "shard_1"), (235, 235, 245), 2, "fall", "cracks"),
    "Jinxed": (("eye",), (160, 70, 200), 1, "drift", "runes"),
    "Weighed Down": (("anvil",), (120, 120, 130), 1, "fall", "none"),
    "Void": (("spiral", "glow"), (60, 30, 110), 4, "sink", "smoke"),
    "Slow": (("hourglass", "dust"), (150, 150, 160), 2, "drift", "none"),
    "Overcharge": (("bolt_3", "ember"), (255, 130, 50), 6, "spark", "flicker"),
    "Silenced": (("cross",), (130, 130, 140), 1, "drift", "veil"),
    "Shrink": (("minus", "dot"), (160, 160, 180), 2, "sink", "none"),
    "Envy": (("eye", "leaf"), (70, 210, 100), 2, "drift", "none"),
    "Corrosion": (("bubble", "drop"), (120, 200, 80), 5, "rise", "drip"),
    "Toll": (("token",), (230, 190, 70), 2, "sink", "none"),
    "Fog": (("smoke_1", "smoke_2", "smoke_3"), (225, 228, 238), 6, "drift", "veil"),
    "Brittle": (("crack", "snow"), (200, 230, 250), 2, "fall", "frost"),
    "Spiked": (("shard_2",), (160, 160, 170), 2, "edge", "none"),
    "Decayed": (("leaf", "dust"), (110, 120, 85), 3, "fall", "smoke"),
    "Counterfeit": (("token", "cross"), (160, 160, 150), 2, "fall", "veil"),
    "Glitch": (("static",), (90, 255, 230), 6, "spark", "glitch"),
    "Heavy Weight": (("anvil", "dust"), (90, 90, 100), 2, "fall", "none"),
    "Shock": (("bolt_1", "bolt_2"), (90, 170, 255), 6, "spark", "flicker"),
    "Siphon": (("spiral", "drop"), (170, 25, 45), 4, "sink", "drip"),
    "Doom": (("skull", "smoke_2"), (40, 40, 45), 3, "rise", "smoke"),
}
for _name in list(BUFFS) + list(DEBUFFS):
    assert _name in FX, _name

_rot_cache = {}


def mod_color(name, now=0.0, k=0):
    col = FX[name][1]
    if col is None:                                     # Wildcard: every colour
        c = pygame.Color(0)
        c.hsva = ((now * 160 + k * 47) % 360, 70, 100, 100)
        return c.r, c.g, c.b
    return col


# --- Particles ---
class Particle:
    __slots__ = ("additive", "color", "gravity", "life", "max_life", "size", "spin", "sprite", "turn", "vx", "vy",
                 "x", "y")

    def __init__(self, x, y, vx, vy, sprite, color, life, size, gravity=0.0, spin=0.0, additive=True):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.sprite, self.color, self.life, self.max_life, self.size = sprite, color, life, life, size
        self.gravity, self.spin, self.turn, self.additive = gravity, spin, random.uniform(0, 360), additive


SOLID = {"coin_1", "coin_2", "coin_3", "skull", "anvil", "lock", "crown", "gem", "drop", "splat", "clover",
         "feather", "leaf", "token", "fang", "hourglass", "eye", "smoke_1", "smoke_2", "smoke_3", "confetti_1",
         "confetti_2", "confetti_3", "static", "cross", "minus", "plus", "gear", "dust"}


def emit(game, tc, now, dt):
    """Spawns each modifier's particles around a card on the table."""
    mods = tc.card.buffs + tc.card.debuffs
    if not mods or "Fog" in tc.card.debuffs and len(mods) > 1:
        mods = ["Fog"] if "Fog" in tc.card.debuffs else mods
    x, y = tc.pos(now)
    hw, hh = art.CARD_W / 2, art.CARD_H / 2
    crowd = max(1.0, len(game.table) / 8)              # a crowded table emits a bit less each
    for k, name in enumerate(mods):
        sprites, _col, rate, motion, _look = FX[name]
        if random.random() > rate * dt * EMIT_SCALE / crowd:
            continue
        sprite = random.choice(sprites)
        col = mod_color(name, now, k)
        size = random.uniform(10, 20) if sprite not in ("glow", "glow_hot", "flare", "ring", "halo") else \
            random.uniform(22, 40)
        if sprite in ("flame_1", "flame_2", "flame_3", "flame_4"):
            size = random.uniform(16, 30)
        life = random.uniform(0.7, 1.5)
        add = sprite not in SOLID
        if motion == "rise":
            p = Particle(x + random.uniform(-hw, hw), y + random.uniform(-hh * 0.3, hh), random.uniform(-12, 12),
                         random.uniform(-70, -30), sprite, col, life, size, 0, random.uniform(-90, 90), add)
        elif motion == "fall":
            p = Particle(x + random.uniform(-hw, hw), y + random.uniform(-hh, 0), random.uniform(-15, 15),
                         random.uniform(-30, 10), sprite, col, life, size, 160, random.uniform(-120, 120), add)
        elif motion == "rain":
            p = Particle(x + random.uniform(-hw, hw), y - hh - 20, random.uniform(-6, 6), random.uniform(40, 80),
                         sprite, col, life, size, 120, random.uniform(-200, 200), add)
        elif motion == "orbit":
            a = now * 1.6 + k * 2.1 + random.uniform(-0.3, 0.3)
            px, py = x + math.cos(a) * hw * 1.25, y + math.sin(a) * hh * 1.15
            p = Particle(px, py, -math.sin(a) * 30, math.cos(a) * 30, sprite, col, life * 0.8, size, 0, 40, add)
        elif motion == "burst":
            a = random.uniform(0, math.tau)
            v = random.uniform(40, 120)
            p = Particle(x + math.cos(a) * hw * 0.6, y + math.sin(a) * hh * 0.6, math.cos(a) * v, math.sin(a) * v,
                         sprite, col, life * 0.8, size, 60, random.uniform(-200, 200), add)
        elif motion == "swirl":
            a = random.uniform(0, math.tau)
            r = random.uniform(0.8, 1.2)
            p = Particle(x + math.cos(a) * hw * r, y + math.sin(a) * hh * r, -math.sin(a) * 60 - math.cos(a) * 10,
                         math.cos(a) * 60 - math.sin(a) * 10 - 20, sprite, col, life, size, 0,
                         random.uniform(-160, 160), add)
        elif motion == "sink":
            a = random.uniform(0, math.tau)
            p = Particle(x + math.cos(a) * hw * 1.4, y + math.sin(a) * hh * 1.3, -math.cos(a) * 55,
                         -math.sin(a) * 55, sprite, col, life * 0.9, size, 0, 220, add)
        elif motion == "edge":
            side = random.choice((-1, 1))
            p = Particle(x + side * hw, y + random.uniform(-hh, hh), side * random.uniform(30, 70),
                         random.uniform(-10, 10), sprite, col, life * 0.6, size, 0, 0, add)
        elif motion == "spark":
            a = random.uniform(0, math.tau)
            v = random.uniform(120, 260)
            p = Particle(x + random.uniform(-hw, hw), y + random.uniform(-hh, hh), math.cos(a) * v,
                         math.sin(a) * v, sprite, col, random.uniform(0.15, 0.35), size, 0, random.uniform(-400, 400),
                         add)
        else:   # drift
            p = Particle(x + random.uniform(-hw * 1.2, hw * 1.2), y + random.uniform(-hh * 1.2, hh * 1.2),
                         random.uniform(-14, 14), random.uniform(-14, 14), sprite, col, life * 1.3, size, 0,
                         random.uniform(-40, 40), add)
        game.sparks.append(p)
    if len(game.sparks) > MAX_SPARKS:
        del game.sparks[:len(game.sparks) - MAX_SPARKS]


def burst(game, pos, mods, now, n=26):
    """A one-off explosion of each modifier's particles (when a modified card lands)."""
    for k, name in enumerate(mods):
        sprites = FX[name][0]
        for _ in range(max(4, n // max(1, len(mods)))):
            a = random.uniform(0, math.tau)
            v = random.uniform(80, 300)
            sprite = random.choice(sprites)
            game.sparks.append(Particle(pos[0], pos[1], math.cos(a) * v, math.sin(a) * v - 60, sprite,
                                        mod_color(name, now, k), random.uniform(0.5, 1.1), random.uniform(12, 24),
                                        280, random.uniform(-300, 300), sprite not in SOLID))


def update(sparks, dt):
    alive = []
    for s in sparks:
        s.life -= dt
        if s.life <= 0:
            continue
        s.vy += s.gravity * dt
        s.x += s.vx * dt
        s.y += s.vy * dt
        s.turn += s.spin * dt
        alive.append(s)
    return alive


def sprite_img(name, size, color, alpha):
    size = max(4, int(size) // 2 * 2)
    tint = tuple(c // 16 * 16 + 15 for c in color)
    a = max(16, int(alpha) // 24 * 24)
    return art.asset("Particles/" + name, size, tint, a)


def draw(surf, sparks):
    for s in sparks:
        k = s.life / s.max_life
        fade = min(1.0, k * 2.5) * min(1.0, (1 - k) * 8 + 0.2)
        size = s.size * (0.6 + 0.4 * min(1.0, k * 2))
        img = art.glow(s.sprite, size, s.color, 255 * fade) if s.additive else \
            sprite_img(s.sprite, size, s.color, 255 * fade)
        if img is None:
            pygame.draw.circle(surf, s.color, (int(s.x), int(s.y)), max(1, int(size / 6)))
            continue
        if s.spin:
            key = (id(img), int(s.turn) // ROT_STEP % (360 // ROT_STEP))
            rot = _rot_cache.get(key)
            if rot is None:
                if len(_rot_cache) > 3000:
                    _rot_cache.clear()
                rot = _rot_cache[key] = pygame.transform.rotate(img, key[1] * ROT_STEP)
            img = rot
        r = img.get_rect(center=(int(s.x), int(s.y)))
        if s.additive:
            surf.blit(img, r, special_flags=pygame.BLEND_RGB_ADD)
        else:
            surf.blit(img, r)


# --- Under-card glow ---
def under(surf, pos, mods, now, alpha=255, scale=1.0):
    """A soft coloured glow behind a modified card, pulsing, one layer per modifier."""
    if not mods:
        return
    for k, name in enumerate(mods[:4]):
        col = mod_color(name, now, k)
        pulse = 0.75 + 0.25 * math.sin(now * (2.2 + k * 0.7) + k)
        size = int((art.CARD_H * 1.7 + 14 * k) * scale * (0.95 + 0.05 * pulse))
        img = art.glow("glow", size, col, alpha * 0.55 * pulse)
        if img is not None:
            surf.blit(img, img.get_rect(center=(int(pos[0]), int(pos[1]))), special_flags=pygame.BLEND_RGB_ADD)


# --- Animated looks drawn into the card ---
def overlay(card, now, phase):
    """A card-sized layer with each modifier's moving look (shine sweeps, rainbow rims, flicker...)."""
    w, h = art.CARD_W, art.CARD_H
    layer = pygame.Surface((w, h), pygame.SRCALPHA)
    mods = ["Fog"] if "Fog" in card.debuffs else card.buffs + card.debuffs     # Fog hides the other modifiers
    t = now + phase
    for k, name in enumerate(mods):
        look = FX[name][4]
        col = mod_color(name, now, k)
        if look == "shine":                                # a bright band sweeps across every ~2.5 s
            x = ((t * 0.4 + k * 0.3) % 1.0) * (w + h) * 1.4 - h
            band = pygame.Surface((w, h), pygame.SRCALPHA)
            for i in range(14):
                a = int(90 * (1 - abs(i - 7) / 7))
                pygame.draw.line(band, (*art.mix(col, (255, 255, 255), 0.6), a), (x + i, 0), (x + i - h * 0.5, h), 2)
            layer.blit(band, (0, 0))
            pygame.draw.rect(layer, (*col, int(150 + 80 * math.sin(t * 3))), (2, 2, w - 4, h - 4), 2,
                             border_radius=art.RADIUS - 1)
        elif look == "rainbow":                            # a border cycling round the rainbow
            for i in range(4):
                c = pygame.Color(0)
                c.hsva = ((t * 220 + i * 40) % 360, 80, 100, 100)
                pygame.draw.rect(layer, (c.r, c.g, c.b, 200 - i * 40), (i, i, w - i * 2, h - i * 2), 1,
                                 border_radius=art.RADIUS)
            tint = pygame.Surface((w, h), pygame.SRCALPHA)
            c = pygame.Color(0)
            c.hsva = ((t * 120) % 360, 60, 100, 100)
            tint.fill((c.r, c.g, c.b, 34))
            layer.blit(tint, (0, 0))
        elif look == "rim":
            a = int(110 + 90 * (0.5 + 0.5 * math.sin(t * 2.5 + k)))
            pygame.draw.rect(layer, (*col, a), (1, 1, w - 2, h - 2), 3, border_radius=art.RADIUS)
        elif look == "pulse":
            a = int(60 * (0.5 + 0.5 * math.sin(t * 4 + k)))
            pulse = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(pulse, (*col, a), (0, 0, w, h), border_radius=art.RADIUS)
            layer.blit(pulse, (0, 0))
            pygame.draw.rect(layer, (*col, 160), (2, 2, w - 4, h - 4), 2, border_radius=art.RADIUS - 1)
        elif look == "flicker":
            a = int(random.uniform(40, 140))
            for i in range(3):
                pygame.draw.rect(layer, (*col, max(0, a - i * 40)), (i, i, w - i * 2, h - i * 2), 2,
                                 border_radius=art.RADIUS)
            for _ in range(2):
                y = random.uniform(0, h)
                pygame.draw.line(layer, (*col, 120), (0, y), (random.uniform(6, 18), y + random.uniform(-6, 6)), 2)
        elif look == "ghost":
            off = 4 + 3 * math.sin(t * 3)
            pygame.draw.rect(layer, (*col, 90), (off, -off, w - 2, h - 2), 2, border_radius=art.RADIUS)
            pygame.draw.rect(layer, (*col, 50), (off * 2, -off * 2, w - 2, h - 2), 2, border_radius=art.RADIUS)
        elif look == "smoke":
            for i in range(5):
                a = t * 0.8 + i * 1.3 + k
                cx = w / 2 + math.cos(a) * w * 0.35
                cy = h * (1 - ((t * 0.15 + i / 5) % 1.0))
                g = art.asset("Particles/smoke_" + str(i % 3 + 1), 46, tuple(c // 16 * 16 for c in col), 96)
                if g is not None:
                    layer.blit(g, g.get_rect(center=(cx, cy)))
        elif look == "static":
            g = art.asset("Particles/static", 64, col, 70)
            if g is not None:
                ox, oy = random.randint(-30, 0), random.randint(-30, 0)
                for gx in range(ox, w, 64):
                    for gy in range(oy, h, 64):
                        layer.blit(g, (gx, gy))
        elif look == "glitch":
            for _ in range(3):
                y = random.randint(0, h - 6)
                pygame.draw.rect(layer, (*col, 110), (0, y, w, random.randint(2, 6)))
                pygame.draw.rect(layer, (255, 40, 120, 90), (random.randint(-6, 6), y + 3, w, 2))
        elif look == "frost":
            for i in range(4):
                a = int(80 + 60 * math.sin(t * 2 + i))
                pygame.draw.rect(layer, (*col, a), (i * 2, i * 2, w - i * 4, h - i * 4), 1, border_radius=art.RADIUS)
        elif look == "drip":
            for i in range(4):
                x = 14 + i * (w - 28) / 3
                ln = (t * 30 + i * 37) % 60
                pygame.draw.line(layer, (*col, 200), (x, 0), (x, ln), 3)
                pygame.draw.circle(layer, (*col, 220), (x, ln), 4)
        elif look == "veil":
            a = int(50 + 30 * math.sin(t * 1.5))
            veil = pygame.Surface((w, h), pygame.SRCALPHA)
            veil.fill((*col, a))
            layer.blit(veil, (0, 0))
        elif look == "runes":
            for i in range(3):
                a = t * 1.2 + i * math.tau / 3
                g = art.asset(f"Particles/rune_{i + 1}", 18, col, 170)
                if g is not None:
                    layer.blit(g, g.get_rect(center=(w / 2 + math.cos(a) * w * 0.32, h / 2 + math.sin(a) * h * 0.32)))
        elif look == "cracks":
            a = int(120 + 100 * (0.5 + 0.5 * math.sin(t * 5)))
            g = art.asset("Particles/crack", 70, col, a)
            if g is not None:
                layer.blit(g, g.get_rect(center=(w * 0.6, h * 0.45)))
    if len(mods) > 1:                                       # a row of gems along the bottom: one per modifier
        n = len(mods)
        gap = min(14, (w - 16) / n)
        x0 = w / 2 - gap * (n - 1) / 2
        for k, name in enumerate(mods):
            col = mod_color(name, now, k)
            cx, cy = x0 + k * gap, h - 9
            bob = math.sin(t * 4 + k) * 1.2
            pygame.draw.circle(layer, (10, 10, 14, 230), (cx, cy + bob), 5)
            pygame.draw.circle(layer, (*col, 255), (cx, cy + bob), 4)
            pygame.draw.circle(layer, (255, 255, 255, 200), (cx - 1, cy - 1 + bob), 1)
    return layer
