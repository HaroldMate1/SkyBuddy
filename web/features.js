/* ============================================================
   SkyBuddy trip tools — the Python capabilities, in the browser
   - seat advisory (FlightAware → SeatMaps, plus cross-checks)
   - booking intents: prepare → confirm → playbook
   - wallet: cards and points earned on a fare
   - passengers: profiles the booking checklist fills from
   Pure client logic plus Supabase reads/writes under RLS.
   ============================================================ */

const LONG_HAUL_MINUTES = 480;

/* ---------------- seat advisory (port of scripts/seat_advisor.py) ---------------- */

const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
const slug = (value) => clean(value).toUpperCase().replace(/[^A-Z0-9]/g, "");

export function seatSources({ airline, aircraft, flightNumber, cabin }) {
  const query = (...parts) => parts.filter(Boolean).join(" ");
  const code = slug(flightNumber);

  return {
    primary: [
      {
        name: "FlightAware",
        role: "verify the aircraft",
        url: code
          ? `https://www.flightaware.com/live/flight/${code}`
          : `https://www.flightaware.com/live/findflight?query=${encodeURIComponent(clean(airline))}`,
        why: "Confirm the exact operating flight and aircraft type before trusting any seat map.",
      },
      {
        name: "SeatMaps",
        role: "the cabin map",
        url: `https://seatmaps.com/search/?q=${encodeURIComponent(query(airline, aircraft, cabin, "seat map"))}`,
        why: "Airline-specific layout: pitch, width, recline, lavatories, galleys and exit rows.",
      },
    ],
    crossChecks: [
      {
        name: "SeatGuru",
        url: "https://www.seatguru.com/",
        search: query(airline, aircraft, "seat map"),
        why: "Colour-coded good/bad seat notes per aircraft version.",
      },
      {
        name: "aeroLOPA",
        url: "https://www.aerolopa.com/",
        search: query(airline, aircraft),
        why: "High-accuracy cabin diagrams drawn from real layout data.",
      },
      {
        name: "ExpertFlyer",
        url: "https://www.expertflyer.com/",
        search: query(flightNumber || airline, aircraft, cabin),
        why: "Live seat availability and alerts when a better seat opens up.",
      },
      {
        name: "Flightradar24",
        url: code
          ? `https://www.flightradar24.com/data/flights/${code.toLowerCase()}`
          : "https://www.flightradar24.com/data/flights",
        search: flightNumber || airline,
        why: "Second source for the aircraft actually flying the route lately.",
      },
      {
        name: `${clean(airline) || "Airline"} seat selection`,
        url: "",
        search: `${clean(airline)} manage my booking seat selection`,
        why: "Where the seat is actually assigned — apply what the maps confirmed.",
      },
    ],
  };
}

export function seatTips(cabin) {
  const premium = /business|first/i.test(cabin || "");
  const tips = [
    "Verify the operating airline, aircraft subtype and cabin layout before choosing — the same model flies in different configurations.",
    "Avoid lavatory and galley clusters on overnight sectors unless quick aisle access matters more than quiet.",
    "Check exit-row trade-offs: more legroom often means narrower seats, fixed armrests, no under-seat bag and a colder cabin.",
    "Bulkhead rows can carry bassinet positions, fixed screens and no floor storage during taxi, take-off and landing.",
    "Window seats protect sleep; aisle seats are kinder for hydration and movement on flights over 8 hours.",
  ];
  tips.push(
    premium
      ? "In a premium cabin, confirm direct aisle access, seat direction and privacy doors for this exact sub-fleet."
      : "In economy, compare pitch, width, recline limits and missing-window rows before accepting the assigned seat."
  );
  return tips;
}

export function seatActions(cabin) {
  const actions = [
    { when: "At booking", action: "Check whether seat selection is included before paying for it separately." },
    { when: "At booking", action: "Apply the seat you validated on the cabin map, and confirm it shows on the itinerary." },
    { when: "Before departure", action: "Re-check a few days out: an aircraft swap silently reassigns seats." },
    { when: "Check-in (24–48h)", action: "Re-open the map — blocked exit rows and bulkheads are often released free." },
  ];
  if (/business|first/i.test(cabin || "")) {
    actions.push({ when: "At booking", action: "Verify aisle access and privacy doors for the exact cabin version." });
  }
  return actions;
}

