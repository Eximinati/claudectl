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
    from . import transcripts
    for n in transcripts.session_files(folder, limit=max_files):
        for obj in transcripts.iter_json(os.path.join(folder, n), limit=max_lines):
            cwd = obj.get('cwd')
            if cwd and os.path.isdir(cwd):
                return cwd
    return None


#: folder -> (mtime_ns, real path). `/api/state`, `/api/search-index`, the usage
#: endpoints and a `/api/dashboard` that polls every 10 s each call this once
#: PER PROJECT, and every call opens up to three transcripts. The folder's mtime
#: changes whenever a session is written, which is exactly when the answer could
#: have changed, so this can never go stale. Keyed by folder rather than by
#: (folder, mtime) so it stays bounded by the number of projects.
_path_cache = {}


def find_actual_path(encoded, max_depth=8, folder=None):
    if folder:
        try:
            mtime = os.stat(folder).st_mtime_ns
        except OSError:
            mtime = None
        hit = _path_cache.get(folder)
        if hit and mtime is not None and hit[0] == mtime:
            return hit[1]
        got = path_from_transcripts(folder)
        if got:
            if mtime is not None:
                _path_cache[folder] = (mtime, got)
            return got
    # Fallback only — the transcript's own `cwd` above is exact, and this walk
    # is guesswork against a lossy encoding. Where it STARTS is the only
    # platform-specific part: 'D--Claude' names a drive, '-home-mab-proj' names
    # the root.
    if os.name == 'nt':
        if '--' not in encoded:
            return None
        drive_part, rest = encoded.split('--', 1)
        if not drive_part:      # UNC (leading '--'); only the transcript knows it
            return None
        base = drive_part + ':\\'
        fold = str.lower                       # NTFS is case-insensitive
    else:
        if not encoded.startswith('-'):
            return None
        base, rest = '/', encoded[1:]
        fold = str                             # and POSIX is not
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
        rem_l = fold(remaining)
        for subdir in subdirs:
            enc = fold(encode_component(subdir))
            if enc == rem_l:
                return os.path.join(current, subdir)
            if rem_l.startswith(enc + '-'):
                r = match(os.path.join(current, subdir), remaining[len(enc)+1:], depth+1)
                if r:
                    return r
        return None

    return match(base, rest, 0)
