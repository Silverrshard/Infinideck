"""The Index, Deck and Stats pages."""
import math

import _art as art
import _ui as ui
import pygame
from _bignum import Big
from _cards import BUFFS, DEBUFFS, RANKS, SUITS, VALUE, Card, mod_info
from _engine import NEXT_RANK

# --- Settings ---
TEXT = (238, 234, 226)
MUTED = (150, 146, 160)
PANEL = (18, 17, 24)
PANEL_EDGE = (58, 52, 70)
PER_PAGE = 12
COLS = 6
CELL_W, CELL_H = 132, 206
GRID_X, GRID_Y = 70, 190
DETAIL = pygame.Rect(900, 172, 640, 672)
OP_START = 0.2                  # first price of a deck action: 0.2x your chips at that moment
OP_GROWTH = 1.2                 # then each one costs +0.2x more than the last
MIN_DECK = 8
SUIT_TEXT = {"hearts": (232, 70, 80), "diamonds": (245, 145, 50), "spades": (30, 28, 36), "clubs": (40, 140, 75)}


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


def card_of(entry):
    c = entry["card"]
    return Card(list(c["r"]), c["s"], list(c["b"]), list(c["d"]), c.get("c", False), c.get("u", False),
                entry.get("rarity", 1.0))


def stat_colors(n):
    """n clearly different colours: hues spread round the wheel, alternating brighter tints and deeper shades."""
    out = []
    for i in range(n):
        c = pygame.Color(0)
        c.hsva = ((i * 360 / n * 7) % 360, 72 if i % 2 else 58, 80 if i % 2 else 92, 100)
        out.append((c.r, c.g, c.b))
    return out


def ach_secret():
    import _achievements as ach
    return ach.SECRET_NAMES


def suit_word(surf, x, y, suit, size=18):
    """Suit names are written in their own colour (spades get a light backing so they stay readable)."""
    t = art.font(size, bold=True).render(suit.title(), True, SUIT_TEXT[suit])
    if suit == "spades":
        surf.blit(art.rounded((t.get_width() + 10, t.get_height() + 2), (210, 206, 214), 5), (x - 5, y - 1))
    surf.blit(t, (x, y))
    return t.get_width()


