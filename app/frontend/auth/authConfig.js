// Auth settings come from the backend (/auth/config), which reads them from
// the project .env. Nothing account-specific is hard-coded in the browser.
const API_BASE_URL = (typeof window !== "undefined" && window.API_BASE_URL) ||
  (/^55\d\d$/.test(location.port) ? `http://${location.hostname || "127.0.0.1"}:8000` : location.origin);

let cognito = {};
let provider = "local";
try {
  const res = await fetch(`${API_BASE_URL}/auth/config`);
  if (res.ok) {
    const data = await res.json();
    cognito = data.cognito || {};
    provider = data.provider || (cognito.user_pool_id ? "cognito" : "local");
  }
} catch (e) {
  console.warn("Could not load auth config from the backend:", e);
}

export const authConfig = {
  // "local" = built-in email/password accounts on our backend; "cognito" = AWS Cognito.
  PROVIDER: provider,
  REGION: cognito.region || "",
  USER_POOL_ID: cognito.user_pool_id || "",
  CLIENT_ID: cognito.client_id || "",
  COGNITO_DOMAIN: cognito.domain || "",
  REDIRECT_URI: cognito.redirect_uri || "",
  API_BASE_URL,
};
