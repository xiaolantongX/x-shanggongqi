# -*- coding: utf-8 -*-
"""X 粉丝增长桌面浮层 — 半透明玻璃胶囊 + 官方 X 标 + 悬停关注列表 + 今日新增。"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import webbrowser
import tkinter as tk
from pathlib import Path
from typing import Any
from datetime import datetime, timezone, timedelta

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageTk
except ImportError:
    import subprocess

    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "pillow", "-q"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageTk

APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "XFanGrowth"
STATE_PATH = APP_DIR / "state.json"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
AVATAR_DIR = APP_DIR / "avatars"
PANEL_URL = (
    "https://cursor.com/canvas/store-aa1e146f-a910-49c0-8cf1-24ec8d9c662a/"
    "e1a51adb-228b-4831-8e11-99bc34d892d5"
)

# Capsule layout — 方案 A 宽版（设计稿）
W, H = 264, 64
SHADOW = 10
RADIUS = 16
CANVAS_W, CANVAS_H = W + SHADOW * 2, H + SHADOW * 2
POLL_SEC = 3.0
KEY = "#010101"

# Hover panel — wide enough for avatar, name, two icon buttons, and the 上供 pill.
PANEL_W = 320
PANEL_GAP = 8
PANEL_RADIUS = 14
TITLE_H = 36
ROW_H = 52
AVATAR_SZ = 32
BTN_H = 28
MAX_ROWS = 6
HOVER_SHOW_MS = 180
HOVER_HIDE_MS = 200


def ensure_state() -> dict[str, Any]:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_PATH.exists():
        data = {
            "account": {
                "username": "your_handle",
                "name": "Your Display Name",
                "followers_count": 0,
            },
            "follower_ids": [],
            "followers": [],
            "new_followers": [],
            "toast_queue": [],
            "tribute_log": [],
            "daily": {"date": "", "count": 0, "names": []},
            "updated_at": "",
        }
        STATE_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return data
    return json.loads(STATE_PATH.read_text(encoding="utf-8-sig"))


def save_state(data: dict[str, Any]) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


TZ_SH = timezone(timedelta(hours=8))


def _today_str() -> str:
    return datetime.now(TZ_SH).strftime("%Y-%m-%d")


def ensure_daily(data: dict[str, Any]) -> dict[str, Any]:
    """Roll daily counter to Asia/Shanghai today; return daily dict."""
    today = _today_str()
    daily = data.get("daily")
    if not isinstance(daily, dict) or daily.get("date") != today:
        daily = {"date": today, "count": 0, "names": []}
        data["daily"] = daily
    else:
        daily.setdefault("count", 0)
        daily.setdefault("names", [])
        data["daily"] = daily
    return daily


def bump_daily(data: dict[str, Any], names: list[str]) -> None:
    daily = ensure_daily(data)
    seen = list(daily.get("names") or [])
    for n in names:
        n = (n or "").strip()
        if not n or n in seen:
            continue
        seen.append(n)
    daily["names"] = seen
    daily["count"] = len(seen)
    data["daily"] = daily


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    windir = os.environ.get("WINDIR", r"C:\Windows")
    fonts = Path(windir) / "Fonts"
    candidates = []
    if bold:
        candidates += [
            (fonts / "msyhbd.ttc", 0),
            (fonts / "msyh.ttc", 0),
            (fonts / "simhei.ttf", 0),
            (fonts / "segoeuib.ttf", 0),
            (fonts / "segoeui.ttf", 0),
        ]
    else:
        candidates += [
            (fonts / "msyh.ttc", 0),
            (fonts / "msyhbd.ttc", 0),
            (fonts / "simhei.ttf", 0),
            (fonts / "segoeui.ttf", 0),
        ]
    for p, idx in candidates:
        if not p.exists():
            continue
        try:
            return ImageFont.truetype(str(p), size, index=idx)
        except OSError:
            try:
                return ImageFont.truetype(str(p), size)
            except OSError:
                continue
    return ImageFont.load_default()


def _tk_font(size: int, bold: bool = False) -> tuple:
    weight = "bold" if bold else "normal"
    for family in ("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "Arial"):
        return (family, size, weight)
    return ("TkDefaultFont", size, weight)


def _ellipsis(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int) -> str:
    if draw.textbbox((0, 0), text, font=font)[2] <= max_w:
        return text
    ell = "…"
    t = text
    while t and draw.textbbox((0, 0), t + ell, font=font)[2] > max_w:
        t = t[:-1]
    return (t + ell) if t else ell


def _harden_for_chromakey(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 140:
                px[x, y] = (1, 1, 1, 0)
            else:
                px[x, y] = (r, g, b, 255)
    return im


def _blend_white(rgb: tuple[int, int, int], amount: float) -> tuple[int, int, int, int]:
    r, g, b = rgb
    return (
        int(r + (255 - r) * amount),
        int(g + (255 - g) * amount),
        int(b + (255 - b) * amount),
        255,
    )


_X_BADGE_CACHE: Image.Image | None = None
_ROW_ICON_CACHE: dict[str, Image.Image] = {}
ICON_BOX = 28
_PANEL_BG = (0x15, 0x20, 0x2B, 255)
_ICON_FACE = (0x25, 0x33, 0x41, 255)
_ICON_EDGE = (0x38, 0x44, 0x4D, 255)


def _x_mark_glyph(size: int = 16) -> Image.Image:
    """Official X mark, black knocked out, scaled to the icon button."""
    for name in ("x-mark-alpha.png", "x-mark-white.png", "logo-white.png"):
        path = ASSETS_DIR / name
        if not path.exists():
            continue
        raw = Image.open(path).convert("RGBA")
        bbox = raw.getbbox()
        if not bbox:
            continue
        return raw.crop(bbox).resize((size, size), Image.Resampling.LANCZOS)
    glyph = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(glyph)
    m = max(1, size // 8)
    draw.line((m, m, size - m, size - m), fill=(255, 255, 255, 255), width=max(2, size // 6))
    draw.line((size - m, m, m, size - m), fill=(255, 255, 255, 255), width=max(2, size // 6))
    return glyph


def _follow_glyph(size: int = 22) -> Image.Image:
    """Person + plus, white on transparent with an X-blue plus badge."""
    scale = 8
    s = size * scale
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    white = (255, 255, 255, 255)
    head_r = int(s * 0.15)
    head = (int(s * 0.34), int(s * 0.30))
    draw.ellipse(
        (head[0] - head_r, head[1] - head_r, head[0] + head_r, head[1] + head_r),
        fill=white,
    )
    body_w = int(s * 0.28)
    draw.rounded_rectangle(
        (head[0] - body_w, int(s * 0.50), head[0] + body_w, int(s * 0.98)),
        radius=int(s * 0.16),
        fill=white,
    )
    br = int(s * 0.20)
    badge = (int(s * 0.74), int(s * 0.68))
    draw.ellipse(
        (badge[0] - br, badge[1] - br, badge[0] + br, badge[1] + br),
        fill=(0x1D, 0x9B, 0xF0, 255),
    )
    thickness = max(8, int(s * 0.05))
    arm = int(s * 0.10)
    draw.rectangle(
        (badge[0] - thickness // 2, badge[1] - arm, badge[0] + thickness // 2, badge[1] + arm),
        fill=white,
    )
    draw.rectangle(
        (badge[0] - arm, badge[1] - thickness // 2, badge[0] + arm, badge[1] + thickness // 2),
        fill=white,
    )
    return im.resize((size, size), Image.Resampling.LANCZOS)


def _icon_plate(glyph: Image.Image, box: int = ICON_BOX) -> Image.Image:
    """Rounded chip on the panel color so the glyph stays readable on #15202B."""
    im = Image.new("RGBA", (box, box), _PANEL_BG)
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle((0, 0, box - 1, box - 1), radius=8, fill=_ICON_FACE, outline=_ICON_EDGE)
    ox = (box - glyph.width) // 2
    oy = (box - glyph.height) // 2
    im.paste(glyph, (ox, oy), glyph)
    return im


