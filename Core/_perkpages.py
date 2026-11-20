"""The Perks page (equip slots, 5 perk cards per page, sacrificing for slots), the Achievements page (Normal and
Secret tabs), the Shatter window and the perk reveal."""
import math
import random

import _achievements as ach
import _art as art
import _meta as meta
import _perks as perks
import _tree as tree
import _ui as ui
import pygame
from _bignum import Big

# --- Settings ---
TEXT = (238, 234, 226)
MUTED = (150, 146, 160)
PANEL = (18, 17, 24)
PANEL_EDGE = (58, 52, 70)
GOLD = (255, 205, 90)
PER_PAGE = 5
CARD_W, CARD_H = 236, 330
ACH_PER_PAGE = 12
CONFIRM_SECONDS = 3.0


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def ease_out(t):
    return 1 - (1 - t) ** 3


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


def perk_color(i):
    c = pygame.Color(0)
    c.hsva = ((i * 137.5) % 360, 62, 92, 100)
    return c.r, c.g, c.b


def big_padlock(s, cx, cy, color, k=3.0):
    pygame.draw.arc(s, color, (cx - 6 * k, cy - 10 * k, 12 * k, 12 * k), 0, math.pi, int(2 * k))
    pygame.draw.rect(s, color, (cx - 7 * k, cy - 4 * k, 14 * k, 10 * k), border_radius=int(2 * k))
    pygame.draw.circle(s, (34, 33, 40), (cx, cy + 1 * k), int(1.5 * k))


def check(s, rect, color, width=3):
    """A drawn check mark (no emoji)."""
    x, y, w, h = rect
    pygame.draw.lines(s, color, False, [(x + w * 0.18, y + h * 0.55), (x + w * 0.42, y + h * 0.78),
                                         (x + w * 0.84, y + h * 0.25)], width)


