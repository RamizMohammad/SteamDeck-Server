const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3001';

let authToken: string | null = localStorage.getItem('authToken');

export function setAuthToken(token: string) {
  authToken = token;
  localStorage.setItem('authToken', token);
}

export function clearAuthToken() {
  authToken = null;
  localStorage.removeItem('authToken');
}

export function getAuthToken(): string | null {
  return authToken;
}

async function fetchApi(endpoint: string, options: RequestInit = {}) {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`;
  }

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Request failed' }));
    throw new Error(error.error || `HTTP ${response.status}`);
  }

  return response.json();
}

export async function login(email: string, password: string) {
  const data = await fetchApi('/api/auth', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  setAuthToken(data.token);
  return data.user;
}

export async function getMe() {
  return fetchApi('/api/me');
}

export async function setPairingCode(pairingCode: string) {
  return fetchApi('/api/pairing', {
    method: 'POST',
    body: JSON.stringify({ pairingCode }),
  });
}

export async function getPrograms() {
  return fetchApi('/api/programs');
}

export async function addProgram(program: { name: string; iconUrl: string; exec: string; meta?: any }) {
  return fetchApi('/api/programs', {
    method: 'POST',
    body: JSON.stringify(program),
  });
}

export async function getActivity() {
  return fetchApi('/api/activity');
}

export async function addActivity(entry: { type: string; msg: string; raw?: any }) {
  return fetchApi('/api/activity', {
    method: 'POST',
    body: JSON.stringify(entry),
  });
}