def _row_icon(kind: str) -> Image.Image:
    cached = _ROW_ICON_CACHE.get(kind)
    if cached is not None:
        return cached.copy()
    if kind == "open":
        im = _icon_plate(_x_mark_glyph(16))
    else:
        im = _icon_plate(_follow_glyph(22))
    _ROW_ICON_CACHE[kind] = im
    return im.copy()


def _ellipsize_px(text: str, font, max_w: int) -> str:
    if max_w < 12 or font.measure(text) <= max_w:
        return text
    ell = "…"
    trimmed = text
    while trimmed and font.measure(trimmed + ell) > max_w:
        trimmed = trimmed[:-1]
    return (trimmed + ell) if trimmed else ell


def _load_x_badge(size: int = 28) -> Image.Image:
    """Official white X on black rounded-square badge (28×28 r=6, pad≈5)."""
    global _X_BADGE_CACHE
    if _X_BADGE_CACHE is not None and _X_BADGE_CACHE.size == (size, size):
        return _X_BADGE_CACHE.copy()

    baked = ASSETS_DIR / "x-badge-28.png"
    if baked.exists() and size == 28:
        im = Image.open(baked).convert("RGBA")
        _X_BADGE_CACHE = im
        return im.copy()

    # Prefer transparent mark / logo-white
    mark: Image.Image | None = None
    for name in ("x-mark-alpha.png", "x-mark-white.png", "logo-white.png", "x-badge-64.png"):
        p = ASSETS_DIR / name
        if not p.exists():
            continue
        raw = Image.open(p)
        if raw.mode == "L":
            rgba = Image.new("RGBA", raw.size, (0, 0, 0, 0))
            px = raw.load()
            op = rgba.load()
            for y in range(raw.height):
                for x in range(raw.width):
                    v = px[x, y]
                    if v > 40:
                        op[x, y] = (255, 255, 255, int(v))
            mark = rgba
        else:
            raw = raw.convert("RGBA")
            # If black background, lift white to alpha
            px = raw.load()
            out = Image.new("RGBA", raw.size, (0, 0, 0, 0))
            op = out.load()
            for y in range(raw.height):
                for x in range(raw.width):
                    r, g, b, a = px[x, y]
                    lum = (r + g + b) / 3
                    if lum > 40 and a > 10:
                        op[x, y] = (255, 255, 255, max(a, int(lum)))
            mark = out
        break

    badge = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(badge)
    rad = max(4, int(round(size * 6 / 28)))
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=rad, fill=(0, 0, 0, 255))
    pad = max(3, int(round(size * 5 / 28)))
    content = size - pad * 2
    if mark is not None:
        bbox = mark.getbbox() or (0, 0, mark.width, mark.height)
        cropped = mark.crop(bbox)
        cropped = cropped.resize((content, content), Image.Resampling.LANCZOS)
        badge.paste(cropped, (pad, pad), cropped)
    _X_BADGE_CACHE = badge
    return badge.copy()


