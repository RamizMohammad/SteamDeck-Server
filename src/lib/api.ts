// =============================
// API Base URL
// =============================
const API_URL: string =
  import.meta.env.VITE_API_URL || 'https://user.side.api.linkium.space';


// =============================
// Token Management
// =============================
function getStoredToken(): string | null {
  return localStorage.getItem('authToken');
}

export function setAuthToken(token: string): void {
  localStorage.setItem('authToken', token);
}

export function clearAuthToken(): void {
  localStorage.removeItem('authToken');
}

export function getAuthToken(): string | null {
  return getStoredToken();
}


// =============================
// Core Fetch Wrapper
// =============================
async function fetchApi<T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getStoredToken();

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (token) {
    (headers as Record<string, string>).Authorization = `Bearer ${token}`;
  }

  let response: Response;

  try {
    response = await fetch(`${API_URL}${endpoint}`, {
      ...options,
      headers,
    });
  } catch (err) {
    throw new Error('Network error. Please check your connection.');
  }

  // Handle errors safely (JSON / text / empty)
  if (!response.ok) {
    let message = `HTTP ${response.status}`;

    try {
      const data = await response.json();
      message = data.error || data.message || message;
    } catch {
      try {
        const text = await response.text();
        if (text) message = text;
      } catch {}
    }

    // Auto logout if token expired
    if (response.status === 401) {
      clearAuthToken();
    }

    throw new Error(message);
  }

  // Handle empty responses (204 No Content)
  if (response.status === 204) {
    return {} as T;
  }

  // Try JSON, fallback to text
  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    return response.json();
  }

  return (await response.text()) as unknown as T;
}


// =============================
// Types
// =============================
interface LoginResponse {
  token: string;
  user: any;
}

interface Program {
  name: string;
  iconUrl: string;
  exec: string;
  meta?: any;
}

interface ActivityEntry {
  type: string;
  msg: string;
  raw?: any;
}


// =============================
// Auth APIs
// =============================
export async function login(
  email: string,
  password: string
): Promise<any> {
  const data = await fetchApi<LoginResponse>('/api/auth', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });

  if (!data.token) {
    throw new Error('Authentication failed. Token not received.');
  }

  setAuthToken(data.token);
  return data.user;
}

export async function getMe() {
  return fetchApi('/api/me');
}


// =============================
// Pairing
// =============================
export async function setPairingCode(pairingCode: string) {
  return fetchApi('/api/pairing', {
    method: 'POST',
    body: JSON.stringify({ pairingCode }),
  });
}


// =============================
// Programs
// =============================
export async function getPrograms() {
  return fetchApi('/api/programs');
}

export async function addProgram(program: Program) {
  return fetchApi('/api/programs', {
    method: 'POST',
    body: JSON.stringify(program),
  });
}


// =============================
// Activity
// =============================
export async function getActivity() {
  return fetchApi('/api/activity');
}

export async function addActivity(entry: ActivityEntry) {
  return fetchApi('/api/activity', {
    method: 'POST',
    body: JSON.stringify(entry),
  });
}