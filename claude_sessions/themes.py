"""Theme palettes — the single source of truth for both UIs.

Every palette is authored in real hex. The GUI consumes them verbatim; the TUI
gets ANSI-256 codes derived here by nearest-cube quantization (``ansi_palette``).

That direction matters. The old arrangement was the reverse: ANSI-256 codes were
the source and the GUI re-derived every surface from the accent's *hue* alone,
so every dark theme was the same theme rotated on a colour wheel and none of the
named schemes (Tokyo Night, Gruvbox, Rosé Pine …) actually looked like itself —
their signature backgrounds can't even be expressed in a 6x6x6 cube.

Palette keys
  label/family/mode  gallery grouping and display name
  motion             motion personality: how far interactions travel and how much
                     they glow. One of 'crisp' | 'smooth' | 'lush', mapped to the
                     --mo-lift/--mo-glow/--mo-beam/--t-spring CSS vars by
                     applyTheme() (MOTION_PERSONA in app.js).

                     This used to name one of 26 generative background renderers
                     — a different animated wallpaper per theme. That layer is
                     gone: it painted abstract fields (rain, embers, petals) that
                     encoded real numbers nobody could read, in ~30 places at
                     once, looping whether or not anything had happened. Motion
                     is now transitional (fires on change, then settles) and
                     gauges are readable instruments, so what a palette gets to
                     choose is its *character*, not its own animation.
  accent/accent2     the --grad pair; keep them visibly distinct or the gradient
                     (logo, primary buttons, meters) collapses to one flat colour
  ok/warn/err        semantic states
  bg                 app background      bg2     sidebar / recessed surface
  panel              card surface        panel2  raised surface, selected row
  line               borders/hairlines   code    code blocks (deepest surface)
  txt/dim/dim2       body / secondary / tertiary text

Contrast floors (enforced by tests/test_themes.py): txt on bg and on panel >= 4.5:1,
dim on panel >= 3:1, accent on bg >= 3:1. Canonical upstream palettes are followed
except where they'd break those floors.
"""

# ── ANSI-256 quantization ────────────────────────────────────

# the 6 levels of the 216-colour cube (indices 16..231); 232..255 is a 24-step
# gray ramp. Inverse of gui._x256_hex, which decodes the same tables.
_CUBE = (0, 95, 135, 175, 215, 255)


def _rgb(h):
    n = int(h.lstrip('#'), 16)
    return (n >> 16) & 255, (n >> 8) & 255, n & 255


def _cube_idx(v):
    return min(range(6), key=lambda i: abs(_CUBE[i] - v))


def hex_to_x256(h):
    """Nearest ANSI-256 index for a hex colour, over the cube AND the gray ramp.

    0-15 are excluded on purpose: those are terminal-configurable, so a palette
    that lands on them stops being the palette the user chose."""
    r, g, b = _rgb(h)
    ri, gi, bi = _cube_idx(r), _cube_idx(g), _cube_idx(b)
    cr, cg, cb = _CUBE[ri], _CUBE[gi], _CUBE[bi]
    cube_d = (cr - r) ** 2 + (cg - g) ** 2 + (cb - b) ** 2

    gi_ = max(0, min(23, round(((r + g + b) / 3 - 8) / 10)))
    gv = 8 + 10 * gi_
    gray_d = (gv - r) ** 2 + (gv - g) ** 2 + (gv - b) ** 2

    return (16 + 36 * ri + 6 * gi + bi) if cube_d <= gray_d else (232 + gi_)


def _mix(a, b, t):
    """Blend hex a toward hex b by t (0..1)."""
    ar, ag, ab = _rgb(a)
    br, bg, bb = _rgb(b)
    return '#%02x%02x%02x' % (round(ar + (br - ar) * t),
                              round(ag + (bg - ag) * t),
                              round(ab + (bb - ab) * t))


