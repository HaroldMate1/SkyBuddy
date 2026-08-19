/**
 * GET /api/cron/check-prices — the scheduled sweep.
 *
 * Vercel Cron calls this on the schedule in vercel.json with
 * `Authorization: Bearer $CRON_SECRET`. It re-prices every active tracked
 * flight, stores the observation, and emails the traveller when a target is
 * met, a new low is set, or the fare drops sharply.
 */

const { admin } = require("../../server/supabase");
const { checkTrackedFlight, evaluateStoredPrice } = require("../../server/tracking");
const { isSandbox } = require("../../server/duffel");

/** Keep one invocation inside the serverless time budget. */
const MAX_FLIGHTS_PER_RUN = 40;

function authorised(req) {
  const secret = process.env.CRON_SECRET;
  if (!secret) return true; // no secret configured: rely on Vercel's own cron auth
  const header = req.headers.authorization || "";
  return header === `Bearer ${secret}`;
}

module.exports = async (req, res) => {
  if (!authorised(req)) {
    return res.status(401).json({ error: "Unauthorised." });
  }

  const started = Date.now();
  try {
    const flights = await admin(
      `tracked_flights?active=is.true&select=*&order=last_checked_at.asc.nullsfirst&limit=${MAX_FLIGHTS_PER_RUN}`
    );

    if (!flights || !flights.length) {
      return res.status(200).json({ checked: 0, alerts: 0, message: "Nothing to check." });
    }

    // One profile lookup for the whole batch, so each flight knows where to mail.
    const userIds = [...new Set(flights.map((flight) => flight.user_id))];
    const profiles = await admin(
      `profiles?id=in.(${userIds.join(",")})&select=id,email,display_name,email_alerts`
    );
    const byUser = Object.fromEntries((profiles || []).map((profile) => [profile.id, profile]));

    // A Duffel test token invents prices, so the sweep must not store them as
    // history. When the key is a sandbox one we only re-evaluate what the
    // Google Flights collector already wrote.
    const sandbox = isSandbox();

    const results = [];
    for (const flight of flights) {
      const profile = byUser[flight.user_id] || {};
      try {
        if (sandbox) {
          results.push(
            await evaluateStoredPrice({
              ...flight,
              email: profile.email,
              display_name: profile.display_name,
              email_alerts: profile.email_alerts,
            })
          );
          continue;
        }
        results.push(
          await checkTrackedFlight(
            {
              ...flight,
              email: profile.email,
              display_name: profile.display_name,
              email_alerts: profile.email_alerts,
            },
            { duffelKey: process.env.DUFFEL_API_KEY, sendEmail: true }
          )
        );
      } catch (error) {
        console.error(`check failed for ${flight.id}:`, error.message);
        results.push({ flight_id: flight.id, status: "error", error: error.message });
      }
    }

    return res.status(200).json({
      checked: results.length,
      mode: sandbox ? "evaluate_stored" : "duffel",
      alerts: results.filter((result) => result.status === "alerted").length,
      errors: results.filter((result) => result.status === "error").length,
      duration_ms: Date.now() - started,
      results,
    });
  } catch (error) {
    console.error("cron sweep failed:", error);
    return res.status(error.statusCode || 500).json({ error: error.message });
  }
};
