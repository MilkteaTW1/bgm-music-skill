#!/usr/bin/env python3
"""Generate instrumental BGM with ACE-Step 1.5 (DiT-only, fits ~6-8 GB VRAM).

Run with the ACE-Step venv's python, not the system one:
  ~/ace-step-1.5/.venv/Scripts/python ace_generate.py --prompt "uplifting corporate pop, plucked synth, warm pad" \
      --duration 30 --bpm 110 --key "C major" --seed 1 --out bgm_ace.wav

Env: ACE_STEP_DIR (default ~/ace-step-1.5). Models download on first run.
"""
import argparse, os, shutil, sys, tempfile

ap = argparse.ArgumentParser()
ap.add_argument('--prompt', required=True)
ap.add_argument('--duration', type=float, default=30)
ap.add_argument('--bpm', type=int)
ap.add_argument('--key', default='', help='e.g. "C major", "A minor"')
ap.add_argument('--seed', type=int, default=1, help='first seed')
ap.add_argument('--n', type=int, default=3, help='candidates; the best-scoring one is kept')
ap.add_argument('--steps', type=int, default=8)
ap.add_argument('--model', default='acestep-v15-turbo')
ap.add_argument('--lufs', type=float, default=-18.0)
ap.add_argument('--raw', action='store_true', help='skip BGM post-processing')
ap.add_argument('--out', required=True)
a = ap.parse_args()

root = os.path.expanduser(os.environ.get('ACE_STEP_DIR', '~/ace-step-1.5'))
sys.path.insert(0, root)
os.chdir(root)
from acestep.handler import AceStepHandler
from acestep.llm_inference import LLMHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music

dit = AceStepHandler()
llm = LLMHandler()
msg, ok = dit.initialize_service(project_root=root, config_path=a.model, device='cuda')
if not ok:
    sys.exit('init failed: ' + str(msg))
caption = a.prompt + (', instrumental, no vocals' if 'instrumental' not in a.prompt.lower() else '')
params = GenerationParams(caption=caption, lyrics='[Instrumental]', instrumental=True, duration=a.duration,
                          bpm=a.bpm, keyscale=a.key, seed=a.seed, inference_steps=a.steps,
                          thinking=False, use_cot_metas=False, use_cot_caption=False, use_cot_language=False)
cfg = GenerationConfig(batch_size=1, audio_format='wav', use_random_seed=False, seeds=[a.seed])
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evaluate
import subprocess
af = ('silenceremove=stop_periods=-1:stop_duration=0.4:stop_threshold=-55dB,'
      'highshelf=f=3500:g=-14,lowpass=f=11000,lowshelf=f=150:g=-4,'
      f'afade=t=in:d=0.05,areverse,afade=t=in:d=1.2,areverse,loudnorm=I={a.lufs}:TP=-1.5:LRA=9')
key_root, _, key_scale = a.key.partition(' ')
tmp = tempfile.mkdtemp()
best = None
for seed in range(a.seed, a.seed + a.n):
    params.seed = seed
    cfg = GenerationConfig(batch_size=1, audio_format='wav', use_random_seed=False, seeds=[seed])
    res = generate_music(dit, llm, params, cfg, save_dir=tmp)
    if not res.success:
        print('seed', seed, 'failed:', res.error, file=sys.stderr)
        continue
    cand = os.path.join(tmp, f'cand_{seed}.wav')
    if a.raw:
        shutil.copy(res.audios[0]['path'], cand)
    else:
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', res.audios[0]['path'], '-af', af, '-ar', '44100', cand], check=True)
    r = evaluate.evaluate(cand, key=key_root or None, scale=key_scale.strip() or None, bpm=a.bpm)
    print(f'seed {seed}: score {r["score"]}', file=sys.stderr)
    if best is None or r['score'] > best[0]:
        best = (r['score'], seed, cand)
if best is None:
    sys.exit('all candidates failed')
shutil.copy(best[2], a.out)
print(f'{a.out}  seed={best[1]} score={best[0]}')