def ansi_palette(p):
    """Build the TUI's switchable C_* entries from an authored hex palette.

    Shape (name -> SGR string) is exactly what config.apply_theme() expects, so
    every consumer of config.THEMES keeps working unchanged."""
    def fg(h):
        return '\033[38;5;%dm' % hex_to_x256(h)

    def bg(h):
        return '\033[48;5;%dm' % hex_to_x256(h)

    # header bar: a tinted accent, not a darkened one. Past ~35% toward the
    # background the colour desaturates enough that the 6x6x6 cube's nearest
    # neighbour is the gray ramp, and the header loses its hue entirely.
    if p['mode'] == 'light':
        head_bg, head_fg = _mix(p['accent'], '#000000', .12), '#ffffff'
    else:
        head_bg, head_fg = _mix(p['accent'], p['bg'], .30), p['txt']

    return {
        'C_ACCENT':    fg(p['accent']),
        'C_TITLE':     fg(p['accent2']),
        'C_OK':        fg(p['ok']),
        'C_WARN':      fg(p['warn']),
        'C_SRCH':      '\033[38;5;%d;1m' % hex_to_x256(p['accent2']),
        'C_STAR':      fg(p['warn']),
        'C_SEL_BG':    bg(p['panel2']) + fg(p['txt']),
        'C_HEADER_BG': bg(head_bg) + fg(head_fg),
    }


# ── palettes ─────────────────────────────────────────────────
# 29 themes: every main hue family plus four real light themes. The 17 original
# names are all kept (re-coloured, never renamed) so no saved settings.json
# breaks. `motion` is the personality, not a per-theme animation (see above).

