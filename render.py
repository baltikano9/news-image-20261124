#!/usr/bin/env python3
"""Render entry.png: a one-page summary of the world news of Tuesday 24 November 2026.

Pillow only. Every illustration is drawn from simple shapes (no photos, no
external images). Run: python3 render.py  -> writes entry.png next to this file.

The script checks its own layout: every text block and illustration is
recorded, and rendering fails if any two overlap or anything is clipped.
"""
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W = H = 1024
SS = 2  # supersampling factor for illustrations

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
F_SERIF_B = os.path.join(FONT_DIR, "DejaVuSerif-Bold.ttf")
F_SANS_B = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
F_SANS = os.path.join(FONT_DIR, "DejaVuSans.ttf")
F_COND_B = os.path.join(FONT_DIR, "DejaVuSansCondensed-Bold.ttf")
F_COND = os.path.join(FONT_DIR, "DejaVuSansCondensed.ttf")

PAPER = (248, 244, 234)
INK = (20, 20, 24)
GREY = (58, 58, 66)
RED = (180, 24, 34)
RULE = (40, 40, 44)
HAIR = (180, 176, 166)
WHITE = (255, 255, 255)

_font_cache = {}
BOXES = []  # (label, (x0, y0, x1, y1)) for the layout self-check


_COND_FALLBACK = {F_COND_B: F_SANS_B, F_COND: F_SANS}


def font(path, size):
    key = (path, size)
    if key not in _font_cache:
        load = path
        if not os.path.exists(load) and load in _COND_FALLBACK:
            load = _COND_FALLBACK[load]
        _font_cache[key] = ImageFont.truetype(load, size)
    return _font_cache[key]


def line_h(fnt, leading):
    asc, desc = fnt.getmetrics()
    return int(round((asc + desc) * leading))


def wrap(text, fnt, width):
    lines, cur = [], ""
    for w in text.split():
        trial = (cur + " " + w).strip()
        if fnt.getlength(trial) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def try_fit(text, path, size, width, max_lines):
    f = font(path, size)
    lines = wrap(text, f, width)
    if len(lines) <= max_lines and all(f.getlength(l) <= width for l in lines):
        return f, lines
    return None


def fit_block(head, sub, width, budget, head_font, head_sizes, head_lines,
              head_lead, sub_font, sub_sizes, sub_lines, sub_lead, gap):
    """Pick the largest headline size (then sub size) whose block fits budget px."""
    for hs in head_sizes:
        h = try_fit(head, head_font, hs, width, head_lines)
        if not h:
            continue
        hh = len(h[1]) * line_h(h[0], head_lead)
        for ss in sub_sizes:
            s = try_fit(sub, sub_font, ss, width, sub_lines)
            if not s:
                continue
            sh = len(s[1]) * line_h(s[0], sub_lead)
            if hh + gap + sh <= budget:
                return h, s
    raise ValueError("block does not fit: %r" % head)


def text(d, xy, s, fnt, fill, label, anchor="la"):
    d.text(xy, s, font=fnt, fill=fill, anchor=anchor)
    BOXES.append((label, d.textbbox(xy, s, font=fnt, anchor=anchor)))


def draw_lines(d, x, y, lines, fnt, fill, leading, label):
    lh = line_h(fnt, leading)
    for ln in lines:
        text(d, (x, y), ln, fnt, fill, label)
        y += lh
    return y


def paste(img, art, xy, label):
    img.paste(art, xy)
    BOXES.append((label, (xy[0], xy[1], xy[0] + art.width, xy[1] + art.height)))


def check_layout():
    problems = []
    for lab, (x0, y0, x1, y1) in BOXES:
        if x0 < 0 or y0 < 0 or x1 > W or y1 > H:
            problems.append("clipped: %s %s" % (lab, (x0, y0, x1, y1)))
    for i in range(len(BOXES)):
        la, a = BOXES[i]
        for j in range(i + 1, len(BOXES)):
            lb, b = BOXES[j]
            if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                problems.append("overlap: %s %s <-> %s %s" % (la, a, lb, b))
    if problems:
        raise SystemExit("layout check failed:\n" + "\n".join(problems))


