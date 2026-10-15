#!/usr/bin/env python3
"""Builds the demo soundtrack (intro track + 8 mood excerpts + outro track), the per-frame
spectrum data and the mood table used by the Remotion demo. Uses only the bgm-music scripts.
  python make_audio.py            (writes public/demo.mp3, src/spectrum.json, src/moods.json)"""
import json, os, subprocess, sys, tempfile
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, '..', 'skills', 'bgm-music', 'scripts')
sys.path.insert(0, S)
import bgm, evaluate

FPS, SEG, EXC = 30, 3.5, 8.0           # fps, seconds per mood excerpt, excerpt start
tmp = tempfile.mkdtemp()
def render(mood, dur, seed, name, **kw):
    out = os.path.join(tmp, name + '.wav')
    cmd = [sys.executable, os.path.join(S, 'bgm.py'), '--mood', mood, '--duration', str(dur), '--seed', str(seed), '--out', out]
    for k, v in kw.items():
        cmd += [f'--{k}', str(v)]
    info = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)
    return out, info

parts, moods = [], []
a, _ = render('uplifting', 14, 1, 'intro', key='C', bpm=120)
parts.append(a)
for i, m in enumerate(sorted(bgm.MOODS, key=lambda k: ['uplifting', 'corporate', 'playful', 'lofi', 'calm', 'ambient', 'cinematic', 'tense'].index(k))):
    w, info = render(m, 20, 2, 'm_' + m)
    ex = os.path.join(tmp, 'x_' + m + '.wav')
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', str(EXC), '-t', str(SEG), '-i', w, '-af',
                    'afade=t=in:d=0.12,afade=t=out:st=%s:d=0.2' % (SEG - 0.2), ex], check=True)
    parts.append(ex)
    r = evaluate.evaluate(w, m, info['key'], info['scale'], info['bpm'], False)
    moods.append(dict(mood=m, bpm=round(info['bpm']), key=f"{info['key']} {info['scale']}", score=r['score']))
b, _ = render('uplifting', 14, 3, 'outro', key='C', bpm=120)
parts.append(b)
lst = os.path.join(tmp, 'list.txt')
open(lst, 'w').write(''.join(f"file '{p.replace(chr(92), '/')}'\n" for p in parts))
cat = os.path.join(tmp, 'cat.wav')
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', cat], check=True)
os.makedirs(os.path.join(HERE, 'public'), exist_ok=True)
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', cat, '-c:a', 'libmp3lame', '-b:a', '256k', os.path.join(HERE, 'public', 'demo.mp3')], check=True)

x = evaluate.load(cat).mean(axis=0); SR = 44100
nb, n = 48, 4096
centers = np.geomspace(70, 12000, nb)
f = np.fft.rfftfreq(n, 1 / SR); w = np.hanning(n)
total = int(len(x) / SR * FPS)
rows = []
for i in range(total):
    c = int(i / FPS * SR); seg = x[max(0, c - n // 2): c + n // 2]
    if len(seg) < n:
        seg = np.pad(seg, (0, n - len(seg)))
    rows.append(np.interp(centers, f, np.abs(np.fft.rfft(seg * w))))
a_ = np.log10(np.array(rows) + 1e-6) + 0.6 * np.log10(centers / 70)[None, :]
lo, hi = np.percentile(a_, 8), np.percentile(a_, 99.5)
a_ = np.clip((a_ - lo) / (hi - lo), 0, 1)
json.dump(np.round(a_, 3).tolist(), open(os.path.join(HERE, 'src', 'spectrum.json'), 'w'))
json.dump(dict(moods=moods, frames=total, seconds=round(len(x) / SR, 2)), open(os.path.join(HERE, 'src', 'moods.json'), 'w'), indent=1)
print(total, 'frames', round(len(x) / SR, 2), 's', [m['score'] for m in moods])
