/* ============================================================
   SkyBuddy live mode
   - magic-link sign-in through Supabase Auth
   - tracked flights stored per account, with real price history
   - live fare search through /api/search (Duffel, server-side)
   - "check now" through /api/check, nightly checks by Vercel Cron
   ============================================================ */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";
import {
  showSeatSheet,
  openSheet,
  closeSheet,
  buildPlaybook,
  intentWarnings,
  estimatePoints,
} from "/features.js";

const UI = window.SkyBuddy;
const authButton = document.getElementById("auth-btn");
const modal = document.getElementById("auth-modal");
const modalForm = document.getElementById("auth-form");
const modalEmail = document.getElementById("auth-email");
const modalNote = document.getElementById("auth-note");
const modalClose = document.getElementById("auth-close");
const account = document.getElementById("account");

let supabase = null;
let session = null;
let profile = null;
let features = {};

/* ---------------- boot ---------------- */

const config = await fetch("/api/config")
  .then((response) => (response.ok ? response.json() : null))
  .catch(() => null);

if (config) features = config.features || {};

if (config && config.supabaseUrl && config.supabaseAnonKey) {
  supabase = createClient(config.supabaseUrl, config.supabaseAnonKey, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
  });

  const { data } = await supabase.auth.getSession();
  await applySession(data.session);

  supabase.auth.onAuthStateChange((_event, next) => { applySession(next); });
} else {
  authButton.textContent = "Sign in";
  authButton.title = "Sign-in is not configured yet — add the Supabase keys in Vercel.";
  authButton.addEventListener("click", () => {
    openModal("Sign-in is not configured yet. Add SUPABASE_URL and SUPABASE_ANON_KEY in Vercel, then reload.");
  });
}

/* ---------------- auth UI ---------------- */

function openModal(message) {
  modal.hidden = false;
  modalNote.textContent = message || "";
  modalNote.className = "auth__note";
  window.setTimeout(() => modalEmail.focus(), 60);
}

function closeModal() {
  modal.hidden = true;
}

modalClose.addEventListener("click", closeModal);
modal.addEventListener("click", (event) => { if (event.target === modal) closeModal(); });
document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeModal(); });

authButton.addEventListener("click", () => {
  if (!supabase) return;
  if (session) return signOut();
  openModal("");
});

modalForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!supabase) return;

  const email = modalEmail.value.trim();
  if (!email) return;

  modalNote.textContent = "Sending your link…";
  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: { emailRedirectTo: window.location.origin },
  });

  if (error) {
    modalNote.textContent = error.message;
    modalNote.className = "auth__note is-error";
    return;
  }
  modalNote.textContent = `Check ${email} — the sign-in link is on its way.`;
  modalNote.className = "auth__note is-ok";
  modalForm.reset();
});

async function signOut() {
  await supabase.auth.signOut();
}

/* ---------------- session handling ---------------- */

async function applySession(next) {
  session = next || null;

  if (!session) {
    profile = null;
    UI.hooks.search = null;
    UI.hooks.track = null;
    UI.hooks.renderTracked = null;
    UI.setMode("demo");
    account.hidden = true;
    authButton.textContent = "Sign in";
    return;
  }

  closeModal();
  authButton.textContent = "Sign out";
  UI.setMode("live");

  profile = await loadProfile();
  renderAccount();

  UI.hooks.search = liveSearch;
  UI.hooks.track = trackFlight;
  UI.hooks.renderTracked = renderTracked;

  await renderTracked();
  UI.showMessage("Search a route to see live fares for your account.");
}

async function loadProfile() {
  const { data } = await supabase
    .from("profiles")
    .select("id,email,display_name,home_airport,currency,email_alerts")
    .eq("id", session.user.id)
    .maybeSingle();

  return data || { id: session.user.id, email: session.user.email, email_alerts: true };
}

