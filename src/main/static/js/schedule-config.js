/**
 * Admin tab for managing the active team's educational stage time ranges.
 * Follows the same IIFE + dom.createElement pattern as classrooms.js and subjects.js.
 * Uses a custom CRUD flow (not createEntityManager) because the API exposes a single
 * PUT endpoint for the full config object rather than per-item REST resources.
 */
(function () {
  const admin = window.AdminBase || {};
  const dom = admin.dom;
  const uiState = window.OrariooAdmin && window.OrariooAdmin.uiState;
  const constants = window.OrariooAdmin && window.OrariooAdmin.constants;

  if (!dom || !admin.api) {
    return;
  }

  // ── Constants ─────────────────────────────────────────────────────

  /** Preferred display order for the built-in stage codes. */
  const STAGE_ORDER = ["PRESCHOOL", "PRIMARY", "SECONDARY", "ALEVELS"];

  const COLOR_OPTIONS = [
    { value: "red", label: "Rojo" },
    { value: "yellow", label: "Amarillo" },
    { value: "orange", label: "Naranja" },
    { value: "green", label: "Verde" },
    { value: "blue", label: "Azul" },
    { value: "purple", label: "Morado" },
    { value: "pink", label: "Rosa" },
    { value: "gray", label: "Gris" },
  ];

  const DEFAULT_STAGE_LABELS = {
    PRESCHOOL: "Infantil",
    PRIMARY: "Primaria",
    SECONDARY: "ESO",
    ALEVELS: "Bachillerato",
  };

  const DEFAULT_STAGE_COLORS = {
    PRESCHOOL: "green",
    PRIMARY: "blue",
    SECONDARY: "orange",
    ALEVELS: "purple",
  };

  // ── Time-select helpers ───────────────────────────────────────────

  function scPadTwo(n) {
    return String(n).padStart(2, "0");
  }

  function scBuildStartOptions(selected) {
    let html = "";
    for (let h = 0; h < 24; h++) {
      for (const m of [0, 15, 30, 45]) {
        const val = scPadTwo(h) + ":" + scPadTwo(m);
        html += `<option value="${val}"${val === selected ? " selected" : ""}>${val}</option>`;
      }
    }
    return html;
  }

  function scBuildEndOptions(startVal, selected) {
    const startParts = (startVal || "00:00").split(":");
    const startMins = parseInt(startParts[1], 10);
    const validMins = startMins === 0 || startMins === 30 ? [0, 30] : [15, 45];
    const startTotal = parseInt(startParts[0], 10) * 60 + startMins;
    let html = "";
    for (let h = 0; h < 24; h++) {
      for (const m of validMins) {
        const total = h * 60 + m;
        if (total <= startTotal) {
          continue;
        }
        const val = scPadTwo(h) + ":" + scPadTwo(m);
        html += `<option value="${val}"${val === selected ? " selected" : ""}>${val}</option>`;
      }
    }
    return html;
  }

  function scRefreshEndOptions(startVal, currentEnd) {
    if (!elements.endTimeInput) {
      return;
    }
    elements.endTimeInput.innerHTML = scBuildEndOptions(startVal, currentEnd);
    if (!elements.endTimeInput.value) {
      const first = elements.endTimeInput.querySelector("option");
      if (first) {
        elements.endTimeInput.value = first.value;
      }
    }
  }

  function scInitSelects(startVal, endVal) {
    if (elements.startTimeInput) {
      elements.startTimeInput.innerHTML = scBuildStartOptions(startVal);
    }
    scRefreshEndOptions(startVal, endVal);
  }

  // ── State ─────────────────────────────────────────────────────────

  /** Full schedule config object currently in sync with the server. */
  let currentConfig = {};

  /** Stage code waiting to be confirmed for deletion. */
  let pendingDeleteCode = "";

  // ── DOM references ────────────────────────────────────────────────

  const elements = {
    alertBox: document.getElementById("schedule-config-alert"),
    stagesContainer: document.getElementById("schedule-config-stages"),
    emptyMessageNode: document.getElementById("schedule-config-empty-message"),
    // Create/edit modal
    modal: document.getElementById("schedule-config-modal"),
    modalTitle: document.getElementById("schedule-config-modal-title"),
    form: document.getElementById("schedule-config-form"),
    modeInput: document.getElementById("schedule-config-mode"),
    editingCodeInput: document.getElementById("schedule-config-editing-code"),
    nameInput: document.getElementById("schedule-config-name"),
    nameError: document.getElementById("schedule-config-name-error"),
    colorOptions: document.getElementById("schedule-config-color-options"),
    colorError: document.getElementById("schedule-config-color-error"),
    startTimeInput: document.getElementById("schedule-config-start-time"),
    startTimeError: document.getElementById("schedule-config-start-time-error"),
    endTimeInput: document.getElementById("schedule-config-end-time"),
    endTimeError: document.getElementById("schedule-config-end-time-error"),
    breaksList: document.getElementById("schedule-config-breaks-list"),
    noBreaksMsg: document.getElementById("schedule-config-no-breaks"),
    breaksError: document.getElementById("schedule-config-breaks-error"),
    addBreakBtn: document.getElementById("schedule-config-add-break-btn"),
    submitBtn: document.getElementById("schedule-config-submit-btn"),
    submitSpinner: document.getElementById("schedule-config-submit-spinner"),
    submitText: document.getElementById("schedule-config-submit-text"),
    cancelBtn: document.getElementById("schedule-config-cancel-btn"),
    // Delete modal
    deleteModal: document.getElementById("schedule-config-delete-modal"),
    deleteNameEl: document.getElementById("schedule-config-delete-name"),
    deleteConfirmBtn: document.getElementById("schedule-config-delete-confirm-btn"),
    deleteCancelBtn: document.getElementById("schedule-config-delete-cancel-btn"),
    deleteSpinner: document.getElementById("schedule-config-delete-spinner"),
    deleteText: document.getElementById("schedule-config-delete-text"),
  };

  /** Bootstrap modal instances, created once. */
  const bsModal = elements.modal && window.bootstrap ? new window.bootstrap.Modal(elements.modal) : null;

  const bsDeleteModal =
    elements.deleteModal && window.bootstrap ? new window.bootstrap.Modal(elements.deleteModal) : null;

  // ── Generic helpers ───────────────────────────────────────────────

  /**
   * Returns a deep clone of the given config object.
   * Input: config - schedule_config object
   * Output: cloned object
   */
  function cloneConfig(config) {
    return JSON.parse(JSON.stringify(config || {}));
  }

  /**
   * Derives a stable uppercase stage code from a display label.
   * Input: label - stage label entered by the user
   * Output: uppercase identifier, e.g. "FP_BASICA"
   */
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
   * Returns the best display label for a stage.
   * Input: code - stage identifier; cfg - optional stage config object
   * Output: string label
   */
  function getStageLabel(code, cfg) {
    if (cfg && cfg.label) {
      return cfg.label;
    }
    if (constants && typeof constants.getStageLabel === "function") {
      return constants.getStageLabel(code);
    }
    return DEFAULT_STAGE_LABELS[code] || code;
  }

  /**
   * Returns the configured color key for a stage.
   * Input: code - stage identifier; cfg - optional stage config object
   * Output: string color key, e.g. "blue"
   */
  function getStageColor(code, cfg) {
    if (cfg && cfg.color) {
      return cfg.color;
    }
    if (constants && typeof constants.getStageColor === "function") {
      return constants.getStageColor(code);
    }
    return DEFAULT_STAGE_COLORS[code] || "blue";
  }

  /**
   * Pushes updated stage labels and colors into the shared admin constants store.
   * Input: res - API response wrapper
   * Output: void
   */
  function syncStageMetadata(res) {
    if (!res || !res.data || !constants) {
      return;
    }
    if (res.data.stage_labels && typeof constants.setStageLabels === "function") {
      constants.setStageLabels(res.data.stage_labels);
    }
    if (res.data.stage_colors && typeof constants.setStageColors === "function") {
      constants.setStageColors(res.data.stage_colors);
    }
  }

  /**
   * Builds the plural/singular break count label in Spanish.
   * Input: breaks - array of break objects
   * Output: string, e.g. "1 recreo" or "2 recreos"
   */
  function formatBreakCount(breaks) {
    const n = Array.isArray(breaks) ? breaks.length : 0;
    return n === 1 ? "1 recreo" : n + " recreos";
  }

  // ── Alert helpers ─────────────────────────────────────────────────

  /**
   * Displays the section-level feedback banner.
   * Input: message - user-facing text; type - "success", "error", or "warning"
   * Output: void
   */
  function showAlert(message, type) {
    if (!elements.alertBox) {
      return;
    }
    const variant = type === "error" ? "danger" : type === "warning" ? "warning" : "success";
    elements.alertBox.className = "alert alert-" + variant + " mb-3";
    elements.alertBox.textContent = message;
    elements.alertBox.classList.remove("d-none");
  }

  /**
   * Hides the section-level feedback banner.
   * Output: void
   */
  function clearAlert() {
    if (!elements.alertBox) {
      return;
    }
    elements.alertBox.classList.add("d-none");
  }

  // ── Form error helpers ────────────────────────────────────────────

  /**
   * Marks an input as invalid and sets its error message.
   * Input: errorEl - the .invalid-feedback element; message - error text
   * Output: void
   */
  function setFieldError(errorEl, message) {
    if (!errorEl) {
      return;
    }
    errorEl.textContent = message;
    const input = errorEl.previousElementSibling;
    if (input) {
      input.classList.add("is-invalid");
    }
  }

  /**
   * Clears all form field errors in the create/edit modal.
   * Output: void
   */
  function clearFormErrors() {
    [
      elements.nameError,
      elements.colorError,
      elements.startTimeError,
      elements.endTimeError,
      elements.breaksError,
    ].forEach(function (el) {
      if (!el) {
        return;
      }
      el.textContent = "";
    });
    [elements.nameInput, elements.startTimeInput, elements.endTimeInput].forEach(function (el) {
      if (el) {
        el.classList.remove("is-invalid");
      }
    });
  }

  // ── API ───────────────────────────────────────────────────────────

  /**
   * Sends the full schedule config to the server via PUT.
   * Input: config - schedule_config object
   * Output: Promise resolving to the API response wrapper
   */
  function persistConfig(config) {
    return admin.api.request("/api/schedule-config/", {
      method: "PUT",
      data: { schedule_config: config },
    });
  }

  // ── Color picker ──────────────────────────────────────────────────

  /**
   * Renders the color radio picker inside the modal.
   * Input: selectedColor - color key to pre-select
   * Output: void
   */
  function renderColorOptions(selectedColor) {
    if (!elements.colorOptions) {
      return;
    }
    elements.colorOptions.innerHTML = COLOR_OPTIONS.map(function (opt) {
      const id = "sc-color-" + opt.value;
      const checked = opt.value === selectedColor ? " checked" : "";
      return (
        '<label class="schedule-config-color-choice stage-color-' +
        opt.value +
        '" for="' +
        id +
        '">' +
        '<input class="schedule-config-color-radio" type="radio" name="schedule-config-color" id="' +
        id +
        '" value="' +
        opt.value +
        '"' +
        checked +
        ">" +
        '<span class="schedule-config-color-swatch" aria-hidden="true"></span>' +
        '<span class="schedule-config-color-label">' +
        opt.label +
        "</span>" +
        "</label>"
      );
    }).join("");
  }

  /**
   * Returns the currently selected color key from the radio picker.
   * Output: string color key, or empty string when none selected
   */
  function getSelectedColor() {
    const checked =
      elements.colorOptions && elements.colorOptions.querySelector('input[name="schedule-config-color"]:checked');
    return checked ? checked.value : "";
  }

  // ── Break rows ────────────────────────────────────────────────────

  var BREAK_DURATION_MINUTES = 30;

  function addMinutesToTime(timeStr, minutes) {
    var parts = timeStr.split(":");
    var total = parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10) + minutes;
    var hh = String(Math.floor(total / 60) % 24).padStart(2, "0");
    var mm = String(total % 60).padStart(2, "0");
    return hh + ":" + mm;
  }

  /**
   * Builds a single break row DOM element for the modal form.
   * Input: cfg - break object with optional start value
   * Output: DOM div element representing one break row
   */
  function buildBreakRow(cfg) {
    const current = cfg || {};

    const startInput = dom.createElement("select", {
      className: "form-select form-select-sm sc-break-start",
      attrs: { "aria-label": "Inicio del recreo" },
    });
    startInput.innerHTML = scBuildStartOptions(current.start || "");

    const durationBadge = dom.createElement("span", {
      className: "badge bg-light text-muted border px-2 py-2",
      text: "⏱ 30 min",
      attrs: {
        "data-bs-toggle": "tooltip",
        "data-bs-placement": "top",
        "data-bs-title": "La duración del recreo es fija: 30 minutos.",
      },
    });

    const removeBtn = dom.createElement("button", {
      className: "btn btn-sm btn-outline-danger sc-remove-break-btn",
      attrs: { type: "button", "aria-label": "Eliminar recreo" },
      children: [dom.createLucideIcon("x")],
    });

    return dom.createElement("div", {
      className: "sc-break-row row g-2 align-items-end mb-2",
      children: [
        dom.createElement("div", {
          className: "col",
          children: [
            dom.createElement("label", {
              className: "form-label small fw-semibold mb-1",
              text: "Hora de inicio",
            }),
            startInput,
          ],
        }),
        dom.createElement("div", {
          className: "col-auto d-flex align-items-end pb-1",
          children: [durationBadge],
        }),
        dom.createElement("div", {
          className: "col-auto d-flex align-items-end",
          children: [removeBtn],
        }),
      ],
    });
  }

  /**
   * Clears and re-renders the breaks list inside the modal.
   * Input: breaks - array of {start, end} objects
   * Output: void
   */
  function renderBreaksList(breaks) {
    if (!elements.breaksList) {
      return;
    }
    elements.breaksList.innerHTML = "";
    (breaks || []).forEach(function (cfg) {
      elements.breaksList.appendChild(buildBreakRow(cfg));
    });
    refreshBreaksEmptyState();
    if (window.lucide && typeof window.lucide.createIcons === "function") {
      window.lucide.createIcons();
    }
    if (window.orariooAuth && typeof window.orariooAuth.initBootstrapTooltips === "function") {
      window.orariooAuth.initBootstrapTooltips();
    }
  }

  /**
   * Appends a new empty break row to the modal breaks list.
   * Output: void
   */
  function addBreakRow() {
    if (!elements.breaksList) {
      return;
    }
    const defaultStart = elements.startTimeInput ? elements.startTimeInput.value : "";
    elements.breaksList.appendChild(buildBreakRow({ start: defaultStart }));
    refreshBreaksEmptyState();
    if (window.lucide && typeof window.lucide.createIcons === "function") {
      window.lucide.createIcons();
    }
    if (window.orariooAuth && typeof window.orariooAuth.initBootstrapTooltips === "function") {
      window.orariooAuth.initBootstrapTooltips();
    }
  }

  /**
   * Shows or hides the "no breaks" placeholder based on current break row count.
   * Output: void
   */
  function refreshBreaksEmptyState() {
    if (!elements.noBreaksMsg || !elements.breaksList) {
      return;
    }
    const hasRows = elements.breaksList.querySelectorAll(".sc-break-row").length > 0;
    elements.noBreaksMsg.classList.toggle("d-none", hasRows);
  }

  /**
   * Reads and validates break rows from the modal form.
   * Output: array of {start, end} objects, or null if validation fails
   */
  function readBreaksFromModal() {
    if (!elements.breaksList) {
      return [];
    }
    const stageStart = elements.startTimeInput ? elements.startTimeInput.value : "";
    const stageEnd = elements.endTimeInput ? elements.endTimeInput.value : "";
    const stageStartMins = stageStart
      ? parseInt(stageStart.split(":")[0], 10) * 60 + parseInt(stageStart.split(":")[1], 10)
      : 0;
    const stageEndMins = stageEnd
      ? parseInt(stageEnd.split(":")[0], 10) * 60 + parseInt(stageEnd.split(":")[1], 10)
      : 24 * 60;

    const rows = Array.from(elements.breaksList.querySelectorAll(".sc-break-row"));
    const breaks = [];
    const outOfRange = [];
    for (let i = 0; i < rows.length; i++) {
      const row = rows[i];
      const startEl = row.querySelector(".sc-break-start");
      const start = startEl ? startEl.value : "";
      if (!start) {
        continue;
      }
      const breakStartMins = parseInt(start.split(":")[0], 10) * 60 + parseInt(start.split(":")[1], 10);
      const breakEndMins = breakStartMins + BREAK_DURATION_MINUTES;
      if (stageStart && stageEnd && (breakStartMins < stageStartMins || breakEndMins > stageEndMins)) {
        const end = addMinutesToTime(start, BREAK_DURATION_MINUTES);
        outOfRange.push(start + "–" + end);
        continue;
      }
      const end = addMinutesToTime(start, BREAK_DURATION_MINUTES);
      breaks.push({ start: start, end: end });
    }
    if (outOfRange.length > 0) {
      if (elements.breaksError) {
        elements.breaksError.textContent =
          "El recreo " +
          outOfRange.join(", ") +
          " debe estar dentro del horario del tramo (" +
          stageStart +
          "–" +
          stageEnd +
          ").";
      }
      return null;
    }
    return breaks;
  }

  // ── Stage cards ───────────────────────────────────────────────────

  /**
   * Builds the card DOM node for one educational stage.
   * Input: code - stage identifier; cfg - stage config object
   * Output: DOM div.col element containing the admin card
   */
  function renderStageCard(code, cfg) {
    const safeCfg = cfg || {};
    const label = getStageLabel(code, safeCfg);
    const color = getStageColor(code, safeCfg);
    const startTime = safeCfg.start_time || "09:00";
    const endTime = safeCfg.end_time || "14:00";
    const breaks = Array.isArray(safeCfg.breaks) ? safeCfg.breaks : [];

    const editBtn = dom.createElement("button", {
      className: "btn btn-link text-primary p-0 admin-action-btn admin-action-btn--edit admin-stage-edit-btn",
      attrs: { type: "button", "aria-label": "Editar etapa " + label },
      dataset: { stageCode: code },
      children: [dom.createLucideIcon("pencil")],
    });

    const deleteBtn = dom.createElement("button", {
      className: "btn btn-link text-danger p-0 admin-action-btn admin-action-btn--delete admin-stage-delete-btn",
      attrs: { type: "button", "aria-label": "Eliminar etapa " + label },
      dataset: { stageCode: code },
      children: [dom.createLucideIcon("trash-2")],
    });

    return dom.createElement("div", {
      className: "col",
      children: [
        dom.createElement("article", {
          className: "card border-0 shadow-sm admin-card admin-stage-card",
          dataset: { stageCode: code },
          children: [
            dom.createElement("div", {
              className: "card-body admin-card-body",
              children: [
                dom.createElement("div", {
                  className: "admin-card-content",
                  children: [
                    dom.createElement("div", {
                      className: "admin-card-main",
                      children: [
                        dom.createElement("h3", {
                          className: "h6 mb-0",
                          text: label,
                        }),
                        dom.createElement("div", {
                          className: "admin-card-meta",
                          children: [
                            dom.createElement("span", {
                              className: "admin-pill stage-color-" + color,
                              text: label,
                            }),
                          ],
                        }),
                        dom.createElement("div", {
                          className: "admin-card-copy d-flex flex-wrap gap-2",
                          children: [
                            dom.createElement("span", {
                              text: startTime + " – " + endTime,
                            }),
                            dom.createElement("span", {
                              text: formatBreakCount(breaks),
                            }),
                          ],
                        }),
                      ],
                    }),
                    dom.createElement("div", {
                      className: "admin-actions",
                      children: [editBtn, deleteBtn],
                    }),
                  ],
                }),
              ],
            }),
          ],
        }),
      ],
    });
  }

  /**
   * Re-renders the full stage grid from the given config.
   * Default stages (STAGE_ORDER) are shown first; custom stages follow alphabetically.
   * Input: config - schedule_config object
   * Output: void
   */
  function renderStages(config) {
    if (!elements.stagesContainer) {
      return;
    }

    const orderedKeys = STAGE_ORDER.filter(function (c) {
      return config[c];
    });
    const extraKeys = Object.keys(config)
      .filter(function (c) {
        return STAGE_ORDER.indexOf(c) < 0;
      })
      .sort();
    const keys = orderedKeys.concat(extraKeys);

    elements.stagesContainer.innerHTML = "";
    elements.stagesContainer.classList.remove("justify-content-center");

    if (!keys.length) {
      if (uiState && typeof uiState.renderEmptyState === "function") {
        uiState.renderEmptyState(elements.stagesContainer, {
          icon: "calendar-clock",
          title: "No hay etapas",
          message: elements.emptyMessageNode
            ? elements.emptyMessageNode.textContent.trim()
            : "No hay etapas registradas. Añade la primera para comenzar.",
        });
      } else {
        elements.stagesContainer.innerHTML =
          '<div class="col-12"><p class="text-center text-body-secondary mb-0">No hay etapas registradas.</p></div>';
      }
      return;
    }

    keys.forEach(function (code) {
      elements.stagesContainer.appendChild(renderStageCard(code, config[code]));
    });

    if (window.lucide && typeof window.lucide.createIcons === "function") {
      window.lucide.createIcons();
    }
  }

  // ── Modal helpers ─────────────────────────────────────────────────

  /**
   * Resets the create/edit modal form to its default empty state.
   * Output: void
   */
  function resetForm() {
    if (elements.modeInput) {
      elements.modeInput.value = "create";
    }
    if (elements.editingCodeInput) {
      elements.editingCodeInput.value = "";
    }
    if (elements.nameInput) {
      elements.nameInput.value = "";
    }
    scInitSelects("09:00", "14:00");
    renderColorOptions("blue");
    renderBreaksList([]);
    clearFormErrors();
  }

  /**
   * Toggles the loading state of the create/edit modal submit controls.
   * Input: loading - boolean
   * Output: void
   */
  function setModalLoading(loading) {
    if (elements.submitBtn) {
      elements.submitBtn.disabled = loading;
    }
    if (elements.cancelBtn) {
      elements.cancelBtn.disabled = loading;
    }
    if (elements.submitSpinner) {
      elements.submitSpinner.classList.toggle("d-none", !loading);
    }
    if (elements.submitText) {
      const mode = elements.modeInput ? elements.modeInput.value : "create";
      elements.submitText.textContent = loading ? "Guardando..." : mode === "create" ? "Crear" : "Guardar";
    }
  }

  /**
   * Toggles the loading state of the delete confirmation modal controls.
   * Input: loading - boolean
   * Output: void
   */
  function setDeleteLoading(loading) {
    if (elements.deleteConfirmBtn) {
      elements.deleteConfirmBtn.disabled = loading;
    }
    if (elements.deleteCancelBtn) {
      elements.deleteCancelBtn.disabled = loading;
    }
    if (elements.deleteSpinner) {
      elements.deleteSpinner.classList.toggle("d-none", !loading);
    }
    if (elements.deleteText) {
      elements.deleteText.textContent = loading ? "Eliminando..." : "Eliminar";
    }
  }

  /**
   * Opens the create/edit modal, pre-filling fields when editing an existing stage.
   * Input: mode - "create" or "edit"; code - stage code (only for edit mode)
   * Output: void
   */
  function openModal(mode, code) {
    const isCreate = mode === "create";
    const cfg = !isCreate ? currentConfig[code] : null;

    if (elements.modeInput) {
      elements.modeInput.value = mode;
    }
    if (elements.editingCodeInput) {
      elements.editingCodeInput.value = code || "";
    }

    if (elements.modalTitle) {
      elements.modalTitle.textContent = isCreate ? "Añadir etapa" : "Editar etapa";
    }
    if (elements.submitText) {
      elements.submitText.textContent = isCreate ? "Crear" : "Guardar";
    }

    if (isCreate) {
      resetForm();
    } else {
      if (elements.nameInput) {
        elements.nameInput.value = cfg ? cfg.label || "" : "";
      }
      const editStart = cfg ? cfg.start_time || "09:00" : "09:00";
      const editEnd = cfg ? cfg.end_time || "14:00" : "14:00";
      scInitSelects(editStart, editEnd);
      renderColorOptions(getStageColor(code, cfg));
      renderBreaksList(cfg ? cfg.breaks || [] : []);
      clearFormErrors();
    }

    if (bsModal) {
      bsModal.show();
    }
  }

  /**
   * Opens the delete confirmation modal for the given stage.
   * Input: code - stage identifier to delete
   * Output: void
   */
  function openDeleteModal(code) {
    pendingDeleteCode = code;
    const label = getStageLabel(code, currentConfig[code]);
    if (elements.deleteNameEl) {
      elements.deleteNameEl.textContent = label;
    }
    if (bsDeleteModal) {
      bsDeleteModal.show();
    }
  }

  // ── CRUD operations ───────────────────────────────────────────────

  /**
   * Builds a stage config payload. session_duration is always 60 (not exposed in the UI).
   * Input: label, color, startTime, endTime, breaks
   * Output: stage config object
   */
  function buildStageCfg(label, color, startTime, endTime, breaks) {
    return {
      label: label,
      color: color,
      start_time: startTime,
      end_time: endTime,
      breaks: breaks || [],
      session_duration: 60,
    };
  }

  /**
   * Handles the modal form submit — creates or updates the stage in the config.
   * Input: event - form submit event
   * Output: Promise<void>
   */
  async function saveStage(event) {
    event.preventDefault();
    clearAlert();
    clearFormErrors();

    const mode = elements.modeInput ? elements.modeInput.value : "create";
    const editingCode = elements.editingCodeInput ? elements.editingCodeInput.value : "";

    const name = elements.nameInput ? elements.nameInput.value.trim() : "";
    const color = getSelectedColor();
    const startTime = elements.startTimeInput ? elements.startTimeInput.value : "";
    const endTime = elements.endTimeInput ? elements.endTimeInput.value : "";
    const breaks = readBreaksFromModal();

    // Client-side validation before sending to the server
    let valid = true;

    if (!name) {
      setFieldError(elements.nameError, "Indica el nombre de la etapa.");
      valid = false;
    }
    if (!color) {
      if (elements.colorError) {
        elements.colorError.textContent = "Selecciona un color.";
      }
      valid = false;
    }
    if (!startTime) {
      setFieldError(elements.startTimeError, "Indica la hora de entrada.");
      valid = false;
    }
    if (!endTime) {
      setFieldError(elements.endTimeError, "Indica la hora de salida.");
      valid = false;
    }
    if (startTime && endTime && startTime >= endTime) {
      setFieldError(elements.endTimeError, "La hora de salida debe ser posterior a la de entrada.");
      valid = false;
    }
    if (breaks === null) {
      valid = false;
    }

    if (!valid) {
      return;
    }

    const nextConfig = cloneConfig(currentConfig);

    if (mode === "create") {
      const code = codeFromLabel(name);
      if (!code) {
        setFieldError(elements.nameError, "No se pudo generar un código válido con ese nombre.");
        return;
      }
      if (nextConfig[code]) {
        setFieldError(elements.nameError, "Este nombre ya existe.");
        return;
      }
      nextConfig[code] = buildStageCfg(name, color, startTime, endTime, breaks);
    } else {
      if (!editingCode || !nextConfig[editingCode]) {
        return;
      }
      nextConfig[editingCode] = buildStageCfg(name, color, startTime, endTime, breaks);
    }

    setModalLoading(true);
    const res = await persistConfig(nextConfig);
    setModalLoading(false);

    if (!res.ok) {
      const errorInfo = res.errorInfo || {};
      const code = (errorInfo.code || "").toUpperCase();
      const message = errorInfo.message || "No se pudo guardar la etapa.";
      const breakErrorCodes = ["BREAK_OUTSIDE_STAGE_RANGE", "INVALID_BREAK_RANGE", "OVERLAPPING_BREAKS"];
      if (breakErrorCodes.indexOf(code) >= 0 && elements.breaksError) {
        elements.breaksError.textContent = message;
      } else {
        showAlert(message, "error");
      }
      return;
    }

    currentConfig = (res.data && res.data.schedule_config) || nextConfig;
    syncStageMetadata(res);
    if (bsModal) {
      bsModal.hide();
    }
    renderStages(currentConfig);
    showAlert(mode === "create" ? "Etapa creada correctamente." : "Etapa actualizada correctamente.", "success");
  }

  /**
   * Deletes the stage stored in pendingDeleteCode and persists the updated config.
   * Output: Promise<void>
   */
  async function deleteStage() {
    if (!pendingDeleteCode) {
      return;
    }
    clearAlert();
    setDeleteLoading(true);
    const nextConfig = cloneConfig(currentConfig);
    delete nextConfig[pendingDeleteCode];
    const res = await persistConfig(nextConfig);
    setDeleteLoading(false);

    if (!res.ok) {
      if (bsDeleteModal) {
        bsDeleteModal.hide();
      }
      const message = res.errorInfo && res.errorInfo.message ? res.errorInfo.message : "No se pudo eliminar la etapa.";
      showAlert(message, "error");
      return;
    }

    currentConfig = (res.data && res.data.schedule_config) || nextConfig;
    pendingDeleteCode = "";
    syncStageMetadata(res);
    if (bsDeleteModal) {
      bsDeleteModal.hide();
    }
    renderStages(currentConfig);
    showAlert("Etapa eliminada correctamente.", "success");
  }

  /**
   * Fetches the active team's schedule config and renders the stage grid.
   * Output: Promise<void>
   */
  async function loadConfig() {
    if (!elements.stagesContainer) {
      return;
    }

    const res = await admin.api.get("/api/schedule-config/");
    if (!res.ok) {
      elements.stagesContainer.innerHTML = "";
      showAlert("No se pudo cargar la configuración.", "error");
      return;
    }

    currentConfig = (res.data && res.data.schedule_config) || {};
    syncStageMetadata(res);
    renderStages(currentConfig);
  }

  // ── Event bindings ────────────────────────────────────────────────

  // Form submit (create / edit)
  if (elements.form) {
    elements.form.addEventListener("submit", saveStage);
  }

  // Add break button inside the modal
  if (elements.addBreakBtn) {
    elements.addBreakBtn.addEventListener("click", addBreakRow);
  }

  // Remove break — delegated on the form to cover dynamically added rows
  if (elements.form) {
    elements.form.addEventListener("click", function (e) {
      const removeBtn = e.target.closest(".sc-remove-break-btn");
      if (!removeBtn) {
        return;
      }
      const row = removeBtn.closest(".sc-break-row");
      if (row) {
        row.remove();
      }
      refreshBreaksEmptyState();
    });
  }

  // Edit / delete buttons on stage cards — delegated on the container
  if (elements.stagesContainer) {
    elements.stagesContainer.addEventListener("click", function (e) {
      const editBtn = e.target.closest(".admin-stage-edit-btn");
      if (editBtn) {
        clearAlert();
        openModal("edit", editBtn.dataset.stageCode);
        return;
      }
      const deleteBtn = e.target.closest(".admin-stage-delete-btn");
      if (deleteBtn) {
        clearAlert();
        openDeleteModal(deleteBtn.dataset.stageCode);
      }
    });
  }

  // Delete confirm button
  if (elements.deleteConfirmBtn) {
    elements.deleteConfirmBtn.addEventListener("click", deleteStage);
  }

  // Regenerate end-time options when start changes
  if (elements.startTimeInput) {
    elements.startTimeInput.addEventListener("change", function () {
      scRefreshEndOptions(elements.startTimeInput.value, elements.endTimeInput ? elements.endTimeInput.value : "");
    });
  }

  // Reset form state when the create/edit modal is fully hidden
  if (elements.modal) {
    elements.modal.addEventListener("hidden.bs.modal", function () {
      setModalLoading(false);
      resetForm();
    });
  }

  // Clear pending delete state when the delete modal is fully hidden
  if (elements.deleteModal) {
    elements.deleteModal.addEventListener("hidden.bs.modal", function () {
      setDeleteLoading(false);
      pendingDeleteCode = "";
    });
  }

  // ── Init ──────────────────────────────────────────────────────────

  scInitSelects("09:00", "14:00");
  renderColorOptions("blue");
  loadConfig();
})();
