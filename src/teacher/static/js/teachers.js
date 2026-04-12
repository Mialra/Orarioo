(function () {
  const admin = window.AdminBase || {};
  const dom = admin.dom;

  const formElement = document.getElementById("admin-teacher-form");
  if (!formElement || !admin.createEntityManager || !dom) {
    return;
  }

  const elements = {
    addButton: document.getElementById("admin-add-teacher-btn"),
    alertBox: document.getElementById("admin-teachers-alert"),
    listContainer: document.getElementById("admin-teachers-list"),
    paginationContainer: document.getElementById("admin-teachers-pagination"),
    emptyMessageNode: document.getElementById("admin-teachers-empty-message"),
    formModal: document.getElementById("admin-teacher-modal"),
    formTitle: document.getElementById("admin-teacher-modal-title"),
    modeInput: document.getElementById("admin-teacher-mode"),
    teacherIdInput: document.getElementById("admin-teacher-id"),
    nameInput: document.getElementById("admin-teacher-name"),
    surnamesInput: document.getElementById("admin-teacher-surnames"),
    maxWeeklyHoursInput: document.getElementById("admin-teacher-max-weekly-hours"),
    workingHoursInput: document.getElementById("admin-teacher-working-hours"),
    timePreferencesInput: document.getElementById("admin-teacher-time-preferences"),
    preferenceBrushInput:
      document.getElementById("admin-teacher-preference-brush") || document.getElementById("teacherPreferenceBrush"),
    preferenceClearButton:
      document.getElementById("admin-teacher-preference-clear-btn") ||
      document.getElementById("teacherPreferenceClearBtn"),
    preferencesGridContainer:
      document.getElementById("admin-teacher-preferences-grid") || document.getElementById("teacherPreferencesGrid"),
    submitButton: document.getElementById("admin-teacher-submit-btn"),
    submitText: document.getElementById("admin-teacher-submit-text"),
    submitSpinner: document.getElementById("admin-teacher-submit-spinner"),
    cancelButton: document.getElementById("admin-teacher-cancel-btn"),
    deleteModal: document.getElementById("admin-teacher-delete-modal"),
    deleteName: document.getElementById("admin-teacher-delete-name"),
    deleteConfirmButton: document.getElementById("admin-teacher-delete-confirm-btn"),
    deleteText: document.getElementById("admin-teacher-delete-text"),
    deleteSpinner: document.getElementById("admin-teacher-delete-spinner"),
    nameError: document.getElementById("admin-teacher-name-error"),
    surnamesError: document.getElementById("admin-teacher-surnames-error"),
    maxWeeklyHoursError: document.getElementById("admin-teacher-max-weekly-hours-error"),
    workingHoursError: document.getElementById("admin-teacher-working-hours-error"),
    timePreferencesError: document.getElementById("admin-teacher-time-preferences-error"),
  };

  const PREFERENCE_STATES = ["AVAILABLE", "PREFER_YES", "PREFER_NO", "UNAVAILABLE"];
  const DAYS = ["MON", "TUE", "WED", "THU", "FRI"];
  const HOURS = [
    "08:00",
    "08:30",
    "09:00",
    "09:30",
    "10:00",
    "10:30",
    "11:00",
    "11:30",
    "12:00",
    "12:30",
    "13:00",
    "13:30",
    "14:00",
    "14:30",
  ];
  const dayLabels = {
    MON: "Lunes",
    TUE: "Martes",
    WED: "Miércoles",
    THU: "Jueves",
    FRI: "Viernes",
  };
  const preferenceStateBySlot = {};

  function resolveTeacherName(teacher) {
    return teacher.name || "Profesor";
  }

  function slotKey(day, hour) {
    return day + "_" + hour;
  }

  function getBrushState() {
    const value = elements.preferenceBrushInput ? elements.preferenceBrushInput.value : "AVAILABLE";
    return PREFERENCE_STATES.indexOf(value) >= 0 ? value : "AVAILABLE";
  }

  function applyStateToCell(cell, state) {
    if (!cell) {
      return;
    }
    PREFERENCE_STATES.forEach(function (candidate) {
      cell.classList.remove("state-" + candidate);
      cell.classList.remove("pref-state-" + candidate);
    });
    cell.classList.add("state-" + state);
    cell.classList.add("pref-state-" + state);
    cell.dataset.state = state;
  }

  function syncTimePreferencesInput() {
    const payload = {};
    Object.keys(preferenceStateBySlot).forEach(function (slot) {
      const state = preferenceStateBySlot[slot];
      if (state !== "AVAILABLE") {
        payload[slot] = state;
      }
    });
    elements.timePreferencesInput.value = JSON.stringify(payload);
  }

  function setSlotState(slot, state) {
    preferenceStateBySlot[slot] = state;
    const cell = elements.preferencesGridContainer
      ? elements.preferencesGridContainer.querySelector('[data-slot="' + slot + '"]')
      : null;
    applyStateToCell(cell, state);
    syncTimePreferencesInput();
  }

  function resetPreferencesGrid(preferences) {
    DAYS.forEach(function (day) {
      HOURS.forEach(function (hour) {
        const slot = slotKey(day, hour);
        const nextState =
          preferences && PREFERENCE_STATES.indexOf(preferences[slot]) >= 0 ? preferences[slot] : "AVAILABLE";
        preferenceStateBySlot[slot] = nextState;
        const cell = elements.preferencesGridContainer
          ? elements.preferencesGridContainer.querySelector('[data-slot="' + slot + '"]')
          : null;
        applyStateToCell(cell, nextState);
      });
    });
    syncTimePreferencesInput();
  }

  function paintSlot(slot) {
    setSlotState(slot, getBrushState());
  }

  function renderPreferencesGrid() {
    if (!elements.preferencesGridContainer) {
      return;
    }

    const headCells = DAYS.map(function (day) {
      return '<div class="pref-grid-header">' + dayLabels[day] + "</div>";
    }).join("");

    const bodyCells = HOURS.map(function (hour) {
      const rowCells = DAYS.map(function (day) {
        const slot = slotKey(day, hour);
        return (
          '<button type="button" class="subject-pref-cell pref-cell state-AVAILABLE pref-state-AVAILABLE" data-slot="' +
          slot +
          '" title="' +
          day +
          " " +
          hour +
          '"></button>'
        );
      }).join("");

      return '<div class="pref-hour">' + hour + "</div>" + rowCells;
    }).join("");

    elements.preferencesGridContainer.innerHTML =
      '<div class="pref-grid">' +
      '<div class="pref-grid-header pref-hour">Hora</div>' +
      headCells +
      bodyCells +
      "</div>";

    elements.preferencesGridContainer.addEventListener("click", function (event) {
      const cell = event.target.closest("[data-slot]");
      if (!cell) {
        return;
      }
      paintSlot(cell.dataset.slot);
    });

    resetPreferencesGrid({});
  }

  function createActionButton(className, title, icon) {
    return dom.createElement("button", {
      className: className,
      attrs: {
        type: "button",
        title: title,
        "aria-label": title,
      },
      children: [dom.createLucideIcon(icon)],
    });
  }

  function renderTeacherItem(teacher) {
    return dom.createElement("div", {
      className: "col",
      children: [
        dom.createElement("article", {
          className: "card border-0 shadow-sm admin-card admin-teacher-card",
          dataset: {
            teacherId: String(teacher.id),
          },
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
                          text: resolveTeacherName(teacher),
                        }),
                        dom.createElement("div", {
                          className: "admin-card-meta",
                          children: [
                            dom.createElement("span", {
                              className: "admin-pill variant-blue",
                              text: teacher.max_weekly_hours + " h máximo",
                            }),
                          ],
                        }),
                      ],
                    }),
                    dom.createElement("div", {
                      className: "admin-actions",
                      children: [
                        createActionButton(
                          "btn btn-link text-primary p-0 admin-action-btn admin-action-btn--edit admin-teacher-edit-btn",
                          "Editar profesor",
                          "pencil",
                        ),
                        createActionButton(
                          "btn btn-link text-danger p-0 admin-action-btn admin-action-btn--delete admin-teacher-delete-btn",
                          "Eliminar profesor",
                          "trash-2",
                        ),
                      ],
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

  function parsePreferences(rawValue) {
    if (rawValue && typeof rawValue === "object") {
      return rawValue;
    }
    if (!rawValue || !String(rawValue).trim()) {
      return {};
    }
    try {
      return JSON.parse(String(rawValue));
    } catch (error) {
      return {};
    }
  }

  renderPreferencesGrid();

  if (elements.preferenceClearButton) {
    elements.preferenceClearButton.addEventListener("click", function () {
      resetPreferencesGrid({});
    });
  }

  admin.createEntityManager({
    endpoint: "/api/teachers/",
    getDetailEndpoint: function (id) {
      return "/api/teachers/" + id + "/";
    },
    getItemId: function (item) {
      return item.id;
    },
    getItemName: function (item) {
      return resolveTeacherName(item);
    },
    parseList: function (data) {
      if (Array.isArray(data)) {
        return data;
      }
      return data && Array.isArray(data.results) ? data.results : [];
    },
    renderItem: renderTeacherItem,
    addButton: elements.addButton,
    alertElement: elements.alertBox,
    messages: {
      loadError: "No se pudieron cargar los profesores.",
      loadItemError: "No se pudo cargar el profesor.",
      validationError: "Revisa los campos marcados en rojo.",
      saveError: "No se pudo guardar el profesor.",
      deleteError: "No se pudo eliminar el profesor.",
      created: "Profesor creado correctamente.",
      updated: "Profesor actualizado correctamente.",
      deleted: "Profesor eliminado correctamente.",
    },
    list: {
      container: elements.listContainer,
      paginationContainer: elements.paginationContainer,
      pageSize: 9,
      loadingMessage: "Cargando profesores...",
      emptyIcon: "graduation-cap",
      emptyTitle: "No hay profesores",
      emptyMessage: elements.emptyMessageNode
        ? elements.emptyMessageNode.textContent.trim()
        : "No hay profesores registrados.",
      rowSelector: ".admin-teacher-card",
      rowIdDataset: "teacherId",
      editSelector: ".admin-teacher-edit-btn",
      deleteSelector: ".admin-teacher-delete-btn",
    },
    form: {
      formElement: formElement,
      modalElement: elements.formModal,
      modeInput: elements.modeInput,
      titleElement: elements.formTitle,
      submitButton: elements.submitButton,
      submitTextElement: elements.submitText,
      submitSpinner: elements.submitSpinner,
      cancelButton: elements.cancelButton,
      focusInput: elements.nameInput,
      labels: {
        createTitle: "Añadir profesor",
        editTitle: "Editar profesor",
        createSubmit: "Crear",
        editSubmit: "Guardar",
      },
      messages: {
        saving: "Guardando...",
      },
      fields: [
        {
          name: "name",
          input: elements.nameInput,
          feedback: elements.nameError,
          rules: [
            {
              validator: function () {
                if (!elements.nameInput.value.trim()) {
                  return window.OrariooErrorHandler.translateEntry({ code: "REQUIRED_FIELD" });
                }
                if (elements.nameInput.value.length > window.ValidationConstants.STRING_MAX_LENGTH) {
                  return "Este campo no puede tener más de " + window.ValidationConstants.STRING_MAX_LENGTH + " caracteres.";
                }
                return "";
              },
            },
          ],
        },
        {
          name: "surnames",
          input: elements.surnamesInput,
          feedback: elements.surnamesError,
          required: false,
          rules: [
            {
              validator: function () {
                if (elements.surnamesInput && elements.surnamesInput.value && elements.surnamesInput.value.length > window.ValidationConstants.STRING_MAX_LENGTH) {
                  return "Este campo no puede tener más de " + window.ValidationConstants.STRING_MAX_LENGTH + " caracteres.";
                }
                return "";
              },
            },
          ],
        },
        {
          name: "max_weekly_hours",
          input: elements.maxWeeklyHoursInput,
          feedback: elements.maxWeeklyHoursError,
          rules: [
            {
              validator: function () {
                const raw = elements.maxWeeklyHoursInput.value.trim();
                if (!raw) {
                  return window.OrariooErrorHandler.translateEntry({ code: "REQUIRED_FIELD" });
                }
                if (!window.OrariooValidators.rules.positiveInteger(raw)) {
                  return window.OrariooErrorHandler.translateEntry({ code: "INVALID_INTEGER" });
                }
                const hours = Number(raw);
                if (hours >= 168) {
                  return window.OrariooErrorHandler.translateEntry({ code: "WEEKLY_HOURS_EXCEEDS_LIMIT" });
                }
                return "";
              },
            },
          ],
        },
        {
          name: "working_hours",
          input: elements.workingHoursInput,
          feedback: elements.workingHoursError,
          required: false,
        },
        {
          name: "time_preferences",
          input: elements.timePreferencesInput,
          feedback: elements.timePreferencesError,
          validator: function () {
            return "";
          },
        },
      ],
      clearValidationOnInput: [
        { input: elements.nameInput, feedback: elements.nameError, event: "input" },
        { input: elements.maxWeeklyHoursInput, feedback: elements.maxWeeklyHoursError, event: "input" },
        { input: elements.workingHoursInput, feedback: elements.workingHoursError, event: "change" },
        { input: elements.timePreferencesInput, feedback: elements.timePreferencesError, event: "input" },
      ],
      resetValues: function () {
        elements.teacherIdInput.value = "";
        elements.nameInput.value = "";
        if (elements.surnamesInput) {
          elements.surnamesInput.value = "";
        }
        elements.maxWeeklyHoursInput.value = "";
        elements.workingHoursInput.value = "0";
        resetPreferencesGrid({});
      },
      setEditingId: function (id) {
        elements.teacherIdInput.value = id || "";
      },
      getEditingId: function () {
        return elements.teacherIdInput.value;
      },
      fillValues: function (item) {
        const fullName = (item.name || "").trim();
        const firstSpaceIndex = fullName.indexOf(" ");
        if (firstSpaceIndex > 0 && elements.surnamesInput) {
          elements.nameInput.value = fullName.slice(0, firstSpaceIndex);
          elements.surnamesInput.value = fullName.slice(firstSpaceIndex + 1);
        } else {
          elements.nameInput.value = fullName;
          if (elements.surnamesInput) {
            elements.surnamesInput.value = "";
          }
        }
        elements.maxWeeklyHoursInput.value = item.max_weekly_hours ?? "";
        elements.workingHoursInput.value = item.working_hours ?? "";
        resetPreferencesGrid(item.time_preferences || {});
      },
      buildPayload: function () {
        const namePart = elements.nameInput.value.trim();
        const surnamesPart = elements.surnamesInput ? elements.surnamesInput.value.trim() : "";
        return {
          name: [namePart, surnamesPart].filter(Boolean).join(" "),
          max_weekly_hours: Number(elements.maxWeeklyHoursInput.value),
          working_hours: Number(elements.workingHoursInput.value),
          time_preferences: parsePreferences(elements.timePreferencesInput.value),
        };
      },
    },
    deleteConfirm: {
      modalElement: elements.deleteModal,
      nameElement: elements.deleteName,
      actionTextElement: elements.deleteText,
      confirmButton: elements.deleteConfirmButton,
      spinnerElement: elements.deleteSpinner,
      labels: {
        defaultName: "profesor seleccionado",
        defaultAction: "Eliminar",
        withName: function () {
          return "Eliminar";
        },
      },
    },
  });
})();
