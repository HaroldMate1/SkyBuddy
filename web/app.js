// SkyBuddy landing page — tabs + live GitHub stats
(function () {
  "use strict";

  // ---- quick-start tabs ----
  var tabs = Array.prototype.slice.call(document.querySelectorAll(".tab"));
  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      tabs.forEach(function (t) {
        t.setAttribute("aria-selected", String(t === tab));
        var panel = document.getElementById(t.dataset.panel);
        if (panel) panel.hidden = t !== tab;
      });
    });
  });

  // ---- live repository stats ----
  var fmt = function (n) {
    return n >= 1000 ? (n / 1000).toFixed(1).replace(/\.0$/, "") + "k" : String(n);
  };

  fetch("https://api.github.com/repos/HaroldMate1/SkyBuddy")
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (data) {
      if (!data) return;
      var stars = document.getElementById("stat-stars");
      var forks = document.getElementById("stat-forks");
      if (stars) stars.textContent = "★ " + fmt(data.stargazers_count) + " stars";
      if (forks) forks.textContent = "⑂ " + fmt(data.forks_count) + " forks";
    })
    .catch(function () { /* badges keep their placeholder text */ });
})();
