/**
 * Onboarding flow: center name first, optional stage/time-range setup second.
 * Stages are configured via an accordion where all items are always editable;
 * changes are saved in bulk when the user clicks "Guardar y continuar".
 */
(function () {
  var ONBOARDING_ENTRY_KEY = "orarioo_onboarding_entry";

  function canAccessOnboarding() {
    var tokens = window.orariooAuth && window.orariooAuth.getTokens ? window.orariooAuth.getTokens() : {};
    var entrySource = "";
    try {
      entrySource = window.sessionStorage.getItem(ONBOARDING_ENTRY_KEY);
    } catch (_error) {
      entrySource = "";
    }
    return entrySource === "signup" && Boolean(tokens.access);
  }

  function clearOnboardingEntry() {
    try {
      window.sessionStorage.removeItem(ONBOARDING_ENTRY_KEY);
    } catch (_error) {
      // Storage can be disabled in some browsers; nothing else to clean up.
    }
  }

  if (!canAccessOnboarding()) {
    window.location.replace("/sign-up/");
    return;
  }

  var DEFAULT_STAGE_TEMPLATE = {
    start_time: "09:00",
    end_time: "14:00",
    breaks: [],
    session_duration: 60,
  };

  var form = document.getElementById("onboarding-form");
  var layout = document.querySelector(".auth-layout");
  var card = document.querySelector(".onboarding-card");
  var teamStep = document.getElementById("onboarding-team-step");
  var scheduleStep = document.getElementById("onboarding-schedule-step");
  var nextStepBtn = document.getElementById("onboarding-next-step");
  var backStepBtn = document.getElementById("onboarding-back-step");
  var skipScheduleBtn = document.getElementById("onboarding-skip-schedule");
  var submitBtn = document.getElementById("onboarding-submit");
  var alertEl = document.getElementById("onboarding-alert");
  var teamNameInput = document.getElementById("onboarding-team-name");
  var teamNameError = document.getElementById("onboarding-team-name-error");
  var stagesContainer = document.getElementById("onboarding-stages-config");
  var stagesError = document.getElementById("onboarding-stages-error");

  var headerTeam = document.getElementById("ob-header-team");
  var headerSchedule = document.getElementById("ob-header-schedule");
  var stepperStep1 = document.getElementById("ob-stepper-step-1");
  var stepperStep2 = document.getElementById("ob-stepper-step-2");
  var stepperLine = document.getElementById("ob-stepper-line");

  var addStageModalEl = document.getElementById("onboarding-add-stage-modal");
  var addStageForm = document.getElementById("onboarding-add-stage-form");
  var addStageNameInput = document.getElementById("onboarding-new-stage-name");
  var addStageNameError = document.getElementById("onboarding-new-stage-name-error");
  var addStageColorOptions = document.getElementById("onboarding-color-options");
  var addStageColorError = document.getElementById("onboarding-new-stage-color-error");

  var addStageModal = addStageModalEl && window.bootstrap ? new window.bootstrap.Modal(addStageModalEl) : null;

  function getInitialData() {
    var node = document.getElementById("onboarding-initial-data");
    if (!node) {
      return { schedule_config: {}, color_options: [] };
    }
    try {
      return JSON.parse(node.textContent || "{}");
    } catch (_) {
      return { schedule_config: {}, color_options: [] };
    }
  }

  var initialData = getInitialData();
  var colorOptions = Array.isArray(initialData.color_options) ? initialData.color_options : [];
  var currentConfig = cloneConfig(initialData.schedule_config || {});

  function cloneConfig(config) {
    return JSON.parse(JSON.stringify(config || {}));
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function showAlert(message, type) {
    if (!alertEl) {
      return;
    }
    alertEl.className = "onboarding-alert alert alert-" + (type === "error" ? "danger" : "success");
    alertEl.textContent = message;
    alertEl.classList.remove("d-none");
  }

  function clearAlert() {
    if (alertEl) {
      alertEl.classList.add("d-none");
    }
  }

  function clearStagesError() {
    if (stagesError) {
      stagesError.textContent = "";
    }
  }

  function showStagesError(message) {
    if (stagesError) {
      stagesError.textContent = message || "";
    }
  }

  function setLoading(loading) {
    [submitBtn, skipScheduleBtn, backStepBtn, nextStepBtn].forEach(function (btn) {
      if (btn) {
        btn.disabled = loading;
      }
    });
    if (!submitBtn) {
      return;
    }
    var label = submitBtn.querySelector(".btn-label");
    var loader = submitBtn.querySelector(".btn-loader");
    if (label) {
      label.style.display = loading ? "none" : "";
    }
    if (loader) {
      loader.style.display = loading ? "inline-block" : "none";
    }
  }

  /**
   * Switches the visible onboarding step and updates the stepper UI state.
   * Input: stepName - "team" or "schedule"
   * Output: void
   */
  function showStep(stepName) {
    var isSchedule = stepName === "schedule";
    if (teamStep) {
      teamStep.classList.toggle("d-none", isSchedule);
    }
    if (scheduleStep) {
      scheduleStep.classList.toggle("d-none", !isSchedule);
    }
    if (headerTeam) {
      headerTeam.classList.toggle("d-none", isSchedule);
    }
    if (headerSchedule) {
      headerSchedule.classList.toggle("d-none", !isSchedule);
    }
    if (layout) {
      layout.classList.toggle("is-onboarding-schedule", isSchedule);
    }
    if (card) {
      card.classList.toggle("is-schedule-step", isSchedule);
    }
    if (stepperStep1) {
      stepperStep1.classList.toggle("ob-stepper-step--done", isSchedule);
      stepperStep1.classList.toggle("ob-stepper-step--active", !isSchedule);
    }
    if (stepperStep2) {
      stepperStep2.classList.toggle("ob-stepper-step--active", isSchedule);
    }
    if (stepperLine) {
      stepperLine.classList.toggle("ob-stepper-line--done", isSchedule);
    }
  }

  function validateTeamName() {
    var value = teamNameInput ? teamNameInput.value.trim() : "";
    if (teamNameError) {
      teamNameError.textContent = "";
      teamNameError.style.display = "none";
    }
    if (!value) {
      if (teamNameError) {
        teamNameError.textContent = "El nombre del centro es obligatorio.";
        teamNameError.style.display = "block";
      }
      if (teamNameInput) {
        teamNameInput.focus();
      }
      return false;
    }
    return true;
  }

  function codeFromLabel(label) {
    var base = String(label || "").trim();
    if (base.normalize) {
      base = base.normalize("NFD").replace(/[̀-ͯ]/g, "");
    }
    return base
      .toUpperCase()
      .replace(/[^A-Z0-9]+/g, "_")
      .replace(/_+/g, "_")
      .replace(/^_|_$/g, "");
  }

  /**
   * Returns a human-readable break count label for the accordion header summary.
   * Input: count - integer number of breaks
   * Output: string such as "1 recreo", "2 recreos" or "Sin recreos"
   */
  function breakCountLabel(count) {
    if (!count) {
      return "Sin recreos";
    }
    return count === 1 ? "1 recreo" : count + " recreos";
  }

  /**
   * Builds a colored dot using the existing stage-color-* + schedule-config-color-swatch mechanic.
   * Input: color - color key such as "blue", "red"
   * Output: HTML string for a colored circle
   */
  function colorDotHtml(color) {
    return (
      '<span class="ob-stage-dot stage-color-' +
      escapeHtml(color) +
      '" aria-hidden="true">' +
      '<span class="schedule-config-color-swatch"></span>' +
      "</span>"
    );
  }

  /**
   * Renders color radio options inside the add-stage modal.
   * Input: selectedColor - color key to pre-select
   * Output: void
   */
  function renderColorOptions(selectedColor) {
    if (!addStageColorOptions) {
      return;
    }
    addStageColorOptions.innerHTML = colorOptions
      .map(function (option) {
        var id = "onboarding-color-" + option.value;
        var checked = option.value === selectedColor ? " checked" : "";
        return (
          '<label class="schedule-config-color-choice stage-color-' +
          option.value +
          '" for="' +
          id +
          '">' +
          '<input class="schedule-config-color-radio" type="radio" name="onboarding-new-stage-color" id="' +
          id +
          '" value="' +
          option.value +
          '"' +
          checked +
          ">" +
          '<span class="schedule-config-color-swatch" aria-hidden="true"></span>' +
          '<span class="schedule-config-color-label">' +
          escapeHtml(option.label) +
          "</span>" +
          "</label>"
        );
      })
      .join("");
  }

  function getSelectedAddColor() {
    var selected = addStageModalEl && addStageModalEl.querySelector('input[name="onboarding-new-stage-color"]:checked');
    return selected ? selected.value : "";
  }

  function resetAddStageForm() {
    if (addStageForm) {
      addStageForm.reset();
    }
    if (addStageNameInput) {
      addStageNameInput.value = "";
    }
    if (addStageNameError) {
      addStageNameError.textContent = "";
    }
    if (addStageColorError) {
      addStageColorError.textContent = "";
    }
    renderColorOptions("blue");
  }

  /**
   * Builds the color <select> HTML for a stage accordion item body.
   * Input: selectedColor - currently selected color key
   * Output: HTML string for the select element
   */
  function colorSelectHtml(selectedColor) {
    return (
      '<select class="form-select form-select-sm ob-stage-color">' +
      colorOptions
        .map(function (option) {
          return (
            '<option value="' +
            option.value +
            '"' +
            (option.value === selectedColor ? " selected" : "") +
            ">" +
            escapeHtml(option.label) +
            "</option>"
          );
        })
        .join("") +
      "</select>"
    );
  }

  /**
   * Builds a single break row with start/end time inputs and a remove button.
   * Input: breakCfg - object with optional start/end strings
   * Output: HTML string for the break row
   */
  function buildBreakRow(breakCfg) {
    var currentBreak = breakCfg || {};
    return (
      '<div class="row g-2 align-items-end ob-break-row mb-2">' +
      '<div class="col">' +
      '<label class="form-label mb-0">Inicio</label>' +
      '<span class="text-danger" aria-hidden="true">*</span>' +
      '<input type="time" class="form-control form-control-sm ob-break-start" value="' +
      escapeHtml(currentBreak.start || "") +
      '">' +
      "</div>" +
      '<div class="col-auto d-flex align-items-end pb-1">' +
      '<span class="badge bg-light text-muted border px-2 py-2"' +
      ' data-bs-toggle="tooltip" data-bs-placement="top"' +
      ' data-bs-title="La duración del recreo es fija: 30 minutos.">&#9201; 30 min</span>' +
      "</div>" +
      '<div class="col-auto pt-3">' +
      '<button type="button" class="btn btn-sm btn-outline-danger ob-remove-break" aria-label="Eliminar recreo">&times;</button>' +
      "</div>" +
      "</div>"
    );
  }

  /**
   * Builds a full accordion item for one educational stage.
   * Input: stageCode   - stage identifier used as data-stage key
   *        stageCfg    - config object for the stage (label, color, times, breaks)
   *        expandFirst - if true, the collapse starts open
   * Output: HTML string for the accordion item
   */
  function buildStageAccordionItem(stageCode, stageCfg, expandFirst) {
    var cfg = stageCfg || {};
    var label = cfg.label || stageCode;
    var color = cfg.color || "blue";
    var start = cfg.start_time || DEFAULT_STAGE_TEMPLATE.start_time;
    var end = cfg.end_time || DEFAULT_STAGE_TEMPLATE.end_time;
    var breaks = Array.isArray(cfg.breaks) ? cfg.breaks : [];
    var collapseId = "ob-stage-body-" + escapeHtml(stageCode);
    var isOpen = expandFirst ? " show" : "";
    var ariaExpanded = expandFirst ? "true" : "false";

    var breaksHtml = breaks
      .map(function (b) {
        return buildBreakRow(b);
      })
      .join("");

    return (
      '<div class="ob-stage-item" data-stage="' +
      escapeHtml(stageCode) +
      '">' +
      '<div class="ob-stage-header">' +
      '<button class="ob-stage-toggle" type="button"' +
      ' data-bs-toggle="collapse" data-bs-target="#' +
      collapseId +
      '"' +
      ' aria-expanded="' +
      ariaExpanded +
      '" aria-controls="' +
      collapseId +
      '">' +
      colorDotHtml(color) +
      '<span class="ob-stage-summary-name ob-stage-label-preview">' +
      escapeHtml(label) +
      "</span>" +
      '<span class="ob-stage-summary-meta">' +
      '<span class="ob-stage-time-range">' +
      escapeHtml(start) +
      " – " +
      escapeHtml(end) +
      "</span>" +
      '<span class="ob-stage-break-count">' +
      escapeHtml(breakCountLabel(breaks.length)) +
      "</span>" +
      "</span>" +
      '<i data-lucide="chevron-down" class="ob-stage-chevron" aria-hidden="true"></i>' +
      "</button>" +
      "</div>" +
      '<div class="collapse' +
      isOpen +
      '" id="' +
      collapseId +
      '">' +
      '<div class="ob-stage-body">' +
      '<div class="row g-3 align-items-end mb-3">' +
      '<div class="col-12 col-md">' +
      '<label class="form-label fw-semibold mb-0" for="ob-name-' +
      escapeHtml(stageCode) +
      '">Nombre</label>' +
      '<span class="text-danger" aria-hidden="true">*</span>' +
      '<input type="text" id="ob-name-' +
      escapeHtml(stageCode) +
      '" class="form-control form-control-sm ob-stage-label" value="' +
      escapeHtml(label) +
      '" placeholder="Nombre visible" maxlength="150">' +
      "</div>" +
      '<div class="col-12 col-md-auto">' +
      '<label class="form-label fw-semibold mb-0">Color</label>' +
      '<span class="text-danger" aria-hidden="true">*</span>' +
      '<div class="d-flex align-items-center gap-2">' +
      '<span class="ob-stage-color-dot stage-color-' +
      escapeHtml(color) +
      '" aria-hidden="true"><span class="schedule-config-color-swatch"></span></span>' +
      colorSelectHtml(color) +
      "</div>" +
      "</div>" +
      '<div class="col-auto d-flex align-items-end">' +
      '<button type="button" class="btn btn-sm btn-outline-danger ob-delete-stage-btn"' +
      ' data-stage="' +
      escapeHtml(stageCode) +
      '" aria-label="Eliminar etapa ' +
      escapeHtml(label) +
      '">' +
      '<i data-lucide="trash-2" aria-hidden="true"></i>' +
      "</button>" +
      "</div>" +
      "</div>" +
      '<div class="row g-3 mb-3">' +
      '<div class="col-6">' +
      '<label class="form-label fw-semibold mb-0">Entrada</label>' +
      '<span class="text-danger" aria-hidden="true">*</span>' +
      '<input type="time" class="form-control form-control-sm ob-stage-start" value="' +
      escapeHtml(start) +
      '">' +
      "</div>" +
      '<div class="col-6">' +
      '<label class="form-label fw-semibold mb-0">Salida</label>' +
      '<span class="text-danger" aria-hidden="true">*</span>' +
      '<input type="time" class="form-control form-control-sm ob-stage-end" value="' +
      escapeHtml(end) +
      '">' +
      "</div>" +
      "</div>" +
      '<div class="ob-breaks-section">' +
      '<div class="d-flex justify-content-between align-items-center mb-2">' +
      '<p class="fw-semibold mb-0">Recreos</p>' +
      '<button type="button" class="btn btn-sm btn-outline-secondary ob-add-break"' +
      ' data-stage="' +
      escapeHtml(stageCode) +
      '">+ Añadir recreo</button>' +
      "</div>" +
      '<div class="ob-breaks-list" data-stage="' +
      escapeHtml(stageCode) +
      '">' +
      breaksHtml +
      "</div>" +
      '<p class="text-body-secondary small mb-0 ob-no-breaks-message' +
      (breaks.length ? " d-none" : "") +
      '">Sin recreos configurados.</p>' +
      "</div>" +
      "</div>" +
      "</div>" +
      "</div>"
    );
  }

  /**
   * Refreshes the accordion header summary (name, time range, break count, dot color)
   * from the current input values in the stage body.
   * Input: item - the ob-stage-item wrapper element
   * Output: void
   */
  function updateStageSummary(item) {
    if (!item) {
      return;
    }
    var labelEl = item.querySelector(".ob-stage-label");
    var colorEl = item.querySelector(".ob-stage-color");
    var startEl = item.querySelector(".ob-stage-start");
    var endEl = item.querySelector(".ob-stage-end");
    var breakRows = item.querySelectorAll(".ob-break-row");

    var label = labelEl && labelEl.value.trim() ? labelEl.value.trim() : item.dataset.stage || "";
    var color = colorEl ? colorEl.value : "blue";
    var start = startEl ? startEl.value : "";
    var end = endEl ? endEl.value : "";

    var namePreview = item.querySelector(".ob-stage-label-preview");
    if (namePreview) {
      namePreview.textContent = label;
    }

    var timeRange = item.querySelector(".ob-stage-time-range");
    if (timeRange && start && end) {
      timeRange.textContent = start + " – " + end;
    }

    var breakCountEl = item.querySelector(".ob-stage-break-count");
    if (breakCountEl) {
      breakCountEl.textContent = breakCountLabel(breakRows.length);
    }

    // Update header dot and inline color dot by swapping the stage-color-* class
    var headerDot = item.querySelector(".ob-stage-toggle .ob-stage-dot");
    if (headerDot) {
      headerDot.className = "ob-stage-dot stage-color-" + color;
    }
    var inlineDot = item.querySelector(".ob-stage-color-dot");
    if (inlineDot) {
      inlineDot.className = "ob-stage-color-dot stage-color-" + color;
    }
  }

  /**
   * Renders all stage accordion items into the stages container and re-binds events.
   * Output: void
   */
  function renderStageAccordion() {
    if (!stagesContainer) {
      return;
    }
    var stageCodes = Object.keys(currentConfig);
    stagesContainer.innerHTML = stageCodes
      .map(function (code, index) {
        return buildStageAccordionItem(code, currentConfig[code], index === 0);
      })
      .join("");
    bindAccordionEvents();
    if (window.lucide && typeof window.lucide.createIcons === "function") {
      window.lucide.createIcons();
    }
    if (window.orariooAuth && typeof window.orariooAuth.initBootstrapTooltips === "function") {
      window.orariooAuth.initBootstrapTooltips();
    }
  }

  function refreshBreakEmptyState(item) {
    if (!item) {
      return;
    }
    var message = item.querySelector(".ob-no-breaks-message");
    var hasBreaks = item.querySelectorAll(".ob-break-row").length > 0;
    if (message) {
      message.classList.toggle("d-none", hasBreaks);
    }
  }

  /**
   * Attaches all interactive event handlers for the accordion stage items.
   * Output: void
   */
  function bindAccordionEvents() {
    if (!stagesContainer) {
      return;
    }

    stagesContainer.querySelectorAll(".ob-delete-stage-btn").forEach(function (btn) {
      btn.onclick = function () {
        clearAlert();
        clearStagesError();
        delete currentConfig[btn.dataset.stage || ""];
        renderStageAccordion();
      };
    });

    stagesContainer.querySelectorAll(".ob-add-break").forEach(function (btn) {
      btn.onclick = function () {
        var item = btn.closest(".ob-stage-item");
        var list = item && item.querySelector(".ob-breaks-list");
        if (!list) {
          return;
        }
        list.insertAdjacentHTML("beforeend", buildBreakRow({}));
        bindAccordionEvents();
        refreshBreakEmptyState(item);
        updateStageSummary(item);
        if (window.orariooAuth && typeof window.orariooAuth.initBootstrapTooltips === "function") {
          window.orariooAuth.initBootstrapTooltips();
        }
      };
    });

    stagesContainer.querySelectorAll(".ob-remove-break").forEach(function (btn) {
      btn.onclick = function () {
        var row = btn.closest(".ob-break-row");
        var item = btn.closest("[data-stage]");
        if (row) {
          row.remove();
        }
        refreshBreakEmptyState(item);
        updateStageSummary(item);
      };
    });

    stagesContainer.querySelectorAll(".ob-stage-label").forEach(function (input) {
      input.oninput = function () {
        updateStageSummary(input.closest("[data-stage]"));
      };
    });

    stagesContainer.querySelectorAll(".ob-stage-color").forEach(function (input) {
      input.onchange = function () {
        updateStageSummary(input.closest("[data-stage]"));
      };
    });

    stagesContainer.querySelectorAll(".ob-stage-start, .ob-stage-end").forEach(function (input) {
      input.oninput = function () {
        updateStageSummary(input.closest("[data-stage]"));
      };
    });
  }

  function readBreaks(item) {
    var breaks = [];
    if (!item) {
      return breaks;
    }
    var rows = Array.prototype.slice.call(item.querySelectorAll(".ob-break-row"));
    for (var i = 0; i < rows.length; i += 1) {
      var row = rows[i];
      var startEl = row.querySelector(".ob-break-start");
      var startVal = startEl ? startEl.value : "";
      if (!startVal) {
        continue;
      }
      var parts = startVal.split(":");
      var total = parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10) + 30;
      var endVal = String(Math.floor(total / 60) % 24).padStart(2, "0") + ":" + String(total % 60).padStart(2, "0");
      breaks.push({ start: startVal, end: endVal });
    }
    return breaks;
  }

  /**
   * Reads the full config for a single stage from its accordion item DOM.
   * Input: item - the ob-stage-item wrapper element with data-stage attribute
   * Output: object with { code, config } or null if validation fails
   */
  function readStageConfig(item) {
    if (!item || !item.dataset.stage) {
      return null;
    }
    var stageCode = item.dataset.stage;
    var labelEl = item.querySelector(".ob-stage-label");
    var colorEl = item.querySelector(".ob-stage-color");
    var startEl = item.querySelector(".ob-stage-start");
    var endEl = item.querySelector(".ob-stage-end");
    var breaks = readBreaks(item);
    if (breaks === null) {
      return null;
    }
    return {
      code: stageCode,
      config: {
        label: labelEl ? labelEl.value.trim() : "",
        color: colorEl ? colorEl.value : "blue",
        start_time: startEl ? startEl.value : DEFAULT_STAGE_TEMPLATE.start_time,
        end_time: endEl ? endEl.value : DEFAULT_STAGE_TEMPLATE.end_time,
        breaks: breaks,
        session_duration: DEFAULT_STAGE_TEMPLATE.session_duration,
      },
    };
  }

  /**
   * Reads the complete schedule config from all accordion items in the DOM.
   * Bootstrap collapse only hides items visually; all inputs remain in the DOM.
   * Output: config object or null if any validation fails
   */
  function readScheduleConfig() {
    var config = {};
    if (!stagesContainer) {
      return config;
    }
    var items = Array.prototype.slice.call(stagesContainer.querySelectorAll(".ob-stage-item"));
    for (var i = 0; i < items.length; i += 1) {
      var stagePayload = readStageConfig(items[i]);
      if (stagePayload === null) {
        return null;
      }
      if (!stagePayload.config.label) {
        showStagesError("Todas las etapas deben tener un nombre.");
        return null;
      }
      config[stagePayload.code] = stagePayload.config;
    }
    return config;
  }

  function createStage(event) {
    event.preventDefault();
    clearAlert();
    clearStagesError();

    var stageName = addStageNameInput ? addStageNameInput.value.trim() : "";
    var stageColor = getSelectedAddColor();
    var stageCode = codeFromLabel(stageName);

    if (addStageNameError) {
      addStageNameError.textContent = "";
    }
    if (addStageColorError) {
      addStageColorError.textContent = "";
    }

    if (!stageName) {
      if (addStageNameError) {
        addStageNameError.textContent = "Indica un nombre para la etapa.";
      }
      return;
    }
    if (!stageColor) {
      if (addStageColorError) {
        addStageColorError.textContent = "Selecciona un color.";
      }
      return;
    }
    if (!stageCode) {
      if (addStageNameError) {
        addStageNameError.textContent = "No se ha podido generar un código válido para esa etapa.";
      }
      return;
    }
    if (currentConfig[stageCode]) {
      if (addStageNameError) {
        addStageNameError.textContent = "Este nombre ya existe.";
      }
      return;
    }

    currentConfig[stageCode] = {
      label: stageName,
      color: stageColor,
      start_time: DEFAULT_STAGE_TEMPLATE.start_time,
      end_time: DEFAULT_STAGE_TEMPLATE.end_time,
      breaks: [],
      session_duration: DEFAULT_STAGE_TEMPLATE.session_duration,
    };

    if (addStageModal) {
      addStageModal.hide();
    }
    resetAddStageForm();
    renderStageAccordion();

    // Open the newly added item so the user can configure it immediately
    var newItem = stagesContainer && stagesContainer.querySelector('[data-stage="' + stageCode + '"]');
    if (newItem && window.bootstrap) {
      var collapseEl = newItem.querySelector(".collapse");
      if (collapseEl) {
        new window.bootstrap.Collapse(collapseEl, { toggle: false }).show();
      }
    }
  }

  async function postOnboarding(scheduleConfig) {
    clearAlert();
    if (!validateTeamName()) {
      return;
    }
    setLoading(true);
    try {
      var response = await window.orariooAuth.apiFetch("/api/onboarding/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          team_name: teamNameInput.value.trim(),
          schedule_config: scheduleConfig || {},
        }),
      });
      var data = {};
      try {
        data = await response.json();
      } catch (_) {
        data = {};
      }

      if (!response.ok) {
        var parsedError =
          window.OrariooErrorHandler && typeof window.OrariooErrorHandler.parseApiError === "function"
            ? window.OrariooErrorHandler.parseApiError(data, { fallbackMessage: "Error al crear el equipo." })
            : null;
        var msg =
          (parsedError && parsedError.message) ||
          data.detail ||
          (data.team_name && data.team_name[0]) ||
          "Error al crear el equipo.";
        showAlert(msg, "error");
        return;
      }

      window.orariooAuth.setAuthSession({ user: data });
      clearOnboardingEntry();
      window.location.href = "/dashboard/";
    } catch (_) {
      showAlert("No hay conexión con el servidor.", "error");
    } finally {
      setLoading(false);
    }
  }

  function submitOnboarding(event) {
    event.preventDefault();
    clearStagesError();
    var scheduleConfig = readScheduleConfig();
    if (scheduleConfig === null) {
      return;
    }
    postOnboarding(scheduleConfig);
  }

  renderColorOptions("blue");
  renderStageAccordion();
  showStep("team");

  if (nextStepBtn) {
    nextStepBtn.addEventListener("click", function () {
      clearAlert();
      if (validateTeamName()) {
        showStep("schedule");
      }
    });
  }
  if (backStepBtn) {
    backStepBtn.addEventListener("click", function () {
      clearAlert();
      showStep("team");
    });
  }
  if (skipScheduleBtn) {
    skipScheduleBtn.addEventListener("click", function () {
      postOnboarding({});
    });
  }
  if (addStageForm) {
    addStageForm.addEventListener("submit", createStage);
  }
  if (addStageModalEl) {
    addStageModalEl.addEventListener("hidden.bs.modal", function () {
      resetAddStageForm();
    });
  }
  if (form) {
    form.addEventListener("submit", submitOnboarding);
  }
})();
