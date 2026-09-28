import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Translate · Research AI",
};

export default function TranslatePage() {
  return (
    <>
<div className="page-head"><div><div className="eyebrow">Translation</div><h1>Translate research content</h1><p>Preserve citations, headings, terminology and scientific meaning across languages.</p></div><div className="actions"><button className="btn" data-toast="Translation settings">Settings</button><button className="btn primary" data-toast="Translation started">Translate</button></div></div><div className="grid grid-2"><section className="card pad"><div className="row"><h3>Source</h3><select className="input" style={{width: '180px'}}><option>English</option></select></div><textarea className="input textarea" style={{height: '470px', marginTop: '12px'}} defaultValue="Transformer-based representations improved decoding performance in low-data settings. We report cross-subject AUROC as the primary endpoint and balanced accuracy as a secondary measure." /></section><section className="card pad"><div className="row"><h3>Target</h3><select className="input" style={{width: '180px'}}><option>Persian</option><option>Arabic</option><option>French</option></select></div><textarea className="input textarea" style={{height: '470px', marginTop: '12px'}} placeholder="ترجمه اینجا نمایش داده می‌شود…" defaultValue="بازنمایی‌های مبتنی بر ترنسفورمر در شرایط داده‌کم، عملکرد رمزگشایی را بهبود دادند. AUROC بین‌فردی به‌عنوان شاخص اصلی و balanced accuracy به‌عنوان شاخص ثانویه گزارش شد." /></section></div><div className="grid grid-3" style={{marginTop: '16px'}}><section className="card pad"><div className="strong">Citation preservation</div><div className="muted small" style={{marginTop: '6px'}}>18 / 18 citations preserved</div></section><section className="card pad"><div className="strong">Terminology</div><div className="muted small" style={{marginTop: '6px'}}>26 / 26 key terms mapped</div></section><section className="card pad"><div className="strong">Formatting</div><div className="muted small" style={{marginTop: '6px'}}>Headings and tables preserved</div></section></div>
    </>
  );
}