PALETTES = {
    # ── cyan ──
    'default': {
        'label': 'Claudectl', 'family': 'cyan', 'mode': 'dark', 'motion': 'smooth',
        'accent': '#7dcfff', 'accent2': '#a78bfa', 'ok': '#3fdd9d',
        'warn': '#f7b955', 'err': '#ff6b81',
        'bg': '#0d1117', 'bg2': '#111827', 'panel': '#161e2e', 'panel2': '#1b2436',
        'line': '#2b3852', 'txt': '#dbe4f3', 'dim': '#98a5c0', 'dim2': '#6d7b96',
        'code': '#0a0e16',
    },
    'nord': {
        'label': 'Nord', 'family': 'cyan', 'mode': 'dark', 'motion': 'smooth',
        'accent': '#88c0d0', 'accent2': '#b48ead', 'ok': '#a3be8c',
        'warn': '#ebcb8b', 'err': '#d08087',
        'bg': '#2e3440', 'bg2': '#333b4a', 'panel': '#3b4252', 'panel2': '#434c5e',
        'line': '#4c566a', 'txt': '#eceff4', 'dim': '#d8dee9', 'dim2': '#a3adc2',
        'code': '#272c36',
    },
    # ── blue ──
    'tokyo': {
        'label': 'Tokyo Night', 'family': 'blue', 'mode': 'dark', 'motion': 'lush',
        'accent': '#7aa2f7', 'accent2': '#bb9af7', 'ok': '#9ece6a',
        'warn': '#e0af68', 'err': '#f7768e',
        'bg': '#1a1b26', 'bg2': '#1f2335', 'panel': '#24283b', 'panel2': '#2f334d',
        'line': '#3b4261', 'txt': '#c0caf5', 'dim': '#a9b1d6', 'dim2': '#7f88ad',
        'code': '#16161e',
    },
    'kanagawa': {
        'label': 'Kanagawa', 'family': 'blue', 'mode': 'dark', 'motion': 'smooth',
        'accent': '#7e9cd8', 'accent2': '#957fb8', 'ok': '#98bb6c',
        'warn': '#ffa066', 'err': '#e46876',
        'bg': '#1f1f28', 'bg2': '#252530', 'panel': '#2a2a37', 'panel2': '#363646',
        'line': '#54546d', 'txt': '#dcd7ba', 'dim': '#c8c093', 'dim2': '#9a9782',
        'code': '#16161d',
    },
    'solarized': {
        'label': 'Solarized Dark', 'family': 'blue', 'mode': 'dark', 'motion': 'crisp',
        'accent': '#4aa8e0', 'accent2': '#2aa198', 'ok': '#859900',
        'warn': '#b58900', 'err': '#ef5c58',
        'bg': '#002b36', 'bg2': '#01313d', 'panel': '#073642', 'panel2': '#0d4552',
        'line': '#1a5262', 'txt': '#93a1a1', 'dim': '#839496', 'dim2': '#6c8288',
        'code': '#001f27',
    },
    'slate': {
        'label': 'Slate', 'family': 'blue', 'mode': 'dark', 'motion': 'crisp',
        'accent': '#818cf8', 'accent2': '#22d3ee', 'ok': '#4ade80',
        'warn': '#fbbf24', 'err': '#f87171',
        'bg': '#08090a', 'bg2': '#0e0f11', 'panel': '#141518', 'panel2': '#1c1d21',
        'line': '#2a2b30', 'txt': '#ededef', 'dim': '#a1a1aa', 'dim2': '#7c7c86',
        'code': '#050506',
    },
    # ── azure / teal ──
    'ocean': {
        'label': 'Ocean', 'family': 'azure', 'mode': 'dark', 'motion': 'lush',
        'accent': '#38bdf8', 'accent2': '#2dd4bf', 'ok': '#34d399',
        'warn': '#fbbf24', 'err': '#fb7185',
        'bg': '#071a26', 'bg2': '#0a2230', 'panel': '#0e2b3b', 'panel2': '#123648',
        'line': '#1b4a5e', 'txt': '#d7ecf7', 'dim': '#9fc3d4', 'dim2': '#7b9dae',
        'code': '#04121b',
    },
    'poimandres': {
        'label': 'Poimandres', 'family': 'teal', 'mode': 'dark', 'motion': 'lush',
        'accent': '#5de4c7', 'accent2': '#89ddff', 'ok': '#5fb3a1',
        'warn': '#fffac2', 'err': '#ff5d5d',
        'bg': '#1b1e28', 'bg2': '#202430', 'panel': '#252b37', 'panel2': '#303340',
        'line': '#3d4356', 'txt': '#e4f0fb', 'dim': '#a6accd', 'dim2': '#868cae',
        'code': '#171922',
    },
    # ── green / sage ──
    'forest': {
        'label': 'Forest', 'family': 'green', 'mode': 'dark', 'motion': 'smooth',
        'accent': '#7ee787', 'accent2': '#56d4dd', 'ok': '#56d364',
        'warn': '#e3b341', 'err': '#f85149',
        'bg': '#0c1a10', 'bg2': '#102216', 'panel': '#14291b', 'panel2': '#1a3423',
        'line': '#275034', 'txt': '#d6f0dc', 'dim': '#9ec3a8', 'dim2': '#7c9c86',
        'code': '#08130b',
    },
    'everforest': {
        'label': 'Everforest', 'family': 'sage', 'mode': 'dark', 'motion': 'smooth',
        'accent': '#a7c080', 'accent2': '#d699b6', 'ok': '#83c092',
        'warn': '#dbbc7f', 'err': '#e67e80',
        'bg': '#2d353b', 'bg2': '#333c42', 'panel': '#3a4248', 'panel2': '#454f55',
        'line': '#4f5b62', 'txt': '#d3c6aa', 'dim': '#b3bcb0', 'dim2': '#96a196',
        'code': '#272e33',
    },
    # ── amber / yellow / orange ──
    'gruvbox': {
        'label': 'Gruvbox', 'family': 'amber', 'mode': 'dark', 'motion': 'smooth',
        'accent': '#fabd2f', 'accent2': '#d3869b', 'ok': '#b8bb26',
        'warn': '#fe8019', 'err': '#fb4934',
        'bg': '#282828', 'bg2': '#32302f', 'panel': '#3c3836', 'panel2': '#504945',
        'line': '#665c54', 'txt': '#ebdbb2', 'dim': '#bdae93', 'dim2': '#a89984',
        'code': '#1d2021',
    },
    'citrus': {
        'label': 'Citrus', 'family': 'yellow', 'mode': 'dark', 'motion': 'crisp',
        'accent': '#e6cc77', 'accent2': '#80a665', 'ok': '#4db38f',
        'warn': '#c99076', 'err': '#cb7676',
        'bg': '#121212', 'bg2': '#181818', 'panel': '#1e1e1e', 'panel2': '#262626',
        'line': '#363636', 'txt': '#dbd7ca', 'dim': '#a8a29a', 'dim2': '#87857d',
        'code': '#0d0d0d',
    },
    'ayu': {
        'label': 'Ayu Mirage', 'family': 'orange', 'mode': 'dark', 'motion': 'smooth',
        'accent': '#ff8f40', 'accent2': '#73d0ff', 'ok': '#d5ff80',
        'warn': '#ffcc66', 'err': '#f07178',
        'bg': '#1f2430', 'bg2': '#242936', 'panel': '#2a3040', 'panel2': '#343b4d',
        'line': '#3f4759', 'txt': '#cccac2', 'dim': '#a8aaa4', 'dim2': '#8a8f9c',
        'code': '#1a1f29',
    },
    # ── red / magenta ──
    'ember': {
        'label': 'Ember', 'family': 'red', 'mode': 'dark', 'motion': 'lush',
        'accent': '#ff6b6b', 'accent2': '#ffa94d', 'ok': '#94d82d',
        'warn': '#ffd43b', 'err': '#ff4d4f',
        'bg': '#1a1012', 'bg2': '#221518', 'panel': '#2a191d', 'panel2': '#351f24',
        'line': '#4b2b31', 'txt': '#f5dede', 'dim': '#cfa4a4', 'dim2': '#a88080',
        'code': '#130b0d',
    },
    'oxocarbon': {
        'label': 'Oxocarbon', 'family': 'magenta', 'mode': 'dark', 'motion': 'crisp',
        'accent': '#ee5396', 'accent2': '#be95ff', 'ok': '#42be65',
        'warn': '#ff832b', 'err': '#fa4d56',
        'bg': '#161616', 'bg2': '#1c1c1c', 'panel': '#262626', 'panel2': '#333333',
        'line': '#404040', 'txt': '#f2f4f8', 'dim': '#c1c7cd', 'dim2': '#9a9a9a',
        'code': '#0d0d0d',
    },
    # ── purple / violet / rose ──
    'dracula': {
        'label': 'Dracula', 'family': 'purple', 'mode': 'dark', 'motion': 'lush',
        'accent': '#bd93f9', 'accent2': '#ff79c6', 'ok': '#50fa7b',
        'warn': '#ffb86c', 'err': '#ff5555',
        'bg': '#282a36', 'bg2': '#2e3140', 'panel': '#343746', 'panel2': '#44475a',
        'line': '#4f5368', 'txt': '#f8f8f2', 'dim': '#bcc0d0', 'dim2': '#8b93b8',
        'code': '#21222c',
    },
    'mocha': {
        'label': 'Catppuccin Mocha', 'family': 'violet', 'mode': 'dark', 'motion': 'lush',
        'accent': '#cba6f7', 'accent2': '#89b4fa', 'ok': '#a6e3a1',
        'warn': '#fab387', 'err': '#f38ba8',
        'bg': '#1e1e2e', 'bg2': '#181825', 'panel': '#313244', 'panel2': '#45475a',
        'line': '#585b70', 'txt': '#cdd6f4', 'dim': '#bac2de', 'dim2': '#9399b2',
        'code': '#11111b',
    },
    'monokai-pro': {
        'label': 'Monokai Pro', 'family': 'violet', 'mode': 'dark', 'motion': 'smooth',
        'accent': '#ab9df2', 'accent2': '#ff6188', 'ok': '#a9dc76',
        'warn': '#ffd866', 'err': '#ff6188',
        'bg': '#2d2a2e', 'bg2': '#221f22', 'panel': '#363336', 'panel2': '#403e41',
        'line': '#5b595c', 'txt': '#fcfcfa', 'dim': '#c1c0c0', 'dim2': '#a1a09f',
        'code': '#19181a',
    },
    'rose': {
        'label': 'Rosé Pine', 'family': 'rose', 'mode': 'dark', 'motion': 'lush',
        'accent': '#ebbcba', 'accent2': '#c4a7e7', 'ok': '#9ccfd8',
        'warn': '#f6c177', 'err': '#eb6f92',
        'bg': '#191724', 'bg2': '#1f1d2e', 'panel': '#26233a', 'panel2': '#403d52',
        'line': '#524f67', 'txt': '#e0def4', 'dim': '#908caa', 'dim2': '#807c99',
        'code': '#16141f',
    },
    # ── neutral ──
    'mono': {
        'label': 'Mono', 'family': 'neutral', 'mode': 'dark', 'motion': 'crisp',
        'accent': '#ededed', 'accent2': '#9e9e9e', 'ok': '#d4d4d4',
        'warn': '#fafafa', 'err': '#bdbdbd',
        'bg': '#0a0a0a', 'bg2': '#101010', 'panel': '#171717', 'panel2': '#212121',
        'line': '#333333', 'txt': '#ededed', 'dim': '#a3a3a3', 'dim2': '#858585',
        'code': '#050505',
    },
    'vesper': {
        'label': 'Vesper', 'family': 'neutral', 'mode': 'dark', 'motion': 'crisp',
        'accent': '#ffc799', 'accent2': '#99ffe4', 'ok': '#7fdbaf',
        'warn': '#ffcb6b', 'err': '#ff8080',
        'bg': '#101010', 'bg2': '#161616', 'panel': '#1c1c1c', 'panel2': '#252525',
        'line': '#343434', 'txt': '#ffffff', 'dim': '#a8a8a8', 'dim2': '#8b8b8b',
        'code': '#0b0b0b',
    },
    'ink': {
        'label': 'Flexoki Ink', 'family': 'neutral', 'mode': 'dark', 'motion': 'crisp',
        'accent': '#4385be', 'accent2': '#ce5d97', 'ok': '#879a39',
        'warn': '#d0a215', 'err': '#d14d41',
        'bg': '#100f0f', 'bg2': '#1c1b1a', 'panel': '#282726', 'panel2': '#343331',
        'line': '#403e3c', 'txt': '#cecdc3', 'dim': '#b7b5ac', 'dim2': '#918f88',
        'code': '#0a0a0a',
    },
    # ── HUD ──
    # Drawn from the reference dashboards in references/: near-black grounds with
    # one saturated cyan/magenta pair, the look those neon control panels get from
    # putting *all* the colour in the data and none in the surface. Deliberately
    # darker grounds than the rest of the set — the instrument arcs and tick rings
    # need somewhere to glow against.
    'neon': {
        'label': 'Neon HUD', 'family': 'cyan', 'mode': 'dark', 'motion': 'lush',
        'accent': '#22d3ee', 'accent2': '#f472b6', 'ok': '#34d399',
        'warn': '#fbbf24', 'err': '#fb7185',
        'bg': '#050810', 'bg2': '#0a0f1c', 'panel': '#0e1526', 'panel2': '#151f36',
        'line': '#1f2f4d', 'txt': '#dbeafe', 'dim': '#93b4d8', 'dim2': '#6b8bb0',
        'code': '#03060d',
    },
    'aurora': {
        'label': 'Aurora', 'family': 'violet', 'mode': 'dark', 'motion': 'lush',
        'accent': '#a78bfa', 'accent2': '#5eead4', 'ok': '#4ade80',
        'warn': '#fcd34d', 'err': '#fb7185',
        'bg': '#0a0a14', 'bg2': '#101024', 'panel': '#16162e', 'panel2': '#1e1e3d',
        'line': '#2c2c56', 'txt': '#e4e4f7', 'dim': '#a9a9d0', 'dim2': '#8484ac',
        'code': '#07070f',
    },
    # the pastel-on-black weather dashboard: a neutral near-black carrying pastel
    # accents, so charts read as colour and chrome reads as nothing
    'noir': {
        'label': 'Noir Pastel', 'family': 'neutral', 'mode': 'dark', 'motion': 'smooth',
        'accent': '#c4b5fd', 'accent2': '#86efac', 'ok': '#86efac',
        'warn': '#fde68a', 'err': '#fca5a5',
        'bg': '#0b0b0d', 'bg2': '#111114', 'panel': '#17171b', 'panel2': '#202026',
        'line': '#2e2e35', 'txt': '#ededf0', 'dim': '#a8a8b2', 'dim2': '#84848f',
        'code': '#070708',
    },
    # ── light ──
    'catppuccin-latte': {
        'label': 'Catppuccin Latte', 'family': 'light', 'mode': 'light', 'motion': 'smooth',
        'accent': '#8839ef', 'accent2': '#1e66f5', 'ok': '#40a02b',
        'warn': '#a86400', 'err': '#d20f39',
        'bg': '#eff1f5', 'bg2': '#e6e9ef', 'panel': '#ffffff', 'panel2': '#e6e9ef',
        'line': '#ccd0da', 'txt': '#4c4f69', 'dim': '#5c5f77', 'dim2': '#6c6f85',
        'code': '#dce0e8',
    },
    'dawn': {
        'label': 'Rosé Pine Dawn', 'family': 'light', 'mode': 'light', 'motion': 'smooth',
        'accent': '#907aa9', 'accent2': '#b4637a', 'ok': '#286983',
        'warn': '#9c6812', 'err': '#93395a',
        'bg': '#faf4ed', 'bg2': '#f2e9e1', 'panel': '#fffaf3', 'panel2': '#f4ede8',
        'line': '#dfdad9', 'txt': '#575279', 'dim': '#6a6685', 'dim2': '#797593',
        'code': '#f2e9e1',
    },
    'paper': {
        'label': 'Flexoki Paper', 'family': 'light', 'mode': 'light', 'motion': 'crisp',
        'accent': '#205ea6', 'accent2': '#a02f6f', 'ok': '#66800b',
        'warn': '#ad8301', 'err': '#af3029',
        'bg': '#fffcf0', 'bg2': '#f2f0e5', 'panel': '#ffffff', 'panel2': '#f2f0e5',
        'line': '#dad8ce', 'txt': '#100f0f', 'dim': '#575653', 'dim2': '#6f6e69',
        'code': '#f2f0e5',
    },
    'mono-light': {
        'label': 'Mono Light', 'family': 'light', 'mode': 'light', 'motion': 'crisp',
        'accent': '#171717', 'accent2': '#525252', 'ok': '#404040',
        'warn': '#6b6b6b', 'err': '#8a8a8a',
        'bg': '#fafafa', 'bg2': '#f2f2f2', 'panel': '#ffffff', 'panel2': '#f0f0f0',
        'line': '#e0e0e0', 'txt': '#171717', 'dim': '#4a4a4a', 'dim2': '#6b6b6b',
        'code': '#f2f2f2',
    },
}

