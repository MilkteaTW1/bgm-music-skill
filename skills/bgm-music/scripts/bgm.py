#!/usr/bin/env python3
"""Procedural background-music composer. numpy + ffmpeg only, no downloads.

  python bgm.py --mood uplifting --duration 30 --out bgm.wav
  python bgm.py --mood lofi --duration 60 --loop --out lofi.mp3 --seed 7

Moods: calm uplifting corporate lofi cinematic tense playful ambient
Deterministic for a given (mood, duration, key, seed).
"""
import argparse, json, math, os, re, subprocess, wave
import numpy as np

SR = 44100
SCALES = {
    'major': [0, 2, 4, 5, 7, 9, 11], 'minor': [0, 2, 3, 5, 7, 8, 10],
    'dorian': [0, 2, 3, 5, 7, 9, 10], 'mixolydian': [0, 2, 4, 5, 7, 9, 10],
    'lydian': [0, 2, 4, 6, 7, 9, 11], 'phrygian': [0, 1, 3, 5, 7, 8, 10],
}
NOTE = {'C': 0, 'C#': 1, 'DB': 1, 'D': 2, 'D#': 3, 'EB': 3, 'E': 4, 'F': 5, 'F#': 6,
        'GB': 6, 'G': 7, 'G#': 8, 'AB': 8, 'A': 9, 'A#': 10, 'BB': 10, 'B': 11}

# prog = scale degrees (0-based), one chord per bar, 4-bar loop.
MOODS = {
    'calm': dict(scale='major', bpm=72, key='F', prog=[0, 4, 5, 3], sev=True, drums='soft',
                 keys='ep', arp=8, bass='whole', lead='soft', swing=0.0, duck=0.0, reverb=0.35,
                 melody='sparse', bright=0.8, lead_gain=0.75),
    'uplifting': dict(scale='major', bpm=116, key='C', prog=[0, 4, 5, 3], sev=False, drums='house',
                      keys='pluck', arp=8, bass='offbeat', lead='pluck', swing=0.0, duck=0.45,
                      reverb=0.22, melody='medium', bright=1.1, lead_gain=1.0),
    'corporate': dict(scale='major', bpm=104, key='G', prog=[0, 5, 3, 4], sev=False, drums='pop',
                      keys='pluck', arp=16, bass='groove', lead='soft', swing=0.0, duck=0.25,
                      reverb=0.2, melody='medium', bright=1.0, lead_gain=0.9),
    'lofi': dict(scale='dorian', bpm=78, key='D', prog=[1, 4, 0, 5], sev=True, drums='boombap',
                 keys='ep', arp=0, bass='sub', lead='ep', swing=0.18, duck=0.0, reverb=0.28,
                 melody='sparse', bright=0.6, lead_gain=0.8),
    'cinematic': dict(scale='minor', bpm=84, key='D', prog=[0, 5, 2, 6], sev=False, drums='epic',
                      keys='bell', arp=0, bass='whole', lead='soft', swing=0.0, duck=0.0,
                      reverb=0.5, melody='sparse', bright=0.9, lead_gain=0.9),
    'tense': dict(scale='phrygian', bpm=100, key='E', prog=[0, 1, 0, 4], sev=False, drums='tense',
                  keys='bell', arp=16, bass='pulse', lead='soft', swing=0.0, duck=0.0,
                  reverb=0.35, melody='sparse', bright=0.85, lead_gain=0.7),
    'playful': dict(scale='major', bpm=126, key='C', prog=[0, 3, 4, 0], sev=False, drums='playful',
                    keys='pluck', arp=8, bass='bounce', lead='pluck', swing=0.08, duck=0.2,
                    reverb=0.15, melody='busy', bright=1.15, lead_gain=1.0),
    'ambient': dict(scale='lydian', bpm=60, key='A', prog=[0, 4, 5, 1], sev=True, drums='none',
                    keys='bell', arp=0, bass='whole', lead='soft', swing=0.0, duck=0.0,
                    reverb=0.6, melody='sparse', bright=0.7, lead_gain=0.7),
}

