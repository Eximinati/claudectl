import type { ReactNode } from 'react';
import Link from 'next/link';
import type { Doc } from '@/lib/content';
import { SectionView } from '@/components/doc/Blocks';

/**
 * The chrome every apex route opens with, so the nine of them read as one site.
 *
 * Width is fixed at max-w-4xl here and in DocSections deliberately: DocView in
 * components/doc/Blocks.tsx already uses it, and a page that mixes widths shows
 * a ragged left edge the moment a screenshot sits next to a paragraph.
 */
export function PageHeader({
  eyebrow,
  title,
  lead,
  children,
}: {
  eyebrow?: string;
  title: string;
  lead?: string;
  /** Call-to-action row under the lead. */
  children?: ReactNode;
}) {
  return (
    <header className="reveal mx-auto max-w-4xl px-5 pt-14 sm:pt-20">
      {eyebrow ? (
        <p className="mb-3 font-mono text-[0.7rem] uppercase tracking-[0.16em] text-cyan/80">
          {eyebrow}
        </p>
      ) : null}
      <h1 className="text-balance text-3xl font-semibold tracking-tight text-text sm:text-[2.5rem] sm:leading-[1.15]">
        {title}
      </h1>
      {lead ? (
        <p className="mt-4 max-w-3xl text-pretty text-lg leading-[1.65] text-dim">{lead}</p>
      ) : null}
      {children ? <div className="mt-7 flex flex-wrap items-center gap-3">{children}</div> : null}
    </header>
  );
}

/**
 * A Doc's sections, with an optional node appended after a named one — which is
 * how a screenshot lands inside the section it illustrates without the prose
 * having to know an image exists.
 */
export function DocSections({
  doc,
  after,
}: {
  doc: Doc;
  after?: Record<string, ReactNode>;
}) {
  return (
    <div className="mx-auto max-w-4xl space-y-16 px-5 py-16">
      {doc.sections.map((s) => (
        <div key={s.id} className="space-y-8">
          <SectionView section={s} />
          {after?.[s.id]}
        </div>
      ))}
    </div>
  );
}

/** Body wrapper for the routes that render markdown rather than a Doc. */
export function PageBody({ children }: { children: ReactNode }) {
  return <div className="reveal mx-auto max-w-4xl px-5 py-16">{children}</div>;
}

/** A link that looks like a button. next/link renders a plain anchor for an
 *  absolute URL, so the external destinations need no second component. */
export function Cta({
  href,
  primary,
  children,
}: {
  href: string;
  primary?: boolean;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      className={`rounded-lg border px-4 py-2 text-sm no-underline transition-colors ${
        primary
          ? 'border-cyan/45 bg-cyan/10 text-text hover:border-cyan/75'
          : 'border-line text-dim hover:border-cyan/45 hover:text-text'
      }`}
    >
      {children}
    </Link>
  );
}