def render_capsule(
    name: str,
    username: str,
    followers: int,
    latest: str | None = None,
    today_new: int = 0,
    pulse: float = 1.0,
) -> Image.Image:
    """Wide glass capsule — 264×64, radius 16, official X badge, 今日新增."""
    scale = pulse
    w, h = max(220, int(W * scale)), max(52, int(H * scale))
    rad = max(12, int(RADIUS * scale))
    pad = SHADOW
    cw, ch = w + pad * 2, h + pad * 2
    out = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))

    # soft depth (slightly lighter so overall -alpha reads glassier)
    depth = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    ImageDraw.Draw(depth).rounded_rectangle(
        (pad + 2, pad + 4, pad + w + 2, pad + h + 4),
        radius=rad,
        fill=(6, 12, 20, 255),
    )
    out.paste(depth, (0, 0), depth)

    # vertical glass gradient #4BB4F5 → #1A8CD8 → #0D6EAD (baked opaque; window -alpha for translucency)
    body = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = body.load()
    for y in range(h):
        t = y / max(1, h - 1)
        if t < 0.42:
            u = t / 0.42
            r = int(75 + (26 - 75) * u)
            g = int(180 + (140 - 180) * u)
            b = int(245 + (216 - 245) * u)
        else:
            u = (t - 0.42) / 0.58
            r = int(26 + (13 - 26) * u)
            g = int(140 + (110 - 140) * u)
            b = int(216 + (173 - 216) * u)
        # lift slightly for sheen/glass read under window alpha
        r = min(255, int(r + 8))
        g = min(255, int(g + 6))
        b = min(255, int(b + 4))
        for x in range(w):
            px[x, y] = (r, g, b, 255)

    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=rad, fill=255)
    mask = mask.point(lambda v: 255 if v >= 128 else 0)
    body.putalpha(mask)

    bp = body.load()
    sheen_h = max(14, int(h * 0.40))
    for y in range(sheen_h):
        fall = 1.0 - (y / max(1, sheen_h - 1))
        amt = 0.22 * fall
        for x in range(w):
            r0, g0, b0, a0 = bp[x, y]
            if a0 < 128:
                continue
            bp[x, y] = _blend_white((r0, g0, b0), amt)

    stroke = Image.new("L", (w, h), 0)
    ImageDraw.Draw(stroke).rounded_rectangle(
        (1, 1, w - 2, h - 2),
        radius=max(8, rad - 1),
        outline=255,
        width=1,
    )
    sp = stroke.load()
    for y in range(h):
        for x in range(w):
            if sp[x, y] > 0 and bp[x, y][3] > 0:
                r0, g0, b0, _ = bp[x, y]
                bp[x, y] = _blend_white((r0, g0, b0), 0.26)

    draw = ImageDraw.Draw(body)

    # left official X badge 28×28, margin 14
    margin_l = 14
    badge_sz = 28
    bx = margin_l
    by = (h - badge_sz) // 2
    badge = _load_x_badge(badge_sz)
    body.paste(badge, (bx, by), badge)

    f_name = _font(14, bold=True)
    f_user = _font(11, bold=False)
    f_count = _font(18, bold=True)
    f_lab = _font(9, bold=False)
    f_lat = _font(11, bold=False)
    f_today = _font(10, bold=True)

    left = bx + badge_sz + 10
    right_pad = 14
    right_col = w - right_pad
    mid_max = max(60, right_col - left - 70)

    disp = _ellipsis(draw, name or username, f_name, mid_max)
    handle = _ellipsis(draw, f"@{username}", f_user, mid_max)

    # 2-line center; optional 3rd line only for real +name (never idle placeholder)
    if latest:
        y0 = 6
        draw.text((left, y0), disp, font=f_name, fill=(255, 255, 255, 255))
        draw.text((left, y0 + 18), handle, font=f_user, fill=(255, 255, 255, 184))
        lat = _ellipsis(draw, f"+ {latest}", f_lat, mid_max)
        draw.text((left, y0 + 36), lat, font=f_lat, fill=(231, 233, 234, 255))
    else:
        y0 = 12
        draw.text((left, y0), disp, font=f_name, fill=(255, 255, 255, 255))
        draw.text((left, y0 + 20), handle, font=f_user, fill=(255, 255, 255, 184))

    num = str(followers)
    nb = draw.textbbox((0, 0), num, font=f_count)
    nw = nb[2] - nb[0]
    lb = draw.textbbox((0, 0), "粉丝", font=f_lab)
    lw = lb[2] - lb[0]
    today_txt = f"今日 +{today_new}"
    tb = draw.textbbox((0, 0), today_txt, font=f_today)
    tw = tb[2] - tb[0]
    col_w = max(nw, lw, tw)
    nx = right_col - col_w

    div_x = nx - 10
    for yy in range(10, h - 10):
        if 0 <= div_x < w and bp[div_x, yy][3] > 0:
            r0, g0, b0, _ = bp[div_x, yy]
            bp[div_x, yy] = _blend_white((r0, g0, b0), 0.28)

    draw.text((nx + (col_w - nw) / 2, 6), num, font=f_count, fill=(255, 255, 255, 255))
    draw.text((nx + (col_w - lw) / 2, 28), "粉丝", font=f_lab, fill=(200, 214, 225, 255))
    today_fill = (29, 155, 240, 255) if today_new > 0 else (139, 152, 165, 255)
    draw.text((nx + (col_w - tw) / 2, 44), today_txt, font=f_today, fill=today_fill)

    out.paste(body, (pad, pad), body)
    out = _harden_for_chromakey(out)

    if out.size != (CANVAS_W, CANVAS_H):
        canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
        ox = (CANVAS_W - out.width) // 2
        oy = (CANVAS_H - out.height) // 2
        canvas.paste(out, (ox, oy), out)
        return _harden_for_chromakey(canvas)
    return out


def rounded_card(w: int, h: int, radius: int = 12) -> Image.Image:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle(
        (0, 0, w - 1, h - 1), radius=radius, fill=(21, 32, 43, 238)
    )
    ImageDraw.Draw(img).rectangle((0, 6, 3, h - 7), fill=(29, 155, 240, 255))
    return img


