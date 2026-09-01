import type { Metadata, Viewport } from 'next';
import './globals.css';
import { Header } from '@/components/site/Header';
import { Footer } from '@/components/site/Footer';
import { SITE, url } from '@/lib/site';
import { HOME } from '@/lib/content';
import { jsonLd } from '@/lib/meta';
import { VERSION } from '@/lib/build-data';

/* No next/font: the type stack in globals.css is fonts that ship with the OS,
   exactly as the app itself does. A webfont here would be a build-time network
   call and a render-blocking request for a look we already have. */

export const metadata: Metadata = {
  metadataBase: new URL(SITE.url),
  title: {
    default: HOME.title,
    template: `%s · ${SITE.name}`,
  },
  description: HOME.description,
  applicationName: SITE.name,
  authors: [{ name: SITE.author, url: SITE.authorGithub }],
  creator: SITE.author,
  keywords: [
    'Claude Code',
    'Claude Code session manager',
    'Claude Code memory',
    'CLAUDE.md',
    'MCP server manager',
    'Claude Code token usage',
    'AI coding workspace',
    'developer tools',
  ],
  alternates: { canonical: SITE.url },
  openGraph: {
    type: 'website',
    url: SITE.url,
    siteName: SITE.name,
    title: HOME.title,
    description: HOME.description,
    images: [{ url: url(SITE.ogImage), width: 1200, height: 630, alt: SITE.tagline }],
  },
  twitter: {
    card: 'summary_large_image',
    title: HOME.title,
    description: HOME.description,
    images: [url(SITE.ogImage)],
  },
  robots: { index: true, follow: true },
  icons: { icon: '/favicon.ico' },
};

export const viewport: Viewport = {
  themeColor: '#0a0c10',
  colorScheme: 'dark',
};

/** One SoftwareApplication for the whole site, in the layout so every page
 *  carries it. Page-specific graphs (FAQPage, BlogPosting) are added per route. */
const APP_LD = {
  '@context': 'https://schema.org',
  '@type': 'SoftwareApplication',
  name: SITE.name,
  applicationCategory: 'DeveloperApplication',
  operatingSystem: 'Windows, macOS, Linux',
  description: HOME.description,
  url: SITE.url,
  downloadUrl: SITE.pypi,
  ...(VERSION ? { softwareVersion: VERSION } : {}),
  license: 'https://opensource.org/licenses/MIT',
  isAccessibleForFree: true,
  offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
  author: { '@type': 'Person', name: SITE.author, url: SITE.authorGithub },
  codeRepository: SITE.repo,
  programmingLanguage: 'Python',
};

export default function RootLayout({ children }: LayoutProps<'/'>) {
  return (
    <html lang="en" className="h-full">
      <body className="flex min-h-full flex-col antialiased">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: jsonLd(APP_LD).text }}
        />
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-panel2 focus:px-3 focus:py-2 focus:text-sm"
        >
          Skip to content
        </a>
        <Header />
        <main id="main" className="flex-1">
          {children}
        </main>
        <Footer />
      </body>
    </html>
  );
}
