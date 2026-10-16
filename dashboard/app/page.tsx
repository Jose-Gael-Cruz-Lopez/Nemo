const stages = ["Observe", "Classify", "Estimate", "Review"];

export default function Home() {
  return (
    <main className="shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Reeftrace home">
          <span className="brand-mark">R</span>
          <span>reeftrace</span>
        </a>
        <span className="system-state"><span className="state-dot" /> LOCAL SYSTEM</span>
      </header>

      <section className="hero">
        <p className="eyebrow">CONTROLLED SOURCE-INTELLIGENCE PROOF OF CONCEPT</p>
        <h1>See where the current<br />may have started.</h1>
        <p className="intro">
          Reeftrace combines camera observations with a measured tank transport model
          to compare candidate debris sources—and make uncertainty visible.
        </p>
        <div className="stage-list" aria-label="Inference workflow">
          {stages.map((stage, index) => (
            <div className="stage" key={stage}>
              <span className="stage-number">0{index + 1}</span>
              <span>{stage}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="workspace" aria-label="Run workspace">
        <div className="workspace-heading">
          <div>
            <p className="eyebrow">WORKSPACE</p>
            <h2>Tank overview</h2>
          </div>
          <span className="badge">AWAITING CAMERA</span>
        </div>
        <div className="tank-panel">
          <div className="tank-grid" aria-hidden="true">
            <div className="source source-a">A</div>
            <div className="source source-b">B</div>
            <div className="source source-c">C</div>
            <div className="coral coral-one" />
            <div className="coral coral-two" />
            <div className="flow flow-one" />
            <div className="flow flow-two" />
            <div className="flow flow-three" />
            <span className="tank-caption">LIVE TRANSPORT MAP</span>
          </div>
          <aside className="evidence-panel">
            <p className="eyebrow">LATEST EVIDENCE</p>
            <p className="empty-state">No active run</p>
            <p className="muted">Connect a camera and load a calibrated site model to begin.</p>
          </aside>
        </div>
        <p className="disclaimer">A source match is not a verified geographic attribution. Results depend on the active site model and its validation.</p>
      </section>
      <footer>REEFTRACE <span>·</span> LOCAL DEMONSTRATION CONSOLE</footer>
    </main>
  );
}
