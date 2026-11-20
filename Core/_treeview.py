"""The Skill Tree screen: an Obsidian-style node graph with Main, Decks and Transcend tabs. Drag to pan, scroll to
zoom, hover to lift a node out of a blurred tree, click to buy."""
import math
import random

import _art as art
import _meta as meta
import _tree as tree
import _ui as ui
import pygame
import pygame.gfxdraw
from _bignum import Big
from _explain import explain

# --- Settings ---
TABS = ["Main", "Decks", "Transcend"]
ZOOM_MIN, ZOOM_MAX = 0.18, 2.6
TEXT = (238, 234, 226)
MUTED = (150, 146, 160)
LOCKED = (44, 42, 54)
EDGE_LOCKED = (34, 33, 44)
PANEL = (18, 17, 24)
PANEL_EDGE = (58, 52, 70)
TP_PURPLE = (150, 80, 220)
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


class Burst:
    def __init__(self, x, y, color, now):
        self.x, self.y, self.color, self.t0 = x, y, color, now
        self.sparks = [(random.uniform(0, math.tau), random.uniform(60, 190), random.uniform(2, 4))
                       for _ in range(18)]


class TreeView:
    def __init__(self, game):
        self.g = game
        self.W, self.H = game.screen.get_size()
        self.tab = "Main"
        self.cams = {"Main": [0.0, 0.0, 0.85], "Decks": [0.0, 0.0, 0.95], "Transcend": [0.0, 0.0, 1.0]}
        self.zoom_target = {k: v[2] for k, v in self.cams.items()}
        self.open_t = 0.0
        self.tab_t = 0.0
        self.hover = None
        self.hover_lift = 0.0
        self.blur_k = 0.0
        self.last_hover = None
        self.drag_from = None
        self.dragging = False
        self.bursts = []
        self.shake = (None, 0.0)
        self.confirm_t = -10.0
        self.picker = False
        self.picker_t = 0.0
        self.max_r = {"Main": tree.MAX_R, "Decks": max(n.r for n in meta.DECK_NODES.values()),
                      "Transcend": max(n.r for n in meta.T_NODES.values())}
        self.label_cache = {}
        self.flash_all = (-10.0, 0)     # Buy All: (time, how many it bought)
        self.blur_cache = None
        self.blur_frame = 0

    # --- Data for the current tab ---
    def nodes(self, tab=None):
        tab = tab or self.tab
        p = self.g.profile
        if tab == "Main":
            return tree.NODES, p.bought
        if tab == "Decks":
            return meta.DECK_NODES, p.deck_bought
        return meta.T_NODES, p.t_bought

    def describe(self, n):
        return explain(self.tab, n, self.g.profile)

    def path_name(self, n):
        if n.path < 0:
            return ""
        if self.tab == "Main":
            return tree.PATHS[n.path][1]
        if self.tab == "Decks":
            return meta.DECKS[n.path][1]
        return meta.T_PATHS[n.path][1]

    def color(self, n):
        if self.tab == "Decks" and n.style:
            _base, light, *_ = art.DECK_STYLES[n.style]
            c = light or (230, 120, 220)
            return c if sum(c) > 200 else art.mix(c, (255, 255, 255), 0.4)
        return tree.depth_color(n.r * tree.MAX_R / self.max_r[self.tab])

    # --- Camera ---
    def to_screen(self, x, y):
        cx, cy, z = self.cams[self.tab]
        return self.W / 2 + (x - cx) * z, self.H / 2 + (y - cy) * z

    def to_world(self, sx, sy):
        cx, cy, z = self.cams[self.tab]
        return cx + (sx - self.W / 2) / z, cy + (sy - self.H / 2) / z

    def node_size(self, n):
        """Node radius on screen: shrinks with the zoom, so zoomed-out paths stay apart instead of merging."""
        z = self.cams[self.tab][2]
        base = 26 if n.kind == "root" else 19 if n.kind == "first" else 10
        k = 0.12 + 0.88 * z if z < 1 else 0.55 + 0.45 * z
        return max(1.6, base * k)

    def open(self, now):
        self.open_t = now
        self.picker = False

    # --- Input ---
    def tab_rects(self):
        out = []
        x = self.W // 2 - 3 * 150 // 2
        for i, name in enumerate(TABS):
            out.append((name, pygame.Rect(x + i * 150, 22, 140, 44)))
        return out

    def back_rect(self):
        return pygame.Rect(18, 18, 190, 44)          # where the menu button is on the table

    def transcend_rect(self):
        return pygame.Rect(self.W // 2 - 220, self.H - 92, 440, 64)

    def buy_all_rect(self):
        return pygame.Rect(self.W // 2 - 150, self.H - 86, 300, 56)

    def buy_all_ready(self):
        m = self.g.engine.meta
        return (self.tab == "Main" and m.buy_all) or (self.tab == "Decks" and m.buy_all_decks)

    def buy_all(self, now):
        g = self.g
        nodes, _ = self.nodes()
        got = g.engine.buy_all(nodes)
        if got:
            g.sound.play("buy", 0.7)
            g.on_purchase(None)
            g.profile.ach["buy_all_used"] = True
            self.flash_all = (now, got)
        else:
            g.sound.play("bad", 0.25)

    def handle(self, e, now):
        """Returns True when the event was used here."""
        if self.picker:
            return self.picker_event(e, now)
        if e.type == pygame.MOUSEWHEEL:
            cam = self.cams[self.tab]
            mx, my = pygame.mouse.get_pos()
            wx, wy = self.to_world(mx, my)
            cam[2] = clamp(cam[2] * (1.15 ** e.y), ZOOM_MIN, ZOOM_MAX)
            nx, ny = self.to_world(mx, my)              # zoom toward the mouse
            cam[0] += wx - nx
            cam[1] += wy - ny
            return True
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for name, r in self.tab_rects():
                if r.collidepoint(e.pos):
                    if name != self.tab:
                        self.tab = name
                        self.tab_t = now
                        self.g.sound.play("click", 0.45)
                    return True
            if self.back_rect().collidepoint(e.pos):
                self.g.set_page("Home", now)
                return True
            if self.tab == "Transcend" and self.transcend_rect().collidepoint(e.pos):
                self.try_transcend(now)
                return True
            if self.buy_all_ready() and self.buy_all_rect().collidepoint(e.pos):
                self.buy_all(now)
                return True
            self.drag_from = (e.pos, list(self.cams[self.tab][:2]))
            self.dragging = False
            return True
        if e.type == pygame.MOUSEMOTION and self.drag_from and e.buttons[0]:
            (sx, sy), (cx, cy) = self.drag_from
            dx, dy = e.pos[0] - sx, e.pos[1] - sy
            if self.dragging or abs(dx) + abs(dy) > 5:
                self.dragging = True
                z = self.cams[self.tab][2]
                self.cams[self.tab][0] = cx - dx / z
                self.cams[self.tab][1] = cy - dy / z
            return True
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1 and self.drag_from:
            was_drag = self.dragging
            self.drag_from, self.dragging = None, False
            if not was_drag and self.hover:
                self.click_node(self.hover, now)
            return True
        return False

    def click_node(self, nid, now):
        g = self.g
        nodes, bought = self.nodes()
        n = nodes[nid]
        if nid in bought:
            if self.tab == "Decks" and n.style and (n.kind in ("first", "root")):
                g.profile.deck_style = n.style
                g.sound.play("click", 0.5)
                self.add_burst(n, now)
            elif self.tab == "Transcend" and n.path == 0 and n.kind != "root":
                g.profile.removal_on ^= {nid}
                g.engine.refresh()
                g.sound.play("click", 0.5)
            elif self.tab == "Transcend" and n.path == 2:
                self.picker = True
                self.picker_t = now
                g.sound.play("click", 0.5)
            return
        if g.engine.buy(nid):
            g.sound.play("buy", 0.6)
            self.add_burst(n, now)
            g.on_purchase(nid)
        else:
            self.shake = (nid, now)
            g.sound.play("bad", 0.25)

    def add_burst(self, n, now):
        self.bursts.append(Burst(n.x, n.y, self.color(n), now))

    def try_transcend(self, now):
        g = self.g
        base, _gain = g.engine.transcend_points()
        if not base:
            g.sound.play("bad", 0.25)
            return
        if now - self.confirm_t > CONFIRM_SECONDS:
            self.confirm_t = now
            g.sound.play("click", 0.5)
            return
        self.confirm_t = -10
        g.do_transcend(now)

    # --- Starting upgrade picker ---
    def picker_options(self):
        p = self.g.profile
        ok = set(p.start_picks) | {"root"}
        opts = [nid for nid, n in tree.NODES.items()
                if nid not in ok and all(par in ok for par in n.parents)]
        opts.sort(key=lambda nid: (tree.NODES[nid].path, tree.NODES[nid].k))
        return opts

    def picker_layout(self):
        panel = pygame.Rect(0, 0, 1040, 700)
        panel.center = (self.W // 2, self.H // 2 + 10)
        p = self.g.profile
        rows = []
        y = panel.y + 120
        for i, nid in enumerate(p.start_picks):
            r = pygame.Rect(panel.x + 30 + (i % 4) * 248, y + (i // 4) * 46, 236, 38)
            rows.append(("pick", nid, r))
        y += max(1, math.ceil(len(p.start_picks) / 4)) * 46 + 50
        for i, nid in enumerate(self.picker_options()[:24]):
            r = pygame.Rect(panel.x + 30 + (i % 4) * 248, y + (i // 4) * 46, 236, 38)
            rows.append(("opt", nid, r))
        close = pygame.Rect(panel.right - 150, panel.bottom - 62, 120, 40)
        return panel, rows, close, y

    def picker_event(self, e, now):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            panel, rows, close, _y = self.picker_layout()
            p = self.g.profile
            slots = self.g.engine.meta.start_slots
            if close.collidepoint(e.pos) or not panel.collidepoint(e.pos):
                self.picker = False
                self.g.sound.play("click", 0.4)
                return True
            for kind, nid, r in rows:
                if r.collidepoint(e.pos):
                    if kind == "pick":
                        keep = [x for x in p.start_picks if x != nid]
                        p.start_picks = [x for x in keep if x in meta.valid_start(keep)]
                        self.g.sound.play("click", 0.4)
                    elif len(p.start_picks) < slots:
                        p.start_picks.append(nid)
                        self.g.sound.play("buy", 0.5)
                    else:
                        self.g.sound.play("bad", 0.25)
                    return True
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.picker = False
            return True
        return True

    def draw_picker(self, screen, now):
        e = ease_out(clamp((now - self.picker_t) / 0.25, 0, 1))
        dim = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, int(170 * e)))
        screen.blit(dim, (0, 0))
        panel, rows, close, opt_y = self.picker_layout()
        panel = panel.move(0, int(30 * (1 - e)))
        ui.panel(screen, panel.inflate(0, ui.LIP).move(0, ui.LIP // 2), radius=22)
        p = self.g.profile
        slots = self.g.engine.meta.start_slots
        ui.label(screen, "Starting upgrades", 30, (panel.x + 30, panel.y + 24))
        sub = (f"{len(p.start_picks)} of {slots} chosen. These Main tree upgrades are free at the start of every run. "
               "An upgrade needs the ones before it picked too.")
        ui.label(screen, sub, 16, (panel.x + 30, panel.y + 70), ui.MUTED, bold=False)
        mouse = pygame.mouse.get_pos()
        if not p.start_picks:
            ui.label(screen, "Nothing chosen yet.", 16, (panel.x + 30, panel.y + 124), ui.MUTED, bold=False)
        ui.label(screen, "Add one", 18, (panel.x + 30, opt_y - 34))
        for kind, nid, r in rows:
            r = r.move(0, int(30 * (1 - e)))
            n = tree.NODES[nid]
            ui.button(screen, r.inflate(-4, -8), n.title, "purple" if kind == "pick" else "dark", now,
                      key=("pick", kind, nid), size=15)
            pygame.draw.circle(screen, ui.EDGE, (r.x + 16, r.centery - 2), 7)
            pygame.draw.circle(screen, tree.depth_color(n.r), (r.x + 16, r.centery - 2), 5)
        if hover_n := next((nid for _k, nid, r in rows if r.collidepoint(mouse)), None):
            ui.label(screen, tree.describe(tree.NODES[hover_n]), 15, (panel.x + 30, panel.bottom - 54), bold=False)
        ui.button(screen, close, "Done", "red", now, key="picker-done", size=18)

    # --- Update and drawing ---
    def update(self, dt, now):
        nodes, _ = self.nodes()
        mx, my = pygame.mouse.get_pos()
        self.hover = None
        if not self.picker and not self.dragging and my > 80:
            best, best_d = None, 1e9
            for nid, n in nodes.items():
                sx, sy = self.to_screen(n.x, n.y)
                d = math.hypot(sx - mx, sy - my)
                if d < max(12, self.node_size(n) + 6) and d < best_d:
                    best, best_d = nid, d
            self.hover = best
        if self.hover != self.last_hover:
            self.hover_lift = 0.0
            if self.hover:
                self.g.sound.play("tick", 0.12)
            self.last_hover = self.hover
        self.hover_lift = min(1.0, self.hover_lift + dt * 6)
        target = 1.0 if self.hover else 0.0               # the blur fades in and out instead of popping
        self.blur_k += (target - self.blur_k) * min(1.0, dt * 7)
        self.bursts = [b for b in self.bursts if now - b.t0 < 1.0]

    def draw(self, screen, now):
        nodes, bought = self.nodes()
        eng = self.g.engine
        W, H = self.W, self.H
        z = self.cams[self.tab][2]
        open_e = ease_out(clamp((now - max(self.open_t, self.tab_t)) / 0.35, 0, 1))
        direct = open_e >= 1 and self.blur_k < 0.01        # no fade or blur: draw straight onto the screen
        layer = screen if direct else pygame.Surface((W, H), pygame.SRCALPHA)
        # edges
        for nid, n in nodes.items():
            a = self.to_screen(n.x, n.y)
            for cid in n.children:
                c = nodes[cid]
                b = self.to_screen(c.x, c.y)
                if max(a[0], b[0]) < -20 or min(a[0], b[0]) > W + 20 or max(a[1], b[1]) < -20 or \
                        min(a[1], b[1]) > H + 20:
                    continue
                if cid in bought:
                    col, width = self.color(c), max(1, int(3 * z))
                elif nid in bought:
                    col, width = art.mix((10, 10, 14), self.color(c), 0.45), max(1, int(2 * z))
                else:
                    col, width = EDGE_LOCKED, 1
                pygame.draw.line(layer, col, a, b, width)
        # nodes
        pulse = 0.5 + 0.5 * math.sin(now * 4)
        for nid, n in nodes.items():
            if nid == self.hover:
                continue
            self.draw_node(layer, n, nid, bought, eng, now, pulse)
        # labels for path starts (always) and every node when zoomed in
        for nid, n in nodes.items():
            if (n.kind in ("first", "root") and z > 0.6) or z > 1.25 or n.kind == "root":
                sx, sy = self.to_screen(n.x, n.y)
                if -100 < sx < W + 100 and -40 < sy < H + 40:
                    text = n.title if n.kind != "first" else self.path_name(n) or n.title
                    lab = self.label(text, 13 if n.kind not in ("first", "root") else 15,
                                     nid in bought or meta.available(nodes, nid, bought))
                    layer.blit(lab, lab.get_rect(midtop=(sx, sy + self.node_size(n) + 5)))
        # purchase bursts
        for b in self.bursts:
            t = (now - b.t0) / 1.0
            sx, sy = self.to_screen(b.x, b.y)
            rad = int(10 + 70 * ease_out(t) * (0.6 + 0.4 * z))
            alpha = int(255 * (1 - t))
            pygame.gfxdraw.aacircle(layer, int(sx), int(sy), rad, (*b.color, alpha))
            pygame.gfxdraw.aacircle(layer, int(sx), int(sy), max(1, rad - 2), (*b.color, alpha // 2))
            for ang, speed, size in b.sparks:
                d = speed * ease_out(t) * (0.6 + 0.4 * z)
                pygame.draw.circle(layer, (*b.color, alpha), (sx + math.cos(ang) * d, sy + math.sin(ang) * d),
                                   max(1, int(size * (1 - t))))
        if open_e < 1:                                    # opening / tab switch: grow in and fade in
            s = 0.92 + 0.08 * open_e
            scaled = pygame.transform.smoothscale(layer, (int(W * s), int(H * s)))
            scaled.set_alpha(int(255 * open_e))
            layer = pygame.Surface((W, H), pygame.SRCALPHA)
            layer.blit(scaled, scaled.get_rect(center=(W // 2, H // 2)))
        if self.blur_k > 0.01:                            # blur everything but the hovered node, fading in
            self.blur_frame += 1                           # a smooth blur (no blocky pixels), made every other frame
            if self.blur_cache is None or self.blur_frame % 2:
                self.blur_cache = ui.blur(layer, 4)
            blurred = self.blur_cache
            if self.blur_k < 0.99:                        # cross-fade: the sharp tree fades as the blur comes in
                layer.set_alpha(int(255 * (1 - self.blur_k)))
                screen.blit(layer, (0, 0))
                layer.set_alpha(None)
                blurred.set_alpha(int(255 * self.blur_k))
            screen.blit(blurred, (0, 0))
            if self.hover:
                self.draw_hovered(screen, nodes[self.hover], self.hover, bought, eng, now)
        elif layer is not screen:
            screen.blit(layer, (0, 0))
        self.draw_chrome(screen, now)
        if self.hover:
            self.draw_tooltip(screen, nodes[self.hover], self.hover, bought, now)
        if self.picker:
            self.draw_picker(screen, now)

    def label(self, text, size, lit):
        key = (text, size, lit)
        if key not in self.label_cache:
            if len(self.label_cache) > 1500:
                self.label_cache.clear()
            self.label_cache[key] = art.font(size, bold=size > 13).render(text, True, TEXT if lit else (110, 106, 120))
        return self.label_cache[key]

    def node_state(self, nid, bought, eng):
        nodes, _ = self.nodes()
        if nid in bought:
            return "owned"
        if meta.available(nodes, nid, bought):
            return "ready" if eng.can_afford(nid) else "open"
        return "locked"

    def draw_node(self, surf, n, nid, bought, eng, now, pulse, scale=1.0, lift=0.0):
        sx, sy = self.to_screen(n.x, n.y)
        r = self.node_size(n) * scale
        if sx < -r - 30 or sx > self.W + r + 30 or sy < -r - 30 or sy > self.H + r + 30:
            return
        sy -= lift
        if self.shake[0] == nid and now - self.shake[1] < 0.35:
            sx += math.sin((now - self.shake[1]) * 70) * 5 * (1 - (now - self.shake[1]) / 0.35)
        state = self.node_state(nid, bought, eng)
        col = self.color(n)
        x, y, ri = int(sx), int(sy), max(2, int(r))
        if self.tab == "Decks" and n.kind in ("first", "root") and n.style:
            back = art.card_back(n.style)
            w = int(ri * 1.9)
            img = pygame.transform.smoothscale(back, (w, int(w * art.CARD_H / art.CARD_W)))
            if state != "owned":
                img = img.copy()
                img.fill((90, 90, 100, 255) if state == "locked" else (170, 170, 180, 255),
                         special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(img, img.get_rect(center=(x, y)))
            if self.g.profile.deck_style == n.style and state == "owned":
                rect = img.get_rect(center=(x, y)).inflate(8, 8)
                pygame.draw.rect(surf, (255, 225, 120), rect, 2, border_radius=8)
            elif state == "ready":
                rect = img.get_rect(center=(x, y)).inflate(6 + 4 * pulse, 6 + 4 * pulse)
                pygame.draw.rect(surf, col, rect, 2, border_radius=8)
            return
        if state == "owned":
            glow = max(4, int(ri * 2.2))
            pygame.gfxdraw.filled_circle(surf, x, y, glow, (*col, 26))
            pygame.gfxdraw.filled_circle(surf, x, y, ri, col)
            pygame.gfxdraw.aacircle(surf, x, y, ri, col)
            if self.tab == "Transcend" and n.path == 0 and nid not in self.g.profile.removal_on:
                pygame.gfxdraw.filled_circle(surf, x, y, max(1, ri - 3), (30, 28, 36))     # switched off
        elif state == "ready":
            pygame.gfxdraw.filled_circle(surf, x, y, int(ri * (1.8 + 0.5 * pulse)), (*col, 40))
            pygame.gfxdraw.filled_circle(surf, x, y, ri, (26, 24, 32))
            for k in range(2):
                pygame.gfxdraw.aacircle(surf, x, y, ri - k, col)
        elif state == "open":
            pygame.gfxdraw.filled_circle(surf, x, y, ri, (22, 21, 28))
            pygame.gfxdraw.aacircle(surf, x, y, ri, art.mix((20, 20, 26), col, 0.55))
        else:
            rl = max(2, int(ri * 0.7))
            pygame.gfxdraw.filled_circle(surf, x, y, rl, LOCKED)
            pygame.gfxdraw.aacircle(surf, x, y, rl, LOCKED)
        if n.kind in ("first", "root"):                   # the first upgrade of each path sits in a circle
            ring = ri + max(4, int(6 * self.cams[self.tab][2]))
            ring_col = col if state != "locked" else LOCKED
            pygame.gfxdraw.aacircle(surf, x, y, ring, ring_col)
            pygame.gfxdraw.aacircle(surf, x, y, ring + 1, ring_col)

    def draw_hovered(self, screen, n, nid, bought, eng, now):
        lift = 10 * ease_out(self.hover_lift)
        scale = 1 + 0.45 * ease_out(self.hover_lift)
        sx, sy = self.to_screen(n.x, n.y)
        r = self.node_size(n) * scale
        sh = art.shadow((int(r * 2), int(r * 2)), int(r), 150, 6)
        screen.blit(sh, sh.get_rect(center=(sx + 4, sy + 8)))
        nodes, _ = self.nodes()
        for cid in n.children + n.parents:              # its own links stay sharp
            c = nodes[cid]
            pygame.draw.line(screen, self.color(c) if cid in bought else (70, 66, 84), (sx, sy - lift),
                             self.to_screen(c.x, c.y), 2)
        self.draw_node(screen, n, nid, bought, eng, now, 1.0, scale, lift)

    def draw_tooltip(self, screen, n, nid, bought, now):
        g = self.g
        eng = g.engine
        state = self.node_state(nid, bought, eng)
        w = 460
        body = wrap(self.describe(n), art.font(16), w - 36)
        lines = 3 + len(body)
        h = 40 + lines * 26
        sx, sy = self.to_screen(n.x, n.y)
        x = clamp(int(sx) + 30, 12, self.W - w - 12)
        y = clamp(int(sy) - h // 2, 90, self.H - h - 12)
        if x < sx < x + w:
            x = clamp(int(sx) - w - 30, 12, self.W - w - 12)
        a = int(255 * ease_out(self.hover_lift))
        panel = pygame.Surface((w + 8, h + 8 + ui.LIP), pygame.SRCALPHA)
        ui.panel(panel, pygame.Rect(4, 4, w, h + ui.LIP), radius=14)
        cy = 18
        ui.label(panel, n.title, 22, (22, cy))
        cy += 32
        if self.path_name(n):
            ui.label(panel, self.path_name(n), 15, (22, cy), self.color(n))
            cy += 26
        for line in body:
            ui.label(panel, line, 16, (22, cy), (226, 230, 232), bold=False)
            cy += 24
        cy += 8
        if state == "owned":
            status = "Owned"
            if self.tab == "Decks" and n.style and n.kind in ("first", "root"):
                status = "In use" if g.profile.deck_style == n.style else "Owned: click to use this deck"
            elif self.tab == "Transcend" and n.path == 0 and n.kind != "root":
                status = "On: click to switch off" if nid in g.profile.removal_on else "Off: click to switch on"
            elif self.tab == "Transcend" and n.path == 2:
                status = "Owned: click to choose starting upgrades"
            ui.tag(panel, status, "buff", (22, cy), 15)
        else:
            cost = n.cost
            if n.cur == "tp":
                ui.tag(panel, f"{cost.fmt()} TP", "tp", (22, cy), 16)
                have = Big(g.profile.tp)
            else:
                panel.blit(art.casino_chip(24), (20, cy - 2))
                ui.tag(panel, f"{cost.fmt()} chips", "chips", (50, cy), 16)
                have = g.profile.balance
            if state == "locked":
                msg, col = "Buy the upgrade connected before it first", MUTED
            elif state == "ready":
                msg, col = "Click to buy", (140, 230, 150)
            else:
                msg, col = f"Need {(cost - have).fmt()} more", (240, 150, 140)
            ui.label(panel, msg, 15, (w - 14, cy + 2), col, "topright")
        panel.set_alpha(a)
        screen.blit(panel, (x, y + int(8 * (1 - ease_out(self.hover_lift)))))

    def draw_chrome(self, screen, now):
        colors = {"Main": "green", "Decks": "blue", "Transcend": "purple"}
        for name, r in self.tab_rects():
            on = name == self.tab
            ui.button(screen, r, name, colors[name] if on else "dark", now, key=("treetab", name), size=19,
                      selected=on)
        ui.button(screen, self.back_rect(), "Back to the table", "orange", now, key="tree-back", size=17)
        self.draw_summary(screen)
        if self.tab == "Transcend":
            self.draw_transcend_button(screen, now)
        elif self.buy_all_ready():
            nodes, bought = self.nodes()
            ready = sum(1 for nid in nodes if meta.available(nodes, nid, bought) and self.g.engine.can_afford(nid))
            ui.button(screen, self.buy_all_rect(), "Buy All", "green" if ready else "dark", now, key="buy-all",
                      size=24, sub=f"{ready} upgrade{'s' if ready != 1 else ''} ready" if ready else "Nothing affordable")
            t0, got = self.flash_all
            if now - t0 < 1.6:
                k = (now - t0) / 1.6
                ui.label(screen, f"Bought {got}!", 22, (self.W // 2, self.H - 110 - int(40 * k)), (140, 240, 160),
                         "center", alpha=int(255 * (1 - k)))
        ui.label(screen, "Drag to move, scroll to zoom", 14, (self.W - 20, self.H - 22), ui.MUTED, "midright",
                 bold=False)

    def draw_summary(self, screen):
        eng = self.g.engine
        st, m, p = eng.st, eng.meta, self.g.profile
        nodes, bought = self.nodes()
        rows = [("Upgrades", f"{len(bought) - 1} / {len(nodes) - 1}", "chips")]
        if self.tab == "Main":
            rows += [("Base chips", f"+{st.base_bonus.fmt()}", "chips"), ("Chip multiplier", f"x{st.chip_mult:.2f}", "mult"),
                     ("Pull speed", f"x{st.speed * m.speed_mult:.2f}", "buff"),
                     ("Buff chance", f"{(st.buff_chance + m.buff_add) * 100:.1f}%", "buff"),
                     ("Critical chance", f"{st.crit_chance * 100:.1f}%", "crit")]
        elif self.tab == "Decks":
            rows += [("All chips from decks", f"x{Big(m.deck_mult * m.value_mult * (1 + m.index_bonus)).fmt()}", "mult"),
                     ("Critical damage", f"x{2.5 + m.crit_dmg:g}", "crit"),
                     ("Debuff chance", f"-{(1 - m.debuff_scale) * 100:.0f}%", "buff")]
        else:
            rows += [("Points you have", f"{p.tp:,}" if p.tp < 1e6 else Big(p.tp).fmt(), "tp"),
                     ("Points per Transcend", f"x{m.tp_mult:.2f}", "mult"),
                     ("Chips from points", f"x{Big(m.tp_chip_mult).fmt()}", "mult"),
                     ("Free starting upgrades", f"{len(p.start_picks)} / {m.start_slots}", "buff"),
                     ("Double-rank card chance", f"{m.double * 100:.1f}%", "buff")]
        x, y = 26, self.H - 34 - len(rows) * 32
        box = pygame.Rect(x - 12, y - 14, 330, len(rows) * 32 + 22 + ui.LIP)
        ui.panel(screen, box, radius=16)
        for i, (name, val, kind) in enumerate(rows):
            ui.label(screen, name, 15, (x + 4, y + i * 32 + 4), (220, 224, 228), bold=False)
            ui.tag(screen, val, kind, (box.right - 16, y + i * 32 + 2), 14, "topright")

    def draw_transcend_button(self, screen, now):
        eng, p = self.g.engine, self.g.profile
        base, gain = eng.transcend_points()
        r = self.transcend_rect()
        confirming = now - self.confirm_t < CONFIRM_SECONDS
        if base:
            text = "Click again to Transcend" if confirming else \
                f"Transcend for +{gain:,} points" if gain < 1e9 else f"Transcend for +{Big(gain).fmt()} points"
            ui.button(screen, r, text, "red" if confirming else "purple", now, key="transcend", size=24,
                      sub="Resets chips and the Main tree. Keeps decks, Transcend upgrades and the Index.")
        else:
            body = ui.panel(screen, r, radius=18)
            need = meta.needed(p.tp_k)
            ui.label(screen, f"Earn {need.fmt()} chips this run to Transcend", 19, (r.centerx, body.centery - 9),
                     (220, 224, 228), "center")
            frac = clamp(p.run_earned.log10() / need.log10(), 0, 1) if p.run_earned > 0 else 0
            bar = ui.inset(screen, pygame.Rect(r.x + 30, body.bottom - 22, r.width - 60, 12), radius=6)
            fill = bar.inflate(-4, -4)
            fill.width = int(fill.width * frac)
            if fill.width > 4:
                pygame.draw.rect(screen, TP_PURPLE, fill, border_radius=4)
