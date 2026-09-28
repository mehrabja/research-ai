import Link from "next/link";
import type { Route } from "next";
const modules: Array<{
  title: string;
  desc: string;
  href: Route;
}> = [
  {title:"AI Paper Chat", desc:"Interactive assistant beside PDFs with citations and highlighted answers.", href:"/files"},
  {title:"PDF Workspace", desc:"Upload area, document preview, annotations and notes workflow.", href:"/files"},
  {title:"Literature Review", desc:"Review builder, paper comparison and research gap canvas.", href:"/literature"},
  {title:"Citation Lab", desc:"Citation library, formats and bibliography export workspace.", href:"/sources"},
  {title:"Knowledge Graph", desc:"Concepts, papers and evidence relationship visualization.", href:"/knowledge"},
  {title:"Team Research", desc:"Review comments, roles and collaboration activity.", href:"/collaboration"},
];

export default function ResearchAIStudio(){
 return <section className="card pad" style={{marginTop:16}}>
  <div className="row"><div><h2>Research AI Studio</h2><p className="muted small">Frontend experiences ready for backend APIs</p></div><span className="tag">6 modules</span></div>
  <div className="grid grid-3" style={{marginTop:16}}>
  {modules.map(m=><article className="card pad" key={m.title}>
    <h3>{m.title}</h3><p className="muted small">{m.desc}</p>
    <Link className="btn primary" href={m.href}>Launch</Link>
  </article>)}
  </div>
 </section>
}