class Pages:
    def __init__(self, game):
        self.g = game
        self.W, self.H = game.screen.get_size()
        self.tab = {"Index": "Deck", "Deck": "Cards"}
        self.page_no = {}
        self.selected = {}
        self.info = False
        self.flash = (None, 0.0)
        self.tips = []                  # (rect, modifier) with a tooltip this frame

    # --- Shared bits ---
    def back_rect(self):
        return pygame.Rect(18, 18, 190, 44)          # where the menu button is on the table

    def tab_rects(self, page):
        names = ["Deck", "Recent", "Rarest", "Payouts"] if page == "Index" else []
        x = GRID_X
        return [(n, pygame.Rect(x + i * 150, 110, 140, 42)) for i, n in enumerate(names)]

    def items(self, page):
        p = self.g.profile
        if page == "Index":
            tab = self.tab["Index"]
            if tab == "Deck":
                return [("base", (r, s)) for s in SUITS for r in RANKS]
            if tab == "Recent":
                return [("entry", e) for e in p.recent]
            if tab == "Payouts":                            # the cards that paid the most, biggest first
                return [("entry", e) for e in p.payouts]
            return [("entry", e) for e in p.rarest]
        return [("deck", i) for i in range(len(p.deck))]

    def pages_count(self, page):
        return max(1, math.ceil(len(self.items(page)) / PER_PAGE))

    def key(self, page):
        return page + "/" + self.tab.get(page, "")

    def cell_rect(self, i):
        return pygame.Rect(GRID_X + (i % COLS) * CELL_W, GRID_Y + (i // COLS) * CELL_H, art.CARD_W, art.CARD_H)

    def pager_rects(self):
        return pygame.Rect(GRID_X, 640, 54, 44), pygame.Rect(GRID_X + 6 * CELL_W - 70, 640, 54, 44)

    # --- Input ---
    def handle(self, page, e, now):
        if page not in ("Index", "Deck", "Stats"):
            return False
        if e.type == pygame.MOUSEWHEEL and page != "Stats":
            self.turn(page, -e.y)
            return True
        if e.type != pygame.MOUSEBUTTONDOWN or e.button != 1:
            return False
        pos = e.pos
        if self.back_rect().collidepoint(pos):
            self.g.set_page("Home", now)
            return True
        if page == "Stats":
            return True
        for name, r in self.tab_rects(page):
            if r.collidepoint(pos):
                self.tab[page] = name
                self.info = False
                self.g.sound.play("click", 0.4)
                return True
        prev, nxt = self.pager_rects()
        if prev.collidepoint(pos):
            self.turn(page, -1)
            return True
        if nxt.collidepoint(pos):
            self.turn(page, 1)
            return True
        k = self.key(page)
        start = self.page_no.get(k, 0) * PER_PAGE
        for i, item in enumerate(self.items(page)[start:start + PER_PAGE]):
            if self.cell_rect(i).collidepoint(pos):
                self.selected[k] = start + i
                self.info = False
                self.g.sound.play("flip", 0.35)
                return True
        if page == "Deck":
            if self.banisher_ready():
                for su, r in self.banish_rects():
                    if r.collidepoint(pos):
                        p = self.g.profile
                        p.banished = None if p.banished == su else su
                        self.g.engine.refresh()
                        self.g.sound.play("click", 0.45)
                        return True
            self.deck_click(pos, now)
        return True

    def turn(self, page, d):
        k = self.key(page)
        n = clamp(self.page_no.get(k, 0) + d, 0, self.pages_count(page) - 1)
        if n != self.page_no.get(k, 0):
            self.page_no[k] = n
            self.g.sound.play("click", 0.35)

    # --- Drawing ---
    def draw(self, page, screen, now):
        e = ease_out(clamp((now - self.g.page_t) / 0.3, 0, 1))
        layer = screen if e >= 1 else pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        self.tips = []
        ui.label(layer, page, 44, (240, 18))
        if page == "Stats":
            self.draw_stats(layer, now)
        else:
            self.draw_grid(layer, page, now)
        ui.button(layer, self.back_rect(), "Back to the table", "orange", now, key="pages-back", size=17)
        if layer is not screen:
            layer.set_alpha(int(255 * e))
            screen.blit(layer, (0, int(24 * (1 - e))))
        else:
            self.draw_tips(screen)

    def draw_grid(self, s, page, now):
        p = self.g.profile
        mouse = pygame.mouse.get_pos()
        for name, r in self.tab_rects(page):
            on = self.tab[page] == name
            ui.button(s, r, name, "red" if on else "dark", now, key=("tab", page, name), size=18, selected=on)
        if page == "Deck":
            line = f"{len(p.deck)} cards in your deck. Pick one to duplicate it, raise its rank or delete it."
            ui.label(s, line, 17, (GRID_X, 120), ui.MUTED, bold=False)
            if self.banisher_ready():
                ui.label(s, "Suit Banisher:", 15, (GRID_X, 714))
                for su, r in self.banish_rects():
                    ui.button(s, r, su.title(), "red" if p.banished == su else "dark", now, key=("ban", su), size=15,
                              selected=p.banished == su)
        k = self.key(page)
        items = self.items(page)
        pg = self.page_no.get(k, 0)
        start = pg * PER_PAGE
        sel = self.selected.get(k)
        removed = self.removed_set() if page == "Deck" else set()
        if not items:
            ui.label(s, "Nothing here yet. Pull some cards!", 20, (GRID_X, GRID_Y + 40), ui.MUTED)
        for i, (kind, item) in enumerate(items[start:start + PER_PAGE]):
            r = self.cell_rect(i)
            hover = r.collidepoint(mouse)
            chosen = sel == start + i
            k = ui.juice(("cell", page, start + i), hover or chosen, now)
            lift = 10 if hover or chosen else 0
            img, label, label_kind, dim = self.cell(kind, item, removed)
            sh = art.shadow((art.CARD_W, art.CARD_H), art.RADIUS, 150, 8)
            s.blit(sh, (r.x - 32 + 6, r.y - 32 + 12))
            if dim:
                img = img.copy()
                img.fill((110, 110, 120, 255), special_flags=pygame.BLEND_RGBA_MULT)
            if k != 1.0 or hover:
                tilt = clamp((r.centerx - mouse[0]) * 0.08, -6, 6) if hover else 0
                img = pygame.transform.rotozoom(img, tilt, k)
            cr = img.get_rect(center=(r.centerx, r.centery - lift))
            if chosen:
                pygame.draw.rect(s, ui.EDGE, cr.inflate(14, 14), border_radius=art.RADIUS + 6)
                pygame.draw.rect(s, (255, 215, 120), cr.inflate(10, 10), 4, border_radius=art.RADIUS + 4)
            s.blit(img, cr)
            if label:
                ui.tag(s, label, label_kind, (r.centerx, r.bottom + 8), 13, "midtop")
        prev, nxt = self.pager_rects()
        for rr, arrow, ok in ((prev, "<", pg > 0), (nxt, ">", pg < self.pages_count(page) - 1)):
            ui.button(s, rr, arrow, "blue", now, key=("pager", page, arrow), enabled=ok, size=24)
        ui.label(s, f"Page {pg + 1} of {self.pages_count(page)}", 18, ((prev.centerx + nxt.centerx) // 2,
                                                                       prev.centery + 2), ui.MUTED, "center")
        if sel is not None and sel < len(items):
            self.draw_detail(s, page, items[sel], now)
        else:
            ui.panel(s, DETAIL, radius=20)
            ui.label(s, "Click a card to see it here.", 19, DETAIL.center, ui.MUTED, "center")

    def banisher_ready(self):
        g = self.g
        return "Suit Banisher" in g.engine.perks.on and (g.profile.balance >= 1e15 or g.profile.banished)

    def banish_rects(self):
        return [(su, pygame.Rect(GRID_X + 130 + i * 140, 706, 128, 36)) for i, su in enumerate(SUITS)]

    def removed_set(self):
        eng = self.g.engine
        gone = set()
        for rank, suits in eng.meta.removed:
            for su in suits:
                gone.add((rank, su))
        return gone

    def cell(self, kind, item, removed):
        p = self.g.profile
        if kind == "base":
            rank, suit = item
            key = f"{rank}|{suit}"
            if key not in p.index:
                return art.card_back(p.deck_style), "Not found yet", "debuff", True
            return art.card_face(Card([rank], suit)), Big.from_json(p.index[key]).fmt(), "chips", False
        if kind == "entry":
            card = card_of(item)
            if "Fog" in card.debuffs:                       # a ??? card: nothing shown but its rarity
                return art.card_face(card, hide=True), "???", "tp", False
            chips = Big.from_json(item["chips"])
            return art.card_face(card), chips.fmt(), "chips" if chips >= 0 else "debuff", False
        rank, suit = p.deck[item]
        gone = (rank, suit) in removed
        return art.card_face(Card([rank], suit)), "Removed" if gone else f"{VALUE[rank]} chips", \
            "debuff" if gone else "chips", gone

    # --- Detail panel (like a receipt: how the card's value was built) ---
    def draw_detail(self, s, page, item, now):
        p = self.g.profile
        kind, data = item
        box = DETAIL
        ui.panel(s, box, radius=20)
        x, y = box.x + 30, box.y + 28
        if kind == "base":
            rank, suit = data
            card = Card([rank], suit)
            best = p.index.get(f"{rank}|{suit}")
        elif kind == "entry":
            card = card_of(data)
            best = None
            if "Fog" in card.debuffs:
                self.draw_fog_detail(s, box, card, data)
                return
        else:
            rank, suit = p.deck[data]
            card = Card([rank], suit)
            best = p.index.get(f"{rank}|{suit}")
        big = pygame.transform.smoothscale(art.card_face(card), (int(art.CARD_W * 1.5), int(art.CARD_H * 1.5)))
        s.blit(art.shadow(big.get_size(), 14, 140, 10), (x - 40 + 6, y - 40 + 10))
        s.blit(big, (x, y))
        tx = x + big.get_width() + 30
        name = card.label()
        ui.label(s, name, 30, (tx, y))
        ui.label(s, "of", 18, (tx, y + 46), ui.MUTED, bold=False)
        suit_word(s, tx + 24, y + 44, card.suit, 20)
        ui.tag(s, f"Base value {card.base_value()}", "chips", (tx, y + 84), 15)
        if card.dup:
            ui.tag(s, "Duplicate", "tp", (tx, y + 114), 14)
        if kind in ("base", "deck"):
            line = f"Best payout: {Big.from_json(best).fmt()} chips" if best else "Not pulled yet"
            ui.label(s, line, 18, (tx, y + 150))
            if kind == "deck":
                self.draw_deck_actions(s, box, data, now)
            return
        chips = Big.from_json(data["chips"])
        hit = Big.from_json(data.get("hit", 0))
        ui.tag(s, ("+" if chips >= 0 else "") + chips.fmt() + " chips", "chips" if chips >= 0 else "debuff",
               (tx, y + 120), 18)
        if data.get("rarity", 1) < 1:
            n = 1 / max(data["rarity"], 1e-300)
            ui.tag(s, f"1 in {Big(round(n) if n < 1e15 else n).fmt()}", "buff", (tx, y + 158), 14)
        if hit > 0:
            ui.tag(s, f"-{hit.fmt()} from your balance", "debuff", (tx, y + 188), 14)
        y = box.y + 296
        ui.label(s, "How it added up", 19, (x, y))
        y += 34
        inner = ui.inset(s, pygame.Rect(x - 8, y - 6, box.w - 44, min(12, len(data.get("steps", []))) * 28 + 12))
        for label, text, k in data.get("steps", [])[:12]:
            r = ui.label(s, label, 16, (x + 4, y + 2), (220, 224, 228), bold=False)
            if label in BUFFS or label in DEBUFFS:
                self.tips.append((r.inflate(8, 6), label))
            ui.tag(s, text, k if k in art.TAG_COLORS else "chips", (inner.right - 12, y), 14, "topright")
            y += 28
        mods = card.buffs + card.debuffs
        if mods:
            y = box.bottom - 40
            xx = x
            ui.label(s, "Hover a modifier to see what it does", 13, (x, y - 24), ui.MUTED, bold=False)
            for m in mods:
                tg = art.tag(m, "buff" if m in BUFFS else "debuff", 13)
                if xx + tg.get_width() > box.right - 30:
                    break
                r = ui.tag(s, m, "buff" if m in BUFFS else "debuff", (xx, y), 13)
                self.tips.append((r.inflate(4, 6), m))
                xx += tg.get_width() + 8

    def draw_fog_detail(self, s, box, card, data):
        """A Fog card in the Index: only its rarity is shown."""
        x, y = box.x + 30, box.y + 28
        big = pygame.transform.smoothscale(art.card_face(card, hide=True), (int(art.CARD_W * 1.5), int(art.CARD_H * 1.5)))
        s.blit(art.shadow(big.get_size(), 14, 140, 10), (x - 40 + 6, y - 40 + 10))
        s.blit(big, (x, y))
        tx = x + big.get_width() + 30
        ui.label(s, "???", 34, (tx, y))
        ui.label(s, "Fog hid everything about this card.", 17, (tx, y + 52), ui.MUTED, bold=False)
        n = 1 / max(data.get("rarity", 1), 1e-300)
        ui.tag(s, f"1 in {Big(round(n) if n < 1e15 else n).fmt()}", "tp", (tx, y + 92), 18)
        ui.label(s, "Its chips still went into your balance.", 15, (tx, y + 134), ui.MUTED, bold=False)

    def draw_tips(self, s):
        """The hovered modifier's tooltip (in the detail panel or the 'How it added up' list)."""
        mouse = pygame.mouse.get_pos()
        for r, m in self.tips:
            if r.collidepoint(mouse):
                desc = mod_info(m)
                if not desc:
                    continue
                f = art.font(15)
                lines = wrap(desc, f, 340)
                w = 28 + max(f.size(line)[0] for line in lines)
                h = 46 + 22 * len(lines)
                px = min(mouse[0] + 16, self.W - w - 12)
                py = min(mouse[1] + 18, self.H - h - 12)
                body = ui.panel(s, pygame.Rect(px, py, w, h + ui.LIP), radius=12)
                ui.label(s, m, 17, (body.x + 14, body.y + 10), (140, 230, 150) if m in BUFFS else (240, 130, 130))
                for i, line in enumerate(lines):
                    ui.label(s, line, 15, (body.x + 14, body.y + 36 + i * 22), (226, 230, 232), bold=False)
                return

    # --- Deck actions ---
    def op_price(self, op):
        p = self.g.profile
        if op in p.op_cost:
            return Big.from_json(p.op_cost[op])
        return max(Big(100), p.balance * OP_START)

    def action_rects(self, box):
        y = box.y + 330
        return [(op, pygame.Rect(box.x + 30, y + i * 96, box.width - 60, 80))
                for i, op in enumerate(("duplicate", "raise", "delete"))]

    def info_rect(self, box):
        return pygame.Rect(box.right - 56, box.y + 22, 32, 32)

    def draw_deck_actions(self, s, box, idx, now):
        p = self.g.profile
        rank, suit = p.deck[idx]
        labels = {"duplicate": ("Duplicate", "Adds an exact copy of this card to your deck"),
                  "raise": ("Raise rank", f"Turns it into a {NEXT_RANK.get(rank, rank)}" if rank != "A"
                            else "Aces are already the highest rank"),
                  "delete": ("Delete", "Removes this card from your deck for good")}
        for op, r in self.action_rects(box):
            price = self.op_price(op)
            ok = p.balance >= price and not (op == "raise" and rank == "A") and \
                not (op == "delete" and len(p.deck) <= MIN_DECK)
            color = "red" if op == "delete" else "blue" if op == "duplicate" else "purple"
            name, desc = labels[op]
            ui.button(s, r, name, color, now, key=("op", op), enabled=ok, size=22, sub=desc)
            ui.tag(s, f"{price.fmt()} chips", "chips", (r.right - 14, r.y + 10), 14, "topright")
            if self.flash[0] == op and now - self.flash[1] < 0.4:
                k = 1 - (now - self.flash[1]) / 0.4
                pygame.draw.rect(s, (255, 255, 255), r.inflate(int(12 * k), int(12 * k)), 3, border_radius=14)
        note = "Each action's price is set the first time you use it, then rises 1.2x every use."
        ui.label(s, note, 14, (box.x + 30, box.bottom - 40), ui.MUTED, bold=False)
        ui.button(s, self.info_rect(box), "i", "blue", now, key="info-btn", size=20)
        if self.info:
            pop = pygame.Rect(box.right - 340, box.y + 66, 300, 96 + ui.LIP)
            ui.panel(s, pop, ui.COLORS["blue"][1], radius=12)
            lines = [f"{rank} of {suit.title()}", f"Base value: {VALUE[rank]} chips",
                     f"Copies in deck: {sum(1 for e in p.deck if e == [rank, suit])}"]
            for i, line in enumerate(lines):
                ui.label(s, line, 16, (pop.x + 16, pop.y + 12 + i * 26), bold=i == 0)

    def deck_click(self, pos, now):
        g, p = self.g, self.g.profile
        idx = self.selected.get(self.key("Deck"))
        if idx is None or idx >= len(p.deck):
            return
        box = DETAIL
        if self.info_rect(box).collidepoint(pos):
            self.info = not self.info
            g.sound.play("click", 0.4)
            return
        for op, r in self.action_rects(box):
            if not r.collidepoint(pos):
                continue
            price = self.op_price(op)
            rank, suit = p.deck[idx]
            if p.balance < price or (op == "raise" and rank == "A") or (op == "delete" and len(p.deck) <= MIN_DECK):
                g.sound.play("bad", 0.3)
                return
            p.balance = p.balance - price
            g.shown = g.shown - price
            p.op_cost[op] = (price * OP_GROWTH).to_json()
            if op == "duplicate":
                p.deck.insert(idx + 1, [rank, suit])
            elif op == "raise":
                p.deck[idx] = [NEXT_RANK[rank], suit]
            else:
                p.deck.pop(idx)
                self.selected[self.key("Deck")] = min(idx, len(p.deck) - 1)
            g.engine.refresh()
            self.flash = (op, now)
            g.sound.play("buy", 0.5)
            return

    # --- Stats ---
    def draw_stats(self, s, now):
        g, p = self.g, self.g.profile
        eng = g.engine
        import _meta as meta
        import _tree as tree
        avg = p.lifetime / p.cards if p.cards else Big(0)
        hours = p.playtime / 3600
        play = f"{int(hours)}h {int(p.playtime % 3600 // 60)}m"
        records = [("Highest card payout", p.best_card.fmt()),
                   ("Longest same-rank streak", f"{p.longest_streak:,}"),
                   ("Longest run with no debuffs", f"{p.longest_clean:,}"),
                   ("Highest chip balance", p.highest.fmt())]
        tp_big = Big(p.tp).fmt() if p.tp >= 1e6 else f"{p.tp:,}"
        tp_total = Big(p.tp_total).fmt() if p.tp_total >= 1e6 else f"{p.tp_total:,}"
        import _achievements as ach_mod
        import _perks as perks_mod
        rows = [
            ("Chips you have now", p.balance.fmt(), p.balance.exact() if 1e6 <= p.balance < 1e15 else ""),
            ("Chips earned in total", p.lifetime.fmt(), ""),
            ("Cards pulled", f"{p.cards:,}", ""),
            ("Average chips per card", avg.fmt(), ""),
            ("Critical hits", f"{p.crits:,}", ""),
            ("Times a modifier did something", f"{p.mod_hits:,}", ""),
            ("Duplicate cards", f"{p.dups:,}", ""),
            ("Cards that went up a rank", f"{p.rank_ups:,}", ""),
            ("Time played", play, ""),
            ("Transcends", f"{p.transcends:,}", ""),
            ("Transcendent Points", f"{tp_big} now / {tp_total} earned", ""),
            ("Main upgrades bought", f"{len(p.bought) - 1} / {len(tree.NODES) - 1}", ""),
            ("Deck upgrades bought", f"{len(p.deck_bought) - 1} / {len(meta.DECK_NODES) - 1}", ""),
            ("Transcend upgrades bought", f"{len(p.t_bought) - 1} / {len(meta.T_NODES) - 1}", ""),
            ("Cards found for the Index", f"{len(p.index_base())} / 52", ""),
            ("Cards in your deck", f"{len(p.deck)} ({len(eng.deck)} after removals)", ""),
            ("Different perks found", f"{len(set(p.perks_owned))} / {len(perks_mod.PERKS)}", ""),
            ("Shatters", f"{p.shatters:,}", ""),
            ("Achievements", f"{sum(1 for n in p.achievements if n not in ach_secret())} / {len(ach_mod.NORMAL)}",
             ""),
            ("Secret achievements", f"{sum(1 for n in p.achievements if n in ach_secret())} / {len(ach_mod.SECRET)}",
             ""),
        ]
        colors = stat_colors(len(records) + len(rows))           # every stat gets its own colour
        for i, (name, val) in enumerate(records):
            r = pygame.Rect(GRID_X + i * 352, 168, 330, 104)
            ui.panel(s, r, radius=18)
            ui.label(s, name, 16, (r.x + 20, r.y + 16), ui.MUTED)
            ui.tag(s, val, colors[i], (r.x + 20, r.y + 48), 26)
        half = (len(rows) + 1) // 2
        for i, (name, val, extra) in enumerate(rows):
            col, row = divmod(i, half)
            x, y = GRID_X + col * 720, 300 + row * 52
            r = pygame.Rect(x, y, 690, 44)
            ui.inset(s, r, radius=12)
            ui.label(s, name, 18, (r.x + 18, r.centery), (226, 230, 232), "midleft", bold=False)
            tg = ui.tag(s, val, colors[len(records) + i], (r.right - 16, r.centery - 2), 16, "midright")
            if extra:
                ex = art.font(13, mono=True).render(extra, True, MUTED)
                s.blit(ex, (tg.x - 12 - ex.get_width(), r.centery - 8))