function renderAccount() {
  const name = profile.display_name || (profile.email || "").split("@")[0];
  account.hidden = false;
  account.innerHTML = `
    <span class="user-chip is-active">
      <span class="user-chip__av">${UI.escapeHtml((name || "?").charAt(0).toUpperCase())}</span>
      <span>${UI.escapeHtml(name)}</span>
    </span>
    <span class="account__email">${UI.escapeHtml(profile.email || "")}</span>
    <label class="account__toggle">
      <input type="checkbox" id="alerts-toggle" ${profile.email_alerts === false ? "" : "checked"}>
      Email me price alerts
    </label>
    ${features.liveSearch ? "" : '<span class="account__warn">Live search is not configured (DUFFEL_API_KEY)</span>'}
    ${
      features.sandbox
        ? '<span class="account__warn" title="Live search runs through a Duffel test token, which invents inventory on every request. Tracked routes are priced from Google Flights by the collector, and those are real.">Search results are Duffel sandbox data — tracked prices are real</span>'
        : ""
    }
    <span class="account__tools">
      <button class="btn btn--sm btn--ghost" id="tool-wallet" type="button">Wallet</button>
      <button class="btn btn--sm btn--ghost" id="tool-passengers" type="button">Travellers</button>
      <button class="btn btn--sm btn--ghost" id="tool-bookings" type="button">Bookings</button>
      ${features.collector ? '<button class="btn btn--sm btn--ghost" id="tool-collect" type="button">Refresh prices</button>' : ""}
    </span>
  `;

  document.getElementById("tool-wallet").addEventListener("click", showWallet);
  document.getElementById("tool-passengers").addEventListener("click", showPassengers);
  document.getElementById("tool-bookings").addEventListener("click", showBookings);
  const collectButton = document.getElementById("tool-collect");
  if (collectButton) {
    collectButton.addEventListener("click", async () => {
      collectButton.disabled = true;
      collectButton.textContent = "Queued…";
      try {
        const result = await authedFetch("/api/collect", {});
        UI.showMessage(result.message);
      } catch (error) {
        UI.showMessage(error.message, "error");
      }
      window.setTimeout(() => {
        collectButton.disabled = false;
        collectButton.textContent = "Refresh prices";
      }, 4000);
    });
  }

  document.getElementById("alerts-toggle").addEventListener("change", async (event) => {
    const enabled = event.target.checked;
    await supabase.from("profiles").update({ email_alerts: enabled }).eq("id", profile.id);
    profile.email_alerts = enabled;
  });
}

/* ---------------- live search ---------------- */