# ---------------------------------------------------------------------------
# Illustration canvas: draw in local units at SS x, then downsample.
# ---------------------------------------------------------------------------
class Pic:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.img = Image.new("RGB", (w * SS, h * SS), bg)
        self.d = ImageDraw.Draw(self.img)

    def _s(self, pts):
        return [v * SS for v in pts]

    def _flat(self, pts):
        out = []
        for x, y in pts:
            out += [x * SS, y * SS]
        return out

    def rect(self, x0, y0, x1, y1, fill, outline=None, width=0, r=0):
        if r:
            self.d.rounded_rectangle(self._s([x0, y0, x1, y1]), radius=r * SS,
                                     fill=fill, outline=outline, width=width * SS)
        else:
            self.d.rectangle(self._s([x0, y0, x1, y1]), fill=fill,
                             outline=outline, width=width * SS)

    def ellipse(self, x0, y0, x1, y1, fill, outline=None, width=0):
        self.d.ellipse(self._s([x0, y0, x1, y1]), fill=fill, outline=outline,
                       width=width * SS)

    def circle(self, cx, cy, r, fill, outline=None, width=0):
        self.ellipse(cx - r, cy - r, cx + r, cy + r, fill, outline, width)

    def poly(self, pts, fill):
        self.d.polygon(self._flat(pts), fill=fill)

    def line(self, pts, fill, width=1):
        self.d.line(self._flat(pts), fill=fill, width=int(width * SS), joint="curve")

    def pie(self, x0, y0, x1, y1, a0, a1, fill):
        self.d.pieslice(self._s([x0, y0, x1, y1]), a0, a1, fill=fill)

    def text(self, x, y, s, path, size, fill, anchor="la"):
        self.d.text((x * SS, y * SS), s, font=font(path, size * SS), fill=fill,
                    anchor=anchor)

    def out(self):
        return self.img.resize((self.w, self.h), Image.LANCZOS)


def person(p, cx, base, s, body, skin=(226, 186, 148), hair=(30, 30, 30)):
    """Generic stylised figure (no likeness): rounded torso and round head."""
    p.rect(cx - 34 * s, base - 70 * s, cx + 34 * s, base, body, r=int(18 * s))
    p.circle(cx, base - 92 * s, 24 * s, skin)
    p.pie(cx - 25 * s, base - 118 * s, cx + 25 * s, base - 80 * s, 180, 360, hair)


# ---- 1. LEAD  Nvidia: Huang back as CEO, shares about +31% -----------------
def ill_nvidia(w, h):
    p = Pic(w, h, (16, 24, 20))
    green = (118, 185, 0)
    for gx in range(20, w, 40):
        p.line([(gx, 16), (gx, h - 16)], (34, 48, 40), 1)
    for gy in range(16, h, 40):
        p.line([(16, gy), (w - 16, gy)], (34, 48, 40), 1)
    # share price chart: flat, then a jump
    pts = [(160, 196), (195, 186), (225, 192), (255, 170), (285, 176),
           (320, 96), (w - 40, 46)]
    p.poly(pts + [(w - 40, h - 16), (160, h - 16)], (36, 64, 20))
    p.line(pts, green, 6)
    ax, ay = w - 40, 46
    p.poly([(ax + 8, ay - 20), (ax + 18, ay + 16), (ax - 20, ay + 4)], green)
    # chip
    cx, cy = 84, 74
    for i in range(5):
        o = -36 + i * 18
        p.rect(cx + o - 3, cy - 58, cx + o + 3, cy - 44, (180, 180, 180))
        p.rect(cx + o - 3, cy + 44, cx + o + 3, cy + 58, (180, 180, 180))
        p.rect(cx - 58, cy + o - 3, cx - 44, cy + o + 3, (180, 180, 180))
        p.rect(cx + 44, cy + o - 3, cx + 58, cy + o + 3, (180, 180, 180))
    p.rect(cx - 46, cy - 46, cx + 46, cy + 46, (40, 40, 44), outline=green,
           width=3, r=8)
    p.text(cx, cy - 8, "GPU", F_SANS_B, 24, green, anchor="mm")
    p.text(cx, cy + 20, "NVIDIA", F_COND_B, 14, (225, 225, 225), anchor="mm")
    # figure back in the CEO chair, at a desk with a nameplate
    fx, fb, s = 112, h - 40, 0.8
    p.rect(fx - 44, fb - 100, fx + 44, fb - 14, (70, 70, 78), r=12)
    person(p, fx, fb, s, (24, 24, 28))
    p.rect(fx - 62, fb - 10, fx + 62, fb + 20, (232, 232, 222), r=4)
    p.text(fx, fb + 5, "CEO", F_SANS_B, 20, INK, anchor="mm")
    # +31% badge
    p.rect(w - 168, h - 76, w - 22, h - 22, green, r=10)
    p.text(w - 95, h - 49, "+31%", F_SANS_B, 34, (10, 20, 5), anchor="mm")
    return p.out()


