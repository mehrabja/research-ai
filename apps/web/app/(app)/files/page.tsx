import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Files & intelligence · Research AI",
};

export default function FilesPage() {
  return (
    <>
<div className="page-head"><div><h1>Files & intelligence</h1><p>Upload papers, datasets, code and notes. Intelligence is linked to the project graph.</p></div><div className="actions"><button className="btn" data-toast="Folder created">+ New folder</button><button className="btn primary" data-toast="Upload panel opened">Upload files</button></div></div><div className="card pad"><div className="row"><div><div className="strong">Drop files here</div><div className="muted small">PDF, DOCX, TXT, CSV, ZIP · max 500 MB each</div></div><span className="tag">36 files · 4.8 GB</span></div></div><div className="card table-wrap" style={{marginTop: '16px'}}><table className="table"><thead><tr><th>File</th><th>Type</th><th>Size</th><th>Intelligence</th><th>Status</th><th>Owner</th></tr></thead><tbody><tr><td><div className="strong">protocol_v7.docx</div><div className="meta">uploaded 18m ago</div></td><td>DOCX</td><td>1.8 MB</td><td>12 entities · 4 claims</td><td><span className="tag success">Indexed</span></td><td>Alex</td></tr><tr><td><div className="strong">analysis_pipeline.zip</div><div className="meta">uploaded 2h ago</div></td><td>ZIP</td><td>184 MB</td><td>23 code refs</td><td><span className="tag warn">Processing</span></td><td>Alex</td></tr><tr><td><div className="strong">participant_metadata.csv</div><div className="meta">uploaded yesterday</div></td><td>CSV</td><td>420 KB</td><td>8 schema fields</td><td><span className="tag success">Indexed</span></td><td>Samir</td></tr><tr><td><div className="strong">review_notes.pdf</div><div className="meta">uploaded Sep 23</div></td><td>PDF</td><td>2.7 MB</td><td>17 notes</td><td><span className="tag danger">Parse failed</span></td><td>Alex</td></tr></tbody></table></div>
    </>
  );
}
