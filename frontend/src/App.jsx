import { useState } from 'react';
import DomainInput from './components/DomainInput';
import ResultCard from './components/ResultCard';
import FeatureList from './components/FeatureList';
import { scanDomain } from './api/scan';

function App() {
  const [domain, setDomain] = useState('');
  const [loading, setLoading] = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [error, setError] = useState('');

  const handleScan = async () => {
    const value = domain.trim();

    if (!value) {
      setError('Enter a domain name to scan.');
      setScanResult(null);
      return;
    }

    setLoading(true);
    setError('');
    setScanResult(null);

    const { data, error: apiError } = await scanDomain(value);

    if (apiError || !data) {
      setError(apiError || 'Unable to scan this domain right now.');
      setLoading(false);
      return;
    }

    setScanResult(data);
    setLoading(false);
  };

  return (
    <main className="app-shell">
      <section className="app-card">
        <header className="hero">
          <p className="eyebrow">Website Security Rating System</p>
          <h1>Scan a domain and review its security posture.</h1>
          <p className="subtitle">
            Enter a website domain, fetch the Flask scan result, and inspect the score, grade, features, and risk flags.
          </p>
        </header>

        <DomainInput
          domain={domain}
          loading={loading}
          onDomainChange={setDomain}
          onScan={handleScan}
        />

        {error ? <div className="message error">{error}</div> : null}
        {loading ? <div className="message loading">Scanning domain...</div> : null}

        {scanResult ? (
          <div className="results-grid">
            <ResultCard result={scanResult.result} domain={scanResult.domain} />
            <FeatureList features={scanResult.features} flags={scanResult.result?.flags || []} />
          </div>
        ) : null}
      </section>
    </main>
  );
}

export default App;