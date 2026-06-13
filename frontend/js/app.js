/**
 * నాPills — Nannagaru Medicine Assistant (AngularJS 1.x)
 *
 * Routing: home (take-now + period picker) → period view (medicine cards).
 * The realtime clock drives the "take now" suggestion: doses within
 * ±15 minutes of the current time, or the closest upcoming doses.
 */

(function () {
  "use strict";

  var app = angular.module("naaPillsApp", ["ngRoute"]);

  /* ── Configuration ─────────────────────────────────────────── */

  app.constant("API_BASE", ""); // Same origin; set full URL if API is hosted elsewhere

  // Telugu labels used across the app
  app.constant("LABELS", {
    periods: {
      morning: { telugu: "ఉదయము", english: "Morning", emoji: "\uD83C\uDF05" },
      afternoon: { telugu: "మధ్యాన్నాము", english: "Afternoon", emoji: "\u2600\uFE0F" },
      evening: { telugu: "సాయంత్రము", english: "Evening", emoji: "\uD83C\uDF19" },
      bedtime: { telugu: "పడుకునే ముందు", english: "Bed Time", emoji: "\uD83D\uDECF\uFE0F" },
    },
    taken: "తీసుకున్నాను",
    notTakenYet: "తీసుకోలేదు",
  });

  app.config(["$routeProvider", function ($routeProvider) {
    $routeProvider
      .when("/", {
        templateUrl: "/templates/home.html",
        controller: "HomeController",
        controllerAs: "home",
      })
      .when("/period/:periodName", {
        templateUrl: "/templates/period.html",
        controller: "PeriodController",
        controllerAs: "period",
      })
      .otherwise({ redirectTo: "/" });
  }]);

  /* ── Shared helpers ─────────────────────────────────────────── */

  // "07:30 AM" → minutes since midnight
  function timeToMinutes(timeStr) {
    var match = /(\d{1,2}):(\d{2})\s*(AM|PM)/i.exec(timeStr);
    if (!match) return 0;
    var hours = parseInt(match[1], 10) % 12;
    if (/PM/i.test(match[3])) hours += 12;
    return hours * 60 + parseInt(match[2], 10);
  }

  // Telugu food instruction based on dose period + raw food text
  function teluguFood(med) {
    var food = (med.food || "").toLowerCase();
    if (med.period === "bedtime" && food.indexOf("bed") !== -1) {
      return "పడుకునే ముందు";
    }
    var before = food.indexOf("before") !== -1;
    if (med.period === "morning") {
      return before ? "ఫలహారానికి ముందు" : "ఫలహారానికి తరువాత";
    }
    return before ? "భోజనానికి ముందు" : "భోజనానికి తరువాత";
  }

  function decorate(med) {
    med.foodTelugu = teluguFood(med);
    med.minutes = timeToMinutes(med.time);
    med.colorClass = "med-" + (med.medicine_id || "default");
    return med;
  }

  /* ── Image lightbox ─────────────────────────────────────────── */

  app.factory("ImageViewer", [function () {
    var state = {
      visible: false,
      src: "",
      alt: "",
      scale: 1,
      _pinchStart: null,
      _pinchStartScale: 1,
    };

    state.open = function (src, alt) {
      state.src = src;
      state.alt = alt || "";
      state.scale = 1;
      state.visible = true;
      document.body.style.overflow = "hidden";
    };

    state.close = function () {
      state.visible = false;
      state.scale = 1;
      document.body.style.overflow = "";
    };

    state.zoomIn = function () {
      state.scale = Math.min(4, +(state.scale + 0.35).toFixed(2));
    };

    state.zoomOut = function () {
      state.scale = Math.max(1, +(state.scale - 0.35).toFixed(2));
    };

    return state;
  }]);

  app.directive("lightboxPinch", ["ImageViewer", function (ImageViewer) {
    return {
      restrict: "A",
      link: function (scope, element) {
        function dist(touches) {
          var dx = touches[0].clientX - touches[1].clientX;
          var dy = touches[0].clientY - touches[1].clientY;
          return Math.sqrt(dx * dx + dy * dy);
        }

        element.on("touchstart", function (e) {
          if (e.originalEvent.touches.length === 2) {
            ImageViewer._pinchStart = dist(e.originalEvent.touches);
            ImageViewer._pinchStartScale = ImageViewer.scale;
          }
        });

        element.on("touchmove", function (e) {
          if (e.originalEvent.touches.length === 2 && ImageViewer._pinchStart) {
            e.preventDefault();
            var ratio = dist(e.originalEvent.touches) / ImageViewer._pinchStart;
            ImageViewer.scale = Math.min(4, Math.max(1, +(ImageViewer._pinchStartScale * ratio).toFixed(2)));
            scope.$applyAsync();
          }
        });

        element.on("touchend", function () {
          ImageViewer._pinchStart = null;
        });
      },
    };
  }]);

  app.run(["$rootScope", "ImageViewer", function ($rootScope, ImageViewer) {
    $rootScope.viewer = ImageViewer;
  }]);

  /* ── API Service ────────────────────────────────────────────── */

  app.service("MedicineApi", ["$http", "API_BASE", function ($http, API_BASE) {
    var base = API_BASE + "/api";

    this.getTodayGrouped = function () {
      return $http.get(base + "/today");
    };

    this.getByPeriod = function (period) {
      return $http.get(base + "/medicines/" + period);
    };

    this.getTodayStatus = function () {
      return $http.get(base + "/status/today");
    };

    this.markTaken = function (doseId, taken) {
      return $http.post(base + "/mark-taken", {
        dose_id: doseId,
        taken: taken !== false,
      });
    };

    this.getSupplementsToday = function () {
      return $http.get(base + "/supplements/today");
    };

    this.logSupplement = function (supplementId, when) {
      return $http.post(base + "/supplements/" + supplementId + "/log", { when: when || null });
    };

    this.undoSupplement = function (supplementId) {
      return $http.post(base + "/supplements/" + supplementId + "/undo", {});
    };
  }]);

  /* ── Main Controller (header clock + progress) ─────────────── */

  app.controller("MainController", [
    "MedicineApi", "$rootScope", "$interval", "LABELS",
    function (MedicineApi, $rootScope, $interval, LABELS) {
      var vm = this;
      vm.showProgress = true;
      vm.progress = { total: 0, taken: 0, percentage: 0, all_taken: false };
      vm.clock = { time: "", ampm: "", daypart: "" };

      function dayPartTelugu(hours) {
        if (hours < 12) return LABELS.periods.morning.telugu;
        if (hours < 16) return LABELS.periods.afternoon.telugu;
        if (hours < 20) return LABELS.periods.evening.telugu;
        return "రాత్రి";
      }

      function tick() {
        var now = new Date();
        var hours = now.getHours();
        var h12 = hours % 12 || 12;
        var minutes = ("0" + now.getMinutes()).slice(-2);
        vm.clock.time = h12 + ":" + minutes;
        vm.clock.ampm = hours >= 12 ? "PM" : "AM";
        vm.clock.daypart = dayPartTelugu(hours);
      }

      tick();
      $interval(tick, 1000);

      function loadProgress() {
        MedicineApi.getTodayStatus().then(function (response) {
          vm.progress = response.data;
        });
      }

      loadProgress();
      $rootScope.$on("doseUpdated", function (e, progress) {
        if (progress) vm.progress = progress;
        else loadProgress();
      });
    },
  ]);

  /* ── Home Controller ────────────────────────────────────────── */

  app.controller("HomeController", [
    "MedicineApi", "$rootScope", "$interval", "LABELS",
    function (MedicineApi, $rootScope, $interval, LABELS) {
      var vm = this;
      var WINDOW_MINUTES = 15; // ± window for "take now"

      vm.loading = true;
      vm.labels = LABELS;
      vm.nowMedicines = [];
      vm.nowTitle = "";
      vm.counts = {};
      vm.periods = ["morning", "afternoon", "evening", "bedtime"].map(function (key) {
        return angular.extend({ key: key }, LABELS.periods[key]);
      });

      var PERIOD_ORDER = ["morning", "afternoon", "evening", "bedtime"];

      function getCurrentPeriod(hours) {
        if (hours < 12) return "morning";
        if (hours < 16) return "afternoon";
        if (hours < 20) return "evening";
        return "bedtime";
      }

      // Show ALL untaken doses for the current period (morning until noon, etc.)
      // plus any missed doses from earlier periods still not taken.
      function pickNowMedicines(doses) {
        var now = new Date();
        var nowMin = now.getHours() * 60 + now.getMinutes();
        var currentPeriod = getCurrentPeriod(now.getHours());
        var currentIdx = PERIOD_ORDER.indexOf(currentPeriod);
        var pending = doses.filter(function (d) { return !d.taken; });

        var result = pending.filter(function (d) {
          return PERIOD_ORDER.indexOf(d.period) <= currentIdx;
        });

        result.forEach(function (d) {
          var doseIdx = PERIOD_ORDER.indexOf(d.period);
          if (doseIdx < currentIdx) {
            d.reminderStatus = "missed";
          } else if (d.minutes < nowMin - WINDOW_MINUTES) {
            d.reminderStatus = "missed";
          } else if (d.minutes <= nowMin + WINDOW_MINUTES) {
            d.reminderStatus = "now";
          } else {
            d.reminderStatus = "upcoming";
          }
        });

        // Missed first, then by scheduled time
        result.sort(function (a, b) {
          if (a.reminderStatus === "missed" && b.reminderStatus !== "missed") return -1;
          if (b.reminderStatus === "missed" && a.reminderStatus !== "missed") return 1;
          return a.minutes - b.minutes;
        });

        var missedCount = result.filter(function (d) { return d.reminderStatus === "missed"; }).length;
        var periodTelugu = LABELS.periods[currentPeriod].telugu;

        if (missedCount > 0) {
          vm.nowTitle = "మరచిపోయిన / తీసుకోవాల్సిన మందులు";
        } else if (result.length) {
          vm.nowTitle = periodTelugu + " — తీసుకోవాల్సిన మందులు";
        } else {
          vm.nowTitle = "";
        }

        return result;
      }

      vm.supplement = null;
      vm.showWhenPicker = false;

      function inferWhen() {
        var h = new Date().getHours();
        if (h < 14) return { id: "breakfast", telugu: "ఫలహారం తరువాత" };
        if (h < 20) return { id: "evening", telugu: "సాయంత్రం" };
        return { id: "bedtime", telugu: "నిద్రకు ముందు" };
      }

      vm.suggestedWhen = inferWhen();

      function load() {
        MedicineApi.getTodayStatus().then(function (response) {
          var doses = (response.data.doses || []).map(decorate);
          var supplements = response.data.supplements || [];
          vm.supplement = supplements.length ? supplements[0] : null;

          vm.periods.forEach(function (p) {
            vm.counts[p.key] = doses.filter(function (d) { return d.period === p.key; }).length;
          });

          vm.nowMedicines = pickNowMedicines(doses).sort(function (a, b) {
            return a.minutes - b.minutes;
          });
          vm.loading = false;
        });
      }

      vm.logSupplementQuick = function () {
        if (!vm.supplement || vm.supplement._saving) return;
        vm.supplement._saving = true;
        var when = inferWhen().id;
        MedicineApi.logSupplement(vm.supplement.id, when).then(function (resp) {
          vm.supplement = resp.data.supplements[0];
          vm.supplement._saving = false;
          vm.showWhenPicker = false;
          $rootScope.$broadcast("doseUpdated", resp.data.progress);
        }).catch(function () {
          vm.supplement._saving = false;
        });
      };

      vm.logSupplementWhen = function (whenId) {
        if (!vm.supplement || vm.supplement._saving) return;
        vm.supplement._saving = true;
        MedicineApi.logSupplement(vm.supplement.id, whenId).then(function (resp) {
          vm.supplement = resp.data.supplements[0];
          vm.supplement._saving = false;
          vm.showWhenPicker = false;
          $rootScope.$broadcast("doseUpdated", resp.data.progress);
        }).catch(function () {
          vm.supplement._saving = false;
        });
      };

      vm.undoSupplement = function () {
        if (!vm.supplement || vm.supplement._saving) return;
        vm.supplement._saving = true;
        MedicineApi.undoSupplement(vm.supplement.id).then(function (resp) {
          vm.supplement = resp.data.supplements[0];
          vm.supplement._saving = false;
          $rootScope.$broadcast("doseUpdated", resp.data.progress);
        }).catch(function () {
          vm.supplement._saving = false;
        });
      };

      vm.toggleWhenPicker = function () {
        vm.showWhenPicker = !vm.showWhenPicker;
      };

      vm.markTaken = function (medicine) {
        if (medicine._saving) return;
        medicine._saving = true;
        medicine.taken = true;

        MedicineApi.markTaken(medicine.id, true).then(function (resp) {
          medicine._saving = false;
          vm.nowMedicines = vm.nowMedicines.filter(function (m) {
            return m.id !== medicine.id;
          });
          $rootScope.$broadcast("doseUpdated", resp.data.progress);
        }).catch(function () {
          medicine.taken = false;
          medicine._saving = false;
        });
      };

      load();

      // Refresh every minute so missed/upcoming list stays current
      $interval(load, 60000);
    },
  ]);

  /* ── Period Controller ──────────────────────────────────────── */

  app.controller("PeriodController", [
    "$routeParams", "MedicineApi", "$rootScope", "LABELS",
    function ($routeParams, MedicineApi, $rootScope, LABELS) {
      var vm = this;
      vm.loading = true;
      vm.medicines = [];
      vm.labels = LABELS;
      vm.periodName = $routeParams.periodName;

      var info = LABELS.periods[vm.periodName] || { telugu: "మందులు", english: "Medicines", emoji: "" };
      vm.title = info.telugu;
      vm.subtitle = info.english;
      vm.emoji = info.emoji;

      function loadMedicines() {
        vm.loading = true;
        MedicineApi.getByPeriod(vm.periodName).then(function (response) {
          var meds = response.data.map(decorate);
          return MedicineApi.getTodayStatus().then(function (statusResp) {
            var statusMap = {};
            (statusResp.data.doses || []).forEach(function (d) {
              statusMap[d.id] = d.taken;
            });
            meds.forEach(function (m) {
              m.taken = statusMap[m.id] || false;
            });
            meds.sort(function (a, b) { return a.minutes - b.minutes; });
            vm.medicines = meds;
            vm.loading = false;
          });
        });
      }

      vm.toggleTaken = function (medicine) {
        if (medicine._saving) return;
        var newState = !medicine.taken;
        medicine._saving = true;
        medicine.taken = newState;

        MedicineApi.markTaken(medicine.id, newState).then(function (resp) {
          medicine._saving = false;
          $rootScope.$broadcast("doseUpdated", resp.data.progress);
        }).catch(function () {
          medicine.taken = !newState;
          medicine._saving = false;
        });
      };

      loadMedicines();
    },
  ]);
})();