DRUMS = {  # 16 steps per bar. k=kick s=snare c=clap h=hat o=open hat t=tom
    'soft':    dict(k='x.......x.......', s='', h='..x...x...x...x.', o='', c='', t=''),
    'house':   dict(k='x...x...x...x...', s='', h='..x...x...x...x.', o='..o...o...o...o.', c='....x.......x...', t=''),
    'pop':     dict(k='x.......x.x.....', s='....x.......x...', h='x.x.x.x.x.x.x.x.', o='', c='', t=''),
    'boombap': dict(k='x.......x.x.....', s='....x.......x...', h='x.x.x.x.x.x.x.xx', o='', c='', t=''),
    'epic':    dict(k='x.......x.......', s='............x...', h='', o='', c='', t='..........x.x...'),
    'tense':   dict(k='x.....x.........', s='', h='xxxxxxxxxxxxxxxx', o='', c='', t=''),
    'playful': dict(k='x.....x.x.......', s='', h='x.x.x.x.x.x.x.xx', o='', c='....x.......x...', t=''),
    'none':    dict(k='', s='', h='', o='', c='', t=''),
}

RHY = {  # (start step, length in steps) per bar of 16
    'sparse': [[(0, 8), (8, 8)], [(0, 6), (6, 2), (8, 8)], [(0, 4), (4, 4), (8, 8)],
               [(2, 6), (8, 8)], [(0, 12), (12, 4)], [(0, 4), (6, 2), (8, 6)]],
    'medium': [[(0, 4), (4, 2), (6, 2), (8, 4), (12, 4)], [(0, 3), (3, 3), (6, 2), (8, 4), (12, 4)],
               [(0, 2), (2, 2), (4, 4), (8, 2), (10, 2), (12, 4)], [(0, 6), (6, 2), (8, 2), (10, 2), (12, 4)],
               [(0, 4), (4, 4), (8, 3), (11, 3), (14, 2)]],
    'busy':   [[(0, 2), (2, 2), (4, 2), (6, 2), (8, 2), (10, 2), (12, 4)],
               [(0, 2), (2, 2), (4, 4), (8, 2), (10, 2), (12, 2), (14, 2)],
               [(0, 3), (3, 3), (6, 2), (8, 2), (10, 2), (12, 2), (14, 2)]],
}


def mtof(m):
    return 440.0 * 2.0 ** ((m - 69.0) / 12.0)


def _t(n):
    return np.arange(n, dtype=np.float64) / SR


# ----------------------------------------------------------------- voices
def v_pad(f, dur, bright=1.0):
    """detuned additive saw-ish pad -> (L, R). Slow attack, gentle release."""
    n = int((dur + 0.9) * SR)
    t = _t(n)
    L = np.zeros(n)
    R = np.zeros(n)
    for cents, pan, ph in ((-11, 0.8, 0.0), (0, 0.5, 1.3), (11, 0.2, 2.1)):
        ff = f * 2 ** (cents / 1200)
        top = min(12, int(0.42 * SR / ff))
        sig = np.zeros(n)
        for h in range(1, top + 1):
            sig += np.sin(2 * np.pi * ff * h * t + ph * h) * h ** (-1.25 * (1.6 - 0.5 * bright))
        L += sig * pan
        R += sig * (1 - pan)
    a = max(0.05, min(0.9, dur * 0.45))
    env = np.minimum(1.0, t / a) ** 1.5
    rel = np.clip((dur + 0.9 - t) / 0.9, 0, 1) ** 1.5
    env = env * np.where(t > dur, rel, 1.0)
    return L * env * 0.22, R * env * 0.22


def v_pluck(f, dur, bright=1.0):
    n = int(min(dur + 0.3, 2.2) * SR)
    t = _t(n)
    sig = np.zeros(n)
    top = min(14, int(0.42 * SR / f))
    for h in range(1, top + 1):
        k = 5.0 + 2.2 * h / max(bright, 0.3)
        sig += np.sin(2 * np.pi * f * h * t) * (h ** -1.1) * np.exp(-t * k)
    sig *= np.minimum(1, t / 0.004)
    return sig * 0.5


def v_ep(f, dur, bright=1.0):
    """FM electric piano (body + tine)."""
    n = int(min(dur + 0.6, 3.5) * SR)
    t = _t(n)
    idx = (1.1 + 1.2 * bright) * np.exp(-t * 4.0)
    body = np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * f * t))
    tine = 0.12 * np.sin(2 * np.pi * f * 7.0 * t + 0.5 * np.sin(2 * np.pi * f * 14.0 * t)) * np.exp(-t * 18.0)
    env = np.exp(-t * 1.6) * np.minimum(1, t / 0.006)
    rel = np.clip((dur + 0.6 - t) / 0.5, 0, 1)
    return (body + tine) * env * rel * 0.5


