import Link from "next/link";

export default function LandingPage() {
  return (
    <main>
      <header className="topbar">
        <Link className="brand" href="/"><span className="brand-mark">R</span><span>Research AI</span></Link>
        <div className="topbar-right">
          <Link className="btn ghost" href="/login">Log in</Link>
          <Link className="btn primary" href="/signup">Start research</Link>
        </div>
      </header>
      <section className="hero">
        <div className="container hero-grid">
          <div>
            <div className="eyebrow">Research operating system</div>
            <h1>From question to defensible paper.</h1>
            <p>Discover literature, organize evidence, plan the study, draft the manuscript and preserve provenance through every research step.</p>
            <div className="actions">
              <Link className="btn primary" href="/signup">Create workspace</Link>
              <Link className="btn" href="/research">Explore research</Link>
            </div>
          </div>
          <div className="hero-card">
            <div className="hero-ui">
              <div className="mini-side">
                <div className="small strong">Research AI</div>
                <div className="mini-line mid" />
                <div className="mini-line short" />
                <div className="mini-line" />
              </div>
              <div className="mini-main">
                <div className="eyebrow">Workflow</div>
                <h3>Question → Discover → Evidence → Plan → Write</h3>
                <div className="stack">
                  {["Research discovery","Evidence matrix","Versioned manuscript"].map((x) => (
                    <div className="list-item" key={x}><div className="title">{x}</div><div className="meta">Connected to the authenticated research workspace</div></div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
      <section className="section">
        <div className="container">
          <div className="eyebrow">Capabilities</div>
          <h2>One research workspace.</h2>
          <p>The production interface follows the supplied 21-page design while backend state remains authoritative.</p>
          <div className="grid grid-3">
            {[
              ["Discover","Search literature and workspace resources with provenance."],
              ["Understand","Bind claims to supporting and conflicting evidence."],
              ["Create","Draft, review, humanize and translate versioned manuscripts."],
            ].map(([title,text]) => <div className="card feature" key={title}><h3>{title}</h3><p>{text}</p></div>)}
          </div>
        </div>
      </section>
    </main>
  );
}