def _circle_avatar(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA").resize((AVATAR_SZ, AVATAR_SZ), Image.Resampling.LANCZOS)
    mask = Image.new("L", (AVATAR_SZ, AVATAR_SZ), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, AVATAR_SZ - 1, AVATAR_SZ - 1), fill=255)
    out = Image.new("RGBA", (AVATAR_SZ, AVATAR_SZ), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out


def _fetch_avatar(user_id: str, url: str, *, network: bool = False) -> Image.Image | None:
    """Load avatar from cache; optional network (keep panel open snappy)."""
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    cache = AVATAR_DIR / f"{user_id}.jpg"
    try:
        if cache.exists():
            return _circle_avatar(Image.open(cache))
        if network and url:
            req = urllib.request.Request(url, headers={"User-Agent": "XFanGrowth/1.0"})
            with urllib.request.urlopen(req, timeout=2) as resp:
                cache.write_bytes(resp.read())
            return _circle_avatar(Image.open(cache))
    except Exception:
        return None
    return None


def _placeholder_avatar() -> Image.Image:
    im = Image.new("RGBA", (AVATAR_SZ, AVATAR_SZ), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse(
        (0, 0, AVATAR_SZ - 1, AVATAR_SZ - 1), fill=(56, 68, 77, 255)  # #38444D
    )
    return im


class ThinScrollbar(tk.Canvas):
    """Slim 7px rounded-feel scrollbar — track #38444D, thumb #8B98A5, hover #E7E9EA."""

    def __init__(self, parent, command=None, width: int = 7, bg: str = "#15202B", **kw):
        super().__init__(
            parent,
            width=width,
            highlightthickness=0,
            bd=0,
            bg=bg,
            cursor="arrow",
            **kw,
        )
        self._command = command
        self._width = width
        self._lo = 0.0
        self._hi = 1.0
        self._hover = False
        self._drag_y0 = 0
        self._drag_lo0 = 0.0
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._motion)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<MouseWheel>", self._wheel)
        self._draw()

    def set(self, lo, hi) -> None:
        try:
            self._lo = float(lo)
            self._hi = float(hi)
        except (TypeError, ValueError):
            self._lo, self._hi = 0.0, 1.0
        self._draw()

    def _on_enter(self, _e=None) -> None:
        self._hover = True
        self._draw()

    def _on_leave(self, _e=None) -> None:
        self._hover = False
        self._draw()

    def _metrics(self):
        h = max(1, int(self.winfo_height() or 1))
        pad = 3
        usable = max(1, h - pad * 2)
        span = max(0.05, self._hi - self._lo)
        th = max(16, int(usable * span))
        if self._hi >= 0.999 and self._lo <= 0.001:
            # full content visible — hide thumb almost
            return pad, pad, usable, True
        top = pad + int(self._lo * (usable - th) / max(1e-6, 1.0 - span))
        top = max(pad, min(pad + usable - th, top))
        return top, top + th, usable, False

    def _draw(self) -> None:
        self.delete("all")
        h = max(1, int(self.winfo_height() or 1))
        w = self._width
        # track
        self.create_rectangle(0, 0, w, h, fill="#38444D", outline="", tags="track")
        t0, t1, _usable, full = self._metrics()
        if full:
            return
        color = "#E7E9EA" if self._hover else "#8B98A5"
        x0, x1 = 1, w - 1
        # pill thumb via oval caps + mid rect
        r = max(2, (x1 - x0) // 2)
        cy0 = t0 + r
        cy1 = t1 - r
        if cy1 < cy0:
            cy0 = cy1 = (t0 + t1) // 2
        self.create_oval(x0, t0, x1, t0 + 2 * r, fill=color, outline="", tags="thumb")
        self.create_oval(x0, t1 - 2 * r, x1, t1, fill=color, outline="", tags="thumb")
        self.create_rectangle(x0, cy0, x1, cy1, fill=color, outline="", tags="thumb")

    def _press(self, e) -> None:
        t0, t1, usable, full = self._metrics()
        if full:
            return
        if t0 <= e.y <= t1:
            self._drag_y0 = e.y
            self._drag_lo0 = self._lo
        else:
            # jump page
            span = max(0.05, self._hi - self._lo)
            target = (e.y - 3) / max(1, usable) - span / 2
            target = max(0.0, min(1.0 - span, target))
            if self._command:
                self._command("moveto", target)

    def _motion(self, e) -> None:
        t0, t1, usable, full = self._metrics()
        if full or not hasattr(self, "_drag_y0"):
            return
        span = max(0.05, self._hi - self._lo)
        dy = e.y - self._drag_y0
        delta = dy / max(1, usable - max(16, int(usable * span)))
        target = max(0.0, min(1.0 - span, self._drag_lo0 + delta * (1.0 - span)))
        if self._command:
            self._command("moveto", target)

    def _release(self, _e) -> None:
        self._drag_y0 = 0

    def _wheel(self, e) -> None:
        if not self._command:
            return
        if getattr(e, "delta", 0):
            steps = -1 if e.delta > 0 else 1
        else:
            steps = 0
        self._command("scroll", steps, "units")


class FanBallApp:
    def __init__(self, demo_panel: bool = False) -> None:
        self.root = tk.Tk()
        self.root.title("X粉丝浮层")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        try:
            self.root.wm_attributes("-transparentcolor", KEY)
        except tk.TclError:
            pass
        try:
            # overall translucency; chromakey still punches rounded corners
            self.root.attributes("-alpha", 0.82)
        except tk.TclError:
            pass
        self.root.configure(bg=KEY)

        self._pulse = 1.0
        self._photo: ImageTk.PhotoImage | None = None
        self.canvas = tk.Canvas(
            self.root,
            width=CANVAS_W,
            height=CANVAS_H,
            highlightthickness=0,
            bg=KEY,
            bd=0,
        )
        self.canvas.pack()
        self._img_id = self.canvas.create_image(
            CANVAS_W // 2, CANVAS_H // 2, anchor="center"
        )

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{CANVAS_W}x{CANVAS_H}+{sw - CANVAS_W - 20}+{sh // 3}")

        self._drag_x = 0
        self._drag_y = 0
        self._dragging = False
        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._end_drag)
        self.canvas.bind("<Button-3>", self._popup_menu)
        self.canvas.bind("<Double-Button-1>", lambda _e: webbrowser.open(PANEL_URL))

        # Hover for follower panel
        self.canvas.bind("<Enter>", self._on_capsule_enter)
        self.canvas.bind("<Leave>", self._on_capsule_leave)

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="打开增长面板", command=lambda: webbrowser.open(PANEL_URL))
        self.menu.add_command(label="关注列表", command=self._show_followers_panel)
        self.menu.add_command(label="刷新状态", command=self.refresh_now)
        self.menu.add_separator()
        self.menu.add_command(label="退出浮层", command=self.root.destroy)

        self.state = ensure_state()
        ensure_daily(self.state)
        try:
            save_state(self.state)
        except Exception:
            pass
        self._seen: set[str] = set()
        self.toast: tk.Toplevel | None = None
        self._toast_photos: list[ImageTk.PhotoImage] = []

        self.followers_win: tk.Toplevel | None = None
        self._panel_photos: list[ImageTk.PhotoImage] = []
        self._hover_show_job: str | None = None
        self._hover_hide_job: str | None = None
        self._panel_alive = False

        self._paint()
        self.root.after(400, self._poll)

        if demo_panel:
            self.root.after(600, self._demo_open_panel)

    def _demo_open_panel(self) -> None:
        self._show_followers_panel()
        # keep open ~4s for screenshot, then leave normal
        self.root.after(20000, self._hide_followers_panel)

    def _acc(self) -> dict[str, Any]:
        return self.state.get("account") or {}

    def _latest_name(self) -> str | None:
        news = self.state.get("new_followers") or []
        if news:
            return str(news[0].get("name") or news[0].get("username") or "") or None
        q = self.state.get("toast_queue") or []
        for item in q:
            name = item.get("name")
            if name:
                return str(name)
        last = self.state.get("last_new_name")
        if last:
            return str(last)
        return None

    def _paint(self) -> None:
        acc = self._acc()
        daily = ensure_daily(self.state)
        im = render_capsule(
            name=str(acc.get("name") or "X 账号"),
            username=str(acc.get("username") or "user"),
            followers=int(acc.get("followers_count") or 0),
            latest=self._latest_name(),
            today_new=int(daily.get("count") or 0),
            pulse=self._pulse,
        )
        if im.size != (CANVAS_W, CANVAS_H):
            canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
            ox = (CANVAS_W - im.width) // 2
            oy = (CANVAS_H - im.height) // 2
            canvas.paste(im, (ox, oy), im)
            im = canvas
        self._photo = ImageTk.PhotoImage(im)
        self.canvas.itemconfigure(self._img_id, image=self._photo)

    def _start_drag(self, e: tk.Event) -> None:
        self._dragging = True
        self._cancel_hover_jobs()
        self._hide_followers_panel()
        self._drag_x = e.x_root - self.root.winfo_x()
        self._drag_y = e.y_root - self.root.winfo_y()

    def _on_drag(self, e: tk.Event) -> None:
        self._dragging = True
        self.root.geometry(f"+{e.x_root - self._drag_x}+{e.y_root - self._drag_y}")
        if self._panel_alive:
            self._position_panel()

    def _end_drag(self, _e: tk.Event) -> None:
        self._dragging = False

    def _popup_menu(self, e: tk.Event) -> None:
        try:
            self.menu.tk_popup(e.x_root, e.y_root)
        finally:
            self.menu.grab_release()

    def refresh_now(self) -> None:
        self.state = ensure_state()
        self._paint()
        self._drain()

    def _poll(self) -> None:
        try:
            if STATE_PATH.exists():
                self.state = json.loads(STATE_PATH.read_text(encoding="utf-8-sig"))
                ensure_daily(self.state)
                self._paint()
                self._drain()
        except Exception:
            pass
        self.root.after(int(POLL_SEC * 1000), self._poll)

    def _drain(self) -> None:
        queue = list(self.state.get("toast_queue") or [])
        news = list(self.state.get("new_followers") or [])
        items = queue + [
            {
                "key": f"nf-{n.get('id')}",
                "title": "粉丝 +1",
                "body": f"{n.get('name', '新粉丝')} 关注了你",
                "sub": f"@{n.get('username', '')}",
                "name": n.get("name"),
            }
            for n in news
        ]
        changed = False
        for item in items:
            key = str(item.get("key") or item.get("body") or "")
            if not key or key in self._seen:
                continue
            self._seen.add(key)
            if item.get("name"):
                self.state["last_new_name"] = item["name"]
            self._bounce_toast(
                str(item.get("body") or "有新粉丝"),
                str(item.get("title") or "粉丝 +1"),
                str(item.get("sub") or ""),
            )
            changed = True
        if changed:
            # fold drained new fans into today's counter (Asia/Shanghai)
            news_names = [
                str(n.get("name") or n.get("username") or "")
                for n in news
                if (n.get("name") or n.get("username"))
            ]
            toast_names = [str(q.get("name") or "") for q in queue if q.get("name")]
            bump_daily(self.state, [n for n in news_names + toast_names if n])
            self.state["toast_queue"] = []
            self.state["new_followers"] = []
            try:
                save_state(self.state)
            except Exception:
                pass
            self._paint()

    def _bounce_toast(self, body: str, title: str, sub: str) -> None:
        steps = [(1.02, 50), (1.04, 60), (1.02, 40), (1.0, 30)]

        def run(i: int = 0) -> None:
            if i >= len(steps):
                self._show_toast(body, title, sub)
                return
            self._pulse, delay = steps[i]
            self._paint()
            self.root.after(delay, lambda: run(i + 1))

        run()

    def _show_toast(self, body: str, title: str, sub: str) -> None:
        if self.toast is not None:
            try:
                self.toast.destroy()
            except Exception:
                pass

        tip = tk.Toplevel(self.root)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        try:
            tip.wm_attributes("-transparentcolor", KEY)
        except tk.TclError:
            pass
        tip.configure(bg=KEY)

        tmp = Image.new("RGBA", (8, 8))
        td = ImageDraw.Draw(tmp)
        fonts = [_font(13, True), _font(12, False), _font(11, False)]
        texts = [title, body] + ([sub] if sub else [])
        max_w = 0
        for t, f in zip(texts, fonts):
            bb = td.textbbox((0, 0), t, font=f)
            max_w = max(max_w, bb[2] - bb[0])
        tw = max(170, min(240, max_w + 36))
        th = 14 + 18 * len(texts) + 10
        card = rounded_card(tw, th)
        wrap = Image.new("RGBA", (tw + 24, th + 24), (0, 0, 0, 0))
        sh = Image.new("RGBA", (tw + 24, th + 24), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle(
            (8, 10, tw + 8, th + 12), radius=14, fill=(0, 0, 0, 110)
        )
        sh = sh.filter(ImageFilter.GaussianBlur(8))
        wrap = Image.alpha_composite(wrap, sh)
        wrap.paste(card, (12, 8), card)
        d = ImageDraw.Draw(wrap)
        y = 8 + 10
        colors = [(255, 255, 255, 255), (231, 233, 234, 255), (139, 152, 165, 255)]
        for i, t in enumerate(texts):
            d.text((12 + 14, y), t, font=fonts[i], fill=colors[i])
            y += 18
        photo = ImageTk.PhotoImage(wrap)
        self._toast_photos = [photo]
        tk.Label(tip, image=photo, bg=KEY, bd=0).pack()
        tip.update_idletasks()
        bx, by = self.root.winfo_x(), self.root.winfo_y()
        tx = bx - wrap.width - 8
        if tx < 8:
            tx = bx + CANVAS_W + 8
        tip.geometry(f"+{tx}+{max(8, by)}")
        tip.attributes("-alpha", 0.0)
        self.toast = tip

        def fade(direction: int) -> None:
            if tip is not self.toast:
                return
            a = float(tip.attributes("-alpha"))
            a = max(0.0, min(1.0, a + direction * 0.12))
            tip.attributes("-alpha", a)
            if direction > 0 and a < 1.0:
                tip.after(20, lambda: fade(1))
            elif direction > 0:
                tip.after(2200, lambda: fade(-1))
            elif a > 0:
                tip.after(18, lambda: fade(-1))
            else:
                try:
                    tip.destroy()
                except Exception:
                    pass
                if self.toast is tip:
                    self.toast = None

        tip.after(16, lambda: fade(1))

    # ---------- Hover follower panel ----------
    def _cancel_hover_jobs(self) -> None:
        if self._hover_show_job is not None:
            try:
                self.root.after_cancel(self._hover_show_job)
            except Exception:
                pass
            self._hover_show_job = None
        if self._hover_hide_job is not None:
            try:
                self.root.after_cancel(self._hover_hide_job)
            except Exception:
                pass
            self._hover_hide_job = None

    def _on_capsule_enter(self, _e: tk.Event | None = None) -> None:
        if self._dragging:
            return
        self._cancel_hover_jobs()
        self._hover_show_job = self.root.after(HOVER_SHOW_MS, self._show_followers_panel)

    def _on_capsule_leave(self, _e: tk.Event | None = None) -> None:
        self._cancel_hover_jobs()
        self._hover_hide_job = self.root.after(HOVER_HIDE_MS, self._maybe_hide_panel)

    def _on_panel_enter(self, _e: tk.Event | None = None) -> None:
        self._cancel_hover_jobs()

    def _on_panel_leave(self, _e: tk.Event | None = None) -> None:
        self._cancel_hover_jobs()
        self._hover_hide_job = self.root.after(HOVER_HIDE_MS, self._maybe_hide_panel)

    def _maybe_hide_panel(self) -> None:
        # Hide only if pointer is outside both capsule and panel
        try:
            x, y = self.root.winfo_pointerxy()
        except Exception:
            self._hide_followers_panel()
            return
        if self._point_in_widget(self.root, x, y):
            return
        if self.followers_win is not None:
            try:
                if self._point_in_widget(self.followers_win, x, y):
                    return
            except Exception:
                pass
        self._hide_followers_panel()

    def _point_in_widget(self, w: tk.Misc, x: int, y: int) -> bool:
        try:
            wx, wy = w.winfo_rootx(), w.winfo_rooty()
            ww, wh = w.winfo_width(), w.winfo_height()
            return wx <= x < wx + ww and wy <= y < wy + wh
        except Exception:
            return False

    def _hide_followers_panel(self) -> None:
        self._panel_alive = False
        if self.followers_win is not None:
            try:
                self.followers_win.destroy()
            except Exception:
                pass
            self.followers_win = None
        self._panel_photos = []

    def _position_panel(self) -> None:
        win = self.followers_win
        if win is None:
            return
        win.update_idletasks()
        n = len(self.state.get("followers") or [])
        rows = min(MAX_ROWS, max(1, n or 1))
        # title pad + title + list + bottom pad + border
        ph = 8 + TITLE_H + 4 + rows * ROW_H + 8 + 4
        pw = PANEL_W
        bx = self.root.winfo_x() + SHADOW
        by = self.root.winfo_y() + SHADOW
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        y = by + H + PANEL_GAP
        if y + ph > sh - 8:
            y = by - PANEL_GAP - ph
        if y < 8:
            y = 8
        # Default capsule sits on the right edge; keep the wider panel on screen.
        x = bx
        if x + pw > sw - 8:
            x = max(8, sw - pw - 8)
        win.geometry(f"{pw}x{ph}+{x}+{y}")

    def _show_followers_panel(self) -> None:
        if self._dragging:
            return
        self._cancel_hover_jobs()
        self._row_text = []
        followers = list(self.state.get("followers") or [])
        if self.followers_win is not None:
            try:
                self.followers_win.destroy()
            except Exception:
                pass
            self.followers_win = None

        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        # Semi-transparent panel via window alpha — NO chromakey
        win.configure(bg="#15202B")
        try:
            win.attributes("-alpha", 0.92)
        except tk.TclError:
            pass
        win.bind("<Enter>", self._on_panel_enter)
        win.bind("<Leave>", self._on_panel_leave)

        outer = tk.Frame(win, bg="#15202B", highlightthickness=1, highlightbackground="#2F3336")
        outer.pack(fill="both", expand=True)

        daily = ensure_daily(self.state)
        today_n = int(daily.get("count") or 0)

        # Title row
        title_row = tk.Frame(outer, bg="#15202B", height=TITLE_H)
        title_row.pack(fill="x", padx=12, pady=(8, 0))
        title_row.pack_propagate(False)
        tk.Label(
            title_row,
            text="关注列表",
            bg="#15202B",
            fg="#FFFFFF",
            font=_tk_font(13, True),
            anchor="w",
        ).pack(side="left")
        right_meta = tk.Frame(title_row, bg="#15202B")
        right_meta.pack(side="right")
        tk.Label(
            right_meta,
            text=f"今日新增 {today_n}",
            bg="#15202B",
            fg="#1D9BF0" if today_n > 0 else "#8B98A5",
            font=_tk_font(11, False),
            anchor="e",
        ).pack(side="right")
        tk.Label(
            right_meta,
            text=f"共 {len(followers)} 人  ·  ",
            bg="#15202B",
            fg="#8B98A5",
            font=_tk_font(11, False),
            anchor="e",
        ).pack(side="right")

        # Scrollable rows + thin custom scrollbar
        list_h = min(MAX_ROWS, max(1, len(followers) or 1)) * ROW_H
        container = tk.Frame(outer, bg="#15202B", height=list_h)
        container.pack(fill="both", expand=True, padx=(4, 2), pady=(4, 8))
        container.pack_propagate(False)

        canvas = tk.Canvas(
            container, bg="#15202B", highlightthickness=0, bd=0, height=list_h
        )
        sb = ThinScrollbar(container, width=7, bg="#15202B", height=list_h)
        sb._command = canvas.yview
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(2, 4), pady=2)
        canvas.pack(side="left", fill="both", expand=True)

        rows_frame = tk.Frame(canvas, bg="#15202B")
        win_id = canvas.create_window((0, 0), window=rows_frame, anchor="nw")

        def _on_frame_configure(_e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(win_id, width=canvas.winfo_width())

        rows_frame.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win_id, width=e.width))

        def _on_mousewheel(e):
            delta = 0
            if getattr(e, "delta", 0):
                delta = -1 if e.delta > 0 else 1
            elif getattr(e, "num", None) == 4:
                delta = -1
            elif getattr(e, "num", None) == 5:
                delta = 1
            canvas.yview_scroll(delta, "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", _on_mousewheel)
        canvas.bind_all("<Button-5>", _on_mousewheel)

        self._panel_photos = []
        if not followers:
            tk.Label(
                rows_frame,
                text="暂无关注数据",
                bg="#15202B",
                fg="#8B98A5",
                font=_tk_font(12),
            ).pack(pady=16)
        else:
            for i, f in enumerate(followers):
                try:
                    self._build_follower_row(rows_frame, f)
                except Exception as ex:
                    try:
                        APP_DIR.mkdir(parents=True, exist_ok=True)
                        with open(APP_DIR / "panel_err.log", "a", encoding="utf-8") as fh:
                            fh.write(f"{i}: {ex}\n")
                    except Exception:
                        pass
                if i < 8:
                    try:
                        win.update_idletasks()
                    except Exception:
                        pass

        self.followers_win = win
        self._panel_alive = True
        self._position_panel()
        self._refit_row_text()
        win.lift()
        # background-prefetch a few avatars then refresh panel quietly
        self.root.after(50, lambda: self._prefetch_avatars(followers[:12]))

    def _pill(self, parent: tk.Misc, text: str, *, fill: str, fg: str, outline: str | None,
              command) -> tk.Label:
        """Label-based pill — Windows tk.Button ignores custom colors."""
        lbl = tk.Label(
            parent,
            text=text,
            font=_tk_font(9, True if fill != "#15202B" else False),
            fg=fg,
            bg=fill,
            cursor="hand2",
            padx=8,
            pady=4,
            bd=0,
            highlightthickness=1 if outline else 0,
            highlightbackground=outline or fill,
            highlightcolor=outline or fill,
        )
        lbl.bind("<Button-1>", lambda _e: command())
        lbl.bind("<Enter>", self._on_panel_enter)
        lbl.bind("<Leave>", self._on_panel_leave)
        return lbl

    def _icon_btn(self, parent: tk.Misc, kind: str, command) -> tk.Label:
        photo = ImageTk.PhotoImage(_row_icon(kind))
        self._panel_photos.append(photo)
        lbl = tk.Label(
            parent,
            image=photo,
            bg="#15202B",
            bd=0,
            cursor="hand2",
            highlightthickness=0,
        )
        lbl.bind("<Button-1>", lambda _e: command())
        lbl.bind("<Enter>", self._on_panel_enter)
        lbl.bind("<Leave>", self._on_panel_leave)
        return lbl

    def _track_row_text(self, lbl: tk.Label, full: str) -> None:
        self._row_text.append((lbl, full))

    def _refit_row_text(self) -> None:
        """Ellipsize name and handle to the width the row actually got."""
        import tkinter.font as tkfont

        try:
            self.root.update_idletasks()
        except Exception:
            return
        for lbl, full in getattr(self, "_row_text", []):
            try:
                width = int(lbl.winfo_width())
                if width < 12:
                    continue
                font = tkfont.Font(font=lbl.cget("font"))
                lbl.configure(text=_ellipsize_px(full, font, max(12, width - 2)))
            except Exception:
                continue

    def _build_follower_row(self, parent: tk.Frame, f: dict[str, Any]) -> None:
        row = tk.Frame(parent, bg="#15202B", height=ROW_H)
        row.pack(fill="x", padx=8, pady=0)
        row.pack_propagate(False)

        av_im = _fetch_avatar(str(f.get("id") or ""), str(f.get("profile_image_url") or ""))
        if av_im is None:
            av_im = _placeholder_avatar()
        photo = ImageTk.PhotoImage(av_im)
        self._panel_photos.append(photo)
        av = tk.Label(row, image=photo, bg="#15202B", bd=0)
        av.pack(side="left", padx=(0, 8), pady=((ROW_H - AVATAR_SZ) // 2, 0))

        # Buttons first (right) so the name uses the remaining width.
        uname = str(f.get("username") or "")
        name = str(f.get("name") or uname)
        btn_col = tk.Frame(row, bg="#15202B")
        btn_col.pack(side="right", padx=(6, 0), pady=((ROW_H - ICON_BOX) // 2, 0))
        open_btn = self._icon_btn(
            btn_col, "open",
            lambda u=uname: webbrowser.open(f"https://x.com/{u}"),
        )
        open_btn.pack(side="left", padx=(0, 6))
        follow_btn = self._icon_btn(
            btn_col, "follow",
            lambda u=uname: webbrowser.open(
                f"https://x.com/intent/follow?screen_name={u}"
            ),
        )
        follow_btn.pack(side="left", padx=(0, 6))
        tribute_btn = self._pill(
            btn_col, "上供",
            fill="#15202B", fg="#1D9BF0", outline="#1D9BF0",
            command=lambda ff=f: self._do_tribute(ff),
        )
        tribute_btn.pack(side="left")

        text_col = tk.Frame(row, bg="#15202B")
        text_col.pack(side="left", fill="both", expand=True)
        name_lbl = tk.Label(
            text_col, text=name, bg="#15202B", fg="#FFFFFF",
            font=_tk_font(12, True), anchor="w",
        )
        name_lbl.pack(fill="x", anchor="w", pady=(8, 0))
        handle_lbl = tk.Label(
            text_col, text=f"@{uname}", bg="#15202B", fg="#8B98A5",
            font=_tk_font(11, False), anchor="w",
        )
        handle_lbl.pack(fill="x", anchor="w")
        self._track_row_text(name_lbl, name)
        self._track_row_text(handle_lbl, f"@{uname}")

        for w in (row, text_col, btn_col, av, name_lbl, handle_lbl):
            w.bind("<Enter>", self._on_panel_enter)
            w.bind("<Leave>", self._on_panel_leave)

    def _prefetch_avatars(self, followers: list[dict[str, Any]]) -> None:
        if getattr(self, "_prefetching", False):
            return
        self._prefetching = True
        changed = False
        try:
            for f in followers:
                uid = str(f.get("id") or "")
                url = str(f.get("profile_image_url") or "")
                if not uid or not url:
                    continue
                cache = AVATAR_DIR / f"{uid}.jpg"
                if cache.exists():
                    continue
                im = _fetch_avatar(uid, url, network=True)
                if im is not None:
                    changed = True
            if changed and self._panel_alive and not getattr(self, "_prefetched_once", False):
                self._prefetched_once = True
                try:
                    self._show_followers_panel()
                except Exception:
                    pass
        finally:
            self._prefetching = False

    def _do_tribute(self, f: dict[str, Any]) -> None:
        uname = str(f.get("username") or "")
        name = str(f.get("name") or uname)
        note = "互关上供"
        # Optional one-line note via tiny dialog
        try:
            dlg = tk.Toplevel(self.root)
            dlg.title("上供备注")
            dlg.attributes("-topmost", True)
            dlg.configure(bg="#15202B")
            dlg.geometry("280x110")
            tk.Label(
                dlg, text=f"给 @{uname} 的上供备注（可空）", bg="#15202B", fg="#E7E9EA",
                font=_tk_font(11),
            ).pack(pady=(12, 4), padx=12, anchor="w")
            var = tk.StringVar(value="互关上供")
            entry = tk.Entry(dlg, textvariable=var, font=_tk_font(11), bg="#0F1419", fg="#FFF",
                             insertbackground="#FFF", relief="flat")
            entry.pack(fill="x", padx=12, pady=4)
            entry.focus_set()
            result: dict[str, str] = {"note": note, "ok": ""}

            def ok():
                result["note"] = var.get().strip() or "互关上供"
                result["ok"] = "1"
                dlg.destroy()

            def cancel():
                dlg.destroy()

            bf = tk.Frame(dlg, bg="#15202B")
            bf.pack(pady=8)
            tk.Button(bf, text="确认上供", command=ok, bg="#1D9BF0", fg="#FFF",
                      relief="flat", padx=10, font=_tk_font(10, True)).pack(side="left", padx=6)
            tk.Button(bf, text="取消", command=cancel, bg="#38444D", fg="#FFF",
                      relief="flat", padx=10, font=_tk_font(10)).pack(side="left", padx=6)
            dlg.transient(self.root)
            dlg.grab_set()
            self.root.wait_window(dlg)
            if not result["ok"]:
                return
            note = result["note"]
        except Exception:
            note = "互关上供"

        entry = {
            "at": datetime.now(TZ_SH).isoformat(timespec="seconds"),
            "username": uname,
            "name": name,
            "note": note,
            "kind": "tribute",
        }
        log = list(self.state.get("tribute_log") or [])
        log.append(entry)
        self.state["tribute_log"] = log
        try:
            save_state(self.state)
        except Exception:
            pass
        self._show_toast(f"@{uname}", "已记上供", note)
        # Keep panel open
        if not self._panel_alive:
            self._show_followers_panel()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    demo = "--demo-panel" in sys.argv or os.environ.get("XFAN_DEMO_PANEL") == "1"
    ensure_state()
    FanBallApp(demo_panel=demo).run()


if __name__ == "__main__":
    main()