# ---- 2. Grok deepfake lawsuits ---------------------------------------------
def ill_grok(w, h):
    p = Pic(w, h, (226, 232, 244))
    # phone: chatbot output crossed out
    p.rect(30, 4, 118, h - 4, (30, 34, 44), r=12)
    p.rect(36, 12, 112, h - 12, (242, 242, 248), r=4)
    p.text(74, 21, "GROK AI", F_COND_B, 11, INK, anchor="mm")
    p.rect(44, 30, 104, h - 20, (200, 205, 220))
    p.circle(74, 44, 8, (150, 155, 170))
    p.rect(60, 54, 88, h - 20, (150, 155, 170), r=6)
    p.line([(44, 30), (104, h - 20)], RED, 4)
    p.line([(104, 30), (44, h - 20)], RED, 4)
    # gavel
    p.poly([(132, 30), (176, 4), (190, 26), (146, 52)], (120, 74, 40))
    p.line([(166, 30), (206, 76)], (150, 96, 54), 7)
    p.rect(136, h - 16, 214, h - 4, (100, 60, 32), r=3)
    # the two suing states
    p.rect(w - 90, 12, w - 10, 44, (30, 60, 140), r=6)
    p.text(w - 50, 28, "VIRGINIA", F_COND_B, 12, WHITE, anchor="mm")
    p.rect(w - 90, 54, w - 10, 86, (30, 60, 140), r=6)
    p.text(w - 50, 70, "OREGON", F_COND_B, 12, WHITE, anchor="mm")
    return p.out()


# ---- 3. Kyiv region strikes ------------------------------------------------
def ill_kyiv(w, h):
    p = Pic(w, h, (60, 66, 84))
    for cx, cy, r in [(118, 30, 24), (140, 20, 18), (98, 22, 16)]:
        p.circle(cx, cy, r, (112, 112, 120))
    blds = [(8, 44, 50), (54, 30, 96), (100, 58, 140), (144, 38, 190),
            (194, 52, 236), (240, 34, 280), (284, 48, w - 4)]
    for x0, top, x1 in blds:
        p.rect(x0, top, x1, h, (36, 40, 54))
        for wy in range(top + 8, h - 6, 13):
            for wx in range(x0 + 6, x1 - 8, 11):
                p.rect(wx, wy, wx + 5, wy + 7, (230, 200, 110))
    # damaged block on fire
    p.poly([(100, 58), (112, 66), (120, 56), (140, 74), (140, 80), (100, 80)],
           (60, 66, 84))
    p.poly([(102, 84), (114, 56), (122, 70), (132, 48), (140, 86)], (240, 120, 30))
    p.poly([(112, 86), (121, 66), (130, 86)], (255, 210, 60))
    # incoming strikes
    p.line([(w - 6, 4), (176, 30)], (255, 220, 120), 3)
    p.line([(w - 50, 2), (156, 16)], (255, 220, 120), 2)
    p.rect(w - 104, h - 26, w - 6, h - 6, (255, 213, 0), r=4)
    p.text(w - 55, h - 16, "KYIV REGION", F_COND_B, 12, INK, anchor="mm")
    return p.out()


