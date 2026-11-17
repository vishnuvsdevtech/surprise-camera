"""Generate a controlled test clip: an empty corridor, then someone walks through.

A synthetic clip is the right test here because the ground truth is exact — we
know precisely which frames contain the only thing worth storing.
"""
from __future__ import annotations

import os
import subprocess

from PIL import Image, ImageDraw

W, H, FPS, N = 320, 180, 12, 144
OUT = os.path.join(os.path.dirname(__file__), "..", "demo")


def frame(i: int) -> Image.Image:
    im = Image.new("RGB", (W, H), (18, 20, 22))
    d = ImageDraw.Draw(im)
    # floor + wall perspective
    d.polygon([(0, H), (W, H), (W - 70, 96), (70, 96)], fill=(30, 33, 36))
    d.line([(70, 96), (0, H)], fill=(52, 56, 60), width=2)
    d.line([(W - 70, 96), (W, H)], fill=(52, 56, 60), width=2)
    # ceiling pipes
    for y in (30, 44, 56):
        d.line([(0, y), (W, y + 6)], fill=(40, 44, 48), width=3)
    # a door on the back wall
    d.rectangle([236, 110, 286, 176], fill=(24, 26, 28), outline=(56, 60, 64))
    # a status LED that blinks (a small, legitimate "surprise")
    if (i // 18) % 2 == 0:
        d.ellipse([150, 70, 156, 76], fill=(120, 60, 40))
    # the event: a person crossing between frames 54 and 108
    if 54 <= i <= 108:
        t = (i - 54) / 54.0
        x = int(20 + t * (W - 60))
        y = int(H - 54 - 8 * abs(0.5 - t) * 2)
        d.ellipse([x, y - 26, x + 16, y - 10], fill=(196, 198, 202))   # head
        d.polygon([(x - 4, y - 10), (x + 20, y - 10), (x + 16, y + 26), (x, y + 26)],
                  fill=(170, 174, 180))                                 # body
    return im


def main():
    os.makedirs(OUT, exist_ok=True)
    tmp = os.path.join(OUT, "_frames")
    os.makedirs(tmp, exist_ok=True)
    for i in range(N):
        frame(i).save(os.path.join(tmp, f"{i:04d}.png"))
    mp4 = os.path.join(OUT, "clip.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS),
        "-i", os.path.join(tmp, "%04d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "30", mp4,
    ], check=True)
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)
    print(f"{mp4}  {os.path.getsize(mp4)//1024} KB  {N} frames @ {FPS} fps")


if __name__ == "__main__":
    main()
