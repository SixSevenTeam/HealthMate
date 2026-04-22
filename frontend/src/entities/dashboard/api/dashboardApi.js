import { httpRequest } from '@/shared/api/httpClient';

export function getDashboardSummary(from, to) {
  return httpRequest(`/api/dashboard/summary?from=${from}&to=${to}`);
}
