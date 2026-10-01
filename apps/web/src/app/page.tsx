import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="landing-page">
      <header style={{borderBottom:"1px solid var(--line)",position:"sticky",top:0,background:"rgba(255,255,255,.86)",backdropFilter:"blur(12px)",zIndex:10}}>
        <div className="container">
          <div className="row" style={{height:70}}>
            <Link className="brand" href="/">
              <span className="brand-mark">R</span><span>Research AI</span>
            </Link>
            <nav className="actions">
              <a href="#features" className="btn ghost">Features</a>
              <a href="#workflow" className="btn ghost">Workflow</a>
              <a href="#pricing" className="btn ghost">Pricing</a>
              <Link href="/login" className="btn ghost">Log in</Link>
              <Link href="/register" className="btn primary">Start research</Link>
            </nav>
          </div>
        </div>
      </header>

      <section className="hero">
        <div className="container hero-grid">
          <div>
            <div className="eyebrow">AI research operating system</div>
            <h1>From question to defensible paper.</h1>
            <p>
              Discover literature, collect evidence, connect your files and code,
              plan your study, and draft a manuscript inside one research workspace.
            </p>
            <div className="actions" style={{marginTop:24}}>
              <Link className="btn primary" href="/register">Create free workspace →</Link>
              <a className="btn" href="#workflow">See workflow</a>
            </div>
            <div className="pillbar" style={{marginTop:18}}>
              <span className="tag">Evidence-first</span>
              <span className="tag">Citation-aware</span>
              <span className="tag">Team-ready</span>
              <span className="tag">FastAPI backend</span>
            </div>
          </div>
          <div className="hero-card">
            <div className="hero-ui">
              <div className="mini-side">
                <div className="mini-line short"/>
                <div className="mini-line"/>
                <div className="mini-line mid"/>
                <div className="mini-line short"/>
                <div style={{height:120}}/>
                <div className="mini-line"/>
              </div>
              <div className="mini-main">
                <div className="row">
                  <div className="strong">Research workspace</div>
                  <span className="tag success">Live API</span>
                </div>
                <div className="mini-line" style={{width:"91%",height:14,marginTop:18}}/>
                <div className="mini-line mid"/>
                <div className="grid grid-2" style={{marginTop:20}}>
                  <div className="card pad"><div className="muted tiny">Evidence</div><div className="strong">Traceable</div></div>
                  <div className="card pad"><div className="muted tiny">Manuscript</div><div className="strong">Versioned</div></div>
                </div>
                <div className="mini-line" style={{height:90,marginTop:18}}/>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="features" className="section">
        <div className="container">
          <h2>One system for the whole research lifecycle.</h2>
          <p>Each page maps to a real research job and a backend capability.</p>
          <div className="grid grid-3">
            <div className="card feature"><div className="tag">01 · Discover</div><h3>Search & literature</h3><p>Find papers, inspect provenance, save sources and build a focused evidence set.</p></div>
            <div className="card feature"><div className="tag">02 · Understand</div><h3>Evidence & knowledge</h3><p>Turn papers and uploaded files into claims, passages, concepts and traceable connections.</p></div>
            <div className="card feature"><div className="tag">03 · Create</div><h3>Plan & write</h3><p>Build a research plan, draft sections, review versions, humanize language and translate without losing structure.</p></div>
          </div>
        </div>
      </section>

      <section id="workflow" className="section">
        <div className="container">
          <div className="page-head">
            <div>
              <h2>Visual workflow</h2>
              <p>Designed as a research SaaS, not a generic chatbot.</p>
            </div>
            <Link className="btn" href="/workspace">Open workspace →</Link>
          </div>
          <div className="timeline">
            {[
              ["Question","Define scope and protocol.","done"],
              ["Discover","Search sources and literature.","done"],
              ["Evidence","Trace claims to passages.","active"],
              ["Plan","Structure the study.",""],
              ["Write","Assemble the manuscript.",""],
            ].map(([title,meta,state])=>(
              <div className={"step "+state} key={title}><div className="dot"/><b>{title}</b><div className="meta">{meta}</div></div>
            ))}
          </div>
        </div>
      </section>

      <section id="pricing" className="section">
        <div className="container">
          <div className="card pad">
            <div className="row">
              <div>
                <div className="eyebrow">Plans</div>
                <h2 style={{marginTop:4}}>Start with the backend-defined workspace plan.</h2>
              </div>
              <Link className="btn primary" href="/register">Create account</Link>
            </div>
            <p className="muted" style={{marginTop:10}}>
              Pricing, usage limits and invoices are read from the billing service. No static price is shown here.
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
