/**
 * Duffel flight search, normalised for SkyBuddy.
 *
 * Uses plain fetch so the deployment stays dependency-free.
 */

const DUFFEL_URL = "https://api.duffel.com/air/offer_requests?return_offers=true&supplier_timeout=20000";
const CABINS = new Set(["economy", "premium_economy", "business", "first"]);

/** Build the Google Flights deep link SkyBuddy uses as the bookable URL. */
function googleFlightsUrl({ origin, destination, outbound_date, return_date }) {
  const query = return_date
    ? `Flights from ${origin} to ${destination} on ${outbound_date} through ${return_date}`
    : `Flights from ${origin} to ${destination} on ${outbound_date}`;
  return `https://www.google.com/travel/flights?q=${encodeURIComponent(query)}`;
}

/** Minutes from an ISO-8601 duration such as PT16H35M. */
function durationMinutes(value) {
  if (!value) return null;
  const match = /^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?/.exec(value);
  if (!match) return null;
  const [, days, hours, minutes] = match;
  return Number(days || 0) * 1440 + Number(hours || 0) * 60 + Number(minutes || 0);
}

function normaliseOffer(offer, request) {
  const slices = offer.slices || [];
  const outbound = slices[0] || {};
  const segments = outbound.segments || [];
  const first = segments[0] || {};
  const last = segments[segments.length - 1] || {};

  return {
    offer_id: offer.id,
    airline: (offer.owner && offer.owner.name) || "Unknown",
    airline_code: (offer.owner && offer.owner.iata_code) || "",
    price: Number(offer.total_amount),
    currency: offer.total_currency,
    duration_minutes: durationMinutes(outbound.duration),
    stops: Math.max(segments.length - 1, 0),
    departure_time: first.departing_at || null,
    arrival_time: last.arriving_at || null,
    flight_number: first.operating_carrier_flight_number
      ? `${(first.operating_carrier && first.operating_carrier.iata_code) || ""} ${first.operating_carrier_flight_number}`.trim()
      : "",
    aircraft: (first.aircraft && first.aircraft.name) || "",
    origin: request.origin,
    destination: request.destination,
    booking_url: googleFlightsUrl(request),
  };
}

/**
 * Search Duffel for a route.
 *
 * @param {object} request  origin, destination, outbound_date, return_date, passengers, cabin
 * @param {string} apiKey   Duffel access token
 * @returns {Promise<{offers: object[], cheapest: object|null}>}
 */
async function searchFlights(request, apiKey) {
  if (!apiKey) {
    const error = new Error("Flight search is not configured: DUFFEL_API_KEY is missing.");
    error.statusCode = 503;
    throw error;
  }

  const origin = String(request.origin || "").toUpperCase().slice(0, 3);
  const destination = String(request.destination || "").toUpperCase().slice(0, 3);
  const cabin = CABINS.has(request.cabin) ? request.cabin : "economy";
  const travellers = Math.min(Math.max(Number(request.passengers) || 1, 1), 9);

  const slices = [{ origin, destination, departure_date: request.outbound_date }];
  if (request.return_date) {
    slices.push({ origin: destination, destination: origin, departure_date: request.return_date });
  }

  const response = await fetch(DUFFEL_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Duffel-Version": "v2",
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      data: {
        slices,
        passengers: Array.from({ length: travellers }, () => ({ type: "adult" })),
        cabin_class: cabin,
      },
    }),
  });

  if (!response.ok) {
    const detail = await response.text();
    const error = new Error(`Duffel search failed (${response.status}): ${detail.slice(0, 300)}`);
    error.statusCode = response.status === 401 ? 500 : 502;
    throw error;
  }

  const payload = await response.json();
  const context = { origin, destination, outbound_date: request.outbound_date, return_date: request.return_date };
  const offers = ((payload.data && payload.data.offers) || [])
    .map((offer) => normaliseOffer(offer, context))
    .filter((offer) => Number.isFinite(offer.price) && offer.price > 0)
    .sort((a, b) => a.price - b.price);

  return { offers, cheapest: offers[0] || null };
}

module.exports = { searchFlights, googleFlightsUrl, durationMinutes };
