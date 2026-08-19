/**
 * Re-price one tracked flight: record the observation, refresh its statistics,
 * decide whether it is worth an alert, and send the email.
 *
 * Shared by the cron sweep and the "check now" button.
 */

const { searchFlights, isSandbox } = require("./duffel");
const { admin } = require("./supabase");
const { sendAlertEmail } = require("./email");

/** How much cheaper than the previous price counts as a drop worth an email. */
const DROP_THRESHOLD = 0.9;

/** Do not repeat the same kind of alert for the same flight within this window. */
const ALERT_COOLDOWN_HOURS = 20;

/**
 * Shortest gap between two manual checks of the same flight. Without it a
 * double-click writes two observations seconds apart, which says nothing about
 * the fare and skews the median.
 */
const MIN_CHECK_SECONDS = 120;

function median(values) {
  if (!values.length) return null;
  const ordered = [...values].sort((a, b) => a - b);
  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2
    ? ordered[middle]
    : Number(((ordered[middle - 1] + ordered[middle]) / 2).toFixed(2));
}

function round(value) {
  return value === null || value === undefined ? null : Number(Number(value).toFixed(2));
}

/**
 * Decide which alert (if any) this new price deserves.
 *
 * Order matters: the target the traveller set beats "cheapest ever", which in
 * turn beats an ordinary drop.
 */
function classify({ price, target, previousLow, previousPrice, samples }) {
  if (target !== null && target !== undefined && price <= Number(target)) {
    return {
      kind: "target_reached",
      message: `Your target of ${target} was met — the fare is now ${price}.`,
    };
  }
  if (previousLow !== null && previousLow !== undefined && samples >= 3 && price < Number(previousLow)) {
    return {
      kind: "new_low",
      message: `Cheapest price SkyBuddy has ever recorded for this route: ${price} (previous best ${previousLow}).`,
    };
  }
  if (
    previousPrice !== null &&
    previousPrice !== undefined &&
    price <= Number(previousPrice) * DROP_THRESHOLD
  ) {
    const drop = Math.round((1 - price / Number(previousPrice)) * 100);
    return { kind: "price_drop", message: `The fare dropped ${drop}% since the last check.` };
  }
  return null;
}

/** Has this alert kind already gone out recently for this flight? */
async function recentlyAlerted(flightId, kind) {
  const since = new Date(Date.now() - ALERT_COOLDOWN_HOURS * 3600 * 1000).toISOString();
  const rows = await admin(
    `alerts?tracked_flight_id=eq.${flightId}&kind=eq.${kind}&created_at=gte.${since}&select=id&limit=1`
  );
  return Array.isArray(rows) && rows.length > 0;
}

/**
 * Apply one price to a tracked flight: optionally store it, refresh the
 * statistics, decide whether it deserves an alert, and send the email.
 *
 * Every price source funnels through here — Duffel, the Google Flights
 * collector, or a manual entry — so the alert rules live in exactly one place.
 *
 * @param {object} flight   row from tracked_flights (plus email/display_name)
 * @param {object} quote    { price, currency, airline, booking_url, source }
 * @param {object} options  { insert, sendEmail, sandbox }
 */
