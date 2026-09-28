import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Research AI — Research workspace",
};

export default function LandingPage() {
  return (
    <div className="landing-page">
      <header
        style={{
          borderBottom: "1px solid var(--border)",
          position: "sticky",
          top: "0",
          background: "rgba(7,17,31,.86)",
          backdropFilter: "blur(12px)",
          zIndex: "10",
        }}
      >
        <div className="container">
          <div className="row" style={{ height: "70px" }}>
            <Link className="brand" href="/">
              <span className="brand-mark">R</span>
              <span>Research AI</span>
            </Link>

            <nav className="actions">
              <a href="#features" className="btn ghost">
                Features
              </a>

              <a href="#workflow" className="btn ghost">
                Workflow
              </a>

              <Link href="/usage-billing" className="btn ghost">
                Pricing
              </Link>

              <Link href="/login" className="btn ghost">
                Log in
              </Link>

              <Link href="/signup" className="btn primary">
                Start research
              </Link>
            </nav>
          </div>
        </div>
      </header>

      <main>
        <section className="hero">
          <div className="container hero-grid">
            <div>
              <div className="eyebrow">AI research operating system</div>

              <h1>From question to defensible paper.</h1>

              <p>
                Discover literature, collect evidence, connect your files and
                code, plan your study, and draft a manuscript inside one
                research workspace.
              </p>

              <div className="actions" style={{ marginTop: "24px" }}>
                <Link className="btn primary" href="/signup">
                  Create free workspace →
                </Link>

                <Link className="btn" href="/dashboard">
                  Preview app loading
                </Link>
              </div>

              <div className="pillbar" style={{ marginTop: "18px" }}>
                <span className="tag">Evidence-first</span>
                <span className="tag">Citation-aware</span>
                <span className="tag">Team-ready</span>
                <span className="tag">FastAPI backend</span>
              </div>
            </div>

            <div className="hero-card">
              <div className="hero-ui">
                <div className="mini-side">
                  <div className="mini-line short"></div>
                  <div className="mini-line"></div>
                  <div className="mini-line mid"></div>
                  <div className="mini-line short"></div>

                  <div style={{ height: "120px" }}></div>

                  <div className="mini-line"></div>
                </div>

                <div className="mini-main">
                  <div className="row">
                    <div className="strong">Neural decoding in fMRI</div>
                    <span className="tag success">12 sources</span>
                  </div>

                  <div
                    className="mini-line"
                    style={{
                      width: "91%",
                      height: "14px",
                      marginTop: "18px",
                    }}
                  ></div>

                  <div className="mini-line mid"></div>

                  <div className="grid grid-2" style={{ marginTop: "20px" }}>
                    <div className="card pad">
                      <div className="muted tiny">Evidence score</div>
                      <div style={{ fontSize: "28px", fontWeight: "800" }}>
                        91%
                      </div>
                    </div>

                    <div className="card pad">
                      <div className="muted tiny">Draft progress</div>
                      <div style={{ fontSize: "28px", fontWeight: "800" }}>
                        68%
                      </div>
                    </div>
                  </div>

                  <div
                    className="mini-line"
                    style={{
                      height: "90px",
                      marginTop: "18px",
                    }}
                  ></div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="features" className="section">
          <div className="container">
            <h2>One system for the whole research lifecycle.</h2>

            <p>Each page in this prototype maps to a clear research job.</p>

            <div className="grid grid-3">
              <div className="card feature">
                <div className="tag">01 · Discover</div>

                <h3>Search &amp; literature</h3>

                <p>
                  Find relevant papers, inspect metadata, save sources and
                  build a focused evidence set.
                </p>
              </div>

              <div className="card feature">
                <div className="tag">02 · Understand</div>

                <h3>Evidence &amp; knowledge</h3>

                <p>
                  Turn papers and uploaded files into claims, snippets,
                  concepts and traceable connections.
                </p>
              </div>

              <div className="card feature">
                <div className="tag">03 · Create</div>

                <h3>Plan &amp; write</h3>

                <p>
                  Build a research plan, draft sections, humanize language and
                  translate without losing structure.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section id="workflow" className="section">
          <div className="container">
            <div className="page-head">
              <div>
                <h2>Visual workflow</h2>

                <p>
                  Designed as a serious research SaaS, not a generic chatbot.
                </p>
              </div>

              <Link className="btn" href="/workspace">
                Open workspace →
              </Link>
            </div>

            <div className="timeline">
              <div className="step done">
                <div className="dot"></div>
                <b>Question</b>
                <div className="meta">Define scope and protocol.</div>
              </div>

              <div className="step done">
                <div className="dot"></div>
                <b>Discover</b>
                <div className="meta">Search sources and literature.</div>
              </div>

              <div className="step active">
                <div className="dot"></div>
                <b>Evidence</b>
                <div className="meta">Trace claims to passages.</div>
              </div>

              <div className="step">
                <div className="dot"></div>
                <b>Plan</b>
                <div className="meta">Structure the study.</div>
              </div>

              <div className="step">
                <div className="dot"></div>
                <b>Write</b>
                <div className="meta">Assemble the manuscript.</div>
              </div>
            </div>
          </div>
        </section>

        <footer className="footer">
          <div className="container row">
            <span>Research AI · research workspace</span>

            <span className="muted">
              From static prototype to a wired Next.js app.
            </span>
          </div>
        </footer>
      </main>
    </div>
  );
}