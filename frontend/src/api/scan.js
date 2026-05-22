const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export async function scanDomain(domain) {
  try {
    const response = await fetch(`${API_BASE_URL}/scan?domain=${encodeURIComponent(domain)}`);
    const rawBody = await response.text();
    const data = rawBody ? JSON.parse(rawBody) : null;

    if (!response.ok) {
      const message = data?.error || rawBody || 'The scan request failed.';
      return { data: null, error: message };
    }

    return { data, error: null };
  } catch (error) {
    return {
      data: null,
      error: error instanceof Error ? error.message : 'Cannot reach the backend API. Make sure Flask is running on port 5001.',
    };
  }
}