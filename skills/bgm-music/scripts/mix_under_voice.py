#!/usr/bin/env python3
"""Mix background music under a voiceover (auto-duck) or onto a video.

  python mix_under_voice.py --voice vo.wav --music bgm.wav --out mixed.wav
  python mix_under_voice.py --video clip.mp4 --music bgm.wav --out clip_scored.mp4
  python mix_under_voice.py --video clip.mp4 --voice vo.wav --music bgm.wav --out final.mp4

Music is looped/trimmed to length, ducked by the voice with a sidechain compressor
(about -12 dB while speaking, 0.4 s release), faded in/out, then loudness-normalised
to -16 LUFS (web/social standard). Without --voice the music is simply faded and
normalised under the video's own audio (kept at its level).
"""
import argparse, json, subprocess, sys


def dur(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', path],
                       capture_output=True, text=True, check=True)
    return float(json.loads(r.stdout)['format']['duration'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--voice')
    ap.add_argument('--video')
    ap.add_argument('--music', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--music-db', type=float, default=-14.0, help='music level before ducking (dB)')
    ap.add_argument('--fade', type=float, default=1.5)
    a = ap.parse_args()
    if not (a.voice or a.video):
        sys.exit('need --voice and/or --video')
    ref = a.video or a.voice
    T = dur(ref)
    fo = max(0.0, T - a.fade)
    mus = (f"[1:a]aloop=loop=-1:size=2e9,atrim=0:{T:.3f},asetpts=N/SR/TB,volume={a.music_db}dB,"
           f"afade=t=in:d={a.fade},afade=t=out:st={fo:.3f}:d={a.fade}[m]")
    inputs = []
    if a.video:
        inputs += ['-i', a.video]
    else:
        inputs += ['-i', a.voice]
    inputs += ['-i', a.music]
    voice_idx = None
    has_audio = bool(a.video) and subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index', '-of', 'csv=p=0', a.video],
        capture_output=True, text=True).stdout.strip() != ''
    if a.video and not a.voice and not has_audio:     # silent video: music only
        f = [mus.replace('[m]', '[a]')]
        cmd = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error'] + inputs + [
            '-filter_complex', ';'.join(f), '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac',
            '-b:a', '192k', '-shortest', a.out]
        subprocess.run(cmd, check=True)
        print(a.out)
        return
    if a.video and a.voice:
        inputs += ['-i', a.voice]
        voice_idx = 2
    elif a.voice:
        voice_idx = 0
    elif a.video:
        voice_idx = 0     # use the video's own audio as the "voice" for ducking
    f = [mus, f"[{voice_idx}:a]apad=whole_dur={T:.3f},asplit=2[v][vsc]",
         "[m][vsc]sidechaincompress=threshold=0.04:ratio=8:attack=20:release=400:makeup=1[md]",
         "[v][md]amix=inputs=2:duration=longest:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[a]"]
    cmd = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error'] + inputs + ['-filter_complex', ';'.join(f)]
    if a.video:
        cmd += ['-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-t', f'{T:.3f}']
    else:
        cmd += ['-map', '[a]', '-t', f'{T:.3f}']
    cmd.append(a.out)
    subprocess.run(cmd, check=True)
    print(a.out)


if __name__ == '__main__':
    main()