export function seatAdvisory(flight) {
  const duration = Number(flight.duration_minutes || 0);
  const longHaul = duration >= LONG_HAUL_MINUTES;
  const context = {
    airline: flight.airline,
    aircraft: flight.aircraft,
    flightNumber: flight.flight_numbers || flight.flight_number,
    cabin: flight.cabin || "economy",
  };

  return {
    longHaul,
    duration,
    warning: flight.aircraft
      ? "Verify the airline's own seat map and operating configuration before choosing — the aircraft model alone is not enough."
      : "No aircraft type on this itinerary, so the cabin layout cannot be inferred. Confirm it on FlightAware first.",
    ...seatSources(context),
    tips: seatTips(context.cabin),
    actions: seatActions(context.cabin),
  };
}

/* ---------------- modal shell ---------------- */

let modalRoot = null;

function ensureModal() {
  if (modalRoot) return modalRoot;
  modalRoot = document.createElement("div");
  modalRoot.className = "sheet";
  modalRoot.hidden = true;
  modalRoot.addEventListener("click", (event) => {
    if (event.target === modalRoot || event.target.dataset.close !== undefined) closeSheet();
  });
  document.body.appendChild(modalRoot);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeSheet();
  });
  return modalRoot;
}

export function openSheet(title, bodyHtml, eyebrow) {
  const root = ensureModal();
  root.innerHTML = `
    <div class="sheet__panel glass" role="dialog" aria-modal="true">
      <button class="sheet__close" data-close aria-label="Close">✕</button>
      ${eyebrow ? `<p class="eyebrow">${eyebrow}</p>` : ""}
      <h3>${title}</h3>
      <div class="sheet__body">${bodyHtml}</div>
    </div>`;
  root.hidden = false;
  return root.querySelector(".sheet__panel");
}

export function closeSheet() {
  if (modalRoot) modalRoot.hidden = true;
}

/* ---------------- seat sheet ---------------- */

const esc = (value) => window.SkyBuddy.escapeHtml(value);

export function showSeatSheet(flight) {
  const advisory = seatAdvisory(flight);
  const hours = advisory.duration ? `${Math.floor(advisory.duration / 60)}h ${advisory.duration % 60}m` : "unknown";

  const primary = advisory.primary
    .map(
      (source, index) => `
      <li>
        <span class="n">${index + 1}</span>
        <div>
          <strong><a href="${esc(source.url)}" target="_blank" rel="noopener">${esc(source.name)}</a>
            <em>${esc(source.role)}</em></strong>
          <span>${esc(source.why)}</span>
        </div>
      </li>`
    )
    .join("");

  const crossChecks = advisory.crossChecks
    .map(
      (source) => `
      <tr>
        <td>${source.url ? `<a href="${esc(source.url)}" target="_blank" rel="noopener">${esc(source.name)}</a>` : esc(source.name)}</td>
        <td class="desc">${esc(source.why)}${
          source.search ? `<br><code>${esc(source.search)}</code>` : ""
        }</td>
      </tr>`
    )
    .join("");

  showSheetWithTabs({
    eyebrow: advisory.longHaul ? "Long-haul seat check" : "Seat check",
    title: `${esc(flight.airline || "Flight")} · ${esc(flight.aircraft || "aircraft not stated")}`,
    body: `
      <p class="sheet__lede">
        ${advisory.longHaul
          ? `This itinerary is ${hours}, so the seat matters. Confirm the aircraft first, then read the cabin map.`
          : `Short sector (${hours}). Worth a glance, not a research project.`}
      </p>
      <div class="note">${esc(advisory.warning)}</div>

      <h4>The workflow</h4>
      <ol class="steps">${primary}</ol>

      <h4>Cross-checks</h4>
      <div class="table-wrap"><table><tbody>${crossChecks}</tbody></table></div>

      <h4>Choosing the seat</h4>
      <ul class="bullets">${advisory.tips.map((tip) => `<li>${esc(tip)}</li>`).join("")}</ul>

      <h4>When to act</h4>
      <ul class="bullets">${advisory.actions
        .map((action) => `<li><strong>${esc(action.when)}</strong> — ${esc(action.action)}</li>`)
        .join("")}</ul>
    `,
  });
}

function showSheetWithTabs({ eyebrow, title, body }) {
  openSheet(title, body, eyebrow);
}

/* ---------------- points ---------------- */

