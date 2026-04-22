const DEFAULT_API_BASE_URL = "http://localhost:8080/healthmate";

function normalizeBaseUrl(url) {
  return String(url || "").replace(/\/+$/, "");
}

// Main backend URL for the frontend.
// Change VITE_API_BASE_URL in .env files instead of editing source code.
export const API_BASE_URL = normalizeBaseUrl(
  import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL,
);

// Set VITE_USE_MOCK_API=true to enable mock API mode.
export const USE_MOCK_API = import.meta.env.VITE_USE_MOCK_API === "true";