def v_bell(f, dur, bright=1.0):
    n = int(min(dur + 1.0, 5.0) * SR)
    t = _t(n)
    sig = np.zeros(n)
    for ratio, amp, dec in ((1, 1.0, 1.2), (2.0, 0.5, 1.8), (2.76, 0.28, 2.6), (4.07, 0.16, 3.4), (5.4, 0.08, 4.5)):
        if f * ratio < 0.45 * SR:
            sig += amp * np.sin(2 * np.pi * f * ratio * t) * np.exp(-t * dec)
    sig *= np.minimum(1, t / 0.003)
    return sig * 0.3


def v_soft(f, dur, bright=1.0):
    """soft lead: sine + 2 harmonics, delayed vibrato."""
    n = int((dur + 0.25) * SR)
    t = _t(n)
    vib = 0.0035 * np.clip((t - 0.12) / 0.3, 0, 1) * np.sin(2 * np.pi * 5.2 * t)
    ph = 2 * np.pi * f * t * (1 + vib)
    sig = np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.12 * bright * np.sin(3 * ph)
    env = np.minimum(1, t / 0.03) * np.exp(-t * 0.6)
    rel = np.clip((dur + 0.25 - t) / 0.25, 0, 1)
    return sig * env * rel * 0.35


def v_bass(f, dur, sustained=True):
    n = int(min(dur + 0.1, 3.0) * SR)
    t = _t(n)
    ph = 2 * np.pi * f * t
    sig = np.sin(ph) + 0.28 * np.sin(2 * ph) + 0.10 * np.sin(3 * ph)
    env = np.minimum(1, t / 0.008) * np.exp(-t * (0.9 if sustained else 2.5))
    rel = np.clip((dur + 0.1 - t) / 0.08, 0, 1)
    return sig * env * rel * 0.6


# ----------------------------------------------------------------- percussion
def hp(x, k=1):
    for _ in range(k):
        x = np.diff(x, prepend=0.0)
    return x


def lp(x, k=3):
    """moving-average lowpass (k taps) - tames the top end of noise percussion"""
    return np.convolve(x, np.ones(k) / k, mode='same')


def d_kick(rng, vel=1.0, deep=1.0):
    n = int(0.42 * SR)
    t = _t(n)
    f = 46 * deep + 110 * np.exp(-t * 28)
    sig = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9.5)
    click = hp(rng.standard_normal(n)) * np.exp(-t * 400) * 0.12
    return (sig + click) * vel * 0.9


def d_snare(rng, vel=1.0, length=0.22):
    n = int(length * SR)
    t = _t(n)
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 28) * 0.5
    nz = lp(hp(rng.standard_normal(n)), 3) * np.exp(-t * 20) * 0.7
    return (tone + nz) * vel * 0.8


def d_clap(rng, vel=1.0):
    n = int(0.25 * SR)
    sig = np.zeros(n)
    for off, a in ((0, 1.0), (0.011, 0.8), (0.022, 0.7), (0.034, 1.0)):
        i = int(off * SR)
        m = n - i
        sig[i:] += lp(hp(rng.standard_normal(m)), 3) * np.exp(-_t(m) * (60 if off < 0.03 else 22)) * a
    return sig * vel * 0.28


def d_hat(rng, vel=1.0, open_=False):
    n = int((0.28 if open_ else 0.045) * SR)
    t = _t(n)
    return lp(hp(rng.standard_normal(n), 2), 4) * np.exp(-t * (14 if open_ else 90)) * vel * 0.16


def d_tom(rng, vel=1.0, f0=70.0):
    n = int(0.9 * SR)
    t = _t(n)
    f = f0 + 40 * np.exp(-t * 14)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 4.2) * 0.9
            + hp(rng.standard_normal(n)) * np.exp(-t * 90) * 0.1) * vel


def d_riser(rng, dur):
    n = int(dur * SR)
    t = _t(n)
    x = t / dur
    nz = lp(hp(rng.standard_normal(n)), 6)
    sw = np.sin(2 * np.pi * np.cumsum(300 + 3000 * x ** 2) / SR)
    return (nz * 0.35 + sw * 0.25) * (x ** 2.2)


def d_crash(rng):
    n = int(1.8 * SR)
    return lp(hp(rng.standard_normal(n), 2), 5) * np.exp(-_t(n) * 2.6) * 0.3


