/**
 * POST /api/check — re-price one tracked flight on demand ("Check now").
 *
 * Runs the same pipeline as the nightly sweep, but only for a flight the
 * caller owns, so the traveller sees a fresh price and a first data point
 * the moment they start tracking a route.
 */

const { admin, getUser, bearerToken } = require("../server/supabase");
const { checkTrackedFlight, MIN_CHECK_SECONDS } = require("../server/tracking");

module.exports = async (req, res) => {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Use POST." });
  }

  try {
    const user = await getUser(bearerToken(req));
    if (!user) {
      return res.status(401).json({ error: "Sign in first." });
    }

    const body = typeof req.body === "string" ? JSON.parse(req.body || "{}") : req.body || {};
    const flightId = String(body.tracked_flight_id || "");
    if (!/^[0-9a-f-]{36}$/i.test(flightId)) {
      return res.status(400).json({ error: "tracked_flight_id must be a UUID." });
    }

    const rows = await admin(
      `tracked_flights?id=eq.${flightId}&user_id=eq.${user.id}&select=*&limit=1`
    );
    const flight = (rows || [])[0];
    if (!flight) {
      return res.status(404).json({ error: "That tracked flight does not exist." });
    }

    const profiles = await admin(
      `profiles?id=eq.${user.id}&select=email,display_name,email_alerts&limit=1`
    );
    const profile = (profiles || [])[0] || {};

    const result = await checkTrackedFlight(
      {
        ...flight,
        email: profile.email || user.email,
        display_name: profile.display_name,
        email_alerts: profile.email_alerts,
      },
      {
        duffelKey: process.env.DUFFEL_API_KEY,
        sendEmail: true,
        minIntervalSeconds: MIN_CHECK_SECONDS,
      }
    );

    return res.status(200).json(result);
  } catch (error) {
    console.error("check failed:", error);
    return res.status(error.statusCode || 500).json({ error: error.message });
  }
};
