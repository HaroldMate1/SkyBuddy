/* ============================================================
   SkyBuddy live mode
   - magic-link sign-in through Supabase Auth
   - tracked flights stored per account, with real price history
   - live fare search through /api/search (Duffel, server-side)
   - "check now" through /api/check, nightly checks by Vercel Cron
   ============================================================ */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";

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
        ? '<span class="account__warn" title="Duffel test tokens invent new inventory on every request, so prices change between identical searches.">Duffel test mode — prices are randomised sandbox data</span>'
        : ""
    }
  `;

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

  return payload.offers.map((offer) => ({
    id: offer.offer_id,
    airline: offer.airline,
    airline_code: offer.airline_code,
    flight_number: offer.flight_number,
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
    history: history && history.prices.length > 1 ? history.prices : null,
  }));
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