async function authedFetch(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.access_token}`,
    },
    body: JSON.stringify(body),
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

async function liveSearch(query) {
  if (!features.liveSearch) {
    throw new Error("Live search is not configured yet — add DUFFEL_API_KEY in Vercel.");
  }

  const payload = await authedFetch("/api/search", {
    origin: query.origin,
    destination: query.destination,
    outbound_date: query.outbound_date,
    return_date: query.return_date,
    passengers: 1,
    cabin: "economy",
  });

  // While live search runs on a Duffel test token its prices are invented, so
  // comparing them against the real collected history would produce a verdict
  // that means nothing — better to show no verdict than a false one.
  if (features.sandbox) {
    return payload.offers.map((offer) => toCard(offer, query, null));
  }

  // If this route is already tracked, show its recorded history on the cards.
  const { data: tracked } = await supabase
    .from("tracked_flights")
    .select("id")
    .eq("origin", query.origin)
    .eq("destination", query.destination)
    .eq("outbound_date", query.outbound_date)
    .maybeSingle();

  let history = null;
  if (tracked) history = await loadHistory(tracked.id);

  return payload.offers.map((offer) =>
    toCard(offer, query, history && history.prices.length > 1 ? history.prices : null)
  );
}

/** Shape one offer the way the card renderer expects. */
function toCard(offer, query, history) {
  return {
    id: offer.offer_id,
    airline: offer.airline,
    airline_code: offer.airline_code,
    flight_number: offer.flight_number,
    aircraft: offer.aircraft,
    duration_minutes: offer.duration_minutes,
    origin: offer.origin,
    destination: offer.destination,
    outbound: query.outbound_date,
    return_date: query.return_date,
    price: offer.price,
    currency: offer.currency,
    departure: UI.timeOf(offer.departure_time),
    arrival: UI.timeOf(offer.arrival_time),
    duration: UI.minutesToText(offer.duration_minutes),
    stops: offer.stops,
    booking_url: offer.booking_url,
    history,
  };
}

async function loadHistory(flightId) {
  const { data } = await supabase
    .from("price_observations")
    .select("price,observed_at")
    .eq("tracked_flight_id", flightId)
    .order("observed_at", { ascending: true })
    .limit(120);

  const rows = data || [];
  return {
    prices: rows.map((row) => Number(row.price)),
    labels: rows.map((row) => new Date(row.observed_at).toLocaleDateString()),
  };
}

/* ---------------- tracking ---------------- */

async function trackFlight(flight, button) {
  const query = UI.readSearch();
  const targetRaw = window.prompt(
    `Alert me when ${query.origin} → ${query.destination} drops to (leave empty for "any new low"):`,
    ""
  );
  if (targetRaw === null) return;
  const target = targetRaw.trim() ? Number(targetRaw.replace(/[^\d.]/g, "")) : null;

  button.disabled = true;
  button.textContent = "Saving…";

  const { data, error } = await supabase
    .from("tracked_flights")
    .insert({
      user_id: session.user.id,
      origin: query.origin,
      destination: query.destination,
      outbound_date: query.outbound_date,
      return_date: query.return_date,
      currency: flight.currency || "EUR",
      target_price: Number.isFinite(target) ? target : null,
      label: `${query.origin} → ${query.destination}`,
      last_price: flight.price,
      last_airline: flight.airline,
      last_booking_url: flight.booking_url,
    })
    .select()
    .single();

  if (error) {
    button.disabled = false;
    button.textContent = "Track price";
    UI.showMessage(error.message, "error");
    return;
  }

  button.innerHTML = '<span class="check">✓</span> Tracking';
  await renderTracked();

  // First real data point straight away, so the history starts now.
  try {
    await authedFetch("/api/check", { tracked_flight_id: data.id });
    await renderTracked();
  } catch (checkError) {
    console.warn("first check failed:", checkError.message);
  }
}

async function renderTracked() {
  const { trackedBox, trackedList, trackedTitle, trackedCount } = UI.elements;

  const { data } = await supabase
    .from("tracked_flights")
    .select("*")
    .eq("active", true)
    .order("created_at", { ascending: false });

  const flights = data || [];
  const name = profile.display_name || (profile.email || "").split("@")[0];
  trackedTitle.textContent = `${name}'s tracked flights`;
  trackedCount.textContent = `${flights.length} watched`;
  trackedBox.hidden = flights.length === 0;
  trackedList.innerHTML = "";

  for (const flight of flights) {
    const row = document.createElement("div");
    row.className = "track-row glass";
    const dates = flight.return_date
      ? `${flight.outbound_date} → ${flight.return_date}`
      : flight.outbound_date;
    const checked = flight.last_checked_at
      ? new Date(flight.last_checked_at).toLocaleString()
      : "not checked yet";

    row.innerHTML = `
      <span class="track-row__route">${UI.escapeHtml(flight.origin)} → ${UI.escapeHtml(flight.destination)}</span>
      <span class="track-row__meta">${UI.escapeHtml(dates)} · checked ${UI.escapeHtml(checked)}</span>
      <span class="track-row__range">
        low <b>${UI.money(flight.lowest_price, flight.currency)}</b> ·
        median <b>${UI.money(flight.median_price, flight.currency)}</b> ·
        high <b>${UI.money(flight.highest_price, flight.currency)}</b>
        ${flight.target_price ? `· target <b>${UI.money(flight.target_price, flight.currency)}</b>` : ""}
      </span>
      <span class="track-row__price display">${UI.money(flight.last_price, flight.currency)}</span>
    `;

    const history = await loadHistory(flight.id);
    if (history.prices.length > 1) {
      const chart = document.createElement("span");
      chart.className = "track-row__spark";
      chart.appendChild(
        UI.sparkline(history.prices, { currency: flight.currency, labels: history.labels })
      );
      row.appendChild(chart);
    }

    // The newest observation carries the aircraft and flight numbers, which is
    // what the seat advisory needs.
    const { data: detail } = await supabase
      .from("price_observations")
      .select("airline,aircraft,flight_numbers,duration_minutes")
      .eq("tracked_flight_id", flight.id)
      .order("observed_at", { ascending: false })
      .limit(1)
      .maybeSingle();

    const seats = document.createElement("button");
    seats.type = "button";
    seats.className = "btn btn--sm btn--ghost";
    seats.textContent = "Seats";
    seats.addEventListener("click", () =>
      showSeatSheet({
        airline: (detail && detail.airline) || flight.last_airline,
        aircraft: detail && detail.aircraft,
        flight_numbers: detail && detail.flight_numbers,
        duration_minutes: (detail && detail.duration_minutes) || 0,
        cabin: flight.cabin,
      })
    );
    row.appendChild(seats);

    const check = document.createElement("button");
    check.type = "button";
    check.className = "btn btn--sm btn--ghost";
    check.textContent = "Check now";
    check.addEventListener("click", async () => {
      check.disabled = true;
      check.textContent = "Checking…";
      try {
        const result = await authedFetch("/api/check", { tracked_flight_id: flight.id });
        await renderTracked();
        if (result.status === "too_soon") {
          UI.showMessage(
            `Just checked — SkyBuddy waits ${result.retry_in_seconds}s between manual checks so the history stays meaningful.`
          );
        } else if (result.status === "alerted") {
          UI.showMessage(`Alert sent for ${flight.origin} → ${flight.destination}.`);
        }
      } catch (error) {
        check.disabled = false;
        check.textContent = "Check now";
        UI.showMessage(error.message, "error");
      }
    });
    row.appendChild(check);

    const stop = document.createElement("button");
    stop.type = "button";
    stop.className = "track-row__x";
    stop.setAttribute("aria-label", "Stop tracking");
    stop.textContent = "✕";
    stop.addEventListener("click", async () => {
      await supabase.from("tracked_flights").delete().eq("id", flight.id);
      await renderTracked();
    });
    row.appendChild(stop);

    trackedList.appendChild(row);
  }
}


