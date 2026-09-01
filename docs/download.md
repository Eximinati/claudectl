---
title: Download claudectl
description: >-
  Every way to get claudectl — pipx, pip, the GitHub release page, the Claude Code plugin
  marketplace and a source checkout — plus what each release contains and how versions work.
jsonld: |
  {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "name": "claudectl",
    "applicationCategory": "DeveloperApplication",
    "operatingSystem": "Windows, macOS, Linux",
    "url": "https://claudectl.vercel.app/download/",
    "downloadUrl": "https://pypi.org/project/claudectl/",
    "installUrl": "https://pypi.org/project/claudectl/",
    "codeRepository": "https://github.com/babarmuhammad/claudectl",
    "softwareRequirements": "Python 3.10 or newer; Claude Code CLI",
    "license": "https://opensource.org/licenses/MIT",
    "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}
  }
---

# Download

claudectl is one pure-Python package with **zero runtime dependencies**. There is nothing
to compile and no platform-specific build — the same wheel runs on Windows, macOS and
Linux.

## From PyPI

```
pipx install claudectl     # or: pip install claudectl
```

[:material-package-variant: claudectl on PyPI](https://pypi.org/project/claudectl/){ .md-button }

That is the recommended route. It gives you `claudectl`, `claudectl --gui`,
`claudectl review`, `claudectl recall "<topic>"` and `claudectl statusline` on your PATH.
Upgrade the same way you installed:

```
pipx upgrade claudectl     # or: pip install --upgrade claudectl
```

## From the release page

Every tagged version publishes a wheel (`.whl`) and a source distribution (`.tar.gz`),
built and uploaded by GitHub Actions using PyPI [trusted publishing][tp] — no API token
is stored anywhere, and the tag is checked against the version in `pyproject.toml` before
anything is uploaded.

[:material-github: Releases on GitHub](https://github.com/babarmuhammad/claudectl/releases){ .md-button }

To install a downloaded artifact directly:

```
pip install claudectl-1.8.2-py3-none-any.whl
```

## From source

```
git clone https://github.com/babarmuhammad/claudectl.git
cd claudectl
python claude-sessions.py
```

No build step and nothing to install. See the [install guide](install.md) for putting a
checkout on your PATH, the desktop GUI window and the Windows shortcuts.

## As a Claude Code plugin

```
/plugin marketplace add babarmuhammad/claudectl
/plugin install claudectl
```

This adds the slash commands and skills to a Claude Code session. It is independent of
the CLI install — the plugin ships no hooks, because claudectl's own hook manager owns
those entries in `settings.json`.

## What is in a release

| Artifact | Where | What it is |
|---|---|---|
| `claudectl-<version>-py3-none-any.whl` | PyPI, GitHub release | The package. Pure Python, no compiled extensions |
| `claudectl-<version>.tar.gz` | PyPI, GitHub release | Source distribution |
| Source (zip / tar.gz) | GitHub release | The repository at that tag |
| Release notes | GitHub release, [changelog](changelog.md) | Keep a Changelog format |

## Versions

Releases follow [semantic versioning](https://semver.org/): the patch digit is fixes
only, the minor digit adds features without breaking a saved `claudectl.json`, and a
major bump would change something you would have to act on. Settings written by a newer
version are preserved by an older one — `load_settings` carries keys it does not
recognise — so downgrading does not erase configuration.

Current numbers, download counts and release history are on the
[project dashboard](dashboard.md).

## Requirements

- Python 3.10 or newer
- Windows, macOS or Linux
- The [Claude Code CLI](https://docs.anthropic.com/claude-code)
- PyQt6 — **optional**, only for the native desktop shell. Without it the GUI opens in
  your browser.

No API key. claudectl uses the Claude Code authentication you already have.

[tp]: https://docs.pypi.org/trusted-publishers/
