#!/usr/bin/env python3
"""Install bgm-music into Claude Code and (optionally) teach your other video skills to use it.

  python install.py              install + add a marked 'Soundtrack' block to video-related skills
  python install.py --no-patch   install only (the skill's own description still triggers it)
  python install.py --uninstall  remove the skill and every block this installer added
  python install.py --dir PATH   use a different skills directory (default ~/.claude/skills)

Patching is conservative: only SKILL.md files that mention video/Remotion/Hyperframes/etc,
one backup per file (SKILL.md.bgm-backup), a clearly delimited block, idempotent.
"""
import argparse, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BEGIN, END = '<!-- bgm-music:begin -->', '<!-- bgm-music:end -->'
TARGET = re.compile(r'video|remotion|hyperframes|veo\b|sora\b|runway|kling|影片|short-form|reel', re.I)

BLOCK = f'''{BEGIN}
## Soundtrack (added by bgm-music)

Every video this skill produces should end with a soundtrack. Do not ship it silent.
Use the `bgm-music` skill's one-shot scorer (mood from the brief, exact length, sections
on scene cuts, best of N seeds by measured quality, ducked under narration):

```bash
S=~/.claude/skills/bgm-music/scripts
python $S/score_video.py --video out.mp4 [--voice narration.wav] --brief "<what the video is>" --out out_scored.mp4
python $S/score_video.py --frames <durationInFrames> --fps <fps> --brief "<what it is>" --audio-out public/bgm.mp3  # Remotion
```
Then evaluate/report honestly (the scorer prints a JSON report with the measured score).
{END}
'''


def skills_dir(arg):
    return os.path.expanduser(arg or '~/.claude/skills')


def strip_block(text):
    return re.sub(r'\n?' + re.escape(BEGIN) + r'.*?' + re.escape(END) + r'\n?', '\n', text, flags=re.S)


def targets(root):
    for name in sorted(os.listdir(root)):
        if name == 'bgm-music':
            continue
        f = os.path.join(root, name, 'SKILL.md')
        if os.path.isfile(f):
            yield name, f


def check_deps():
    ok = True
    try:
        import numpy  # noqa: F401
    except ImportError:
        print('! numpy missing:  pip install numpy'); ok = False
    for tool in ('ffmpeg', 'ffprobe'):
        if not shutil.which(tool):
            print(f'! {tool} not found on PATH (https://ffmpeg.org/download.html)'); ok = False
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dir')
    ap.add_argument('--no-patch', action='store_true')
    ap.add_argument('--uninstall', action='store_true')
    a = ap.parse_args()
    root = skills_dir(a.dir)
    dest = os.path.join(root, 'bgm-music')

    if a.uninstall:
        for name, f in targets(root) if os.path.isdir(root) else []:
            t = open(f, encoding='utf-8', newline='').read()
            if BEGIN in t:
                open(f, 'w', encoding='utf-8', newline='').write(strip_block(t).rstrip() + '\n')
                print('unpatched', name)
        shutil.rmtree(dest, ignore_errors=True)
        print('removed', dest)
        return

    os.makedirs(root, exist_ok=True)
    src = os.path.join(HERE, 'skills', 'bgm-music')
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns('__pycache__'))
    print('installed', dest)
    deps = check_deps()

    if not a.no_patch:
        n = 0
        for name, f in targets(root):
            t = open(f, encoding='utf-8', newline='').read()
            head = t[:2500]
            if BEGIN in t or 'bgm-music' in t or not TARGET.search(head):
                continue
            bak = f + '.bgm-backup'
            if not os.path.exists(bak):
                shutil.copy2(f, bak)
            open(f, 'w', encoding='utf-8', newline='').write(t.rstrip() + '\n\n' + BLOCK)
            print('patched', name)
            n += 1
        print(f'{n} video-related skill(s) now score their output.' if n else 'no other video skills found to patch.')

    r = subprocess.run([sys.executable, os.path.join(dest, 'scripts', 'bgm.py'), '--mood', 'calm', '--duration', '8',
                        '--out', os.path.join(dest, '.selftest.wav')], capture_output=True, text=True)
    st = os.path.join(dest, '.selftest.wav')
    if os.path.exists(st):
        os.remove(st)
    print('self-test:', 'OK' if r.returncode == 0 else 'FAILED\n' + r.stderr[-400:])
    if not deps or r.returncode:
        sys.exit(1)


if __name__ == '__main__':
    main()
