export default function ResearchFeatureHub() {
  const features = [
    ["AI PDF Assistant", "Ask questions from papers, summarize sections, extract findings"],
    ["Citation Manager", "APA / IEEE / BibTeX export workflow ready for backend integration"],
    ["Literature Review", "Generate reviews, compare papers and identify research gaps"],
    ["Knowledge Graph", "Visualize papers, concepts and evidence relationships"],
    ["Collaboration", "Comments, roles, reviews and team workflows"],
    ["Smart Search", "Global search across projects, files and sources"],
  ];

  return (
    <section className="card pad" style={{marginTop:"16px"}}>
      <div className="row">
        <div>
          <h3>Research AI capabilities</h3>
          <div className="muted small">Frontend modules prepared for API integration</div>
        </div>
        <span className="tag">Product upgrade</span>
      </div>
      <div className="grid grid-3" style={{marginTop:"16px"}}>
        {features.map(([title, desc]) => (
          <div className="card pad" key={title}>
            <h4>{title}</h4>
            <p className="muted small">{desc}</p>
            <button className="btn" data-toast={`${title} opened`}>Open</button>
          </div>
        ))}
      </div>
    </section>
  );
}
