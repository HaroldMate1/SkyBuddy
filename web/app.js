/* ============================================================
   SkyBuddy landing page
   - traveller (multi-user) workspaces, stored per browser
   - scanning search → skeleton shimmer → glass flight cards
   - price-trend sparklines with glowing hover tooltips
   - price-drop success animation
   ============================================================ */
(function () {
  "use strict";

  var STORE = "skybuddy.users.v1";
  var REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------------- sample fare data (demo only) ---------------- */

  var AIRLINES = [
    { code: "IB", name: "Iberia", flight: "IB 6585", color: "#ff4d6d" },
    { code: "AV", name: "Avianca", flight: "AV 121", color: "#ff2e63" },
    { code: "KL", name: "KLM", flight: "KL 741", color: "#00b0ff" },
    { code: "AF", name: "Air France", flight: "AF 428", color: "#4d9fff" },
    { code: "LH", name: "Lufthansa", flight: "LH 512", color: "#ffb703" }
  ];

  var VERDICTS = [
    { key: "buy_now", label: "Buy now", cls: "v-buy" },
    { key: "good", label: "Good", cls: "v-good" },
    { key: "fair", label: "Fair", cls: "v-wait" },
    { key: "wait", label: "Wait", cls: "v-wait" },
    { key: "high", label: "High", cls: "v-high" }
  ];

  /* deterministic pseudo-random so a route always renders the same way */
  function seeded(seed) {
    var value = 0;
    for (var i = 0; i < seed.length; i++) value = (value * 31 + seed.charCodeAt(i)) >>> 0;
    return function () {
      value = (value * 1664525 + 1013904223) >>> 0;
      return value / 4294967296;
    };
  }

  function buildFlights(origin, destination, outbound) {
    var rand = seeded(origin + destination + outbound);
    var base = 560 + Math.floor(rand() * 260);

    /* one flight per position in the price distribution, so the demo shows the
       whole verdict scale instead of four identical "buy now" badges */
    var POSITION = [0.06, 0.2, 0.45, 0.82];

    return AIRLINES.slice(0, 4).map(function (airline, index) {
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

      var sorted = history.slice().sort(function (a, b) { return a - b; });
      var median = sorted[Math.floor(sorted.length / 2)];
      var p10 = sorted[Math.floor(sorted.length * 0.1)];
      var p25 = sorted[Math.floor(sorted.length * 0.25)];
      var p75 = sorted[Math.floor(sorted.length * 0.75)];

      var verdict = VERDICTS[4];
      if (price <= p10) verdict = VERDICTS[0];
      else if (price <= p25) verdict = VERDICTS[1];
      else if (price <= median) verdict = VERDICTS[2];
      else if (price <= p75) verdict = VERDICTS[3];

      var depart = 7 + index * 3;
      var duration = 570 + Math.floor(rand() * 300);
      var stops = index === 0 ? 0 : (rand() > 0.55 ? 1 : 2);

      return {
        id: airline.code + "-" + origin + destination + "-" + outbound,
        airline: airline,
        origin: origin,
        destination: destination,
        outbound: outbound,
        price: price,
        median: median,
        low: sorted[0],
        high: sorted[sorted.length - 1],
        history: history,
        verdict: verdict,
        departure: pad(depart) + ":" + (index % 2 ? "45" : "10"),
        arrival: pad((depart + Math.floor(duration / 60)) % 24) + ":" + (index % 2 ? "20" : "55"),
        duration: Math.floor(duration / 60) + "h " + (duration % 60) + "m",
        stops: stops
      };
    });
  }

  function pad(value) { return value < 10 ? "0" + value : String(value); }
  function euro(value) { return "€" + Math.round(value).toLocaleString("en-GB"); }

  /* ---------------- traveller workspaces ---------------- */

  var state = load();

  function load() {
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

  function save() {
    try { localStorage.setItem(STORE, JSON.stringify(state)); } catch (error) { /* private mode */ }
  }

  function activeUser() {
    return state.users.filter(function (user) { return user.id === state.active; })[0] || state.users[0];
  }

  var usersList = document.getElementById("users-list");
  var usersHint = document.getElementById("users-hint");
  var addButton = document.getElementById("user-add");

  function renderUsers() {
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
        save();
        renderUsers();
        renderTracked();
      });
      usersList.appendChild(chip);
    });
    usersHint.textContent = activeUser().name + "'s workspace — routes, alerts and bookings stay separate";
  }

  addButton.addEventListener("click", function () {
    var name = (window.prompt("Traveller name") || "").trim();
    if (!name) return;
    var id = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || ("user" + state.users.length);
    if (state.users.some(function (user) { return user.id === id; })) {
      state.active = id;
    } else {
      state.users.push({
        id: id,
        name: name,
        initials: name.trim().charAt(0).toUpperCase(),
        tracked: []
      });
      state.active = id;
    }
    save();
    renderUsers();
    renderTracked();
  });

  /* ---------------- tracked flights ---------------- */

  var trackedBox = document.getElementById("tracked");
  var trackedList = document.getElementById("tracked-list");
  var trackedTitle = document.getElementById("tracked-title");
  var trackedCount = document.getElementById("tracked-count");

  function renderTracked() {
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
        '<span class="track-row__price display" data-price="' + item.price + '">' + euro(item.price) + "</span>" +
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
        save();
        renderUsers();
        renderTracked();
      });
      row.appendChild(remove);

      trackedList.appendChild(row);
    });
  }

  function simulateDrop(row, item) {
    var priceEl = row.querySelector(".track-row__price");
    var newPrice = Math.round(item.price * 0.88);
    item.price = newPrice;
    item.cls = "v-buy";
    item.label = "Buy now";
    save();

    priceEl.textContent = euro(newPrice);
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

  function sparkline(flight) {
    var width = 170, height = 54, points = flight.history;
    var min = Math.min.apply(null, points), max = Math.max.apply(null, points);
    var span = Math.max(max - min, 1);
    var stepX = width / (points.length - 1);

    var coords = points.map(function (value, index) {
      return {
        x: index * stepX,
        y: height - ((value - min) / span) * (height - 8) - 4,
        value: value,
        week: points.length - index
      };
    });

    var line = coords.map(function (point, index) {
      return (index ? "L" : "M") + point.x.toFixed(1) + " " + point.y.toFixed(1);
    }).join(" ");

    var svgNS = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("class", "spark");
    svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    svg.setAttribute("preserveAspectRatio", "none");

    var defs = document.createElementNS(svgNS, "defs");
    defs.innerHTML =
      '<linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0%" stop-color="#00f0ff" stop-opacity="0.32"/>' +
      '<stop offset="100%" stop-color="#00f0ff" stop-opacity="0"/></linearGradient>';
    svg.appendChild(defs);

    var grid = document.createElementNS(svgNS, "g");
    grid.setAttribute("class", "spark__grid");
    [0.25, 0.5, 0.75].forEach(function (fraction) {
      var gridLine = document.createElementNS(svgNS, "line");
      gridLine.setAttribute("x1", 0);
      gridLine.setAttribute("x2", width);
      gridLine.setAttribute("y1", height * fraction);
      gridLine.setAttribute("y2", height * fraction);
      grid.appendChild(gridLine);
    });
    svg.appendChild(grid);

    var area = document.createElementNS(svgNS, "path");
    area.setAttribute("class", "spark__area");
    area.setAttribute("d", line + " L" + width + " " + height + " L0 " + height + " Z");
    svg.appendChild(area);

    var path = document.createElementNS(svgNS, "path");
    path.setAttribute("class", "spark__line");
    path.setAttribute("d", line);
    svg.appendChild(path);

    coords.forEach(function (point) {
      var dot = document.createElementNS(svgNS, "circle");
      dot.setAttribute("class", "spark__dot" + (point.value === flight.low ? " spark__dot--low" : ""));
      dot.setAttribute("cx", point.x.toFixed(1));
      dot.setAttribute("cy", point.y.toFixed(1));
      dot.addEventListener("mouseenter", function (event) {
        tip.innerHTML = euro(point.value) + "<small>" + point.week + " weeks ago</small>";
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

  /* ---------------- results ---------------- */

  var results = document.getElementById("results");

  function renderFlights(flights) {
    results.innerHTML = "";
    flights.forEach(function (flight, index) {
      var card = document.createElement("article");
      card.className = "flight glass";
      card.style.animationDelay = (index * 0.09) + "s";

      card.innerHTML =
        '<div class="flight__airline">' +
          '<span class="flight__logo" style="background:' + flight.airline.color + '; color:#08131f">' +
            flight.airline.code +
          "</span>" +
          "<span><span class='flight__carrier'>" + escapeHtml(flight.airline.name) + "</span>" +
          "<span class='flight__fno'>" + escapeHtml(flight.airline.flight) + "</span></span>" +
        "</div>" +
        '<div class="flight__route">' +
          '<div class="leg"><div class="leg__time">' + flight.departure + '</div><div class="leg__code">' + escapeHtml(flight.origin) + "</div></div>" +
          '<div class="path"><div class="path__line"></div><div class="path__meta">' +
            flight.duration + " · " + (flight.stops ? flight.stops + " stop" + (flight.stops > 1 ? "s" : "") : "non-stop") +
          "</div></div>" +
          '<div class="leg"><div class="leg__time">' + flight.arrival + '</div><div class="leg__code">' + escapeHtml(flight.destination) + "</div></div>" +
        "</div>" +
        '<div class="flight__trend"><span class="trend__label">26-week history</span></div>' +
        '<div class="flight__price">' +
          '<span class="price">' + euro(flight.price) + "</span>" +
          '<span class="price__verdict ' + flight.verdict.cls + '">' + flight.verdict.label + "</span>" +
        "</div>";

      var trend = card.querySelector(".flight__trend");
      trend.appendChild(sparkline(flight));

      var stats = document.createElement("div");
      stats.className = "trend__stats";
      stats.innerHTML =
        '<span class="ts ts--low">low <b>' + euro(flight.low) + "</b></span>" +
        '<span class="ts">med <b>' + euro(flight.median) + "</b></span>" +
        '<span class="ts ts--high">high <b>' + euro(flight.high) + "</b></span>";
      trend.appendChild(stats);

      var track = document.createElement("button");
      track.type = "button";
      track.className = "btn btn--sm btn--primary";
      track.textContent = "Track price";
      track.addEventListener("click", function () {
        var user = activeUser();
        if (user.tracked.some(function (entry) { return entry.id === flight.id; })) {
          track.textContent = "Already tracked";
          return;
        }
        user.tracked.push({
          id: flight.id,
          origin: flight.origin,
          destination: flight.destination,
          outbound: flight.outbound,
          airline: flight.airline.name,
          price: flight.price,
          low: flight.low,
          median: flight.median,
          high: flight.high,
          cls: flight.verdict.cls,
          label: flight.verdict.label
        });
        save();
        renderUsers();
        renderTracked();

        track.innerHTML = '<span class="check">✓</span> Tracking';
        window.setTimeout(function () { track.textContent = "Tracked"; }, 1200);
      });
      card.querySelector(".flight__price").appendChild(track);

      results.appendChild(card);
    });
  }

  function renderSkeletons(count) {
    results.innerHTML = "";
    for (var index = 0; index < count; index++) {
      var block = document.createElement("div");
      block.className = "skeleton glass";
      results.appendChild(block);
    }
  }

  /* ---------------- search ---------------- */

  var dash = document.getElementById("dash");
  var form = document.getElementById("search-form");

  function runSearch() {
    var origin = (document.getElementById("f-origin").value || "BIO").toUpperCase().slice(0, 3);
    var destination = (document.getElementById("f-dest").value || "BOG").toUpperCase().slice(0, 3);
    var outbound = document.getElementById("f-out").value || "2026-12-04";
    var flights = buildFlights(origin, destination, outbound);

    if (REDUCED) {
      renderFlights(flights);
      return;
    }

    dash.classList.add("is-scanning");
    window.setTimeout(function () { dash.classList.remove("is-scanning"); }, 900);
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


  /* ---------------- background: drifting clouds with changing faces ---------------- */

  var CLOUD_TINTS = [
    { id: "amethyst", top: "#c8b0ff", bottom: "#8f5cff", glow: "rgba(155,107,255,0.55)" },
    { id: "cyan", top: "#c9fbff", bottom: "#00d6f0", glow: "rgba(0,240,255,0.5)" },
    { id: "magenta", top: "#ffc2e0", bottom: "#ff2f92", glow: "rgba(255,0,127,0.45)" },
    { id: "lime", top: "#e6ffb8", bottom: "#a5f02a", glow: "rgba(180,255,57,0.4)" },
    { id: "ice", top: "#dbe9ff", bottom: "#7ea8e8", glow: "rgba(120,180,255,0.45)" }
  ];

  /* placement is fixed so the layout never jumps between reloads */
  var CLOUD_LAYOUT = [
    { tint: 0, width: 210, top: "13%", left: "3%", delay: 0.0, small: false },
    { tint: 1, width: 150, top: "58%", left: "88%", delay: 0.7, small: false },
    { tint: 2, width: 96, top: "31%", left: "83%", delay: 1.2, small: true },
    { tint: 4, width: 120, top: "74%", left: "9%", delay: 1.6, small: true },
    { tint: 3, width: 84, top: "8%", left: "72%", delay: 2.1, small: true }
  ];

  function buildClouds() {
    var host = document.getElementById("clouds");
    if (!host) return [];

    return CLOUD_LAYOUT.map(function (spec, index) {
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
      return wrapper;
    });
  }

  /* ---------------- a paper plane looping across the sky ---------------- */

  /* The flight path is a real curve: it climbs, throws an elliptical loop
     mid-screen, then descends out the far side. `offset-path` moves the plane
     along it and `offset-rotate: auto` keeps the nose pointing exactly where
     it is going, while the body rolls for a three-dimensional feel. */
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

    /* real geometry, not a flat icon: two wings folded along the fuselage
       plus a keel, so rolling the body actually shows depth */
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

  /* ---------------- boot ---------------- */

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, function (character) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character];
    });
  }

  buildClouds();
  scheduleFlights();

  renderUsers();
  renderTracked();
  renderFlights(buildFlights("BIO", "BOG", "2026-12-04"));
})();
