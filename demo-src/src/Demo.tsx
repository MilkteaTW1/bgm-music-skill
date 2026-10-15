import React from 'react';
import {AbsoluteFill, Audio, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import gsap from 'gsap';
import spectrum from './spectrum.json';
import data from './moods.json';

const BG = '#0a0a18';
const C = ['#ff4d8d', '#ffb347', '#43e0b8', '#5aa9ff', '#b57bff'];
const MUTED = '#8f93b8';
const REPO = 'github.com/MilkteaTW1/bgm-music-skill';
const USE: Record<string, string> = {
  uplifting: 'Promos, social reels, launches',
  corporate: 'Product demos, SaaS, B2B explainers',
  playful: 'Kids, games, quirky brand clips',
  lofi: 'Study, vlogs, casual coding streams',
  calm: 'Tutorials, walkthroughs, onboarding',
  ambient: 'Wellness, sleep, nature, focus',
  cinematic: 'Trailers, announcements, brand films',
  tense: 'Alerts, security, thrillers, bug reports',
};

const Count: React.FC<{to: number; decimals?: number; start?: number; dur?: number; suffix?: string}> = ({to, decimals = 0, start = 0, dur = 1.6, suffix = ''}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = Math.min(1, Math.max(0, (f / fps - start) / dur));
  return <span>{(to * gsap.parseEase('power3.out')(p)).toFixed(decimals)}{suffix}</span>;
};

const Spectrum: React.FC<{height: number; offset: number; opacity?: number}> = ({height, offset, opacity = 1}) => {
  const f = useCurrentFrame();
  const i = Math.min(f + offset, spectrum.length - 1);
  const row = spectrum[i] as number[];
  const prev = spectrum[Math.max(0, i - 1)] as number[];
  return (
    <div style={{display: 'flex', alignItems: 'flex-end', gap: 8, height, opacity, width: '100%', justifyContent: 'center'}}>
      {row.map((v, k) => {
        const s = v * 0.7 + prev[k] * 0.3;
        return <div key={k} style={{width: 20, height: 6 + s * s * height, borderRadius: 10,
          background: `linear-gradient(180deg, ${C[k % 5]}, ${C[(k + 2) % 5]})`, boxShadow: `0 0 ${10 + s * 24}px ${C[k % 5]}66`}} />;
      })}
    </div>
  );
};

const Fade: React.FC<{children: React.ReactNode; dur: number}> = ({children, dur}) => {
  const f = useCurrentFrame();
  return <AbsoluteFill style={{opacity: interpolate(f, [0, 10, dur - 10, dur], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}}>{children}</AbsoluteFill>;
};

const Title: React.FC<{small?: string; big: string; size?: number}> = ({small, big, size = 104}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame: f, fps, config: {damping: 14}});
  return (
    <div style={{textAlign: 'center', transform: `translateY(${(1 - s) * 40}px)`, opacity: s}}>
      {small && <div style={{fontSize: 32, letterSpacing: 9, color: MUTED, fontWeight: 600, textTransform: 'uppercase'}}>{small}</div>}
      <div style={{fontSize: size, fontWeight: 900, color: '#fff', marginTop: 8, letterSpacing: -2}}>{big}</div>
    </div>
  );
};

const Intro: React.FC<{offset: number}> = ({offset}) => (
  <AbsoluteFill style={{alignItems: 'center'}}>
    <div style={{marginTop: 190}}><Title small="Claude Code skill" big="bgm-music" size={170} /></div>
    <div style={{marginTop: 26, fontSize: 48, color: '#e6e8ff', fontWeight: 600}}>Your AI videos finally get a soundtrack.</div>
    <div style={{display: 'flex', gap: 18, marginTop: 36}}>
      {['offline · no downloads', '8 moods', 'scene-synced', 'measured quality'].map((t, i) => (
        <div key={t} style={{padding: '12px 26px', borderRadius: 40, border: `2px solid ${C[i]}88`, color: C[i], fontSize: 26, fontWeight: 700}}>{t}</div>
      ))}
    </div>
    <div style={{position: 'absolute', bottom: 70, width: '100%'}}><Spectrum height={300} offset={offset} /></div>
  </AbsoluteFill>
);

