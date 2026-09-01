/**
 * The mark: a dodecahedron silhouette, the same solid the journey scene draws.
 * Inline SVG rather than a file — one request fewer and it inherits currentColor
 * so it is correct in every surface it sits on.
 */
export function Mark({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true" fill="none">
      <path
        d="M16 3 27 8.6v10.8L16 29 5 19.4V8.6Z"
        stroke="var(--color-cyan)"
        strokeWidth="1.3"
        strokeLinejoin="round"
      />
      <path
        d="M16 3v7.4m0 0 6.8 4.2M16 10.4l-6.8 4.2m13.6 0v7.6L16 29m6.8-6.8L27 19.4M9.2 14.6v7.6L16 29m-6.8-6.8L5 19.4"
        stroke="var(--color-violet)"
        strokeWidth="1.1"
        strokeLinejoin="round"
        opacity="0.85"
      />
      <circle cx="16" cy="10.4" r="1.5" fill="var(--color-cyan)" />
    </svg>
  );
}
