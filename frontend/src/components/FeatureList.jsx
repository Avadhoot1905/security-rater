function formatValue(value) {
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return 'None';
    }

    return value.map((item) => String(item)).join(', ');
  }

  if (value === null || value === undefined || value === '') {
    return 'Not available';
  }

  if (typeof value === 'object') {
    const entries = Object.entries(value);
    if (entries.length === 0) {
      return 'Not available';
    }

    return entries.map(([key, nestedValue]) => `${key}: ${formatValue(nestedValue)}`).join(' · ');
  }

  return String(value);
}

function flattenFeatures(features, prefix = '') {
  if (!features || typeof features !== 'object' || Array.isArray(features)) {
    return [];
  }

  return Object.entries(features).flatMap(([key, value]) => {
    const label = prefix ? `${prefix}.${key}` : key;

    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return flattenFeatures(value, label);
    }

    return [{ label, value: formatValue(value) }];
  });
}

function FeatureList({ features, flags = [] }) {
  const rows = flattenFeatures(features);

  return (
    <article className="feature-card">
      <div className="section-head">
        <div>
          <p className="card-label">Key features</p>
          <h3>Signals from the scan</h3>
        </div>
      </div>

      <dl className="feature-list">
        {rows.length > 0 ? (
          rows.map((row) => (
            <div className="feature-row" key={row.label}>
              <dt>{row.label}</dt>
              <dd>{row.value}</dd>
            </div>
          ))
        ) : (
          <div className="empty-state">No feature data returned.</div>
        )}
      </dl>

      <div className="flags-block">
        <p className="card-label">Risk flags</p>
        {flags.length > 0 ? (
          <div className="flag-list">
            {flags.map((flag) => (
              <span className="flag-pill" key={flag}>
                {flag}
              </span>
            ))}
          </div>
        ) : (
          <div className="empty-state">No flags returned.</div>
        )}
      </div>
    </article>
  );
}

export default FeatureList;