# ---- 4. Khartoum drone strikes ---------------------------------------------
def ill_khartoum(w, h):
    p = Pic(w, h, (238, 214, 170))
    for x0, top in [(10, 54), (62, 62), (232, 58), (282, 66)]:
        p.rect(x0, top, x0 + 44, h - 8, (196, 150, 100))
        p.rect(x0 + 16, top + 16, x0 + 28, h - 8, (120, 84, 50))
    p.rect(0, h - 8, w, h, (200, 170, 120))
    # UN building
    p.rect(118, 40, 214, h - 8, (240, 244, 250), outline=(90, 140, 200), width=2)
    for wy in range(50, h - 16, 13):
        for wx in range(126, 206, 14):
            p.rect(wx, wy, wx + 8, wy + 7, (120, 170, 220))
    p.rect(144, 20, 188, 40, (70, 130, 220), r=3)
    p.text(166, 30, "UN", F_SANS_B, 14, WHITE, anchor="mm")
    # damage: broken corner + smoke
    p.poly([(194, 40), (215, 40), (215, 70), (204, 56)], (238, 214, 170))
    p.circle(208, 30, 12, (120, 110, 100))
    p.circle(224, 18, 9, (140, 130, 120))
    # drone
    dx, dy = 66, 24
    p.rect(dx - 22, dy - 6, dx + 22, dy + 6, (40, 40, 44), r=5)
    for ox in (-30, 30):
        p.line([(dx, dy), (dx + ox, dy - 10)], (40, 40, 44), 3)
        p.ellipse(dx + ox - 14, dy - 14, dx + ox + 14, dy - 8, (90, 90, 96))
    p.line([(dx + 10, dy + 8), (196, 46)], RED, 2)
    p.text(w - 8, 8, "KHARTOUM", F_COND_B, 12, INK, anchor="ra")
    return p.out()


# ---- 5. Congressman to resign ----------------------------------------------
def ill_gomez(w, h):
    p = Pic(w, h, (222, 230, 240))
    stone, edge = (250, 250, 252), (110, 110, 120)
    cx = 106
    p.rect(cx - 88, h - 18, cx + 88, h - 4, stone, outline=edge, width=1)
    for i in range(9):
        x = cx - 78 + i * 19
        p.rect(x, h - 40, x + 6, h - 18, stone, outline=edge, width=1)
    p.rect(cx - 84, h - 46, cx + 84, h - 40, stone, outline=edge, width=1)
    p.rect(cx - 36, h - 58, cx + 36, h - 46, stone, outline=edge, width=1)
    p.pie(cx - 34, 12, cx + 34, h - 30, 180, 360, stone)
    p.line([(cx, 12), (cx, 4)], edge, 2)
    p.circle(cx, 4, 2, edge)
    # calendar: 1 December
    kx, ky = 226, 4
    p.rect(kx, ky, kx + 78, ky + 66, WHITE, outline=edge, width=2, r=6)
    p.rect(kx, ky, kx + 78, ky + 22, RED, r=6)
    p.rect(kx, ky + 14, kx + 78, ky + 22, RED)
    p.text(kx + 39, ky + 11, "DEC", F_SANS_B, 14, WHITE, anchor="mm")
    p.text(kx + 39, ky + 45, "1", F_SANS_B, 30, INK, anchor="mm")
    # exit arrow
    p.line([(214, h - 12), (290, h - 12)], INK, 4)
    p.poly([(290, h - 21), (306, h - 12), (290, h - 3)], INK)
    return p.out()


