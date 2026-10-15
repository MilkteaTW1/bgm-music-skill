#!/usr/bin/env python3
"""Objective quality check for background music (numpy + ffmpeg only).

  python evaluate.py track.wav --mood uplifting --key C --scale major --bpm 113 [--loop] [--json] [--spectrogram out.png]

Scores 0-100 from 9 measurable criteria and prints concrete fixes for anything weak.
These are proxies for "sounds good": they catch the usual failures (clipping, mud,
harshness, out-of-key notes, no pulse, static or jumpy dynamics, bad loop seam) but
cannot replace a human listen. Treat <75 as "iterate", >=85 as "ship".
"""
import argparse, json, math, re, subprocess, sys
import numpy as np

SR = 44100
SCALES = {
    'major': [0, 2, 4, 5, 7, 9, 11], 'minor': [0, 2, 3, 5, 7, 8, 10],
    'dorian': [0, 2, 3, 5, 7, 9, 10], 'mixolydian': [0, 2, 4, 5, 7, 9, 10],
    'lydian': [0, 2, 4, 6, 7, 9, 11], 'phrygian': [0, 1, 3, 5, 7, 8, 10],
}
NOTE = {'C': 0, 'C#': 1, 'DB': 1, 'D': 2, 'D#': 3, 'EB': 3, 'E': 4, 'F': 5, 'F#': 6,
        'GB': 6, 'G': 7, 'G#': 8, 'AB': 8, 'A': 9, 'A#': 10, 'BB': 10, 'B': 11}
# spectral energy share targets (min, max) per band for finished BGM
BANDS = [('sub<60', 0, 60, 0.00, 0.22), ('bass60-250', 60, 250, 0.15, 0.50), ('lowmid250-500', 250, 500, 0.08, 0.30),
         ('mid500-2k', 500, 2000, 0.12, 0.40), ('himid2-6k', 2000, 6000, 0.02, 0.18), ('air>6k', 6000, 22050, 0.00, 0.06)]


def load(path):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-ac', '2', '-ar', str(SR), '-'],
                       capture_output=True)
    if r.returncode or not r.stdout:
        sys.exit('cannot decode: ' + r.stderr.decode(errors='ignore'))
    return np.frombuffer(r.stdout, dtype=np.float32).reshape(-1, 2).T.astype(np.float64)


def ebur(path):
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', path, '-filter_complex',
                        'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True)
    tail = r.stderr[r.stderr.rfind('Summary:'):]
    g = lambda k: float(re.search(k + r':\s+(-?[\d.]+)', tail).group(1)) if re.search(k + r':\s+(-?[\d.]+)', tail) else None
    return dict(lufs=g('I'), lra=g('LRA'), tp=g(r'Peak'))


