import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Humanize · Research AI",
};

export default function HumanizePage() {
  return (
    <>
<div className="page-head"><div><div className="eyebrow">Language studio</div><h1>Humanize & rewrite</h1><p>Adjust clarity, rhythm and academic voice without changing the underlying claims.</p></div><div className="actions"><button className="btn" data-toast="Comparison ready">Compare</button><button className="btn primary" data-toast="Rewrite generated">Rewrite</button></div></div><div className="grid grid-2"><section className="card pad"><div className="row"><h3>Original</h3><span className="tag">412 words</span></div><textarea className="input textarea" style={{height: '430px', marginTop: '12px'}} defaultValue="Our findings demonstrate that transformer-based representations are capable of improving decoding performance under constrained sample regimes. This improvement may be attributable to the regularizing effect of contrastive pretraining, although the current evidence does not establish causality." /></section><section className="card pad"><div className="row"><h3>Rewritten</h3><span className="tag success">Claim-safe</span></div><textarea className="input textarea" style={{height: '430px', marginTop: '12px'}} defaultValue="In our low-data setting, transformer-based representations improved decoding performance. One plausible explanation is that contrastive pretraining acts as a form of regularization. However, the available evidence is correlational, so a causal interpretation would be premature." /></section></div><div className="card pad" style={{marginTop: '16px'}}><div className="row"><div><h3>Rewrite controls</h3><div className="muted small">Balanced for academic writing.</div></div><div className="pillbar"><span className="tag success">Clarity ↑</span><span className="tag success">Naturalness ↑</span><span className="tag">Claim integrity 100%</span></div></div><div className="grid grid-3" style={{marginTop: '16px'}}><div><div className="small muted">Sentence variety</div><div className="progress" style={{marginTop: '8px'}}><span style={{width: '82%'}}></span></div></div><div><div className="small muted">Readability</div><div className="progress" style={{marginTop: '8px'}}><span style={{width: '87%'}}></span></div></div><div><div className="small muted">Academic tone</div><div className="progress" style={{marginTop: '8px'}}><span style={{width: '93%'}}></span></div></div></div></div>
    </>
  );
}
