/**
 * Pill Track — caregiver dashboard
 */
(function () {
  "use strict";

  var RING_C = 2 * Math.PI * 52; // ~327

  function esc(s) {
    var d = document.createElement("div");
    d.textContent = s || "";
    return d.innerHTML;
  }

  function setRing(pct) {
    var fill = document.getElementById("ringFill");
    var text = document.getElementById("ringPct");
    if (!fill) return;
    var offset = RING_C - (RING_C * pct / 100);
    fill.style.strokeDashoffset = offset;
    text.textContent = pct + "%";
  }

  function markedClass(dose) {
    if (!dose.taken) return "mark-miss";
    if (dose.on_time === true) return "mark-ok";
    if (dose.on_time === false) return "mark-late";
    return "mark-unknown";
  }

  function markedText(dose) {
    if (!dose.taken) return "Not taken";
    if (dose.period === "flexible" && dose.when_telugu) {
      var t = dose.when_telugu;
      if (dose.taken_at_display) t += " · " + dose.taken_at_display;
      return t;
    }
    if (dose.taken_at_display) {
      return dose.taken_at_display + (dose.minutes_delta_label ? " · " + dose.minutes_delta_label : "");
    }
    return "Taken (time not recorded)";
  }

  function dayBadge(day) {
    if (day.all_taken) return '<span class="pt-day-badge badge-ok">All done</span>';
    if (day.taken === 0) return '<span class="pt-day-badge badge-bad">None taken</span>';
    return '<span class="pt-day-badge badge-warn">' + day.taken + "/" + day.total + "</span>";
  }

  function renderDose(d) {
    var icon = d.taken ? "✓" : "✗";
    var statusCls = d.taken ? "status-ok" : "status-miss";
    var timeParts = (d.scheduled_time || "").split(" ");

    return (
      '<div class="pt-dose">' +
      '<div class="pt-dose-time">' + esc(timeParts[0] || "") + "<br>" + esc(timeParts[1] || "") + "</div>" +
      '<div class="pt-dose-info">' +
      '<div class="pt-dose-name">' + esc(d.name) + "</div>" +
      '<div class="pt-dose-period">' + esc(d.period) + " · " + esc(d.dose) + "</div>" +
      '<div class="pt-dose-marked ' + markedClass(d) + '">' + esc(markedText(d)) + "</div>" +
      "</div>" +
      '<div class="pt-dose-status ' + statusCls + '">' + icon + "</div>" +
      "</div>"
    );
  }

  function renderDay(day, isToday) {
    return (
      '<section class="pt-day' + (isToday ? " pt-day-today" : "") + '">' +
      '<div class="pt-day-head">' +
      "<div><div class=\"pt-day-date\">" + esc(day.date_display) + "</div>" +
      '<div class="pt-day-meta">' + day.percentage + "% · " + day.on_time_count + " on time</div></div>" +
      dayBadge(day) +
      "</div>" +
      '<div class="pt-doses">' + day.doses.map(renderDose).join("") + "</div>" +
      "</section>"
    );
  }

  function render(data) {
    var summary = data.summary || {};
    var days = data.days || [];

    document.getElementById("totalDays").textContent = summary.total_days != null ? summary.total_days : 0;
    document.getElementById("perfectDays").textContent = summary.perfect_days != null ? summary.perfect_days : 0;
    document.getElementById("windowMins").textContent =
      "\u00b1" + (summary.on_time_window_minutes != null ? summary.on_time_window_minutes : 15);

    if (summary.storage_note) {
      document.getElementById("storageNote").textContent = summary.storage_note;
    }

    var main = document.getElementById("trackMain");
    document.getElementById("loading").style.display = "none";

    if (days.length) {
      var today = days[0];
      document.getElementById("todayCard").hidden = false;
      document.getElementById("todayCount").textContent = today.taken + " / " + today.total;
      document.getElementById("todayOntime").textContent = today.on_time_count + " on time";
      setRing(today.percentage);
      main.innerHTML = days.map(function (d, i) { return renderDay(d, i === 0); }).join("");
      return;
    }

    document.getElementById("todayCard").hidden = true;
    var storageHint = summary.storage === "blob"
      ? "No marks recorded yet today."
      : "Tracking storage not connected — marks may not persist. Link Vercel Blob store.";
    main.innerHTML = '<p class="pt-loading">' + esc(storageHint) + "</p>";
  }

  function load() {
    var loading = document.getElementById("loading");
    loading.style.display = "block";
    loading.textContent = "Loading...";

    fetch("/api/pilltrack")
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        render(data);
      })
      .catch(function (err) {
        loading.textContent = "Failed to load. Tap ↻ to retry.";
        console.error("pilltrack error:", err);
      });
  }

  document.getElementById("btnRefresh").addEventListener("click", load);
  load();
})();
