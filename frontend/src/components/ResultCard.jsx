function getScoreTone(score) {
  if (score >= 80) {
    return 'good';
  }

  if (score >= 60) {
    return 'warn';
  }

  return 'bad';
}

function ResultCard({ result, domain }) {
  const score = Number(result?.score ?? 0);
  const grade = result?.grade || '-';
  const tone = getScoreTone(score);

  return (
    <article className="result-card">
      <p className="card-label">Scan result</p>
      <h2>{domain}</h2>
      <div className="score-row">
        <div className={`score-display ${tone}`}>
          <span className="score-value">{score}</span>
          <span className="score-max">/100</span>
        </div>
        <div className="grade-badge">Grade {grade}</div>
      </div>
      <p className="result-copy">
        The score reflects the backend assessment of TLS, HTTP headers, WHOIS age, and page signals.
      </p>
    </article>
  );
}

export default ResultCard;