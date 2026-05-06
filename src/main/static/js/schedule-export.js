/**
 * Export modal: entity selection, options loading, file download, and event wiring.
 * Depends on window.ScheduleUtils (buildSummaryPath).
 * Output: window.ScheduleExport — { createExportManager }
 */
(function () {
  var EXPORT_ENTITY_SELECT_IDS = {
    group: "exportGroupSelect",
    teacher: "exportTeacherSelect",
    classroom: "exportClassroomSelect",
  };

  /**
   * Creates an export manager bound to the provided state and callbacks.
   * Input: config - { state, apiJson, showAlert, extractApiErrorMessage,
   *                   showModalElement, hideModalElement, listFromPayload }
   * Output: object with openExportModal and bindExportEvents
   */
  function createExportManager(config) {
    var state = config.state;
    var apiJson = config.apiJson;
    var showAlert = config.showAlert;
    var extractApiErrorMessage = config.extractApiErrorMessage;
    var showModalElement = config.showModalElement;
    var hideModalElement = config.hideModalElement;
    var listFromPayload = config.listFromPayload;

    /**
     * Returns the relevant entity array from state for a given export entity type.
     * Input: entityType - "group" | "teacher" | "classroom"
     * Output: array of entity objects
     */
    function getEntitiesByType(entityType) {
      if (entityType === "group") { return state.currentGroups; }
      if (entityType === "teacher") { return state.currentTeachers; }
      if (entityType === "classroom") { return state.currentClassrooms; }
      return [];
    }

    /**
     * Renders the checkbox list for a single export entity type, preserving checked state.
     * Input: entityType - "group" | "teacher" | "classroom"
     * Output: void; replaces the container's inner HTML
     */
    function populateExportEntitySelect(entityType) {
      var containerId = EXPORT_ENTITY_SELECT_IDS[entityType] || null;
      var container = containerId ? document.getElementById(containerId) : null;
      if (!container) {
        return;
      }
      var checkedValues = new Set(
        Array.from(container.querySelectorAll("input[type='checkbox']:checked")).map(function (input) {
          return input.value;
        })
      );
      container.innerHTML = getEntitiesByType(entityType)
        .slice()
        .sort(function (left, right) {
          return String(left.name || "").localeCompare(String(right.name || ""), "es");
        })
        .map(function (entity) {
          var checked = checkedValues.has(String(entity.id)) ? " checked" : "";
          return (
            '<div class="checkbox-item">' +
            '<input type="checkbox" id="check-' + entityType + "-" + entity.id +
            '" value="' + entity.id + '"' + checked + ">" +
            '<label for="check-' + entityType + "-" + entity.id + '">' +
            (entity.name || "#" + entity.id) +
            "</label></div>"
          );
        })
        .join("");
    }

    /**
     * Repopulates all three export entity checkbox containers.
     * Input: none
     * Output: void
     */
    function populateAllExportEntitySelects() {
      ["group", "teacher", "classroom"].forEach(function (entityType) {
        populateExportEntitySelect(entityType);
      });
    }

    /**
     * Returns the list of checked entity IDs for a given export entity type.
     * Input: entityType - "group" | "teacher" | "classroom"
     * Output: array of positive integer IDs
     */
    function getExportSelectionForEntity(entityType) {
      var containerId = EXPORT_ENTITY_SELECT_IDS[entityType] || null;
      var container = containerId ? document.getElementById(containerId) : null;
      if (!container) {
        return [];
      }
      return Array.from(container.querySelectorAll("input[type='checkbox']:checked"))
        .map(function (checkbox) { return Number.parseInt(checkbox.value, 10); })
        .filter(function (value) { return Number.isInteger(value) && value > 0; });
    }

    /**
     * Toggles the active CSS class on export entity card buttons to match state.exportEntityState.
     * Input: none
     * Output: void
     */
    function renderExportEntityCards() {
      document.querySelectorAll(".export-entity-card").forEach(function (button) {
        var entityType = button.dataset.exportEntity;
        var active = !!state.exportEntityState[entityType];
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", active ? "true" : "false");
      });
    }

    /**
     * Returns true when at least one export entity card or individual checkbox is selected.
     * Input: none
     * Output: boolean
     */
    function hasAnyExportSelection() {
      if (Object.values(state.exportEntityState).some(Boolean)) {
        return true;
      }
      return ["group", "teacher", "classroom"].some(function (entityType) {
        return getExportSelectionForEntity(entityType).length > 0;
      });
    }

    /**
     * Downloads a file from an API endpoint and triggers a browser download.
     * Input: endpoint - API path after "/api"
     * Output: Promise<void>; throws Error on non-OK response
     */
    async function downloadFileFromApi(endpoint) {
      var response = await window.orariooAuth.apiFetch("/api" + endpoint, { method: "GET" });
      if (!response.ok) {
        var errorData = {};
        try { errorData = await response.json(); } catch (_e) {}
        throw new Error(extractApiErrorMessage(errorData, "No se pudo exportar."));
      }
      var disposition = response.headers.get("Content-Disposition") || "";
      var match = disposition.match(/filename="?([^";]+)"?/i);
      var fileName = match ? match[1] : "horario_export";
      var blob = await response.blob();
      var url = window.URL.createObjectURL(blob);
      var link = document.createElement("a");
      link.href = url;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    }

    /**
     * Loads export entity options (teachers, classrooms, groups) in parallel with caching.
     * Input: none
     * Output: Promise<boolean> — true when all three loaded successfully
     */
    async function loadExportEntityOptions() {
      if (state.exportOptionsLoaded) {
        return true;
      }
      if (state.exportOptionsPromise) {
        return state.exportOptionsPromise;
      }
      var buildSummaryPath = window.ScheduleUtils.buildSummaryPath;
      state.exportOptionsPromise = Promise.all([
        apiJson(buildSummaryPath("/teachers/", "options")),
        apiJson(buildSummaryPath("/classrooms/", "options")),
        apiJson(buildSummaryPath("/groups/", "options")),
      ])
        .then(function (responses) {
          state.currentTeachers = responses[0].ok ? listFromPayload(responses[0].data) : [];
          state.currentClassrooms = responses[1].ok ? listFromPayload(responses[1].data) : [];
          state.currentGroups = responses[2].ok ? listFromPayload(responses[2].data) : [];
          state.exportOptionsLoaded = responses[0].ok && responses[1].ok && responses[2].ok;
          if (!state.exportOptionsLoaded) {
            showAlert("warning", "No se pudieron cargar todas las opciones de exportacion.");
          }
          return state.exportOptionsLoaded;
        })
        .catch(function () {
          state.exportOptionsLoaded = false;
          state.currentTeachers = [];
          state.currentClassrooms = [];
          state.currentGroups = [];
          showAlert("warning", "No se pudieron cargar las opciones de exportacion.");
          return false;
        })
        .finally(function () { state.exportOptionsPromise = null; });
      return state.exportOptionsPromise;
    }

    /**
     * Opens the export modal and pre-configures it for the given source and entity state flags.
     * Input: exportConfig - object with source ("generated"|"saved"), savedName, format, lockFormat
     * Output: Promise<void>
     */
    async function openExportModal(exportConfig) {
      var modal = document.getElementById("exportModal");
      var exportFormat = document.getElementById("exportFormat");
      if (!modal || !exportFormat) {
        return;
      }
      var safeConfig = exportConfig || {};
      state.currentExportSource = safeConfig.source || "generated";
      state.currentExportSavedName = String(safeConfig.savedName || "").trim();
      if (state.currentExportSource === "saved") {
        var activeName = state.currentExportSavedName || state.selectedSavedTimetableName || state.generatedSavedName;
        state.currentExportSavedName = activeName || "";
      }
      state.exportEntityState.group = false;
      state.exportEntityState.teacher = false;
      state.exportEntityState.classroom = false;
      exportFormat.value = safeConfig.format || "csv";
      exportFormat.disabled = !!safeConfig.lockFormat;
      await loadExportEntityOptions();
      populateAllExportEntitySelects();
      ["exportGroupSelect", "exportTeacherSelect", "exportClassroomSelect"].forEach(function (id) {
        var container = document.getElementById(id);
        if (!container) {
          return;
        }
        Array.from(container.querySelectorAll("input[type='checkbox']")).forEach(function (checkbox) {
          checkbox.checked = false;
        });
      });
      renderExportEntityCards();
      showModalElement(modal);
    }

    /**
     * Closes the export modal and re-enables the format selector.
     * Input: none
     * Output: void
     */
    function closeExportModal() {
      var modal = document.getElementById("exportModal");
      var exportFormat = document.getElementById("exportFormat");
      if (exportFormat) {
        exportFormat.disabled = false;
      }
      hideModalElement(modal);
    }

    /**
     * Validates the current export selection and triggers the file download.
     * Input: none
     * Output: Promise<void>; shows alerts on validation failure or API error
     */
    async function handleExportConfirm() {
      if (!hasAnyExportSelection()) {
        showAlert("error", "Marca al menos una entidad o selecciona objetos concretos para exportar.");
        return;
      }
      var exportFormat = document.getElementById("exportFormat");
      var format = exportFormat ? exportFormat.value : "csv";
      var selectedGroupIds = getExportSelectionForEntity("group");
      var selectedTeacherIds = getExportSelectionForEntity("teacher");
      var selectedClassroomIds = getExportSelectionForEntity("classroom");
      var params = new URLSearchParams();
      params.set("export_format", format);
      params.set("source", state.currentExportSource);
      params.set("selection_mode", "cards");
      params.set("group_all", state.exportEntityState.group ? "1" : "0");
      params.set("teacher_all", state.exportEntityState.teacher ? "1" : "0");
      params.set("classroom_all", state.exportEntityState.classroom ? "1" : "0");
      if (state.currentExportSource === "saved" && state.currentExportSavedName) {
        params.set("saved_timetable_name", state.currentExportSavedName);
      }
      if (selectedGroupIds.length) { params.set("group_ids", selectedGroupIds.join(",")); }
      if (selectedTeacherIds.length) { params.set("teacher_ids", selectedTeacherIds.join(",")); }
      if (selectedClassroomIds.length) { params.set("classroom_ids", selectedClassroomIds.join(",")); }
      try {
        await downloadFileFromApi("/schedules/export/?" + params.toString());
        closeExportModal();
        showAlert("success", "Exportacion completada.");
      } catch (error) {
        showAlert("error", error.message || "No se pudo exportar.");
      }
    }

    /**
     * Attaches all event listeners for the export modal (entity cards, cancel, confirm).
     * Input: none
     * Output: void
     */
    function bindExportEvents() {
      var modal = document.getElementById("exportModal");
      if (!modal) {
        return;
      }
      var cancelButton = document.getElementById("cancelExportBtn");
      if (cancelButton) {
        cancelButton.addEventListener("click", closeExportModal);
      }
      var confirmButton = document.getElementById("confirmExportBtn");
      if (confirmButton) {
        confirmButton.addEventListener("click", handleExportConfirm);
      }
      modal.querySelectorAll(".export-entity-card").forEach(function (button) {
        button.addEventListener("click", function () {
          var entityType = button.dataset.exportEntity;
          if (!entityType) {
            return;
          }
          state.exportEntityState[entityType] = !state.exportEntityState[entityType];
          renderExportEntityCards();
          var selectId = button.dataset.exportSelect;
          if (selectId) {
            var container = document.getElementById(selectId);
            if (container) {
              var nowActive = state.exportEntityState[entityType];
              container.querySelectorAll("input[type='checkbox']").forEach(function (cb) {
                cb.checked = nowActive;
              });
            }
          }
        });
      });
    }

    return {
      openExportModal: openExportModal,
      bindExportEvents: bindExportEvents,
    };
  }

  window.ScheduleExport = {
    createExportManager: createExportManager,
  };
})();