# colour keys every palette carries — the GUI maps these straight to CSS vars
COLOR_KEYS = ('accent', 'accent2', 'ok', 'warn', 'err',
              'bg', 'bg2', 'panel', 'panel2', 'line', 'txt', 'dim', 'dim2', 'code')

PALETTE_NAMES = list(PALETTES)


# ── skins ────────────────────────────────────────────────────
"""A palette answers "what colours". A skin answers "what IS this app".

The two are orthogonal: any palette renders under any skin, so 29 x 7. Each
palette names a default skin that suits its colours, and the user can override.

Skins exist because a palette alone cannot make the app feel like anything — every
theme rendered the same rounded-6px card in a different hue. A skin owns the
*shape* of the thing: corner treatment, border weight, surface fill, edge
treatment, heading type, how cards arrive, how modals open, and how a gauge is
stroked.

A skin used to be chrome only — radius, border, one texture, a heading font —
which was not enough: every theme still read as the same app in a different hue.
It now owns the CHASSIS. Layout frame, topbar shape, type scale, row density,
surface translucency, how the page arrives, and which animated background runs
behind the whole app.

Keys — chrome
  label/blurb    what the picker shows
  radius/border  card geometry, in px
  shadow         card box-shadow (offset-hard for brutal, soft or none elsewhere)
  surface        extra background layer painted on a card ('' = flat panel)
  edge           border/inset treatment
  font           heading font stack. WINDOWS SYSTEM FONTS ONLY — the GUI is
                 self-contained and offline by design, so no webfont may be
                 introduced here. Bahnschrift and Segoe UI Variable ship with
                 Win10+; Consolas/Cascadia with every Windows.
  track/caps     heading letter-spacing and text-transform
  ease           the skin's own motion curve (overrides the palette personality
                 for skin-owned animation: entrances, modal open, page change)
  enter          card entrance choreography, keyed in SKIN_ENTER (motion.js)
  burst          the one-shot signature effect, keyed in MO_BURST (motion.js)
  gauge          how instruments.js strokes an arc: tick shape, line cap, stroke
                 weight multiplier, glow strength

Keys — chassis
  chassis        the viewport frame itself: 'brackets' (corner rules + a live
                 status rail), 'console' (hard bar + left indicator column),
                 'bezel' (rounded screen inside a vignette), 'float' (panels
                 hovering clear of the edges), 'none'
  scale          type-scale multiplier. This is most of why one skin reads as a
                 different application from another — Brutalist's headings are
                 20% larger than Terminal's, not merely a different family.
  density        row/padding multiplier. Airy Sakura vs tight Mecha.
  topbar         'flat' | 'notch' (clipped corner) | 'rail' (tick ruler beneath)
  arrive         page-arrival timeline, keyed in SKIN_ARRIVE (motion.js). The
                 whole page is choreographed, not each card independently.
  op             surface opacity, 0..1. THE reason the stage is visible at all:
                 fully opaque panels would hide it everywhere but the gutters.
                 Applied via rgba() on --panel-rgb — never via `filter` or
                 `backdrop-filter`, which are what tore the Qt compositor.
  stage          which background scene runs (STAGE_SCENES in stage.js)
  bloom          bloom strength for that scene; 0 disables the composer entirely
                 (two render targets saved), which is what brutal/crt want

THE RULE: every `burst` is event-scoped — it fires on mount, open or launch, runs
ONCE, and removes itself. None of them loop. Petals falling forever is the ambient
wallpaper this project deleted; petals bursting once when a session launches is
feedback. tests/test_skins.py enforces the one-shot part.

The stage is the ONE deliberate exception, and it is not a counter-example: it is
a single surface behind everything rather than thirty inside the content, it is
driven by real workspace state rather than free-running, and it stops on hidden,
blur, motion:off and stage:off. See the header of stage.js.
"""

