import { httpRequest } from '@/shared/api/httpClient';

export function register(payload) {
  return httpRequest('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function login(payload) {
  return httpRequest('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function me() {
  return httpRequest('/api/auth/me');
}

export function logout() {
  return httpRequest('/api/auth/logout', {
    method: 'POST',
  });
}
