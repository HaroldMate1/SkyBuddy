/**
 * Public runtime configuration for the browser.
 *
 * Only values that are safe in a client bundle: the Supabase project URL and
 * its anon key (both are public by design and protected by row-level
 * security), plus flags so the UI can explain what is not set up yet.
 */
module.exports = (req, res) => {
  res.setHeader("Cache-Control", "public, max-age=60, s-maxage=300");
  res.status(200).json({
    supabaseUrl: process.env.SUPABASE_URL || "",
    supabaseAnonKey: process.env.SUPABASE_ANON_KEY || "",
    features: {
      auth: Boolean(process.env.SUPABASE_URL && process.env.SUPABASE_ANON_KEY),
      liveSearch: Boolean(process.env.DUFFEL_API_KEY),
      emailAlerts: Boolean(process.env.RESEND_API_KEY),
      tracking: Boolean(process.env.SUPABASE_SERVICE_ROLE_KEY),
      sandbox: String(process.env.DUFFEL_API_KEY || "").startsWith("duffel_test_"),
      collector: Boolean(process.env.GITHUB_DISPATCH_TOKEN),
    },
  });
};
