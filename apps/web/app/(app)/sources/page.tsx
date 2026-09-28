import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sources · Research AI",
};

export default function SourcesPage() {
  return (
    <>
<div className="page-head"><div><h1>Sources</h1><p>Your curated source library across all research projects.</p></div><div className="actions"><button className="btn" data-toast="Import source dialog">Import DOI / URL</button><Link className="btn primary" href="/research">Discover more</Link></div></div><div className="card pad"><div className="row"><div className="pillbar"><span className="tag">248 total</span><span className="tag">92 primary</span><span className="tag">127 reviews</span><span className="tag">29 other</span></div><input className="search" style={{maxWidth: '310px'}} placeholder="Filter sources..." /></div></div><div className="card table-wrap" style={{marginTop: '16px'}}><table className="table"><thead><tr><th>Source</th><th>Type</th><th>Project</th><th>Evidence</th><th>Status</th><th></th></tr></thead><tbody><tr><td><div className="strong">Contrastive neural representations…</div><div className="meta">doi:10.1000/example.2025.11</div></td><td>Primary</td><td>PRI-042</td><td>18 claims</td><td><span className="tag success">Parsed</span></td><td><button className="btn ghost" data-toast="Source preview">Open</button></td></tr><tr><td><div className="strong">Transformer architectures for sparse neuroimaging</div><div className="meta">NeuroImage · 2024</div></td><td>Review</td><td>PRI-042</td><td>11 claims</td><td><span className="tag success">Parsed</span></td><td><button className="btn ghost" data-toast="Source preview">Open</button></td></tr><tr><td><div className="strong">Foundation models for brain decoding</div><div className="meta">Trends in Cognitive Systems · 2026</div></td><td>Review</td><td>PRI-042</td><td>7 claims</td><td><span className="tag warn">Needs review</span></td><td><button className="btn ghost" data-toast="Review source">Review</button></td></tr><tr><td><div className="strong">Sparse acquisition benchmark dataset</div><div className="meta">OSF · 2023</div></td><td>Dataset</td><td>PRI-042</td><td>4 claims</td><td><span className="tag success">Linked</span></td><td><button className="btn ghost" data-toast="Dataset preview">Open</button></td></tr></tbody></table></div>
    </>
  );
}
