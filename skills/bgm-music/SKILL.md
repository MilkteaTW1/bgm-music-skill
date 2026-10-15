---
name: bgm-music
description: "Add a measured-quality soundtrack to ANY video: use whenever a video is being created, generated, rendered or edited (Remotion, Hyperframes, Veo, Sora, Runway, HeyGen, ffmpeg, screen recordings, demos, trailers, reels) and has no music, or when the user asks for background music, BGM, a soundtrack, a loop, 配樂, 背景音樂, 做音樂. Composes offline (8 moods, no downloads), fits the exact video length, changes sections on scene cuts, self-evaluates and iterates, and ducks under narration. Optional neural tier (ACE-Step) for richer music. For voice/TTS see voicebox."
metadata:
  version: 1.0.0
---

# bgm-music

Make background music that is on-key, on-tempo, correctly loud, not harsh, and the right
length - then prove it with measurements before handing it over.

Scripts live in `scripts/` next to this file (resolve with the skill's directory,
usually `~/.claude/skills/bgm-music/scripts`). Needs only Python 3 + numpy + ffmpeg.

## Honest limits - read first

- You cannot hear audio. "Good" here means **measured** good: key, tempo, loudness,
  spectral balance, harshness, dynamics, seams. A human listen is still the final judge.
- The procedural composer makes clean, tasteful, *generic* production-music: pads,
  plucks, simple drums, a catchy 4-bar melody. It will not sound like a Suno track.
  It is ideal for BGM under voice/UI, which is most video work.
- For richer, more "produced" music use the neural tier (ACE-Step 1.5, optional ~17 GB
  install, 6-8 GB VRAM). See `references/neural-tier.md` for setup. Always ask before downloading.

## Fast path: score a video (use this first)

```bash
S=~/.claude/skills/bgm-music/scripts
python $S/score_video.py --video out/video.mp4 [--voice vo.wav] --brief "<what it is>" --out out/final.mp4
python $S/score_video.py --frames 900 --fps 30 --brief "<what it is>" --audio-out public/bgm.mp3   # Remotion
```
Mood from the brief, exact length, sections on detected scene cuts (`--cuts 6,14` to
set them), best of 4 seeds by evaluator, ducked under narration, JSON report (exit 2 if
nothing reached 85). The video skill and gsap-remotion skill call this automatically.
The manual workflow below is for custom control.

## Workflow

1. **Brief.** Get: mood/genre, total duration (match the video length), loop or one-shot,
   whether voiceover plays over it, hard sync points (optional). Default to the mood
   that fits the content (product demo -> `corporate`/`uplifting`, tutorial -> `calm`/`lofi`,
   trailer -> `cinematic`, bug/horror/alert -> `tense`, kids/game -> `playful`).
2. **Compose.**
   ```bash
   python scripts/bgm.py --mood corporate --duration 45 --out bgm.wav            # one-shot with ring-out
   python scripts/bgm.py --mood lofi --duration 32 --loop --out loop.wav          # seamless loop
   python scripts/bgm.py --mood uplifting --duration 30 --key D --seed 4 --lufs -20 --out bgm.mp3
   ```
   Tempo snaps so whole bars fill the duration exactly (video-length safe). Same seed =
   same track; change `--seed` for a different melody, `--key`/`--scale`/`--bpm` to taste.
3. **Evaluate - mandatory.** Pass the same facts you composed with:
   ```bash
   python scripts/evaluate.py bgm.wav --mood corporate --key G --scale major --bpm 104 \
       --spectrogram bgm.png [--loop]
   ```
   Then **Read the PNG**: look for solid bright vertical/horizontal walls above ~8 kHz
   (hiss), gaps, or flat sections. Metrics miss things the picture shows.
4. **Iterate.** If score < 85 or any line is WEAK/BAD, apply the fix printed next to it
   (see table), re-render, re-evaluate. Stop at >= 85 with no BAD, or after ~4 rounds
   and say what remains. Never claim quality you did not measure.
