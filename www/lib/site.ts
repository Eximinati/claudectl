export const SITE = {
  url: 'https://claudectl.space',
  docs: 'https://docs.claudectl.space',
  name: 'claudectl',
  tagline: 'The workspace layer for Claude Code',
  repo: 'https://github.com/babarmuhammad/claudectl',
  pypi: 'https://pypi.org/project/claudectl/',
  author: 'Babar Muhammad Anas',
  authorGithub: 'https://github.com/babarmuhammad',
  license: 'MIT',
  ogImage: '/og-card.png',
} as const;

export const NAV = [
  { href: '/features', label: 'Features' },
  { href: '/download', label: 'Download' },
  { href: '/architecture', label: 'Architecture' },
  { href: '/changelog', label: 'Changelog' },
  { href: '/blog', label: 'Blog' },
  { href: '/faq', label: 'FAQ' },
  { href: '/community', label: 'Community' },
  { href: '/about', label: 'About' },
] as const;

/** Old docs URLs that now live on the docs subdomain. */
export const DOC_REDIRECTS = [
  'install', 'usage', 'gui', 'graph', 'token-economy', 'health', 'sessions',
  'memory', 'accounts', 'mcp', 'agents', 'hooks', 'statusline', 'plan-execute',
  'reference', 'api', 'dashboard', 'context-handoff', 'agent-library',
] as const;

export const url = (path: string) => new URL(path, SITE.url).toString();
