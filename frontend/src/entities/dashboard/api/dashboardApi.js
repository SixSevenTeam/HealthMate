import { httpRequest } from "@/shared/api/httpClient";

export function getDashboardSummary(from, to) {
  const params = new URLSearchParams();

  if (from) {
    params.set("from", from);
  }

  if (to) {
    params.set("to", to);
  }

  const query = params.toString();
  return httpRequest(`/api/dashboard/summary${query ? `?${query}` : ""}`);
}
