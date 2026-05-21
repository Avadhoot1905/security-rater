export async function scanDomain(domain) {
  try {
    const response = await fetch(`/scan?domain=${encodeURIComponent(domain)}`);
    const data = await response.json().catch(() => null);

    if (!response.ok) {
      const message = data?.error || 'The scan request failed.';
      return { data: null, error: message };
    }

    return { data, error: null };
  } catch {
    return { data: null, error: 'Cannot reach the backend API. Make sure Flask is running on port 5000.' };
  }
}