# ---- 6. UN chief: AI risk framework within a year --------------------------
def ill_un_ai(w, h):
    p = Pic(w, h, (220, 234, 250))
    blue, navy = (60, 120, 200), (30, 60, 120)
    gx, gy, r = 70, h // 2, 42
    p.circle(gx, gy, r, (120, 170, 230), outline=blue, width=3)
    p.ellipse(gx - 18, gy - r, gx + 18, gy + r, None, outline=blue, width=2)
    p.line([(gx - r, gy), (gx + r, gy)], blue, 2)
    p.line([(gx - r + 7, gy - 20), (gx + r - 7, gy - 20)], blue, 2)
    p.line([(gx - r + 7, gy + 20), (gx + r - 7, gy + 20)], blue, 2)
    sx, sy = 184, 8
    for oy in (-16, 0, 16):
        p.line([(gx + r, gy + oy), (sx - 40, sy + 38 + oy // 2)], navy, 2)
    p.poly([(sx - 40, sy), (sx + 40, sy), (sx + 40, sy + 46), (sx, sy + 84),
            (sx - 40, sy + 46)], navy)
    p.text(sx, sy + 34, "AI", F_SANS_B, 28, WHITE, anchor="mm")
    p.rect(w - 80, h - 54, w - 8, h - 10, WHITE, outline=blue, width=2, r=6)
    p.text(w - 44, h - 41, "WITHIN", F_COND_B, 11, INK, anchor="mm")
    p.text(w - 44, h - 23, "1 YEAR", F_SANS_B, 14, RED, anchor="mm")
    return p.out()


# ---- 7. India-Nepal train --------------------------------------------------
def ill_train(w, h):
    p = Pic(w, h, (250, 228, 196))
    p.pie(-40, 40, 150, 200, 180, 360, (150, 190, 120))
    p.pie(140, 34, 360, 214, 180, 360, (120, 170, 100))
    p.rect(0, h - 22, w, h - 16, (90, 70, 50))
    for x in range(4, w, 16):
        p.rect(x, h - 18, x + 8, h - 10, (120, 90, 60))
    by = h - 24
    p.rect(40, by - 50, 210, by - 8, (40, 90, 160), r=8)
    p.poly([(210, by - 50), (252, by - 28), (252, by - 8), (210, by - 8)], (40, 90, 160))
    p.rect(40, by - 50, 210, by - 43, (230, 120, 30))
    for wx in range(52, 200, 30):
        p.rect(wx, by - 38, wx + 20, by - 24, (230, 240, 250), r=3)
    p.poly([(216, by - 44), (240, by - 30), (216, by - 30)], (230, 240, 250))
    for wx in (64, 110, 160, 222):
        p.circle(wx, by - 6, 7, (30, 30, 34))
    # route: Ayodhya (India) <-> Janakpur Dham (Nepal)
    p.text(8, 4, "AYODHYA", F_COND_B, 12, INK)
    p.text(w - 8, 4, "JANAKPUR", F_COND_B, 12, INK, anchor="ra")
    # arrow sits on its own row below the labels (text occupies ~y 4-19)
    ay = 26
    p.line([(18, ay), (w - 18, ay)], INK, 2)
    p.poly([(w - 18, ay - 5), (w - 10, ay), (w - 18, ay + 5)], INK)
    p.poly([(18, ay - 5), (10, ay), (18, ay + 5)], INK)
    return p.out()


# ---------------------------------------------------------------------------
LEAD = dict(
    kicker="LEAD · USA · TECH & MARKETS",
    head="HUANG IS BACK",
    sub="Nvidia reinstates its co-founder as chief executive; shares jump about 31%.",
    src="Sources: Reuters; The Japan Times",
)

STORIES = [
    dict(tag="USA · TECH & LAW", head="STATES SUE OVER GROK IMAGES",
         sub="Virginia and Oregon accuse Musk's firms of letting Grok create sexualised deepfakes.",
         art=ill_grok),
    dict(tag="UKRAINE · WAR", head="14 KILLED IN KYIV REGION STRIKES",
         sub="Russian attacks hit homes and facilities around Ukraine's capital.",
         art=ill_kyiv),
    dict(tag="SUDAN · CONFLICT", head="DRONES HIT KHARTOUM",
         sub="Strikes damage homes and a United Nations building.",
         art=ill_khartoum),
    dict(tag="USA · POLITICS", head="CONGRESSMAN TO QUIT AFTER ETHICS REPORT",
         sub="Rep. Jimmy Gomez resigns over misconduct finding; exit set for 1 December.",
         art=ill_gomez),
    dict(tag="UNITED NATIONS · AI", head="UN CHIEF: SET AI SAFETY RULES IN A YEAR",
         sub="Guterres urges a global framework to manage AI risks.",
         art=ill_un_ai),
    dict(tag="INDIA · NEPAL", head="NEW TRAIN LINKS INDIA AND NEPAL",
         sub="Saryu-Kamala Express connects Ayodhya with Janakpur Dham.",
         art=ill_train),
]

TICKER = [
    "CrowdStrike to buy Zscaler in a $44bn deal",
    "Trump to award Giuliani the Medal of Freedom",
    "UK nations to jointly host the 2035 Women's World Cup",
    "Amnesty alleges possible war crimes in Ethiopia shelling; 14 civilians killed",
]


def render():
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    M = 18

    # ---- masthead ----
    d.rectangle([0, 0, W, 6], fill=INK)
    text(d, (W // 2, 50), "THE WORLD TODAY", font(F_SERIF_B, 70), INK, "masthead", "mm")
    d.line([(M, 92), (W - M, 92)], fill=RULE, width=3)
    d.rectangle([M, 96, W - M, 126], fill=INK)
    text(d, (W // 2, 111), "TUESDAY, 24 NOVEMBER 2026", font(F_SANS_B, 21), WHITE,
         "date", "mm")
    f_small = font(F_COND_B, 13)
    text(d, (M + 10, 111), "THE DAY'S NEWS IN ONE PAGE", f_small, (225, 225, 225),
         "date-l", "lm")
    text(d, (W - M - 10, 111), "7 STORIES · 4 BRIEFS", f_small, (225, 225, 225),
         "date-r", "rm")

    # ---- lead story ----
    ly0, ly1 = 136, 406
    art_w = 400
    paste(img, ill_nvidia(art_w, ly1 - ly0), (M, ly0), "lead-art")
    tx = M + art_w + 22
    tw = W - M - tx
    text(d, (tx, ly0), LEAD["kicker"], font(F_COND_B, 17), RED, "lead-kicker")
    src_f = font(F_COND, 14)
    budget = (ly1 - ly0) - 30 - 26
    (hf, hl), (sf, sl) = fit_block(
        LEAD["head"], LEAD["sub"], tw, budget,
        F_SERIF_B, range(76, 39, -2), 2, 1.02,
        F_SANS, range(25, 19, -1), 3, 1.25, 12)
    y = draw_lines(d, tx, ly0 + 28, hl, hf, INK, 1.02, "lead-head")
    draw_lines(d, tx, y + 12, sl, sf, INK, 1.25, "lead-sub")
    text(d, (tx, ly1), LEAD["src"], src_f, GREY, "lead-src", "ld")
    d.line([(M, ly1 + 9), (W - M, ly1 + 9)], fill=RULE, width=2)

    # ---- grid of six ----
    cols, gap = 3, 18
    cw = (W - 2 * M - (cols - 1) * gap) // cols
    row_tops = [426, 678]
    pitch = row_tops[1] - row_tops[0]
    art_h = 100
    for i, s in enumerate(STORIES):
        r, c = divmod(i, cols)
        x0 = M + c * (cw + gap)
        y0 = row_tops[r]
        lab = "story%d" % (i + 2)
        text(d, (x0, y0), s["tag"], font(F_COND_B, 14), RED, lab + "-tag")
        paste(img, s["art"](cw, art_h), (x0, y0 + 20), lab + "-art")
        yy = y0 + 20 + art_h + 7
        budget = y0 + pitch - 10 - yy
        (hf, hl), (sf, sl) = fit_block(
            s["head"], s["sub"], cw, budget,
            F_COND_B, range(24, 15, -1), 2, 1.02,
            F_COND, range(16, 11, -1), 3, 1.1, 3)
        yy = draw_lines(d, x0, yy, hl, hf, INK, 1.02, lab + "-head")
        draw_lines(d, x0, yy + 3, sl, sf, GREY, 1.1, lab + "-sub")
        if c < cols - 1:
            lx = x0 + cw + gap // 2
            d.line([(lx, y0), (lx, y0 + pitch - 12)], fill=HAIR, width=1)
    d.line([(M, row_tops[1] - 7), (W - M, row_tops[1] - 7)], fill=HAIR, width=1)

    # ---- ticker ----
    ty = 932
    d.rectangle([0, ty, W, H], fill=(255, 238, 160))
    d.rectangle([0, ty, W, ty + 3], fill=INK)
    d.rectangle([0, ty + 3, 148, H], fill=RED)
    text(d, (74, ty + 32), "ALSO", font(F_SANS_B, 21), WHITE, "tick-l1", "mm")
    text(d, (74, ty + 60), "TODAY", font(F_SANS_B, 21), WHITE, "tick-l2", "mm")
    f_t = font(F_COND_B, 17)
    step = (H - ty - 10) // len(TICKER)
    for k, item in enumerate(TICKER):
        text(d, (164, ty + 8 + k * step), "▸ " + item, f_t, INK, "tick%d" % k)

    check_layout()
    img.save(os.path.join(HERE, "entry.png"), optimize=True)
    return BOXES


if __name__ == "__main__":
    for lab, box in render():
        print("%-16s %s" % (lab, box))