async function applyPrice(flight, quote, { insert = true, sendEmail = true, sandbox = false } = {}) {
  const price = round(quote.price);
  const currency = quote.currency || flight.currency || "EUR";

  if (insert) {
    await admin("price_observations", {
      method: "POST",
      body: {
        tracked_flight_id: flight.id,
        user_id: flight.user_id,
        price,
        currency,
        airline: quote.airline,
        booking_url: quote.booking_url,
        source: quote.source || "duffel",
      },
      prefer: "return=minimal",
    });
  }

  // Recompute the statistics from the full history.
  const history = await admin(
    `price_observations?tracked_flight_id=eq.${flight.id}&select=price&order=observed_at.desc&limit=400`
  );
  const prices = (history || []).map((row) => Number(row.price)).filter(Number.isFinite);

  const stats = {
    last_price: price,
    lowest_price: round(Math.min(...prices, price)),
    highest_price: round(Math.max(...prices, price)),
    median_price: round(median(prices.length ? prices : [price])),
    last_airline: quote.airline,
    last_booking_url: quote.booking_url,
    last_checked_at: new Date().toISOString(),
  };

  const alert = classify({
    price,
    target: flight.target_price,
    previousLow: flight.lowest_price,
    previousPrice: flight.last_price,
    samples: prices.length,
  });

  await admin(`tracked_flights?id=eq.${flight.id}`, { method: "PATCH", body: stats });

  if (!alert) {
    return { flight_id: flight.id, status: "checked", price, currency, stats };
  }
  if (await recentlyAlerted(flight.id, alert.kind)) {
    return { flight_id: flight.id, status: "alert_suppressed", price, currency, kind: alert.kind };
  }

  let emailedAt = null;
  if (sendEmail && flight.email && flight.email_alerts !== false) {
    emailedAt = await sendAlertEmail({
      to: flight.email,
      name: flight.display_name,
      flight,
      price,
      currency,
      previousPrice: flight.last_price,
      stats,
      kind: alert.kind,
      message: alert.message,
      bookingUrl: quote.booking_url,
      airline: quote.airline,
      sandbox,
    });
  }

  await admin("alerts", {
    method: "POST",
    body: {
      tracked_flight_id: flight.id,
      user_id: flight.user_id,
      kind: alert.kind,
      price,
      previous_price: flight.last_price,
      currency,
      message: alert.message,
      booking_url: quote.booking_url,
      emailed_at: emailedAt,
    },
    prefer: "return=minimal",
  });

  return {
    flight_id: flight.id,
    status: "alerted",
    kind: alert.kind,
    price,
    currency,
    emailed: Boolean(emailedAt),
    stats,
  };
}

/**
 * Re-price one tracked flight through Duffel.
 *
 * @param {object} flight   row from tracked_flights
 * @param {object} options  { duffelKey, sendEmail, minIntervalSeconds }
 */
async function checkTrackedFlight(flight, { duffelKey, sendEmail = true, minIntervalSeconds = 0 } = {}) {
  if (minIntervalSeconds && flight.last_checked_at) {
    const secondsSince = (Date.now() - new Date(flight.last_checked_at).getTime()) / 1000;
    if (secondsSince < minIntervalSeconds) {
      return {
        flight_id: flight.id,
        status: "too_soon",
        retry_in_seconds: Math.ceil(minIntervalSeconds - secondsSince),
      };
    }
  }

  const sandbox = isSandbox(duffelKey);
  const { cheapest } = await searchFlights(
    {
      origin: flight.origin,
      destination: flight.destination,
      outbound_date: flight.outbound_date,
      return_date: flight.return_date,
      passengers: flight.passengers,
      cabin: flight.cabin,
    },
    duffelKey
  );

  if (!cheapest) {
    await admin(`tracked_flights?id=eq.${flight.id}`, {
      method: "PATCH",
      body: { last_checked_at: new Date().toISOString() },
    });
    return { flight_id: flight.id, status: "no_offers" };
  }

  return applyPrice(
    flight,
    {
      price: cheapest.price,
      currency: cheapest.currency,
      airline: cheapest.airline,
      booking_url: cheapest.booking_url,
      source: sandbox ? "duffel_test" : "duffel",
    },
    { insert: true, sendEmail, sandbox }
  );
}

/**
 * Evaluate the newest stored observation for a flight without querying any
 * provider — used after the Google Flights collector writes its results.
 */
async function evaluateStoredPrice(flight, { sendEmail = true } = {}) {
  const rows = await admin(
    `price_observations?tracked_flight_id=eq.${flight.id}` +
      "&select=price,currency,airline,booking_url,source&order=observed_at.desc&limit=1"
  );
  const latest = (rows || [])[0];
  if (!latest) return { flight_id: flight.id, status: "no_observations" };

  return applyPrice(
    flight,
    {
      price: latest.price,
      currency: latest.currency,
      airline: latest.airline,
      booking_url: latest.booking_url,
      source: latest.source,
    },
    { insert: false, sendEmail, sandbox: String(latest.source || "").endsWith("_test") }
  );
}

module.exports = {
  applyPrice,
  checkTrackedFlight,
  evaluateStoredPrice,
  classify,
  median,
  MIN_CHECK_SECONDS,
};
