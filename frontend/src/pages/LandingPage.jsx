import { useEffect } from "react";
import { Link } from "react-router-dom";
import "./LandingPage.css";
import ProductPreviewCard from "./ProductPreviewCard.jsx";

const GITHUB_URL = "https://github.com/adithyans2030/AI_bot";

const STATS = [
  { value: "30 hrs", label: "mandated doubt-clearing time per year" },
  { value: "1", label: "clearly-labeled AI assistant, always" },
  { value: "0", label: "attendance figures fabricated, ever" },
  { value: "4", label: "steps from mic to session report" },
];

const STEPS = [
  {
    number: "01",
    title: "Listens",
    desc: "Captures live audio and keeps a rolling 90-second transcript of the session.",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <rect x="9" y="2" width="6" height="11" rx="3" />
        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
        <line x1="12" y1="19" x2="12" y2="23" />
        <line x1="8" y1="23" x2="16" y2="23" />
      </svg>
    ),
  },
  {
    number: "02",
    title: "Matches the unit",
    desc: "Compares the live transcript against the uploaded unit notes to find the closest topic.",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="11" cy="11" r="8" />
        <line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
    ),
  },
  {
    number: "03",
    title: "Retrieves & asks",
    desc: "Pulls the matching notes and generates one grounded question, timed around silences.",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="10" />
        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>
    ),
  },
  {
    number: "04",
    title: "Logs honestly",
    desc: "Every question and topic match is timestamped into a real end-of-session report.",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="8" y1="13" x2="16" y2="13" />
        <line x1="8" y1="17" x2="12" y2="17" />
      </svg>
    ),
  },
];

const WITHOUT_LIST = [
  "Room stays quiet since attendance isn't mandatory",
  "Session happens but nothing shows doubts were cleared",
  "Teachers hold the hour with little to show for the audit",
];

const WITH_LIST = [
  "A question breaks the silence at the natural pause",
  "Every question is grounded in actual unit material",
  "An honest timestamped report comes out at the end",
];

