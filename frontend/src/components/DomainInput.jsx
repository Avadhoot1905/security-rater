function DomainInput({ domain, loading, onDomainChange, onScan }) {
  const handleSubmit = (event) => {
    event.preventDefault();
    onScan();
  };

  return (
    <form className="input-row" onSubmit={handleSubmit}>
      <input
        type="text"
        value={domain}
        onChange={(event) => onDomainChange(event.target.value)}
        placeholder="example.com"
        aria-label="Domain name"
      />
      <button type="submit" disabled={loading}>
        {loading ? 'Scanning...' : 'Scan'}
      </button>
    </form>
  );
}

export default DomainInput;