/**
 * POST /api/collect — ask the Google Flights collector to run now.
 *
 * The scraper is Python and takes tens of seconds per route, so it lives in a
 * GitHub Actions workflow rather than a serverless function. This endpoint
 * triggers that workflow for the signed-in traveller, which is what makes the
 * "Refresh prices" button on the dashboard possible.
 */

const { getUser, bearerToken, admin } = require("../server/supabase");

const REPO = process.env.GITHUB_REPO || "HaroldMate1/SkyBuddy";

module.exports = async (req, res) => {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Use POST." });
  }

  const token = process.env.GITHUB_DISPATCH_TOKEN;
  if (!token) {
    return res.status(503).json({
      error:
        "On-demand collection is not configured. Add GITHUB_DISPATCH_TOKEN in Vercel, " +
        "or wait for the scheduled run.",
    });
  }

  try {
    const user = await getUser(bearerToken(req));
    if (!user) {
      return res.status(401).json({ error: "Sign in first." });
    }

    const body = typeof req.body === "string" ? JSON.parse(req.body || "{}") : req.body || {};
    let flightId = null;

    if (body.tracked_flight_id) {
      // Only ever collect for a flight the caller actually owns.
      const rows = await admin(
        `tracked_flights?id=eq.${encodeURIComponent(body.tracked_flight_id)}` +
          `&user_id=eq.${user.id}&select=id&limit=1`
      );
      if (!rows || !rows.length) {
        return res.status(404).json({ error: "That tracked flight does not exist." });
      }
      flightId = rows[0].id;
    }

    const response = await fetch(`https://api.github.com/repos/${REPO}/dispatches`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        event_type: "collect-prices",
        client_payload: flightId ? { flight_id: flightId } : {},
      }),
    });

    if (!response.ok) {
      const detail = await response.text();
      return res.status(502).json({
        error: `GitHub refused the trigger (${response.status}): ${detail.slice(0, 200)}`,
      });
    }

    return res.status(202).json({
      status: "queued",
      scope: flightId ? "flight" : "all",
      message: "Collecting real Google Flights prices — this takes about a minute per route.",
    });
  } catch (error) {
    console.error("collect trigger failed:", error);
    return res.status(error.statusCode || 500).json({ error: error.message });
  }
};
