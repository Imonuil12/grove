// Shared by the account menu and login page. Guest identity is tab-scoped,
// not a Cognito account or a fabricated login token.
export async function startGuestSession(apiBaseUrl, returnTo) {
  const response = await fetch(`${apiBaseUrl.replace(/\/$/, "")}/auth/guest`, {
    method: "POST"
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "Could not start guest play.");
  if (!data.token || !data.username) throw new Error("The server did not return a guest session.");

  sessionStorage.setItem("guestToken", data.token);
  sessionStorage.setItem("guestIdentity", data.username);
  // Only same-site pages, so a crafted link can't send guests elsewhere.
  const safe = typeof returnTo === "string" && /^[\w-]+\.html(\?[^#]*)?(#[\w-]*)?$/.test(returnTo);
  window.location.href = safe ? returnTo : "index.html";
}