def stft(x, n=4096, hop=1024):
    w = np.hanning(n)
    nf = 1 + (len(x) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(nf)[:, None]
    return np.abs(np.fft.rfft(x[idx] * w, axis=1))


def tri(v, lo, ok_lo, ok_hi, hi):
    """1 inside [ok_lo, ok_hi], linear to 0 at lo/hi."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return 0.0
    if ok_lo <= v <= ok_hi:
        return 1.0
    if v < ok_lo:
        return max(0.0, (v - lo) / (ok_lo - lo))
    return max(0.0, (hi - v) / (hi - ok_hi))


def evaluate(path, mood=None, key=None, scale=None, bpm=None, loop=False, spectrogram=None):
    x = load(path)
    mono = x.mean(axis=0)
    dur = x.shape[1] / SR
    L = ebur(path)
    S = {}        # criterion -> (score 0..1, detail, advice)
    issues = []

    # 1 loudness ---------------------------------------------------------
    s = tri(L['lufs'], -30, -21, -15, -9)
    S['loudness'] = (s, f"{L['lufs']} LUFS (target -21..-15 for BGM under voice)",
                     'rerun with --lufs -18' if s < 0.9 else '')
    # 2 headroom / clipping ----------------------------------------------
    pk = float(np.max(np.abs(x)))
    clip = int(np.sum(np.abs(x) >= 0.999))
    s = (1.0 if pk <= 0.95 else max(0, 1 - (pk - 0.95) * 10)) * (1.0 if clip == 0 else 0.0)
    S['headroom'] = (s, f'peak {20 * math.log10(pk + 1e-9):.1f} dBFS, {clip} clipped samples',
                     'lower --lufs or soften limiter' if s < 0.9 else '')
    # 3 spectral balance -------------------------------------------------
    M = stft(mono)
    P = (M ** 2).mean(axis=0)
    f = np.fft.rfftfreq(4096, 1 / SR)
    tot = P.sum() + 1e-12
    shares, sc = {}, []
    for name, lo, hi, a, b in BANDS:
        sh = float(P[(f >= lo) & (f < hi)].sum() / tot)
        shares[name] = round(sh, 3)
        sc.append(tri(sh, a - 0.12, a, b, b + 0.12))
        if sh > b:
            issues.append(f'{name} too strong ({sh:.2f}>{b})')
        elif sh < a:
            issues.append(f'{name} too weak ({sh:.2f}<{a})')
    cent = float((f[:, None] * M.T).sum() / (M.sum() + 1e-12))
    S['spectrum'] = (float(np.mean(sc)), f'bands {shares}, centroid {cent:.0f} Hz',
                     'adjust brightness / reverb / bass level' if np.mean(sc) < 0.8 else '')
    # 3b brightness: average level of 6-16 kHz vs 250-2 kHz (dB). Harsh/hissy if too close.
    def band_db(lo, hi):
        return 10 * np.log10(P[(f >= lo) & (f < hi)].mean() + 1e-18)
    tilt = band_db(6000, 16000) - band_db(250, 2000)
    s_tilt = tri(tilt, -80, -62, -38, -22)
    S['brightness'] = (s_tilt, f'6-16k vs 250-2k = {tilt:.0f} dB (want -62..-38)',
                       'hissy/harsh: low-pass hats, cut noise into reverb' if tilt > -38 else 'dull: raise tone_hz / add air' if tilt < -62 else '')
    # 4 key adherence ----------------------------------------------------
    # peak-picked chroma: only spectral peaks (tones), so noise/percussion can't dilute the key estimate
    sel = (f >= 100) & (f <= 2500)
    Ms = M[:, sel]
    peak = (Ms[:, 1:-1] > Ms[:, :-2]) & (Ms[:, 1:-1] > Ms[:, 2:]) & (Ms[:, 1:-1] > 0.05 * Ms.max(axis=1, keepdims=True))
    fsel = f[sel][1:-1]
    midi = 69 + 12 * np.log2(fsel / 440.0)
    dev = np.abs(midi - np.round(midi))
    pcs = np.round(midi).astype(int) % 12
    chroma = np.zeros(12)
    wgt = (Ms[:, 1:-1] ** 2) * peak * (dev < 0.3)
    for pc in range(12):
        chroma[pc] = wgt[:, pcs == pc].sum()
    chroma /= chroma.sum() + 1e-12
    if key and scale:
        inscale = sum(chroma[(NOTE[key.upper()] + d) % 12] for d in SCALES[scale])
        s = tri(inscale, 0.55, 0.9, 1.0, 1.01)
        S['key'] = (s, f'{inscale * 100:.0f}% of pitch energy in {key} {scale}',
                    'out-of-scale notes: check melody pool / percussion leakage' if s < 0.9 else '')
    else:
        top = np.sort(chroma)[::-1]
        s = tri(float(top[:7].sum()), 0.6, 0.88, 1.0, 1.01)
        S['key'] = (s, f'top-7 pitch classes carry {top[:7].sum() * 100:.0f}% (no key supplied)', '')
    # 5 rhythm / pulse ---------------------------------------------------
    mag = np.log1p(M * 10)
    flux = np.maximum(0, np.diff(mag, axis=0)).sum(axis=1)
    flux -= flux.mean()
    hop_s = 1024 / SR
    ac = np.correlate(flux, flux, 'full')[len(flux) - 1:]
    ac /= ac[0] + 1e-12
    lo_l, hi_l = int(60 / 190 / hop_s), int(60 / 55 / hop_s)
    seg = ac[lo_l:hi_l]
    lag = lo_l + int(np.argmax(seg))
    est = 60.0 / (lag * hop_s)
    clarity = float(seg.max())
    if bpm:
        cands = [est, est * 2, est / 2]
        err = min(abs(c - bpm) / bpm for c in cands)
    else:
        err = 0.0
    s_t = tri(err, -1, 0, 0.04, 0.15)
    s_c = tri(clarity, 0.0, 0.18, 1.0, 1.1) if mood not in ('ambient', 'calm', 'cinematic') else tri(clarity, -0.2, 0.05, 1.0, 1.1)
    S['rhythm'] = (0.5 * s_t + 0.5 * s_c, f'tempo ~{est:.0f} BPM (target {bpm}), pulse clarity {clarity:.2f}',
                   'weak pulse: raise drum/arp level or reduce reverb' if s_c < 0.7 else
                   'tempo mismatch' if s_t < 0.7 else '')
    # 6 dynamics over time ----------------------------------------------
    win = SR
    rms = np.array([np.sqrt(np.mean(mono[i:i + win] ** 2)) + 1e-9 for i in range(0, len(mono) - win, win)])
    db = 20 * np.log10(rms)
    body = db[:-2] if len(db) > 6 else db            # ignore the fade-out
    rng_db = float(np.percentile(body, 95) - np.percentile(body, 5)) if len(body) > 3 else 0.0
    if dur < 20:
        s = tri(rng_db, -1, 0.5, 8, 14)
    else:
        s = tri(rng_db, -1, 2.0, 9, 15)
    S['dynamics'] = (s, f'short-term level range {rng_db:.1f} dB over {dur:.0f}s',
                     'static: add sections/energy changes' if rng_db < 2 else 'too jumpy: reduce section contrast' if s < 0.9 else '')
    # 7 variety (block-to-block novelty, not random, not frozen) --------
    blk = int(4 * SR / 1024)
    feats = []
    for i in range(0, M.shape[0] - blk, blk):
        v = M[i:i + blk].mean(axis=0)
        v = np.log1p(v * 50)
        feats.append(v / (np.linalg.norm(v) + 1e-9))
    if len(feats) >= 3:
        sims = [float(np.dot(feats[i], feats[i + 1])) for i in range(len(feats) - 1)]
        nov = 1 - float(np.mean(sims))
        s = tri(nov, -0.02, 0.01, 0.20, 0.5)
        S['variety'] = (s, f'block-to-block novelty {nov:.3f}', 'too repetitive' if nov < 0.01 else 'too chaotic' if nov > 0.2 else '')
    else:
        S['variety'] = (0.8, 'too short to judge', '')
    # 8 stereo -----------------------------------------------------------
    l, r = x[0], x[1]
    corr = float(np.corrcoef(l, r)[0, 1]) if np.std(l) > 0 and np.std(r) > 0 else 1.0
    side = float(np.std(l - r) / (np.std(l + r) + 1e-9))
    s = tri(corr, 0.0, 0.25, 0.97, 1.0)
    S['stereo'] = (s, f'L/R correlation {corr:.2f}, side/mid {side:.2f}',
                   'too mono: detune/pan more' if corr > 0.97 else 'phasey: reduce width' if s < 0.9 else '')
    # 9 start/end & seam -------------------------------------------------
    head = float(np.sqrt(np.mean(mono[: int(0.2 * SR)] ** 2)))
    tail = float(np.sqrt(np.mean(mono[-int(0.2 * SR):] ** 2)))
    lastbit = float(np.sqrt(np.mean(mono[-int(0.02 * SR):] ** 2)))
    med = float(np.median(rms)) + 1e-9
    if loop:
        jump = float(abs(mono[-1] - mono[0]) / (np.percentile(np.abs(np.diff(mono)), 95) + 1e-9))
        match = min(head, tail) / (max(head, tail) + 1e-9)
        s = (1.0 if jump < 1.5 else 0.5) * tri(match, 0.0, 0.5, 1.0, 1.1)
        S['ends'] = (s, f'loop seam jump {jump:.2f}x typical step, start/end level match {match:.2f}', 'wrap tail / equalise ends' if s < 0.8 else '')
    else:
        ends_quiet = tail / med
        s = tri(ends_quiet, -0.1, 0.0, 0.25, 0.8) * (1.0 if lastbit < 0.01 else 0.5)
        S['ends'] = (s, f'ending level {ends_quiet:.2f}x median, last-20ms rms {lastbit:.4f}', 'needs a longer fade/ring-out' if s < 0.8 else '')

    w = dict(loudness=1.0, headroom=1.0, brightness=1.3, spectrum=1.5, key=1.5, rhythm=1.2, dynamics=1.0, variety=0.8, stereo=0.7, ends=0.8)
    score = 100 * sum(S[k][0] * w[k] for k in S) / sum(w[k] for k in S)
    crit = min(S['key'][0], S['headroom'][0], S['loudness'][0] + 0.25, S['brightness'][0] + 0.3, 1.0)
    score = min(score, 55 + 45 * crit)          # a critical failure caps the whole score
    if spectrogram:
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', path, '-lavfi',
                        'showspectrumpic=s=1280x480:legend=1:scale=log', spectrogram], check=False)
    return dict(score=round(score, 1), duration=round(dur, 1), criteria={k: dict(score=round(v[0], 2), detail=v[1], fix=v[2]) for k, v in S.items()},
                chroma={n: round(float(c), 3) for n, c in zip(['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'], chroma)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file')
    ap.add_argument('--mood')
    ap.add_argument('--key')
    ap.add_argument('--scale')
    ap.add_argument('--bpm', type=float)
    ap.add_argument('--loop', action='store_true')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--spectrogram', help='write a spectrogram PNG here (look at it!)')
    a = ap.parse_args()
    res = evaluate(a.file, a.mood, a.key, a.scale, a.bpm, a.loop, a.spectrogram)
    if a.json:
        print(json.dumps(res, indent=1))
        return
    print(f"SCORE {res['score']}/100   ({res['duration']}s)")
    for k, v in res['criteria'].items():
        mark = 'ok ' if v['score'] >= 0.85 else 'WEAK' if v['score'] >= 0.5 else 'BAD'
        print(f"  {mark:4} {k:9} {v['score']:.2f}  {v['detail']}" + (f"   -> {v['fix']}" if v['fix'] else ''))


if __name__ == '__main__':
    main()