class PerkPages:
    def __init__(self, game):
        self.g = game
        self.W, self.H = game.screen.get_size()
        self.page = {"Perks": 0, "Normal": 0, "Secret": 0}
        self.ach_tab = "Normal"
        self.hover = None
        self.hover_t = 0.0
        self.sac_confirm = -10.0
        self.equip_flash = (None, 0.0)
        self.shatter_open = False
        self.shatter_t = 0.0
        self.reveal = None              # (perk, time) after a Shatter
        self.search = ""                # the achievements search box

    def back_rect(self):
        return pygame.Rect(18, 18, 190, 44)          # where the menu button is on the table

    # --- Perks page layout ---
    def slot_rects(self):
        return [pygame.Rect(self.W // 2 - 5 * 186 // 2 + i * 186, 112, 172, 64) for i in range(5)]

    def card_rects(self):
        x0 = self.W // 2 - (PER_PAGE * (CARD_W + 30) - 30) // 2
        return [pygame.Rect(x0 + i * (CARD_W + 30), 236, CARD_W, CARD_H) for i in range(PER_PAGE)]

    def pager(self):
        return pygame.Rect(self.W // 2 - 240, 610, 54, 44), pygame.Rect(self.W // 2 + 186, 610, 54, 44)

    def sacrifice_rect(self):
        return pygame.Rect(self.W // 2 - 380, self.H - 150, 760, 70)

    def total_pages(self, name):
        if name == "Perks":
            return math.ceil(len(perks.PERKS) / PER_PAGE)
        return max(1, math.ceil(len(self.ach_list()) / ACH_PER_PAGE))

    def ach_list(self):
        """The achievements on the current tab that match the search (hidden secret ones only match '???')."""
        group = ach.NORMAL if self.ach_tab == "Normal" else ach.SECRET
        q = self.search.strip().lower()
        if not q:
            return group
        got = self.g.profile.achievements
        out = []
        for a in group:
            hidden = self.ach_tab == "Secret" and a[0] not in got
            text = "???" if hidden else (a[0] + " " + a[1]).lower()
            if q in text or (q in ("done", "unlocked") and a[0] in got) or (q == "locked" and a[0] not in got):
                out.append(a)
        return out

    def search_rect(self):
        return pygame.Rect(self.W - 520, 110, 450, 42)

    # --- Input ---
    def handle(self, page, e, now):
        if page not in ("Perks", "Achievements"):
            return False
        if page == "Achievements" and e.type == pygame.TEXTINPUT:          # typing goes into the search box
            if len(self.search) < 40:
                self.search += e.text
                self.page["Normal"] = self.page["Secret"] = 0
            return True
        if page == "Achievements" and e.type == pygame.KEYDOWN and e.key != pygame.K_ESCAPE:
            if e.key == pygame.K_BACKSPACE:
                self.search = self.search[:-1]
                self.page["Normal"] = self.page["Secret"] = 0
            return True
        key = "Perks" if page == "Perks" else self.ach_tab
        if e.type == pygame.MOUSEWHEEL:
            self.turn(key, -e.y)
            return True
        if e.type != pygame.MOUSEBUTTONDOWN or e.button != 1:
            return False
        pos = e.pos
        if self.back_rect().collidepoint(pos):
            self.g.set_page("Home", now)
            return True
        prev, nxt = self.pager()
        if prev.collidepoint(pos):
            self.turn(key, -1)
            return True
        if nxt.collidepoint(pos):
            self.turn(key, 1)
            return True
        if page == "Achievements":
            for name, r in self.ach_tabs():
                if r.collidepoint(pos):
                    self.ach_tab = name
                    self.g.sound.play("click", 0.4)
            if self.search and pygame.Rect(self.search_rect().right - 44, self.search_rect().y, 44, 42).collidepoint(pos):
                self.search = ""
                self.g.sound.play("click", 0.4)
            return True
        eng, p = self.g.engine, self.g.profile
        for i, r in enumerate(self.slot_rects()):
            if r.collidepoint(pos) and i < len(p.equipped):
                eng.toggle_equip(p.equipped[i])
                self.g.sound.play("click", 0.45)
                return True
        start = self.page["Perks"] * PER_PAGE
        for i, r in enumerate(self.card_rects()):
            idx = start + i
            if r.collidepoint(pos) and idx < len(perks.PERKS):
                if idx in p.perks_owned and eng.toggle_equip(idx):
                    self.equip_flash = (idx, now)
                    self.g.sound.play("equip", 0.6)
                else:
                    self.g.sound.play("bad", 0.25)
                return True
        if eng.can_sacrifice() and self.sacrifice_rect().collidepoint(pos):
            if now - self.sac_confirm > CONFIRM_SECONDS:
                self.sac_confirm = now
                self.g.sound.play("click", 0.5)
            else:
                self.sac_confirm = -10
                self.g.do_sacrifice(now)
        return True

    def turn(self, key, d):
        n = clamp(self.page[key] + d, 0, self.total_pages(key) - 1)
        if n != self.page[key]:
            self.page[key] = n
            self.g.sound.play("click", 0.35)

    # --- Drawing ---
    def draw(self, page, screen, now):
        e = ease_out(clamp((now - self.g.page_t) / 0.3, 0, 1))
        blur = page == "Perks" and self.hover is not None
        layer = screen if e >= 1 and not blur else pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        ui.label(layer, page, 44, (240, 18))
        top = None
        if page == "Perks":
            top = self.draw_perks(layer, now)
        else:
            self.draw_achievements(layer, now)
        ui.button(layer, self.back_rect(), "Back to the table", "orange", now, key="perk-back", size=17)
        if top is not None and layer is not screen:       # hovering an owned perk: blur the rest
            layer = ui.blur(layer, 4)
        if layer is not screen:
            if e < 1:
                layer.set_alpha(int(255 * e))
            screen.blit(layer, (0, int(24 * (1 - e))))
        if top is not None:
            idx, rect = top
            self.draw_perk_card(screen, idx, rect, now, hovered=True)

    def draw_perks(self, s, now):
        g, p = self.g, self.g.profile
        mouse = pygame.mouse.get_pos()
        held = len(p.perks_owned)
        ui.label(s, f"You own {held} perks (room for {p.perk_cap}).   Different perks found: "
                    f"{len(set(p.perks_owned))} of 100.", 17, (self.W // 2 - 80, 74), ui.MUTED, "center", bold=False)
        ui.label(s, "Get new perks by Shattering: the red ? in the Skill Tree, once every tree is maxed.", 15,
                 (self.W // 2 - 80, 96), ui.MUTED, "center", bold=False)
        for i, r in enumerate(self.slot_rects()):
            unlocked = i < p.perk_slots
            filled = i < len(p.equipped)
            if filled:
                idx = p.equipped[i]
                name = perks.PERKS[idx][0]
                ui.button(s, r, name, "purple", now, key=("slot", i), size=16 if len(name) < 16 else 13)
                pygame.draw.circle(s, ui.EDGE, (r.x + 14, r.y + 14), 7)
                pygame.draw.circle(s, perk_color(idx), (r.x + 14, r.y + 14), 5)
            else:
                body = ui.panel(s, r, ui.PANEL_IN if unlocked else (20, 23, 25), radius=12)
                if unlocked:
                    ui.label(s, "Empty slot", 15, body.center, ui.MUTED, "center")
                else:
                    big_padlock(s, body.centerx, body.centery, (80, 86, 90), 1.6)
        start = self.page["Perks"] * PER_PAGE
        top = None
        hovered = None
        for i, r in enumerate(self.card_rects()):
            idx = start + i
            if idx < len(perks.PERKS) and r.collidepoint(mouse) and idx in p.perks_owned:
                hovered = idx
        if hovered != self.hover:
            self.hover_t = now
            self.hover = hovered
        for i, r in enumerate(self.card_rects()):
            idx = start + i
            if idx >= len(perks.PERKS):
                break
            if idx == hovered:
                top = (idx, r)
                continue
            self.draw_perk_card(s, idx, r, now)
        prev, nxt = self.pager()
        pg, total = self.page["Perks"], self.total_pages("Perks")
        for rr, arrow, ok in ((prev, "<", pg > 0), (nxt, ">", pg < total - 1)):
            ui.button(s, rr, arrow, "blue", now, key=("perkpager", arrow), enabled=ok, size=24)
        ui.label(s, f"Page {pg + 1} of {total}", 18, (self.W // 2, prev.centery + 2), ui.MUTED, "center")
        ui.label(s, "Click a perk you own to equip it. Click it again (or its slot) to take it off.", 15,
                 (self.W // 2, 696), ui.MUTED, "center", bold=False)
        if g.engine.can_sacrifice():
            self.draw_sacrifice(s, now)
        return top

    def draw_perk_card(self, s, idx, rect, now, hovered=False):
        p = self.g.profile
        owned = idx in p.perks_owned
        equipped = idx in p.equipped
        r = rect.copy()
        lift = 0
        if hovered:
            k = ease_out(clamp((now - self.hover_t) / 0.25, 0, 1))
            lift = int(18 * k)
            r = r.inflate(int(26 * k), int(36 * k))
        r = r.move(0, -lift)
        if not hovered:
            k = ui.juice(("perkcard", idx), r.collidepoint(pygame.mouse.get_pos()), now)
            r = r.inflate(int(r.w * (k - 1)), int(r.h * (k - 1)))
        sh = art.shadow(r.size, 16, 170 if hovered else 120, 12 if hovered else 8)
        s.blit(sh, (r.x - 48 + 8, r.y - 48 + 14 + lift // 2))
        if not owned:                                      # locked: grey, padlock, nothing readable but its number
            body = ui.panel(s, r, (26, 28, 34), radius=18)
            for k in range(0, body.h, 14):
                pygame.draw.line(s, (32, 34, 41), (body.x + 10, body.y + k), (body.right - 10, body.y + k + 30), 2)
            big_padlock(s, body.centerx, body.centery, (96, 102, 112))
            ui.label(s, f"#{idx + 1}", 14, (body.x + 12, body.y + 8), (150, 154, 166))
            return
        col = perk_color(idx)
        body = ui.panel(s, r, art.mix((30, 34, 37), col, 0.35), radius=18)
        inner = body.inflate(-16, -16)
        pygame.draw.rect(s, (12, 13, 18), inner, border_radius=12)
        pygame.draw.rect(s, (0, 0, 0), inner, 2, border_radius=12)
        ui.label(s, f"#{idx + 1}", 14, (inner.x + 8, inner.y + 6), (190, 194, 206))
        if equipped:
            pygame.draw.rect(s, (255, 255, 255), body.inflate(-4, -4), 3, border_radius=16)
        flash = self.equip_flash[0] == idx and now - self.equip_flash[1] < 0.5
        if flash:
            k = 1 - (now - self.equip_flash[1]) / 0.5
            pygame.draw.rect(s, (255, 255, 255), r.inflate(int(16 * k), int(16 * k)), 2, border_radius=18)
        rnd = random.Random(idx)                          # each perk gets its own emblem
        cx, cy = inner.centerx, inner.y + 92
        for k in range(3):
            pygame.draw.circle(s, art.mix((22, 20, 30), col, 0.25 + 0.2 * k), (cx, cy), 52 - k * 14, 3)
        shape = rnd.choice(["hearts", "diamonds", "spades", "clubs"])
        art.suit(s, shape, cx, cy, 34, col)
        for _ in range(5):
            a = rnd.uniform(0, math.tau)
            pygame.draw.circle(s, col, (cx + math.cos(a) * 66, cy + math.sin(a) * 66), 3)
        name, desc, bad = perks.PERKS[idx]
        y = inner.y + 168
        for line in wrap(name, art.font(22, bold=True), inner.w - 20):
            ui.label(s, line, 22, (inner.centerx, y), anchor="midtop")
            y += 26
        copies = p.perks_owned.count(idx)
        tag = "Equipped" if equipped else f"Owned x{copies}" if copies > 1 else "Owned"
        ui.tag(s, tag, "buff" if equipped else "chips", (inner.centerx, y + 4), 13, "midtop")
        if bad:
            ui.tag(s, "Has a downside", "debuff", (inner.centerx, y + 32), 12, "midtop")
        if hovered:                                        # the description fades in under the name
            k = clamp((now - self.hover_t) / 0.35, 0, 1)
            box = pygame.Rect(r.x - 30, r.bottom + 12, r.w + 60, 0)
            lines = wrap(desc, art.font(16), box.w - 32)
            box.h = 26 + 22 * len(lines) + ui.LIP
            panel = pygame.Surface((box.w + 8, box.h + 8), pygame.SRCALPHA)
            ui.panel(panel, pygame.Rect(4, 4, box.w, box.h), radius=12)
            for i, line in enumerate(lines):
                ui.label(panel, line, 16, (20, 14 + i * 22), (230, 234, 236), bold=False)
            panel.set_alpha(int(255 * k))
            s.blit(panel, box.topleft)

    def draw_sacrifice(self, s, now):
        p = self.g.profile
        r = self.sacrifice_rect()
        confirming = now - self.sac_confirm < CONFIRM_SECONDS
        text = "Click again: everything resets, perks too" if confirming else \
            f"Sacrifice {p.perk_req} perks for another perk slot and a bigger perk inventory?"
        sub = f"Inventory {p.perk_cap} -> {p.perk_cap * 2}. The next one needs {p.perk_req * 2} perks."
        ui.button(s, r, text, "red", now, key="sacrifice", size=20, sub=sub, selected=confirming)

    # --- Achievements ---
    def ach_tabs(self):
        return [(n, pygame.Rect(70 + i * 220, 110, 206, 42)) for i, n in enumerate(("Normal", "Secret"))]

    def draw_achievements(self, s, now):
        p = self.g.profile
        for name, r in self.ach_tabs():
            on = self.ach_tab == name
            group = ach.NORMAL if name == "Normal" else ach.SECRET
            got = sum(1 for a in group if a[0] in p.achievements)
            ui.button(s, r, f"{name}  {got} / {len(group)}", ("gold" if name == "Normal" else "purple") if on else "dark",
                      now,
                      key=("achtab", name), size=18, selected=on)
        group = self.ach_list()
        secret = self.ach_tab == "Secret"
        self.draw_search(s, now)
        pg = min(self.page[self.ach_tab], self.total_pages("ach") - 1)
        self.page[self.ach_tab] = pg
        start = pg * ACH_PER_PAGE
        if not group:
            ui.label(s, f"No achievements match \"{self.search}\".", 20, (self.W // 2, 330), ui.MUTED, "center")
        for i, (name, desc, _chk, prog) in enumerate(group[start:start + ACH_PER_PAGE]):
            col, row = i % 2, i // 2
            r = pygame.Rect(70 + col * 740, 176 + row * 70, 720, 60)
            done = name in p.achievements
            if done:
                pulse = 0.5 + 0.5 * math.sin(now * 2 + i)
                glow = art.shadow(r.size, 14, int(60 + 40 * pulse), 6)
                tinted = glow.copy()
                tinted.fill((255, 200, 80, 255), special_flags=pygame.BLEND_RGBA_MULT)
                s.blit(tinted, (r.x - 24, r.y - 24))
            ui.panel(s, r.inflate(0, ui.LIP).move(0, ui.LIP // 2), (92, 72, 30) if done else ui.PANEL, radius=12)
            if done:
                pygame.draw.rect(s, GOLD, r.inflate(-2, -2), 2, border_radius=12)
            badge = pygame.Rect(r.x + 10, r.y + 6, 48, 48)
            hidden = secret and not done
            icon = None if hidden else art.asset(ach.icon_name(name), 50, None if done else (90, 92, 104))
            if icon is not None:                               # every achievement has its own icon (grey until done)
                s.blit(icon, icon.get_rect(center=badge.center))
                if not done:
                    art.padlock(s, badge.right - 6, badge.bottom - 6, (200, 200, 210))
            elif done:
                check(s, badge.inflate(-12, -12), GOLD, 4)
            else:
                pygame.draw.circle(s, (34, 32, 42), badge.center, 20)
                art.padlock(s, badge.centerx, badge.centery, (90, 86, 100))
            shown_name = "???" if hidden else name
            shown_desc = "???" if hidden else desc
            ui.label(s, shown_name, 18, (r.x + 64, r.y + 7), TEXT if done else (220, 224, 228))
            ui.label(s, shown_desc, 14, (r.x + 64, r.y + 33), (236, 222, 190) if done else ui.MUTED, bold=False)
            if prog and not done and not hidden:
                have, need = prog(p, p.ach)
                hb, nb = Big(have), Big(need)
                if nb <= 1e6:
                    frac = clamp(float(hb) / float(nb), 0, 1)
                else:
                    frac = clamp(hb.log10() / nb.log10(), 0, 1) if hb > 1 else 0
                bar = ui.inset(s, pygame.Rect(r.right - 200, r.y + 34, 180, 14), radius=7)
                fill = bar.inflate(-4, -4)
                fill.width = int(fill.width * frac)
                if fill.width > 4:
                    face, lip = ui.COLORS["blue"]
                    pygame.draw.rect(s, lip, fill, border_radius=5)
                    pygame.draw.rect(s, face, fill.inflate(0, -3).move(0, -1), border_radius=5)
                ui.label(s, f"{Big(have).fmt()} / {Big(need).fmt()}", 13, (bar.right, r.y + 10), ui.MUTED,
                         "topright", bold=False)
        prev, nxt = self.pager()
        total = self.total_pages("ach")
        for rr, arrow, ok in ((prev, "<", pg > 0), (nxt, ">", pg < total - 1)):
            ui.button(s, rr, arrow, "blue", now, key=("achpager", arrow), enabled=ok, size=24)
        ui.label(s, f"Page {pg + 1} of {total}", 18, (self.W // 2, prev.centery + 2), ui.MUTED, "center")

    def draw_search(self, s, now):
        r = self.search_rect()
        box = ui.inset(s, r, radius=12)
        icon = art.asset("Particles/eye", 22, (170, 176, 190))
        if icon is not None:
            s.blit(icon, icon.get_rect(center=(box.x + 22, box.centery)))
        if self.search:
            caret = "_" if int(now * 2) % 2 == 0 else " "
            ui.label(s, self.search + caret, 18, (box.x + 44, box.centery), anchor="midleft", bold=False)
            ui.label(s, "x", 20, (box.right - 22, box.centery), (230, 120, 120), "center")
            n = len(self.ach_list())
            ui.label(s, f"{n} found", 14, (box.x, box.bottom + 6), ui.MUTED, bold=False)
        else:
            ui.label(s, "Type to search achievements...", 17, (box.x + 44, box.centery), (120, 124, 136), "midleft",
                     bold=False, shadow=False)

    # --- Shatter window (opened from the red ? in the Skill Tree) ---
    def shatter_button(self):
        return pygame.Rect(self.W - 98, self.H - 150, 64, 64)

    def shatter_box(self):
        r = pygame.Rect(0, 0, 820, 360)
        r.center = (self.W // 2, self.H // 2)
        return r

    def shatter_go(self):
        b = self.shatter_box()
        return pygame.Rect(b.centerx - 130, b.bottom - 96, 260, 62)

    def draw_shatter_button(self, s, now):
        """The red question mark: a glowing ? with glass shards circling it (no ball behind it)."""
        r = self.shatter_button()
        ready = self.g.engine.can_shatter()
        hover = r.inflate(20, 20).collidepoint(pygame.mouse.get_pos())
        pulse = 0.5 + 0.5 * math.sin(now * (4 if ready else 2))
        glow = art.glow("glow", 120 + 30 * pulse + (20 if hover else 0), (255, 40, 50),
                        110 + 100 * pulse if ready else 72)
        if glow is not None:
            s.blit(glow, glow.get_rect(center=r.center), special_flags=pygame.BLEND_RGB_ADD)
        for k in range(5):                                  # shards orbiting the ?
            a = now * (1.2 if ready else 0.5) + k * math.tau / 5
            px, py = r.centerx + math.cos(a) * 40, r.centery + math.sin(a) * 26
            shard = art.asset(f"Particles/shard_{k % 3 + 1}", 16, (255, 120, 130) if ready else (150, 110, 118), 220)
            if shard is not None:
                s.blit(shard, shard.get_rect(center=(px, py)))
        size = int(56 + (6 if hover else 0) + 4 * pulse * ready)
        f = art.font(size, bold=True)
        wob = math.sin(now * 3) * (4 if ready else 1.5)
        q = pygame.transform.rotate(f.render("?", True, (255, 236, 236) if ready else (210, 170, 176)), wob)
        sh = pygame.transform.rotate(f.render("?", True, (70, 0, 10)), wob)
        s.blit(sh, sh.get_rect(center=(r.centerx + 3, r.centery + 4)))
        s.blit(q, q.get_rect(center=r.center))

    def open_shatter(self, now):
        self.shatter_open = True
        self.shatter_t = now
        self.g.sound.play("click", 0.5)

    def shatter_event(self, e, now):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.shatter_open = False
            return True
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.g.engine.can_shatter() and self.shatter_go().collidepoint(e.pos):
                self.shatter_open = False
                self.g.do_shatter(now)
            elif not self.shatter_box().collidepoint(e.pos):
                self.shatter_open = False
        return True

    def draw_shatter(self, screen, now):
        g, p = self.g, self.g.profile
        e = ease_out(clamp((now - self.shatter_t) / 0.3, 0, 1))
        dim = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, int(190 * e)))
        screen.blit(dim, (0, 0))
        b = self.shatter_box()
        k = ui.pop(now - self.shatter_t, 0.3)
        body = b.inflate(int(b.w * (k - 1)), int(b.h * (k - 1)))
        ui.panel(screen, body, (24, 12, 18), radius=24)
        glow = art.glow("glow", 640, (150, 20, 40), 160)
        if glow is not None:
            screen.blit(pygame.transform.smoothscale(glow, (body.w, body.h)), body.topleft,
                        special_flags=pygame.BLEND_RGB_ADD)
        rnd = random.Random(7)
        for i in range(12):                                  # glass shards drifting in the window
            x = body.x + 40 + (rnd.uniform(0, body.w - 80) + now * rnd.uniform(8, 24)) % (body.w - 80)
            y = body.y + 30 + (rnd.uniform(0, body.h - 60) + math.sin(now + i) * 10)
            sh = art.asset(f"Particles/shard_{i % 3 + 1}", rnd.randint(12, 24), (255, 140, 150), 90)
            if sh is not None:
                screen.blit(pygame.transform.rotate(sh, (now * 40 + i * 30) % 360), (x, y))
        if not g.engine.all_maxed():
            self.draw_shatter_locked(screen, body, now)
            return
        if len(p.perks_owned) >= p.perk_cap:
            ui.label(screen, "Your perk inventory is full. Sacrifice perks on the Perks page for a bigger one.", 20,
                     b.center, anchor="center")
            return
        # "Are you sure you want to SHATTER the tree for a permanent perk?" with SHATTER rainbow and shaking
        f = art.font(28, bold=True)
        parts = [("Are you sure you want to ", False), ("SHATTER", True), (" the tree", False)]
        width = sum(f.size(t)[0] for t, _ in parts)
        x = b.centerx - width // 2
        y = b.y + 80
        for text, rainbow in parts:
            if not rainbow:
                ui.label(screen, text, 28, (x, y))
                x += f.size(text)[0]
                continue
            for i, ch in enumerate(text):
                c = pygame.Color(0)
                c.hsva = ((i * 40 + now * 260) % 360, 80, 100, 100)
                jx = math.sin(now * 37 + i * 3) * 1.6
                jy = math.cos(now * 41 + i * 2) * 1.6
                ui.label(screen, ch, 28, (x + jx, y + jy), (c.r, c.g, c.b))
                x += f.size(ch)[0]
        ui.label(screen, "for a permanent perk?", 28, (b.centerx, y + 58), anchor="center")
        ui.label(screen, "Every tree, your chips, Transcendent Points and deck changes reset. Perks stay. "
                 "The perk is completely random.", 16, (b.centerx, y + 104), ui.MUTED, "center", bold=False)
        ui.button(screen, self.shatter_go(), "Shatter", "red", now, key="shatter-go", size=26)

    def draw_shatter_locked(self, screen, body, now):
        """Not ready yet: three rings that fill up as each tree gets maxed, and what Shattering will do."""
        p = self.g.profile
        ui.label(screen, "THE SHATTER", 34, (body.centerx, body.y + 40), (255, 120, 130), "center")
        ui.label(screen, "Max out every skill tree, then break it all for a permanent perk.", 17,
                 (body.centerx, body.y + 82), (220, 200, 206), "center", bold=False)
        parts = [("Main", len(p.bought) - 1, len(tree.NODES) - 1, (90, 220, 120)),
                 ("Decks", len(p.deck_bought) - 1, len(meta.DECK_NODES) - 1, (80, 150, 255)),
                 ("Transcend", len(p.t_bought) - 1, len(meta.T_NODES) - 1, (170, 100, 240))]
        for i, (name, have, need, col) in enumerate(parts):
            cx = body.centerx + (i - 1) * 230
            cy = body.y + 196
            frac = have / need if need else 1
            shown = frac * ease_out(clamp((now - self.shatter_t - i * 0.1) / 0.8, 0, 1))
            pygame.draw.circle(screen, (10, 8, 12), (cx, cy), 62)
            pygame.draw.circle(screen, (40, 34, 44), (cx, cy), 62, 10)
            if shown > 0:                                    # the filled part of the ring
                pts = [(cx + math.cos(-math.pi / 2 + a * math.tau * shown / 60) * 57,
                        cy + math.sin(-math.pi / 2 + a * math.tau * shown / 60) * 57) for a in range(61)]
                pygame.draw.lines(screen, col, False, pts, 10)
            ui.label(screen, f"{int(frac * 100)}%", 26, (cx, cy - 4), anchor="center")
            ui.label(screen, f"{have} / {need}", 14, (cx, cy + 22), ui.MUTED, "center", bold=False)
            ui.label(screen, name, 19, (cx, cy + 82), col, "center")
        ui.label(screen, "Click anywhere outside to close", 14, (body.centerx, body.bottom - 22), ui.MUTED, "center",
                 bold=False)

    # --- The perk reveal after a Shatter ---
    def draw_reveal(self, screen, now):
        idx, t0 = self.reveal
        t = now - t0
        dim = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, int(238 * clamp(t / 0.4, 0, 1))))
        screen.blit(dim, (0, 0))
        rnd = random.Random(int(t0))                      # glass shards flying out
        surf = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        for k in range(70):
            a = rnd.uniform(0, math.tau)
            sp = rnd.uniform(200, 900)
            d = sp * min(t, 1.6)
            x, y = self.W / 2 + math.cos(a) * d, self.H / 2 + math.sin(a) * d + 300 * min(t, 1.6) ** 2 * 0.3
            size = rnd.uniform(6, 18)
            alpha = int(255 * clamp(1 - t / 1.8, 0, 1))
            pts = [(x + math.cos(a + j * 2.1 + t * 3) * size, y + math.sin(a + j * 2.1 + t * 3) * size)
                   for j in range(3)]
            tint = (255, 255, 255) if k % 3 else (255, 110, 120)
            img = art.asset("shard", int(size * 2.4), tint)
            if img is None:
                pygame.draw.polygon(surf, (*tint, alpha), pts)
            else:
                spun = pygame.transform.rotate(img, (a * 57 + t * 220 * (1 if k % 2 else -1)) % 360)
                spun.set_alpha(alpha)
                surf.blit(spun, spun.get_rect(center=(x, y)))
        screen.blit(surf, (0, 0))
        if t > 0.6:
            k = ease_out(clamp((t - 0.6) / 0.5, 0, 1))
            r = pygame.Rect(0, 0, int(CARD_W * 1.2), int(CARD_H * 1.2))
            r.center = (self.W // 2, self.H // 2 - 20 + int(60 * (1 - k)))
            self.draw_perk_card(screen, idx, r, now)
            head = art.font(30, bold=True).render("A new perk", True, TEXT)
            head.set_alpha(int(255 * k))
            screen.blit(head, head.get_rect(center=(self.W // 2, r.y - 40)))
            for i, line in enumerate(wrap(perks.PERKS[idx][1], art.font(18), 620)):
                tt = art.font(18).render(line, True, (225, 220, 232))
                tt.set_alpha(int(255 * k))
                screen.blit(tt, tt.get_rect(center=(self.W // 2, r.bottom + 30 + i * 26)))
            hint = art.font(15).render("Click to continue. Equip it on the Perks page.", True, MUTED)
            hint.set_alpha(int(255 * k))
            screen.blit(hint, hint.get_rect(center=(self.W // 2, self.H - 50)))
