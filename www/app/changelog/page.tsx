import { CHANGELOG_HTML, VERSION } from '@/lib/build-data';
import { breadcrumbs, jsonLd, meta } from '@/lib/meta';
import { SITE } from '@/lib/site';
import { Cta, PageBody, PageHeader } from '@/components/Page';

export const metadata = meta({
  title: 'Changelog',
  description:
    'Every claudectl release and what changed in it, straight from the repository CHANGELOG.md. Semantic versioning, Keep a Changelog format.',
  path: '/changelog',
});

const CRUMBS = breadcrumbs([
  { name: 'Home', path: '/' },
  { name: 'Changelog', path: '/changelog' },
]);

export default function ChangelogPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: jsonLd(CRUMBS).text }}
      />

      <PageHeader
        eyebrow={VERSION ? `Current release · v${VERSION}` : 'Releases'}
        title="Changelog"
        lead="Every release, rendered from the repository's own CHANGELOG.md at build time. Versioning is semantic and the format follows Keep a Changelog."
      >
        <Cta href={`${SITE.repo}/releases`} primary>
          GitHub releases
        </Cta>
        <Cta href="/download">Install or upgrade</Cta>
      </PageHeader>

      <PageBody>
        {CHANGELOG_HTML ? (
          <div className="prose" dangerouslySetInnerHTML={{ __html: CHANGELOG_HTML }} />
        ) : (
          /* The file is read from the repository at build time, so it can be
             absent in a checkout that does not carry it. One missing file must
             not take the route down. */
          <div className="panel p-6">
            <h2 className="text-lg font-semibold text-text">Release notes live on GitHub</h2>
            <p className="mt-2 text-[0.95rem] leading-[1.7] text-dim">
              The changelog could not be read for this build. Every release is tagged and
              described on the{' '}
              <a
                href={`${SITE.repo}/releases`}
                className="text-cyan no-underline underline-offset-[3px] hover:underline"
              >
                releases page
              </a>
              , and the full file is{' '}
              <a
                href={`${SITE.repo}/blob/main/CHANGELOG.md`}
                className="text-cyan no-underline underline-offset-[3px] hover:underline"
              >
                in the repository
              </a>
              .
            </p>
          </div>
        )}
      </PageBody>
    </>
  );
}
