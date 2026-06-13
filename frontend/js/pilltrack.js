/**
 * Pill Track — caregiver dashboard (standalone, not linked from main app)
 */
(function () {
  "use strict";

  var main = document.getElementById("trackMain");
  var loading = document.getElementById("loading");

  function esc(str) {
    var d = document.createElement("div");
    d.textContent = str || "";
    return d.innerHTML;
  }

  function timingClass(dose) {
    if (!dose.taken) return "";
    if (dose.on_time === true) return "timing-ok";
    if (dose.on_time === false) return dose.minutes_delta > 0 ? "timing-late" : "timing-early";
    return "timing-unknown";
  }

  function timingText(dose) {
    if (!dose.taken) return "—";
    if (dose.taken_at_display) {
      var label = dose.minutes_delta_label ? " (" + dose.minutes_delta_label + ")" : "";
      return dose.taken_at_display + label;
    }
    return "Taken (time not recorded)";
  }

  function dayBadge(day) {
    if (day.all_taken) return '<span class="day-badge badge-perfect">All taken</span>';
    if (day.taken === 0) return '<span class="day-badge badge-missed">None taken</span>';
    return '<span class="day-badge badge-partial">' + day.taken + "/" + day.total + " taken</span>";
  }

  function renderDay(day) {
    var rows = day.doses.map(function (d) {
      var status = d.taken
        ? '<span class="status-pill status-taken">Taken</span>'
        : '<span class="status-pill status-missed">Missed</span>';

      return (
        "<tr>" +
        '<td data-label="Medicine">' + esc(d.name) + "</td>" +
        '<td data-label="Scheduled">' + esc(d.scheduled_time) + "</td>" +
        '<td data-label="Period">' + esc(d.period) + "</td>" +
        '<td data-label="Status">' + status + "</td>" +
        '<td data-label="Marked at" class="' + timingClass(d) + '">' + esc(timingText(d)) + "</td>" +
        "</tr>"
      );
    }).join("");

    return (
      '<section class="day-block">' +
      '<div class="day-header">' +
      "<div>" +
      '<div class="day-date">' + esc(day.date_display) + "</div>" +
      '<div class="day-stats"><strong>' + day.percentage + "%</strong> complete · " +
      day.on_time_count + " on time</div>" +
      "</div>" +
      dayBadge(day) +
      "</div>" +
      '<table class="dose-table">' +
      "<thead><tr>" +
      "<th>Medicine</th><th>Scheduled</th><th>Period</th><th>Status</th><th>Marked at</th>" +
      "</tr></thead>" +
      "<tbody>" + rows + "</tbody>" +
      "</table></section>"
    );
  }

  fetch("/api/pilltrack")
    .then(function (r) { return r.json(); })
    .then(function (data) {
      loading.style.display = "none";
      document.getElementById("totalDays").textContent = data.summary.total_days;
      document.getElementById("perfectDays").textContent = data.summary.perfect_days;
      document.getElementById("windowMins").textContent =
        "\u00b1" + data.summary.on_time_window_minutes + " min";

      if (!data.days.length) {
        main.innerHTML = '<p class="track-loading">No tracking data yet.</p>';
        return;
      }

      main.innerHTML = data.days.map(renderDay).join("");
    })
    .catch(function () {
      loading.textContent = "Failed to load tracking data.";
    });
})();