# ----------------------------------------------------------------- harmony
def chord_notes(root_midi, scale, degree, seventh):
    sc = SCALES[scale]
    out = []
    for k in range(4 if seventh else 3):
        d = degree + 2 * k
        out.append(root_midi + sc[d % 7] + 12 * (d // 7))
    return out


def voice_lead(notes, prev, lo=52, hi=76):
    """pick the inversion/octave of a chord that moves least from the previous voicing."""
    base = sorted(n % 12 for n in notes)
    cands = []
    for inv in range(len(notes)):
        pcs = base[inv:] + base[:inv]
        for octv in range(lo // 12 - 1, hi // 12 + 1):
            v, cur = [], octv * 12
            for pc in pcs:
                while cur % 12 != pc:
                    cur += 1
                v.append(cur)
                cur += 1
            cands.append(v)
    best, bestc = None, 1e9
    for v in cands:
        if v[0] < lo or v[-1] > hi:
            continue
        c = abs(np.mean(v) - 62) if prev is None else (
            sum(min(abs(a - b) for b in prev) for a in v) + 0.3 * abs(np.mean(v) - 62))
        if c < bestc:
            best, bestc = v, c
    return best if best else sorted(notes)


# ----------------------------------------------------------------- melody
def gen_phrase(seed, pool, chords_pcs, density, final_target):
    """one 4-bar phrase -> [(bar, step, len_steps, midi)]. Chord tones on strong beats, arch contour."""
    r = np.random.default_rng(seed)
    pal = RHY[density]
    notes, cur = [], None
    for bar in range(4):
        cpcs = chords_pcs[bar]
        pat = pal[r.integers(len(pal))]
        if bar == 3:
            pat = [(0, 6), (6, 2), (8, 8)] if density != 'busy' else [(0, 4), (4, 4), (8, 8)]
        for (st, ln) in pat:
            if cur is None:
                cands = [m for m in pool if m % 12 in cpcs and 64 <= m <= 76] or pool
                cur = int(r.choice(cands))
            else:
                idx = pool.index(cur)
                mv = int(r.choice([-1, 1, -2, 2, 0, -3, 3], p=[.26, .26, .13, .13, .08, .07, .07]))
                if r.random() < 0.25:
                    mv = abs(mv) * (1 if bar < 2 else -1)
                cur = pool[int(np.clip(idx + mv, 0, len(pool) - 1))]
            if st in (0, 8) and cur % 12 not in cpcs and r.random() < 0.85:
                cur = min((m for m in pool if m % 12 in cpcs), key=lambda m: abs(m - cur))
            if bar == 3 and st == 8:
                cur = min((p for p in pool if p % 12 in final_target), key=lambda p: abs(p - cur))
            notes.append((bar, st, ln, cur))
    return notes


# ----------------------------------------------------------------- render helpers
def put(buf, start, sig, gain=1.0, pan=0.5):
    """add mono sig into stereo buf (2,N), constant-power pan."""
    if start >= buf.shape[1] or start + len(sig) <= 0:
        return
    s0 = max(0, -start)
    e = min(len(sig), buf.shape[1] - start)
    seg = sig[s0:e] * gain
    buf[0, start + s0:start + e] += seg * math.cos(pan * math.pi / 2)
    buf[1, start + s0:start + e] += seg * math.sin(pan * math.pi / 2)


def put2(buf, start, L, R, gain=1.0):
    e = min(len(L), buf.shape[1] - start)
    if e > 0:
        buf[0, start:start + e] += L[:e] * gain
        buf[1, start:start + e] += R[:e] * gain


def make_ir(seed, T60=2.4, fc=3200.0):
    r = np.random.default_rng(seed)
    n = int(T60 * 1.1 * SR)
    t = _t(n)
    ir = np.zeros((2, n))
    f = np.fft.rfftfreq(n, 1 / SR)
    common = r.standard_normal(n)
    for c in range(2):
        x = (0.55 * common + 0.85 * r.standard_normal(n)) * np.exp(-t * 6.91 / T60)
        x[: int(0.018 * SR)] = 0
        ir[c] = np.fft.irfft(np.fft.rfft(x) / (1 + (f / fc) ** 2), n)
    return ir / (np.sqrt(np.sum(ir ** 2)) + 1e-9)


def convolve_tail(x, ir, loop):
    n, m = x.shape[1], ir.shape[1]
    nf = 1 << int(math.ceil(math.log2(n + m)))
    out = np.zeros((2, n + m - 1))
    for c in range(2):
        out[c] = np.fft.irfft(np.fft.rfft(x[c], nf) * np.fft.rfft(ir[c], nf), nf)[: n + m - 1]
    if loop:  # fold the tail back onto the start so the loop is seamless
        tail = out[:, n:]
        out[:, : tail.shape[1]] += tail
        return out[:, :n]
    return out


def energy_from_cuts(bars, bar_s, cuts):
    """scene cuts (seconds) -> per-bar energy; each cut becomes a section change on the nearest bar."""
    edges = sorted({min(bars - 2, max(1, int(round(c / bar_s)))) for c in cuts if 0 < c < bars * bar_s})
    levels = [0.4, 0.75, 0.95, 0.6, 1.0]
    e = np.zeros(bars)
    seg, start = 0, 0
    for end in edges + [bars]:
        lv = 1.0 if end == bars and seg > 0 else levels[min(seg, len(levels) - 2)]
        e[start:end] = lv
        start, seg = end, seg + 1
    return e


def energy_curve(bars, loop):
    e = np.zeros(bars)
    for i in range(bars):
        g = (i // 4 * 4) / bars if bars >= 16 else i / bars
        if bars <= 12:
            e[i] = 0.4 if g < 0.15 else 0.75 if g < 0.5 else 1.0
        else:
            e[i] = 0.3 if g < 0.12 else 0.55 if g < 0.3 else 0.85 if g < 0.55 else 0.45 if g < 0.68 else 1.0
    if loop:
        e = np.clip(e, 0.5, 1.0)
    else:
        e[-1] = 0.15
    return e


# ----------------------------------------------------------------- composer
def compose(mood, duration, key=None, scale=None, bpm=None, seed=1, loop=False,
            no_drums=False, no_melody=False, cuts=None):
    cfg = dict(MOODS[mood])
    if scale:
        cfg['scale'] = scale
    keyname = (key or cfg['key']).upper().replace('MAJOR', '').replace('MINOR', '').strip()
    root_pc = NOTE[keyname]
    root = 28 + (root_pc - 4) % 12            # bass register E1..D#2 (MIDI 28..39)
    root_mid = root + 24
    base_bpm = bpm or cfg['bpm']
    tail = 0.0 if loop else 2.4
    bars = max(4, int(round((duration - tail) / (4 * 60.0 / base_bpm))))
    if loop:
        bars = max(4, int(round(bars / 4)) * 4)
    real_bpm = 4 * 60.0 * bars / max(1.0, duration - tail)
    bar_s = 4 * 60.0 / real_bpm
    step_s = bar_s / 16
    total = int(round((bars * bar_s + tail) * SR))
    rng = np.random.default_rng(seed * 1009 + 12345)
    en = energy_from_cuts(bars, bar_s, cuts) if cuts else energy_curve(bars, loop)
    if cuts and not loop:
        en[-1] = 0.15

    dry = np.zeros((2, total))        # un-reverbed bus: bass, drums
    wet = np.zeros((2, total))        # reverb-send bus: keys, melody, perc
    harm = np.zeros((2, total))       # pads (sidechained, reverb-send)
    prog, sev, scl = cfg['prog'], cfg['sev'], cfg['scale']
    chords, prev = [], None
    for b in range(bars):
        v = voice_lead(chord_notes(root_mid, scl, prog[b % len(prog)], sev), prev)
        prev = v
        chords.append(v)
    chord_pcs = [[n % 12 for n in c] for c in chords]
    bar_pos = [int(round(b * bar_s * SR)) for b in range(bars)]
    last = bars - 1

    def at(b, s, swing=True):
        sw = cfg['swing'] * step_s if (swing and s % 2 == 1) else 0.0
        return bar_pos[b] + int(round((s * step_s + sw) * SR))

    def hum(ms=4.0):
        return int(rng.normal(0, ms / 1000.0) * SR)

    # ---- pad
    for b in range(bars):
        dur = bar_s + (0.15 if b != last else 1.8)
        vel = 0.55 + 0.45 * en[b]
        for n in chords[b]:
            L, R = v_pad(float(mtof(n)), dur, cfg['bright'])
            put2(harm, bar_pos[b], L, R, vel * 0.7)
        if en[b] >= 0.85 and b != last:
            for n in chords[b][:2]:
                L, R = v_pad(float(mtof(n + 12)), dur, cfg['bright'])
                put2(harm, bar_pos[b], L, R, 0.2)

    # ---- keys
    ktype = cfg['keys']
    vk = {'pluck': v_pluck, 'ep': v_ep, 'bell': v_bell}[ktype]
    for b in range(bars):
        e = en[b]
        if b == last:
            for n in chords[b]:
                put(wet, bar_pos[b], vk(float(mtof(n + 12)), bar_s * 1.2, cfg['bright']), 0.7, 0.5)
            continue
        if e < 0.3 and ktype != 'ep':
            continue
        if cfg['arp']:
            step = 16 // cfg['arp']
            tones = chords[b] + [chords[b][0] + 12, chords[b][1] + 12]
            seqidx = [0, 1, 2, 3, 4, 3, 2, 1] if len(tones) >= 5 else [0, 1, 2, 1]
            k = 0
            for s in range(0, 16, step):
                if e < 0.5 and (s // step) % 2:
                    continue
                n = tones[seqidx[k % len(seqidx)] % len(tones)] + (12 if e > 0.9 and k % 8 == 5 else 0)
                k += 1
                vel = (0.5 + 0.3 * (s % 8 == 0)) * (0.6 + 0.4 * e)
                put(wet, at(b, s) + hum(), vk(float(mtof(n + 12)), step * step_s, cfg['bright']),
                    vel * (0.55 if cfg['arp'] == 16 else 0.7), 0.5 + 0.18 * math.sin(k))
        else:
            hits = [0, 6, 10] if (ktype == 'ep' and e >= 0.5) else [0]
            for s in hits:
                for i, n in enumerate(chords[b]):
                    put(wet, at(b, s) + hum() + i * int(0.006 * SR),
                        vk(float(mtof(n + (0 if ktype == 'ep' else 12))), step_s * (4 if s else 12), cfg['bright']),
                        0.55 * (0.7 + 0.3 * e) * (0.8 if s else 1.0), 0.35 + 0.1 * i)

    # ---- bass
    bst = cfg['bass']
    for b in range(bars):
        e = en[b]
        if e < 0.3 and bst != 'whole':
            continue
        deg = prog[b % len(prog)]
        r_ = root + SCALES[scl][deg % 7] + 12 * (deg // 7)
        if r_ > root + 7:
            r_ -= 12
        fifth = r_ + 7
        if b == last or bst == 'whole':
            patt = [(0, 16, r_)]
        elif bst == 'offbeat':
            patt = [(s, 2, r_ + (12 if (e > 0.8 and k % 4 == 3) else 0)) for k, s in enumerate((2, 6, 10, 14))]
        elif bst == 'groove':
            patt = [(0, 3, r_), (4, 2, r_), (6, 2, fifth), (8, 3, r_), (12, 2, r_ + 12 if e > .8 else r_), (14, 2, fifth)]
        elif bst == 'sub':
            patt = [(0, 6, r_), (6, 2, r_), (10, 6, fifth if b % 2 else r_)]
        elif bst == 'pulse':
            patt = [(s, 2, r_) for s in range(0, 16, 2)]
        else:  # bounce
            patt = [(0, 2, r_), (4, 2, r_ + 12), (6, 2, r_), (8, 2, fifth), (12, 2, r_ + 12), (14, 2, r_)]
        for (s, l, m) in patt:
            sig = v_bass(float(mtof(m)), l * step_s * 0.92, sustained=bst in ('whole', 'sub'))
            put(dry, at(b, s) + hum(2), sig, (1.3 if bst == 'whole' else 0.8) * (0.75 + 0.25 * e), 0.5)

    # ---- drums
    dp = DRUMS[cfg['drums']]
    drum_on = not no_drums and cfg['drums'] != 'none'
    kick_bar = np.zeros(bars, bool)
    if drum_on:
        always = cfg['drums'] in ('soft', 'boombap')
        for b in range(bars):
            e = en[b]
            if b == last:
                if cfg['drums'] in ('epic', 'house', 'pop'):
                    put(dry, bar_pos[b], d_kick(rng, 1.0, 0.8), 0.8, 0.5)
                    put(wet, bar_pos[b], d_crash(rng), 0.5, 0.5)
                continue
            if e < 0.45 and not always:
                continue
            kick_bar[b] = True
            lvl = 0.5 + 0.5 * e
            for s in range(16):
                ch = lambda k: len(dp[k]) > s and dp[k][s] in 'xo'
                v = lvl * (1.0 if s % 4 == 0 else 0.8) * (0.9 + 0.2 * rng.random())
                t0 = at(b, s) + int(rng.normal(0, 0.003) * SR)
                if ch('k'):
                    put(dry, t0, d_kick(rng, v), 0.85, 0.5)
                if ch('s') and e >= 0.5:
                    ep = cfg['drums'] == 'epic'
                    put(wet, t0, d_snare(rng, v, 0.35 if ep else 0.22), 0.55 if ep else 0.8, 0.5)
                if ch('c') and e >= 0.7:
                    put(wet, t0, d_clap(rng, v), 0.8, 0.5)
                if ch('t') and e >= 0.6:
                    put(wet, t0, d_tom(rng, v, 62 + 8 * (s % 3)), 0.8, 0.35 + 0.3 * (s % 4 == 2))
                if ch('h') and (e >= 0.5 or always):
                    if cfg['drums'] == 'boombap' and rng.random() < 0.18:
                        continue
                    hv = v * (0.55 if cfg['drums'] == 'tense' else 0.9) * (1.15 if s % 4 == 2 else 0.8)
                    put(dry, t0, d_hat(rng, hv), 0.4 if cfg['drums'] == 'soft' else 0.7, 0.62)
                if ch('o') and e >= 0.7:
                    put(dry, t0, d_hat(rng, v, True), 0.7, 0.4)
            if b + 1 < bars and en[b + 1] - e > 0.25:       # snare fill before a jump
                for k in range(4):
                    put(wet, at(b, 12 + k, False), d_snare(rng, 0.4 + 0.15 * k, 0.15), 0.6, 0.5)
        for b in range(bars - 1):                           # riser + crash on a jump
            if en[b + 1] - en[b] > 0.25:
                put(wet, bar_pos[b], d_riser(rng, bar_s), 0.5, 0.5)
                put(wet, bar_pos[b + 1], d_crash(rng), 0.6, 0.5)

    # ---- melody
    if not no_melody:
        sc = SCALES[scl]
        pool = sorted({root_mid + 12 * o + s for o in range(0, 4) for s in sc if 60 <= root_mid + 12 * o + s <= 84})
        lead_fn = {'soft': v_soft, 'pluck': v_pluck, 'ep': v_ep}[cfg['lead']]
        n_ph = (bars + 3) // 4
        first4 = [chord_pcs[i] for i in range(min(4, bars))]
        while len(first4) < 4:
            first4.append(first4[-1])
        tonic_t = [first4[0][0], first4[0][2]]
        cache = {}
        for p in range(n_ph):
            tag = ['A', 'A', 'B', 'A'][p % 4]
            if tag not in cache:
                cache[tag] = gen_phrase(seed * 7 + 11 + (0 if tag == 'A' else 99), pool, first4, cfg['melody'], tonic_t)
            notes = cache[tag]
            if p % 4 == 3:    # answer phrase: last bar a scale step lower
                notes = [(bb, ss, ll, pool[max(0, pool.index(mm) - 1)] if bb == 3 else mm) for bb, ss, ll, mm in notes]
            for (bb, ss, ll, mm) in notes:
                b = p * 4 + bb
                if b >= bars - 1 or en[b] < (0.6 if cfg['melody'] == 'sparse' else 0.5):
                    continue
                t0 = at(b, ss) + hum()
                sig = lead_fn(float(mtof(mm)), ll * step_s * 0.95, cfg['bright'])
                g = 0.55 * cfg['lead_gain'] * (0.7 + 0.3 * en[b])
                put(wet, t0, sig, g, 0.5)
                d = int(step_s * 3 * SR)                    # dotted-eighth ping-pong echo
                put(wet, t0 + d, sig, g * 0.32, 0.8)
                put(wet, t0 + 2 * d, sig, g * 0.14, 0.2)
        tonic = min(pool, key=lambda m: abs(m - (root_mid + 12)))
        put(wet, bar_pos[last] + int(0.02 * SR), lead_fn(float(mtof(tonic)), 2.2, cfg['bright']),
            0.5 * cfg['lead_gain'], 0.5)

    # ---- sidechain pump on pads/keys
    if cfg['duck'] > 0 and drum_on:
        ph = (np.arange(total) % (60.0 / real_bpm * SR)) / (60.0 / real_bpm * SR)
        env = 1.0 - cfg['duck'] * np.exp(-ph * 7.0)
        for b in range(bars):
            if not kick_bar[b]:
                env[bar_pos[b]:(bar_pos[b + 1] if b + 1 < bars else total)] = 1.0
        harm *= env
        wet *= 0.5 + 0.5 * env

    # ---- bus mix + reverb
    ir = make_ir(seed + 3, T60=1.2 + 2.6 * cfg['reverb'])
    rev = convolve_tail(wet + harm * 0.9, ir, loop)
    if rev.shape[1] < total:
        rev = np.pad(rev, ((0, 0), (0, total - rev.shape[1])))
    mix = dry + harm * 0.9 + wet * 0.8 + rev[:, :total] * (0.35 + 0.9 * cfg['reverb'])
    return mix, dict(mood=mood, bpm=round(real_bpm, 2), bars=bars, key=keyname, scale=scl,
                     duration=round(total / SR, 2), seed=seed, loop=loop)


# ----------------------------------------------------------------- master
def write_wav(path, x):
    pcm = (np.clip(x, -1, 1).T * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def _hp1(x, a):
    """one-pole DC blocker, y[n] = a*(y[n-1] + x[n] - x[n-1])"""
    out, py, px = [0.0] * len(x), 0.0, 0.0
    for i, v in enumerate(x.tolist()):
        py = a * (py + v - px)
        px = v
        out[i] = py
    return np.asarray(out)


def master(mix, loop, target_lufs, tmp, tone_hz=7500.0):
    mix = mix - mix.mean(axis=1, keepdims=True)
    a = math.exp(-2 * math.pi * 28 / SR)
    for c in range(2):
        mix[c] = _hp1(mix[c], a)
    fr = np.fft.rfftfreq(mix.shape[1], 1 / SR)
    tone = 1.0 / np.sqrt(1.0 + (fr / tone_hz) ** 4)          # 12 dB/oct, -3 dB at tone_hz
    for c in range(2):
        mix[c] = np.fft.irfft(np.fft.rfft(mix[c]) * tone, mix.shape[1])
    mix = np.tanh(mix / (np.max(np.abs(mix)) + 1e-9) * 1.2) / np.tanh(1.2)   # gentle saturation
    fi = int(0.012 * SR)
    if not loop:
        mix[:, :fi] *= np.linspace(0, 1, fi)
        fo = int(1.2 * SR)
        mix[:, -fo:] *= np.linspace(1, 0, fo) ** 2
    raw = tmp + '.raw.wav'
    write_wav(raw, mix * 0.5)
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', raw, '-af',
                        f'loudnorm=I={target_lufs}:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-'],
                       capture_output=True, text=True)
    m = re.search(r'\{[^{}]*"input_i"[^{}]*\}', r.stderr, re.S)
    gain_db = target_lufs - float(json.loads(m.group(0))['input_i']) if m else 0.0
    out = mix * 0.5 * 10 ** (gain_db / 20)
    lim = 10 ** (-1.5 / 20)      # soft-knee peak limiter above 0.7
    mag = np.abs(out)
    out = np.where(mag > 0.7, np.sign(out) * (0.7 + (lim - 0.7) * np.tanh((mag - 0.7) / (lim - 0.7))), out)
    os.remove(raw)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--mood', default='uplifting', choices=sorted(MOODS))
    ap.add_argument('--duration', type=float, default=30.0, help='total seconds incl. ring-out')
    ap.add_argument('--key', help='tonic, e.g. C F# Bb')
    ap.add_argument('--scale', choices=sorted(SCALES))
    ap.add_argument('--bpm', type=float, help='target tempo; actual tempo snaps so whole bars fill the duration')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--loop', action='store_true', help='seamless loop (no fade, tail wrapped to start)')
    ap.add_argument('--cuts', help='scene-cut times in seconds, e.g. 6.5,14,22: sections change on the nearest bar')
    ap.add_argument('--no-drums', action='store_true')
    ap.add_argument('--no-melody', action='store_true')
    ap.add_argument('--lufs', type=float, default=-18.0, help='integrated loudness (BGM under voice: -20..-18)')
    ap.add_argument('--out', default='bgm.wav', help='.wav / .mp3 / .m4a / .ogg')
    a = ap.parse_args()
    mix, info = compose(a.mood, a.duration, a.key, a.scale, a.bpm, a.seed, a.loop, a.no_drums, a.no_melody,
                         [float(x) for x in a.cuts.split(',')] if a.cuts else None)
    base, ext = os.path.splitext(a.out)
    out = master(mix, a.loop, a.lufs, base)
    wav = a.out if ext.lower() == '.wav' else base + '.tmp.wav'
    write_wav(wav, out)
    if ext.lower() != '.wav':
        codec = ['-c:a', 'libmp3lame', '-b:a', '256k'] if ext.lower() == '.mp3' else []
        subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', wav] + codec + [a.out], check=True)
        os.remove(wav)
    info['out'] = a.out
    print(json.dumps(info))


if __name__ == '__main__':
    main()
