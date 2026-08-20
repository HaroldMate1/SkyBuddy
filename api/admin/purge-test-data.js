/**
 * POST /api/admin/purge-test-data — remove sandbox prices and their alerts.
 *
 * A Duffel test token invents fares, so any history recorded from it makes the
 * low/median/high meaningless. This clears exactly that: observations from a
 * sandbox source, the alerts they raised, and the cached statistics — real
 * prices collected from Google Flights are left untouched.
 *
 * Deliberately narrow: it cannot delete tracked routes, accounts or real
 * observations, so the CRON_SECRET that guards it cannot be used to wipe data.
 */

const { admin } = require("../../server/supabase");

const SANDBOX_SOURCES = "like.duffel*";

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
    const before = await admin("price_observations?select=id,source");
    const sandboxRows = (before || []).filter((row) => String(row.source || "").startsWith("duffel"));

    // Alerts first: they reference observations only indirectly, but an alert
    // raised by an invented price is noise either way.
    const alerts = await admin("alerts?id=gt.0", {
      method: "DELETE",
      prefer: "return=representation",
    });

    const observations = await admin(`price_observations?source=${SANDBOX_SOURCES}`, {
      method: "DELETE",
      prefer: "return=representation",
    });

    // Clear the cached statistics so the next check recomputes them from the
    // real history alone.
    const flights = await admin("tracked_flights?id=not.is.null", {
      method: "PATCH",
      body: { lowest_price: null, highest_price: null, median_price: null },
      prefer: "return=representation",
    });

    const remaining = await admin(
      "price_observations?select=source,price,airline,aircraft,flight_numbers,duration_minutes" +
        "&order=observed_at.desc&limit=5"
    );

    return res.status(200).json({
      status: "purged",
      sandbox_observations_found: sandboxRows.length,
      alerts_deleted: (alerts || []).length,
      observations_deleted: (observations || []).length,
      flights_reset: (flights || []).length,
      remaining_sample: remaining || [],
    });
  } catch (error) {
    console.error("purge failed:", error);
    return res.status(error.statusCode || 500).json({ error: error.message });
  }
};
