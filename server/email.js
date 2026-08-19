/**
 * Price-alert emails, sent through Resend.
 *
 * Returns the timestamp the mail went out, or null when email is not
 * configured — a missing key must never break a price check.
 */

const RESEND_URL = "https://api.resend.com/emails";

const SUBJECTS = {
  target_reached: (flight, price, currency) =>
    `✈️ ${flight.origin} → ${flight.destination} hit your target: ${currency} ${price}`,
  new_low: (flight, price, currency) =>
    `📉 New low for ${flight.origin} → ${flight.destination}: ${currency} ${price}`,
  price_drop: (flight, price, currency) =>
    `💸 ${flight.origin} → ${flight.destination} dropped to ${currency} ${price}`,
};

function escapeHtml(value) {
  return String(value === null || value === undefined ? "" : value).replace(
    /[&<>"']/g,
    (character) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character])
  );
}

function money(value, currency) {
  return value === null || value === undefined ? "—" : `${currency} ${Number(value).toFixed(2)}`;
}

function buildHtml({ name, flight, price, currency, previousPrice, stats, message, bookingUrl, airline, sandbox }) {
  const dates = flight.return_date
    ? `${flight.outbound_date} → ${flight.return_date}`
    : flight.outbound_date;

  return `<!doctype html>
<html><body style="margin:0;background:#0d1b2a;font-family:Inter,Segoe UI,Helvetica,Arial,sans-serif;color:#eef4ff">
  <div style="max-width:560px;margin:0 auto;padding:32px 24px">
    <p style="margin:0 0 6px;font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:#00f0ff">SkyBuddy price alert</p>
    <h1 style="margin:0 0 14px;font-size:26px;line-height:1.2;color:#fff">
      ${escapeHtml(flight.origin)} → ${escapeHtml(flight.destination)}
    </h1>
    <p style="margin:0 0 22px;color:#a9b8d4;font-size:15px">
      ${escapeHtml(name ? `Hi ${name}, ` : "")}${escapeHtml(message)}
    </p>

    <div style="border:1px solid rgba(255,255,255,.14);border-radius:16px;padding:22px;background:#13223a">
      <p style="margin:0 0 4px;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#7c8bab">Current fare</p>
      <p style="margin:0 0 18px;font-size:34px;font-weight:800;color:#b4ff39">${money(price, currency)}</p>

      <table style="width:100%;border-collapse:collapse;font-size:14px;color:#a9b8d4">
        <tr><td style="padding:5px 0">Dates</td><td style="text-align:right;color:#fff">${escapeHtml(dates)}</td></tr>
        <tr><td style="padding:5px 0">Airline</td><td style="text-align:right;color:#fff">${escapeHtml(airline || "—")}</td></tr>
        <tr><td style="padding:5px 0">Previous check</td><td style="text-align:right;color:#fff">${money(previousPrice, currency)}</td></tr>
        <tr><td style="padding:5px 0">Recorded low</td><td style="text-align:right;color:#b4ff39">${money(stats.lowest_price, currency)}</td></tr>
        <tr><td style="padding:5px 0">Recorded median</td><td style="text-align:right;color:#fff">${money(stats.median_price, currency)}</td></tr>
        <tr><td style="padding:5px 0">Recorded high</td><td style="text-align:right;color:#ff007f">${money(stats.highest_price, currency)}</td></tr>
        ${
          flight.target_price
            ? `<tr><td style="padding:5px 0">Your target</td><td style="text-align:right;color:#fff">${money(flight.target_price, currency)}</td></tr>`
            : ""
        }
      </table>

      <p style="margin:22px 0 0">
        <a href="${escapeHtml(bookingUrl)}"
           style="display:inline-block;padding:13px 26px;border-radius:999px;background:#00f0ff;color:#04121c;font-weight:700;text-decoration:none">
          Open the flight
        </a>
      </p>
    </div>

    ${
      sandbox
        ? `<p style="margin:18px 0 0;padding:12px 16px;border-radius:12px;background:rgba(255,209,102,.12);border-left:3px solid #ffd166;color:#ffdda6;font-size:13px">
             Duffel is in test mode, so this fare is randomly generated sandbox data — useful for
             checking that alerts work, not for booking. Switch to a live Duffel token for real prices.
           </p>`
        : ""
    }
    <p style="margin:22px 0 0;font-size:12px;color:#7c8bab">
      You are receiving this because you track this route on SkyBuddy.
      Turn alerts off from your dashboard at any time.
    </p>
  </div>
</body></html>`;
}

/**
 * Send one price alert.
 *
 * @returns {Promise<string|null>} ISO timestamp when sent, null when skipped
 */
async function sendAlertEmail(payload) {
  const apiKey = process.env.RESEND_API_KEY;
  const from = process.env.ALERT_FROM_EMAIL || "SkyBuddy <onboarding@resend.dev>";
  if (!apiKey || !payload.to) return null;

  const subject =
    (payload.sandbox ? "[test data] " : "") +
    (SUBJECTS[payload.kind] || SUBJECTS.price_drop)(
      payload.flight,
      Number(payload.price).toFixed(2),
      payload.currency
    );

  const response = await fetch(RESEND_URL, {
    method: "POST",
    headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
    body: JSON.stringify({ from, to: [payload.to], subject, html: buildHtml(payload) }),
  });

  if (!response.ok) {
    console.error("Resend failed:", response.status, (await response.text()).slice(0, 300));
    return null;
  }
  return new Date().toISOString();
}

module.exports = { sendAlertEmail, buildHtml };
