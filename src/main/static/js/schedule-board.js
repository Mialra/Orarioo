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
    };
  }

  /**
   * Groups mapped sessions into board rows keyed by time range; falls back to DEFAULT_BOARD_ROWS.
   * Injects recess rows from scheduleConfig when provided.
   * Input: mappedSessions - array of board session objects from mapSessionForBoard
   *        scheduleConfig - optional schedule_config dict from /api/schedule-config/
   * Output: sorted array of { start, end, isRecess, cells } row objects
   */
  function buildBoardRows(mappedSessions, scheduleConfig) {
    var byRange = new Map();

    mappedSessions.forEach(function (session) {
      var rangeKey = session.startHm + "-" + session.endHm;
      if (!byRange.has(rangeKey)) {
        byRange.set(rangeKey, {
          start: session.startHm,
          end: session.endHm,
          isRecess: false,
          cells: createEmptyDayCells(),
        });
      }
      byRange.get(rangeKey).cells[session.dayName].push(session);
    });

    if (scheduleConfig) {
      var sessionRanges = [];
      byRange.forEach(function (row) {
        if (!row.isRecess) {
          sessionRanges.push({ start: row.start, end: row.end });
        }
      });

      Object.values(scheduleConfig).forEach(function (stageCfg) {
        var breakList = Array.isArray(stageCfg.breaks) ? stageCfg.breaks : [];
        if (!breakList.length && stageCfg.break_start && stageCfg.break_end) {
          breakList = [{ start: stageCfg.break_start, end: stageCfg.break_end }];
        }
        breakList.forEach(function (b) {
          if (!b.start || !b.end) {
            return;
          }
          var overlapsSession = sessionRanges.some(function (r) {
            return r.start < b.end && b.start < r.end;
          });
          var hasSessionBefore = sessionRanges.some(function (r) {
            return r.end <= b.start;
          });
          var hasSessionAfter = sessionRanges.some(function (r) {
            return r.start >= b.end;
          });
          if (overlapsSession || !hasSessionBefore || !hasSessionAfter) {
            return;
          }
          var key = b.start + "-" + b.end;
          if (!byRange.has(key)) {
            byRange.set(key, {
              start: b.start,
              end: b.end,
              isRecess: true,
              cells: createEmptyDayCells(),
            });
          }
        });
      });
    }

    var rows = Array.from(byRange.values()).sort(utils.compareRowsByTime);
    if (rows.length) {
      return rows;
    }

    return DEFAULT_BOARD_ROWS.map(function (range) {
      return { start: range[0], end: range[1], isRecess: false, cells: createEmptyDayCells() };
    });
  }

  /**
   * Renders the HTML article element for a single session card.
   * Input: session - mapped board session object
   *        options - object with enableDragDrop boolean and teacherWorkloadsByName map
   * Output: HTML string for a schedule-board-card article
   */
  function renderSessionCard(session, options) {
    var safeOptions = options || {};
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
   * Input: none
   * Output: HTML string
   */
  function renderEmptyCell() {
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

    var rows = buildBoardRows(mappedSessions, safeOptions.scheduleConfig || null);

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
