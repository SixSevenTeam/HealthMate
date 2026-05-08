import { httpRequest } from "@/shared/api/httpClient";

export function getDashboardSummary(from, to, scope = "active") {
  const params = new URLSearchParams();

  if (from) {
    params.set("from", from);
  }

  if (to) {
    params.set("to", to);
  }

  if (scope) {
    params.set("scope", scope);
  }

  const query = params.toString();
  return httpRequest(`/api/dashboard/summary${query ? `?${query}` : ""}`);
}
