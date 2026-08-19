/**
 * Thin Supabase REST helpers for the serverless functions.
 *
 * The browser talks to Supabase directly with the anon key and RLS; these
 * helpers exist for the two things the browser must not do: verify a token
 * server-side, and write with the service-role key from the cron job.
 */

const SUPABASE_URL = (process.env.SUPABASE_URL || "").replace(/\/+$/, "");
const ANON_KEY = process.env.SUPABASE_ANON_KEY || "";
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || "";

function requireConfig() {
  if (!SUPABASE_URL || !ANON_KEY) {
    const error = new Error("Supabase is not configured: set SUPABASE_URL and SUPABASE_ANON_KEY.");
    error.statusCode = 503;
    throw error;
  }
}

/** Resolve the signed-in user from a browser access token. */
async function getUser(accessToken) {
  requireConfig();
  if (!accessToken) return null;

  const response = await fetch(`${SUPABASE_URL}/auth/v1/user`, {
    headers: { apikey: ANON_KEY, Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok) return null;

  const user = await response.json();
  return user && user.id ? user : null;
}

/** Read the bearer token off a request. */
function bearerToken(req) {
  const header = req.headers.authorization || req.headers.Authorization || "";
  return header.startsWith("Bearer ") ? header.slice(7) : "";
}

/** Query PostgREST with the service-role key (bypasses RLS — server only). */
async function admin(path, { method = "GET", body, prefer } = {}) {
  requireConfig();
  if (!SERVICE_KEY) {
    const error = new Error("Server writes are not configured: SUPABASE_SERVICE_ROLE_KEY is missing.");
    error.statusCode = 503;
    throw error;
  }

  const headers = {
    apikey: SERVICE_KEY,
    Authorization: `Bearer ${SERVICE_KEY}`,
    "Content-Type": "application/json",
  };
  if (prefer) headers.Prefer = prefer;

  const response = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  const text = await response.text();
  if (!response.ok) {
    throw new Error(`Supabase ${method} ${path} failed (${response.status}): ${text.slice(0, 300)}`);
  }
  return text ? JSON.parse(text) : null;
}

module.exports = { getUser, bearerToken, admin, SUPABASE_URL, ANON_KEY };
