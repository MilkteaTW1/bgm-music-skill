# Neural tier: ACE-Step 1.5 (optional, opt-in)

Use when the user wants fuller, more realistic music than the procedural composer gives,
has an NVIDIA GPU, and **approves a multi-GB model download** (ask first; downloads
need explicit permission).

## Facts (from the project README/install guide, Oct 2026 - verify before relying)

- Repo: https://github.com/ACE-Step/ACE-Step-1.5 - MIT license, trained on licensed /
  royalty-free data, commercial use allowed.
- Python 3.11-3.12, `uv` for setup, ffmpeg required.
- VRAM: >= 4 GB DiT-only, >= 6 GB with the LLM planner. ~10 GB disk for core models.
- Setup: `git clone` the repo, `uv sync`, then `uv run acestep` (Gradio UI at
  localhost:7860, models download on first run) or `uv run acestep-api` (REST on :8001).
- Weak spots per the authors: seed-to-seed quality variance, coarse fine-grained control,
  vocals. For BGM use instrumental prompts (no lyrics, or "[instrumental]").

## Prompt recipe for BGM

`<genre/mood>, <tempo> bpm, <key>, <instruments>, instrumental, no vocals, <role>`
e.g. `uplifting corporate pop, 110 bpm, C major, plucked synth arpeggio, warm pad,
soft four-on-the-floor kick, instrumental, no vocals, background for product demo`.
Generate 3 seeds, **evaluate each with `scripts/evaluate.py`** (pass --key/--bpm you asked
for), keep the best, then trim/loop/duck with `scripts/mix_under_voice.py`.

## When not to bother

Short UI stingers, anything that must hit an exact duration/bar grid, or machines without
a CUDA GPU: the procedural composer is faster, deterministic and exact on length.

## Other open-source options surveyed

| Model | Good for | Caveat |
|---|---|---|
| ACE-Step 1.5 | full tracks, low VRAM | variance, coarse control |
| MusicGen (Meta) | instrumental clips <= 30 s | weights CC-BY-NC: not for commercial work |
| Stable Audio Open / 3 | loops, ambience, SFX, long clips | community license revenue limits; heavier VRAM |
| YuE | lyrics-to-song | 16 GB+ VRAM, slow |

## Measured (RTX 3050 8 GB, 2026-10-15)

- Setup used: `git clone` + `uv sync` into `~/ace-step-1.5` (the wrapper's default; override with `ACE_STEP_DIR`) (7 GB venv, 9.4 GB
  checkpoints, DiT-only turbo model, `scripts/ace_generate.py` is the wrapper).
- Same "uplifting, C major, 113 bpm" brief, after post-processing, evaluator scores:
  ACE seeds 91 / 74 / 91 (raw, unprocessed first output: 81, brightness BAD);
  procedural 99.6. Lofi D dorian: ACE 55 / 73 / 71 vs procedural 98.
- Reading: ACE is not "better" by these metrics, which only measure technical fit
  (key, tempo, loudness, harshness, seams) and give no credit for richer timbre or
  arrangement. ACE misses on key purity (jazzy chords), runs short, and is bright and
  bass-heavy raw. Decide by listening; the metrics tell you which ACE seed is cleanest.
- The brightness/spectrum targets were tuned on the procedural engine, so shelving ACE
  to meet them is partly circular; treat its score as relative between seeds.
