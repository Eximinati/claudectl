import json
import os
import re


# ── path resolution ──────────────────────────────────────────

# Claude Code encodes each path component with /[^a-zA-Z0-9]/g -> '-'
# (verified against claude.exe). ASCII-only: dots, spaces, _, +, #, parens,
# AND non-ASCII letters (accents, CJK) all collapse to '-'. Mirror it
# exactly — Python's str.isalnum() is Unicode-aware and would wrongly keep
# accented chars, so use an explicit ASCII class instead.
_NON_ALNUM = re.compile(r'[^a-zA-Z0-9]')


def encode_component(name):
    return _NON_ALNUM.sub('-', name)


def resolve_dir(raw):
    """Absolute existing directory, or ''. The single validator for any path that
    arrives from a request body before it becomes a subprocess `cwd`."""
    raw = (raw or '').strip()
    if not raw:
        return ''
    cand = os.path.abspath(os.path.expandvars(os.path.expanduser(raw)))
    return cand if os.path.isdir(cand) else ''


def path_from_transcripts(folder, max_files=3, max_lines=40):
    """The real path, read from what Claude Code itself recorded.

    Every transcript line carries `cwd`. Decoding the folder NAME cannot work in
    general — the encoding maps every non-alnum character to '-', so it is lossy
    — and for a UNC path it fails outright: `\\\\server\\share\\P` encodes to
    `--server-share-P`, whose leading '--' makes the drive-letter split below
    yield an empty drive. Reading the recorded value is both exact and cheaper
    than the recursive directory walk it replaces."""
    try:
        names = sorted((n for n in os.listdir(folder) if n.endswith('.jsonl')),
                       key=lambda n: os.path.getmtime(os.path.join(folder, n)),
                       reverse=True)[:max_files]
    except OSError:
        return None
    for n in names:
        try:
            with open(os.path.join(folder, n), encoding='utf-8', errors='ignore') as f:
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    cwd = obj.get('cwd') if isinstance(obj, dict) else None
                    if cwd and os.path.isdir(cwd):
                        return cwd
        except OSError:
            continue
    return None


def find_actual_path(encoded, max_depth=8, folder=None):
    if folder:
        got = path_from_transcripts(folder)
        if got:
            return got
    if '--' not in encoded:
        return None
    drive_part, rest = encoded.split('--', 1)
    if not drive_part:          # UNC (leading '--'); only the transcript knows it
        return None
    base = drive_part + ':\\'
    if not os.path.exists(base):
        return None

    def match(current, remaining, depth):
        if not remaining:
            return current
        if depth > max_depth:
            return None
        try:
            subdirs = [d for d in os.listdir(current)
                       if os.path.isdir(os.path.join(current, d))]
        except (PermissionError, OSError):
            return None
        rem_l = remaining.lower()
        for subdir in subdirs:
            enc = encode_component(subdir).lower()   # NTFS is case-insensitive
            if enc == rem_l:
                return os.path.join(current, subdir)
            if rem_l.startswith(enc + '-'):
                r = match(os.path.join(current, subdir), remaining[len(enc)+1:], depth+1)
                if r:
                    return r
        return None

    return match(base, rest, 0)
