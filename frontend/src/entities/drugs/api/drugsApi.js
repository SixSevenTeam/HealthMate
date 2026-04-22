import { httpRequest } from "@/shared/api/httpClient";

export function searchDrugs(q) {
  return httpRequest(`/api/drugs/search?q=${encodeURIComponent(q)}`);
}
