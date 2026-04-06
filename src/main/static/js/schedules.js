(function () {
  const schedulesSection = document.getElementById("schedulesSection");
  const savedSection = document.getElementById("savedSection");

  if (!schedulesSection && !savedSection) {
    return;
  }

  const AUTO_GENERATED_OBSERVATION = "Auto-generated with CP-SAT basic constraints.";
  const WORK_CENTER_SUBJECT = "Trabajo de Centro";
  const BOARD_DAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"];
  const BOARD_DAY_INDEX = {
    Lunes: 1,
    Martes: 2,
    Miércoles: 3,
    Jueves: 4,
    Viernes: 5,
  };
  const DEFAULT_BOARD_ROWS = [
    ["08:00", "09:00"],
    ["09:00", "10:00"],
    ["10:00", "11:00"],
    ["11:00", "12:00"],
    ["12:00", "13:00"],
    ["13:00", "14:00"],
  ];
  const MOVE_API_PATH = "/schedules/move/";
  const SAVED_SUMMARY_API_PATH = "/schedules/saved-summary/";
  const SAVED_DETAIL_API_PATH = "/schedules/saved-detail/";
  const CELL_UPDATE_ANIMATION_MS = 420;

  const generatedFilterIds = {
    courseId: "generatedWorkspaceCourseFilter",
    teacherId: "generatedWorkspaceTeacherFilter",
    subjectId: "generatedWorkspaceSubjectFilter",
  };

  const savedFilterIds = {
    courseId: "savedWorkspaceCourseFilter",
    teacherId: "savedWorkspaceTeacherFilter",
    subjectId: "savedWorkspaceSubjectFilter",
  };

  const state = {
    currentTeachers: [],
    currentClassrooms: [],
    currentGroups: [],
    currentSubjects: [],
    latestGeneratedSchedules: [],
    generatedDetailPage: 1,
    savedDetailPage: 1,
    detailPageSize: 20,
    generatedSaved: false,
    generatedSavedName: "",
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
    initialSavedRouteName: "",
    exportEntityState: {
      group: false,
      teacher: false,
      classroom: false,
    },
  };

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function closeScheduleFilterDropdown(dropdown) {
    if (!dropdown) {
      return;
    }

    dropdown.classList.remove("is-open");
    const trigger = dropdown.querySelector(".schedule-filter-trigger");
    if (trigger) {
      trigger.setAttribute("aria-expanded", "false");
    }
  }

  function closeAllScheduleFilterDropdowns(exceptDropdown) {
    document.querySelectorAll(".schedule-filter-dropdown.is-open").forEach(function (dropdown) {
      if (exceptDropdown && dropdown === exceptDropdown) {
        return;
      }
      closeScheduleFilterDropdown(dropdown);
    });
  }

  function getScheduleFilterOptionButtons(dropdown) {
    if (!dropdown) {
      return [];
    }

    return Array.from(
      dropdown.querySelectorAll(".schedule-filter-option:not(:disabled)"),
    );
  }

  function focusScheduleFilterOption(dropdown, index) {
    const options = getScheduleFilterOptionButtons(dropdown);
    if (!options.length) {
      return;
    }

    const boundedIndex = Math.max(0, Math.min(index, options.length - 1));
    options[boundedIndex].focus();
  }

  function focusSelectedScheduleFilterOption(dropdown) {
    if (!dropdown) {
      return;
    }

    const selectedOption = dropdown.querySelector(".schedule-filter-option.is-selected");
    if (selectedOption) {
      selectedOption.focus();
      return;
    }

    focusScheduleFilterOption(dropdown, 0);
  }

  function ensureScheduleFilterMenuVisible(dropdown) {
    if (!dropdown) {
      return;
    }

    const menu = dropdown.querySelector(".schedule-filter-menu");
    if (!menu) {
      return;
    }

    const menuRect = menu.getBoundingClientRect();
    const viewportBottom = window.innerHeight || document.documentElement.clientHeight || 0;
    const overflowBottom = menuRect.bottom - viewportBottom;

    if (overflowBottom > 0) {
      window.scrollBy({
        top: overflowBottom + 12,
        left: 0,
        behavior: "smooth",
      });
    }
  }

  function openScheduleFilterDropdown(dropdown) {
    if (!dropdown) {
      return;
    }

    closeAllScheduleFilterDropdowns(dropdown);
    dropdown.classList.add("is-open");

    const trigger = dropdown.querySelector(".schedule-filter-trigger");
    if (trigger) {
      trigger.setAttribute("aria-expanded", "true");
    }

    window.requestAnimationFrame(function () {
      ensureScheduleFilterMenuVisible(dropdown);
    });
  }

  function toggleScheduleFilterDropdown(dropdown) {
    if (!dropdown) {
      return;
    }

    if (dropdown.classList.contains("is-open")) {
      closeScheduleFilterDropdown(dropdown);
      return;
    }

    openScheduleFilterDropdown(dropdown);
  }

  function syncScheduleFilterDropdown(select) {
    if (!select) {
      return;
    }

    const dropdown = select.closest(".schedule-filter-dropdown");
    if (!dropdown) {
      return;
    }

    const triggerLabel = dropdown.querySelector(".schedule-filter-trigger-label");
    const menu = dropdown.querySelector(".schedule-filter-menu");
    if (!triggerLabel || !menu) {
      return;
    }

    const selectedOption = select.options[select.selectedIndex >= 0 ? select.selectedIndex : 0] || null;
    const selectedLabel = selectedOption ? String(selectedOption.textContent || "").trim() : "";

    triggerLabel.textContent = selectedLabel || "Selecciona una opción";

    menu.innerHTML = Array.from(select.options)
      .map(function (option) {
        const label = String(option.textContent || "").trim();
        const selectedClass = option.selected ? " is-selected" : "";
        const selectedAttr = option.selected ? "true" : "false";
        const disabledAttr = option.disabled ? " disabled" : "";

        return (
          '<button type="button" class="schedule-filter-option' +
          selectedClass +
          '" role="option" aria-selected="' +
          selectedAttr +
          '" data-filter-value="' +
          escapeHtml(option.value) +
          '"' +
          disabledAttr +
          ">" +
          escapeHtml(label) +
          "</button>"
        );
      })
      .join("");
  }

  function enhanceScheduleFilterSelect(select) {
    if (!select || select.dataset.customFilterReady === "true") {
      return;
    }

    const wrapper = document.createElement("div");
    const trigger = document.createElement("button");
    const triggerLabel = document.createElement("span");
    const triggerIcon = document.createElement("span");
    const menu = document.createElement("div");

    wrapper.className = "schedule-filter-dropdown";
    trigger.type = "button";
    trigger.className = "schedule-filter-trigger";
    trigger.setAttribute("aria-expanded", "false");
    trigger.setAttribute("aria-haspopup", "listbox");
    triggerLabel.className = "schedule-filter-trigger-label";
    triggerIcon.className = "schedule-filter-trigger-icon";
    triggerIcon.setAttribute("aria-hidden", "true");
    triggerIcon.textContent = "▾";
    menu.className = "schedule-filter-menu";
    menu.setAttribute("role", "listbox");

    trigger.appendChild(triggerLabel);
    trigger.appendChild(triggerIcon);
    wrapper.appendChild(trigger);
    wrapper.appendChild(menu);

    select.parentNode.insertBefore(wrapper, select);
    wrapper.appendChild(select);

    select.classList.add("schedule-toolbar-select-native");
    select.tabIndex = -1;
    select.setAttribute("aria-hidden", "true");
    select.dataset.customFilterReady = "true";

    trigger.addEventListener("click", function () {
      toggleScheduleFilterDropdown(wrapper);
    });

    trigger.addEventListener("keydown", function (event) {
      if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openScheduleFilterDropdown(wrapper);
        focusSelectedScheduleFilterOption(wrapper);
        return;
      }

      if (event.key === "Escape") {
        closeScheduleFilterDropdown(wrapper);
      }
    });

    menu.addEventListener("click", function (event) {
      const optionButton = event.target.closest(".schedule-filter-option[data-filter-value]");
      if (!optionButton) {
        return;
      }

      const nextValue = optionButton.dataset.filterValue || "";
      const hasChanged = select.value !== nextValue;
      select.value = nextValue;
      syncScheduleFilterDropdown(select);
      closeScheduleFilterDropdown(wrapper);
      trigger.focus();

      if (hasChanged) {
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });

    menu.addEventListener("keydown", function (event) {
      const activeElement = document.activeElement;
      if (!(activeElement instanceof HTMLElement)) {
        return;
      }

      const options = getScheduleFilterOptionButtons(wrapper);
      const currentIndex = options.indexOf(activeElement);

      if (event.key === "Escape") {
        event.preventDefault();
        closeScheduleFilterDropdown(wrapper);
        trigger.focus();
        return;
      }

      if (event.key === "ArrowDown") {
        event.preventDefault();
        focusScheduleFilterOption(wrapper, currentIndex + 1);
        return;
      }

      if (event.key === "ArrowUp") {
        event.preventDefault();
        if (currentIndex <= 0) {
          trigger.focus();
          return;
        }
        focusScheduleFilterOption(wrapper, currentIndex - 1);
      }
    });

    select.addEventListener("change", function () {
      syncScheduleFilterDropdown(select);
    });

    syncScheduleFilterDropdown(select);
  }

  function initScheduleFilterDropdowns() {
    document.querySelectorAll(".schedule-toolbar-select").forEach(function (select) {
      enhanceScheduleFilterSelect(select);
    });

    document.addEventListener("click", function (event) {
      const target = event.target;
      if (target instanceof HTMLElement && target.closest(".schedule-filter-dropdown")) {
        return;
      }
      closeAllScheduleFilterDropdowns();
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        closeAllScheduleFilterDropdowns();
      }
    });

    window.addEventListener("resize", function () {
      closeAllScheduleFilterDropdowns();
    });
  }

  function getSavedListUrl() {
    if (savedSection && savedSection.dataset.savedListUrl) {
      return savedSection.dataset.savedListUrl;
    }
    return "/dashboard/saved/";
  }

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

  function navigateToSavedDetail(timetableName) {
    const url = buildSavedDetailUrl(timetableName);
    if (!url) {
      return false;
    }
    window.location.assign(url);
    return true;
  }

  function navigateToSavedList() {
    const url = getSavedListUrl();
    if (!url) {
      return false;
    }
    window.location.assign(url);
    return true;
  }

  function getAlertElement() {
    return document.getElementById("scheduleAlert");
  }

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
    alert.textContent = message;
    alert.classList.remove("d-none");

    window.clearTimeout(showAlert._timer);
    showAlert._timer = window.setTimeout(function () {
      alert.classList.add("d-none");
    }, 4500);
  }

  function extractApiErrorMessage(data, fallback) {
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

  async function apiJson(path, method, body) {
    const options = {
      method: method || "GET",
      headers: {
        "Content-Type": "application/json",
      },
    };

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
      return {
        ok: response.ok,
        status: response.status,
        data: data,
        response: response,
      };
    } catch (error) {
      return {
        ok: false,
        status: 0,
        data: { detail: error && error.message ? error.message : "Error de red" },
      };
    }
  }

  function listFromPayload(payload) {
    if (Array.isArray(payload)) {
      return payload;
    }
    if (payload && Array.isArray(payload.results)) {
      return payload.results;
    }
    return [];
  }

  function setText(id, value) {
    const element = document.getElementById(id);
    if (element) {
      element.textContent = String(value);
    }
  }

  function getCollectionCount(payload, fallbackItems) {
    if (payload && typeof payload.count === "number") {
      return payload.count;
    }
    return Array.isArray(fallbackItems) ? fallbackItems.length : 0;
  }

  function normalizeForCompare(value) {
    return String(value || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .trim();
  }

  function isWorkCenterSubjectValue(value) {
    return normalizeForCompare(value) === normalizeForCompare(WORK_CENTER_SUBJECT);
  }

  function getSubjectTypeValue(item) {
    if (!item || typeof item !== "object") {
      return "";
    }

    return String(item.subject_type || item.type || "")
      .trim()
      .toUpperCase();
  }

  function findCurrentSubjectById(subjectId) {
    if (subjectId === null || subjectId === undefined || subjectId === "") {
      return null;
    }

    const normalizedId = String(subjectId);
    for (let index = 0; index < state.currentSubjects.length; index += 1) {
      const subject = state.currentSubjects[index];
      if (String(subject.id) === normalizedId) {
        return subject;
      }
    }

    return null;
  }

  function getSessionSubjectType(session) {
    const directType = getSubjectTypeValue(session);
    if (directType) {
      return directType;
    }

    const currentSubject = findCurrentSubjectById(session && session.subject);
    return getSubjectTypeValue(currentSubject);
  }

  function hasWorkCenterSubjects(items) {
    return (items || []).some(function (item) {
      if (getSubjectTypeValue(item) === "TC") {
        return true;
      }

      const currentSubject = findCurrentSubjectById(item && item.subject);
      return getSubjectTypeValue(currentSubject) === "TC";
    });
  }

  function toUtcHM(date) {
    return String(date.getUTCHours()).padStart(2, "0") + ":" + String(date.getUTCMinutes()).padStart(2, "0");
  }

  function toIsoDateDisplay(value) {
    if (!value) {
      return "-";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "-";
    }
    return date.toLocaleString("es-ES", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function toDateMillis(value) {
    if (!value) {
      return 0;
    }
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? 0 : parsed.getTime();
  }

  function createEmptyDayCells() {
    const cells = {};
    BOARD_DAYS.forEach(function (dayName) {
      cells[dayName] = [];
    });
    return cells;
  }

  function parseHourKey(value) {
    const tokens = String(value || "").split(":");
    if (tokens.length !== 2) {
      return Number.MAX_SAFE_INTEGER;
    }

    const hour = Number.parseInt(tokens[0], 10);
    const minute = Number.parseInt(tokens[1], 10);
    if (Number.isNaN(hour) || Number.isNaN(minute)) {
      return Number.MAX_SAFE_INTEGER;
    }

    return hour * 60 + minute;
  }

  function compareRowsByTime(left, right) {
    const startCompare = parseHourKey(left.start) - parseHourKey(right.start);
    if (startCompare !== 0) {
      return startCompare;
    }
    return parseHourKey(left.end) - parseHourKey(right.end);
  }

  function mapSessionForBoard(session, options) {
    const start = new Date(session.start_time);
    const end = new Date(session.end_time);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
      return null;
    }

    const weekdayMap = {
      1: "Lunes",
      2: "Martes",
      3: "Miércoles",
      4: "Jueves",
      5: "Viernes",
    };

    const dayName = weekdayMap[start.getUTCDay()];
    if (!dayName || BOARD_DAYS.indexOf(dayName) < 0) {
      return null;
    }

    const forceWorkCenterLabel = options && options.forceWorkCenterSubjectLabel === true;
    const displaySubjectName =
      forceWorkCenterLabel && getSessionSubjectType(session) === "TC"
        ? WORK_CENTER_SUBJECT
        : session.subject_name || "-";

    return {
      id: session.id,
      teacherId: session.teacher,
      groupId: session.group,
      classroomId: session.classroom,
      subjectName: displaySubjectName,
      teacherName: session.teacher_name || "-",
      groupName: session.group_name || "-",
      classroomName: session.classroom_name || "-",
      dayName: dayName,
      start: start,
      end: end,
      startHm: toUtcHM(start),
      endHm: toUtcHM(end),
    };
  }

  function buildBoardRows(mappedSessions) {
    const byRange = new Map();

    mappedSessions.forEach(function (session) {
      const rangeKey = session.startHm + "-" + session.endHm;
      if (!byRange.has(rangeKey)) {
        byRange.set(rangeKey, {
          start: session.startHm,
          end: session.endHm,
          cells: createEmptyDayCells(),
        });
      }
      byRange.get(rangeKey).cells[session.dayName].push(session);
    });

    const rows = Array.from(byRange.values()).sort(compareRowsByTime);
    if (rows.length) {
      return rows;
    }

    return DEFAULT_BOARD_ROWS.map(function (range) {
      return {
        start: range[0],
        end: range[1],
        cells: createEmptyDayCells(),
      };
    });
  }

  function createBoardCellKey(dayName, startHm, endHm) {
    return dayName + "|" + startHm + "|" + endHm;
  }

  function parseHmToMinutes(value) {
    const parts = String(value || "").split(":");
    if (parts.length !== 2) {
      return Number.NaN;
    }
    const hour = Number.parseInt(parts[0], 10);
    const minute = Number.parseInt(parts[1], 10);
    if (Number.isNaN(hour) || Number.isNaN(minute)) {
      return Number.NaN;
    }
    return hour * 60 + minute;
  }

  function hmRangesOverlap(leftStart, leftEnd, rightStart, rightEnd) {
    const leftStartMinutes = parseHmToMinutes(leftStart);
    const leftEndMinutes = parseHmToMinutes(leftEnd);
    const rightStartMinutes = parseHmToMinutes(rightStart);
    const rightEndMinutes = parseHmToMinutes(rightEnd);

    if (
      Number.isNaN(leftStartMinutes) ||
      Number.isNaN(leftEndMinutes) ||
      Number.isNaN(rightStartMinutes) ||
      Number.isNaN(rightEndMinutes)
    ) {
      return false;
    }

    return leftStartMinutes < rightEndMinutes && rightStartMinutes < leftEndMinutes;
  }

  function renderSessionCard(session, options) {
    const safeOptions = options || {};
    const canDrag = safeOptions.enableDragDrop === true;
    const dragAttrs = canDrag ? ' draggable="true" data-draggable="true"' : "";
    const dragClass = canDrag ? " schedule-board-card-draggable" : "";

    return (
      '<article class="schedule-board-card' +
      dragClass +
      '" data-schedule-id="' +
      session.id +
      '" data-slot-day="' +
      session.dayName +
      '" data-slot-start="' +
      session.startHm +
      '" data-slot-end="' +
      session.endHm +
      '"' +
      dragAttrs +
      ">" +
      '<h4 class="schedule-board-card-subject">' +
      session.subjectName +
      "</h4>" +
      '<p class="schedule-board-card-line">' +
      session.teacherName +
      "</p>" +
      '<p class="schedule-board-card-line">' +
      session.groupName +
      " | " +
      session.classroomName +
      "</p>" +
      "</article>"
    );
  }

  function renderEmptyCell() {
    return '<div class="schedule-board-slot-empty" aria-hidden="true"></div>';
  }

  function createDetailPaginationHtml(currentPage, totalPages) {
    if (totalPages <= 1) {
      return "";
    }

    function pageButton(label, page, disabled, active) {
      return (
        '<li class="page-item' +
        (disabled ? " disabled" : "") +
        (active ? " active" : "") +
        '"><button type="button" class="page-link"' +
        (active ? ' aria-current="page"' : "") +
        (disabled ? " disabled" : ' data-detail-page="' + page + '"') +
        ">" +
        label +
        "</button></li>"
      );
    }

    function ellipsis() {
      return '<li class="page-item disabled"><span class="page-link">...</span></li>';
    }

    const windowSize = 5;
    let start = Math.max(1, currentPage - 2);
    let end = Math.min(totalPages, start + windowSize - 1);
    start = Math.max(1, end - windowSize + 1);

    let html = "";
    html += pageButton("Anterior", currentPage - 1, currentPage <= 1, false);

    if (start > 1) {
      html += pageButton("1", 1, false, currentPage === 1);
      if (start > 2) {
        html += ellipsis();
      }
    }

    for (let page = start; page <= end; page += 1) {
      html += pageButton(String(page), page, false, page === currentPage);
    }

    if (end < totalPages) {
      if (end < totalPages - 1) {
        html += ellipsis();
      }
      html += pageButton(String(totalPages), totalPages, false, currentPage === totalPages);
    }

    html += pageButton("Siguiente", currentPage + 1, currentPage >= totalPages, false);

    return (
      '<div class="schedule-detail-pagination"><nav aria-label="Paginación de sesiones"><ul class="pagination pagination-sm mb-0">' +
      html +
      "</ul></nav></div>"
    );
  }

  function renderSessionDetailTable(mappedSessions, options) {
    const safeOptions = options || {};
    const pageSize = Math.max(1, safeOptions.pageSize || 20);
    const totalItems = mappedSessions.length;
    const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
    const requestedPage = Math.max(1, safeOptions.page || 1);
    const currentPage = Math.min(requestedPage, totalPages);

    const startIndex = (currentPage - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    const pagedItems = mappedSessions.slice(startIndex, endIndex);

    const rowsHtml = pagedItems.length
      ? pagedItems
          .map(function (item) {
            return (
              "<tr>" +
              "<td>" +
              item.dayName +
              "</td>" +
              "<td>" +
              item.startHm +
              "</td>" +
              "<td>" +
              item.endHm +
              "</td>" +
              "<td>" +
              item.groupName +
              "</td>" +
              "<td>" +
              item.teacherName +
              "</td>" +
              "<td>" +
              item.classroomName +
              "</td>" +
              "<td>" +
              item.subjectName +
              "</td>" +
              "</tr>"
            );
          })
          .join("")
      : '<tr><td colspan="7" class="text-secondary">No hay sesiones para los filtros seleccionados.</td></tr>';

    const firstItem = totalItems ? startIndex + 1 : 0;
    const lastItem = totalItems ? Math.min(endIndex, totalItems) : 0;

    const html =
      '<section class="schedule-detail-block">' +
      '<div class="schedule-detail-head">' +
      '<h4 class="schedule-detail-title">' +
      (safeOptions.title || "Detalle de sesiones") +
      "</h4>" +
      '<span class="schedule-detail-meta">Mostrando ' +
      firstItem +
      "-" +
      lastItem +
      " de " +
      totalItems +
      " sesiones</span>" +
      "</div>" +
      '<div class="schedule-detail-table-wrap">' +
      '<table class="table table-sm align-middle mb-0 schedule-detail-table">' +
      "<thead><tr><th>Día</th><th>Inicio</th><th>Fin</th><th>Curso</th><th>Profesor</th><th>Aula</th><th>Asignatura</th></tr></thead>" +
      "<tbody>" +
      rowsHtml +
      "</tbody></table></div>" +
      createDetailPaginationHtml(currentPage, totalPages) +
      "</section>";

    return {
      html: html,
      currentPage: currentPage,
      totalItems: totalItems,
    };
  }

  function renderScheduleBoard(sessions, outputId, options) {
    const output = document.getElementById(outputId);
    if (!output) {
      return;
    }

    const safeOptions = options || {};

    const mappedSessions = (sessions || [])
      .map(function (session) {
        return mapSessionForBoard(session, safeOptions);
      })
      .filter(Boolean)
      .sort(function (left, right) {
        return left.start - right.start;
      });

    const rows = buildBoardRows(mappedSessions);

    const rowHtml = rows
      .map(function (row) {
        const dayCells = BOARD_DAYS.map(function (dayName) {
          const entries = row.cells[dayName] || [];
          const cellKey = createBoardCellKey(dayName, row.start, row.end);
          return (
            '<td class="schedule-board-cell" data-board-day="' +
            dayName +
            '" data-board-start="' +
            row.start +
            '" data-board-end="' +
            row.end +
            '" data-board-key="' +
            cellKey +
            '">' +
            (entries.length
              ? entries
                  .map(function (entry) {
                    return renderSessionCard(entry, safeOptions);
                  })
                  .join("")
              : renderEmptyCell()) +
            "</td>"
          );
        }).join("");

        return (
          "<tr>" +
          '<td class="schedule-board-time"><strong>' +
          row.start +
          "</strong><span>" +
          row.end +
          "</span></td>" +
          dayCells +
          "</tr>"
        );
      })
      .join("");

    const detail = renderSessionDetailTable(mappedSessions, {
      title: safeOptions.detailTitle || "Detalle de sesiones",
      page: safeOptions.detailPage || 1,
      pageSize: safeOptions.detailPageSize || 20,
    });

    output.innerHTML =
      '<div class="schedule-board-wrap">' +
      '<table class="schedule-board-table">' +
      '<thead><tr><th class="schedule-board-time-head">Horario</th>' +
      BOARD_DAYS.map(function (dayName) {
        return "<th>" + dayName + "</th>";
      }).join("") +
      "</tr></thead>" +
      "<tbody>" +
      rowHtml +
      "</tbody></table></div>" +
      '<p class="schedule-board-scroll-hint">Desliza lateralmente para ver todo el horario.</p>' +
      detail.html;
    output.style.display = "block";

    return {
      currentPage: detail.currentPage,
      totalItems: detail.totalItems,
    };
  }

  function buildGeneratedMappedSessions() {
    const selectedSubject = getFilterValue(generatedFilterIds.subjectId);
    const forceWorkCenterLabel = isWorkCenterSubjectValue(selectedSubject);
    const filtered = getFilteredSessions(state.latestGeneratedSchedules, generatedFilterIds);

    return filtered
      .map(function (session) {
        return mapSessionForBoard(session, {
          forceWorkCenterSubjectLabel: forceWorkCenterLabel,
        });
      })
      .filter(Boolean)
      .sort(function (left, right) {
        return left.start - right.start;
      });
  }

  function buildGeneratedMappedSessionsAll() {
    return state.latestGeneratedSchedules
      .map(function (session) {
        return mapSessionForBoard(session, {});
      })
      .filter(Boolean)
      .sort(function (left, right) {
        return left.start - right.start;
      });
  }

  function resetGeneratedDragState() {
    state.generatedDragState.sourceScheduleId = null;
    state.generatedDragState.sourceDay = "";
    state.generatedDragState.sourceStart = "";
    state.generatedDragState.sourceEnd = "";
    state.generatedDragState.sourceSlotKey = "";
  }

  function clearGeneratedDropFeedback() {
    const output = document.getElementById("generatedWorkspaceOutput");
    if (!output) {
      return;
    }

    output
      .querySelectorAll(
        ".schedule-board-cell-drop-hover, .schedule-board-cell-drop-valid, .schedule-board-cell-drop-invalid",
      )
      .forEach(function (cell) {
        cell.classList.remove(
          "schedule-board-cell-drop-hover",
          "schedule-board-cell-drop-valid",
          "schedule-board-cell-drop-invalid",
        );
      });
  }

  function upsertGeneratedSchedules(updatedSchedules) {
    if (!Array.isArray(updatedSchedules) || !updatedSchedules.length) {
      return;
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

  function refreshGeneratedDetailBlock(mappedSessions) {
    const output = document.getElementById("generatedWorkspaceOutput");
    if (!output) {
      return;
    }

    const detailBlock = output.querySelector(".schedule-detail-block");
    if (!detailBlock) {
      return;
    }

    const detail = renderSessionDetailTable(mappedSessions, {
      title: "Detalle de sesiones generadas",
      page: state.generatedDetailPage,
      pageSize: state.detailPageSize,
    });

    state.generatedDetailPage = detail && detail.currentPage ? detail.currentPage : 1;
    detailBlock.outerHTML = detail.html;
  }

  function updateGeneratedBoardCells(slotKeys, mappedSessions) {
    const output = document.getElementById("generatedWorkspaceOutput");
    if (!output) {
      return;
    }

    const uniqueSlotKeys = Array.from(
      new Set(
        (slotKeys || []).filter(function (key) {
          return !!key;
        }),
      ),
    );

    if (!uniqueSlotKeys.length) {
      return;
    }

    const byCellKey = new Map();
    (mappedSessions || []).forEach(function (session) {
      const key = createBoardCellKey(session.dayName, session.startHm, session.endHm);
      if (!byCellKey.has(key)) {
        byCellKey.set(key, []);
      }
      byCellKey.get(key).push(session);
    });

    uniqueSlotKeys.forEach(function (slotKey) {
      const cell = output.querySelector('.schedule-board-cell[data-board-key="' + slotKey + '"]');
      if (!cell) {
        return;
      }

      const entries = byCellKey.get(slotKey) || [];
      cell.innerHTML = entries.length
        ? entries
            .map(function (entry) {
              return renderSessionCard(entry, { enableDragDrop: true });
            })
            .join("")
        : renderEmptyCell();

      cell.classList.remove("schedule-board-cell-updated");
      void cell.offsetWidth;
      cell.classList.add("schedule-board-cell-updated");
    });

    window.setTimeout(function () {
      uniqueSlotKeys.forEach(function (slotKey) {
        const cell = output.querySelector('.schedule-board-cell[data-board-key="' + slotKey + '"]');
        if (cell) {
          cell.classList.remove("schedule-board-cell-updated");
        }
      });
    }, CELL_UPDATE_ANIMATION_MS);
  }

  function evaluateGeneratedDropCandidate(targetCell, forcedTargetScheduleId) {
    const dragState = state.generatedDragState;
    const sourceScheduleId = Number.parseInt(dragState.sourceScheduleId, 10);
    if (!Number.isInteger(sourceScheduleId) || sourceScheduleId <= 0) {
      return { valid: false, reason: "no_source" };
    }

    if (!(targetCell instanceof HTMLElement)) {
      return { valid: false, reason: "no_target_cell" };
    }

    const targetDay = targetCell.dataset.boardDay || "";
    const targetStart = targetCell.dataset.boardStart || "";
    const targetEnd = targetCell.dataset.boardEnd || "";
    if (!targetDay || !targetStart || !targetEnd || !BOARD_DAY_INDEX[targetDay]) {
      return { valid: false, reason: "invalid_target_slot" };
    }

    const targetSlotKey = createBoardCellKey(targetDay, targetStart, targetEnd);
    let targetScheduleId = Number.parseInt(forcedTargetScheduleId || "", 10);
    if (!Number.isInteger(targetScheduleId) || targetScheduleId <= 0) {
      targetScheduleId = null;
      const fallbackCard = targetCell.querySelector(".schedule-board-card[data-schedule-id]");
      if (fallbackCard) {
        const parsedFallback = Number.parseInt(fallbackCard.dataset.scheduleId || "", 10);
        if (Number.isInteger(parsedFallback) && parsedFallback > 0 && parsedFallback !== sourceScheduleId) {
          targetScheduleId = parsedFallback;
        }
      }
    }

    const sameSlot = dragState.sourceSlotKey === targetSlotKey;
    if (sameSlot && !targetScheduleId) {
      return {
        valid: false,
        reason: "same_slot",
        mode: "move",
        sourceScheduleId: sourceScheduleId,
        targetScheduleId: null,
        sourceSlotKey: dragState.sourceSlotKey,
        targetSlotKey: targetSlotKey,
      };
    }

    const mode = targetScheduleId ? "swap" : "move";
    const mappedAll = buildGeneratedMappedSessionsAll();
    const mappedById = new Map(
      mappedAll.map(function (item) {
        return [String(item.id), item];
      }),
    );

    const sourceMapped = mappedById.get(String(sourceScheduleId));
    if (!sourceMapped) {
      return { valid: false, reason: "missing_source_session" };
    }

    const candidateById = new Map();
    candidateById.set(String(sourceScheduleId), {
      id: sourceMapped.id,
      teacherId: sourceMapped.teacherId,
      groupId: sourceMapped.groupId,
      classroomId: sourceMapped.classroomId,
      dayName: targetDay,
      startHm: targetStart,
      endHm: targetEnd,
    });

    if (mode === "swap") {
      const targetMapped = mappedById.get(String(targetScheduleId));
      if (!targetMapped) {
        return { valid: false, reason: "missing_target_session" };
      }

      candidateById.set(String(targetScheduleId), {
        id: targetMapped.id,
        teacherId: targetMapped.teacherId,
        groupId: targetMapped.groupId,
        classroomId: targetMapped.classroomId,
        dayName: dragState.sourceDay,
        startHm: dragState.sourceStart,
        endHm: dragState.sourceEnd,
      });
    }

    const changedIds = Array.from(candidateById.keys());
    for (let changedIndex = 0; changedIndex < changedIds.length; changedIndex += 1) {
      const changedId = changedIds[changedIndex];
      const candidate = candidateById.get(changedId);
      for (let sessionIndex = 0; sessionIndex < mappedAll.length; sessionIndex += 1) {
        const other = mappedAll[sessionIndex];
        const otherId = String(other.id);
        if (otherId === changedId) {
          continue;
        }

        const otherCandidate = candidateById.get(otherId) || other;
        if (candidate.dayName !== otherCandidate.dayName) {
          continue;
        }

        if (!hmRangesOverlap(candidate.startHm, candidate.endHm, otherCandidate.startHm, otherCandidate.endHm)) {
          continue;
        }

        if (candidate.teacherId && otherCandidate.teacherId && candidate.teacherId === otherCandidate.teacherId) {
          return { valid: false, reason: "teacher_conflict" };
        }

        if (candidate.groupId && otherCandidate.groupId && candidate.groupId === otherCandidate.groupId) {
          return { valid: false, reason: "group_conflict" };
        }

        if (
          candidate.classroomId &&
          otherCandidate.classroomId &&
          candidate.classroomId === otherCandidate.classroomId
        ) {
          return { valid: false, reason: "classroom_conflict" };
        }
      }
    }

    return {
      valid: true,
      mode: mode,
      sourceScheduleId: sourceScheduleId,
      targetScheduleId: targetScheduleId,
      sourceSlotKey: dragState.sourceSlotKey,
      targetSlotKey: targetSlotKey,
      sourceDay: dragState.sourceDay,
      sourceStart: dragState.sourceStart,
      sourceEnd: dragState.sourceEnd,
      targetDay: targetDay,
      targetStart: targetStart,
      targetEnd: targetEnd,
    };
  }

  async function applyGeneratedDropChange(candidate) {
    if (!candidate || !candidate.valid) {
      return;
    }

    if (state.generatedMoveInFlight) {
      return;
    }

    state.generatedMoveInFlight = true;
    const result = await apiJson(MOVE_API_PATH, "POST", {
      mode: candidate.mode,
      source_slot: {
        schedule_id: candidate.sourceScheduleId,
        day: candidate.sourceDay,
        start: candidate.sourceStart,
        end: candidate.sourceEnd,
      },
      target_slot: {
        day: candidate.targetDay,
        start: candidate.targetStart,
        end: candidate.targetEnd,
        schedule_id: candidate.targetScheduleId || null,
      },
    });
    state.generatedMoveInFlight = false;

    if (!result.ok) {
      showAlert("error", extractApiErrorMessage(result.data, "No se pudo aplicar el cambio manual."));
      return;
    }

    if (result.data && result.data.no_changes) {
      showAlert("info", "No se aplicaron cambios.");
      return;
    }

    upsertGeneratedSchedules(result.data && result.data.affected_schedules);

    const affectedKeys = [candidate.sourceSlotKey, candidate.targetSlotKey];
    if (Array.isArray(result.data && result.data.affected_slots)) {
      result.data.affected_slots.forEach(function (slot) {
        if (!slot || !slot.day || !slot.start || !slot.end) {
          return;
        }
        affectedKeys.push(createBoardCellKey(slot.day, slot.start, slot.end));
      });
    }

    const mappedVisible = buildGeneratedMappedSessions();
    updateGeneratedBoardCells(affectedKeys, mappedVisible);
    refreshGeneratedDetailBlock(mappedVisible);

    const successMessage =
      candidate.mode === "swap" ? "Intercambio aplicado correctamente." : "Sesión movida correctamente.";
    showAlert("success", successMessage);
  }

  function buildSavedMappedSessions() {
    const selectedGroup = getSelectedSavedGroup();
    if (!selectedGroup) {
      return [];
    }

    const selectedSubject = getFilterValue(savedFilterIds.subjectId);
    const forceWorkCenterLabel = isWorkCenterSubjectValue(selectedSubject);
    const sourceSessions = Array.isArray(selectedGroup.sessions) ? selectedGroup.sessions : [];
    const filtered = getFilteredSessions(sourceSessions, savedFilterIds);

    return filtered
      .map(function (session) {
        return mapSessionForBoard(session, {
          forceWorkCenterSubjectLabel: forceWorkCenterLabel,
        });
      })
      .filter(Boolean)
      .sort(function (left, right) {
        return left.start - right.start;
      });
  }

  function buildSavedMappedSessionsAll() {
    const selectedGroup = getSelectedSavedGroup();
    if (!selectedGroup) {
      return [];
    }

    const sourceSessions = Array.isArray(selectedGroup.sessions) ? selectedGroup.sessions : [];
    return sourceSessions
      .map(function (session) {
        return mapSessionForBoard(session, {});
      })
      .filter(Boolean)
      .sort(function (left, right) {
        return left.start - right.start;
      });
  }

  function resetSavedDragState() {
    state.savedDragState.sourceScheduleId = null;
    state.savedDragState.sourceDay = "";
    state.savedDragState.sourceStart = "";
    state.savedDragState.sourceEnd = "";
    state.savedDragState.sourceSlotKey = "";
  }

  function clearSavedDropFeedback() {
    const output = document.getElementById("savedWorkspaceOutput");
    if (!output) {
      return;
    }

    output
      .querySelectorAll(
        ".schedule-board-cell-drop-hover, .schedule-board-cell-drop-valid, .schedule-board-cell-drop-invalid",
      )
      .forEach(function (cell) {
        cell.classList.remove(
          "schedule-board-cell-drop-hover",
          "schedule-board-cell-drop-valid",
          "schedule-board-cell-drop-invalid",
        );
      });
  }

  function upsertSelectedSavedSchedules(updatedSchedules) {
    if (!Array.isArray(updatedSchedules) || !updatedSchedules.length) {
      return;
    }

    const selectedGroup = getSelectedSavedGroup();
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

  function refreshSavedDetailBlock(mappedSessions) {
    const output = document.getElementById("savedWorkspaceOutput");
    if (!output) {
      return;
    }

    const detailBlock = output.querySelector(".schedule-detail-block");
    if (!detailBlock) {
      return;
    }

    const detail = renderSessionDetailTable(mappedSessions, {
      title: "Detalle de sesiones guardadas",
      page: state.savedDetailPage,
      pageSize: state.detailPageSize,
    });

    state.savedDetailPage = detail && detail.currentPage ? detail.currentPage : 1;
    detailBlock.outerHTML = detail.html;
  }

  function updateSavedBoardCells(slotKeys, mappedSessions) {
    const output = document.getElementById("savedWorkspaceOutput");
    if (!output) {
      return;
    }

    const uniqueSlotKeys = Array.from(
      new Set(
        (slotKeys || []).filter(function (key) {
          return !!key;
        }),
      ),
    );

    if (!uniqueSlotKeys.length) {
      return;
    }

    const byCellKey = new Map();
    (mappedSessions || []).forEach(function (session) {
      const key = createBoardCellKey(session.dayName, session.startHm, session.endHm);
      if (!byCellKey.has(key)) {
        byCellKey.set(key, []);
      }
      byCellKey.get(key).push(session);
    });

    uniqueSlotKeys.forEach(function (slotKey) {
      const cell = output.querySelector('.schedule-board-cell[data-board-key="' + slotKey + '"]');
      if (!cell) {
        return;
      }

      const entries = byCellKey.get(slotKey) || [];
      cell.innerHTML = entries.length
        ? entries
            .map(function (entry) {
              return renderSessionCard(entry, { enableDragDrop: true });
            })
            .join("")
        : renderEmptyCell();

      cell.classList.remove("schedule-board-cell-updated");
      void cell.offsetWidth;
      cell.classList.add("schedule-board-cell-updated");
    });

    window.setTimeout(function () {
      uniqueSlotKeys.forEach(function (slotKey) {
        const cell = output.querySelector('.schedule-board-cell[data-board-key="' + slotKey + '"]');
        if (cell) {
          cell.classList.remove("schedule-board-cell-updated");
        }
      });
    }, CELL_UPDATE_ANIMATION_MS);
  }

  function evaluateSavedDropCandidate(targetCell, forcedTargetScheduleId) {
    const selectedGroup = getSelectedSavedGroup();
    if (!selectedGroup) {
      return { valid: false, reason: "no_saved_group" };
    }

    const dragState = state.savedDragState;
    const sourceScheduleId = Number.parseInt(dragState.sourceScheduleId, 10);
    if (!Number.isInteger(sourceScheduleId) || sourceScheduleId <= 0) {
      return { valid: false, reason: "no_source" };
    }

    if (!(targetCell instanceof HTMLElement)) {
      return { valid: false, reason: "no_target_cell" };
    }

    const targetDay = targetCell.dataset.boardDay || "";
    const targetStart = targetCell.dataset.boardStart || "";
    const targetEnd = targetCell.dataset.boardEnd || "";
    if (!targetDay || !targetStart || !targetEnd || !BOARD_DAY_INDEX[targetDay]) {
      return { valid: false, reason: "invalid_target_slot" };
    }

    const targetSlotKey = createBoardCellKey(targetDay, targetStart, targetEnd);
    let targetScheduleId = Number.parseInt(forcedTargetScheduleId || "", 10);
    if (!Number.isInteger(targetScheduleId) || targetScheduleId <= 0) {
      targetScheduleId = null;
      const fallbackCard = targetCell.querySelector(".schedule-board-card[data-schedule-id]");
      if (fallbackCard) {
        const parsedFallback = Number.parseInt(fallbackCard.dataset.scheduleId || "", 10);
        if (Number.isInteger(parsedFallback) && parsedFallback > 0 && parsedFallback !== sourceScheduleId) {
          targetScheduleId = parsedFallback;
        }
      }
    }

    const sameSlot = dragState.sourceSlotKey === targetSlotKey;
    if (sameSlot && !targetScheduleId) {
      return {
        valid: false,
        reason: "same_slot",
        mode: "move",
        sourceScheduleId: sourceScheduleId,
        targetScheduleId: null,
        sourceSlotKey: dragState.sourceSlotKey,
        targetSlotKey: targetSlotKey,
      };
    }

    const mode = targetScheduleId ? "swap" : "move";
    const mappedAll = buildSavedMappedSessionsAll();
    const mappedById = new Map(
      mappedAll.map(function (item) {
        return [String(item.id), item];
      }),
    );

    const sourceMapped = mappedById.get(String(sourceScheduleId));
    if (!sourceMapped) {
      return { valid: false, reason: "missing_source_session" };
    }

    const candidateById = new Map();
    candidateById.set(String(sourceScheduleId), {
      id: sourceMapped.id,
      teacherId: sourceMapped.teacherId,
      groupId: sourceMapped.groupId,
      classroomId: sourceMapped.classroomId,
      dayName: targetDay,
      startHm: targetStart,
      endHm: targetEnd,
    });

    if (mode === "swap") {
      const targetMapped = mappedById.get(String(targetScheduleId));
      if (!targetMapped) {
        return { valid: false, reason: "missing_target_session" };
      }

      candidateById.set(String(targetScheduleId), {
        id: targetMapped.id,
        teacherId: targetMapped.teacherId,
        groupId: targetMapped.groupId,
        classroomId: targetMapped.classroomId,
        dayName: dragState.sourceDay,
        startHm: dragState.sourceStart,
        endHm: dragState.sourceEnd,
      });
    }

    const changedIds = Array.from(candidateById.keys());
    for (let changedIndex = 0; changedIndex < changedIds.length; changedIndex += 1) {
      const changedId = changedIds[changedIndex];
      const candidate = candidateById.get(changedId);
      for (let sessionIndex = 0; sessionIndex < mappedAll.length; sessionIndex += 1) {
        const other = mappedAll[sessionIndex];
        const otherId = String(other.id);
        if (otherId === changedId) {
          continue;
        }

        const otherCandidate = candidateById.get(otherId) || other;
        if (candidate.dayName !== otherCandidate.dayName) {
          continue;
        }

        if (!hmRangesOverlap(candidate.startHm, candidate.endHm, otherCandidate.startHm, otherCandidate.endHm)) {
          continue;
        }

        if (candidate.teacherId && otherCandidate.teacherId && candidate.teacherId === otherCandidate.teacherId) {
          return { valid: false, reason: "teacher_conflict" };
        }

        if (candidate.groupId && otherCandidate.groupId && candidate.groupId === otherCandidate.groupId) {
          return { valid: false, reason: "group_conflict" };
        }

        if (
          candidate.classroomId &&
          otherCandidate.classroomId &&
          candidate.classroomId === otherCandidate.classroomId
        ) {
          return { valid: false, reason: "classroom_conflict" };
        }
      }
    }

    return {
      valid: true,
      mode: mode,
      sourceScheduleId: sourceScheduleId,
      targetScheduleId: targetScheduleId,
      sourceSlotKey: dragState.sourceSlotKey,
      targetSlotKey: targetSlotKey,
      sourceDay: dragState.sourceDay,
      sourceStart: dragState.sourceStart,
      sourceEnd: dragState.sourceEnd,
      targetDay: targetDay,
      targetStart: targetStart,
      targetEnd: targetEnd,
    };
  }

  async function applySavedDropChange(candidate) {
    if (!candidate || !candidate.valid) {
      return;
    }

    if (state.savedMoveInFlight) {
      return;
    }

    state.savedMoveInFlight = true;
    const result = await apiJson(MOVE_API_PATH, "POST", {
      mode: candidate.mode,
      source_slot: {
        schedule_id: candidate.sourceScheduleId,
        day: candidate.sourceDay,
        start: candidate.sourceStart,
        end: candidate.sourceEnd,
      },
      target_slot: {
        day: candidate.targetDay,
        start: candidate.targetStart,
        end: candidate.targetEnd,
        schedule_id: candidate.targetScheduleId || null,
      },
    });
    state.savedMoveInFlight = false;

    if (!result.ok) {
      showAlert("error", extractApiErrorMessage(result.data, "No se pudo aplicar el cambio manual."));
      return;
    }

    if (result.data && result.data.no_changes) {
      showAlert("info", "No se aplicaron cambios.");
      return;
    }

    upsertSelectedSavedSchedules(result.data && result.data.affected_schedules);

    state.savedTimetableGroups.sort(function (left, right) {
      const updatedDiff = toDateMillis(right.updated_at) - toDateMillis(left.updated_at);
      if (updatedDiff !== 0) {
        return updatedDiff;
      }
      return String(left.name || "").localeCompare(String(right.name || ""), "es");
    });
    syncSelectedSavedIndexByName();
    renderSavedCards();

    const affectedKeys = [candidate.sourceSlotKey, candidate.targetSlotKey];
    if (Array.isArray(result.data && result.data.affected_slots)) {
      result.data.affected_slots.forEach(function (slot) {
        if (!slot || !slot.day || !slot.start || !slot.end) {
          return;
        }
        affectedKeys.push(createBoardCellKey(slot.day, slot.start, slot.end));
      });
    }

    const mappedVisible = buildSavedMappedSessions();
    updateSavedBoardCells(affectedKeys, mappedVisible);
    refreshSavedDetailBlock(mappedVisible);

    const successMessage =
      candidate.mode === "swap" ? "Intercambio aplicado correctamente." : "Sesión movida correctamente.";
    showAlert("success", successMessage);
  }

  function getFilterValue(selectId) {
    const select = document.getElementById(selectId);
    return select ? select.value : "";
  }

  function setSelectOptions(selectId, optionValues, emptyLabel) {
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
          return '<option value="' + value + '">' + value + "</option>";
        })
        .join("");

    if (currentValue && values.indexOf(currentValue) >= 0) {
      select.value = currentValue;
    }

    syncScheduleFilterDropdown(select);
  }

  function populateWorkspaceFiltersFromSessions(sessions, filterIds) {
    const courseNames = Array.from(
      new Set(
        (sessions || [])
          .map(function (session) {
            return session.group_name;
          })
          .filter(Boolean),
      ),
    );

    const teacherNames = Array.from(
      new Set(
        (sessions || [])
          .map(function (session) {
            return session.teacher_name;
          })
          .filter(Boolean),
      ),
    );

    const subjectNames = Array.from(
      new Set(
        (sessions || [])
          .map(function (session) {
            return session.subject_name;
          })
          .filter(Boolean),
      ),
    );

    if (hasWorkCenterSubjects(sessions) && subjectNames.indexOf(WORK_CENTER_SUBJECT) < 0) {
      subjectNames.push(WORK_CENTER_SUBJECT);
    }

    setSelectOptions(filterIds.courseId, courseNames, "Todos los cursos");
    setSelectOptions(filterIds.teacherId, teacherNames, "Todos los profesores");
    setSelectOptions(filterIds.subjectId, subjectNames, "Todas las asignaturas");
  }

  function getFilteredSessions(sessions, filterIds) {
    const selectedCourse = getFilterValue(filterIds.courseId);
    const selectedTeacher = getFilterValue(filterIds.teacherId);
    const selectedSubject = getFilterValue(filterIds.subjectId);

    return (sessions || []).filter(function (session) {
      if (selectedCourse && normalizeForCompare(session.group_name) !== normalizeForCompare(selectedCourse)) {
        return false;
      }

      if (selectedTeacher && normalizeForCompare(session.teacher_name) !== normalizeForCompare(selectedTeacher)) {
        return false;
      }

      if (!selectedSubject) {
        return true;
      }

      if (isWorkCenterSubjectValue(selectedSubject)) {
        return getSessionSubjectType(session) === "TC";
      }

      return normalizeForCompare(session.subject_name) === normalizeForCompare(selectedSubject);
    });
  }

  function updateGeneratedWorkspaceHeader() {
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

  function updateSavedWorkspaceHeader(selectedGroup) {
    const title = document.getElementById("savedWorkspaceTitle");
    if (title) {
      title.textContent = selectedGroup ? "Horario Escolar - " + selectedGroup.name : "Horario Guardado";
    }
  }

  function toggleSection(sectionId, shouldShow) {
    const section = document.getElementById(sectionId);
    if (!section) {
      return;
    }
    section.classList.toggle("d-none", !shouldShow);
  }

  function showGeneratedWorkspace() {
    toggleSection("generatedLandingSection", false);
    toggleSection("generatedWorkspaceSection", true);
  }

  function showGeneratedLanding() {
    toggleSection("generatedLandingSection", true);
    toggleSection("generatedWorkspaceSection", false);
  }

  function showSavedWorkspace() {
    toggleSection("savedPickerSection", false);
    toggleSection("savedWorkspaceSection", true);
  }

  function showSavedPicker() {
    toggleSection("savedPickerSection", true);
    toggleSection("savedWorkspaceSection", false);
    clearSavedDropFeedback();
    resetSavedDragState();
  }

  function renderGeneratedWorkspace() {
    updateGeneratedWorkspaceHeader();

    const selectedSubject = getFilterValue(generatedFilterIds.subjectId);
    const filtered = getFilteredSessions(state.latestGeneratedSchedules, generatedFilterIds);

    const detail = renderScheduleBoard(filtered, "generatedWorkspaceOutput", {
      forceWorkCenterSubjectLabel: isWorkCenterSubjectValue(selectedSubject),
      detailTitle: "Detalle de sesiones generadas",
      detailPage: state.generatedDetailPage,
      detailPageSize: state.detailPageSize,
      enableDragDrop: true,
    });

    state.generatedDetailPage = detail && detail.currentPage ? detail.currentPage : 1;
  }

  function syncSelectedSavedIndexByName() {
    const selectedName = String(state.selectedSavedTimetableName || "").trim();
    if (!selectedName) {
      state.selectedSavedTimetableIndex = null;
      return null;
    }

    const normalized = normalizeForCompare(selectedName);
    const index = state.savedTimetableGroups.findIndex(function (group) {
      return normalizeForCompare(group.name) === normalized;
    });
    if (index < 0) {
      state.selectedSavedTimetableIndex = null;
      state.selectedSavedTimetableName = null;
      return null;
    }

    state.selectedSavedTimetableIndex = index;
    state.selectedSavedTimetableName = state.savedTimetableGroups[index].name;
    return state.savedTimetableGroups[index];
  }

  function getSelectedSavedGroup() {
    if (state.selectedSavedTimetableName) {
      const byName = syncSelectedSavedIndexByName();
      if (byName) {
        return byName;
      }
    }

    if (state.selectedSavedTimetableIndex === null) {
      return null;
    }
    return state.savedTimetableGroups[state.selectedSavedTimetableIndex] || null;
  }

  function renderSavedWorkspace() {
    const selectedGroup = getSelectedSavedGroup();
    updateSavedWorkspaceHeader(selectedGroup);

    const output = document.getElementById("savedWorkspaceOutput");
    if (!selectedGroup || !output) {
      if (output) {
        output.innerHTML = "";
        output.style.display = "none";
      }
      return;
    }

    const selectedSubject = getFilterValue(savedFilterIds.subjectId);
    const sourceSessions = Array.isArray(selectedGroup.sessions) ? selectedGroup.sessions : [];
    const filtered = getFilteredSessions(sourceSessions, savedFilterIds);

    const detail = renderScheduleBoard(filtered, "savedWorkspaceOutput", {
      forceWorkCenterSubjectLabel: isWorkCenterSubjectValue(selectedSubject),
      detailTitle: "Detalle de sesiones guardadas",
      detailPage: state.savedDetailPage,
      detailPageSize: state.detailPageSize,
      enableDragDrop: true,
    });

    state.savedDetailPage = detail && detail.currentPage ? detail.currentPage : 1;
  }

  function buildSavedTimetableGroups(items) {
    const byName = new Map();

    (items || []).forEach(function (item) {
      const name = String(item.name || "").trim();
      if (!name) {
        return;
      }

      if (!byName.has(name)) {
        byName.set(name, {
          name: name,
          updated_at: item.updated_at || "",
          sessions: [],
          sessionsLoaded: false,
        });
      }

      const group = byName.get(name);
      if (item.updated_at && toDateMillis(item.updated_at) > toDateMillis(group.updated_at)) {
        group.updated_at = item.updated_at;
      }
    });

    return Array.from(byName.values()).sort(function (left, right) {
      const updatedDiff = toDateMillis(right.updated_at) - toDateMillis(left.updated_at);
      if (updatedDiff !== 0) {
        return updatedDiff;
      }
      return String(left.name || "").localeCompare(String(right.name || ""), "es");
    });
  }

  function renderSavedCards() {
    const container = document.getElementById("savedScheduleCards");
    if (!container) {
      return;
    }

    if (!state.savedTimetableGroups.length) {
      container.innerHTML =
        '<div class="col"><article class="saved-card-placeholder"><p class="text-secondary mb-0">No hay horarios guardados todavía.</p></article></div>';
      return;
    }

    container.innerHTML = state.savedTimetableGroups
      .map(function (group, index) {
        return (
          '<div class="col"><article class="saved-card" data-action="open" data-index="' +
          index +
          '" tabindex="0" role="button" aria-label="Abrir horario guardado ' +
          group.name +
          '">' +
          '<div class="saved-card-body">' +
          '<h3 class="saved-card-title">' +
          group.name +
          "</h3>" +
          '<p class="saved-card-date">Última actualización el ' +
          toIsoDateDisplay(group.updated_at) +
          "</p>" +
          "</div>" +
          '<div class="saved-card-footer">' +
          '<button type="button" class="btn btn-link text-danger p-0 saved-card-delete" data-action="delete" data-index="' +
          index +
          '" title="Eliminar horario" aria-label="Eliminar horario ' +
          group.name +
          '">' +
          '<i data-lucide="trash-2" class="saved-card-delete-icon" aria-hidden="true"></i></button>' +
          "</div>" +
          "</article></div>"
        );
      })
      .join("");

    if (window.orariooAuth && typeof window.orariooAuth.initLucideIcons === "function") {
      window.orariooAuth.initLucideIcons();
    }
  }

  async function fetchSavedSessionsByName(timetableName) {
    const name = String(timetableName || "").trim();
    if (!name) {
      return null;
    }

    const result = await apiJson(SAVED_DETAIL_API_PATH + "?timetable_name=" + encodeURIComponent(name));
    if (!result.ok) {
      showAlert("error", extractApiErrorMessage(result.data, "No se pudo cargar el horario guardado."));
      return null;
    }

    return listFromPayload(result.data);
  }

  async function openSavedWorkspace(index) {
    const selected = state.savedTimetableGroups[index];
    if (!selected) {
      showAlert("error", "Horario guardado no encontrado.");
      return false;
    }

    state.selectedSavedTimetableIndex = index;
    state.selectedSavedTimetableName = selected.name;
    state.savedDetailPage = 1;

    showSavedWorkspace();

    if (!selected.sessionsLoaded) {
      const output = document.getElementById("savedWorkspaceOutput");
      if (output) {
        output.style.display = "block";
        output.innerHTML =
          '<article class="saved-card-placeholder"><p class="text-secondary mb-0">Cargando sesiones...</p></article>';
      }

      const sessions = await fetchSavedSessionsByName(selected.name);
      if (sessions === null) {
        showSavedPicker();
        return false;
      }

      selected.sessions = sessions;
      selected.sessionsLoaded = true;

      const latestUpdatedAt = sessions.reduce(function (latest, session) {
        if (!session || !session.updated_at) {
          return latest;
        }
        return toDateMillis(session.updated_at) > toDateMillis(latest) ? session.updated_at : latest;
      }, selected.updated_at || "");

      if (latestUpdatedAt) {
        selected.updated_at = latestUpdatedAt;
      }
      renderSavedCards();
    }

    populateWorkspaceFiltersFromSessions(selected.sessions, savedFilterIds);
    renderSavedWorkspace();
    return true;
  }

  async function openSavedWorkspaceByName(timetableName) {
    const normalized = normalizeForCompare(timetableName);
    if (!normalized) {
      return false;
    }

    const index = state.savedTimetableGroups.findIndex(function (group) {
      return normalizeForCompare(group.name) === normalized;
    });

    if (index < 0) {
      return false;
    }

    return openSavedWorkspace(index);
  }

  async function deleteSavedTimetable(index) {
    const selected = state.savedTimetableGroups[index];
    if (!selected) {
      showAlert("error", "Horario guardado no encontrado.");
      return;
    }

    if (!window.confirm('¿Eliminar el horario guardado "' + selected.name + '"?')) {
      return;
    }

    const result = await apiJson("/schedules/delete-saved-timetable/", "POST", {
      timetable_name: selected.name,
    });

    if (!result.ok) {
      showAlert("error", extractApiErrorMessage(result.data, "No se pudo eliminar el horario guardado."));
      return;
    }

    if (normalizeForCompare(state.selectedSavedTimetableName) === normalizeForCompare(selected.name)) {
      state.selectedSavedTimetableIndex = null;
      state.selectedSavedTimetableName = null;
      showSavedPicker();
    }

    showAlert("success", "Horario eliminado correctamente.");
    await loadSavedSchedules();
  }

  async function loadSavedSchedules() {
    const result = await apiJson(SAVED_SUMMARY_API_PATH);
    if (!result.ok) {
      state.savedTimetableGroups = [];
      state.selectedSavedTimetableIndex = null;
      state.selectedSavedTimetableName = null;
      renderSavedCards();
      showAlert("error", extractApiErrorMessage(result.data, "No se pudieron cargar los horarios guardados."));
      return;
    }

    let selectedName = state.selectedSavedTimetableName;
    const routeRequestedName = state.initialSavedRouteName;
    if (!selectedName && routeRequestedName) {
      selectedName = routeRequestedName;
    }

    state.savedTimetableGroups = buildSavedTimetableGroups(listFromPayload(result.data));
    renderSavedCards();

    if (selectedName) {
      state.selectedSavedTimetableName = selectedName;
      syncSelectedSavedIndexByName();
    }

    if (routeRequestedName) {
      state.initialSavedRouteName = "";
      if (!(await openSavedWorkspaceByName(routeRequestedName))) {
        showSavedPicker();
        showAlert("warning", 'No se encontró el horario guardado "' + routeRequestedName + '".');
      }
      return;
    }

    if (savedSection && !document.getElementById("savedWorkspaceSection")?.classList.contains("d-none")) {
      const currentName = state.selectedSavedTimetableName;
      if (!currentName) {
        showSavedPicker();
        return;
      }

      if (!(await openSavedWorkspaceByName(currentName))) {
        showSavedPicker();
      }
    }
  }

  function getExportEntitySelectId(entityType) {
    if (entityType === "group") {
      return "exportGroupSelect";
    }
    if (entityType === "teacher") {
      return "exportTeacherSelect";
    }
    if (entityType === "classroom") {
      return "exportClassroomSelect";
    }
    return null;
  }

  function getEntitiesByType(entityType) {
    if (entityType === "group") {
      return state.currentGroups;
    }
    if (entityType === "teacher") {
      return state.currentTeachers;
    }
    if (entityType === "classroom") {
      return state.currentClassrooms;
    }
    return [];
  }

  function populateExportEntitySelect(entityType) {
    const containerId = getExportEntitySelectId(entityType);
    const container = containerId ? document.getElementById(containerId) : null;
    if (!container) {
      return;
    }

    const checkedValues = new Set(
      Array.from(container.querySelectorAll("input[type='checkbox']:checked")).map(function (input) {
        return input.value;
      }),
    );

    container.innerHTML = getEntitiesByType(entityType)
      .slice()
      .sort(function (left, right) {
        return String(left.name || "").localeCompare(String(right.name || ""), "es");
      })
      .map(function (entity) {
        const checked = checkedValues.has(String(entity.id)) ? " checked" : "";
        return (
          '<div class="checkbox-item">' +
          '<input type="checkbox" id="check-' +
          entityType +
          "-" +
          entity.id +
          '" value="' +
          entity.id +
          '"' +
          checked +
          ">" +
          '<label for="check-' +
          entityType +
          "-" +
          entity.id +
          '">' +
          (entity.name || "#" + entity.id) +
          "</label>" +
          "</div>"
        );
      })
      .join("");
  }

  function populateAllExportEntitySelects() {
    ["group", "teacher", "classroom"].forEach(function (entityType) {
      populateExportEntitySelect(entityType);
    });
  }

  function getExportSelectionForEntity(entityType) {
    const containerId = getExportEntitySelectId(entityType);
    const container = containerId ? document.getElementById(containerId) : null;
    if (!container) {
      return [];
    }

    return Array.from(container.querySelectorAll("input[type='checkbox']:checked"))
      .map(function (checkbox) {
        return Number.parseInt(checkbox.value, 10);
      })
      .filter(function (value) {
        return Number.isInteger(value) && value > 0;
      });
  }

  function renderExportEntityCards() {
    document.querySelectorAll(".export-entity-card").forEach(function (button) {
      const entityType = button.dataset.exportEntity;
      const active = !!state.exportEntityState[entityType];
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
  }

  function hasAnyExportSelection() {
    if (Object.values(state.exportEntityState).some(Boolean)) {
      return true;
    }

    return ["group", "teacher", "classroom"].some(function (entityType) {
      return getExportSelectionForEntity(entityType).length > 0;
    });
  }

  function openExportModal(config) {
    const modal = document.getElementById("exportModal");
    const contextText = document.getElementById("exportContextText");
    const exportFormat = document.getElementById("exportFormat");

    if (!modal || !contextText || !exportFormat) {
      return;
    }

    const safeConfig = config || {};
    state.currentExportSource = safeConfig.source || "generated";
    state.currentExportSavedName = String(safeConfig.savedName || "").trim();

    if (state.currentExportSource === "saved") {
      const activeName = state.currentExportSavedName || state.selectedSavedTimetableName || state.generatedSavedName;
      state.currentExportSavedName = activeName || "";
      contextText.textContent = activeName
        ? 'Exportar sesiones de "' + activeName + '"'
        : "Exportar sesiones de horarios guardados";
    } else {
      contextText.textContent = "Exportar sesiones de horario generado";
    }

    state.exportEntityState.group = false;
    state.exportEntityState.teacher = false;
    state.exportEntityState.classroom = false;

    exportFormat.value = safeConfig.format || "csv";
    exportFormat.disabled = !!safeConfig.lockFormat;

    populateAllExportEntitySelects();

    ["exportGroupSelect", "exportTeacherSelect", "exportClassroomSelect"].forEach(function (id) {
      const container = document.getElementById(id);
      if (!container) {
        return;
      }
      Array.from(container.querySelectorAll("input[type='checkbox']")).forEach(function (checkbox) {
        checkbox.checked = false;
      });
    });

    renderExportEntityCards();
    modal.classList.add("show");
  }

  function closeExportModal() {
    const modal = document.getElementById("exportModal");
    const exportFormat = document.getElementById("exportFormat");
    if (exportFormat) {
      exportFormat.disabled = false;
    }
    if (modal) {
      modal.classList.remove("show");
    }
  }

  function openSaveGeneratedModal() {
    if (!state.latestGeneratedSchedules.length) {
      showAlert("error", "No hay un horario generado para guardar.");
      return;
    }

    if (state.generatedSaved) {
      showAlert("info", "Este horario ya está guardado.");
      return;
    }

    const modal = document.getElementById("saveGeneratedModal");
    const input = document.getElementById("saveGeneratedNameInput");
    if (!modal || !input) {
      showAlert("error", "No se pudo abrir el formulario de guardado.");
      return;
    }

    input.value = state.generatedSavedName || buildDefaultTimetableName();
    modal.classList.add("show");

    window.setTimeout(function () {
      input.focus();
      input.select();
    }, 0);
  }

  function closeSaveGeneratedModal() {
    const modal = document.getElementById("saveGeneratedModal");
    if (modal) {
      modal.classList.remove("show");
    }
  }

  function hasSavedTimetableNameCollision(timetableName) {
    const normalized = normalizeForCompare(timetableName);
    return state.savedTimetableGroups.some(function (group) {
      return normalizeForCompare(group.name) === normalized;
    });
  }

  async function downloadFileFromApi(endpoint) {
    const response = await window.orariooAuth.apiFetch("/api" + endpoint, {
      method: "GET",
    });

    if (!response.ok) {
      let errorData = {};
      try {
        errorData = await response.json();
      } catch (_error) {
        errorData = {};
      }
      throw new Error(extractApiErrorMessage(errorData, "No se pudo exportar."));
    }

    const disposition = response.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="?([^";]+)"?/i);
    const fileName = match ? match[1] : "horario_export";

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  }

  async function handleExportConfirm() {
    if (!hasAnyExportSelection()) {
      showAlert("error", "Marca al menos una entidad o selecciona objetos concretos para exportar.");
      return;
    }

    const exportFormat = document.getElementById("exportFormat");
    const format = exportFormat ? exportFormat.value : "csv";
    const selectedGroupIds = getExportSelectionForEntity("group");
    const selectedTeacherIds = getExportSelectionForEntity("teacher");
    const selectedClassroomIds = getExportSelectionForEntity("classroom");

    const params = new URLSearchParams();
    params.set("export_format", format);
    params.set("source", state.currentExportSource);
    params.set("selection_mode", "cards");
    params.set("group_all", state.exportEntityState.group ? "1" : "0");
    params.set("teacher_all", state.exportEntityState.teacher ? "1" : "0");
    params.set("classroom_all", state.exportEntityState.classroom ? "1" : "0");

    if (state.currentExportSource === "saved" && state.currentExportSavedName) {
      params.set("saved_timetable_name", state.currentExportSavedName);
    }

    if (selectedGroupIds.length) {
      params.set("group_ids", selectedGroupIds.join(","));
    }
    if (selectedTeacherIds.length) {
      params.set("teacher_ids", selectedTeacherIds.join(","));
    }
    if (selectedClassroomIds.length) {
      params.set("classroom_ids", selectedClassroomIds.join(","));
    }

    try {
      await downloadFileFromApi("/schedules/export/?" + params.toString());
      closeExportModal();
      showAlert("success", "Exportación completada.");
    } catch (error) {
      showAlert("error", error.message || "No se pudo exportar.");
    }
  }

  function buildDefaultTimetableName() {
    const now = new Date();
    return (
      "Horario " +
      now.toLocaleDateString("es-ES") +
      " " +
      now.toLocaleTimeString("es-ES", {
        hour: "2-digit",
        minute: "2-digit",
      })
    );
  }

  async function handleSaveGeneratedConfirm() {
    if (!state.latestGeneratedSchedules.length) {
      showAlert("error", "No hay un horario generado para guardar.");
      return;
    }

    if (state.generatedSaved) {
      showAlert("info", "Este horario ya está guardado.");
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

    if (hasSavedTimetableNameCollision(timetableName)) {
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

    populateWorkspaceFiltersFromSessions(state.latestGeneratedSchedules, generatedFilterIds);
    renderGeneratedWorkspace();
    await loadSavedSchedules();

    showAlert("success", 'Horario guardado como "' + timetableName + '".');
  }

  function handleSaveGenerated() {
    openSaveGeneratedModal();
  }

  async function handleGenerate() {
    const button = document.getElementById("generateBtn");
    if (button) {
      button.disabled = true;
    }

    clearGeneratedDropFeedback();
    resetGeneratedDragState();

    const result = await apiJson("/schedules/generate/", "POST", {});

    if (button) {
      button.disabled = false;
    }

    if (!result.ok) {
      state.latestGeneratedSchedules = [];
      state.generatedSaved = false;
      state.generatedSavedName = "";
      state.generatedMoveInFlight = false;
      showGeneratedLanding();
      showAlert("error", extractApiErrorMessage(result.data, "No se pudo generar el horario."));
      return;
    }

    state.latestGeneratedSchedules = (result.data && result.data.schedules) || [];
    state.generatedDetailPage = 1;
    state.generatedSaved = false;
    state.generatedSavedName = "";
    state.generatedMoveInFlight = false;

    populateWorkspaceFiltersFromSessions(state.latestGeneratedSchedules, generatedFilterIds);
    showGeneratedWorkspace();
    renderGeneratedWorkspace();

    const generatedCount =
      result.data && result.data.generated_count ? result.data.generated_count : state.latestGeneratedSchedules.length;
    showAlert("success", "Se generaron " + generatedCount + " sesiones.");
  }

  async function handleRegenerate() {
    await handleGenerate();
  }

  function openGeneratedExport(format) {
    const source = state.generatedSaved ? "saved" : "generated";
    const savedName = state.generatedSaved ? state.generatedSavedName : "";
    openExportModal({
      source: source,
      savedName: savedName,
      format: format,
      lockFormat: true,
    });
  }

  async function loadCoreData() {
    const responses = await Promise.all([
      apiJson("/teachers/"),
      apiJson("/classrooms/"),
      apiJson("/groups/"),
      apiJson("/subjects/"),
    ]);

    const teachersResponse = responses[0];
    const classroomsResponse = responses[1];
    const groupsResponse = responses[2];
    const subjectsResponse = responses[3];

    state.currentTeachers = listFromPayload(teachersResponse.data);
    state.currentClassrooms = listFromPayload(classroomsResponse.data);
    state.currentGroups = listFromPayload(groupsResponse.data);
    state.currentSubjects = listFromPayload(subjectsResponse.data);

    setText("statTeachers", getCollectionCount(teachersResponse.data, state.currentTeachers));
    setText("statClassrooms", getCollectionCount(classroomsResponse.data, state.currentClassrooms));
    setText("statGroups", getCollectionCount(groupsResponse.data, state.currentGroups));
    setText("statSubjects", getCollectionCount(subjectsResponse.data, state.currentSubjects));

    populateAllExportEntitySelects();

    if (!teachersResponse.ok || !classroomsResponse.ok || !groupsResponse.ok || !subjectsResponse.ok) {
      showAlert("warning", "Algunos datos administrativos no se pudieron cargar completamente.");
    }
  }

  function bindGeneratedEvents() {
    const generateButton = document.getElementById("generateBtn");
    if (generateButton) {
      generateButton.addEventListener("click", handleGenerate);
    }

    [generatedFilterIds.courseId, generatedFilterIds.teacherId, generatedFilterIds.subjectId].forEach(function (id) {
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
      generatedOutput.addEventListener("dragstart", function (event) {
        const target = event.target;
        if (!(target instanceof HTMLElement)) {
          return;
        }

        if (state.generatedMoveInFlight) {
          event.preventDefault();
          return;
        }

        const card = target.closest(".schedule-board-card[data-draggable='true'][data-schedule-id]");
        if (!card) {
          return;
        }

        const sourceScheduleId = Number.parseInt(card.dataset.scheduleId || "", 10);
        if (!Number.isInteger(sourceScheduleId) || sourceScheduleId <= 0) {
          event.preventDefault();
          return;
        }

        const sourceDay = card.dataset.slotDay || "";
        const sourceStart = card.dataset.slotStart || "";
        const sourceEnd = card.dataset.slotEnd || "";
        if (!sourceDay || !sourceStart || !sourceEnd) {
          event.preventDefault();
          return;
        }

        state.generatedDragState.sourceScheduleId = sourceScheduleId;
        state.generatedDragState.sourceDay = sourceDay;
        state.generatedDragState.sourceStart = sourceStart;
        state.generatedDragState.sourceEnd = sourceEnd;
        state.generatedDragState.sourceSlotKey = createBoardCellKey(sourceDay, sourceStart, sourceEnd);

        card.classList.add("schedule-board-card-dragging");

        if (event.dataTransfer) {
          event.dataTransfer.effectAllowed = "move";
          event.dataTransfer.setData("text/plain", String(sourceScheduleId));
        }
      });

      generatedOutput.addEventListener("dragover", function (event) {
        if (!state.generatedDragState.sourceScheduleId) {
          return;
        }

        const target = event.target;
        if (!(target instanceof HTMLElement)) {
          return;
        }

        const targetCell = target.closest(".schedule-board-cell");
        if (!targetCell) {
          return;
        }

        event.preventDefault();
        if (event.dataTransfer) {
          event.dataTransfer.dropEffect = "move";
        }

        clearGeneratedDropFeedback();

        const targetCard = target.closest(".schedule-board-card[data-schedule-id]");
        const preview = evaluateGeneratedDropCandidate(targetCell, targetCard ? targetCard.dataset.scheduleId : null);

        targetCell.classList.add("schedule-board-cell-drop-hover");
        targetCell.classList.add(preview.valid ? "schedule-board-cell-drop-valid" : "schedule-board-cell-drop-invalid");
      });

      generatedOutput.addEventListener("drop", async function (event) {
        if (!state.generatedDragState.sourceScheduleId) {
          return;
        }

        event.preventDefault();

        const target = event.target;
        if (!(target instanceof HTMLElement)) {
          clearGeneratedDropFeedback();
          resetGeneratedDragState();
          return;
        }

        const targetCell = target.closest(".schedule-board-cell");
        if (!targetCell) {
          clearGeneratedDropFeedback();
          resetGeneratedDragState();
          return;
        }

        const targetCard = target.closest(".schedule-board-card[data-schedule-id]");
        const preview = evaluateGeneratedDropCandidate(targetCell, targetCard ? targetCard.dataset.scheduleId : null);

        clearGeneratedDropFeedback();

        if (!preview.valid) {
          const sourceSelector =
            '.schedule-board-card[data-schedule-id="' + state.generatedDragState.sourceScheduleId + '"]';
          const sourceCard = generatedOutput.querySelector(sourceSelector);
          if (sourceCard) {
            sourceCard.classList.add("schedule-board-card-invalid-shake");
            window.setTimeout(function () {
              sourceCard.classList.remove("schedule-board-card-invalid-shake");
            }, 350);
          }

          if (preview.reason === "same_slot") {
            showAlert("info", "La sesión ya está en esa misma celda.");
          } else {
            showAlert("warning", "Movimiento no válido con las reglas actuales del horario.");
          }

          generatedOutput.querySelectorAll(".schedule-board-card-dragging").forEach(function (card) {
            card.classList.remove("schedule-board-card-dragging");
          });
          resetGeneratedDragState();
          return;
        }

        await applyGeneratedDropChange(preview);

        generatedOutput.querySelectorAll(".schedule-board-card-dragging").forEach(function (card) {
          card.classList.remove("schedule-board-card-dragging");
        });
        resetGeneratedDragState();
      });

      generatedOutput.addEventListener("dragend", function () {
        generatedOutput.querySelectorAll(".schedule-board-card-dragging").forEach(function (card) {
          card.classList.remove("schedule-board-card-dragging");
        });
        clearGeneratedDropFeedback();
        resetGeneratedDragState();
      });

      generatedOutput.addEventListener("click", function (event) {
        const target = event.target;
        if (!(target instanceof HTMLElement)) {
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

    const pdfButton = document.getElementById("generatedWorkspacePdfBtn");
    if (pdfButton) {
      pdfButton.addEventListener("click", function () {
        openGeneratedExport("pdf");
      });
    }

    const csvButton = document.getElementById("generatedWorkspaceCsvBtn");
    if (csvButton) {
      csvButton.addEventListener("click", function () {
        openGeneratedExport("csv");
      });
    }

    const saveButton = document.getElementById("generatedWorkspaceSaveBtn");
    if (saveButton) {
      saveButton.addEventListener("click", handleSaveGenerated);
    }

    const saveModal = document.getElementById("saveGeneratedModal");
    if (saveModal) {
      saveModal.addEventListener("click", function (event) {
        if (event.target === saveModal) {
          closeSaveGeneratedModal();
        }
      });
    }

    const cancelSaveButton = document.getElementById("cancelSaveGeneratedBtn");
    if (cancelSaveButton) {
      cancelSaveButton.addEventListener("click", closeSaveGeneratedModal);
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
      regenerateButton.addEventListener("click", handleRegenerate);
    }
  }

  function bindSavedEvents() {
    const cardsContainer = document.getElementById("savedScheduleCards");
    if (cardsContainer) {
      cardsContainer.addEventListener("click", async function (event) {
        const target = event.target;
        if (!(target instanceof HTMLElement)) {
          return;
        }

        const deleteButton = target.closest("button[data-action='delete'][data-index]");
        if (deleteButton) {
          const deleteIndex = Number.parseInt(deleteButton.dataset.index || "", 10);
          if (Number.isNaN(deleteIndex) || deleteIndex < 0) {
            return;
          }
          deleteSavedTimetable(deleteIndex);
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
          await openSavedWorkspace(index);
        }
      });

      cardsContainer.addEventListener("keydown", async function (event) {
        const target = event.target;
        if (!(target instanceof HTMLElement)) {
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
          await openSavedWorkspace(index);
        }
      });
    }

    [savedFilterIds.courseId, savedFilterIds.teacherId, savedFilterIds.subjectId].forEach(function (id) {
      const select = document.getElementById(id);
      if (!select) {
        return;
      }
      select.addEventListener("change", function () {
        state.savedDetailPage = 1;
        renderSavedWorkspace();
      });
    });

    const savedOutput = document.getElementById("savedWorkspaceOutput");
    if (savedOutput) {
      savedOutput.addEventListener("dragstart", function (event) {
        const target = event.target;
        if (!(target instanceof HTMLElement)) {
          return;
        }

        if (state.savedMoveInFlight) {
          event.preventDefault();
          return;
        }

        const card = target.closest(".schedule-board-card[data-draggable='true'][data-schedule-id]");
        if (!card) {
          return;
        }

        const sourceScheduleId = Number.parseInt(card.dataset.scheduleId || "", 10);
        if (!Number.isInteger(sourceScheduleId) || sourceScheduleId <= 0) {
          event.preventDefault();
          return;
        }

        const sourceDay = card.dataset.slotDay || "";
        const sourceStart = card.dataset.slotStart || "";
        const sourceEnd = card.dataset.slotEnd || "";
        if (!sourceDay || !sourceStart || !sourceEnd) {
          event.preventDefault();
          return;
        }

        state.savedDragState.sourceScheduleId = sourceScheduleId;
        state.savedDragState.sourceDay = sourceDay;
        state.savedDragState.sourceStart = sourceStart;
        state.savedDragState.sourceEnd = sourceEnd;
        state.savedDragState.sourceSlotKey = createBoardCellKey(sourceDay, sourceStart, sourceEnd);

        card.classList.add("schedule-board-card-dragging");

        if (event.dataTransfer) {
          event.dataTransfer.effectAllowed = "move";
          event.dataTransfer.setData("text/plain", String(sourceScheduleId));
        }
      });

      savedOutput.addEventListener("dragover", function (event) {
        if (!state.savedDragState.sourceScheduleId) {
          return;
        }

        const target = event.target;
        if (!(target instanceof HTMLElement)) {
          return;
        }

        const targetCell = target.closest(".schedule-board-cell");
        if (!targetCell) {
          return;
        }

        event.preventDefault();
        if (event.dataTransfer) {
          event.dataTransfer.dropEffect = "move";
        }

        clearSavedDropFeedback();

        const targetCard = target.closest(".schedule-board-card[data-schedule-id]");
        const preview = evaluateSavedDropCandidate(targetCell, targetCard ? targetCard.dataset.scheduleId : null);

        targetCell.classList.add("schedule-board-cell-drop-hover");
        targetCell.classList.add(preview.valid ? "schedule-board-cell-drop-valid" : "schedule-board-cell-drop-invalid");
      });

      savedOutput.addEventListener("drop", async function (event) {
        if (!state.savedDragState.sourceScheduleId) {
          return;
        }

        event.preventDefault();

        const target = event.target;
        if (!(target instanceof HTMLElement)) {
          clearSavedDropFeedback();
          resetSavedDragState();
          return;
        }

        const targetCell = target.closest(".schedule-board-cell");
        if (!targetCell) {
          clearSavedDropFeedback();
          resetSavedDragState();
          return;
        }

        const targetCard = target.closest(".schedule-board-card[data-schedule-id]");
        const preview = evaluateSavedDropCandidate(targetCell, targetCard ? targetCard.dataset.scheduleId : null);

        clearSavedDropFeedback();

        if (!preview.valid) {
          const sourceSelector =
            '.schedule-board-card[data-schedule-id="' + state.savedDragState.sourceScheduleId + '"]';
          const sourceCard = savedOutput.querySelector(sourceSelector);
          if (sourceCard) {
            sourceCard.classList.add("schedule-board-card-invalid-shake");
            window.setTimeout(function () {
              sourceCard.classList.remove("schedule-board-card-invalid-shake");
            }, 350);
          }

          if (preview.reason === "same_slot") {
            showAlert("info", "La sesión ya está en esa misma celda.");
          } else {
            showAlert("warning", "Movimiento no válido con las reglas actuales del horario.");
          }

          savedOutput.querySelectorAll(".schedule-board-card-dragging").forEach(function (card) {
            card.classList.remove("schedule-board-card-dragging");
          });
          resetSavedDragState();
          return;
        }

        await applySavedDropChange(preview);

        savedOutput.querySelectorAll(".schedule-board-card-dragging").forEach(function (card) {
          card.classList.remove("schedule-board-card-dragging");
        });
        resetSavedDragState();
      });

      savedOutput.addEventListener("dragend", function () {
        savedOutput.querySelectorAll(".schedule-board-card-dragging").forEach(function (card) {
          card.classList.remove("schedule-board-card-dragging");
        });
        clearSavedDropFeedback();
        resetSavedDragState();
      });

      savedOutput.addEventListener("click", function (event) {
        const target = event.target;
        if (!(target instanceof HTMLElement)) {
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

    const pdfButton = document.getElementById("savedWorkspacePdfBtn");
    if (pdfButton) {
      pdfButton.addEventListener("click", function () {
        openExportModal({
          source: "saved",
          savedName: state.selectedSavedTimetableName || "",
          format: "pdf",
          lockFormat: true,
        });
      });
    }

    const csvButton = document.getElementById("savedWorkspaceCsvBtn");
    if (csvButton) {
      csvButton.addEventListener("click", function () {
        openExportModal({
          source: "saved",
          savedName: state.selectedSavedTimetableName || "",
          format: "csv",
          lockFormat: true,
        });
      });
    }
  }

  function bindExportEvents() {
    const modal = document.getElementById("exportModal");
    if (!modal) {
      return;
    }

    const cancelButton = document.getElementById("cancelExportBtn");
    if (cancelButton) {
      cancelButton.addEventListener("click", closeExportModal);
    }

    const confirmButton = document.getElementById("confirmExportBtn");
    if (confirmButton) {
      confirmButton.addEventListener("click", handleExportConfirm);
    }

    modal.addEventListener("click", function (event) {
      if (event.target === modal) {
        closeExportModal();
      }
    });

    document.querySelectorAll(".export-entity-card").forEach(function (button) {
      button.addEventListener("click", function () {
        const entityType = button.dataset.exportEntity;
        if (!entityType) {
          return;
        }

        state.exportEntityState[entityType] = !state.exportEntityState[entityType];
        renderExportEntityCards();
      });
    });
  }

  async function init() {
    initScheduleFilterDropdowns();
    bindExportEvents();

    if (schedulesSection) {
      bindGeneratedEvents();
      showGeneratedLanding();
    }

    if (savedSection) {
      bindSavedEvents();
      showSavedPicker();
      state.initialSavedRouteName = String(savedSection.dataset.openSavedName || "").trim();
    }

    await loadCoreData();
    await loadSavedSchedules();

    if (window.orariooAuth && typeof window.orariooAuth.initLucideIcons === "function") {
      window.orariooAuth.initLucideIcons();
    }
  }

  init();
})();
