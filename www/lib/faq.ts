/**
 * The FAQ, once. The page renders it and the FAQPage JSON-LD is generated from
 * the same array, so the structured data can never describe questions the page
 * does not answer. (Ported from docs/faq.md, whose hand-written JSON-LD block
 * had fallen to six of its twelve questions.)
 */
export type QA = { q: string; a: string };

export const FAQ: QA[] = [
  {
    q: 'How do I manage Claude Code sessions on Windows?',
    a: 'Claude Code stores every session as a JSONL transcript under your config directory, but gives you no way to browse them. claudectl lists every session per project with its topic, message count and age, and lets you search, tag, fork, resume, export and archive them — from a terminal UI or a desktop GUI.',
  },
  {
    q: 'How do I reduce Claude Code token usage?',
    a: 'The largest recurring cost is context you pay for on every message. claudectl keeps the always-on CLAUDE.md block to a bounded index of about 250 tokens, moves per-module detail into path-scoped rules files that load only when Claude touches those files, and can inject only the memory subgraph a given prompt needs. Its own internal calls route to a cheap economy model, and Plan to Execute runs an expensive model once for the plan and a cheap one for execution.',
  },
  {
    q: 'What is a Claude Code MCP server manager?',
    a: 'MCP servers are configured in JSON and are otherwise invisible — you cannot easily tell which are connected to a project or what tools they expose. claudectl detects the servers configured for each project, shows them at a glance, and can run an analysis that lists a server’s actual tools into your global CLAUDE.md inside a re-updatable block.',
  },
  {
    q: 'How do I run multiple Claude accounts at the same time?',
    a: 'Claude Code selects its account through the CLAUDE_CONFIG_DIR environment variable. claudectl detects every configured account, merges their projects into one list, shows per-account usage side by side, and sets that variable for you when it launches a session, so you pick the account at launch rather than juggling environment variables.',
  },
  {
    q: 'Does claudectl require any Python dependencies?',
    a: 'No. It runs on the Python standard library alone and needs Python 3.10 or newer. PyQt6 is optional and only needed for the native desktop shell — without it the GUI opens in your browser instead.',
  },
  {
    q: 'Does claudectl work on macOS and Linux, or only Windows?',
    a: 'It runs on all three, and CI tests all three. It is Windows-first in that Windows gets the widest Python version matrix and the most real-world use, so rough edges are likelier on macOS and Linux. Bug reports from those platforms are welcome.',
  },
  {
    q: 'How is claudectl different from Claude Code’s built-in /resume?',
    a: '/resume reattaches you to a recent session in the current directory. claudectl treats your sessions as a searchable archive across every project and every account, adds tags, export, fork and archive, and controls what model, effort, permissions and project context a session launches with. /resume answers "put me back"; claudectl answers "what have I done here, and how should the next session start".',
  },
  {
    q: 'Can I use a cheaper model to execute a plan made by a stronger model?',
    a: 'Yes — that is what Plan to Execute does. It runs a headless planning pass with the strong model, shows you the plan for approval or editing, then hands the approved plan to a cheaper model to carry out. Free execution routes that half through OmniRoute’s free tier.',
  },
  {
    q: 'What happens to my project memory after /compact?',
    a: '/compact discards detail from the conversation, which is where context loss usually bites. claudectl’s memory lives outside the transcript — in the project’s memory graph and its rules files — so it is re-injected at the next launch regardless of what the conversation dropped.',
  },
  {
    q: 'Does claudectl have a GUI, or is it terminal-only?',
    a: 'Both, over the same engine. The terminal UI is the default. Running claudectl --gui opens a desktop GUI: a native window if PyQt6 is installed, otherwise your browser, served over loopback only.',
  },
  {
    q: 'Is claudectl free and open source?',
    a: 'Yes, MIT licensed and free. It uses your existing Claude Code authentication and adds no subscription and no API key of its own.',
  },
  {
    q: 'Can I install it from PyPI?',
    a: 'Yes: pipx install claudectl, or pip install claudectl. It also ships as a Claude Code plugin if you would rather stay inside the session.',
  },
];

export const faqJsonLd = () => ({
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: FAQ.map(({ q, a }) => ({
    '@type': 'Question',
    name: q,
    acceptedAnswer: { '@type': 'Answer', text: a },
  })),
});