const Install: React.FC = () => {
  const f = useCurrentFrame();
  const lines: [string, string, number][] = [
    ['$ python install.py', '#fff', 0],
    ['installed  ~/.claude/skills/bgm-music', C[2], 24],
    ['patched    video', C[2], 40],
    ['patched    gsap-remotion', C[2], 52],
    ['self-test: OK', C[2], 70],
  ];
  const steps = ['Brief', 'Mood', 'Compose', 'Evaluate', 'Mix'];
  return (
    <AbsoluteFill style={{alignItems: 'center'}}>
      <div style={{marginTop: 100}}><Title small="Install once" big="Every video gets scored" /></div>
      <div style={{marginTop: 50, width: 1100, padding: '36px 44px', borderRadius: 24, background: '#10102a', border: '2px solid #2a2a55',
        fontFamily: 'Consolas, monospace', fontSize: 38, lineHeight: 1.7}}>
        {lines.map(([t, c, at]) => <div key={t} style={{color: c, opacity: f >= at ? 1 : 0}}>{t}</div>)}
      </div>
      <div style={{display: 'flex', alignItems: 'center', gap: 18, marginTop: 56}}>
        {steps.map((s, i) => {
          const on = f >= 100 + i * 16;
          return (
            <React.Fragment key={s}>
              <div style={{padding: '18px 34px', borderRadius: 18, fontSize: 36, fontWeight: 800, background: on ? C[i] : '#14142b',
                color: on ? BG : '#5f6390', boxShadow: on ? `0 0 40px ${C[i]}77` : 'none'}}>{s}</div>
              {i < steps.length - 1 && <div style={{fontSize: 36, color: '#5f6390'}}>→</div>}
            </React.Fragment>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const MoodCard: React.FC<{i: number; offset: number}> = ({i, offset}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const m = data.moods[i];
  const s = spring({frame: f, fps, config: {damping: 14}});
  const col = C[i % 5];
  return (
    <AbsoluteFill style={{alignItems: 'center'}}>
      <div style={{marginTop: 90, fontSize: 30, letterSpacing: 9, color: MUTED, textTransform: 'uppercase'}}>Mood {i + 1} of 8 · actual output</div>
      <div style={{marginTop: 20, fontSize: 190, fontWeight: 900, color: col, transform: `scale(${0.9 + 0.1 * s})`, opacity: s, letterSpacing: -4}}>{m.mood}</div>
      <div style={{fontSize: 46, color: '#fff', fontWeight: 600}}>{USE[m.mood]}</div>
      <div style={{display: 'flex', gap: 22, marginTop: 36}}>
        {[`${m.bpm} BPM`, m.key, `score ${m.score.toFixed(1)}`].map((t) => (
          <div key={t} style={{padding: '14px 30px', borderRadius: 16, background: '#14142b', border: `2px solid ${col}55`, color: '#e6e8ff', fontSize: 36, fontWeight: 700}}>{t}</div>
        ))}
      </div>
      <div style={{position: 'absolute', bottom: 60, width: '100%'}}><Spectrum height={250} offset={offset} /></div>
    </AbsoluteFill>
  );
};

const Sync: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const secs = 8;
  const W = 1500;
  const cuts = [2, 4, 6];
  const levels = [0.4, 0.75, 0.95, 1.0];
  const edges = [0, ...cuts, secs];
  const metrics: [string, number, string][] = [['Loudness', 1.0, '-17.7 LUFS'], ['Key fit', 0.98, '98%'], ['Brightness', 0.97, 'no hiss'], ['Rhythm', 1.0, '120 BPM'], ['Stereo', 1.0, 'mono-safe']];
  return (
    <AbsoluteFill style={{alignItems: 'center'}}>
      <div style={{marginTop: 70}}><Title small="Sections follow your edit" big="Cuts in, energy up" /></div>
      <div style={{marginTop: 50, width: W, height: 220, position: 'relative', background: '#10102a', borderRadius: 20, overflow: 'hidden'}}>
        {levels.map((l, i) => {
          const x0 = (edges[i] / secs) * W, w = ((edges[i + 1] - edges[i]) / secs) * W;
          const s = spring({frame: f - i * 12, fps, config: {damping: 16}});
          return <div key={i} style={{position: 'absolute', left: x0 + 6, bottom: 0, width: w - 12, height: 200 * l * s, borderRadius: '14px 14px 0 0',
            background: `linear-gradient(180deg, ${C[i]}, ${C[i]}55)`}} />;
        })}
        {cuts.map((c) => <div key={c} style={{position: 'absolute', left: (c / secs) * W - 2, top: 0, width: 4, height: 220, background: '#fff'}} />)}
      </div>
      <div style={{display: 'flex', justifyContent: 'space-between', width: W, marginTop: 10, fontSize: 26, color: MUTED}}>
        <span>scene 1</span><span>cut</span><span>cut</span><span>cut → final push</span>
      </div>
      <div style={{display: 'flex', gap: 34, marginTop: 44, alignItems: 'center'}}>
        <div style={{fontSize: 150, fontWeight: 900, color: C[2], lineHeight: 1}}><Count to={99.7} decimals={1} start={0.4} dur={2} /></div>
        <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 40px'}}>
          {metrics.map(([n, v, t], i) => (
            <div key={n} style={{width: 420}}>
              <div style={{fontSize: 24, color: MUTED}}>{n} · <b style={{color: '#fff'}}>{t}</b></div>
              <div style={{height: 14, borderRadius: 7, background: '#14142b', marginTop: 4}}>
                <div style={{height: '100%', width: `${Math.min(1, Math.max(0, (f - 20 - i * 6) / 40)) * v * 100}%`, borderRadius: 7, background: C[i % 5]}} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const Outro: React.FC<{offset: number}> = ({offset}) => (
  <AbsoluteFill style={{alignItems: 'center'}}>
    <div style={{marginTop: 150}}><Title small="Get it" big="Install once. Score everything." size={92} /></div>
    <div style={{marginTop: 50, padding: '26px 54px', borderRadius: 20, background: '#10102a', border: '2px solid #2a2a55', fontFamily: 'Consolas, monospace', fontSize: 40, color: C[2]}}>
      git clone https://{REPO} && python install.py
    </div>
    <div style={{marginTop: 30, fontSize: 36, color: '#e6e8ff'}}>Composed by code. Verified by numbers.</div>
    <div style={{position: 'absolute', bottom: 40, width: '100%'}}><Spectrum height={220} offset={offset} opacity={0.8} /></div>
  </AbsoluteFill>
);

export const Demo: React.FC = () => {
  const frame = useCurrentFrame();
  const row = spectrum[Math.min(frame, spectrum.length - 1)] as number[];
  const pulse = (row[0] + row[1] + row[2] + row[3]) / 4;
  const total = data.frames;
  const MOOD_LEN = 105;
  return (
    <AbsoluteFill style={{background: BG, fontFamily: 'Inter, "Segoe UI", system-ui, sans-serif', overflow: 'hidden'}}>
      <AbsoluteFill style={{background: `radial-gradient(circle at 50% 60%, ${C[4]}${Math.round(20 + pulse * 45).toString(16).padStart(2, '0')}, transparent 60%)`}} />
      <Audio src={staticFile('demo.mp3')} volume={(f) => interpolate(f, [0, 15, total - 40, total - 1], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})} />
      <Sequence from={0} durationInFrames={180}><Fade dur={180}><Intro offset={0} /></Fade></Sequence>
      <Sequence from={180} durationInFrames={240}><Fade dur={240}><Install /></Fade></Sequence>
      {data.moods.map((_, i) => (
        <Sequence key={i} from={420 + i * MOOD_LEN} durationInFrames={MOOD_LEN}>
          <Fade dur={MOOD_LEN}><MoodCard i={i} offset={420 + i * MOOD_LEN} /></Fade>
        </Sequence>
      ))}
      <Sequence from={1260} durationInFrames={240}><Fade dur={240}><Sync /></Fade></Sequence>
      <Sequence from={1500} durationInFrames={total - 1500}><Fade dur={total - 1500}><Outro offset={1500} /></Fade></Sequence>
    </AbsoluteFill>
  );
};
