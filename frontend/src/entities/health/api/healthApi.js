import { httpRequest } from '@/shared/api/httpClient';

export function getHealth() {
  return httpRequest('/api/health');
}
