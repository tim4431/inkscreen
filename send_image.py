#!/usr/bin/env python3
"""ESP32‑EPD CLI – gray (4‑bit) *or* BW (2 ppB / 8 ppB)
=======================================================

* Default **gray 4‑bit / 2 pix‑per‑byte** payload.
* `--bw`  —— switch to monochrome; image auto‑dithered (Floyd–Steinberg).
* `--package {2ppB,8ppB}`  —— choose encoding when `--bw` is used.
  * **2ppB** (default) : two 4‑bit pixels per byte → firmware’s `n_epd_draw_monochrome()` expects this.
  * **8ppB**           : one 1‑bit bitmap byte holds eight pixels; needs much less RAM.

The FW’s single endpoint `/draw` is used; a header `bw: 1/0` tells it which
function to call.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import NamedTuple

import requests
from PIL import Image, ImageOps

# ───────────────────────── HTTP helpers ──────────────────────────


def http_get(host: str, path: str = "", timeout: int = 5) -> requests.Response:
    r = requests.get(f"http://{host}{path}", timeout=timeout)
    r.raise_for_status()
    return r


def http_post(host: str, path: str, **kw) -> requests.Response:
    r = requests.post(f"http://{host}{path}", timeout=5, **kw)
    r.raise_for_status()
    return r


# ──────────────────────── Board & data classes ───────────────────


class EpdInfo(NamedTuple):
    width: int
    height: int
    temperature: int

    @classmethod
    def from_response(cls, r: requests.Response) -> "EpdInfo":
        h = r.headers
        return cls(int(h["width"]), int(h["height"]), int(h["temperature"]))


class Dim(NamedTuple):
    width: int
    height: int


# ────────────────────────── Image helpers ─────────────────────────


def image_refit(img: Image.Image, bound: Dim) -> Image.Image:
    r = bound.width / bound.height
    w, h = img.size
    nw, nh = (int(r * h), h) if w / h > r else (w, int(w / r))
    return ImageOps.fit(img, (nw, nh)).resize(
        (bound.width, bound.height), Image.LANCZOS
    )


def dither_to_bw(img: Image.Image) -> Image.Image:
    return img.convert("1", dither=Image.FLOYDSTEINBERG).convert("L")


def pack_4bit(buf: bytes) -> bytes:
    out = bytearray(len(buf) // 2)
    for i in range(0, len(buf), 2):
        out[i // 2] = (buf[i] // 17) << 4 | (buf[i + 1] // 17)
    return bytes(out)


def pack_1bit(buf: bytes, thresh: int = 128) -> bytes:
    out = bytearray(len(buf) // 8)
    for i in range(0, len(buf), 8):
        b = 0
        for j in range(8):
            b = (b << 1) | (0 if buf[i + j] > thresh else 1)
        out[i // 8] = b
    return bytes(out)


# ───────────────────────── upload routine ────────────────────────


def draw_image(
    host: str,
    path: Path,
    *,
    bw: bool,
    package: str,
    clear: bool,
    preview: bool,
    x: int,
    y: int,
    w: int | None,
    h: int | None,
    max_usage: float,
) -> None:
    info = EpdInfo.from_response(http_get(host))
    free = int(http_get(host, "/free").text.strip())
    # print(f"Free PSRAM: {free} B")
    # x, y = y, x

    w = w or (info.width - x)
    h = h or (info.height - y)
    if x + w > info.width or y + h > info.height:
        raise ValueError("ROI out of bounds")

    img = Image.open(path).convert("L")
    img = image_refit(img, Dim(w, h))

    # choose packing
    if bw:
        img = dither_to_bw(img)
        encode = pack_1bit if package == "8ppB" else pack_4bit
        bpp = 0.125 if package == "8ppB" else 0.5
    else:
        if package != "2ppB":
            raise ValueError("Package must be 2ppB when not in BW mode")
        encode = pack_4bit
        bpp = 0.5

    if preview:
        print(f"Previewing {package} image {img.size} @ {x},{y}")
        img.show()

    usable = int(free * max_usage)
    max_pix = int(usable / bpp)
    patch_h = min(max(max_pix // w, 2), h)
    if patch_h % 2:
        patch_h -= 1
    if patch_h < 2:
        raise RuntimeError("ROI too wide for PSRAM")

    # print(f"Uploading {'BW' if bw else 'GRAY'} {package} in {patch_h}-row patches…")

    for y_off in range(0, h, patch_h):
        ph = min(patch_h, h - y_off)
        patch = img.crop((0, y_off, w, y_off + ph))
        payload = encode(patch.tobytes())
        hdr = {
            "width": str(w),
            "height": str(ph),
            "x": str(x),
            "y": str(y + y_off),
            "clear": "1" if clear and y_off == 0 else "0",
            "bw": "1" if package == "8ppB" else "0",
        }
        http_post(host, "/draw", headers=hdr, data=payload)
        # print(f"patch {y + y_off}->{y + y_off + ph} OK")
    # print("Done")


# ─────────────────────────── CLI ─────────────────────────────────


def cli() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ESP32‑EPD uploader")
    p.add_argument("hostname")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("clear")
    sub.add_parser("info")
    sub.add_parser("free")

    d = sub.add_parser("draw")
    d.add_argument("file", type=Path)
    d.add_argument("--bw", action="store_true", help="monochrome mode")
    d.add_argument(
        "--package",
        choices=["2ppB", "8ppB"],
        default="2ppB",
        help="pixel packing when --bw (default 2ppB)",
    )
    d.add_argument("--x", type=int, default=0)
    d.add_argument("--y", type=int, default=0)
    d.add_argument("--width", type=int)
    d.add_argument("--height", type=int)
    d.add_argument("-c", "--clear", action="store_true")
    d.add_argument("--preview", action="store_true")
    d.add_argument("--max-usage", type=float, default=0.8)
    return p.parse_args()


# ─────────────────────────── Main ────────────────────────────────


def main() -> None:
    a = cli()
    if a.cmd == "clear":
        http_post(a.hostname, "/clear")
        return
    if a.cmd == "info":
        print(EpdInfo.from_response(http_get(a.hostname)))
        return
    if a.cmd == "free":
        print(http_get(a.hostname, "/free").text.strip())
        return

    draw_image(
        a.hostname,
        a.file,
        bw=a.bw,
        package=a.package,
        clear=a.clear,
        preview=a.preview,
        x=a.x,
        y=a.y,
        w=a.width,
        h=a.height,
        max_usage=a.max_usage,
    )


if __name__ == "__main__":
    main()
