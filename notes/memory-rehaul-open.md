# Memory / CLAUDE.md rehaul — what is still open

Last updated 2026-09-01. The session that did most of this work (`1f5e732a`,
Lorenzo account, 21:32–23:29) hit its Claude session limit **mid-`Edit`**, in the
middle of the last item it started; this note reconstructs where it stopped, from
that session's transcript, and tracks what is finished against what is not.

Companion: `notes/memory-ui-research.md` (the cited research the restructure
applies), `notes/memory-tabs-rehaul.md` (the original brief).

---

## 0. State of the tree

`main` is at `acbbee1`. The rehaul is **uncommitted** in the working tree, plus
two new untracked tests (`tests/test_gui_memory_surface.py`) and these notes.

Verified 2026-09-01 after the bucket restructure:

- `pytest tests/` — **1698 passed, 1 skipped**
- `ruff check --select E9,F821,F811,F632,F702,B023,B006,B002` — clean
- `py tools/smoke_gui.py` — **150 checks**, FAILURES none, JS errors none
- `py tools/shot_gui.py` — every page and all 9 project tabs clean, all 7 skins.
  `RAGGED` on the per-skin audit is the pre-existing dashboard row, unchanged.

One caveat on the suite: a run taken while auto-memory happened to be rewriting
`.claude/rules/*.md` and `CLAUDE.md` produced **8 sandbox teardown errors** from
`_no_writes_outside_the_sandbox`. They did not reproduce on a quiet run. The
harness already documents this race for its polling threads; live background
writes are a second source of it.

---

## 1. Still open

### `updated <n> ago` on each machine-written row (research P1 #10)
Answers "is this stale?", the second question after "who wrote it?". Blocked on
data, not design: `/api/memory/state` carries `generated_at` (the graph build)
and `auto_updated` (the last cycle), but there is **no per-artifact timestamp** —
the worklog, the conventions block and the rule files are each written on their
own schedule. Either stamp each write, or state the one build time on the
`Always on` bucket header and leave the rows bare.

### CLAUDE.md sentinel markers should name the tool and how to regenerate (P3 #15–17)
Currently bare: `<!-- AUTOGEN:START -->`, `<!-- SESSIONS:START -->`,
`<!-- CLAUDECTL:MEMORY:START -->` (`config.py:932`). The convention with four
independent precedents (Ansible `blockinfile`, all-contributors, doctoc, conda)
puts the tool name, the prohibition and the regeneration command *inside* the
marker — and Anthropic strips block-level HTML comments before injection, so
**the marker text is free**. There is no budget argument for terse sentinels.

**This one needs a migration, which is why it is not done.** `_swap_blocks`
matches the literal string; changing it means an old CLAUDE.md no longer matches,
so the block is *appended again* and every project ends up with two. Any change
must accept the old markers for reading and write the new ones — a tuple of
accepted openers, not a replaced constant.

### AGENTS.md (research disagreement E)
AGENTS.md is the cross-tool standard Claude Code deliberately does not read; it
recommends `@AGENTS.md` as CLAUDE.md's first line instead. If claudectl's
generated blocks live only in CLAUDE.md, a repo that later adopts AGENTS.md has
them in the file other agents ignore. **A decision to take, not necessarily a
change.**

---

## 2. Landed since the handoff

### The bucket restructure (the thing that was interrupted)
The interrupted edit had rewritten `invRow` from six parameters to five and added
`bucket()` / `invTable()` / `REACH` / `rch()`, but died before rewriting the
eleven call sites. They kept passing the old sixth argument, so the load-rule
keyword rendered in the **size** column, the size rendered where the button goes,
and the action was **dropped** — with the whole suite, the smoke tool and the
overflow audit all green, because every check read a row's *text* and text does
not know which cell it is in.

The twelve artifacts are now four groups, stated once each rather than as a badge
repeated down a wall:

| bucket | reach | members |
|---|---|---|
| Always on | every session | CLAUDE.md digest, AUTOGEN / SESSIONS, cross-project conventions, recent work |
| Every prompt | every prompt | Recall (renamed from "per-prompt recall injection" — a load rule masquerading as a topic) |
| When relevant | when Claude opens a matching file | path-scoped rules, lessons |
| Stored, not loaded | on request | semantic graph, reinforcement log, edit log, workspace manifest, version snapshots — collapsed behind *"5 records · 0 tokens — read only when you or Claude ask"* |

Deviations from the research's proposed assignment, both deliberate:
- It put **path-scoped rules** in *Always on* with a "verify this" caveat, because
  the files it could see had no `paths:`. That was fixed first (3 875 tok/turn),
  so they genuinely belong in *When relevant*.
- It put **cross-project conventions** and **recent work** in *Stored*. Both are
  really injected — conventions into the global CLAUDE.md, recent work at
  SessionStart — so both sit in *Always on*.

Also landed from the research: the ownership sentence (P0 #1) and the always-on
cost as a **share of the context window** (P1 #7) — `CTX_WINDOW` had been defined
and unused since the interrupted edit added it.

### The gate that would have caught it
`test_no_row_helper_is_called_with_more_arguments_than_it_takes` counts the
top-level arguments at every call of `invRow` / `bucket` / `invTable` / `rch` and
fails when a call passes more than the function declares — JS discards the extra
silently. Mutation-verified against the exact historical shape (a sixth argument
on one `invRow`). Fewer than declared stays legal, since trailing arguments are
genuinely optional. Line numbering in the failure is real, because `_source()`
now collapses a block comment to the newlines it spanned.

### `linguist-generated`
`.gitattributes` marks `.claude/rules/claudectl-mem-*.md`, `docs/api.md` and
`plugin/skills/**` as generated, so their diffs collapse in review. Verified with
`git check-attr`.

### The live CLAUDE.md
Regenerated through `claude_md.prune_claude_md` (atomic, snapshotted, manifest
re-baselined). The SESSIONS block held ten rows of claudectl talking to itself
and now holds ten real topics. One opener was missing from `HEADLESS_OPENERS` —
`agents.sharpen_prompt` — so it leaked one row; added, and `agents` is now in the
gate's module list. The gate can only rot one way and this was the other way, so
its docstring now says why that is acceptable: `HEADLESS_MARK` covers every new
call at the `memory._claude_stdin` seam, leaving the opener list to matter only
for transcripts written before it existed.

---

## 3. Finished earlier — do not redo

Each was verified against this repo's real data, per *"test on my real claudectl
project before saying it's implemented correctly"*.

- **Why the cycle said "0 modules, 6 still queued".** All six `_extract` calls
  **failed** (rate limit); `failed_units` and `skipped_units` were summed into one
  `pending_units` and every consumer worded it "the next cycle takes them", so six
  dead calls an hour read as progress. `gui_api._run_cancellable` also discarded
  the real error on a nonzero exit when there was no job context — which is
  exactly the scheduler and the detached worker.
- **"why does the reinforcement log say folding in?"** It was a literal string
  derived from the graph's top-hits list — a different thing, and it never
  changed. `recall.hits_pending` counts the sidecar; the row reads `<n> to fold in`.
- **The rule files were never actually lazy.** All 11 `claudectl-mem-*.md` used
  `globs:` (the Cursor key). Claude Code reads `paths:`; a rule without it "is
  loaded unconditionally". Measured: **22 238 → 18 363 always-on tokens, 3 875
  off every single turn**, 11 files migrated free, and one rule that had scoped
  itself narrower than its own module corrected.
- **The CLAUDE.md memory block carries content, not just an index** — the budget
  goes to the highest-signal lessons and the module dependency edges instead of a
  module listing.
- **Most-reinforced facts are clickable** (`entDetail`).
- **History is no longer a wall, and sits beside the artifact it is history of.**
- **Headless sessions are marked at the one seam** (`memory._claude_stdin`).
- **Every field the four memory handlers put on the wire reaches the screen**,
  enforced by `tests/test_gui_memory_surface.py`.
