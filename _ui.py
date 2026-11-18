"""Infinideck's UI kit, in a Balatro-like style: chunky slab panels with thick dark outlines, bold coloured
buttons with a darker lip that lift and wobble when hovered, and text with a drop shadow."""
import math

import _art as art
import pygame

# --- Look ---
PANEL = (19, 20, 27)            # near-black panel (black UI makes the colours pop)
PANEL_IN = (8, 9, 13)           # sunken boxes inside panels
EDGE = (0, 0, 0)                # thick outline
TEXT = (246, 244, 238)
MUTED = (168, 176, 180)
SHADOW = (0, 0, 0)
COLORS = {                      # face, lip (the darker underside)
    "red": ((232, 72, 64), (150, 38, 34)),
    "blue": ((0, 140, 228), (0, 88, 156)),
    "orange": ((246, 156, 22), (168, 98, 8)),
    "green": ((60, 176, 124), (32, 110, 76)),
    "purple": ((142, 92, 224), (88, 52, 150)),
    "gold": ((236, 188, 70), (160, 118, 30)),
    "pink": ((236, 72, 153), (150, 28, 90)),
    "cyan": ((20, 200, 220), (8, 120, 140)),
    "gray": ((58, 60, 72), (32, 33, 42)),
    "dark": ((34, 35, 46), (16, 17, 24)),
}
LIP = 6                         # how thick the slab edge is
_juice = {}                     # key -> [hovering, time the hover changed]


def juice(key, hovering, now):
    """A springy scale: a little bounce when the mouse arrives, then a small lift while it stays."""
    st = _juice.get(key)
    if st is None or st[0] != hovering:
        st = _juice[key] = [hovering, now]
    t = now - st[1]
    if hovering:
        return 1.04 + 0.05 * math.exp(-t * 9) * math.cos(t * 32)
    return 1.0 + 0.03 * math.exp(-t * 10) * math.cos(t * 30)


def label(s, text, size, pos, color=TEXT, anchor="topleft", bold=True, shadow=True, alpha=255):
    f = art.font(size, bold=bold)
    t = f.render(str(text), True, color)
    r = t.get_rect(**{anchor: pos})
    if shadow:
        sh = f.render(str(text), True, SHADOW)
        sh.set_alpha(int(150 * alpha / 255))
        s.blit(sh, r.move(max(1, size // 12), max(1, size // 12)))
    if alpha < 255:
        t.set_alpha(alpha)
    s.blit(t, r)
    return r


def panel(s, rect, fill=PANEL, radius=16, lip=LIP, edge=EDGE, alpha=255, outline=3):
    """A chunky slab: dark outline, a darker underside showing below, and a soft top highlight."""
    rect = pygame.Rect(rect)
    under = tuple(max(0, c - 22) for c in fill)
    body = rect.copy()
    body.height -= lip
    if alpha < 255:
        layer = pygame.Surface((rect.w + outline * 2, rect.h + outline * 2), pygame.SRCALPHA)
        panel(layer, pygame.Rect(outline, outline, rect.w, rect.h), fill, radius, lip, edge, 255, outline)
        layer.set_alpha(alpha)
        s.blit(layer, (rect.x - outline, rect.y - outline))
        return body
    pygame.draw.rect(s, edge, rect.inflate(outline * 2, outline * 2), border_radius=radius + outline)
    pygame.draw.rect(s, under, rect, border_radius=radius)
    pygame.draw.rect(s, fill, body, border_radius=radius)
    hi = tuple(min(255, c + 16) for c in fill)
    pygame.draw.line(s, hi, (body.x + radius, body.y + 2), (body.right - radius, body.y + 2), 2)
    return body


def inset(s, rect, fill=PANEL_IN, radius=10):
    """A sunken box (where numbers live)."""
    rect = pygame.Rect(rect)
    pygame.draw.rect(s, fill, rect, border_radius=radius)
    pygame.draw.rect(s, (0, 0, 0), rect, 2, border_radius=radius)
    pygame.draw.line(s, tuple(max(0, c - 10) for c in fill), (rect.x + radius, rect.y + 3),
                     (rect.right - radius, rect.y + 3), 2)
    return rect


def button(s, rect, text, color="red", now=0.0, key=None, enabled=True, size=22, sub=None, selected=False,
           icon=None):
    """A Balatro button. Returns True while the mouse is over it (and it's enabled)."""
    rect = pygame.Rect(rect)
    mouse = pygame.mouse.get_pos()
    hover = enabled and rect.collidepoint(mouse)
    pressed = hover and pygame.mouse.get_pressed()[0]
    face, lip = COLORS["gray" if not enabled else color]
    if not enabled:
        face, lip = (60, 66, 70), (38, 42, 45)
    k = juice(key or (text, rect.topleft), hover or selected, now) if enabled else 1.0
    r = rect.inflate(int(rect.w * (k - 1)), int(rect.h * (k - 1)))
    drop = LIP if not pressed else 2
    pygame.draw.rect(s, EDGE, r.inflate(6, 6 + LIP).move(0, LIP // 2), border_radius=14)
    pygame.draw.rect(s, lip, r.move(0, LIP), border_radius=12)
    top = r.move(0, LIP - drop)
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
    label(s, text, size, (tx, cy), TEXT if enabled else (150, 154, 158), "center")
    if sub:
        label(s, sub, 13, (top.centerx, top.centery + 13), (255, 255, 255) if enabled else (130, 134, 138),
              "center", bold=False)
    return hover


def tag(s, text, kind, pos, size=15, anchor="topleft"):
    """A coloured value chip with a darker lip (chips blue, mult red, TP purple...)."""
    img = art.tag(text, kind, size)
    r = img.get_rect(**{anchor: pos})
    under = tuple(max(0, c - 70) for c in (kind if isinstance(kind, tuple) else art.TAG_COLORS[kind]))
    pygame.draw.rect(s, under, r.move(0, 3), border_radius=6)
    s.blit(img, r)
    return r


def pop(t, dur=0.28):
    """Scale for a popping-in element: overshoots, then settles at 1."""
    if t >= dur:
        return 1.0
    x = t / dur
    return 0.2 + 0.8 * (1 - (1 - x) ** 3) + 0.25 * math.sin(x * math.pi) * (1 - x)
