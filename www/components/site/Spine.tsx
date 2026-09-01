import type { ReactNode } from 'react';

/**
 * The skill tree for the content routes.
 *
 * The landing page connects its sections in 3D. Every other page had no
 * connective tissue at all — a list of panels with a drifting constellation
 * behind it that bore no relation to them. This is the same idea in the DOM: a
 * spine down the column, a node at every section, drawn as you scroll.
 *
 * Drawn with `pathLength="1"` and `stroke-dashoffset` on a native view timeline,
 * which is how `.station-in` and `.reveal` already work here — no observer, no
 * JS, no measurement, and it stays a hairline at any zoom because it is a vector.
 *
 * The nodes are positioned by the flex layout, not by coordinates: each child
 * sits in a row beside its own marker, so nothing has to know how tall a section
 * is. Getting that wrong is how a spine ends up pointing at the wrong paragraph
 * the moment a screenshot loads and the section grows.
 */

/** connections.TYPE_COLORS, cycled — the same palette the scene draws with.
 *  Written out in full because Tailwind scans source text: a class built by
 *  interpolation (`bg-${name}`) is a class that never gets generated. */
const NODE = [
  'bg-module', 'bg-component', 'bg-concept', 'bg-service', 'bg-model', 'bg-agent',
] as const;

export function Spine({
  items,
  dense,
}: {
  items: { key: string; node: ReactNode; weight?: number }[];
  /** Natural row height instead of one section per screen. For lists — a FAQ or
   *  a post index padded to twelve screens is worse to read, not better. */
  dense?: boolean;
}) {
  return (
    // Wide container, narrow column. The copy keeps the left ~42rem and the
    // right half of the viewport is deliberately empty — that space is where the
    // section's own solid sits, which is the same composition the landing page
    // uses. A full-width column leaves nowhere for it to be, and the solid ends
    // up over the text instead of beside it.
    <div className="mx-auto max-w-[92rem] px-5">
      <ol>
        {items.map((it, i) => (
          /* data-section/data-weight are the contract with Canvas.tsx: it
             measures these offsets to know which section you are reading, and
             reads the weight to size the focal solid. A section with more in it
             gets a bigger object. */
          <li
            key={it.key}
            data-section={i}
            data-weight={it.weight ?? 1}
            data-dense={dense ? '1' : undefined}
            data-side={i % 2 === 0 ? 'left' : 'right'}
            className={`relative grid grid-cols-[28px_minmax(0,1fr)] items-center gap-x-4 sm:grid-cols-[36px_minmax(0,1fr)] sm:gap-x-6 ${
              dense ? 'py-6' : 'min-h-[74svh] py-10'
            } ${
              // Alternating: the copy takes one half and leaves the other for its
              // solid, so the page reads as a path down the middle rather than a
              // single column with decoration stapled to one side.
              i % 2 === 0 ? '' : 'lg:justify-items-end'
            }`}
          >
            <div className="relative flex items-center justify-center self-stretch" aria-hidden="true">
              {/* The rail. A scaled div, not an SVG path: `stroke-dashoffset`
                  repaints, and the rule here is transform and opacity only. It
                  spans the whole row, so a tall section gets a long rail for free
                  and nothing has to measure anything. The last row stops halfway
                  — a tree ends, it does not trail off. */}
              <span
                className={`spine-rail absolute left-1/2 top-0 w-px -translate-x-1/2 ${
                  i === items.length - 1 ? 'h-1/2' : 'bottom-0'
                }`}
              />
              <span
                className={`spine-node relative h-2.5 w-2.5 rounded-full ${NODE[i % NODE.length]}`}
              />
            </div>
            <div className="reveal min-w-0 max-w-[44rem] pb-2">{it.node}</div>
          </li>
        ))}
      </ol>
    </div>
  );
}
