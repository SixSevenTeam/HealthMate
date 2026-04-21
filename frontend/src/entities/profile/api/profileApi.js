import { httpRequest } from '@/shared/api/httpClient';

export function getProfile() {
  return httpRequest('/api/profile');
}

export function updateProfile(payload) {
  return httpRequest('/api/profile', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}
