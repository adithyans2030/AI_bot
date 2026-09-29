// Illustrative mock of a live session — fictional placeholder content, not
// real session data. Visually self-contained, so it's its own component.
export default function ProductPreviewCard() {
  return (
    <div className="hero-mock" role="img" aria-label="Illustrative mock of a live MimeBot session card">
      <div className="mock-header">
        <span className="live-dot" aria-hidden="true"></span>
        <span className="mock-live-label">Live session &middot; 00:14:32</span>
        <span className="mock-brand" aria-hidden="true">MIMEBOT</span>
      </div>
      <div>
        <span className="mock-pill">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          Topic matched &middot; Binary search trees
        </span>
      </div>
      <div className="mock-question-box">
        <p>&quot;What happens to the in-order traversal if we delete a node with two children?&quot;</p>
      </div>
      <p className="mock-caption">Generated 00:14:29 &middot; grounded in Unit 4 notes</p>
      <div className="mock-footer-label">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <rect x="2" y="7" width="20" height="14" rx="2" />
          <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" />
          <line x1="12" y1="12" x2="12" y2="12" />
        </svg>
        AI assistant &mdash; not a student
      </div>
    </div>
  );
}