/* ---------------- trip tools ---------------- */

/**
 * Add the seat and booking buttons to a rendered fare card.
 *
 * The seat advisory is plain client-side logic — no account needed — so it is
 * offered to everyone. Booking needs somewhere to store the intent, so it only
 * appears once someone is signed in.
 */
function decorateCard(card, flight) {
  const actions = document.createElement("span");
  actions.className = "flight__tools";

  const seats = document.createElement("button");
  seats.type = "button";
  seats.className = "btn btn--sm btn--ghost";
  seats.textContent = "Seats";
  seats.addEventListener("click", () => showSeatSheet(flight));
  actions.appendChild(seats);

  if (session) {
    const book = document.createElement("button");
    book.type = "button";
    book.className = "btn btn--sm btn--ghost";
    book.textContent = "Book";
    book.addEventListener("click", () => prepareBooking(flight));
    actions.appendChild(book);
  }

  card.querySelector(".flight__price").appendChild(actions);
}

UI.cardDecorators.push(decorateCard);
// re-render whatever is on screen so the buttons appear on first load too
if (UI.elements.results.querySelector(".flight")) UI.runSearch();

/* ---------------- booking intents ---------------- */

async function prepareBooking(flight) {
  const query = UI.readSearch();
  const travellers = await listPassengers();
  const ceilingRaw = window.prompt(
    `Hard price ceiling for this booking (${flight.currency || "EUR"}):`,
    String(Math.round(Number(flight.price) * 1.02))
  );
  if (ceilingRaw === null) return;
  const ceiling = Number(String(ceilingRaw).replace(/[^\d.]/g, "")) || Number(flight.price);

  const draft = {
    user_id: session.user.id,
    booking_url: flight.booking_url || "https://www.google.com/travel/flights",
    airline: flight.airline,
    flight_numbers: flight.flight_number || "",
    aircraft: flight.aircraft || "",
    duration_minutes: flight.duration_minutes || 0,
    origin: query.origin,
    destination: query.destination,
    outbound_date: query.outbound_date,
    return_date: query.return_date,
    cabin: "economy",
    price: flight.price,
    currency: flight.currency || "EUR",
    max_price: ceiling,
    passengers: travellers.map((person) => person.name),
    notes: "Created from the SkyBuddy dashboard.",
  };
  draft.warnings = intentWarnings(draft);

  const { data, error } = await supabase.from("booking_intents").insert(draft).select().single();
  if (error) return UI.showMessage(error.message, "error");

  showIntentSheet(data, travellers);
}