5. **Deliver / mix.**
   ```bash
   python scripts/mix_under_voice.py --voice vo.wav --music bgm.wav --out mixed.wav
   python scripts/mix_under_voice.py --video clip.mp4 --voice vo.wav --music bgm.wav --out final.mp4
   python scripts/mix_under_voice.py --video clip.mp4 --music bgm.wav --out scored.mp4
   ```
   Music is ducked ~12 dB under speech, faded in/out, normalised to -16 LUFS.

For Remotion: render `bgm.mp3` into `public/`, use `<Audio src={staticFile('bgm.mp3')}
volume={0.35} loop />`; the generated file is already loudness-managed.

## Neural tier (ACE-Step) quick use

```bash
cd ~/ace-step-1.5 && .venv/Scripts/python ~/.claude/skills/bgm-music/scripts/ace_generate.py   --prompt "uplifting corporate pop, plucked synth arpeggio, warm pad, soft kick"   --duration 30 --bpm 113 --key "C major" --n 3 --out bgm_ace.wav
```
Renders N seeds, post-processes (trims trailing silence, tames highs, fades, -18 LUFS),
evaluates each and keeps the best. About 1-2 min per seed after the first model load.
Measured on an RTX 3050 8 GB: output runs 2-5 s shorter than requested and quality varies a
lot by seed (74-96 on the same prompt), so always keep best-of-N and let
`mix_under_voice.py` loop/trim. Prefer procedural when exact length, loop seams or
guaranteed key matter; prefer ACE when richer timbre and arrangement matter and a
human will listen to confirm.

## What the evaluator checks (and the fix)

| Criterion | Pass looks like | Typical fix |
|---|---|---|
| loudness | -21..-15 LUFS | `--lufs -18` |
| headroom | peak <= -1 dBFS, no clipping | lower `--lufs` |
| brightness | 6-16 kHz is 38-62 dB below 250-2k | hats/noise too hot: lower drum noise gain, lower `tone_hz` in `master()` |
| spectrum | band shares in range (no mud, no boom) | change pad register / bass gain / reverb amount in the mood |
| key | >= 90% of tonal energy in the scale | wrong key/scale passed, or out-of-scale melody notes |
| rhythm | tempo matches, clear pulse | raise drums/arp; ambient/calm/cinematic are allowed weak pulse |
| dynamics | 2-9 dB level range over the piece | too flat: more section contrast; too jumpy: less |
| variety | not frozen, not chaotic | change `--seed`, longer duration adds sections |
| stereo | L/R correlation 0.25-0.97 | too mono: detune/pan; phasey: reduce reverb width |
| ends | fades out / loop seam inaudible | use `--loop` for loops; ring-out is automatic |

A critical failure (wrong key, clipping, way off loudness, hiss) caps the score at 55-100
proportionally, so one disaster cannot hide behind averages.

## Regression bench

After editing `bgm.py`, run `python scripts/bench.py <outdir>`. It renders every mood
(plus a loop and a 15 s cut), prints scores, and writes spectrogram PNGs. Baseline when
this skill was written: mean 97.5, min 89.9 (ambient; pulse is intentionally weak).
Negative controls the evaluator must keep failing: white noise (~41), clipped sine (~41),
random notes (~60), wrong key (capped).

## Extending

- New mood = one dict in `MOODS` (scale, bpm, 4-chord `prog` as scale degrees, drum
  pattern name, keys/lead voice, reverb, brightness). Drum grids live in `DRUMS`
  (16 steps/bar; `x` hit).
- Lessons already paid for: noise percussion must be low-passed before reverb or the
  track hisses (found only via spectrogram); chord voicings must be voice-led or pads
  jump around; the melody uses chord tones on strong beats with an A-A-B-A' phrase form;
  stereo width comes from detuned pad voices and a partly-correlated reverb IR.
- Ideas not done yet: key modulation for the last chorus, bass-line walking variants,
  sample-accurate sync points (`--hit-at`), per-section stems export.
