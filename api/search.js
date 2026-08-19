/**
 * POST /api/search — live fares for a route, for signed-in travellers.
 *
 * The Duffel key never reaches the browser: the client sends its Supabase
 * access token, this function verifies it and does the search server-side.
 */

const { searchFlights } = require("../server/duffel");
const { getUser, bearerToken } = require("../server/supabase");

const DATE = /^\d{4}-\d{2}-\d{2}$/;

module.exports = async (req, res) => {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Use POST." });
  }

  try {
    const user = await getUser(bearerToken(req));
    if (!user) {
      return res.status(401).json({ error: "Sign in to run a live search." });
    }

    const body = typeof req.body === "string" ? JSON.parse(req.body || "{}") : req.body || {};
    const origin = String(body.origin || "").toUpperCase();
    const destination = String(body.destination || "").toUpperCase();

    if (!/^[A-Z]{3}$/.test(origin) || !/^[A-Z]{3}$/.test(destination)) {
      return res.status(400).json({ error: "Origin and destination must be IATA codes." });
    }
    if (origin === destination) {
      return res.status(400).json({ error: "Origin and destination must differ." });
    }
    if (!DATE.test(body.outbound_date || "")) {
      return res.status(400).json({ error: "outbound_date must be YYYY-MM-DD." });
    }
    if (body.return_date && !DATE.test(body.return_date)) {
      return res.status(400).json({ error: "return_date must be YYYY-MM-DD." });
    }

    const { offers } = await searchFlights(
      {
        origin,
        destination,
        outbound_date: body.outbound_date,
        return_date: body.return_date || null,
        passengers: body.passengers,
        cabin: body.cabin,
      },
      process.env.DUFFEL_API_KEY
    );

    return res.status(200).json({
      origin,
      destination,
      outbound_date: body.outbound_date,
      return_date: body.return_date || null,
      count: offers.length,
      offers: offers.slice(0, 12),
    });
  } catch (error) {
    console.error("search failed:", error);
    return res.status(error.statusCode || 500).json({ error: error.message });
  }
};
