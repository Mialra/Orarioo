/**
 * Schedule board rendering: produces the HTML for session cards, the timetable grid,
 * and the paginated session detail table.
 * Depends on window.ScheduleUtils being loaded first.
 * Output: window.ScheduleBoard — { mapSessionForBoard, buildBoardRows, renderSessionCard,
 *   renderEmptyCell, createDetailPaginationHtml, renderSessionDetailTable, renderScheduleBoard }
 */
(function () {
  var utils = window.ScheduleUtils;

  var WORK_CENTER_SUBJECT = "Trabajo de Centro";
  var BOARD_DAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"];
  var BOARD_DAY_INDEX = { Lunes: 1, Martes: 2, Miércoles: 3, Jueves: 4, Viernes: 5 };
  var DEFAULT_BOARD_ROWS = [
    ["08:00", "09:00"],
    ["09:00", "10:00"],
    ["10:00", "11:00"],
    ["11:00", "12:00"],
    ["12:00", "13:00"],
    ["13:00", "14:00"],
  ];

  /**
   * Creates an empty cells map keyed by weekday name.
   * Input: none
   * Output: object { Lunes: [], Martes: [], … } for all BOARD_DAYS
   */
  function createEmptyDayCells() {
    var cells = {};
    BOARD_DAYS.forEach(function (dayName) {
      cells[dayName] = [];
    });
    return cells;
  }

  /**
   * Maps a raw API session object to the display-ready board session shape.
   * Input: session - raw schedule session object with start_time, end_time, and entity fields
   *        options - object with optional forceWorkCenterSubjectLabel boolean and
   *                  getSessionSubjectType callback; falls back to utils.getSubjectTypeValue
   * Output: board session object, or null if the session has invalid times or a non-workday
   */
  function mapSessionForBoard(session, options) {
    var start = new Date(session.start_time);
    var end = new Date(session.end_time);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
      return null;
    }

    var weekdayMap = { 1: "Lunes", 2: "Martes", 3: "Miércoles", 4: "Jueves", 5: "Viernes" };
    var dayName = weekdayMap[start.getUTCDay()];
    if (!dayName || BOARD_DAYS.indexOf(dayName) < 0) {
      return null;
    }

    var safeOptions = options || {};
    var getSubjectType = safeOptions.getSessionSubjectType || utils.getSubjectTypeValue;
    var forceWorkCenterLabel = safeOptions.forceWorkCenterSubjectLabel === true;
    var displaySubjectName =
      forceWorkCenterLabel && getSubjectType(session) === "TC" ? WORK_CENTER_SUBJECT : session.subject_name || "-";

    return {
      id: session.id,
      teacherId: session.teacher,
      groupId: session.group,
      classroomId: session.classroom,
      subjectId: session.subject,
      subjectName: displaySubjectName,
      teacherName: session.teacher_name || "-",
      groupName: session.group_name || "-",
      classroomName: session.classroom_name || "-",
      dayName: dayName,
      start: start,
      end: end,
      startHm: utils.toUtcHM(start),
      endHm: utils.toUtcHM(end),
      groupStage: session.group_stage || null,
      isTc: session.is_tc === true,
    };
  }

  /**
   * Computes all slot windows (session + recess) for one stage config, mirroring
   * the Python build_windows_from_stage_config logic in slots.py.
   * Input: cfg - stage config object { start_time, end_time, breaks?, break_start?, break_end? }
   * Output: array of { start: "HH:MM", end: "HH:MM", isRecess: bool }
   */
  function buildWindowsFromStageConfig(cfg) {
    function toMin(hhmm) {
      var p = (hhmm || "00:00").split(":");
      return parseInt(p[0], 10) * 60 + parseInt(p[1], 10);
    }
    function fromMin(m) {
      var h = Math.floor(m / 60);
      var min = m % 60;
      return (h < 10 ? "0" : "") + h + ":" + (min < 10 ? "0" : "") + min;
    }

    var startMin = toMin(cfg.start_time);
    var endMin = toMin(cfg.end_time);
    var durMin = 60;

    var rawBreaks = Array.isArray(cfg.breaks) ? cfg.breaks : [];
    if (!rawBreaks.length && cfg.break_start && cfg.break_end) {
      rawBreaks = [{ start: cfg.break_start, end: cfg.break_end }];
    }
    var parsedBreaks = rawBreaks
      .filter(function (b) { return b.start && b.end; })
      .map(function (b) { return { start: toMin(b.start), end: toMin(b.end) }; })
      .sort(function (a, b) { return a.start - b.start; });

    var result = [];
    var segStart = startMin;
    parsedBreaks.forEach(function (b) {
      var cursor = segStart;
      while (cursor < b.start) {
        var slotEnd = Math.min(cursor + durMin, b.start);
        result.push({ start: fromMin(cursor), end: fromMin(slotEnd), isRecess: false });
        cursor = slotEnd;
      }
      result.push({ start: fromMin(b.start), end: fromMin(b.end), isRecess: true });
      segStart = b.end;
    });
    var cursor = segStart;
    while (cursor < endMin) {
      var slotEnd = Math.min(cursor + durMin, endMin);
      result.push({ start: fromMin(cursor), end: fromMin(slotEnd), isRecess: false });
      cursor = slotEnd;
    }
    return result;
  }

  /**
   * Builds canonical session-slot rows from all stages (recess rows excluded).
   * Used only in TC/teacher view to show the full possible assignment grid.
   */
  function buildCanonicalRowsFromConfig(scheduleConfig) {
    var byKey = new Map();
    Object.values(scheduleConfig).forEach(function (stageCfg) {
      var windows = buildWindowsFromStageConfig(stageCfg);
      windows.forEach(function (w) {
        if (w.isRecess) { return; }
        var key = w.start + "-" + w.end;
        if (!byKey.has(key)) {
          byKey.set(key, { start: w.start, end: w.end, isRecess: false, cells: createEmptyDayCells() });
        }
      });
    });
    return Array.from(byKey.values()).sort(utils.compareRowsByTime);
  }

  /**
   * Groups mapped sessions into board rows.
   * tcMode=false (group/classroom/subject view): rows built from actual session times;
   *   recess rows injected from config only where sessions exist on both sides and
   *   the break doesn't overlap an existing session — original behaviour restored.
   * tcMode=true  (teacher TC view): full canonical session grid as base, blocked-day
   *   detection, and phantom-row filtering.
   */
  function buildBoardRows(mappedSessions, scheduleConfig, tcMode) {
    var byRange;
    var hasConfig = !!(scheduleConfig && Object.keys(scheduleConfig).length > 0);

    if (!tcMode) {
      // ── Non-TC view: original behaviour from 5d1fa7a ─────────────────────
      byRange = new Map();
      mappedSessions.forEach(function (session) {
        var key = session.startHm + "-" + session.endHm;
        if (!byRange.has(key)) {
          byRange.set(key, { start: session.startHm, end: session.endHm, isRecess: false, cells: createEmptyDayCells() });
        }
        byRange.get(key).cells[session.dayName].push(session);
      });

      if (hasConfig) {
        var sessionRanges = [];
        byRange.forEach(function (row) {
          if (!row.isRecess) { sessionRanges.push({ start: row.start, end: row.end }); }
        });
        Object.values(scheduleConfig).forEach(function (stageCfg) {
          var breakList = Array.isArray(stageCfg.breaks) ? stageCfg.breaks : [];
          if (!breakList.length && stageCfg.break_start && stageCfg.break_end) {
            breakList = [{ start: stageCfg.break_start, end: stageCfg.break_end }];
          }
          breakList.forEach(function (b) {
            if (!b.start || !b.end) { return; }
            var overlapsSession = sessionRanges.some(function (r) { return r.start < b.end && b.start < r.end; });
            var hasSessionBefore = sessionRanges.some(function (r) { return r.end <= b.start; });
            if (overlapsSession || !hasSessionBefore) { return; }
            var key = b.start + "-" + b.end;
            if (!byRange.has(key)) {
              byRange.set(key, { start: b.start, end: b.end, isRecess: true, cells: createEmptyDayCells() });
            }
          });
        });
      }

      var rows = Array.from(byRange.values()).sort(utils.compareRowsByTime);
      if (rows.length) { return rows; }
      return DEFAULT_BOARD_ROWS.map(function (range) {
        return { start: range[0], end: range[1], isRecess: false, cells: createEmptyDayCells() };
      });
    }

    // ── TC teacher view ───────────────────────────────────────────────────────
    byRange = new Map();

    if (hasConfig) {
      buildCanonicalRowsFromConfig(scheduleConfig, false).forEach(function (row) {
        byRange.set(row.start + "-" + row.end, {
          start: row.start, end: row.end, isRecess: false, cells: createEmptyDayCells(),
        });
      });
    } else {
      DEFAULT_BOARD_ROWS.forEach(function (r) {
        byRange.set(r[0] + "-" + r[1], { start: r[0], end: r[1], isRecess: false, cells: createEmptyDayCells() });
      });
    }

    mappedSessions.forEach(function (session) {
      var key = session.startHm + "-" + session.endHm;
      if (!byRange.has(key)) {
        byRange.set(key, { start: session.startHm, end: session.endHm, isRecess: false, cells: createEmptyDayCells() });
      }
      if (!byRange.get(key).isRecess) {
        byRange.get(key).cells[session.dayName].push(session);
      }
    });

    var rows = Array.from(byRange.values()).sort(utils.compareRowsByTime);

    rows.forEach(function (row) {
      row.blockedDays = {};
      BOARD_DAYS.forEach(function (dayName) {
        if ((row.cells[dayName] || []).length === 0) {
          var blocked = mappedSessions.some(function (s) {
            return s.dayName === dayName && s.startHm < row.end && s.endHm > row.start;
          });
          if (blocked) { row.blockedDays[dayName] = true; }
        }
      });
    });

    rows = rows.filter(function (row) {
      var hasAnySessions = BOARD_DAYS.some(function (d) { return (row.cells[d] || []).length > 0; });
      if (hasAnySessions) { return true; }
      var allBlocked = BOARD_DAYS.every(function (d) { return row.blockedDays[d]; });
      return !allBlocked;
    });

    if (rows.length) { return rows; }

    return DEFAULT_BOARD_ROWS.map(function (range) {
      return { start: range[0], end: range[1], isRecess: false, cells: createEmptyDayCells() };
    });
  }

  /**
   * Renders the HTML article element for a single session card.
   * Input: session - mapped board session object; isTc flag triggers TC-specific styling/delete button
   *        options - object with enableDragDrop boolean and teacherWorkloadsByName map
   * Output: HTML string for a schedule-board-card article
   */
  function renderSessionCard(session, options) {
    var safeOptions = options || {};

    if (session.isTc) {
      return (
        '<article class="schedule-board-card schedule-board-card--tc"' +
        ' data-tc-session-id="' + session.id + '">' +
        '<div class="schedule-board-card-tc-row">' +
        '<h4 class="schedule-board-card-subject mb-0">Guardia TC</h4>' +
        '<button class="schedule-board-card-tc-delete" data-tc-delete-id="' + session.id + '" title="Eliminar guardia TC" aria-label="Eliminar guardia TC">' +
        '<i data-lucide="trash-2" class="schedule-board-card-tc-delete-icon" aria-hidden="true"></i>' +
        '</button>' +
        '</div>' +
        '<p class="schedule-board-card-line">' + session.teacherName + "</p>" +
        "</article>"
      );
    }

    var canDrag = safeOptions.enableDragDrop === true;
    var dragAttrs = canDrag ? ' draggable="true" data-draggable="true"' : "";
    var dragClass = canDrag ? " schedule-board-card-draggable" : "";

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

  /**
   * Returns the placeholder HTML for an empty board cell.
   * Input: options - optional object; if options.enableTcCreate is true, renders an add-TC button
   * Output: HTML string
   */
  function renderEmptyCell(options) {
    var safeOptions = options || {};
    if (safeOptions.enableTcCreate && !safeOptions.tcBlocked) {
      return (
        '<div class="schedule-board-slot-empty schedule-board-slot-empty--tc-add">' +
        '<button class="schedule-board-slot-tc-add" data-add-tc="true" title="Añadir guardia TC" aria-label="Añadir guardia TC">' +
        '<i data-lucide="shield-plus" class="schedule-board-slot-tc-add-icon" aria-hidden="true"></i>' +
        '</button>' +
        '</div>'
      );
    }
    return '<div class="schedule-board-slot-empty" aria-hidden="true"></div>';
  }

  /**
   * Builds Bootstrap pagination HTML for the session detail table.
   * Input: currentPage - 1-based current page number
   *        totalPages  - total number of pages
   * Output: HTML string with nav/ul, or empty string when totalPages <= 1
   */
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

    var windowSize = 5;
    var start = Math.max(1, currentPage - 2);
    var end = Math.min(totalPages, start + windowSize - 1);
    start = Math.max(1, end - windowSize + 1);

    var html = "";
    html += pageButton("Anterior", currentPage - 1, currentPage <= 1, false);

    if (start > 1) {
      html += pageButton("1", 1, false, currentPage === 1);
      if (start > 2) {
        html += ellipsis();
      }
    }

    for (var page = start; page <= end; page += 1) {
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

  /**
   * Renders the paginated session detail table section.
   * Input: mappedSessions - array of board session objects
   *        options - { title, page, pageSize }
   * Output: { html: string, currentPage: number, totalItems: number }
   */
  function renderSessionDetailTable(mappedSessions, options) {
    var safeOptions = options || {};
    var pageSize = Math.max(1, safeOptions.pageSize || 20);
    var totalItems = mappedSessions.length;
    var totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
    var requestedPage = Math.max(1, safeOptions.page || 1);
    var currentPage = Math.min(requestedPage, totalPages);

    var startIndex = (currentPage - 1) * pageSize;
    var endIndex = startIndex + pageSize;
    var pagedItems = mappedSessions.slice(startIndex, endIndex);

    var rowsHtml = pagedItems.length
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

    var firstItem = totalItems ? startIndex + 1 : 0;
    var lastItem = totalItems ? Math.min(endIndex, totalItems) : 0;

    var html =
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

    return { html: html, currentPage: currentPage, totalItems: totalItems };
  }

  /**
   * Renders the full timetable board and session detail table into the given output element.
   * Input: sessions - array of raw API session objects
   *        outputId - ID string of the container element to render into
   *        options - { forceWorkCenterSubjectLabel, getSessionSubjectType, detailTitle,
   *                    detailPage, detailPageSize, enableDragDrop, teacherWorkloadsByName }
   * Output: { currentPage, totalItems } from the rendered detail table, or undefined on missing element
   */
  function renderScheduleBoard(sessions, outputId, options) {
    var output = document.getElementById(outputId);
    if (!output) {
      return;
    }

    var safeOptions = options || {};

    var mappedSessions = (sessions || [])
      .map(function (session) {
        return mapSessionForBoard(session, safeOptions);
      })
      .filter(Boolean)
      .sort(function (left, right) {
        return left.start - right.start;
      });

    var rows = buildBoardRows(
      mappedSessions,
      safeOptions.scheduleConfig || null,
      safeOptions.enableTcCreate === true
    );

    var rowHtml = rows
      .map(function (row) {
        if (row.isRecess) {
          return (
            '<tr class="schedule-board-row-recess">' +
            '<td class="schedule-board-time"><strong>' +
            row.start +
            "</strong><span>" +
            row.end +
            "</span></td>" +
            '<td colspan="' +
            BOARD_DAYS.length +
            '" class="schedule-board-recess-cell">Recreo</td>' +
            "</tr>"
          );
        }

        var dayCells = BOARD_DAYS.map(function (dayName) {
          var entries = row.cells[dayName] || [];
          var cellKey = utils.createBoardCellKey(dayName, row.start, row.end);
          var isBlocked = row.blockedDays && row.blockedDays[dayName];
          var emptyCellOptions = isBlocked
            ? Object.assign({}, safeOptions, { tcBlocked: true })
            : safeOptions;
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
              : renderEmptyCell(emptyCellOptions)) +
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

    var detail = renderSessionDetailTable(mappedSessions, {
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

    return { currentPage: detail.currentPage, totalItems: detail.totalItems };
  }

  window.ScheduleBoard = {
    mapSessionForBoard: mapSessionForBoard,
    buildBoardRows: buildBoardRows,
    renderSessionCard: renderSessionCard,
    renderEmptyCell: renderEmptyCell,
    createDetailPaginationHtml: createDetailPaginationHtml,
    renderSessionDetailTable: renderSessionDetailTable,
    renderScheduleBoard: renderScheduleBoard,
  };
})();
