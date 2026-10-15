#!/usr/bin/env python3
"""Render every mood (and a loop + a short cut) and print the evaluator score table.
Use after changing bgm.py to check for regressions:  python bench.py [outdir]"""
import json, os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
import bgm, evaluate

out = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
os.makedirs(out, exist_ok=True)
cases = [(m, 45, False) for m in sorted(bgm.MOODS)] + [('lofi', 30, True), ('uplifting', 15, False)]
rows = []
for mood, dur, loop in cases:
    p = os.path.join(out, f"{mood}_{dur}{'_loop' if loop else ''}.wav")
    cmd = [sys.executable, os.path.join(here, 'bgm.py'), '--mood', mood, '--duration', str(dur), '--out', p]
    if loop:
        cmd.append('--loop')
    info = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)
    cfg = bgm.MOODS[mood]
    r = evaluate.evaluate(p, mood, info['key'], info['scale'], info['bpm'], loop, p[:-4] + '.png')
    rows.append((mood, dur, loop, r))
    c = r['criteria']
    print(f"{mood:10} {dur:>3}s {'loop' if loop else '    '} score {r['score']:5.1f} | " +
          ' '.join(f"{k[:4]}={v['score']:.2f}" for k, v in c.items()), flush=True)
print('mean', round(sum(r['score'] for *_, r in rows) / len(rows), 1), 'min', min(r['score'] for *_, r in rows))