function showIntentSheet(intent, travellers) {
  const playbook = buildPlaybook(intent, { passengers: travellers });
  const money = (value) => UI.money(value, intent.currency);

  const steps = playbook.steps
    .map(
      (step, index) => `
      <li><span class="n">${index + 1}</span>
        <div><strong>${UI.escapeHtml(step.step.replace(/_/g, " "))}</strong>
        <span>${UI.escapeHtml(step.action)}</span>
        <span class="muted">Check: ${UI.escapeHtml(step.check)}</span></div>
      </li>`
    )
    .join("");

  const warnings = (intent.warnings || [])
    .map((warning) => `<li>${UI.escapeHtml(warning)}</li>`)
    .join("");

  const panel = openSheet(
    `${UI.escapeHtml(intent.origin)} → ${UI.escapeHtml(intent.destination)} · ${money(intent.price)}`,
    `
      <p class="sheet__lede">
        Status <strong>${UI.escapeHtml(intent.status.replace(/_/g, " "))}</strong> ·
        ceiling ${money(intent.max_price)} ·
        ${intent.passengers && intent.passengers.length ? UI.escapeHtml(intent.passengers.join(", ")) : "no traveller attached"}
      </p>
      ${warnings ? `<div class="note"><ul class="bullets">${warnings}</ul></div>` : ""}
      <h4>Agent playbook</h4>
      <ol class="steps">${steps}</ol>
      <h4>Abort if</h4>
      <ul class="bullets">${playbook.abortConditions.map((item) => `<li>${UI.escapeHtml(item)}</li>`).join("")}</ul>
      <div class="sheet__actions">
        ${
          intent.status === "awaiting_confirmation"
            ? '<button class="btn btn--primary" id="intent-confirm" type="button">Confirm this booking</button>'
            : `<a class="btn btn--primary" href="${UI.escapeHtml(intent.booking_url)}" target="_blank" rel="noopener">Open the flight</a>`
        }
        <button class="btn btn--ghost" id="intent-cancel" type="button">Cancel intent</button>
      </div>
    `,
    "Booking intent"
  );

  const confirm = panel.querySelector("#intent-confirm");
  if (confirm) {
    confirm.addEventListener("click", async () => {
      const { data } = await supabase
        .from("booking_intents")
        .update({
          status: "ready_to_execute",
          approved_by: profile.email,
          approved_at: new Date().toISOString(),
          history: [...(intent.history || []), { at: new Date().toISOString(), event: "confirmed" }],
        })
        .eq("id", intent.id)
        .select()
        .single();
      showIntentSheet(data || { ...intent, status: "ready_to_execute" }, travellers);
    });
  }

  panel.querySelector("#intent-cancel").addEventListener("click", async () => {
    await supabase.from("booking_intents").update({ status: "cancelled" }).eq("id", intent.id);
    closeSheet();
  });
}

async function showBookings() {
  const { data } = await supabase
    .from("booking_intents")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(20);

  const intents = data || [];
  const rows = intents
    .map(
      (intent) => `
      <tr>
        <td><code>${UI.escapeHtml(intent.id.slice(0, 8))}</code></td>
        <td>${UI.escapeHtml(intent.origin)} → ${UI.escapeHtml(intent.destination)}<br>
            <small>${UI.escapeHtml(intent.outbound_date)}</small></td>
        <td>${UI.money(intent.price, intent.currency)}</td>
        <td><span class="price__verdict ${
          intent.status === "booked" ? "v-buy" : intent.status === "cancelled" ? "v-high" : "v-good"
        }">${UI.escapeHtml(intent.status.replace(/_/g, " "))}</span></td>
      </tr>`
    )
    .join("");

  openSheet(
    "Booking intents",
    intents.length
      ? `<div class="table-wrap"><table><thead><tr><th>id</th><th>route</th><th>price</th><th>status</th></tr></thead><tbody>${rows}</tbody></table></div>
         <p class="sheet__lede">Nothing is ever purchased automatically: an intent only becomes actionable once you confirm it.</p>`
      : '<p class="sheet__lede">No booking intents yet. Search a route and press <strong>Book</strong> on a fare.</p>',
    "Audit trail"
  );
}

/* ---------------- wallet ---------------- */

