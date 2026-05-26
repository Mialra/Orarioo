/**
 * Schedule workspace factory: creates a stateful controller for a single timetable workspace
 * (generated or saved). Eliminates the duplicate generated/saved function pairs from schedules.js.
 * Depends on window.ScheduleUtils and window.ScheduleBoard being loaded first.
 * Output: window.ScheduleWorkspace — { createScheduleWorkspace }
 */
(function () {
  var utils = window.ScheduleUtils;
  var board = window.ScheduleBoard;

  var BOARD_DAY_INDEX = { Lunes: 1, Martes: 2, "Miércoles": 3, Jueves: 4, Viernes: 5 };
  var DAY_NAME_TO_CODE = { Lunes: "MON", Martes: "TUE", "Miércoles": "WED", Jueves: "THU", Viernes: "FRI" };
  var CELL_UPDATE_ANIMATION_MS = 420;
  var MOVE_API_PATH = "/schedules/move/";

  var DROP_REASON_MESSAGES = {
    teacher_conflict: "El profesor ya tiene otra sesión en ese hueco horario.",
    group_conflict: "El curso ya tiene otra sesión en ese hueco horario.",
    classroom_conflict: "El aula ya está ocupada en ese hueco horario.",
    teacher_unavailable: "El profesor no está disponible en ese hueco horario.",
    subject_unavailable: "La asignatura no está disponible en ese hueco horario.",
    duration_mismatch: "No se puede mover la sesión: el hueco destino tiene distinta duración. Comprueba que ambas sesiones tengan la misma duración.",
    stage_window_violation: "El hueco horario no está permitido para la etapa de esta sesión.",
  };

  /**
   * Creates a workspace controller that manages drag-drop state and board cell updates
   * for a single timetable workspace (generated or saved).
   *
   * Input: config - {
   *   outputId          {string}    DOM id of the board container
   *   filterIds         {object}    { courseId, teacherId, classroomId, subjectId }
   *   detailTitle       {string}    title for the session detail table
   *   getDetailPage     {function}  () => number
   *   setDetailPage     {function}  (n: number) => void
   *   getDetailPageSize {function}  () => number
   *   getMoveInFlight   {function}  () => boolean
   *   setMoveInFlight   {function}  (v: boolean) => void
   *   getDragState      {function}  () => dragState object
   *   resetDragState    {function}  () => void
   *   getSessions       {function}  () => rawSession[]
   *   upsertSessions    {function}  (updated: rawSession[]) => void
   *   getTeacherWorkloads {function} () => workloadsByName object
   *   setTeacherWorkloads {function} (w: object) => void
   *   onDropComplete    {function}  () => void  extra side effects after a successful drop
   *   showAlert         {function}  (type: string, msg: string) => void
   *   apiJson           {function}  (path, method, body) => Promise<{ok, data}>
   *   getFilteredSessions {function} (sessions, filterIds) => session[]
   *   populateFilters   {function}  (sessions, filterIds, opts) => void
   *   getSessionSubjectType {function} (session) => string  used for TC-subject label resolution
   * }
   * Output: controller object — { clearDropFeedback, buildMappedSessions, buildMappedSessionsAll,
   *   refreshDetailBlock, updateBoardCells, evaluateDropCandidate, applyDropChange, bindDragDropEvents }
   */
  function createScheduleWorkspace(config) {
    /**
     * Removes all drop-state CSS classes from board cells inside this workspace's output element.
     * Input: none
     * Output: void
     */
    function clearDropFeedback() {
      var output = document.getElementById(config.outputId);
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

    /**
     * Maps the filtered session list to board session objects sorted by start time.
     * Input: none (reads config.getSessions, config.filterIds, config.getFilteredSessions)
     * Output: sorted board session array for display
     */
    function buildMappedSessions() {
      var sessions = config.getSessions();
      var selectedSubject = (function () {
        var el = document.getElementById(config.filterIds.subjectId);
        return el ? el.value : "";
      })();
      var forceWorkCenterLabel = utils.isWorkCenterSubjectValue(selectedSubject);
      var filtered = config.getFilteredSessions(sessions, config.filterIds);

      return filtered
        .map(function (session) {
          return board.mapSessionForBoard(session, {
            forceWorkCenterSubjectLabel: forceWorkCenterLabel,
            getSessionSubjectType: config.getSessionSubjectType,
          });
        })
        .filter(Boolean)
        .sort(function (left, right) {
          return left.start - right.start;
        });
    }

    /**
     * Maps all sessions (no filter) to board session objects sorted by start time.
     * Input: none (reads config.getSessions)
     * Output: sorted board session array used for conflict detection
     */
    function buildMappedSessionsAll() {
      return config
        .getSessions()
        .map(function (session) {
          return board.mapSessionForBoard(session, {
            getSessionSubjectType: config.getSessionSubjectType,
          });
        })
        .filter(Boolean)
        .sort(function (left, right) {
          return left.start - right.start;
        });
    }

    /**
     * Replaces the detail-block section inside the output element with a re-rendered table.
     * Input: mappedSessions - array of board session objects
     * Output: void; updates detailPage state via config.setDetailPage
     */
    function refreshDetailBlock(mappedSessions) {
      var output = document.getElementById(config.outputId);
      if (!output) {
        return;
      }
      var detailBlock = output.querySelector(".schedule-detail-block");
      if (!detailBlock) {
        return;
      }
      var detail = board.renderSessionDetailTable(mappedSessions, {
        title: config.detailTitle,
        page: config.getDetailPage(),
        pageSize: config.getDetailPageSize(),
      });
      config.setDetailPage(detail && detail.currentPage ? detail.currentPage : 1);
      detailBlock.outerHTML = detail.html;
    }

    /**
     * Re-renders the board cells for the given slot keys and triggers a brief highlight animation.
     * Input: slotKeys - array of board-key strings to refresh
     *        mappedSessions - current filtered board session array
     * Output: void
     */
    function updateBoardCells(slotKeys, mappedSessions) {
      var output = document.getElementById(config.outputId);
      if (!output) {
        return;
      }

      var uniqueSlotKeys = Array.from(
        new Set(
          (slotKeys || []).filter(function (key) {
            return !!key;
          }),
        ),
      );
      if (!uniqueSlotKeys.length) {
        return;
      }

      var byCellKey = new Map();
      (mappedSessions || []).forEach(function (session) {
        var key = utils.createBoardCellKey(session.dayName, session.startHm, session.endHm);
        if (!byCellKey.has(key)) {
          byCellKey.set(key, []);
        }
        byCellKey.get(key).push(session);
      });

      uniqueSlotKeys.forEach(function (slotKey) {
        var cell = output.querySelector('.schedule-board-cell[data-board-key="' + slotKey + '"]');
        if (!cell) {
          return;
        }
        var entries = byCellKey.get(slotKey) || [];
        cell.innerHTML = entries.length
          ? entries
              .map(function (entry) {
                return board.renderSessionCard(entry, {
                  enableDragDrop: true,
                  teacherWorkloadsByName: config.getTeacherWorkloads(),
                });
              })
              .join("")
          : board.renderEmptyCell();

        cell.classList.remove("schedule-board-cell-updated");
        void cell.offsetWidth;
        cell.classList.add("schedule-board-cell-updated");
      });

      window.setTimeout(function () {
        uniqueSlotKeys.forEach(function (slotKey) {
          var cell = output.querySelector('.schedule-board-cell[data-board-key="' + slotKey + '"]');
          if (cell) {
            cell.classList.remove("schedule-board-cell-updated");
          }
        });
      }, CELL_UPDATE_ANIMATION_MS);
    }

    /**
     * Validates a drag-drop operation and returns a candidate descriptor.
     * Input: targetCell - the HTMLElement board cell being dropped on
     *        forcedTargetScheduleId - optional schedule ID string for the target card
     * Output: candidate object with { valid, mode, reason, sourceScheduleId, targetScheduleId,
     *         sourceSlotKey, targetSlotKey, sourceDay, sourceStart, sourceEnd,
     *         targetDay, targetStart, targetEnd }
     */
    function evaluateDropCandidate(targetCell, forcedTargetScheduleId) {
      var dragState = config.getDragState();
      var sourceScheduleId = Number.parseInt(dragState.sourceScheduleId, 10);
      if (!Number.isInteger(sourceScheduleId) || sourceScheduleId <= 0) {
        return { valid: false, reason: "no_source" };
      }

      if (!(targetCell instanceof HTMLElement)) {
        return { valid: false, reason: "no_target_cell" };
      }

      var targetDay = targetCell.dataset.boardDay || "";
      var targetStart = targetCell.dataset.boardStart || "";
      var targetEnd = targetCell.dataset.boardEnd || "";
      if (!targetDay || !targetStart || !targetEnd || !BOARD_DAY_INDEX[targetDay]) {
        return { valid: false, reason: "invalid_target_slot" };
      }

      var targetSlotKey = utils.createBoardCellKey(targetDay, targetStart, targetEnd);
      var targetScheduleId = Number.parseInt(forcedTargetScheduleId || "", 10);
      if (!Number.isInteger(targetScheduleId) || targetScheduleId <= 0) {
        targetScheduleId = null;
        var fallbackCard = targetCell.querySelector(".schedule-board-card[data-schedule-id]");
        if (fallbackCard) {
          var parsedFallback = Number.parseInt(fallbackCard.dataset.scheduleId || "", 10);
          if (Number.isInteger(parsedFallback) && parsedFallback > 0 && parsedFallback !== sourceScheduleId) {
            targetScheduleId = parsedFallback;
          }
        }
      }

      var sameSlot = dragState.sourceSlotKey === targetSlotKey;
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

      var mode = targetScheduleId ? "swap" : "move";

      // For moves onto empty cells, reject immediately if the target row has a
      // different duration than the session being dragged.
      if (mode === "move") {
        var srcDurMin = utils.parseHmToMinutes(dragState.sourceEnd) - utils.parseHmToMinutes(dragState.sourceStart);
        var tgtDurMin = utils.parseHmToMinutes(targetEnd) - utils.parseHmToMinutes(targetStart);
        if (srcDurMin !== tgtDurMin) {
          return { valid: false, reason: "duration_mismatch" };
        }
      }

      var mappedAll = buildMappedSessionsAll();
      var mappedById = new Map(
        mappedAll.map(function (item) {
          return [String(item.id), item];
        }),
      );

      var sourceMapped = mappedById.get(String(sourceScheduleId));
      if (!sourceMapped) {
        return { valid: false, reason: "missing_source_session" };
      }

      var candidateById = new Map();
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
        var targetMapped = mappedById.get(String(targetScheduleId));
        if (!targetMapped) {
          return { valid: false, reason: "missing_target_session" };
        }
        var sourceDuration =
          utils.parseHmToMinutes(dragState.sourceEnd) - utils.parseHmToMinutes(dragState.sourceStart);
        var targetDuration =
          utils.parseHmToMinutes(targetMapped.endHm) - utils.parseHmToMinutes(targetMapped.startHm);
        if (sourceDuration !== targetDuration) {
          return { valid: false, reason: "duration_mismatch" };
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

      var changedIds = Array.from(candidateById.keys());
      for (var changedIndex = 0; changedIndex < changedIds.length; changedIndex += 1) {
        var changedId = changedIds[changedIndex];
        var candidate = candidateById.get(changedId);
        for (var sessionIndex = 0; sessionIndex < mappedAll.length; sessionIndex += 1) {
          var other = mappedAll[sessionIndex];
          var otherId = String(other.id);
          if (otherId === changedId) {
            continue;
          }
          var otherCandidate = candidateById.get(otherId) || other;
          if (candidate.dayName !== otherCandidate.dayName) {
            continue;
          }
          if (!utils.hmRangesOverlap(candidate.startHm, candidate.endHm, otherCandidate.startHm, otherCandidate.endHm)) {
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

      var unavailability = config.getUnavailability ? config.getUnavailability() : null;
      if (unavailability) {
        var targetPrefKey = DAY_NAME_TO_CODE[targetDay] ? DAY_NAME_TO_CODE[targetDay] + "_" + targetStart : null;
        var sourcePrefKey =
          DAY_NAME_TO_CODE[dragState.sourceDay] ? DAY_NAME_TO_CODE[dragState.sourceDay] + "_" + dragState.sourceStart : null;

        if (targetPrefKey) {
          var srcTeacherId = String(sourceMapped.teacherId || "");
          var srcSubjectId = String(sourceMapped.subjectId || "");
          var teacherSlots = (unavailability.teachers && unavailability.teachers[srcTeacherId]) || [];
          var subjectSlots = (unavailability.subjects && unavailability.subjects[srcSubjectId]) || [];
          if (teacherSlots.indexOf(targetPrefKey) !== -1) {
            return { valid: false, reason: "teacher_unavailable" };
          }
          if (subjectSlots.indexOf(targetPrefKey) !== -1) {
            return { valid: false, reason: "subject_unavailable" };
          }
        }

        if (mode === "swap" && sourcePrefKey) {
          var targetMappedForUnavail = mappedById.get(String(targetScheduleId));
          if (targetMappedForUnavail) {
            var tgtTeacherId = String(targetMappedForUnavail.teacherId || "");
            var tgtSubjectId = String(targetMappedForUnavail.subjectId || "");
            var tgtTeacherSlots = (unavailability.teachers && unavailability.teachers[tgtTeacherId]) || [];
            var tgtSubjectSlots = (unavailability.subjects && unavailability.subjects[tgtSubjectId]) || [];
            if (tgtTeacherSlots.indexOf(sourcePrefKey) !== -1) {
              return { valid: false, reason: "teacher_unavailable" };
            }
            if (tgtSubjectSlots.indexOf(sourcePrefKey) !== -1) {
              return { valid: false, reason: "subject_unavailable" };
            }
          }
        }
      }

      var stageWindows = config.getStageWindows ? config.getStageWindows() : null;
      if (stageWindows) {
        var srcStage = sourceMapped.groupStage;
        var srcAllowed = stageWindows[srcStage] || [];
        var srcSlotOk = srcAllowed.some(function (r) {
          return r[0] === targetStart && r[1] === targetEnd;
        });
        if (!srcSlotOk) {
          return { valid: false, reason: "stage_window_violation" };
        }
        if (mode === "swap") {
          var tgtStage = targetMapped.groupStage;
          var tgtAllowed = stageWindows[tgtStage] || [];
          var tgtSlotOk = tgtAllowed.some(function (r) {
            return r[0] === dragState.sourceStart && r[1] === dragState.sourceEnd;
          });
          if (!tgtSlotOk) {
            return { valid: false, reason: "stage_window_violation" };
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

    /**
     * Sends the validated move/swap to the backend, updates state, and refreshes affected cells.
     * Input: candidate - result object from evaluateDropCandidate with valid === true
     * Output: Promise<void>; shows an alert and updates the board as side effects
     */
    async function applyDropChange(candidate) {
      if (!candidate || !candidate.valid) {
        return;
      }
      if (config.getMoveInFlight()) {
        return;
      }

      config.setMoveInFlight(true);
      var result = await config.apiJson(MOVE_API_PATH, "POST", {
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
      config.setMoveInFlight(false);

      if (!result.ok) {
        var errMsg =
          (result.data && (result.data.detail || result.data.message)) || "No se pudo aplicar el cambio manual.";
        config.showAlert("error", errMsg);
        return;
      }

      if (result.data && result.data.no_changes) {
        config.showAlert("info", "No se aplicaron cambios.");
        return;
      }

      config.upsertSessions(result.data && result.data.affected_schedules);

      if (result.data && Array.isArray(result.data.teacher_workloads)) {
        config.setTeacherWorkloads(utils.buildTeacherWorkloadsByNameFromApi(result.data.teacher_workloads));
      } else {
        config.setTeacherWorkloads(utils.buildTeacherWorkloadsByNameFromSessions(config.getSessions()));
      }

      config.populateFilters(config.getSessions(), config.filterIds, {
        teacherWorkloadsByName: config.getTeacherWorkloads(),
      });

      config.onDropComplete();

      var affectedKeys = [candidate.sourceSlotKey, candidate.targetSlotKey];
      if (result.data && Array.isArray(result.data.affected_slots)) {
        result.data.affected_slots.forEach(function (slot) {
          if (!slot || !slot.day || !slot.start || !slot.end) {
            return;
          }
          affectedKeys.push(utils.createBoardCellKey(slot.day, slot.start, slot.end));
        });
      }

      var mappedVisible = buildMappedSessions();
      updateBoardCells(affectedKeys, mappedVisible);
      refreshDetailBlock(mappedVisible);

      var successMessage =
        candidate.mode === "swap" ? "Intercambio aplicado correctamente." : "Sesión movida correctamente.";
      config.showAlert("success", successMessage);
    }

    /**
     * Attaches dragstart, dragover, drop, and dragend listeners to the given output element.
     * Input: outputEl - HTMLElement of the workspace board container
     * Output: void; side effects: listeners registered on outputEl
     */
    function bindDragDropEvents(outputEl) {
      if (!outputEl) {
        return;
      }

      // Auto-scroll the page while dragging near the viewport edges.
      var _autoScrollRAF = null;
      var _autoScrollClientY = 0;

      function _startAutoScroll() {
        if (_autoScrollRAF !== null) { return; }
        function step() {
          var y = _autoScrollClientY;
          var threshold = 80;
          var speed = 12;
          var vh = window.innerHeight;
          if (y < threshold && y > 0) {
            window.scrollBy(0, -speed * (1 - y / threshold));
          } else if (y > vh - threshold && y < vh) {
            window.scrollBy(0, speed * (1 - (vh - y) / threshold));
          }
          _autoScrollRAF = requestAnimationFrame(step);
        }
        _autoScrollRAF = requestAnimationFrame(step);
      }

      function _stopAutoScroll() {
        if (_autoScrollRAF !== null) {
          cancelAnimationFrame(_autoScrollRAF);
          _autoScrollRAF = null;
        }
      }

      outputEl.addEventListener("dragstart", function (event) {
        var target = event.target;
        if (!(target instanceof HTMLElement)) {
          return;
        }
        if (config.getMoveInFlight()) {
          event.preventDefault();
          return;
        }
        var card = target.closest(".schedule-board-card[data-draggable='true'][data-schedule-id]");
        if (!card) {
          return;
        }
        var sourceScheduleId = Number.parseInt(card.dataset.scheduleId || "", 10);
        if (!Number.isInteger(sourceScheduleId) || sourceScheduleId <= 0) {
          event.preventDefault();
          return;
        }
        var sourceDay = card.dataset.slotDay || "";
        var sourceStart = card.dataset.slotStart || "";
        var sourceEnd = card.dataset.slotEnd || "";
        if (!sourceDay || !sourceStart || !sourceEnd) {
          event.preventDefault();
          return;
        }

        var dragState = config.getDragState();
        dragState.sourceScheduleId = sourceScheduleId;
        dragState.sourceDay = sourceDay;
        dragState.sourceStart = sourceStart;
        dragState.sourceEnd = sourceEnd;
        dragState.sourceSlotKey = utils.createBoardCellKey(sourceDay, sourceStart, sourceEnd);

        card.classList.add("schedule-board-card-dragging");
        outputEl.querySelectorAll(".schedule-board-cell").forEach(function (cell) {
          var preview = evaluateDropCandidate(cell, null);
          if (preview.valid) {
            cell.classList.add("schedule-board-cell-drop-swappable");
          }
        });
        if (event.dataTransfer) {
          event.dataTransfer.effectAllowed = "move";
          event.dataTransfer.setData("text/plain", String(sourceScheduleId));
        }
        _startAutoScroll();
      });

      outputEl.addEventListener("dragover", function (event) {
        _autoScrollClientY = event.clientY;
        if (!config.getDragState().sourceScheduleId) {
          return;
        }
        var target = event.target;
        if (!(target instanceof HTMLElement)) {
          return;
        }
        var targetCell = target.closest(".schedule-board-cell");
        if (!targetCell) {
          return;
        }
        event.preventDefault();
        if (event.dataTransfer) {
          event.dataTransfer.dropEffect = "move";
        }
        clearDropFeedback();
        var targetCard = target.closest(".schedule-board-card[data-schedule-id]");
        var preview = evaluateDropCandidate(targetCell, targetCard ? targetCard.dataset.scheduleId : null);
        targetCell.classList.add("schedule-board-cell-drop-hover");
        targetCell.classList.add(preview.valid ? "schedule-board-cell-drop-valid" : "schedule-board-cell-drop-invalid");
      });

      outputEl.addEventListener("drop", async function (event) {
        if (!config.getDragState().sourceScheduleId) {
          return;
        }
        event.preventDefault();
        var target = event.target;
        if (!(target instanceof HTMLElement)) {
          clearDropFeedback();
          config.resetDragState();
          return;
        }
        var targetCell = target.closest(".schedule-board-cell");
        if (!targetCell) {
          clearDropFeedback();
          config.resetDragState();
          return;
        }
        var targetCard = target.closest(".schedule-board-card[data-schedule-id]");
        var preview = evaluateDropCandidate(targetCell, targetCard ? targetCard.dataset.scheduleId : null);
        clearDropFeedback();

        if (!preview.valid) {
          var sourceSelector = '.schedule-board-card[data-schedule-id="' + config.getDragState().sourceScheduleId + '"]';
          var sourceCard = outputEl.querySelector(sourceSelector);
          if (sourceCard) {
            sourceCard.classList.add("schedule-board-card-invalid-shake");
            window.setTimeout(function () {
              sourceCard.classList.remove("schedule-board-card-invalid-shake");
            }, 350);
          }
          if (preview.reason === "same_slot") {
            config.showAlert("info", "La sesión ya está en esa misma celda.");
          } else {
            config.showAlert(
              "warning",
              DROP_REASON_MESSAGES[preview.reason] || "Movimiento no válido con las reglas actuales del horario.",
            );
          }
          _stopAutoScroll();
          outputEl.querySelectorAll(".schedule-board-card-dragging").forEach(function (card) {
            card.classList.remove("schedule-board-card-dragging");
          });
          config.resetDragState();
          return;
        }

        await applyDropChange(preview);
        _stopAutoScroll();
        outputEl.querySelectorAll(".schedule-board-card-dragging").forEach(function (card) {
          card.classList.remove("schedule-board-card-dragging");
        });
        config.resetDragState();
      });

      outputEl.addEventListener("dragend", function () {
        _stopAutoScroll();
        outputEl.querySelectorAll(".schedule-board-card-dragging").forEach(function (card) {
          card.classList.remove("schedule-board-card-dragging");
        });
        clearDropFeedback();
        outputEl.querySelectorAll(".schedule-board-cell-drop-swappable").forEach(function (cell) {
          cell.classList.remove("schedule-board-cell-drop-swappable");
        });
        config.resetDragState();
      });
    }

    return {
      clearDropFeedback: clearDropFeedback,
      buildMappedSessions: buildMappedSessions,
      buildMappedSessionsAll: buildMappedSessionsAll,
      refreshDetailBlock: refreshDetailBlock,
      updateBoardCells: updateBoardCells,
      evaluateDropCandidate: evaluateDropCandidate,
      applyDropChange: applyDropChange,
      bindDragDropEvents: bindDragDropEvents,
    };
  }

  window.ScheduleWorkspace = {
    createScheduleWorkspace: createScheduleWorkspace,
  };
})();
