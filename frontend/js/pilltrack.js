/**
 * Pill Track — caregiver dashboard + schedule management
 */
(function () {
  "use strict";

  var RING_C = 2 * Math.PI * 52;
  var currentTab = "track";

  function esc(s) {
    var d = document.createElement("div");
    d.textContent = s || "";
    return d.innerHTML;
  }

  function api(method, url, body) {
    var opts = { method: method, headers: { "Content-Type": "application/json" } };
    if (body) opts.body = JSON.stringify(body);
    return fetch(url, opts).then(function (r) {
      if (!r.ok) return r.json().then(function (e) { throw new Error(e.detail || "HTTP " + r.status); });
      return r.json();
    });
  }

  function setRing(pct) {
    var fill = document.getElementById("ringFill");
    var text = document.getElementById("ringPct");
    if (!fill) return;
    fill.style.strokeDashoffset = RING_C - (RING_C * pct / 100);
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

  function renderTrack(data) {
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

  function statusBadge(status) {
    var map = {
      active: ["badge-ok", "Active"],
      skipped_today: ["badge-warn", "Skipped today"],
      disabled: ["badge-bad", "Disabled"],
      expired: ["badge-muted", "Course ended"],
    };
    var item = map[status] || ["badge-muted", status];
    return '<span class="pt-day-badge ' + item[0] + '">' + item[1] + "</span>";
  }

  function manageActions(dose) {
    var id = esc(dose.id);
    var btns = [];

    if (dose.status === "active") {
      btns.push('<button type="button" class="pt-btn pt-btn-warn" data-action="skip" data-id="' + id + '">Skip today</button>');
      btns.push('<button type="button" class="pt-btn pt-btn-muted" data-action="disable" data-id="' + id + '">Disable</button>');
    }
    if (dose.status === "skipped_today") {
      btns.push('<button type="button" class="pt-btn pt-btn-primary" data-action="unskip" data-id="' + id + '">Unskip today</button>');
    }
    if (dose.status === "disabled") {
      btns.push('<button type="button" class="pt-btn pt-btn-primary" data-action="enable" data-id="' + id + '">Enable</button>');
    }
    if (dose.is_custom) {
      btns.push('<button type="button" class="pt-btn pt-btn-danger" data-action="remove" data-id="' + id + '">Delete</button>');
    }
    return btns.join("");
  }

  function renderManageRow(dose) {
    return (
      '<div class="pt-manage-row">' +
      '<div class="pt-manage-info">' +
      '<div class="pt-manage-name">' + esc(dose.name) + "</div>" +
      '<div class="pt-manage-meta-line">' + esc(dose.period) + " · " + esc(dose.time) + " · " + esc(dose.dose) + "</div>" +
      '<div class="pt-manage-id">' + esc(dose.id) + "</div>" +
      "</div>" +
      '<div class="pt-manage-side">' + statusBadge(dose.status) +
      '<div class="pt-manage-actions">' + manageActions(dose) + "</div></div>" +
      "</div>"
    );
  }

  function renderManage(data) {
    document.getElementById("manageLoading").style.display = "none";
    document.getElementById("manageMeta").textContent =
      data.active_count + " active today · " + data.date;

    var groups = { morning: [], afternoon: [], evening: [], bedtime: [] };
    (data.doses || []).forEach(function (d) {
      if (groups[d.period]) groups[d.period].push(d);
    });

    var html = "";
    ["morning", "afternoon", "evening", "bedtime"].forEach(function (p) {
      if (!groups[p].length) return;
      html += '<section class="pt-manage-group"><h3 class="pt-manage-period">' + p + "</h3>";
      html += groups[p].map(renderManageRow).join("");
      html += "</section>";
    });

    document.getElementById("manageMain").innerHTML = html || '<p class="pt-loading">No doses configured.</p>';
  }

  function loadTrack() {
    var loading = document.getElementById("loading");
    loading.style.display = "block";
    loading.textContent = "Loading...";

    return api("GET", "/api/pilltrack").then(renderTrack).catch(function (err) {
      loading.textContent = "Failed to load. Tap ↻ to retry.";
      console.error("pilltrack error:", err);
    });
  }

  function loadManage() {
    var loading = document.getElementById("manageLoading");
    loading.style.display = "block";
    loading.textContent = "Loading schedule...";

    return api("GET", "/api/schedule").then(renderManage).catch(function (err) {
      loading.textContent = "Failed to load schedule.";
      console.error("schedule error:", err);
    });
  }

  function scheduleAction(action, doseId) {
    var routes = {
      skip: ["POST", "/api/schedule/skip-today", { dose_id: doseId }],
      unskip: ["POST", "/api/schedule/unskip-today", { dose_id: doseId }],
      disable: ["POST", "/api/schedule/disable/" + encodeURIComponent(doseId), null],
      enable: ["POST", "/api/schedule/enable/" + encodeURIComponent(doseId), null],
      remove: ["DELETE", "/api/schedule/dose/" + encodeURIComponent(doseId), null],
    };
    var route = routes[action];
    if (!route) return Promise.resolve();

    if (action === "remove" && !window.confirm("Delete custom dose " + doseId + "?")) {
      return Promise.resolve();
    }

    return api(route[0], route[1], route[2]).then(function (data) {
      renderManage(data);
      if (currentTab === "track") loadTrack();
    }).catch(function (err) {
      alert(err.message || "Action failed");
    });
  }

  function switchTab(tab) {
    currentTab = tab;
    document.querySelectorAll(".pt-tab").forEach(function (btn) {
      btn.classList.toggle("pt-tab-active", btn.getAttribute("data-tab") === tab);
    });
    document.getElementById("panelTrack").hidden = tab !== "track";
    document.getElementById("panelManage").hidden = tab !== "manage";
    if (tab === "manage") loadManage();
    else loadTrack();
  }

  function initAddForm() {
    var startInput = document.getElementById("addStart");
    if (startInput && !startInput.value) {
      startInput.value = new Date().toISOString().slice(0, 10);
    }

    document.getElementById("btnAddDose").addEventListener("click", function () {
      var msg = document.getElementById("addMsg");
      var payload = {
        id: document.getElementById("addId").value.trim(),
        name: document.getElementById("addName").value.trim(),
        period: document.getElementById("addPeriod").value,
        time: document.getElementById("addTime").value.trim(),
        dose: document.getElementById("addDose").value.trim(),
        start_date: document.getElementById("addStart").value,
        duration_days: parseInt(document.getElementById("addDuration").value, 10) || 30,
      };

      if (!payload.id || !payload.name || !payload.time || !payload.dose) {
        msg.textContent = "Fill ID, name, time, and dose.";
        return;
      }

      api("POST", "/api/schedule/add", payload).then(function (data) {
        msg.textContent = "Added " + payload.id;
        renderManage(data);
        document.getElementById("addId").value = "";
        document.getElementById("addName").value = "";
        document.getElementById("addTime").value = "";
        document.getElementById("addDose").value = "";
      }).catch(function (err) {
        msg.textContent = err.message || "Failed to add";
      });
    });
  }

  document.getElementById("btnRefresh").addEventListener("click", function () {
    if (currentTab === "manage") loadManage();
    else loadTrack();
  });

  document.querySelectorAll(".pt-tab").forEach(function (btn) {
    btn.addEventListener("click", function () {
      switchTab(btn.getAttribute("data-tab"));
    });
  });

  document.getElementById("manageMain").addEventListener("click", function (e) {
    var btn = e.target.closest("[data-action]");
    if (!btn) return;
    scheduleAction(btn.getAttribute("data-action"), btn.getAttribute("data-id"));
  });

  initAddForm();
  loadTrack();
})();