async function showWallet() {
  const { data } = await supabase.from("loyalty_cards").select("*").order("created_at");
  const cards = data || [];

  const { data: tracked } = await supabase
    .from("tracked_flights")
    .select("last_price,currency")
    .not("last_price", "is", null)
    .order("last_price", { ascending: false })
    .limit(1);
  const fare = tracked && tracked[0] ? Number(tracked[0].last_price) : 0;
  const currency = tracked && tracked[0] ? tracked[0].currency : "EUR";

  const estimate = fare ? estimatePoints(cards, fare) : [];
  const rows = cards
    .map(
      (card) => `
      <tr>
        <td><strong>${UI.escapeHtml(card.issuer)} ${UI.escapeHtml(card.product)}</strong><br>
            <small>${UI.escapeHtml(card.programme || "")} ${card.balance ? `· ${card.balance.toLocaleString()} pts` : ""}</small></td>
        <td>${Number(card.points_per_unit).toFixed(2)} / ${UI.escapeHtml(currency)}</td>
        <td><button class="btn btn--sm btn--ghost" data-remove-card="${card.id}">Remove</button></td>
      </tr>`
    )
    .join("");

  const panel = openSheet(
    "Wallet",
    `
      ${
        cards.length
          ? `<div class="table-wrap"><table><thead><tr><th>card</th><th>earn rate</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`
          : '<p class="sheet__lede">No cards yet. Add one to see what a fare would earn.</p>'
      }
      ${
        estimate.length
          ? `<h4>On your most expensive tracked fare (${UI.money(fare, currency)})</h4>
             <ul class="bullets">${estimate
               .map((row) => `<li><strong>${row.points.toLocaleString()} pts</strong> — ${UI.escapeHtml(row.card)}</li>`)
               .join("")}</ul>`
          : ""
      }
      <h4>Add a card</h4>
      <form class="sheet__form" id="card-form">
        <input name="issuer" placeholder="Issuer (American Express)" required>
        <input name="product" placeholder="Product (Platinum)" required>
        <input name="points_per_unit" type="number" step="0.1" min="0" placeholder="Points per ${UI.escapeHtml(currency)}" value="1.5" required>
        <input name="programme" placeholder="Programme (Membership Rewards)">
        <button class="btn btn--primary" type="submit">Add card</button>
      </form>
    `,
    "Loyalty and points"
  );

  panel.querySelectorAll("[data-remove-card]").forEach((button) => {
    button.addEventListener("click", async () => {
      await supabase.from("loyalty_cards").delete().eq("id", button.dataset.removeCard);
      showWallet();
    });
  });

  panel.querySelector("#card-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    const issuer = form.get("issuer");
    const product = form.get("product");
    const { error } = await supabase.from("loyalty_cards").insert({
      user_id: session.user.id,
      card_id: `${issuer}-${product}`.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
      issuer,
      product,
      points_per_unit: Number(form.get("points_per_unit")) || 1,
      programme: form.get("programme") || null,
    });
    if (error) return UI.showMessage(error.message, "error");
    showWallet();
  });
}

/* ---------------- passengers ---------------- */

async function listPassengers() {
  const { data } = await supabase.from("passengers").select("*").order("created_at");
  return data || [];
}

async function showPassengers() {
  const travellers = await listPassengers();
  const rows = travellers
    .map(
      (person) => `
      <tr>
        <td><strong>${UI.escapeHtml(person.given_name)} ${UI.escapeHtml(person.family_name)}</strong><br>
            <small>${UI.escapeHtml(person.name)} ${person.born_on ? `· ${UI.escapeHtml(person.born_on)}` : ""}</small></td>
        <td>${UI.escapeHtml(person.passport || "no passport on file")}</td>
        <td><button class="btn btn--sm btn--ghost" data-remove-passenger="${person.id}">Remove</button></td>
      </tr>`
    )
    .join("");

  const panel = openSheet(
    "Travellers",
    `
      ${
        travellers.length
          ? `<div class="table-wrap"><table><thead><tr><th>traveller</th><th>passport</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`
          : '<p class="sheet__lede">No traveller profiles yet. A booking intent needs at least one.</p>'
      }
      <h4>Add a traveller</h4>
      <form class="sheet__form" id="passenger-form">
        <input name="given_name" placeholder="Given name" required>
        <input name="family_name" placeholder="Family name" required>
        <input name="born_on" type="date" placeholder="Date of birth">
        <input name="passport" placeholder="Passport number">
        <input name="nationality" placeholder="Nationality (CO)">
        <button class="btn btn--primary" type="submit">Add traveller</button>
      </form>
      <p class="sheet__lede">Stored under your account only, and used to fill the booking checklist.</p>
    `,
    "Passenger profiles"
  );

  panel.querySelectorAll("[data-remove-passenger]").forEach((button) => {
    button.addEventListener("click", async () => {
      await supabase.from("passengers").delete().eq("id", button.dataset.removePassenger);
      showPassengers();
    });
  });

  panel.querySelector("#passenger-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    const given = form.get("given_name");
    const family = form.get("family_name");
    const { error } = await supabase.from("passengers").insert({
      user_id: session.user.id,
      name: `${given}-${family}`.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
      given_name: given,
      family_name: family,
      born_on: form.get("born_on") || null,
      passport: form.get("passport") || null,
      nationality: form.get("nationality") || null,
    });
    if (error) return UI.showMessage(error.message, "error");
    showPassengers();
  });
}