SKINS = {
    'hud': {
        'label': 'HUD', 'blurb': 'Instrument panel over a wireframe horizon. Corner brackets, range rings, radar sweep.',
        'radius': 4, 'border': 1, 'shadow': 'none',
        'surface': 'grid', 'edge': 'brackets',
        'font': 'var(--mono)', 'track': '.10em', 'caps': 'uppercase',
        'ease': 'cubic-bezier(.2,.9,.3,1)',
        'enter': 'wipe', 'burst': 'brackets',
        'gauge': {'tick': 'line', 'cap': 'round', 'lw': 1.0, 'glow': .5},
        'chassis': 'brackets', 'scale': 1.0, 'density': .94, 'topbar': 'rail',
        'arrive': 'boot', 'op': .84, 'stage': 'hud', 'bloom': .55,
    },
    'sakura': {
        'label': 'Sakura', 'blurb': 'Soft anime. Petals drifting through colour blooms, airy panels, big radii.',
        'radius': 18, 'border': 1, 'shadow': 'soft',
        'surface': 'wash', 'edge': 'soft',
        'font': '"Segoe UI Variable Display","Segoe UI Semibold","Segoe UI",system-ui,sans-serif',
        'track': '.01em', 'caps': 'none',
        'ease': 'cubic-bezier(.34,1.4,.5,1)',
        'enter': 'bloom', 'burst': 'petals',
        'gauge': {'tick': 'dot', 'cap': 'round', 'lw': 1.25, 'glow': .8},
        'chassis': 'float', 'scale': 1.06, 'density': 1.18, 'topbar': 'flat',
        'arrive': 'bloom', 'op': .80, 'stage': 'sakura', 'bloom': .5,
    },
    'mecha': {
        'label': 'Mecha', 'blurb': 'NERV console. A hex panel wall snapping in blocks, hazard stripes, no easing.',
        'radius': 0, 'border': 2, 'shadow': 'none',
        'surface': 'stripe', 'edge': 'heavy',
        'font': '"Bahnschrift Condensed","Bahnschrift SemiCondensed",'
                '"Franklin Gothic Medium Cond","Arial Narrow",Impact,sans-serif',
        'track': '.16em', 'caps': 'uppercase',
        'ease': 'steps(1,end)',
        'enter': 'cut', 'burst': 'stripe',
        'gauge': {'tick': 'block', 'cap': 'butt', 'lw': 1.6, 'glow': .2},
        'chassis': 'console', 'scale': 1.16, 'density': .86, 'topbar': 'notch',
        'arrive': 'slam', 'op': .90, 'stage': 'mecha', 'bloom': .35,
    },
    'neon-city': {
        'label': 'Neon City', 'blurb': 'Cyberpunk. An endless neon flythrough behind scanlined glass, heavy bloom.',
        'radius': 2, 'border': 1, 'shadow': 'glow',
        'surface': 'scan', 'edge': 'chroma',
        'font': 'var(--mono)', 'track': '.14em', 'caps': 'uppercase',
        'ease': 'cubic-bezier(.16,1,.3,1)',
        'enter': 'glitch', 'burst': 'scan',
        'gauge': {'tick': 'line', 'cap': 'butt', 'lw': 1.15, 'glow': 1.0},
        'chassis': 'brackets', 'scale': 1.02, 'density': .94, 'topbar': 'rail',
        'arrive': 'glitch', 'op': .76, 'stage': 'neon-city', 'bloom': .9,
    },
    'crt': {
        'label': 'Terminal', 'blurb': 'Retro CRT in a bezel. Curved raster, rolling refresh, phosphor glow.',
        'radius': 0, 'border': 1, 'shadow': 'none',
        'surface': 'scan', 'edge': 'double',
        'font': 'var(--mono)', 'track': '.06em', 'caps': 'lowercase',
        'ease': 'steps(12,end)',
        'enter': 'type', 'burst': 'caret',
        'gauge': {'tick': 'block', 'cap': 'butt', 'lw': 1.0, 'glow': .7},
        # bloom 0: the tube's glow is drawn in the scene shader itself, so the
        # composer would only cost two render targets to duplicate it
        'chassis': 'bezel', 'scale': .98, 'density': .92, 'topbar': 'flat',
        'arrive': 'type', 'op': .88, 'stage': 'crt', 'bloom': 0,
    },
    'brutal': {
        'label': 'Brutalist', 'blurb': 'Halftone dot field, thick borders, hard offset shadows, zero easing.',
        'radius': 0, 'border': 3, 'shadow': 'hard',
        'surface': '', 'edge': 'heavy',
        'font': '"Arial Black","Segoe UI Black",Impact,system-ui,sans-serif',
        'track': '-.01em', 'caps': 'uppercase',
        'ease': 'linear',
        'enter': 'slam', 'burst': 'snap',
        'gauge': {'tick': 'block', 'cap': 'butt', 'lw': 2.0, 'glow': 0},
        # op 1.0 and bloom 0 on purpose: brutalism does not do translucency and
        # it does not do glow. The stage shows in the gutters, and that is all.
        'chassis': 'none', 'scale': 1.20, 'density': 1.0, 'topbar': 'flat',
        'arrive': 'slam', 'op': 1.0, 'stage': 'brutal', 'bloom': 0,
    },
    'glass': {
        # DELIBERATELY faked. Real glassmorphism wants backdrop-filter: blur(),
        # which is the property that caused this project's QtWebEngine tearing and
        # which tests/test_gui_flicker.py now forbids outright. Layered translucent
        # gradients + a 1px inset highlight + a hairline border read as glass with
        # zero framebuffer readback. Do not "fix" this by adding the blur back.
        #
        # It got much more convincing for free: with a live caustic scene behind
        # the lowest `op` in the set, there is now something real to be translucent
        # *over*, which is the half that was always missing.
        'label': 'Glass', 'blurb': 'Liquid caustics under floating translucent panels (no blur — see themes.py).',
        'radius': 14, 'border': 1, 'shadow': 'soft',
        'surface': 'sheen', 'edge': 'inset',
        'font': '"Segoe UI Variable Text","Segoe UI",system-ui,sans-serif',
        'track': '.02em', 'caps': 'none',
        'ease': 'cubic-bezier(.22,1,.36,1)',
        'enter': 'lift', 'burst': 'sheen',
        'gauge': {'tick': 'dot', 'cap': 'round', 'lw': 1.1, 'glow': .6},
        'chassis': 'float', 'scale': 1.0, 'density': 1.12, 'topbar': 'flat',
        'arrive': 'lift', 'op': .66, 'stage': 'glass', 'bloom': .75,
    },
}

