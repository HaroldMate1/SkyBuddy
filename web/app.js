/* ============================================================
   SkyBuddy landing page + dashboard shell
   - airport/city autocomplete on the search fields
   - scanning search → skeleton shimmer → glass flight cards
   - price-trend sparklines with glowing hover tooltips
   - demo mode (signed out) with browser-local travellers
   - hooks so live.js can take over once someone signs in
   ============================================================ */
(function () {
  "use strict";

  var STORE = "skybuddy.users.v1";
  var REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* Overridable behaviour. live.js replaces these once a session exists. */
  var hooks = { search: null, track: null, renderTracked: null };
  /* other modules push (card, flight) => void here to add buttons */
  var cardDecorators = [];
  var mode = "demo";

  /* ---------------- helpers ---------------- */

  function pad(value) { return value < 10 ? "0" + value : String(value); }

  function money(value, currency) {
    if (value === null || value === undefined || value === "") return "—";
    var symbols = { EUR: "€", USD: "$", GBP: "£" };
    var symbol = symbols[currency || "EUR"] || (currency ? currency + " " : "€");
    return symbol + Math.round(Number(value)).toLocaleString("en-GB");
  }

  function euro(value) { return money(value, "EUR"); }

  function escapeHtml(value) {
    return String(value === null || value === undefined ? "" : value).replace(
      /[&<>"']/g,
      function (character) {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character];
      }
    );
  }

  function minutesToText(minutes) {
    if (!minutes && minutes !== 0) return "";
    return Math.floor(minutes / 60) + "h " + (minutes % 60) + "m";
  }

  function timeOf(iso) {
    if (!iso) return "--:--";
    var date = new Date(iso);
    if (isNaN(date)) return String(iso).slice(11, 16) || "--:--";
    return pad(date.getHours()) + ":" + pad(date.getMinutes());
  }

  /* ---------------- airport autocomplete ---------------- */

  var airports = null;
  var airportsPromise = null;

  function loadAirports() {
    if (airports) return Promise.resolve(airports);
    if (!airportsPromise) {
      airportsPromise = fetch("/data/airports.json")
        .then(function (response) { return response.ok ? response.json() : []; })
        .then(function (rows) {
          airports = rows.map(function (row) {
            return {
              code: row.c,
              name: row.n,
              city: row.m,
              country: row.k || row.y,
              rank: row.r,
              haystack: (row.c + " " + row.n + " " + row.m + " " + (row.k || "") + " " + row.y).toLowerCase()
            };
          });
          return airports;
        })
        .catch(function () { airports = []; return airports; });
    }
    return airportsPromise;
  }

  /** Rank matches so an exact IATA code and the big hubs come first. */
  function findAirports(query, limit) {
    var needle = query.trim().toLowerCase();
    if (!needle || !airports) return [];

    var scored = [];
    for (var i = 0; i < airports.length; i++) {
      var airport = airports[i];
      var score = -1;

      if (airport.code.toLowerCase() === needle) score = 0;
      else if (airport.city && airport.city.toLowerCase().indexOf(needle) === 0) score = 1;
      else if (airport.name.toLowerCase().indexOf(needle) === 0) score = 2;
      else if (airport.code.toLowerCase().indexOf(needle) === 0) score = 3;
      else if (airport.haystack.indexOf(needle) !== -1) score = 4;

      if (score >= 0) scored.push({ airport: airport, score: score * 10 + airport.rank });
    }

    scored.sort(function (a, b) { return a.score - b.score; });
    return scored.slice(0, limit || 7).map(function (entry) { return entry.airport; });
  }

  function attachAutocomplete(input) {
    var field = input.closest(".field");
    if (!field) return;

    field.classList.add("field--combo");
    var list = document.createElement("div");
    list.className = "combo";
    list.setAttribute("role", "listbox");
    field.appendChild(list);

    var caption = document.createElement("span");
    caption.className = "field__caption";
    input.insertAdjacentElement("afterend", caption);

    var active = -1;
    var matches = [];

    function describe(airport) {
      var place = [airport.city, airport.country].filter(Boolean).join(", ");
      return airport.name + (place ? " · " + place : "");
    }

    function close() {
      list.classList.remove("is-open");
      active = -1;
    }

    function choose(airport) {
      input.value = airport.code;
      input.dataset.iata = airport.code;
      caption.textContent = describe(airport);
      close();
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function render() {
      list.innerHTML = "";
      if (!matches.length) return close();

      matches.forEach(function (airport, index) {
        var option = document.createElement("button");
        option.type = "button";
        option.className = "combo__item" + (index === active ? " is-active" : "");
        option.setAttribute("role", "option");
        option.innerHTML =
          '<span class="combo__code">' + escapeHtml(airport.code) + "</span>" +
          '<span class="combo__text"><strong>' + escapeHtml(airport.city || airport.name) + "</strong>" +
          "<small>" + escapeHtml(describe(airport)) + "</small></span>";
        option.addEventListener("mousedown", function (event) {
          event.preventDefault();
          choose(airport);
        });
        list.appendChild(option);
      });
      list.classList.add("is-open");
    }

    function update() {
      loadAirports().then(function () {
        matches = findAirports(input.value, 7);
        active = matches.length ? 0 : -1;
        render();
      });
    }

    input.setAttribute("autocomplete", "off");
    input.removeAttribute("maxlength");
    input.addEventListener("focus", update);
    input.addEventListener("input", function () {
      delete input.dataset.iata;
      caption.textContent = "";
      update();
    });
    input.addEventListener("blur", function () { window.setTimeout(close, 120); });
    input.addEventListener("keydown", function (event) {
      if (!list.classList.contains("is-open")) return;
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        active = (active + (event.key === "ArrowDown" ? 1 : -1) + matches.length) % matches.length;
        render();
      } else if (event.key === "Enter" && matches[active]) {
        event.preventDefault();
        choose(matches[active]);
      } else if (event.key === "Escape") {
        close();
      }
    });

    // resolve whatever is already in the field (the BIO/BOG defaults)
    loadAirports().then(function () {
      var seeded = findAirports(input.value, 1)[0];
      if (seeded && seeded.code.toLowerCase() === input.value.trim().toLowerCase()) {
        input.dataset.iata = seeded.code;
        caption.textContent = describe(seeded);
      }
    });
  }

  /* ---------------- demo fare data ---------------- */

  var AIRLINES = [
    { code: "IB", name: "Iberia", flight: "IB 6585", color: "#ff4d6d" },
    { code: "AV", name: "Avianca", flight: "AV 121", color: "#ff2e63" },
    { code: "KL", name: "KLM", flight: "KL 741", color: "#00b0ff" },
    { code: "AF", name: "Air France", flight: "AF 428", color: "#4d9fff" }
  ];

  var VERDICTS = {
    buy_now: { label: "Buy now", cls: "v-buy" },
    good: { label: "Good", cls: "v-good" },
    fair: { label: "Fair", cls: "v-wait" },
    wait: { label: "Wait", cls: "v-wait" },
    high: { label: "High", cls: "v-high" }
  };

  function seeded(seed) {
    var value = 0;
    for (var i = 0; i < seed.length; i++) value = (value * 31 + seed.charCodeAt(i)) >>> 0;
    return function () {
      value = (value * 1664525 + 1013904223) >>> 0;
      return value / 4294967296;
    };
  }

  function verdictFor(price, history) {
    if (!history || !history.length) return null;
    var ordered = history.slice().sort(function (a, b) { return a - b; });
    var at = function (fraction) { return ordered[Math.round(fraction * (ordered.length - 1))]; };
    if (price <= at(0.1)) return "buy_now";
    if (price <= at(0.25)) return "good";
    if (price <= at(0.5)) return "fair";
    if (price <= at(0.75)) return "wait";
    return "high";
  }

  function buildDemoFlights(origin, destination, outbound) {
    var rand = seeded(origin + destination + outbound);
    var base = 560 + Math.floor(rand() * 260);
    var POSITION = [0.06, 0.2, 0.45, 0.82];

    return AIRLINES.map(function (airline, index) {
      var centre = base + index * 60;
      var history = [];
      var point = centre;
      for (var week = 0; week < 26; week++) {
        point += (rand() - 0.5) * 70;
        history.push(Math.round(Math.max(centre * 0.72, Math.min(centre * 1.35, point))));
      }

      var ranked = history.slice().sort(function (a, b) { return a - b; });
      var price = ranked[Math.round(POSITION[index] * (ranked.length - 1))];
      history[history.length - 1] = price;

      var depart = 7 + index * 3;
      var duration = 570 + Math.floor(rand() * 300);

      return {
        id: airline.code + "-" + origin + destination + "-" + outbound,
        airline: airline.name,
        airline_code: airline.code,
        color: airline.color,
        flight_number: airline.flight,
        origin: origin,
        destination: destination,
        outbound: outbound,
        price: price,
        currency: "EUR",
        history: history,
        departure: pad(depart) + ":" + (index % 2 ? "45" : "10"),
        arrival: pad((depart + Math.floor(duration / 60)) % 24) + ":" + (index % 2 ? "20" : "55"),
        duration: minutesToText(duration),
        stops: index === 0 ? 0 : (rand() > 0.55 ? 1 : 2)
      };
    });
  }

  /* ---------------- browser-local travellers (demo mode) ---------------- */

  var state = loadState();

  function loadState() {
    try {
      var raw = JSON.parse(localStorage.getItem(STORE) || "null");
      if (raw && raw.users && raw.users.length) return raw;
    } catch (error) { /* fall through to defaults */ }
    return {
      active: "harold",
      users: [
        { id: "harold", name: "Harold", initials: "H", tracked: [] },
        { id: "ana", name: "Ana", initials: "A", tracked: [] }
      ]
    };
  }

  function saveState() {
    try { localStorage.setItem(STORE, JSON.stringify(state)); } catch (error) { /* private mode */ }
  }

  function activeUser() {
    return state.users.filter(function (user) { return user.id === state.active; })[0] || state.users[0];
  }

  var usersRow = document.getElementById("users");
  var usersList = document.getElementById("users-list");
  var usersHint = document.getElementById("users-hint");
  var addButton = document.getElementById("user-add");

  function renderUsers() {
    if (mode !== "demo") return;
    usersList.innerHTML = "";
    state.users.forEach(function (user) {
      var chip = document.createElement("button");
      chip.type = "button";
      chip.className = "user-chip" + (user.id === state.active ? " is-active" : "");
      chip.innerHTML =
        '<span class="user-chip__av">' + escapeHtml(user.initials) + "</span>" +
        "<span>" + escapeHtml(user.name) + "</span>" +
        '<span class="user-chip__n">' + user.tracked.length + "</span>";
      chip.addEventListener("click", function () {
        state.active = user.id;
        saveState();
        renderUsers();
        renderTracked();
      });
      usersList.appendChild(chip);
    });
    usersHint.textContent = activeUser().name + "'s preview — sign in to track routes for real";
  }

  addButton.addEventListener("click", function () {
    var name = (window.prompt("Traveller name") || "").trim();
    if (!name) return;
    var id = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || ("user" + state.users.length);
    if (!state.users.some(function (user) { return user.id === id; })) {
      state.users.push({ id: id, name: name, initials: name.charAt(0).toUpperCase(), tracked: [] });
    }
    state.active = id;
    saveState();
    renderUsers();
    renderTracked();
  });

  /* ---------------- tracked list (demo mode) ---------------- */

  var trackedBox = document.getElementById("tracked");
  var trackedList = document.getElementById("tracked-list");
  var trackedTitle = document.getElementById("tracked-title");
  var trackedCount = document.getElementById("tracked-count");

  function renderTracked() {
    if (hooks.renderTracked) return hooks.renderTracked();

    var user = activeUser();
    trackedTitle.textContent = user.name + "'s tracked flights";
    trackedCount.textContent = user.tracked.length + " watched";
    trackedBox.hidden = user.tracked.length === 0;
    trackedList.innerHTML = "";

    user.tracked.forEach(function (item) {
      var row = document.createElement("div");
      row.className = "track-row glass";
      row.innerHTML =
        '<span class="track-row__route">' + escapeHtml(item.origin) + " → " + escapeHtml(item.destination) + "</span>" +
        '<span class="track-row__meta">' + escapeHtml(item.airline) + " · " + escapeHtml(item.outbound) + "</span>" +
        '<span class="track-row__range">low <b>' + euro(item.low || item.price) + "</b> · median <b>" +
          euro(item.median || item.price) + "</b> · high <b>" + euro(item.high || item.price) + "</b></span>" +
        '<span class="track-row__price display">' + euro(item.price) + "</span>" +
        '<span class="price__verdict ' + item.cls + '">' + escapeHtml(item.label) + "</span>";

      var drop = document.createElement("button");
      drop.type = "button";
      drop.className = "btn btn--sm btn--ghost";
      drop.textContent = "Simulate drop";
      drop.addEventListener("click", function () { simulateDrop(row, item); });
      row.appendChild(drop);

      var remove = document.createElement("button");
      remove.type = "button";
      remove.className = "track-row__x";
      remove.setAttribute("aria-label", "Stop tracking");
      remove.textContent = "✕";
      remove.addEventListener("click", function () {
        user.tracked = user.tracked.filter(function (entry) { return entry.id !== item.id; });
        saveState();
        renderUsers();
        renderTracked();
      });
      row.appendChild(remove);

      trackedList.appendChild(row);
    });
  }

  function simulateDrop(row, item) {
    var priceEl = row.querySelector(".track-row__price");
    item.price = Math.round(item.price * 0.88);
    item.cls = "v-buy";
    item.label = "Buy now";
    saveState();

    priceEl.textContent = euro(item.price);
    priceEl.classList.add("is-drop");

    var badge = row.querySelector(".price__verdict");
    badge.className = "price__verdict v-buy";
    badge.textContent = "Buy now";

    var existing = row.querySelector(".drop-flag");
    if (existing) existing.remove();

    var flag = document.createElement("span");
    flag.className = "drop-flag drop-row";
    flag.innerHTML = '<span class="check">✓</span><small>−12% · alert sent</small>';
    row.insertBefore(flag, row.querySelector(".btn"));

    window.setTimeout(function () { priceEl.classList.remove("is-drop"); }, 1400);
  }

  /* ---------------- sparkline ---------------- */

  var tip = document.getElementById("tip");

  function sparkline(points, options) {
    var settings = options || {};
    var width = 170;
    var height = 54;
    var min = Math.min.apply(null, points);
    var max = Math.max.apply(null, points);
    var span = Math.max(max - min, 1);
    var stepX = width / Math.max(points.length - 1, 1);

    var coords = points.map(function (value, index) {
      return {
        x: index * stepX,
        y: height - ((value - min) / span) * (height - 8) - 4,
        value: value,
        label: settings.labels ? settings.labels[index] : (points.length - index) + " checks ago"
      };
    });

    var line = coords
      .map(function (point, index) { return (index ? "L" : "M") + point.x.toFixed(1) + " " + point.y.toFixed(1); })
      .join(" ");

    var ns = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(ns, "svg");
    svg.setAttribute("class", "spark");
    svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    svg.setAttribute("preserveAspectRatio", "none");

    var defs = document.createElementNS(ns, "defs");
    defs.innerHTML =
      '<linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0%" stop-color="#00f0ff" stop-opacity="0.32"/>' +
      '<stop offset="100%" stop-color="#00f0ff" stop-opacity="0"/></linearGradient>';
    svg.appendChild(defs);

    var grid = document.createElementNS(ns, "g");
    grid.setAttribute("class", "spark__grid");
    [0.25, 0.5, 0.75].forEach(function (fraction) {
      var gridLine = document.createElementNS(ns, "line");
      gridLine.setAttribute("x1", 0);
      gridLine.setAttribute("x2", width);
      gridLine.setAttribute("y1", height * fraction);
      gridLine.setAttribute("y2", height * fraction);
      grid.appendChild(gridLine);
    });
    svg.appendChild(grid);

    var area = document.createElementNS(ns, "path");
    area.setAttribute("class", "spark__area");
    area.setAttribute("d", line + " L" + width + " " + height + " L0 " + height + " Z");
    svg.appendChild(area);

    var path = document.createElementNS(ns, "path");
    path.setAttribute("class", "spark__line");
    path.setAttribute("d", line);
    svg.appendChild(path);

    coords.forEach(function (point) {
      var dot = document.createElementNS(ns, "circle");
      dot.setAttribute("class", "spark__dot" + (point.value === min ? " spark__dot--low" : ""));
      dot.setAttribute("cx", point.x.toFixed(1));
      dot.setAttribute("cy", point.y.toFixed(1));
      dot.addEventListener("mouseenter", function (event) {
        tip.innerHTML = money(point.value, settings.currency) + "<small>" + escapeHtml(point.label) + "</small>";
        tip.classList.add("is-on");
        moveTip(event);
      });
      dot.addEventListener("mousemove", moveTip);
      dot.addEventListener("mouseleave", function () { tip.classList.remove("is-on"); });
      svg.appendChild(dot);
    });

    return svg;
  }

  function moveTip(event) {
    tip.style.left = event.clientX + "px";
    tip.style.top = event.clientY + "px";
  }

  /* ---------------- flight cards ---------------- */

  var results = document.getElementById("results");

  function renderFlights(flights) {
    results.innerHTML = "";
    if (!flights || !flights.length) {
      return showMessage("No fares came back for that route and date.");
    }

    flights.forEach(function (flight, index) {
      var history = flight.history || null;
      var verdict = flight.verdict || verdictFor(flight.price, history);
      var badge = VERDICTS[verdict];
      var ordered = history ? history.slice().sort(function (a, b) { return a - b; }) : null;

      var card = document.createElement("article");
      card.className = "flight glass";
      card.style.animationDelay = (index * 0.09) + "s";
      card.innerHTML =
        '<div class="flight__airline">' +
          '<span class="flight__logo" style="background:' + (flight.color || "#4d9fff") + '">' +
            escapeHtml(flight.airline_code || (flight.airline || "??").slice(0, 2).toUpperCase()) +
          "</span>" +
          "<span><span class='flight__carrier'>" + escapeHtml(flight.airline) + "</span>" +
          "<span class='flight__fno'>" + escapeHtml(flight.flight_number || "") + "</span></span>" +
        "</div>" +
        '<div class="flight__route">' +
          '<div class="leg"><div class="leg__time">' + escapeHtml(flight.departure) + "</div>" +
          '<div class="leg__code">' + escapeHtml(flight.origin) + "</div></div>" +
          '<div class="path"><div class="path__line"></div><div class="path__meta">' +
            escapeHtml(flight.duration || "") +
            (flight.stops === undefined || flight.stops === null
              ? ""
              : " · " + (flight.stops ? flight.stops + " stop" + (flight.stops > 1 ? "s" : "") : "non-stop")) +
          "</div></div>" +
          '<div class="leg"><div class="leg__time">' + escapeHtml(flight.arrival) + "</div>" +
          '<div class="leg__code">' + escapeHtml(flight.destination) + "</div></div>" +
        "</div>" +
        '<div class="flight__trend"><span class="trend__label">' +
          (history ? "price history" : "no history yet") +
        "</span></div>" +
        '<div class="flight__price">' +
          '<span class="price">' + money(flight.price, flight.currency) + "</span>" +
          (badge ? '<span class="price__verdict ' + badge.cls + '">' + badge.label + "</span>" : "") +
        "</div>";

      var trend = card.querySelector(".flight__trend");
      if (history) {
        trend.appendChild(sparkline(history, { currency: flight.currency }));
        var stats = document.createElement("div");
        stats.className = "trend__stats";
        stats.innerHTML =
          '<span class="ts ts--low">low <b>' + money(ordered[0], flight.currency) + "</b></span>" +
          '<span class="ts">med <b>' + money(ordered[Math.floor(ordered.length / 2)], flight.currency) + "</b></span>" +
          '<span class="ts ts--high">high <b>' + money(ordered[ordered.length - 1], flight.currency) + "</b></span>";
        trend.appendChild(stats);
      } else {
        var note = document.createElement("p");
        note.className = "trend__empty";
        note.textContent = "Track it and SkyBuddy starts recording the price history.";
        trend.appendChild(note);
      }

      var track = document.createElement("button");
      track.type = "button";
      track.className = "btn btn--sm btn--primary";
      track.textContent = "Track price";
      track.addEventListener("click", function () {
        if (hooks.track) return hooks.track(flight, track);
        trackInDemo(flight, track, history);
      });
      card.querySelector(".flight__price").appendChild(track);
      cardDecorators.forEach(function (decorate) { decorate(card, flight); });

      results.appendChild(card);
    });
  }

  function trackInDemo(flight, button, history) {
    var user = activeUser();
    if (user.tracked.some(function (entry) { return entry.id === flight.id; })) {
      button.textContent = "Already tracked";
      return;
    }
    var ordered = (history || [flight.price]).slice().sort(function (a, b) { return a - b; });
    var verdict = VERDICTS[flight.verdict || verdictFor(flight.price, history) || "fair"];

    user.tracked.push({
      id: flight.id,
      origin: flight.origin,
      destination: flight.destination,
      outbound: flight.outbound,
      airline: flight.airline,
      price: flight.price,
      low: ordered[0],
      median: ordered[Math.floor(ordered.length / 2)],
      high: ordered[ordered.length - 1],
      cls: verdict.cls,
      label: verdict.label
    });
    saveState();
    renderUsers();
    renderTracked();

    button.innerHTML = '<span class="check">✓</span> Tracking';
    window.setTimeout(function () { button.textContent = "Tracked"; }, 1200);
  }

  function renderSkeletons(count) {
    results.innerHTML = "";
    for (var index = 0; index < count; index++) {
      var block = document.createElement("div");
      block.className = "skeleton glass";
      results.appendChild(block);
    }
  }

  function showMessage(text, kind) {
    results.innerHTML = "";
    var box = document.createElement("p");
    box.className = "results__msg glass" + (kind === "error" ? " is-error" : "");
    box.textContent = text;
    results.appendChild(box);
  }

  /* ---------------- search ---------------- */

  var dash = document.getElementById("dash");
  var form = document.getElementById("search-form");

  function readSearch() {
    var origin = document.getElementById("f-origin");
    var destination = document.getElementById("f-dest");
    return {
      origin: (origin.dataset.iata || origin.value || "BIO").toUpperCase().slice(0, 3),
      destination: (destination.dataset.iata || destination.value || "BOG").toUpperCase().slice(0, 3),
      outbound_date: document.getElementById("f-out").value || "2026-12-04",
      return_date: document.getElementById("f-ret").value || null
    };
  }

  function scan() {
    if (REDUCED) return;
    dash.classList.add("is-scanning");
    window.setTimeout(function () { dash.classList.remove("is-scanning"); }, 900);
  }

  function runSearch() {
    var query = readSearch();

    if (hooks.search) {
      scan();
      renderSkeletons(4);
      hooks.search(query).then(renderFlights).catch(function (error) {
        showMessage(error.message || "The search failed.", "error");
      });
      return;
    }

    var flights = buildDemoFlights(query.origin, query.destination, query.outbound_date);
    if (REDUCED) return renderFlights(flights);

    scan();
    renderSkeletons(4);
    window.setTimeout(function () { renderFlights(flights); }, 1250);
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    runSearch();
  });

  /* ---------------- quick-start tabs ---------------- */

  var tabs = Array.prototype.slice.call(document.querySelectorAll(".tab"));
  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      tabs.forEach(function (other) {
        other.setAttribute("aria-selected", String(other === tab));
        var panel = document.getElementById(other.dataset.panel);
        if (panel) panel.hidden = other !== tab;
      });
    });
  });

  /* ---------------- background: drifting clouds ---------------- */

  var CLOUD_TINTS = [
    { top: "#c8b0ff", bottom: "#8f5cff", glow: "rgba(155,107,255,0.55)" },
    { top: "#c9fbff", bottom: "#00d6f0", glow: "rgba(0,240,255,0.5)" },
    { top: "#ffc2e0", bottom: "#ff2f92", glow: "rgba(255,0,127,0.45)" },
    { top: "#e6ffb8", bottom: "#a5f02a", glow: "rgba(180,255,57,0.4)" },
    { top: "#dbe9ff", bottom: "#7ea8e8", glow: "rgba(120,180,255,0.45)" }
  ];

  var CLOUD_LAYOUT = [
    { tint: 0, width: 210, top: "13%", left: "3%", delay: 0.0, small: false },
    { tint: 1, width: 150, top: "58%", left: "88%", delay: 0.7, small: false },
    { tint: 2, width: 96, top: "31%", left: "83%", delay: 1.2, small: true },
    { tint: 4, width: 120, top: "74%", left: "9%", delay: 1.6, small: true },
    { tint: 3, width: 84, top: "8%", left: "72%", delay: 2.1, small: true }
  ];

  function buildClouds() {
    var host = document.getElementById("clouds");
    if (!host) return;

    CLOUD_LAYOUT.forEach(function (spec, index) {
      var tint = CLOUD_TINTS[spec.tint];
      var wrapper = document.createElement("div");
      wrapper.className = "cloud" + (spec.small ? " cloud--small" : "");
      wrapper.style.width = spec.width + "px";
      wrapper.style.top = spec.top;
      wrapper.style.left = spec.left;
      wrapper.style.setProperty("--cloud-opacity", spec.small ? 0.55 : 0.72);
      wrapper.style.animationDelay = spec.delay + "s, " + (spec.delay + 1.2) + "s, " + (spec.delay + 0.4) + "s";
      wrapper.style.animationDuration = "1.4s, " + (6 + index * 0.7) + "s, " + (30 + index * 5) + "s";
      wrapper.style.filter = "drop-shadow(0 18px 34px " + tint.glow + ")";
      wrapper.innerHTML =
        '<svg viewBox="0 0 64 48" xmlns="http://www.w3.org/2000/svg">' +
          "<defs>" +
            '<linearGradient id="cloud-' + index + '" gradientUnits="userSpaceOnUse" x1="0" y1="4" x2="0" y2="46">' +
              '<stop offset="0%" stop-color="' + tint.top + '"/>' +
              '<stop offset="100%" stop-color="' + tint.bottom + '"/>' +
            "</linearGradient>" +
          "</defs>" +
          '<g fill="url(#cloud-' + index + ')">' +
            '<rect x="7" y="26" width="50" height="18" rx="9"/>' +
            '<circle cx="23" cy="26" r="13"/>' +
            '<circle cx="43" cy="29" r="11"/>' +
            '<circle cx="33" cy="19" r="13"/>' +
          "</g>" +
        "</svg>";
      host.appendChild(wrapper);
    });
  }

  /* ---------------- a paper plane looping across the sky ---------------- */

  function flightPath(eastbound) {
    var width = window.innerWidth;
    var height = window.innerHeight;
    var entry = 90 + Math.random() * Math.max(120, height * 0.4);
    var loopY = entry - 60 - Math.random() * 60;
    var radius = 54 + Math.random() * 46;
    var loopX = width * (0.38 + Math.random() * 0.2);
    var exit = entry - 40 - Math.random() * 90;

    var from = eastbound ? -160 : width + 160;
    var to = eastbound ? width + 160 : -160;
    var sweep = eastbound ? 1 : 0;
    var control1 = eastbound ? width * 0.14 : width * 0.86;
    var control2 = eastbound ? width * 0.3 : width * 0.7;
    var control3 = eastbound ? width * 0.72 : width * 0.28;
    var control4 = eastbound ? width * 0.88 : width * 0.12;

    return (
      "M " + from + " " + entry +
      " C " + control1 + " " + (entry - 70) + ", " + control2 + " " + (entry + 50) + ", " + loopX + " " + loopY +
      " a " + radius + " " + (radius * 0.62) + " 0 1 " + sweep + " " + (eastbound ? 2 : -2) + " 1" +
      " C " + control3 + " " + (loopY - 70) + ", " + control4 + " " + (entry + 30) + ", " + to + " " + exit
    );
  }

  function flyPlane() {
    var host = document.getElementById("clouds");
    if (!host || REDUCED) return;

    var eastbound = Math.random() > 0.4;
    var duration = 16 + Math.random() * 6;

    var plane = document.createElement("div");
    plane.className = "plane";
    plane.style.offsetPath = 'path("' + flightPath(eastbound) + '")';
    plane.style.animationDuration = duration + "s";
    plane.innerHTML =
      '<div class="plane__body">' +
        '<span class="pf pf--wing-top"></span>' +
        '<span class="pf pf--wing-bottom"></span>' +
        '<span class="pf pf--keel"></span>' +
      "</div>";

    host.appendChild(plane);
    window.setTimeout(function () { plane.remove(); }, duration * 1000 + 500);
  }

  function scheduleFlights() {
    if (REDUCED) return;
    window.setTimeout(flyPlane, 2500);
    window.setInterval(function () {
      if (Math.random() > 0.3) flyPlane();
    }, 14000);
  }

  /* ---------------- live repository stats ---------------- */

  function short(value) {
    return value >= 1000 ? (value / 1000).toFixed(1).replace(/\.0$/, "") + "k" : String(value);
  }

  fetch("https://api.github.com/repos/HaroldMate1/SkyBuddy")
    .then(function (response) { return response.ok ? response.json() : null; })
    .then(function (data) {
      if (!data) return;
      var stars = document.getElementById("stat-stars");
      var forks = document.getElementById("stat-forks");
      if (stars) stars.textContent = "★ " + short(data.stargazers_count) + " stars";
      if (forks) forks.textContent = "⑂ " + short(data.forks_count) + " forks";
    })
    .catch(function () { /* pills keep their placeholder text */ });

  /* ---------------- public surface for live.js ---------------- */

  window.SkyBuddy = {
    hooks: hooks,
    cardDecorators: cardDecorators,
    money: money,
    escapeHtml: escapeHtml,
    minutesToText: minutesToText,
    timeOf: timeOf,
    verdictFor: verdictFor,
    VERDICTS: VERDICTS,
    sparkline: sparkline,
    renderFlights: renderFlights,
    renderSkeletons: renderSkeletons,
    showMessage: showMessage,
    readSearch: readSearch,
    runSearch: runSearch,
    scan: scan,
    elements: {
      dash: dash,
      results: results,
      usersRow: usersRow,
      trackedBox: trackedBox,
      trackedList: trackedList,
      trackedTitle: trackedTitle,
      trackedCount: trackedCount
    },
    setMode: function (next) {
      mode = next;
      document.body.dataset.mode = next;
      if (usersRow) usersRow.hidden = next !== "demo";
      if (next === "demo") {
        renderUsers();
        renderTracked();
      }
    }
  };

  /* ---------------- boot ---------------- */

  buildClouds();
  scheduleFlights();
  attachAutocomplete(document.getElementById("f-origin"));
  attachAutocomplete(document.getElementById("f-dest"));
  renderUsers();
  renderTracked();
  renderFlights(buildDemoFlights("BIO", "BOG", "2026-12-04"));
})();
