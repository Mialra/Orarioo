/**
 * Schedule workspace: timetable generation, drag-and-drop rescheduling, filtering, and export.
 * Depends on schedule-utils.js, schedule-board.js, schedule-workspace.js, schedule-analysis.js.
 */
(function () {
  const schedulesSection = document.getElementById("schedulesSection");
  const savedSection = document.getElementById("savedSection");

  if (!schedulesSection && !savedSection) {
    return;
  }

  const errorHandler = window.OrariooErrorHandler || {};

  const generatedFilterIds = {
    courseId: "generatedWorkspaceCourseFilter",
    teacherId: "generatedWorkspaceTeacherFilter",
    classroomId: "generatedWorkspaceClassroomFilter",
    subjectId: "generatedWorkspaceSubjectFilter",
  };

  const savedFilterIds = {
    courseId: "savedWorkspaceCourseFilter",
    teacherId: "savedWorkspaceTeacherFilter",
    classroomId: "savedWorkspaceClassroomFilter",
    subjectId: "savedWorkspaceSubjectFilter",
  };

  const state = {
    currentTeachers: [],
    currentClassrooms: [],
    currentGroups: [],
    latestGeneratedSchedules: [],
    latestTCSessions: [],
    tcSessionsContext: null,
    generatedTCViewMode: false,
    savedTCViewMode: false,
    generatedUnavailability: null,
    generatedStageWindows: null,
    generatedDetailPage: 1,
    savedDetailPage: 1,
    detailPageSize: 20,
    generatedSaved: false,
    generatedSavedName: "",
    generatedTeacherWorkloadsByName: {},
    savedTeacherWorkloadsByName: {},
    generatedMoveInFlight: false,
    savedMoveInFlight: false,
    generatedDragState: {
      sourceScheduleId: null,
      sourceDay: "",
      sourceStart: "",
      sourceEnd: "",
      sourceSlotKey: "",
    },
    savedDragState: {
      sourceScheduleId: null,
      sourceDay: "",
      sourceStart: "",
      sourceEnd: "",
      sourceSlotKey: "",
    },
    savedTimetableGroups: [],
    selectedSavedTimetableIndex: null,
    selectedSavedTimetableName: null,
    currentExportSource: "generated",
    currentExportSavedName: "",
    generateModalMode: "generate",
    initialSavedRouteName: "",
    savedSummaryLoaded: false,
    savedSummaryPromise: null,
    exportOptionsLoaded: false,
    exportOptionsPromise: null,
    scheduleConfig: null,
    exportEntityState: {
      group: false,
      teacher: false,
      classroom: false,
    },
  };

  // ── Sub-module imports ─────────────────────────────────────────────────────
  const {
    normalizeForCompare,
    toIsoDateDisplay,
    toDateMillis,
    buildTeacherWorkloadsByNameFromApi,
    buildTeacherWorkloadsByNameFromSessions,
    getCollectionCount,
    buildSummaryPath,
  } = window.ScheduleUtils;

  const { renderScheduleBoard } = window.ScheduleBoard;

  const { initScheduleFilterDropdowns, syncScheduleFilterDropdown, enhanceScheduleFilterSelect } =
    window.ScheduleFilterDropdown;

  // ── Saved / export managers ────────────────────────────────────────────────
  const savedManager = window.ScheduleSaved.createSavedManager({
    state: state,
    apiJson: apiJson,
    showAlert: showAlert,
    extractApiErrorMessage: extractApiErrorMessage,
    listFromPayload: listFromPayload,
    onShowSavedWorkspace: showSavedWorkspace,
    onShowSavedPicker: showSavedPicker,
    onRenderSavedWorkspace: renderSavedWorkspace,
    onPopulateFilters: populateFiltersWithTC,
    savedFilterIds: savedFilterIds,
  });

  const exportManager = window.ScheduleExport.createExportManager({
    state: state,
    apiJson: apiJson,
    showAlert: function (type, message) {
      if (type === "error" || type === "warning") {
        showExportModalAlert(type, message);
      } else {
        showAlert(type, message);
      }
    },
    extractApiErrorMessage: extractApiErrorMessage,
    showModalElement: showModalElement,
    hideModalElement: hideModalElement,
    listFromPayload: listFromPayload,
  });

  // ── Workspace instances ────────────────────────────────────────────────────
  const generatedWorkspace = window.ScheduleWorkspace.createScheduleWorkspace({
    outputId: "generatedWorkspaceOutput",
    filterIds: generatedFilterIds,
    detailTitle: "Detalle de sesiones generadas",
    getDetailPage: function () {
      return state.generatedDetailPage;
    },
    setDetailPage: function (p) {
      state.generatedDetailPage = p;
    },
    getDetailPageSize: function () {
      return state.detailPageSize;
    },
    getMoveInFlight: function () {
      return state.generatedMoveInFlight;
    },
    setMoveInFlight: function (v) {
      state.generatedMoveInFlight = v;
    },
    getDragState: function () {
      return state.generatedDragState;
    },
    resetDragState: resetGeneratedDragState,
    getSessions: function () {
      return state.latestGeneratedSchedules;
    },
    upsertSessions: upsertGeneratedSchedules,
    getTeacherWorkloads: function () {
      return state.generatedTeacherWorkloadsByName;
    },
    setTeacherWorkloads: function (w) {
      state.generatedTeacherWorkloadsByName = w;
    },
    onDropComplete: function () {},
    showAlert: showAlert,
    apiJson: apiJson,
    getFilteredSessions: getFilteredSessions,
    populateFilters: populateFiltersWithTC,
    getUnavailability: function () {
      return state.generatedUnavailability;
    },
    getStageWindows: function () {
      return state.generatedStageWindows;
    },
  });

  const savedWorkspace = window.ScheduleWorkspace.createScheduleWorkspace({
    outputId: "savedWorkspaceOutput",
    filterIds: savedFilterIds,
    detailTitle: "Detalle de sesiones guardadas",
    getDetailPage: function () {
      return state.savedDetailPage;
    },
    setDetailPage: function (p) {
      state.savedDetailPage = p;
    },
    getDetailPageSize: function () {
      return state.detailPageSize;
    },
    getMoveInFlight: function () {
      return state.savedMoveInFlight;
    },
    setMoveInFlight: function (v) {
      state.savedMoveInFlight = v;
    },
    getDragState: function () {
      return state.savedDragState;
    },
    resetDragState: resetSavedDragState,
    getSessions: function () {
      const group = savedManager.getSelectedSavedGroup();
      return group && Array.isArray(group.sessions) ? group.sessions : [];
    },
    upsertSessions: upsertSelectedSavedSchedules,
    getTeacherWorkloads: function () {
      return state.savedTeacherWorkloadsByName;
    },
    setTeacherWorkloads: function (w) {
      state.savedTeacherWorkloadsByName = w;
    },
    onDropComplete: function () {
      savedManager.onAfterDropComplete();
    },
    showAlert: showAlert,
    apiJson: apiJson,
    getFilteredSessions: getFilteredSessions,
    populateFilters: populateFiltersWithTC,
    getUnavailability: function () {
      const group = savedManager.getSelectedSavedGroup();
      return (group && group.unavailability) || null;
    },
    getStageWindows: function () {
      const group = savedManager.getSelectedSavedGroup();
      return (group && group.stageWindows) || null;
    },
  });

  // ── Workspace state helpers ────────────────────────────────────────────────

  /**
   * Resets the generated drag state to its empty initial values.
   * Input: none
   * Output: void; mutates state.generatedDragState
   */
  function resetGeneratedDragState() {
    state.generatedDragState.sourceScheduleId = null;
    state.generatedDragState.sourceDay = "";
    state.generatedDragState.sourceStart = "";
    state.generatedDragState.sourceEnd = "";
    state.generatedDragState.sourceSlotKey = "";
  }

  /**
   * Resets the saved drag state to its empty initial values.
   * Input: none
   * Output: void; mutates state.savedDragState
   */
  function resetSavedDragState() {
    state.savedDragState.sourceScheduleId = null;
    state.savedDragState.sourceDay = "";
    state.savedDragState.sourceStart = "";
    state.savedDragState.sourceEnd = "";
    state.savedDragState.sourceSlotKey = "";
  }

  /**
   * Merges updated sessions into state.latestGeneratedSchedules by ID.
   * Input: updatedSchedules - array of session objects with id fields
   * Output: void; mutates state.latestGeneratedSchedules
   */
  function upsertGeneratedSchedules(updatedSchedules) {
    if (!Array.isArray(updatedSchedules) || !updatedSchedules.length) {
      return true;
    }
    const byId = new Map();
    updatedSchedules.forEach(function (item) {
      byId.set(String(item.id), item);
    });
    state.latestGeneratedSchedules = state.latestGeneratedSchedules.map(function (item) {
      const replacement = byId.get(String(item.id));
      return replacement ? replacement : item;
    });
  }

  /**
   * Merges updated sessions into the currently selected saved timetable group by ID.
   * Input: updatedSchedules - array of session objects with id fields
   * Output: void; mutates the selected group's sessions array and updated_at
   */
  function upsertSelectedSavedSchedules(updatedSchedules) {
    if (!Array.isArray(updatedSchedules) || !updatedSchedules.length) {
      return;
    }
    const selectedGroup = savedManager.getSelectedSavedGroup();
    if (!selectedGroup || !Array.isArray(selectedGroup.sessions)) {
      return;
    }
    const byId = new Map();
    updatedSchedules.forEach(function (item) {
      byId.set(String(item.id), item);
    });
    selectedGroup.sessions = selectedGroup.sessions.map(function (item) {
      const replacement = byId.get(String(item.id));
      return replacement ? replacement : item;
    });
    const updatedAt = selectedGroup.sessions.reduce(function (latest, session) {
      if (!session || !session.updated_at) {
        return latest;
      }
      return toDateMillis(session.updated_at) > toDateMillis(latest) ? session.updated_at : latest;
    }, selectedGroup.updated_at || "");
    if (updatedAt) {
      selectedGroup.updated_at = updatedAt;
    }
  }

  // ── Modal utilities ────────────────────────────────────────────────────────

  /**
   * Returns the Bootstrap Modal instance for the given element, or null when unavailable.
   * Input: element - DOM element with a Bootstrap modal
   * Output: Bootstrap.Modal instance or null
   */
  function getModalInstance(element) {
    if (!element || !window.bootstrap || !window.bootstrap.Modal) {
      return null;
    }
    return window.bootstrap.Modal.getOrCreateInstance(element);
  }

  /**
   * Shows a Bootstrap modal element, optionally running a callback after the animation completes.
   * Input: element - modal DOM element
   *        onShown - optional function called once the modal is visible
   * Output: void
   */
  function showModalElement(element, onShown) {
    if (!element) {
      return;
    }
    if (typeof onShown === "function") {
      element.addEventListener(
        "shown.bs.modal",
        function handleShown() {
          onShown();
        },
        { once: true },
      );
    }
    const instance = getModalInstance(element);
    if (instance) {
      instance.show();
      return;
    }
    element.classList.add("show");
    element.style.display = "block";
    element.removeAttribute("aria-hidden");
    document.body.classList.add("modal-open");
    if (typeof onShown === "function") {
      onShown();
    }
  }

  /**
   * Hides a Bootstrap modal element.
   * Input: element - modal DOM element
   * Output: void
   */
  function hideModalElement(element) {
    if (!element) {
      return;
    }
    const instance = getModalInstance(element);
    if (instance) {
      instance.hide();
      return;
    }
    element.classList.remove("show");
    element.style.display = "none";
    element.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
  }

  // ── Navigation helpers ─────────────────────────────────────────────────────

  /**
   * Returns the URL for the saved-timetables list from the savedSection data attribute.
   * Input: none
   * Output: string URL, defaulting to "/dashboard/saved/"
   */
  function getSavedListUrl() {
    if (savedSection && savedSection.dataset.savedListUrl) {
      return savedSection.dataset.savedListUrl;
    }
    return "/dashboard/saved/";
  }

  /**
   * Builds the detail URL for a specific saved timetable name.
   * Input: timetableName - string name of the timetable
   * Output: string URL, or empty string when the name is blank
   */
  function buildSavedDetailUrl(timetableName) {
    const name = String(timetableName || "").trim();
    if (!name) {
      return "";
    }
    const encodedName = encodeURIComponent(name);
    const template =
      savedSection && savedSection.dataset.savedDetailUrlTemplate ? savedSection.dataset.savedDetailUrlTemplate : "";
    if (template && template.indexOf("__SAVED_NAME__") >= 0) {
      return template.replace("__SAVED_NAME__", encodedName);
    }
    const base = getSavedListUrl();
    return base.replace(/\/?$/, "/") + encodedName + "/";
  }

  /**
   * Navigates the browser to the detail page for a saved timetable.
   * Input: timetableName - string name of the timetable
   * Output: boolean — true if navigation was triggered, false when name is blank
   */
  function navigateToSavedDetail(timetableName) {
    const url = buildSavedDetailUrl(timetableName);
    if (!url) {
      return false;
    }
    window.location.assign(url);
    return true;
  }

  /**
   * Navigates the browser to the saved-timetables list page.
   * Input: none
   * Output: boolean — true if navigation was triggered
   */
  function navigateToSavedList() {
    const url = getSavedListUrl();
    if (!url) {
      return false;
    }
    window.location.assign(url);
    return true;
  }

  // ── Alert ──────────────────────────────────────────────────────────────────

  /**
   * Returns the schedule alert banner element.
   * Input: none
   * Output: HTMLElement or null
   */
  function getAlertElement() {
    return document.getElementById("scheduleAlert");
  }

  /**
   * Displays a contextual alert banner. Errors stay visible until a later alert replaces them.
   * Input: type - "success" | "error" | "info" | "warning"
   *        message - string or error info object (rendered via errorHandler.renderAlertContent)
   */
  function showAlert(type, message) {
    const alert = getAlertElement();
    if (!alert) {
      return;
    }
    const classMap = {
      success: "alert-success",
      error: "alert-danger",
      info: "alert-info",
      warning: "alert-warning",
    };
    alert.className = "alert " + (classMap[type] || "alert-info");
    if (
      message &&
      typeof message === "object" &&
      errorHandler &&
      typeof errorHandler.renderAlertContent === "function"
    ) {
      alert.innerHTML = errorHandler.renderAlertContent(message);
    } else if (errorHandler && typeof errorHandler.escapeHtml === "function") {
      alert.innerHTML = window.OrariooErrorHandler.escapeHtml(message);
    } else {
      alert.textContent = message;
    }
    alert.classList.remove("d-none");
    window.clearTimeout(showAlert._timer);
    showAlert._timer = null;
    if (type !== "error") {
      showAlert._timer = window.setTimeout(function () {
        alert.classList.add("d-none");
      }, 4500);
    }
  }

  /**
   * Displays a contextual alert banner in the export modal.
   * Input: type - "success" | "error" | "info" | "warning"
   *        message - string or error info object (rendered via errorHandler.renderAlertContent)
   */
  function showExportModalAlert(type, message) {
    const alert = document.getElementById("export-modal-alert");
    if (!alert) {
      showAlert(type, message);
      return;
    }
    const classMap = {
      success: "alert-success",
      error: "alert-danger",
      info: "alert-info",
      warning: "alert-warning",
    };
    alert.className = "alert " + (classMap[type] || "alert-info");
    if (
      message &&
      typeof message === "object" &&
      errorHandler &&
      typeof errorHandler.renderAlertContent === "function"
    ) {
      alert.innerHTML = errorHandler.renderAlertContent(message);
    } else if (errorHandler && typeof errorHandler.escapeHtml === "function") {
      alert.innerHTML = window.OrariooErrorHandler.escapeHtml(message);
    } else {
      alert.textContent = message;
    }
    alert.classList.remove("d-none");
  }

  // ── API helpers ────────────────────────────────────────────────────────────

  /**
   * Parses an API error response into a structured error info object.
   * Input: data - API error response body
   *        fallback - fallback message string
   * Output: error info object with message, suggestions, code, and raw fields
   */
  function extractApiErrorInfo(data, fallback) {
    if (errorHandler && typeof errorHandler.parseApiError === "function") {
      return errorHandler.parseApiError(data, { fallbackMessage: fallback });
    }
    return {
      message: extractApiErrorMessage(data, fallback),
      suggestions: [],
      code: "",
      raw: data || null,
    };
  }

  /**
   * Extracts the most relevant error message string from an API error response body.
   * Input: data - API error response object or null; fallback - string shown on no match
   * Output: string error message
   */
  function extractApiErrorMessage(data, fallback) {
    if (errorHandler && typeof errorHandler.parseApiError === "function") {
      return errorHandler.parseApiError(data, { fallbackMessage: fallback }).message;
    }
    if (!data || typeof data !== "object") {
      return fallback;
    }
    if (typeof data.detail === "string" && data.detail.trim()) {
      return data.detail;
    }
    const firstValue = Object.values(data)[0];
    if (Array.isArray(firstValue) && firstValue.length) {
      return String(firstValue[0]);
    }
    if (typeof firstValue === "string" && firstValue.trim()) {
      return firstValue;
    }
    return fallback;
  }

  /**
   * Makes an authenticated JSON API request using window.orariooAuth.apiFetch.
   * Input: path - API path after "/api"; method - HTTP verb; body - optional request body
   * Output: Promise<{ok, status, data, response}>
   */
  async function apiJson(path, method, body, fetchOptions) {
    const options = Object.assign(
      {
        method: method || "GET",
        headers: { "Content-Type": "application/json" },
      },
      fetchOptions || {},
    );
    if (body !== undefined && body !== null) {
      options.body = JSON.stringify(body);
    }
    try {
      const response = await window.orariooAuth.apiFetch("/api" + path, options);
      let data = {};
      try {
        data = await response.json();
      } catch (_error) {
        data = {};
      }
      return { ok: response.ok, status: response.status, data: data, response: response };
    } catch (error) {
      return {
        ok: false,
        status: 0,
        data: { detail: error && error.message ? error.message : "Error de red" },
      };
    }
  }

  /**
   * Extracts a flat array from a paginated or plain array API response payload.
   * Input: payload - API response body (array or { results: [] })
   * Output: array of items
   */
  function listFromPayload(payload) {
    if (Array.isArray(payload)) {
      return payload;
    }
    if (payload && Array.isArray(payload.results)) {
      return payload.results;
    }
    return [];
  }

  /**
   * Sets the text content of an element by ID.
   * Input: id - element ID; value - string value to display
   * Output: void
   */
  function setText(id, value) {
    const element = document.getElementById(id);
    if (element) {
      element.textContent = String(value);
    }
  }

  // ── Subject / session type helpers ────────────────────────────────────────

  // ── Filter helpers ─────────────────────────────────────────────────────────

  /**
   * Returns the current value of a filter select by its element ID.
   * Input: selectId - string element ID
   * Output: string value or empty string
   */
  function getFilterValue(selectId) {
    const select = document.getElementById(selectId);
    return select ? select.value : "";
  }

  /**
   * Repopulates a filter select with sorted options, preserving the current selection.
   * Input: selectId - string element ID; optionValues - string array; emptyLabel - label for ""
   *        labelsByValue - optional object mapping values to display labels
   * Output: void; also triggers syncScheduleFilterDropdown on the select
   */
  function setSelectOptions(selectId, optionValues, emptyLabel, labelsByValue) {
    const select = document.getElementById(selectId);
    if (!select) {
      return;
    }
    const currentValue = select.value;
    const values = optionValues
      .slice()
      .filter(Boolean)
      .sort(function (left, right) {
        return left.localeCompare(right, "es");
      });
    select.innerHTML =
      '<option value="">' +
      emptyLabel +
      "</option>" +
      values
        .map(function (value) {
          const label = labelsByValue && labelsByValue[value] ? labelsByValue[value] : value;
          return '<option value="' + value + '">' + label + "</option>";
        })
        .join("");
    if (currentValue && values.indexOf(currentValue) >= 0) {
      select.value = currentValue;
    }
    syncScheduleFilterDropdown(select);
  }

  /**
   * Rebuilds the workspace filter dropdowns from the unique entity values in the session list.
   * Input: sessions - array of raw API session objects
   *        filterIds - object mapping entity types to filter select IDs
   *        options - object with optional preserveSelection boolean
   */
  function populateWorkspaceFiltersFromSessions(sessions, filterIds, options) {
    const safeOptions = options || {};
    const courseNames = Array.from(
      new Set(
        (sessions || [])
          .map(function (s) {
            return s.group_name;
          })
          .filter(Boolean),
      ),
    );
    const teacherNames = Array.from(
      new Set(
        (sessions || [])
          .map(function (s) {
            return s.teacher_name;
          })
          .filter(Boolean),
      ),
    );
    const teacherWorkloadsByName =
      safeOptions.teacherWorkloadsByName || buildTeacherWorkloadsByNameFromSessions(sessions);
    const teacherLabelsByName = teacherNames.reduce(function (acc, teacherName) {
      const workload = teacherWorkloadsByName && teacherWorkloadsByName[teacherName];
      const hoursLabel =
        workload && Number.isFinite(Number(workload)) && Number(workload) > 0
          ? " (" + window.ScheduleUtils.formatTeacherWorkloadHours(workload) + ")"
          : "";
      acc[teacherName] = teacherName + hoursLabel;
      return acc;
    }, {});
    const classroomNames = Array.from(
      new Set(
        (sessions || [])
          .map(function (s) {
            return s.classroom_name;
          })
          .filter(Boolean),
      ),
    );
    const subjectNames = Array.from(
      new Set(
        (sessions || [])
          .map(function (s) {
            return s.subject_name;
          })
          .filter(Boolean),
      ),
    );
    setSelectOptions(filterIds.courseId, courseNames, "Todos los cursos");
    setSelectOptions(filterIds.teacherId, teacherNames, "Todos los profesores", teacherLabelsByName);
    setSelectOptions(filterIds.classroomId, classroomNames, "Todas las aulas");
    setSelectOptions(filterIds.subjectId, subjectNames, "Todas las asignaturas");
  }

  // Reference Monday (2024-01-01 = Monday) used to convert TC day+time to UTC datetime strings.
  var TC_REFERENCE_MONDAY_MS = Date.UTC(2024, 0, 1); // 2024-01-01 00:00:00 UTC

  /**
   * Converts a TCSession API object to a pseudo-schedule object that renderScheduleBoard can render.
   * TC sessions have day (0-4) + TimeField; the board expects UTC ISO datetime strings.
   * Input: tcSession - TCSession object from GET /tc-sessions/
   * Output: pseudo-schedule object with is_tc: true and fake ISO datetimes
   */
  function tcSessionToScheduleFormat(tcSession) {
    var dayOffsetMs = tcSession.day * 24 * 60 * 60 * 1000;
    var timeParts = (tcSession.start_time || "00:00:00").split(":");
    var endParts = (tcSession.end_time || "00:00:00").split(":");
    var startMs =
      TC_REFERENCE_MONDAY_MS +
      dayOffsetMs +
      parseInt(timeParts[0], 10) * 3600000 +
      parseInt(timeParts[1], 10) * 60000;
    var endMs =
      TC_REFERENCE_MONDAY_MS +
      dayOffsetMs +
      parseInt(endParts[0], 10) * 3600000 +
      parseInt(endParts[1], 10) * 60000;
    return {
      id: tcSession.id,
      teacher: tcSession.teacher,
      teacher_name: tcSession.teacher_name || "-",
      group: null,
      group_name: "-",
      classroom: null,
      classroom_name: "-",
      subject: null,
      subject_name: "Guardia TC",
      start_time: new Date(startMs).toISOString(),
      end_time: new Date(endMs).toISOString(),
      is_tc: true,
    };
  }

  /**
   * Returns TC sessions to overlay on the board based on active filters.
   * Hidden when filtering by course, classroom or subject (those views don't include TC).
   * Filtered by teacher when a teacher filter is active; all TC sessions otherwise.
   * Input: filterIds - workspace filter IDs object
   * Output: filtered array of pseudo-schedule TC session objects, or []
   */
  function getFilteredTCSessions(filterIds) {
    if (getFilterValue(filterIds.courseId) || getFilterValue(filterIds.classroomId) || getFilterValue(filterIds.subjectId)) {
      return [];
    }
    var pool = state.latestTCSessions || [];
    var selectedTeacher = getFilterValue(filterIds.teacherId);
    if (selectedTeacher) {
      return pool
        .filter(function (tc) {
          return normalizeForCompare(tc.teacher_name) === normalizeForCompare(selectedTeacher);
        })
        .map(tcSessionToScheduleFormat);
    }
    return pool.map(tcSessionToScheduleFormat);
  }

  /**
   * Adds TC session minutes to a base workload-by-name object and returns a new merged object.
   * Input: baseWorkloads - object { teacherName: hoursNumber } from regular sessions
   *        tcSessions    - array of raw TC session objects from state.latestTCSessions
   * Output: new object with TC hours added on top of regular hours
   */
  function mergeTCWorkloads(baseWorkloads, tcSessions) {
    var merged = Object.assign({}, baseWorkloads);
    (tcSessions || []).forEach(function (tc) {
      var name = String(tc.teacher_name || "").trim();
      if (!name) {
        return;
      }
      var startParts = (tc.start_time || "00:00:00").split(":");
      var endParts = (tc.end_time || "00:00:00").split(":");
      var durationMinutes =
        (parseInt(endParts[0], 10) * 60 + parseInt(endParts[1], 10)) -
        (parseInt(startParts[0], 10) * 60 + parseInt(startParts[1], 10));
      if (durationMinutes > 0) {
        merged[name] = (merged[name] || 0) + durationMinutes / 60;
      }
    });
    return merged;
  }

  /**
   * Re-populates both workspace filter dropdowns with workloads that include TC hours.
   * Call this whenever state.latestTCSessions changes.
   * Input: none
   * Output: void
   */
  function refreshFilterWorkloads() {
    const generatedWorkloads = mergeTCWorkloads(
      state.generatedTeacherWorkloadsByName,
      state.latestTCSessions,
    );
    populateWorkspaceFiltersFromSessions(state.latestGeneratedSchedules, generatedFilterIds, {
      teacherWorkloadsByName: generatedWorkloads,
    });
    const savedGroup = savedManager.getSelectedSavedGroup();
    if (savedGroup) {
      const savedWorkloads = mergeTCWorkloads(
        state.savedTeacherWorkloadsByName,
        state.latestTCSessions,
      );
      populateWorkspaceFiltersFromSessions(
        Array.isArray(savedGroup.sessions) ? savedGroup.sessions : [],
        savedFilterIds,
        { teacherWorkloadsByName: savedWorkloads },
      );
    }
  }

  /**
   * TC-aware wrapper for populateWorkspaceFiltersFromSessions.
   * Automatically merges latestTCSessions into teacherWorkloadsByName before populating.
   * Use this everywhere instead of calling populateWorkspaceFiltersFromSessions directly
   * (except inside refreshFilterWorkloads which already does the merge manually).
   */
  function populateFiltersWithTC(sessions, filterIds, options) {
    var opts = options || {};
    var base = opts.teacherWorkloadsByName || {};
    populateWorkspaceFiltersFromSessions(
      sessions,
      filterIds,
      Object.assign({}, opts, { teacherWorkloadsByName: mergeTCWorkloads(base, state.latestTCSessions) }),
    );
  }

  /**
   * Returns the subset of sessions matching all active filter dropdown selections.
   * Input: sessions - array of raw API session objects
   *        filterIds - object mapping entity types to filter select IDs
   * Output: filtered array of session objects
   */
  function getFilteredSessions(sessions, filterIds) {
    const selectedCourse = getFilterValue(filterIds.courseId);
    const selectedTeacher = getFilterValue(filterIds.teacherId);
    const selectedClassroom = getFilterValue(filterIds.classroomId);
    const selectedSubject = getFilterValue(filterIds.subjectId);
    return (sessions || []).filter(function (session) {
      if (selectedCourse && normalizeForCompare(session.group_name) !== normalizeForCompare(selectedCourse)) {
        return false;
      }
      if (selectedTeacher && normalizeForCompare(session.teacher_name) !== normalizeForCompare(selectedTeacher)) {
        return false;
      }
      if (selectedClassroom && normalizeForCompare(session.classroom_name) !== normalizeForCompare(selectedClassroom)) {
        return false;
      }
      if (!selectedSubject) {
        return true;
      }
      return normalizeForCompare(session.subject_name) === normalizeForCompare(selectedSubject);
    });
  }

  // ── Workspace section visibility ───────────────────────────────────────────

  /**
   * Updates the generated workspace header badge and save button to reflect saved/draft state.
   * Input: none
   * Output: void; mutates badge text/class and save button disabled state
   */
  function updateGeneratedWorkspaceHeader() {
    const count = Array.isArray(state.latestGeneratedSchedules) ? state.latestGeneratedSchedules.length : 0;
    const badge = document.getElementById("generatedWorkspaceStateBadge");
    if (badge) {
      badge.textContent = state.generatedSaved ? "Guardado" : "Borrador";
      badge.classList.toggle("schedule-pill-draft", !state.generatedSaved);
      badge.classList.toggle("schedule-pill-saved", state.generatedSaved);
    }
    const saveButton = document.getElementById("generatedWorkspaceSaveBtn");
    const saveLabel = document.getElementById("generatedWorkspaceSaveBtnLabel");
    if (saveButton) {
      saveButton.disabled = state.generatedSaved || count === 0;
    }
    if (saveLabel) {
      saveLabel.textContent = state.generatedSaved ? "Guardado" : "Guardar";
    }
  }

  /**
   * Updates the saved workspace title element with the selected timetable name.
   * Input: selectedGroup - timetable group object or null
   * Output: void
   */
  function updateSavedWorkspaceHeader(selectedGroup) {
    const title = document.getElementById("savedWorkspaceTitle");
    if (title) {
      title.textContent = selectedGroup ? "Horario Escolar - " + selectedGroup.name : "Horario Guardado";
    }
  }

  /**
   * Toggles the d-none class on a section element to show or hide it.
   * Input: sectionId - string element ID; shouldShow - boolean
   * Output: void
   */
  function toggleSection(sectionId, shouldShow) {
    const section = document.getElementById(sectionId);
    if (!section) {
      return;
    }
    section.classList.toggle("d-none", !shouldShow);
  }

  /**
   * Shows the generated workspace section and hides the landing section.
   * Input: none
   * Output: void
   */
  function showGeneratedWorkspace() {
    toggleSection("generatedLandingSection", false);
    toggleSection("generatedProgressSection", false);
    toggleSection("generatedWorkspaceSection", true);
  }

  /**
   * Shows the generated landing section and hides the workspace section.
   * Input: none
   * Output: void
   */
  function showGeneratedLanding() {
    toggleSection("generatedLandingSection", true);
    toggleSection("generatedProgressSection", false);
    toggleSection("generatedWorkspaceSection", false);
  }

  // ── Generation progress animation ─────────────────────────────────────────
  var _genProgressPhase2Timer = null;
  var _genProgressPhase1Timer = null;
  var GEN_PHASE1_FAKE_MS = 5000; // estimated Phase 1 duration shown before Phase 2 starts

  function _genProgressSetPhase1Active() {
    var step1 = document.getElementById("genProgressStep1");
    var icon1 = document.getElementById("genProgressIcon1");
    var bar1 = document.getElementById("genProgressBar1");
    if (step1) {
      step1.classList.remove("gen-progress-step--pending");
    }
    if (icon1) {
      icon1.className = "gen-progress-step-icon gen-progress-step-icon--active";
      icon1.innerHTML = "<div class='gen-spinner'></div>";
    }
    if (bar1) {
      bar1.className = "progress-bar progress-bar-striped progress-bar-animated";
      bar1.style.width = "100%";
    }
  }

  function _genProgressSetPhase1Done() {
    var icon1 = document.getElementById("genProgressIcon1");
    var bar1 = document.getElementById("genProgressBar1");
    if (icon1) {
      icon1.className = "gen-progress-step-icon gen-progress-step-icon--done";
      icon1.innerHTML = "<i data-lucide='check' style='width:1rem;height:1rem;color:#fff'></i>";
      if (window.lucide) {
        window.lucide.createIcons();
      }
    }
    if (bar1) {
      bar1.className = "progress-bar bg-primary";
      bar1.style.width = "100%";
    }
  }

  function _genProgressStartPhase2(timeoutMinutes) {
    var step2 = document.getElementById("genProgressStep2");
    var icon2 = document.getElementById("genProgressIcon2");
    var bar2Wrap = document.getElementById("genProgressBar2Wrap");
    var bar2 = document.getElementById("genProgressBar2");
    var label = document.getElementById("genProgressTimeLabel");

    if (step2) {
      step2.classList.remove("gen-progress-step--pending");
    }
    if (label) {
      label.textContent = "(" + timeoutMinutes + " min)";
    }
    if (icon2) {
      icon2.className = "gen-progress-step-icon gen-progress-step-icon--active";
      icon2.innerHTML = "<div class='gen-spinner'></div>";
    }
    if (bar2Wrap) {
      bar2Wrap.classList.remove("d-none");
    }

    var totalMs = timeoutMinutes * 60 * 1000;
    var startMs = Date.now();
    _genProgressPhase2Timer = setInterval(function () {
      var pct = Math.min(100, ((Date.now() - startMs) / totalMs) * 100);
      if (bar2) {
        bar2.style.width = pct + "%";
        bar2.setAttribute("aria-valuenow", Math.round(pct));
      }
      if (pct >= 100) {
        clearInterval(_genProgressPhase2Timer);
        _genProgressPhase2Timer = null;
        _genProgressSetPhase2Done();
        _genProgressStartPhase3();
      }
    }, 200);
  }

  /**
   * Marks Phase 2 as complete: switches the icon to a checkmark and freezes the bar solid at 100%.
   * Input: none
   * Output: void
   */
  function _genProgressSetPhase2Done() {
    var icon2 = document.getElementById("genProgressIcon2");
    var bar2 = document.getElementById("genProgressBar2");
    if (icon2) {
      icon2.className = "gen-progress-step-icon gen-progress-step-icon--done";
      icon2.innerHTML = "<i data-lucide='check' style='width:1rem;height:1rem;color:#fff'></i>";
      if (window.lucide) {
        window.lucide.createIcons();
      }
    }
    if (bar2) {
      bar2.className = "progress-bar bg-success";
      bar2.style.width = "100%";
    }
  }

  /**
   * Activates Phase 3: shows the indeterminate purple bar while the backend finalizes and polling responds.
   * Input: none
   * Output: void
   */
  function _genProgressStartPhase3() {
    var step3 = document.getElementById("genProgressStep3");
    var icon3 = document.getElementById("genProgressIcon3");
    var bar3Wrap = document.getElementById("genProgressBar3Wrap");
    if (step3) {
      step3.classList.remove("gen-progress-step--pending");
    }
    if (icon3) {
      icon3.className = "gen-progress-step-icon gen-progress-step-icon--active";
      icon3.innerHTML = "<div class='gen-spinner'></div>";
    }
    if (bar3Wrap) {
      bar3Wrap.classList.remove("d-none");
    }
  }

  function startGenerationProgress(timeoutMinutes) {
    clearInterval(_genProgressPhase2Timer);
    clearTimeout(_genProgressPhase1Timer);
    _genProgressPhase2Timer = null;
    _genProgressPhase1Timer = null;

    // Reset step 2 to pending state
    var step2 = document.getElementById("genProgressStep2");
    var icon2 = document.getElementById("genProgressIcon2");
    var bar2Wrap = document.getElementById("genProgressBar2Wrap");
    var bar2 = document.getElementById("genProgressBar2");
    var label = document.getElementById("genProgressTimeLabel");
    if (step2) {
      step2.classList.add("gen-progress-step--pending");
    }
    if (icon2) {
      icon2.className = "gen-progress-step-icon";
      icon2.innerHTML = "<span class='gen-progress-step-num'>2</span>";
    }
    if (bar2Wrap) {
      bar2Wrap.classList.add("d-none");
    }
    if (bar2) {
      bar2.className = "progress-bar bg-success";
      bar2.style.width = "0%";
    }
    if (label) {
      label.textContent = "";
    }

    // Reset step 3 to pending state
    var step3 = document.getElementById("genProgressStep3");
    var icon3 = document.getElementById("genProgressIcon3");
    var bar3Wrap = document.getElementById("genProgressBar3Wrap");
    if (step3) {
      step3.classList.add("gen-progress-step--pending");
    }
    if (icon3) {
      icon3.className = "gen-progress-step-icon";
      icon3.innerHTML = "<span class='gen-progress-step-num'>3</span>";
    }
    if (bar3Wrap) {
      bar3Wrap.classList.add("d-none");
    }

    _genProgressSetPhase1Active();
    toggleSection("generatedLandingSection", false);
    toggleSection("generatedProgressSection", true);
    toggleSection("generatedWorkspaceSection", false);

    _genProgressPhase1Timer = setTimeout(function () {
      _genProgressSetPhase1Done();
      _genProgressStartPhase2(timeoutMinutes);
    }, GEN_PHASE1_FAKE_MS);
  }

  function stopGenerationProgress() {
    clearInterval(_genProgressPhase2Timer);
    clearTimeout(_genProgressPhase1Timer);
    _genProgressPhase2Timer = null;
    _genProgressPhase1Timer = null;
    toggleSection("generatedProgressSection", false);
  }

  /**
   * Shows the saved workspace section and hides the saved picker section.
   * Input: none
   * Output: void
   */
  function showSavedWorkspace() {
    toggleSection("savedPickerSection", false);
    toggleSection("savedWorkspaceSection", true);
  }

  /**
   * Shows the saved picker section, hides the workspace, and clears drag state.
   * Input: none
   * Output: void
   */
  function showSavedPicker() {
    if (state.tcSessionsContext !== "") {
      state.tcSessionsContext = "";
      state.latestTCSessions = [];
      if (state.latestGeneratedSchedules.length > 0) {
        apiJson("/tc-sessions/").then(function (res) {
          if (res.ok) {
            state.latestTCSessions = (res.data && (res.data.results || res.data)) || [];
            refreshFilterWorkloads();
          }
        });
      }
    }
    toggleSection("savedPickerSection", true);
    toggleSection("savedWorkspaceSection", false);
    savedWorkspace.clearDropFeedback();
    resetSavedDragState();
  }

  // ── Board rendering ────────────────────────────────────────────────────────

  /**
   * Re-renders the generated-schedule board and detail table based on active filters.
   */
  function renderGeneratedWorkspace() {
    updateGeneratedWorkspaceHeader();
    const tcBtn = document.getElementById("generatedWorkspaceTCBtn");
    var boardSessions;
    var tcSessions;
    var enableTcCreate;
    if (state.generatedTCViewMode) {
      boardSessions = [];
      tcSessions = (state.latestTCSessions || []).map(tcSessionToScheduleFormat);
      enableTcCreate = false;
      if (tcBtn) {
        tcBtn.classList.add("schedule-toolbar-btn-tc--active");
      }
    } else {
      boardSessions = getFilteredSessions(state.latestGeneratedSchedules, generatedFilterIds);
      tcSessions = getFilteredTCSessions(generatedFilterIds);
      enableTcCreate = !!getFilterValue(generatedFilterIds.teacherId);
      if (tcBtn) {
        tcBtn.classList.remove("schedule-toolbar-btn-tc--active");
      }
    }
    const detail = renderScheduleBoard(boardSessions.concat(tcSessions), "generatedWorkspaceOutput", {
      detailTitle: "Detalle de sesiones generadas",
      detailPage: state.generatedDetailPage,
      detailPageSize: state.detailPageSize,
      enableDragDrop: !state.generatedTCViewMode,
      teacherWorkloadsByName: state.generatedTeacherWorkloadsByName,
      scheduleConfig: state.scheduleConfig,
      enableTcCreate: enableTcCreate,
    });
    state.generatedDetailPage = detail && detail.currentPage ? detail.currentPage : 1;
    if (window.orariooAuth && typeof window.orariooAuth.initLucideIcons === "function") {
      window.orariooAuth.initLucideIcons();
    }
  }

  /**
   * Re-renders the saved-schedule board and detail table for the currently selected timetable.
   */
  function renderSavedWorkspace() {
    const selectedGroup = savedManager.getSelectedSavedGroup();
    updateSavedWorkspaceHeader(selectedGroup);
    const output = document.getElementById("savedWorkspaceOutput");
    if (!selectedGroup || !output) {
      if (output) {
        output.innerHTML = "";
        output.style.display = "none";
      }
      return;
    }

    const currentTimetableName = String(selectedGroup.name || "");
    if (state.tcSessionsContext !== currentTimetableName) {
      state.tcSessionsContext = currentTimetableName;
      state.latestTCSessions = [];
      if (currentTimetableName) {
        apiJson("/tc-sessions/?timetable_name=" + encodeURIComponent(currentTimetableName)).then(function (res) {
          if (res.ok) {
            state.latestTCSessions = (res.data && (res.data.results || res.data)) || [];
            refreshFilterWorkloads();
            renderSavedWorkspace();
          }
        });
      }
      return;
    }

    const sourceSessions = Array.isArray(selectedGroup.sessions) ? selectedGroup.sessions : [];
    const filtered = getFilteredSessions(sourceSessions, savedFilterIds);
    const tcBtn = document.getElementById("savedWorkspaceTCBtn");
    var boardSessions;
    var tcSessions;
    var enableTcCreate;
    if (state.savedTCViewMode) {
      boardSessions = [];
      tcSessions = (state.latestTCSessions || []).map(tcSessionToScheduleFormat);
      enableTcCreate = false;
      if (tcBtn) {
        tcBtn.classList.add("schedule-toolbar-btn-tc--active");
      }
    } else {
      boardSessions = filtered;
      tcSessions = getFilteredTCSessions(savedFilterIds);
      enableTcCreate = !!getFilterValue(savedFilterIds.teacherId);
      if (tcBtn) {
        tcBtn.classList.remove("schedule-toolbar-btn-tc--active");
      }
    }
    const detail = renderScheduleBoard(boardSessions.concat(tcSessions), "savedWorkspaceOutput", {
      detailTitle: "Detalle de sesiones guardadas",
      detailPage: state.savedDetailPage,
      detailPageSize: state.detailPageSize,
      enableDragDrop: !state.savedTCViewMode,
      teacherWorkloadsByName: state.savedTeacherWorkloadsByName,
      scheduleConfig: state.scheduleConfig,
      enableTcCreate: enableTcCreate,
    });
    state.savedDetailPage = detail && detail.currentPage ? detail.currentPage : 1;
    if (window.orariooAuth && typeof window.orariooAuth.initLucideIcons === "function") {
      window.orariooAuth.initLucideIcons();
    }
  }

  // ── Save generated modal ───────────────────────────────────────────────────

  /**
   * Opens the "save generated schedule" modal and pre-fills the name input.
   * Input: none
   * Output: void; shows error alert if no generated schedule exists
   */
  function openSaveGeneratedModal() {
    if (!state.latestGeneratedSchedules.length) {
      showAlert("error", "No hay un horario generado para guardar.");
      return;
    }
    if (state.generatedSaved) {
      showAlert("info", "Este horario ya esta guardado.");
      return;
    }
    const modal = document.getElementById("saveGeneratedModal");
    const input = document.getElementById("saveGeneratedNameInput");
    if (!modal || !input) {
      showAlert("error", "No se pudo abrir el formulario de guardado.");
      return;
    }
    savedManager.ensureSavedSchedulesLoaded().catch(function () {
      return false;
    });
    input.value = state.generatedSavedName || buildDefaultTimetableName();
    showModalElement(modal, function () {
      input.focus();
      input.select();
    });
  }

  /**
   * Closes the "save generated schedule" modal.
   * Input: none
   * Output: void
   */
  function closeSaveGeneratedModal() {
    hideModalElement(document.getElementById("saveGeneratedModal"));
  }

  /**
   * Opens the schedule generation/regeneration modal in the specified mode.
   * Input: mode - "generate" to start fresh, "regenerate" to replace the current schedule
   */
  function openGenerateModal(mode) {
    const modal = document.getElementById("scheduleGenerateModal");
    const title = document.getElementById("scheduleGenerateModalTitle");
    const text = document.getElementById("scheduleGenerateModalText");
    const hintText = document.getElementById("scheduleGenerateModalHintText");
    const confirmButton = document.getElementById("confirmScheduleGenerateBtn");
    if (!modal || !title || !text || !confirmButton) {
      handleGenerate();
      return;
    }
    state.generateModalMode = mode === "regenerate" ? "regenerate" : "generate";
    if (state.generateModalMode === "regenerate") {
      title.textContent = "Regenerar horario";
      text.textContent = state.generatedSaved
        ? "Se generará una nueva propuesta en borrador. El horario guardado actual seguirá disponible."
        : "Se generará una nueva propuesta y reemplazará el borrador actual que estás viendo.";
      if (hintText) {
        hintText.textContent =
          "Usará las restricciones actuales y puede tardar unos segundos si el problema es complejo.";
      }
      confirmButton.textContent = "Regenerar horario";
    } else {
      title.textContent = "Generar horario";
      text.textContent = "Se lanzará una nueva generación con las restricciones actuales.";
      if (hintText) {
        hintText.textContent = "Este proceso puede tardar bastante tiempo si el problema es complejo.";
      }
      confirmButton.textContent = "Generar horario";
    }
    resetGenerationTimeoutControls();
    showModalElement(modal, function () {
      confirmButton.focus();
      if (window.orariooAuth && typeof window.orariooAuth.initBootstrapTooltips === "function") {
        window.orariooAuth.initBootstrapTooltips();
      }
    });
  }

  /**
   * Closes the schedule generation modal.
   * Input: none
   * Output: void
   */
  function closeGenerateModal() {
    hideModalElement(document.getElementById("scheduleGenerateModal"));
  }

  /**
   * Builds a default timetable name using the current local date and time.
   * Input: none
   * Output: string like "Horario 20/04/2026 14:35"
   */
  function buildDefaultTimetableName() {
    const now = new Date();
    return (
      "Horario " +
      now.toLocaleDateString("es-ES") +
      " " +
      now.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })
    );
  }

  /**
   * Validates the save form, calls the API, updates state, and navigates to the saved list.
   * Input: none
   * Output: Promise<void>; shows alert on success or error
   */
  async function handleSaveGeneratedConfirm() {
    if (!state.latestGeneratedSchedules.length) {
      showAlert("error", "No hay un horario generado para guardar.");
      return;
    }
    if (state.generatedSaved) {
      showAlert("info", "Este horario ya esta guardado.");
      return;
    }
    const nameInput = document.getElementById("saveGeneratedNameInput");
    const confirmButton = document.getElementById("confirmSaveGeneratedBtn");
    const timetableName = String(nameInput ? nameInput.value : "").trim();
    if (!timetableName) {
      showAlert("warning", "Indica un nombre para guardar el horario.");
      if (nameInput) {
        nameInput.focus();
      }
      return;
    }
    const hasSavedSummary = await savedManager.ensureSavedSchedulesLoaded().catch(function () {
      return false;
    });
    if (hasSavedSummary && savedManager.hasSavedTimetableNameCollision(timetableName)) {
      showAlert(
        "error",
        "Ya existe un horario guardado con ese nombre. Usa otro nombre o elimina el horario anterior.",
      );
      if (nameInput) {
        nameInput.focus();
        nameInput.select();
      }
      return;
    }
    const scheduleIds = state.latestGeneratedSchedules
      .map(function (session) {
        return session.id;
      })
      .filter(function (id) {
        return Number.isInteger(id);
      });
    if (!scheduleIds.length) {
      showAlert("error", "No se encontraron sesiones para guardar.");
      return;
    }
    if (confirmButton) {
      confirmButton.disabled = true;
    }
    const result = await apiJson("/schedules/save-generated/", "POST", {
      timetable_name: timetableName,
      schedule_ids: scheduleIds,
      user_ids: [],
    });
    if (confirmButton) {
      confirmButton.disabled = false;
    }
    if (!result.ok) {
      showAlert("error", extractApiErrorMessage(result.data, "No se pudo guardar el horario generado."));
      if (nameInput) {
        nameInput.focus();
        nameInput.select();
      }
      return;
    }
    closeSaveGeneratedModal();
    state.generatedSaved = true;
    state.generatedSavedName = timetableName;
    state.latestGeneratedSchedules = (result.data && result.data.schedules) || state.latestGeneratedSchedules;
    state.generatedTeacherWorkloadsByName =
      result.data && Array.isArray(result.data.teacher_workloads)
        ? buildTeacherWorkloadsByNameFromApi(result.data.teacher_workloads)
        : buildTeacherWorkloadsByNameFromSessions(state.latestGeneratedSchedules);
    refreshFilterWorkloads();
    renderGeneratedWorkspace();
    savedManager.rememberSavedTimetableSummary(timetableName, state.latestGeneratedSchedules);
    showAlert("success", 'Horario guardado como "' + timetableName + '".');
  }

  /**
   * Opens the save-generated modal; called from the Save toolbar button.
   * Input: none
   * Output: void
   */
  function handleSaveGenerated() {
    openSaveGeneratedModal();
  }

  /**
   * Disables or enables the generate/regenerate action buttons during generation.
   * Input: disabled - boolean
   * Output: void
   */
  function setGenerateActionButtonsDisabled(disabled) {
    ["generateBtn", "generatedWorkspaceRegenerateBtn", "confirmScheduleGenerateBtn"].forEach(function (id) {
      const button = document.getElementById(id);
      if (button) {
        button.disabled = disabled;
      }
    });
  }

  /**
   * Restores the generation timeout input to the default value.
   * Input: none
   * Output: void
   */
  function resetGenerationTimeoutControls() {
    var timeoutInput = document.getElementById("gen-timeout-minutes");
    if (timeoutInput) {
      timeoutInput.value = "15";
    }
  }

  /**
   * Reads the state of the generation options checkboxes and returns an options object.
   * Input: none
   * Output: object with boolean fields for each generation option
   */
  function _readGenerationOptions() {
    function checked(id) {
      var el = document.getElementById(id);
      return el ? el.checked : true;
    }
    var dutyEl = document.getElementById("gen-opt-teachers-on-duty");
    var seedEl = document.getElementById("gen-opt-seed");
    var seedValue = seedEl && seedEl.value.trim() !== "" ? parseInt(seedEl.value, 10) : null;
    var opts = {
      enable_no_intraday_gaps: checked("gen-opt-no-intraday-gaps"),
      enable_subject_unavailable_times: checked("gen-opt-subject-unavailable"),
      enable_teacher_unavailable_times: checked("gen-opt-teacher-unavailable"),
      enable_subject_time_preferences: checked("gen-opt-subject-preferences"),
      enable_teacher_time_preferences: checked("gen-opt-teacher-preferences"),
      enable_subject_day_spread: checked("gen-opt-day-spread"),
      enable_teacher_gap_minimization: checked("gen-opt-gap-minimization"),
      teachers_on_duty: dutyEl ? parseInt(dutyEl.value, 10) || 0 : 0,
    };
    if (seedValue !== null && !isNaN(seedValue)) {
      opts.seed = seedValue;
    }
    return opts;
  }

  /**
   * Reads the timeout minutes input and returns the generation payload fragment.
   * Input: none
   * Output: object with timeout_minutes from the input field
   */
  function readGenerationTimeoutOption() {
    var timeoutInput = document.getElementById("gen-timeout-minutes");
    return {
      timeout_minutes: timeoutInput ? timeoutInput.value : "15",
    };
  }

  /**
   * Resolves a teacher name to its numeric ID from the latest generated sessions.
   * Input: teacherName - string
   * Output: integer teacher ID, or null if not found
   */
  function resolveTeacherId(teacherName) {
    const savedGroup = savedManager.getSelectedSavedGroup();
    const savedSessions = savedGroup && Array.isArray(savedGroup.sessions) ? savedGroup.sessions : [];
    const allSessions = (state.latestGeneratedSchedules || [])
      .concat(savedSessions)
      .concat(state.latestTCSessions || []);
    const found = allSessions.find(function (s) {
      return normalizeForCompare(s.teacher_name) === normalizeForCompare(teacherName);
    });
    return found ? found.teacher : null;
  }

  /**
   * Creates a TC session for the active teacher at the given cell slot.
   * Input: day - weekday name string (e.g. "Lunes"), startHm - "HH:MM", endHm - "HH:MM",
   *        filterIds - workspace filter IDs object
   * Output: Promise<void>
   */
  async function handleTCSessionCreate(day, startHm, endHm, filterIds) {
    const teacherName = getFilterValue(filterIds.teacherId);
    if (!teacherName) {
      return;
    }
    const teacherId = resolveTeacherId(teacherName);
    if (!teacherId) {
      showAlert("error", "No se pudo identificar al profesor seleccionado.");
      return;
    }
    const dayIndex = { Lunes: 0, Martes: 1, "Miércoles": 2, Jueves: 3, Viernes: 4 }[day];
    if (dayIndex === undefined) {
      return;
    }
    const result = await apiJson("/tc-sessions/create/", "POST", {
      teacher: teacherId,
      day: dayIndex,
      start_time: startHm + ":00",
      end_time: endHm + ":00",
    });
    if (!result.ok) {
      const msg = (result.data && result.data.detail) || "No se pudo crear la guardia TC.";
      showAlert("error", msg);
      return;
    }
    const created = result.data && result.data.tc_session;
    if (created) {
      state.latestTCSessions = (state.latestTCSessions || []).concat([created]);
    }
    if (result.data && result.data.warning) {
      showAlert("warning", result.data.warning);
    }
    refreshFilterWorkloads();
    renderGeneratedWorkspace();
    renderSavedWorkspace();
  }

  /**
   * Deletes a TC session by ID, updates state, and re-renders both workspaces.
   * Input: tcSessionId - integer PK of the TCSession to delete
   * Output: Promise<void>
   */
  async function handleTCSessionDelete(tcSessionId) {
    if (!tcSessionId) {
      return;
    }
    const result = await apiJson("/tc-sessions/" + tcSessionId + "/", "DELETE");
    if (!result.ok) {
      showAlert("error", "No se pudo eliminar la guardia TC.");
      return;
    }
    state.latestTCSessions = (state.latestTCSessions || []).filter(function (tc) {
      return tc.id !== tcSessionId;
    });
    refreshFilterWorkloads();
    renderGeneratedWorkspace();
    renderSavedWorkspace();
  }

  /**
   * Calls the schedule generation API, updates state, and renders the workspace on success.
   * Input: none
   * Output: Promise<void>; shows error alert and landing view on failure
   */
  async function handleGenerate() {
    setGenerateActionButtonsDisabled(true);
    generatedWorkspace.clearDropFeedback();
    resetGeneratedDragState();
    const timeoutOpt = readGenerationTimeoutOption();
    const payload = Object.assign({}, _readGenerationOptions(), timeoutOpt);
    startGenerationProgress(parseInt(timeoutOpt.timeout_minutes, 10));

    var startResult = await apiJson("/schedules/generate/", "POST", payload, { _skipSpinner: true });
    if (!startResult.ok) {
      stopGenerationProgress();
      setGenerateActionButtonsDisabled(false);
      state.latestGeneratedSchedules = [];
      state.generatedSaved = false;
      state.generatedSavedName = "";
      state.generatedMoveInFlight = false;
      showGeneratedLanding();
      showAlert("error", extractApiErrorInfo(startResult.data, "No se pudo iniciar la generación."));
      return;
    }

    var jobId = startResult.data && startResult.data.job_id;
    var result = null;
    while (true) {
      await new Promise(function (resolve) { setTimeout(resolve, 10000); });
      var poll = await apiJson("/schedules/generate/status/" + jobId + "/", "GET", null, { _skipSpinner: true });
      if (!poll.ok) {
        result = { ok: false, data: poll.data };
        break;
      }
      if (poll.data.status === "DONE") {
        result = { ok: true, data: poll.data.result };
        break;
      }
      if (poll.data.status === "ERROR") {
        result = { ok: false, data: poll.data.error };
        break;
      }
    }

    stopGenerationProgress();
    setGenerateActionButtonsDisabled(false);
    if (!result.ok) {
      state.latestGeneratedSchedules = [];
      state.generatedSaved = false;
      state.generatedSavedName = "";
      state.generatedMoveInFlight = false;
      showGeneratedLanding();
      showAlert("error", extractApiErrorInfo(result.data, "No se pudo generar el horario."));
      return;
    }
    state.latestGeneratedSchedules = (result.data && result.data.schedules) || [];
    state.latestTCSessions = [];
    state.tcSessionsContext = "";
    apiJson("/tc-sessions/").then(function (tcResult) {
      if (tcResult.ok) {
        state.latestTCSessions = (tcResult.data && (tcResult.data.results || tcResult.data)) || [];
        refreshFilterWorkloads();
        renderGeneratedWorkspace();
      }
    });
    state.generatedUnavailability = (result.data && result.data.unavailability) || null;
    state.generatedStageWindows = (result.data && result.data.stage_windows) || null;
    state.generatedDetailPage = 1;
    state.generatedSaved = false;
    state.generatedSavedName = "";
    state.generatedTeacherWorkloadsByName =
      result.data && Array.isArray(result.data.teacher_workloads)
        ? buildTeacherWorkloadsByNameFromApi(result.data.teacher_workloads)
        : buildTeacherWorkloadsByNameFromSessions(state.latestGeneratedSchedules);
    state.generatedMoveInFlight = false;
    refreshFilterWorkloads();
    showGeneratedWorkspace();
    renderGeneratedWorkspace();
    const generatedCount =
      result.data && result.data.generated_count ? result.data.generated_count : state.latestGeneratedSchedules.length;
    showAlert("success", "Se generaron " + generatedCount + " sesiones.");
    const tcWarnings = (result.data && result.data.tc_warnings) || [];
    if (tcWarnings.length > 0) {
      const days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"];
      const lines = tcWarnings.map(function (w) {
        const dayName = days[w.day] || "Día " + w.day;
        return dayName + " " + w.start_time.slice(0, 5) + ": " + w.assigned + "/" + w.required + " docentes TC";
      });
      showAlert("warning", "Guardias TC con cobertura incompleta:\n" + lines.join("\n"));
    }
  }

  /**
   * Closes the generate modal and immediately starts generation.
   * Input: none
   * Output: Promise<void>
   */
  async function handleGenerateModalConfirm() {
    closeGenerateModal();
    await handleGenerate();
  }

  /**
   * Opens the export modal pre-configured for the generated schedule source.
   * Input: none
   * Output: void
   */
  function openGeneratedExport() {
    const source = state.generatedSaved ? "saved" : "generated";
    const savedName = state.generatedSaved ? state.generatedSavedName : "";
    exportManager.openExportModal({ source: source, savedName: savedName });
  }

  /**
   * Loads teachers, classrooms, groups, and subjects in parallel and updates the dashboard metrics.
   * Input: none
   * Output: Promise<void>; shows warning alert if any request fails
   */
  async function loadCoreData() {
    const responses = await Promise.all([
      apiJson(buildSummaryPath("/teachers/", "count")),
      apiJson(buildSummaryPath("/classrooms/", "count")),
      apiJson(buildSummaryPath("/groups/", "count")),
      apiJson(buildSummaryPath("/subjects/", "count")),
    ]);
    const teachersResponse = responses[0];
    const classroomsResponse = responses[1];
    const groupsResponse = responses[2];
    const subjectsResponse = responses[3];
    setText("statTeachers", getCollectionCount(teachersResponse.data));
    setText("statClassrooms", getCollectionCount(classroomsResponse.data));
    setText("statGroups", getCollectionCount(groupsResponse.data));
    setText("statSubjects", getCollectionCount(subjectsResponse.data));
    if (!teachersResponse.ok || !classroomsResponse.ok || !groupsResponse.ok || !subjectsResponse.ok) {
      showAlert("warning", "Algunos datos administrativos no se pudieron cargar completamente.");
    }
  }

  // ── Event binding ──────────────────────────────────────────────────────────

  /**
   * Attaches all event listeners for the generated-schedule workspace (filters, drag-drop, actions).
   */
  function bindGeneratedEvents() {
    const generateButton = document.getElementById("generateBtn");
    if (generateButton) {
      generateButton.addEventListener("click", function () {
        openGenerateModal("generate");
      });
    }

    [
      generatedFilterIds.courseId,
      generatedFilterIds.teacherId,
      generatedFilterIds.classroomId,
      generatedFilterIds.subjectId,
    ].forEach(function (id) {
      const select = document.getElementById(id);
      if (!select) {
        return;
      }
      select.addEventListener("change", function () {
        state.generatedDetailPage = 1;
        renderGeneratedWorkspace();
      });
    });

    const generatedOutput = document.getElementById("generatedWorkspaceOutput");
    if (generatedOutput) {
      generatedWorkspace.bindDragDropEvents(generatedOutput);

      generatedOutput.addEventListener("click", function (event) {
        const target = event.target;
        if (!(target instanceof Element)) {
          return;
        }
        const tcDeleteBtn = target.closest("button[data-tc-delete-id]");
        if (tcDeleteBtn) {
          handleTCSessionDelete(Number.parseInt(tcDeleteBtn.dataset.tcDeleteId, 10));
          return;
        }
        const tcAddBtn = target.closest("button[data-add-tc]");
        if (tcAddBtn) {
          const cell = tcAddBtn.closest("td[data-board-day]");
          if (cell) {
            handleTCSessionCreate(cell.dataset.boardDay, cell.dataset.boardStart, cell.dataset.boardEnd, generatedFilterIds);
          }
          return;
        }
        const pageButton = target.closest("button[data-detail-page]");
        if (!pageButton) {
          return;
        }
        const page = Number.parseInt(pageButton.dataset.detailPage || "", 10);
        if (Number.isNaN(page) || page < 1 || page === state.generatedDetailPage) {
          return;
        }
        state.generatedDetailPage = page;
        renderGeneratedWorkspace();
      });
    }

    const exportButton = document.getElementById("generatedWorkspaceExportBtn");
    if (exportButton) {
      exportButton.addEventListener("click", function () {
        openGeneratedExport();
      });
    }

    const saveButton = document.getElementById("generatedWorkspaceSaveBtn");
    if (saveButton) {
      saveButton.addEventListener("click", handleSaveGenerated);
    }

    const confirmSaveButton = document.getElementById("confirmSaveGeneratedBtn");
    if (confirmSaveButton) {
      confirmSaveButton.addEventListener("click", handleSaveGeneratedConfirm);
    }

    const saveNameInput = document.getElementById("saveGeneratedNameInput");
    if (saveNameInput) {
      saveNameInput.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
          event.preventDefault();
          handleSaveGeneratedConfirm();
        }
      });
    }

    const regenerateButton = document.getElementById("generatedWorkspaceRegenerateBtn");
    if (regenerateButton) {
      regenerateButton.addEventListener("click", function () {
        openGenerateModal("regenerate");
      });
    }

    const confirmGenerateButton = document.getElementById("confirmScheduleGenerateBtn");
    if (confirmGenerateButton) {
      confirmGenerateButton.addEventListener("click", handleGenerateModalConfirm);
    }

    const tcBtn = document.getElementById("generatedWorkspaceTCBtn");
    if (tcBtn) {
      tcBtn.addEventListener("click", function () {
        state.generatedTCViewMode = !state.generatedTCViewMode;
        renderGeneratedWorkspace();
      });
    }
  }

  /**
   * Attaches all event listeners for the saved-schedule workspace (filters, drag-drop, navigation).
   */
  function bindSavedEvents() {
    const cardsContainer = document.getElementById("savedScheduleCards");
    if (cardsContainer) {
      cardsContainer.addEventListener("click", async function (event) {
        const target = event.target;
        if (!(target instanceof Element)) {
          return;
        }
        const renameButton = target.closest("button[data-action='rename'][data-index]");
        if (renameButton) {
          event.preventDefault();
          event.stopPropagation();
          const renameIndex = Number.parseInt(renameButton.dataset.index || "", 10);
          if (Number.isNaN(renameIndex) || renameIndex < 0) {
            return;
          }
          savedManager.renameSavedTimetable(renameIndex);
          return;
        }
        const deleteButton = target.closest("button[data-action='delete'][data-index]");
        if (deleteButton) {
          event.preventDefault();
          event.stopPropagation();
          const deleteIndex = Number.parseInt(deleteButton.dataset.index || "", 10);
          if (Number.isNaN(deleteIndex) || deleteIndex < 0) {
            return;
          }
          savedManager.deleteSavedTimetable(deleteIndex);
          return;
        }
        const card = target.closest(".saved-card[data-action='open'][data-index]");
        if (!card) {
          return;
        }
        const index = Number.parseInt(card.dataset.index || "", 10);
        if (Number.isNaN(index) || index < 0) {
          return;
        }
        const selected = state.savedTimetableGroups[index];
        if (!selected) {
          showAlert("error", "Horario guardado no encontrado.");
          return;
        }
        if (!navigateToSavedDetail(selected.name)) {
          await savedManager.openSavedWorkspace(index);
        }
      });

      cardsContainer.addEventListener("keydown", async function (event) {
        const target = event.target;
        if (!(target instanceof Element)) {
          return;
        }
        if (target.closest("button")) {
          return;
        }
        if (event.key !== "Enter" && event.key !== " ") {
          return;
        }
        const card = target.closest(".saved-card[data-action='open'][data-index]");
        if (!card) {
          return;
        }
        event.preventDefault();
        const index = Number.parseInt(card.dataset.index || "", 10);
        if (Number.isNaN(index) || index < 0) {
          return;
        }
        const selected = state.savedTimetableGroups[index];
        if (!selected) {
          showAlert("error", "Horario guardado no encontrado.");
          return;
        }
        if (!navigateToSavedDetail(selected.name)) {
          await savedManager.openSavedWorkspace(index);
        }
      });
    }

    [savedFilterIds.courseId, savedFilterIds.teacherId, savedFilterIds.classroomId, savedFilterIds.subjectId].forEach(
      function (id) {
        const select = document.getElementById(id);
        if (!select) {
          return;
        }
        select.addEventListener("change", function () {
          state.savedDetailPage = 1;
          renderSavedWorkspace();
        });
      },
    );

    const savedOutput = document.getElementById("savedWorkspaceOutput");
    if (savedOutput) {
      savedWorkspace.bindDragDropEvents(savedOutput);

      savedOutput.addEventListener("click", function (event) {
        const target = event.target;
        if (!(target instanceof Element)) {
          return;
        }
        const tcDeleteBtn = target.closest("button[data-tc-delete-id]");
        if (tcDeleteBtn) {
          handleTCSessionDelete(Number.parseInt(tcDeleteBtn.dataset.tcDeleteId, 10));
          return;
        }
        const tcAddBtn = target.closest("button[data-add-tc]");
        if (tcAddBtn) {
          const cell = tcAddBtn.closest("td[data-board-day]");
          if (cell) {
            handleTCSessionCreate(cell.dataset.boardDay, cell.dataset.boardStart, cell.dataset.boardEnd, savedFilterIds);
          }
          return;
        }
        const pageButton = target.closest("button[data-detail-page]");
        if (!pageButton) {
          return;
        }
        const page = Number.parseInt(pageButton.dataset.detailPage || "", 10);
        if (Number.isNaN(page) || page < 1 || page === state.savedDetailPage) {
          return;
        }
        state.savedDetailPage = page;
        renderSavedWorkspace();
      });
    }

    const backButton = document.getElementById("savedWorkspaceBackBtn");
    if (backButton) {
      backButton.addEventListener("click", function () {
        if (!navigateToSavedList()) {
          showSavedPicker();
        }
      });
    }

    const exportButton = document.getElementById("savedWorkspaceExportBtn");
    if (exportButton) {
      exportButton.addEventListener("click", function () {
        exportManager.openExportModal({
          source: "saved",
          savedName: state.selectedSavedTimetableName || "",
        });
      });
    }

    const tcBtn = document.getElementById("savedWorkspaceTCBtn");
    if (tcBtn) {
      tcBtn.addEventListener("click", function () {
        state.savedTCViewMode = !state.savedTCViewMode;
        renderSavedWorkspace();
      });
    }
  }

  // ── CSRF / analysis ────────────────────────────────────────────────────────

  /**
   * Reads the CSRF token from a hidden input or the csrftoken cookie.
   * Input: none
   * Output: string CSRF token, or empty string when not found
   */
  function getCsrfToken() {
    // Intenta obtener el CSRF token de varias formas
    // 1. Desde input hidden
    let token = document.querySelector("[name=csrfmiddlewaretoken]")?.value;
    if (token) return token;

    // 2. Desde cookies
    const name = "csrftoken";
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
      const cookies = document.cookie.split(";");
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === name + "=") {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue || "";
  }

  /**
   * Wires the analysis (defects) buttons for both generated and saved workspaces.
   * Input: none
   * Output: void; attaches click listeners that delegate to window.ScheduleAnalysis.showAnalysisModal
   */
  function bindCentralDefectsButtonEvents() {
    const generatedDefectsBtn = document.getElementById("generatedDefectsBtn");
    if (generatedDefectsBtn) {
      generatedDefectsBtn.addEventListener("click", function (e) {
        e.preventDefault();
        if (!state.latestGeneratedSchedules || state.latestGeneratedSchedules.length === 0) {
          return;
        }
        const scheduleIds = state.latestGeneratedSchedules.map(function (s) {
          return s.id;
        });
        window.ScheduleAnalysis.showAnalysisModal(
          scheduleIds,
          "scheduleAnalysisModal",
          "Análisis del Horario",
          "schedule-analysis-content",
          apiJson,
        );
      });
    }

    const savedDefectsBtn = document.getElementById("savedDefectsBtn");
    if (savedDefectsBtn) {
      savedDefectsBtn.addEventListener("click", function (e) {
        e.preventDefault();
        const selectedGroup = savedManager.getSelectedSavedGroup();
        const schedules = selectedGroup && Array.isArray(selectedGroup.sessions) ? selectedGroup.sessions : [];
        if (!schedules.length) {
          showAlert("info", "No hay horarios guardados seleccionados.");
          return;
        }
        const scheduleIds = schedules.map(function (s) {
          return s.id;
        });
        window.ScheduleAnalysis.showAnalysisModal(
          scheduleIds,
          "savedAnalysisModal",
          "Análisis del Horario Guardado",
          "saved-analysis-content",
          apiJson,
        );
      });
    }
  }

  // ── Init ───────────────────────────────────────────────────────────────────

  /**
   * Bootstraps the schedules module: initializes filters, binds events, loads data.
   * Input: none
   * Output: Promise<void>
   */
  async function init() {
    initScheduleFilterDropdowns();
    exportManager.bindExportEvents();
    bindCentralDefectsButtonEvents();

    if (schedulesSection) {
      bindGeneratedEvents();
      showGeneratedLanding();
    }

    if (savedSection) {
      bindSavedEvents();
      showSavedPicker();
      state.initialSavedRouteName = String(savedSection.dataset.openSavedName || "").trim();
    }

    const initTasks = [];
    if (schedulesSection) {
      initTasks.push(loadCoreData());
    }
    if (savedSection) {
      initTasks.push(savedManager.ensureSavedSchedulesLoaded());
    }
    initTasks.push(
      apiJson("/schedule-config/").then(function (res) {
        if (res.ok && res.data && res.data.schedule_config) {
          state.scheduleConfig = res.data.schedule_config;
        }
      }),
    );
    state.tcSessionsContext = "";
    initTasks.push(
      apiJson("/tc-sessions/").then(function (res) {
        if (res.ok) {
          state.latestTCSessions = (res.data && (res.data.results || res.data)) || [];
          refreshFilterWorkloads();
        }
      }),
    );
    await Promise.all(initTasks);

    if (window.orariooAuth && typeof window.orariooAuth.initLucideIcons === "function") {
      window.orariooAuth.initLucideIcons();
    }
  }

  init();
})();