SKIN_NAMES = list(SKINS)

#: keys every skin must define — tests/test_skins.py rejects a partial skin,
#: because a missing token silently falls back and the skin becomes a no-op
SKIN_KEYS = ('label', 'blurb', 'radius', 'border', 'shadow', 'surface', 'edge',
             'font', 'track', 'caps', 'ease', 'enter', 'burst', 'gauge',
             'chassis', 'scale', 'density', 'topbar', 'arrive', 'op',
             'stage', 'bloom')

#: the background scenes stage.js implements, one per skin. Kept here so
#: tests/test_stage.py can assert the two sides never drift apart — a skin
#: naming a scene that does not exist would silently fall back to 'hud'.
STAGE_SCENES = ('hud', 'sakura', 'mecha', 'neon-city', 'crt', 'brutal', 'glass')

#: how much of the stage runs. 'cinematic' = bloom (two extra render targets);
#: 'lite' = the scene without the composer, the first thing to try if the Qt
#: shell ever tears; 'off' = no GL at all, the static CSS gradient instead.
STAGE_TIERS = ('cinematic', 'lite', 'off')

#: which skin each palette wears by default. Chosen so the pairing reads as one
#: idea — Neon HUD under HUD, the pastel/rose palettes under Sakura, the warm
#: high-contrast ones under Mecha, the monochromes under Terminal.
DEFAULT_SKIN = {
    'neon': 'neon-city', 'aurora': 'glass', 'noir': 'sakura',
    'default': 'hud', 'slate': 'hud', 'poimandres': 'hud', 'ocean': 'hud',
    'tokyo': 'neon-city', 'oxocarbon': 'neon-city', 'dracula': 'neon-city',
    'ember': 'mecha', 'gruvbox': 'mecha', 'ayu': 'mecha',
    'mono': 'crt', 'vesper': 'crt', 'citrus': 'crt', 'ink': 'crt',
    'mono-light': 'brutal', 'paper': 'brutal', 'catppuccin-latte': 'brutal',
    'rose': 'sakura', 'dawn': 'sakura', 'mocha': 'sakura',
    'monokai-pro': 'glass', 'kanagawa': 'glass', 'nord': 'glass',
    'forest': 'sakura', 'everforest': 'sakura', 'solarized': 'crt',
}
for _n in PALETTES:
    PALETTES[_n]['skin'] = DEFAULT_SKIN.get(_n, 'hud')