export function estimatePoints(cards, fare) {
  return cards
    .map((card) => ({
      card: `${card.issuer} ${card.product}`,
      points: Math.round(Number(fare) * Number(card.points_per_unit || 1)),
      programme: card.programme || "",
    }))
    .sort((a, b) => b.points - a.points);
}

/* ---------------- booking intents (port of scripts/booking_agent.py) ---------------- */

const KNOWN_BOOKING_HOSTS = [
  "google.com",
  "avianca.com",
  "iberia.com",
  "klm.com",
  "airfrance.com",
  "airfrance.es",
  "kayak.com",
  "skyscanner.net",
  "skyscanner.com",
  "duffel.com",
];

/** Everything suspicious about this intent, stated before anyone confirms it. */
export function intentWarnings({ booking_url, passengers, price, max_price }) {
  const warnings = [];
  let host = "";
  try {
    const parsed = new URL(booking_url);
    host = parsed.hostname.toLowerCase();
    if (parsed.protocol !== "https:") warnings.push("The link is not HTTPS — never enter payment details on it.");
  } catch (error) {
    warnings.push("The booking link could not be parsed.");
  }
  if (host && !KNOWN_BOOKING_HOSTS.some((known) => host === known || host.endsWith("." + known))) {
    warnings.push(`Host “${host}” is not one of SkyBuddy's known booking sources — verify it manually.`);
  }
  if (!passengers || !passengers.length) {
    warnings.push("No traveller attached, so the agent cannot fill passenger details.");
  }
  if (max_price !== null && max_price !== undefined && Number(price) > Number(max_price)) {
    warnings.push(`Price ${price} is above the ceiling ${max_price}.`);
  }
  return warnings;
}

/** The ordered steps an agent (or you) follows on the booking link. */
export function buildPlaybook(intent, { passengers = [] } = {}) {
  const dates = intent.return_date
    ? `${intent.outbound_date} → ${intent.return_date}`
    : intent.outbound_date;

  const steps = [
    {
      step: "open_link",
      action: `Open the booking URL: ${intent.booking_url}`,
      check: "The page loads on the airline or aggregator site, not a redirect elsewhere.",
    },
    {
      step: "verify_itinerary",
      action: `Confirm the offer shows ${intent.origin} → ${intent.destination} on ${dates}, ${intent.cabin} class, ${intent.airline || "the expected carrier"}.`,
      check: "Abort if route, dates, cabin or carrier differ from this intent.",
    },
    {
      step: "verify_price",
      action: `Confirm the total is at or below ${intent.max_price ?? intent.price} ${intent.currency}, including taxes and baggage.`,
      check: "Abort and report back if the total is above the ceiling.",
    },
    {
      step: "fill_passengers",
      action: `Fill traveller details: ${passengers.length ? passengers.map((p) => `${p.given_name} ${p.family_name}`).join(", ") : "none attached"}`,
      check: "Names must match passports exactly; ask for anything missing.",
    },
  ];

  if (Number(intent.duration_minutes || 0) >= LONG_HAUL_MINUTES) {
    steps.push({
      step: "check_seats",
      action: "Long-haul: confirm the aircraft on FlightAware, then read the cabin map before choosing seats.",
      check: "Aircraft model alone is not enough — configurations vary by airline and sub-fleet.",
    });
  }

  steps.push({
    step: "select_extras",
    action: "Apply the agreed baggage and seat choices only; decline upsells that are not in this intent.",
    check: "Any added cost must keep the total under the ceiling.",
  });

  steps.push(
    intent.allow_payment
      ? {
          step: "pay",
          action: "Payment authority was granted for this intent — complete the purchase.",
          check: "Stop immediately if the final total differs from the verified one.",
        }
      : {
          step: "stop_before_payment",
          action: "STOP at the payment page and hand control back to the traveller.",
          check: "Never enter card details without explicit payment authority.",
        }
  );

  steps.push({
    step: "record_result",
    action: "After booking, record the confirmation code against this intent.",
    check: "That closes the audit trail.",
  });

  return {
    steps,
    abortConditions: [
      "Route, dates, cabin or airline do not match the intent.",
      `Total above ${intent.max_price ?? intent.price} ${intent.currency}.`,
      "The site asks for data no profile covers and nobody is available to answer.",
      "The page is not HTTPS, or the domain looks unrelated to the airline.",
    ],
  };
}
