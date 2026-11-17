"""Surprise camera: store what the model could not predict.

A static camera's world model is its own background. Predict the next frame as a
slowly-adapting background estimate; the residual is surprise. Frames below the
threshold are not stored at all — only the moments the camera did not expect,
plus a sparse keyframe spine so the gaps are reconstructible.

    python3 tools/surprise.py demo/clip.mp4

Prints frame statistics, the surprise curve, the detected event windows, and a
byte comparison against storing every frame.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess

import numpy as np
from PIL import Image


def frames(path: str, w: int, h: int):
    """Decode with ffmpeg to raw greyscale — no OpenCV, no OpenCV-shaped install."""
    cmd = ["ffmpeg", "-loglevel", "error", "-i", path,
           "-vf", f"scale={w}:{h}", "-pix_fmt", "gray", "-f", "rawvideo", "-"]
    p = subprocess.run(cmd, capture_output=True, check=True)
    buf = np.frombuffer(p.stdout, dtype=np.uint8)
    n = len(buf) // (w * h)
    return buf[: n * w * h].reshape(n, h, w).astype(np.float32)


def jpeg_bytes(arr: np.ndarray, quality=55) -> int:
    im = Image.fromarray(arr.astype(np.uint8))
    b = io.BytesIO()
    im.save(b, format="JPEG", quality=quality)
    return len(b.getvalue())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--w", type=int, default=320)
    ap.add_argument("--h", type=int, default=180)
    ap.add_argument("--alpha", type=float, default=0.02, help="background adaptation rate")
    ap.add_argument("--thr", type=float, default=0.0,
                    help="absolute threshold; 0 = adaptive (recommended)")
    ap.add_argument("--keyframe", type=int, default=60, help="keyframe spine interval")
    a = ap.parse_args()

    f = frames(a.video, a.w, a.h) / 255.0
    n = len(f)
    bg = f[0].copy()

    # Pass 1: score every frame as "mass of meaningfully changed pixels".
    # A plain mean over the whole frame is diluted by the 95% of pixels that are
    # wall: a person crossing a 320x180 corridor scored 0.017, below any sane
    # threshold, and the first run reported 97.9% savings while storing nothing.
    # Subtracting a floor first and summing only the excess is much closer to
    # what a human would call "something happened".
    scores, kept_frames = [], []
    for i in range(n):
        r = np.abs(f[i] - bg)
        scores.append(float(np.clip(r - 0.06, 0, None).mean()))
        kept_frames.append(f[i].copy())
        if scores[-1] < 0.02:
            bg = (1 - a.alpha) * bg + a.alpha * f[i]

    # Pass 2: adaptive threshold unless one was given. Median is robust to both
    # the long empty stretch and the long event.
    med = float(np.median(scores))
    thr = a.thr if a.thr > 0 else max(med * 3.0, 0.0008)
    a.thr = thr

    surf, stored = [], []
    for i in range(n):
        surf.append(scores[i])
        stored.append(scores[i] > thr or i % a.keyframe == 0 or i == 0)

    peak = max(surf)
    idx = [i for i, k in enumerate(stored) if k]
    all_bytes = sum(jpeg_bytes(f[i]) for i in range(n))
    stored_bytes = sum(jpeg_bytes(f[i]) for i in idx)

    # event windows: contiguous runs above threshold
    events, run = [], None
    for i, s in enumerate(surf):
        if s > a.thr and run is None:
            run = i
        elif s <= a.thr and run is not None:
            events.append((run, i - 1)); run = None
    if run is not None:
        events.append((run, n - 1))

    ramp = " .:-=+*#%@"
    lo, hi = min(surf), max(surf)
    span = (hi - lo) or 1.0
    curve = "".join(ramp[min(9, int((s - lo) / span * 9))] for s in surf)

    out = {
        "frames": n, "threshold": a.thr,
        "frames_stored": len(idx), "frames_skipped": n - len(idx),
        "store_ratio": round(len(idx) / n, 3),
        "bytes_all": all_bytes, "bytes_stored": stored_bytes,
        "saved_pct": round(100 * (1 - stored_bytes / all_bytes), 1),
        "peak_surprise": round(peak, 4),
        "events": [{"start": s, "end": e, "frames": e - s + 1} for s, e in events],
        "surprise": [round(s, 4) for s in surf],
    }
    print(f"  surprise curve  |{curve}|")
    print(f"  frames          {n} total -> {len(idx)} stored ({out['store_ratio']*100:.0f}%)")
    print(f"  bytes           {all_bytes//1024} KB all  ->  {stored_bytes//1024} KB stored  "
          f"({out['saved_pct']}% saved)")
    print(f"  peak surprise   {peak:.4f} at frame {surf.index(peak)}")
    print(f"  events          {[(e['start'], e['end']) for e in out['events']]}")

    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "assets"), exist_ok=True)
    dst = os.path.join(os.path.dirname(__file__), "..", "assets", "result.json")
    with open(dst, "w") as fh:
        json.dump(out, fh, indent=1)
    print(f"  wrote {os.path.normpath(dst)}")


if __name__ == "__main__":
    main()
