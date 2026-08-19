/**
 * POST /api/evaluate — run the alert rules over already-stored prices.
 *
 * The Google Flights collector writes observations straight into Supabase and
 * then calls this, so the alert rules, statistics and emails stay in one place
 * instead of being reimplemented in Python.
 *
 * Authorised with CRON_SECRET, like the scheduled sweep.
 */

const { admin } = require("../server/supabase");
const { evaluateStoredPrice } = require("../server/tracking");

const MAX_FLIGHTS = 60;

function authorised(req) {
  const secret = process.env.CRON_SECRET;
  if (!secret) return false;
  return (req.headers.authorization || "") === `Bearer ${secret}`;
}

module.exports = async (req, res) => {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Use POST." });
  }
  if (!authorised(req)) {
    return res.status(401).json({ error: "Unauthorised." });
  }

  try {
    const body = typeof req.body === "string" ? JSON.parse(req.body || "{}") : req.body || {};
    const filter = body.tracked_flight_id
      ? `id=eq.${encodeURIComponent(body.tracked_flight_id)}`
      : "active=is.true";

    const flights = await admin(`tracked_flights?${filter}&select=*&limit=${MAX_FLIGHTS}`);
    if (!flights || !flights.length) {
      return res.status(200).json({ evaluated: 0, message: "Nothing to evaluate." });
    }

    const userIds = [...new Set(flights.map((flight) => flight.user_id))];
    const profiles = await admin(
      `profiles?id=in.(${userIds.join(",")})&select=id,email,display_name,email_alerts`
    );
    const byUser = Object.fromEntries((profiles || []).map((profile) => [profile.id, profile]));

    const results = [];
    for (const flight of flights) {
      const profile = byUser[flight.user_id] || {};
      try {
        results.push(
          await evaluateStoredPrice({
            ...flight,
            email: profile.email,
            display_name: profile.display_name,
            email_alerts: profile.email_alerts,
          })
        );
      } catch (error) {
        console.error(`evaluate failed for ${flight.id}:`, error.message);
        results.push({ flight_id: flight.id, status: "error", error: error.message });
      }
    }

    return res.status(200).json({
      evaluated: results.length,
      alerts: results.filter((result) => result.status === "alerted").length,
      results,
    });
  } catch (error) {
    console.error("evaluate failed:", error);
    return res.status(error.statusCode || 500).json({ error: error.message });
  }
};
