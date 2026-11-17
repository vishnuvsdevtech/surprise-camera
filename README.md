# Surprise Camera

**Live:** https://vishnuvsdevtech.github.io/surprise-camera/

An NVR that stores **novelty, not time**. A background model predicts each frame;
what it fails to predict is kept, with a sparse keyframe spine so the gaps stay
reconstructible.

## Measured, on a controlled clip

A synthetic corridor, 144 frames at 12 fps, empty except for one person crossing
at frames **54–108**:

```
surprise curve  |                                                      @%%%%%%%%%%####...%%%                          |
frames          144 total -> 57 stored (40%)
bytes           143 KB all  ->  56 KB stored  (60.4% saved)
peak surprise   0.0097 at frame 54
events          [(54, 108)]
```

The detection window is exactly the ground truth, peaking at the frame of entry.
The modest 60 % saving is because the event occupies 38 % of this clip — on a real
camera the interesting fraction is nearer 1 %, where the same arithmetic lands
near 99 %.

## The trap, recorded because it is instructive

The first implementation scored the **mean** absolute difference over the whole
frame. A person crossing a 320×180 corridor scored `0.017` — the wall outvoted
them — so the threshold sat above the peak and the tool reported **97.9 % saved
while storing nothing at all**. A storage system that stores nothing looks perfect
on every metric except the one that matters.

Fix: subtract a noise floor and sum only the excess (change *mass*), then set the
threshold adaptively at three times the median.

## Use it on real footage

```bash
python3 tools/make_clip.py                  # regenerate the test clip
python3 tools/surprise.py path/to/take.mp4  # any video ffmpeg can read
```

Dependencies: `numpy`, `pillow`, `ffmpeg`. No OpenCV — frames are decoded as raw
greyscale through an ffmpeg pipe, which keeps the install trivial.

## What this is not

- **Not a codec.** Skipped frames are not reconstructed from neighbours; there is
  a keyframe spine and that is all.
- **Not lighting-ro invariant.** A light switching on is genuine surprise and will
  be stored — correctly — but a slow sunset keeps the model confused until it adapts.
- **Not a retention policy.** "Store only surprise" still needs a rule for when
  surprise is irrelevant (a flag moving in wind, a TV in frame).
