#!/usr/bin/env python3
"""One-shot: give it a video (or a Remotion duration) and get it scored.

  # finished video (optionally with narration): detects scene cuts, composes music that
  # changes section on those cuts, picks the best of N seeds by evaluator, ducks under
  # the narration, writes the scored video
  python score_video.py --video out/video.mp4 --brief "product demo for a SaaS dashboard" --out out/scored.mp4
  python score_video.py --video out/video.mp4 --voice public/narration.wav --out out/final.mp4

  # Remotion / Hyperframes project: just produce the track, sized to the composition
  python score_video.py --frames 900 --fps 30 --brief "kids game trailer" --audio-out public/bgm.mp3
  # then in the composition:  <Audio src={staticFile('bgm.mp3')} volume={0.4} />

Prints a JSON report (mood, seed, score, cuts, output). Exit code 2 if no candidate
reached --min-score (the best one is still written so you can decide).
"""
import argparse, json, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bgm, evaluate  # noqa: E402

MOOD_WORDS = [  # first match wins
    ('tense', r'horror|bug|alert|error|danger|security|thriller|mystery|warning|incident|scary'),
    ('cinematic', r'trailer|cinematic|epic|launch|announce|reveal|film|brand film|keynote|story'),
    ('playful', r'kids?|game|fun|cartoon|playful|toy|party|cute|emoji|quirky|zoo|monster'),
    ('lofi', r'lo-?fi|study|chill|coding|relax|cozy|vlog|casual|podcast'),
    ('ambient', r'meditat|sleep|spa|ambient|calm focus|nature|wellness|yoga'),
    ('calm', r'tutorial|explain|walkthrough|onboarding|how[- ]to|education|course|docs'),
    ('uplifting', r'promo|social|reel|tiktok|short|ad\b|celebrat|win|growth|startup|energetic|upbeat'),
    ('corporate', r'demo|product|saas|dashboard|business|b2b|feature|enterprise|pitch|corporate|update'),
]


def pick_mood(brief):
    b = (brief or '').lower()
    for mood, pat in MOOD_WORDS:
        if re.search(pat, b):
            return mood
    return 'corporate'


def probe_duration(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', path],
                       capture_output=True, text=True, check=True)
    return float(json.loads(r.stdout)['format']['duration'])


def detect_cuts(video, dur, thresh=0.3, max_cuts=4, min_gap=4.0):
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', video, '-vf',
                        f"select='gt(scene,{thresh})',showinfo", '-an', '-f', 'null', '-'],
                       capture_output=True, text=True)
    times = [float(t) for t in re.findall(r'pts_time:([\d.]+)', r.stderr)]
    keep, last = [], 0.0
    for t in times:
        if t - last >= min_gap and dur - t >= min_gap:
            keep.append(round(t, 2))
            last = t
    if len(keep) > max_cuts:      # keep the evenly spread subset
        step = len(keep) / max_cuts
        keep = [keep[int(i * step)] for i in range(max_cuts)]
    return keep


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--video')
    ap.add_argument('--voice', help='narration to duck under')
    ap.add_argument('--frames', type=int, help='composition length in frames (no video yet)')
    ap.add_argument('--fps', type=float, default=30)
    ap.add_argument('--duration', type=float)
    ap.add_argument('--brief', default='', help='what the video is; used to choose the mood')
    ap.add_argument('--mood', choices=sorted(bgm.MOODS))
    ap.add_argument('--key')
    ap.add_argument('--bpm', type=float, help='target tempo (snaps so whole bars fill the duration)')
    ap.add_argument('--cuts', help='comma list of seconds; default: auto-detect from --video')
    ap.add_argument('--no-cuts', action='store_true')
    ap.add_argument('--tries', type=int, default=4, help='seeds to try; best evaluator score wins')
    ap.add_argument('--min-score', type=float, default=85)
    ap.add_argument('--lufs', type=float, default=-18)
    ap.add_argument('--out', help='scored video (needs --video) or mixed audio (needs --voice)')
    ap.add_argument('--audio-out', help='write just the music track here (.mp3/.wav)')
    a = ap.parse_args()

    dur = a.duration or (a.frames / a.fps if a.frames else None) or (probe_duration(a.video) if a.video else None)
    if not dur:
        sys.exit('need --video, --frames/--fps or --duration')
    mood = a.mood or pick_mood(a.brief)
    if a.cuts:
        cuts = [float(x) for x in a.cuts.split(',')]
    elif a.video and not a.no_cuts:
        cuts = detect_cuts(a.video, dur)
    else:
        cuts = []
    # at least ~16 bars of material per cut to feel like a section; very short pieces get none
    cuts = [c for c in cuts if dur >= 12]

    tmp = tempfile.mkdtemp()
    best = None
    for seed in range(1, a.tries + 1):
        mix, info = bgm.compose(mood, dur, a.key, None, a.bpm, seed, False, False, False, cuts or None)
        wav = os.path.join(tmp, f'cand{seed}.wav')
        bgm.write_wav(wav, bgm.master(mix, False, a.lufs, os.path.join(tmp, f'm{seed}')))
        r = evaluate.evaluate(wav, mood, info['key'], info['scale'], info['bpm'], False)
        print(f'seed {seed}: score {r["score"]}', file=sys.stderr)
        if best is None or r['score'] > best[0]:
            best = (r['score'], seed, wav, info, r)
        if r['score'] >= 95:
            break
    score, seed, wav, info, r = best
    music = a.audio_out or os.path.join(tmp, 'music.wav')
    if a.audio_out and not a.audio_out.lower().endswith('.wav'):
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', wav, '-c:a', 'libmp3lame', '-b:a', '256k', music], check=True)
    else:
        import shutil
        shutil.copy(wav, music)
    out = None
    if a.out and (a.video or a.voice):
        cmd = [sys.executable, os.path.join(HERE, 'mix_under_voice.py'), '--music', music, '--out', a.out]
        if a.video:
            cmd += ['--video', a.video]
        if a.voice:
            cmd += ['--voice', a.voice]
        subprocess.run(cmd, check=True, capture_output=True)
        out = a.out
    report = dict(mood=mood, seed=seed, score=score, bpm=info['bpm'], key=info['key'], scale=info['scale'],
                  duration=dur, cuts=cuts, music=music if a.audio_out or out else None, output=out,
                  weak=[k for k, v in r['criteria'].items() if v['score'] < 0.85])
    print(json.dumps(report, ensure_ascii=False))
    sys.exit(0 if score >= a.min_score else 2)


if __name__ == '__main__':
    main()