function XIcon() {
  return (
    <svg className="compare-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#8C877D" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-label="No" role="img">
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg className="compare-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-label="Yes" role="img">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

export default function LandingPage() {
  useEffect(() => {
    document.title = "MimeBot — The 30 mandatory hours, actually used";
  }, []);

  return (
    <div className="landing-page">
      {/* NAV */}
      <nav aria-label="Main navigation">
        <div className="container nav-inner">
          <a href="#" className="nav-logo" aria-label="MimeBot home">
            <span className="nav-logo-mark" aria-hidden="true">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#121110" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 18v3" />
                <path d="M8 21h8" />
                <rect x="6" y="3" width="12" height="12" rx="6" />
                <path d="M9 8a3 3 0 0 1 3-3" />
              </svg>
            </span>
            MimeBot
          </a>
          <ul className="nav-links" role="list">
            <li><a href="#how-it-works">How it works</a></li>
            <li><a href="#compare">Compare</a></li>
            <li><a href="#guardrails">Guardrails</a></li>
          </ul>
          <div className="nav-right">
            <Link to="/app" className="btn btn-ghost-on-accent">Open the app</Link>
            <a href={GITHUB_URL} className="btn btn-on-accent" target="_blank" rel="noopener noreferrer">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22" />
              </svg>
              View on GitHub
            </a>
          </div>
        </div>
      </nav>

      {/* HERO */}
      <section className="hero" aria-labelledby="hero-heading">
        <div className="container hero-inner">
          <div className="hero-copy">
            <div className="hero-eyebrow-pill">
              <span className="dot" aria-hidden="true"></span>
              v1 prototype &middot; built for NEP audit-hour sessions
            </div>
            <h1 id="hero-heading" className="hero-headline">
              The 30 mandatory hours,<br /><span className="accent">actually used</span>
            </h1>
            <p className="hero-sub">
              MimeBot listens to a doubt-clearing session, works out which unit is being taught, and asks a
              grounded question the moment the room goes quiet — so the session produces something real, and
              the record of it is honest.
            </p>
            <div className="hero-actions">
              <a href={GITHUB_URL} className="btn btn-primary" target="_blank" rel="noopener noreferrer">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                  <polyline points="15 3 21 3 21 9" />
                  <line x1="10" y1="14" x2="21" y2="3" />
                </svg>
                View the repository
              </a>
              <a href="#how-it-works" className="btn btn-ghost">See how it works</a>
            </div>
          </div>

          <ProductPreviewCard />
        </div>
      </section>

      {/* STATS STRIP */}
      <div className="stats-strip" role="region" aria-label="Key figures">
        <div className="container stats-inner">
          {STATS.map((s) => (
            <div className="stat-item" key={s.label}>
              <span className="stat-number">{s.value}</span>
              <p className="stat-label">{s.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* COMPARE */}
      <section id="compare" className="section" aria-labelledby="compare-heading">
        <div className="container">
          <div className="section-header">
            <span className="eyebrow">Why it helps</span>
            <h2 id="compare-heading" className="section-heading">A silent session versus one with a co-host</h2>
          </div>
          <div className="compare-grid">
            <div className="compare-card">
              <h3 className="compare-card-title">Without MimeBot</h3>
              <ul className="compare-list" role="list">
                {WITHOUT_LIST.map((line) => (
                  <li key={line}><XIcon /><span>{line}</span></li>
                ))}
              </ul>
            </div>
            <div className="compare-card accent-border">
              <h3 className="compare-card-title">With MimeBot</h3>
              <ul className="compare-list" role="list">
                {WITH_LIST.map((line) => (
                  <li className="accent-item" key={line}><CheckIcon /><span>{line}</span></li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section
        id="how-it-works"
        className="section"
        aria-labelledby="hiw-heading"
        style={{ borderTop: "1px solid var(--border)", background: "var(--surface)" }}
      >
        <div className="container">
          <div className="section-header">
            <span className="eyebrow">How it works</span>
            <h2 id="hiw-heading" className="section-heading">Four steps, start to finish</h2>
          </div>
          <div className="steps-grid">
            {STEPS.map((step) => (
              <div className="step" key={step.number}>
                <div className="step-number">{step.number}</div>
                <div className="step-icon">{step.icon}</div>
                <h3 className="step-title">{step.title}</h3>
                <p className="step-desc">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* GUARDRAILS */}
      <section id="guardrails" className="guardrails-section" aria-labelledby="gr-heading">
        <div className="container">
          <div className="guardrails-card">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <h2 id="gr-heading" className="guardrails-heading">MimeBot is always one clearly-labeled AI assistant</h2>
            <p className="guardrails-body">
              Despite the name, it never impersonates a student, never simulates multiple fake participants, and
              never records or reports attendance or presence data of any kind. Its session report reflects only
              what the log actually captured — nothing invented, nothing implied.
            </p>
          </div>
        </div>
      </section>

      {/* TECH STACK */}
      <section className="tech-section" aria-labelledby="tech-heading">
        <div className="container">
          <span className="eyebrow" id="tech-heading">Built with</span>
          <div className="tech-pills" role="list">
            <span className="tech-pill" role="listitem">FastAPI backend</span>
            <span className="tech-pill" role="listitem">sentence-transformers embeddings</span>
            <span className="tech-pill" role="listitem">Local vector search</span>
            <span className="tech-pill" role="listitem">Local LLM (Ollama)</span>
            <span className="tech-pill" role="listitem">React + Vite</span>
            <span className="tech-pill" role="listitem">Web Speech API</span>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer>
        <div className="container footer-cta">
          <h2 className="footer-cta-heading">Prototype status: v1, running locally</h2>
          <p className="footer-cta-sub">
            No live meeting-join yet — everything runs from the browser mic and the local backend in this repo.
          </p>
          <a href={GITHUB_URL} className="btn btn-primary" target="_blank" rel="noopener noreferrer">
            View on GitHub
          </a>
        </div>
        <div className="footer-bottom">
          <div className="container footer-bottom-inner">
            <span className="footer-wordmark">MimeBot</span>
            <ul className="footer-nav" role="list">
              <li><a href="#how-it-works">How it works</a></li>
              <li><a href="#guardrails">Guardrails</a></li>
              <li><a href={GITHUB_URL} target="_blank" rel="noopener noreferrer">GitHub</a></li>
            </ul>
          </div>
        </div>
      </footer>
    </div>
  );
}
