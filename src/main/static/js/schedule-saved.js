/**
 * Saved timetable management: card rendering, loading, opening, deleting, and state caching.
 * Depends on window.ScheduleUtils.
 * Output: window.ScheduleSaved — { createSavedManager }
 */
(function () {
  var SAVED_SUMMARY_API_PATH = "/schedules/saved-summary/";
  var SAVED_DETAIL_API_PATH = "/schedules/saved-detail/";

  /**
   * Creates a saved-timetable manager bound to the provided state slice and callbacks.
   * Input: config - { state, apiJson, showAlert, extractApiErrorMessage, listFromPayload,
   *                   onShowSavedWorkspace, onShowSavedPicker, onRenderSavedWorkspace,
   *                   onPopulateFilters, savedFilterIds }
   * Output: object with methods for loading, rendering, and managing saved timetables
   */
  function createSavedManager(config) {
    var state = config.state;
    var apiJson = config.apiJson;
    var showAlert = config.showAlert;
    var extractApiErrorMessage = config.extractApiErrorMessage;
    var listFromPayload = config.listFromPayload;
    var utils = window.ScheduleUtils;

    /**
     * Groups a flat list of saved-timetable summary items by name and sorts by updated_at.
     * Input: items - array of saved schedule summary objects with name and updated_at
     * Output: sorted array of { name, updated_at, sessions, sessionsLoaded } group objects
     */
    function buildSavedTimetableGroups(items) {
      var byName = new Map();
      (items || []).forEach(function (item) {
        var name = String(item.name || "").trim();
        if (!name) {
          return;
        }
        if (!byName.has(name)) {
          byName.set(name, { name: name, updated_at: item.updated_at || "", sessions: [], sessionsLoaded: false });
        }
        var group = byName.get(name);
        if (item.updated_at && utils.toDateMillis(item.updated_at) > utils.toDateMillis(group.updated_at)) {
          group.updated_at = item.updated_at;
        }
      });
      return Array.from(byName.values()).sort(function (left, right) {
        var updatedDiff = utils.toDateMillis(right.updated_at) - utils.toDateMillis(left.updated_at);
        if (updatedDiff !== 0) {
          return updatedDiff;
        }
        return String(left.name || "").localeCompare(String(right.name || ""), "es");
      });
    }

    /**
     * Renders the saved timetable card list into the #savedScheduleCards container.
     * Input: none
     * Output: void; replaces the container's inner HTML and refreshes Lucide icons
     */
    function renderSavedCards() {
      var container = document.getElementById("savedScheduleCards");
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
            '<div class="saved-card-heading">' +
            '<h3 class="saved-card-title">' +
            group.name +
            "</h3>" +
            '<p class="saved-card-date">Última actualización el ' +
            utils.toIsoDateDisplay(group.updated_at) +
            "</p>" +
            "</div>" +
            '<div class="saved-card-actions">' +
            '<button type="button" class="btn btn-link text-primary p-0 saved-card-rename" data-action="rename" data-index="' +
            index +
            '" title="Renombrar horario" aria-label="Renombrar horario ' +
            group.name +
            '">' +
            '<i data-lucide="pencil" class="saved-card-rename-icon" aria-hidden="true"></i></button>' +
            '<button type="button" class="btn btn-link text-danger p-0 saved-card-delete" data-action="delete" data-index="' +
            index +
            '" title="Eliminar horario" aria-label="Eliminar horario ' +
            group.name +
            '">' +
            '<i data-lucide="trash-2" class="saved-card-delete-icon" aria-hidden="true"></i></button>' +
            "</div>" +
            "</div>" +
            "</article></div>"
          );
        })
        .join("");
      if (window.orariooAuth && typeof window.orariooAuth.initLucideIcons === "function") {
        window.orariooAuth.initLucideIcons();
      }
    }

    /**
     * Fetches sessions and teacher workloads for a saved timetable by name.
     * Input: timetableName - string name of the timetable to load
     * Output: Promise<{sessions, teacherWorkloadsByName}> or null on error
     */
    async function fetchSavedSessionsByName(timetableName) {
      var name = String(timetableName || "").trim();
      if (!name) {
        return null;
      }
      var result = await apiJson(SAVED_DETAIL_API_PATH + "?timetable_name=" + encodeURIComponent(name));
      if (!result.ok) {
        showAlert("error", extractApiErrorMessage(result.data, "No se pudo cargar el horario guardado."));
        return null;
      }
      return {
        sessions: listFromPayload(result.data),
        teacherWorkloadsByName: utils.buildTeacherWorkloadsByNameFromApi(
          result.data && result.data.teacher_workloads
        ),
        unavailability: (result.data && result.data.unavailability) || null,
        stageWindows: (result.data && result.data.stage_windows) || null,
      };
    }

    /**
     * Syncs state.selectedSavedTimetableIndex to match state.selectedSavedTimetableName.
     * Input: none
     * Output: the matched timetable group object, or null when not found
     */
    function syncSelectedSavedIndexByName() {
      var selectedName = String(state.selectedSavedTimetableName || "").trim();
      if (!selectedName) {
        state.selectedSavedTimetableIndex = null;
        return null;
      }
      var normalized = utils.normalizeForCompare(selectedName);
      var index = state.savedTimetableGroups.findIndex(function (group) {
        return utils.normalizeForCompare(group.name) === normalized;
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

    /**
     * Returns the currently selected saved timetable group from state.
     * Input: none
     * Output: timetable group object or null
     */
    function getSelectedSavedGroup() {
      if (state.selectedSavedTimetableName) {
        var byName = syncSelectedSavedIndexByName();
        if (byName) {
          return byName;
        }
      }
      if (state.selectedSavedTimetableIndex === null) {
        return null;
      }
      return state.savedTimetableGroups[state.selectedSavedTimetableIndex] || null;
    }

    /**
     * Opens the saved workspace for a timetable group by index, loading sessions if needed.
     * Input: index - zero-based index into state.savedTimetableGroups
     * Output: Promise<boolean> — true on success, false on error
     */
    async function openSavedWorkspace(index) {
      var selected = state.savedTimetableGroups[index];
      if (!selected) {
        showAlert("error", "Horario guardado no encontrado.");
        return false;
      }
      state.selectedSavedTimetableIndex = index;
      state.selectedSavedTimetableName = selected.name;
      state.savedDetailPage = 1;
      config.onShowSavedWorkspace();
      if (!selected.sessionsLoaded) {
        var output = document.getElementById("savedWorkspaceOutput");
        if (output) {
          output.style.display = "block";
          output.innerHTML =
            '<article class="saved-card-placeholder"><p class="text-secondary mb-0">Cargando sesiones...</p></article>';
        }
        var savedDetail = await fetchSavedSessionsByName(selected.name);
        if (savedDetail === null) {
          config.onShowSavedPicker();
          return false;
        }
        var sessions = savedDetail.sessions;
        selected.sessions = sessions;
        selected.unavailability = savedDetail.unavailability || null;
        selected.stageWindows = savedDetail.stageWindows || null;
        selected.sessionsLoaded = true;
        state.savedTeacherWorkloadsByName =
          savedDetail.teacherWorkloadsByName && Object.keys(savedDetail.teacherWorkloadsByName).length
            ? savedDetail.teacherWorkloadsByName
            : utils.buildTeacherWorkloadsByNameFromSessions(sessions);
        var latestUpdatedAt = sessions.reduce(function (latest, session) {
          if (!session || !session.updated_at) {
            return latest;
          }
          return utils.toDateMillis(session.updated_at) > utils.toDateMillis(latest)
            ? session.updated_at
            : latest;
        }, selected.updated_at || "");
        if (latestUpdatedAt) {
          selected.updated_at = latestUpdatedAt;
        }
        renderSavedCards();
      }
      if (!state.savedTeacherWorkloadsByName || !Object.keys(state.savedTeacherWorkloadsByName).length) {
        state.savedTeacherWorkloadsByName = utils.buildTeacherWorkloadsByNameFromSessions(selected.sessions);
      }
      config.onPopulateFilters(selected.sessions, config.savedFilterIds, {
        teacherWorkloadsByName: state.savedTeacherWorkloadsByName,
      });
      config.onRenderSavedWorkspace();
      return true;
    }

    /**
     * Opens the saved workspace for a timetable group by name.
     * Input: timetableName - string name to look up in state.savedTimetableGroups
     * Output: Promise<boolean> — true on success, false when not found
     */
    async function openSavedWorkspaceByName(timetableName) {
      var normalized = utils.normalizeForCompare(timetableName);
      if (!normalized) {
        return false;
      }
      var index = state.savedTimetableGroups.findIndex(function (group) {
        return utils.normalizeForCompare(group.name) === normalized;
      });
      if (index < 0) {
        return false;
      }
      return openSavedWorkspace(index);
    }

    function openRenameModal(currentName) {
      return new Promise(function (resolve) {
        var modal = document.getElementById("renameSavedTimetableModal");
        var input = document.getElementById("renameSavedTimetableInput");
        var nameError = document.getElementById("renameSavedTimetableNameError");
        var alertEl = document.getElementById("renameSavedTimetableAlert");
        var confirmBtn = document.getElementById("confirmRenameSavedTimetableBtn");
        if (!modal || !confirmBtn) {
          var newName = window.prompt("Nuevo nombre para el horario:", currentName);
          resolve(newName && newName.trim() ? newName.trim() : null);
          return;
        }
        if (input) { input.value = currentName; input.classList.remove("is-invalid"); }
        if (nameError) { nameError.textContent = ""; }
        if (alertEl) { alertEl.classList.add("d-none"); alertEl.textContent = ""; }

        var resolved = false;
        var instance = window.bootstrap && window.bootstrap.Modal
          ? window.bootstrap.Modal.getOrCreateInstance(modal)
          : null;

        function closeModal() {
          if (instance) { instance.hide(); }
          else { modal.classList.remove("show"); modal.style.display = "none"; document.body.classList.remove("modal-open"); }
        }

        function onConfirm() {
          if (resolved) { return; }
          var val = (input ? input.value : "").trim();
          if (!val) {
            if (input) { input.classList.add("is-invalid"); }
            if (nameError) { nameError.textContent = "El nombre es obligatorio."; }
            return;
          }
          resolved = true;
          closeModal();
          resolve(val);
        }

        function onDismiss() {
          if (resolved) { return; }
          resolved = true;
          resolve(null);
        }

        confirmBtn.addEventListener("click", onConfirm, { once: true });
        modal.addEventListener("hidden.bs.modal", onDismiss, { once: true });

        if (instance) { instance.show(); }
        else { modal.classList.add("show"); modal.style.display = "block"; document.body.classList.add("modal-open"); }
        setTimeout(function () { if (input) { input.select(); } }, 300);
      });
    }

    async function renameSavedTimetable(index) {
      try {
        var selected = state.savedTimetableGroups[index];
        if (!selected) {
          showAlert("error", "Horario guardado no encontrado.");
          return;
        }
        var newName = await openRenameModal(selected.name);
        if (!newName) { return; }
        if (utils.normalizeForCompare(newName) === utils.normalizeForCompare(selected.name)) { return; }

        var result = await apiJson("/schedules/rename-saved-timetable/", "POST", {
          old_name: selected.name,
          new_name: newName,
        });

        if (!result.ok) {
          var fieldError = result.data && result.data.new_name;
          if (fieldError) {
            var input = document.getElementById("renameSavedTimetableInput");
            var nameError = document.getElementById("renameSavedTimetableNameError");
            if (input) { input.classList.add("is-invalid"); }
            if (nameError) { nameError.textContent = fieldError; }
            var modal = document.getElementById("renameSavedTimetableModal");
            var instance = window.bootstrap && window.bootstrap.Modal
              ? window.bootstrap.Modal.getOrCreateInstance(modal) : null;
            if (instance) { instance.show(); }
            return;
          }
          showAlert("error", extractApiErrorMessage(result.data, "No se pudo renombrar el horario guardado."));
          return;
        }

        var oldName = selected.name;
        selected.name = newName;
        if (utils.normalizeForCompare(state.selectedSavedTimetableName) === utils.normalizeForCompare(oldName)) {
          state.selectedSavedTimetableName = newName;
        }
        renderSavedCards();
        showAlert("success", "Horario renombrado correctamente.");
      } catch (_error) {
        showAlert("error", "No se pudo renombrar el horario guardado.");
      }
    }

    function openDeleteConfirmModal(name) {
      return new Promise(function (resolve) {
        var modal = document.getElementById("deleteSavedTimetableModal");
        var nameEl = document.getElementById("deleteSavedTimetableName");
        var confirmBtn = document.getElementById("confirmDeleteSavedTimetableBtn");
        if (!modal || !confirmBtn) {
          resolve(window.confirm('¿Eliminar el horario guardado "' + name + '"?'));
          return;
        }
        if (nameEl) {
          nameEl.textContent = name;
        }
        var resolved = false;
        var instance = window.bootstrap && window.bootstrap.Modal
          ? window.bootstrap.Modal.getOrCreateInstance(modal)
          : null;

        function closeModal() {
          if (instance) {
            instance.hide();
          } else {
            modal.classList.remove("show");
            modal.style.display = "none";
            document.body.classList.remove("modal-open");
          }
        }

        function onConfirm() {
          if (resolved) { return; }
          resolved = true;
          closeModal();
          resolve(true);
        }

        function onDismiss() {
          if (resolved) { return; }
          resolved = true;
          resolve(false);
        }

        confirmBtn.addEventListener("click", onConfirm, { once: true });
        modal.addEventListener("hidden.bs.modal", onDismiss, { once: true });

        if (instance) {
          instance.show();
        } else {
          modal.classList.add("show");
          modal.style.display = "block";
          document.body.classList.add("modal-open");
        }
      });
    }

    /**
     * Prompts for confirmation and deletes a saved timetable via the API.
     * Input: index - zero-based index into state.savedTimetableGroups
     * Output: Promise<void>; shows alert and reloads saved list on success
     */
    async function deleteSavedTimetable(index) {
      try {
        var selected = state.savedTimetableGroups[index];
        if (!selected) {
          showAlert("error", "Horario guardado no encontrado.");
          return;
        }
        if (!(await openDeleteConfirmModal(selected.name))) {
          return;
        }
        var result = await apiJson("/schedules/delete-saved-timetable/", "POST", {
          timetable_name: selected.name,
        });
        if (!result.ok) {
          showAlert("error", extractApiErrorMessage(result.data, "No se pudo eliminar el horario guardado."));
          return;
        }
        if (utils.normalizeForCompare(state.selectedSavedTimetableName) === utils.normalizeForCompare(selected.name)) {
          state.selectedSavedTimetableIndex = null;
          state.selectedSavedTimetableName = null;
          config.onShowSavedPicker();
        }
        showAlert("success", "Horario eliminado correctamente.");
        await loadSavedSchedules();
      } catch (_error) {
        showAlert("error", "No se pudo eliminar el horario guardado.");
      }
    }

    /**
     * Loads the saved-timetable summary list and renders cards; navigates to initial timetable if set.
     * Input: none
     * Output: Promise<boolean>; updates state.savedTimetableGroups and renders picker or workspace
     */
    async function loadSavedSchedules() {
      var result = await apiJson(SAVED_SUMMARY_API_PATH);
      if (!result.ok) {
        state.savedSummaryLoaded = false;
        state.savedTimetableGroups = [];
        state.selectedSavedTimetableIndex = null;
        state.selectedSavedTimetableName = null;
        renderSavedCards();
        showAlert("error", extractApiErrorMessage(result.data, "No se pudieron cargar los horarios guardados."));
        return false;
      }
      var selectedName = state.selectedSavedTimetableName;
      var routeRequestedName = state.initialSavedRouteName;
      if (!selectedName && routeRequestedName) {
        selectedName = routeRequestedName;
      }
      state.savedSummaryLoaded = true;
      state.savedTimetableGroups = buildSavedTimetableGroups(listFromPayload(result.data));
      renderSavedCards();
      if (selectedName) {
        state.selectedSavedTimetableName = selectedName;
        syncSelectedSavedIndexByName();
      }
      if (routeRequestedName) {
        state.initialSavedRouteName = "";
        if (!(await openSavedWorkspaceByName(routeRequestedName))) {
          config.onShowSavedPicker();
          showAlert("warning", 'No se encontro el horario guardado "' + routeRequestedName + '".');
        }
        return true;
      }
      var savedSectionEl = document.getElementById("savedSection");
      var savedWorkspaceSectionEl = document.getElementById("savedWorkspaceSection");
      if (savedSectionEl && savedWorkspaceSectionEl && !savedWorkspaceSectionEl.classList.contains("d-none")) {
        var currentName = state.selectedSavedTimetableName;
        if (!currentName) {
          config.onShowSavedPicker();
          return true;
        }
        if (!(await openSavedWorkspaceByName(currentName))) {
          config.onShowSavedPicker();
        }
      }
      return true;
    }

    /**
     * Ensures the saved schedule summary is loaded, using a cached promise to deduplicate calls.
     * Input: forceRefresh - boolean; if true, reloads even if already cached
     * Output: Promise<boolean>
     */
    async function ensureSavedSchedulesLoaded(forceRefresh) {
      var shouldRefresh = Boolean(forceRefresh);
      if (!shouldRefresh && state.savedSummaryLoaded) {
        return true;
      }
      if (!shouldRefresh && state.savedSummaryPromise) {
        return state.savedSummaryPromise;
      }
      state.savedSummaryPromise = loadSavedSchedules()
        .catch(function () { return false; })
        .finally(function () { state.savedSummaryPromise = null; });
      return state.savedSummaryPromise;
    }

    /**
     * Upserts a timetable group into state from a freshly saved timetable name and sessions.
     * Input: timetableName - string; sessions - array of session objects
     * Output: void; mutates state.savedTimetableGroups
     */
    function rememberSavedTimetableSummary(timetableName, sessions) {
      var name = String(timetableName || "").trim();
      if (!name) {
        return;
      }
      var nextSessions = Array.isArray(sessions) ? sessions.slice() : [];
      var nextUpdatedAt =
        nextSessions.reduce(function (latest, session) {
          if (!session || !session.updated_at) {
            return latest;
          }
          return utils.toDateMillis(session.updated_at) > utils.toDateMillis(latest)
            ? session.updated_at
            : latest;
        }, "") || new Date().toISOString();
      var normalizedName = utils.normalizeForCompare(name);
      var existingIndex = state.savedTimetableGroups.findIndex(function (group) {
        return utils.normalizeForCompare(group.name) === normalizedName;
      });
      var nextGroup = {
        name: name,
        updated_at: nextUpdatedAt,
        sessions: nextSessions,
        sessionsLoaded: nextSessions.length > 0,
      };
      if (existingIndex >= 0) {
        state.savedTimetableGroups[existingIndex] = nextGroup;
      } else {
        state.savedTimetableGroups.push(nextGroup);
      }
      state.savedSummaryLoaded = true;
      state.savedTimetableGroups.sort(function (left, right) {
        var updatedDiff = utils.toDateMillis(right.updated_at) - utils.toDateMillis(left.updated_at);
        if (updatedDiff !== 0) {
          return updatedDiff;
        }
        return String(left.name || "").localeCompare(String(right.name || ""), "es");
      });
    }

    /**
     * Returns true when a saved timetable with the given name already exists in state.
     * Input: timetableName - string
     * Output: boolean
     */
    function hasSavedTimetableNameCollision(timetableName) {
      var normalized = utils.normalizeForCompare(timetableName);
      return state.savedTimetableGroups.some(function (group) {
        return utils.normalizeForCompare(group.name) === normalized;
      });
    }

    /**
     * Sorts savedTimetableGroups, re-syncs the selected index, and re-renders cards.
     * Input: none
     * Output: void; called after a drag-drop completes in the saved workspace
     */
    function onAfterDropComplete() {
      state.savedTimetableGroups.sort(function (left, right) {
        var updatedDiff = utils.toDateMillis(right.updated_at) - utils.toDateMillis(left.updated_at);
        if (updatedDiff !== 0) {
          return updatedDiff;
        }
        return String(left.name || "").localeCompare(String(right.name || ""), "es");
      });
      syncSelectedSavedIndexByName();
      renderSavedCards();
    }

    return {
      renderSavedCards: renderSavedCards,
      syncSelectedSavedIndexByName: syncSelectedSavedIndexByName,
      getSelectedSavedGroup: getSelectedSavedGroup,
      openSavedWorkspace: openSavedWorkspace,
      deleteSavedTimetable: deleteSavedTimetable,
      renameSavedTimetable: renameSavedTimetable,
      ensureSavedSchedulesLoaded: ensureSavedSchedulesLoaded,
      rememberSavedTimetableSummary: rememberSavedTimetableSummary,
      hasSavedTimetableNameCollision: hasSavedTimetableNameCollision,
      onAfterDropComplete: onAfterDropComplete,
    };
  }

  window.ScheduleSaved = {
    createSavedManager: createSavedManager,
  };
})();
