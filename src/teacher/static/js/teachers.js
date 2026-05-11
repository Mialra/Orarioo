/**
 * Admin page entrypoint for teacher CRUD management with time-preference grid.
 */
(function () {
  const admin = window.AdminBase || {};
  const dom = admin.dom;
  const fv = admin.formUtils && admin.formUtils.validators;

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
    maxWeeklyMinutesInput: document.getElementById("admin-teacher-max-weekly-minutes"),
    weeklyHoursExactInput: document.getElementById("admin-teacher-weekly-hours-exact"),
    modeMaxButton: document.getElementById("admin-teacher-mode-max"),
    modeExactButton: document.getElementById("admin-teacher-mode-exact"),
    weeklyLoadHint: document.getElementById("admin-teacher-weekly-load-hint"),
    workingHoursInput: document.getElementById("admin-teacher-working-hours"),
    timePreferencesInput: document.getElementById("admin-teacher-time-preferences"),
    preferenceBrushInput: document.getElementById("admin-teacher-preference-brush"),
    preferenceClearButton: document.getElementById("admin-teacher-preference-clear-btn"),
    preferencesGridContainer: document.getElementById("admin-teacher-preferences-grid"),
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

  function _updateHoursModeUI() {
    const isExact = elements.weeklyHoursExactInput.value === "true";
    if (elements.modeMaxButton) {
      elements.modeMaxButton.className = "btn btn-sm " + (isExact ? "btn-outline-secondary" : "btn-primary");
    }
    if (elements.modeExactButton) {
      elements.modeExactButton.className = "btn btn-sm " + (isExact ? "btn-primary" : "btn-outline-secondary");
    }
    if (elements.weeklyLoadHint) {
      const h = Number(elements.maxWeeklyHoursInput.value) || 0;
      const m = Number(elements.maxWeeklyMinutesInput ? elements.maxWeeklyMinutesInput.value : 0) || 0;
      const timeStr = m > 0 ? h + " h " + m + " min" : h + " h";
      elements.weeklyLoadHint.innerHTML = isExact
        ? "El algoritmo asignará <strong>exactamente " + timeStr + "</strong>."
        : "El algoritmo asignará <strong>hasta " + timeStr + "</strong>, pudiendo ser menos si conviene al horario.";
    }
  }

  if (elements.modeMaxButton) {
    elements.modeMaxButton.addEventListener("click", function () {
      elements.weeklyHoursExactInput.value = "false";
      _updateHoursModeUI();
    });
  }
  if (elements.modeExactButton) {
    elements.modeExactButton.addEventListener("click", function () {
      elements.weeklyHoursExactInput.value = "true";
      _updateHoursModeUI();
    });
  }
  if (elements.maxWeeklyHoursInput) {
    elements.maxWeeklyHoursInput.addEventListener("input", _updateHoursModeUI);
  }
  if (elements.maxWeeklyMinutesInput) {
    elements.maxWeeklyMinutesInput.addEventListener("change", _updateHoursModeUI);
  }

  const prefManager = admin.createPreferencesManager({
    gridContainer: elements.preferencesGridContainer,
    brushInput: elements.preferenceBrushInput,
    timePreferencesInput: elements.timePreferencesInput,
    defaultBrushState: "AVAILABLE",
  });

  /**
   * Returns the display name for a teacher.
   * Input: teacher - teacher object from the API
   * Output: string display name, defaults to "Profesor" if missing
   */
  function resolveTeacherName(teacher) {
    return teacher.name || "Profesor";
  }

  /**
   * Renders a single teacher card for the admin list.
   * Input: teacher - teacher object from the API
   * Output: DOM div element representing the teacher card
   */
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
                              text: (function () {
                                const mins = teacher.max_weekly_minutes || 0;
                                const modeLabel = teacher.weekly_hours_exact ? "exactas" : "máximo";
                                return mins > 0
                                  ? teacher.max_weekly_hours + " h " + mins + " min " + modeLabel
                                  : teacher.max_weekly_hours + " h " + modeLabel;
                              }()),
                            }),
                          ],
                        }),
                      ],
                    }),
                    dom.createElement("div", {
                      className: "admin-actions",
                      children: [
                        dom.createActionButton(
                          "btn btn-link text-primary p-0 admin-action-btn admin-action-btn--edit admin-teacher-edit-btn",
                          "Editar profesor",
                          "pencil",
                        ),
                        dom.createActionButton(
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

  prefManager.render();

  if (elements.preferenceClearButton) {
    elements.preferenceClearButton.addEventListener("click", function () {
      prefManager.reset({});
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
    parseList: admin.api.parseList,
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
            fv.requiredString(
              function () { return elements.nameInput; },
              function () { return window.ValidationConstants.STRING_MAX_LENGTH; },
            ),
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
          rules: [fv.weeklyHours(function () { return elements.maxWeeklyHoursInput; })],
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
        { input: elements.maxWeeklyMinutesInput, feedback: elements.maxWeeklyHoursError, event: "change" },
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
        if (elements.maxWeeklyMinutesInput) {
          elements.maxWeeklyMinutesInput.value = "0";
        }
        if (elements.weeklyHoursExactInput) {
          elements.weeklyHoursExactInput.value = "false";
        }
        elements.workingHoursInput.value = "0";
        _updateHoursModeUI();
        prefManager.reset({});
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
        elements.maxWeeklyHoursInput.value = item.max_weekly_hours ?? 0;
        if (elements.maxWeeklyMinutesInput) {
          elements.maxWeeklyMinutesInput.value = item.max_weekly_minutes ?? 0;
        }
        if (elements.weeklyHoursExactInput) {
          elements.weeklyHoursExactInput.value = item.weekly_hours_exact ? "true" : "false";
        }
        _updateHoursModeUI();
        elements.workingHoursInput.value = item.working_hours ?? "";
        prefManager.reset(item.time_preferences || {});
      },
      buildPayload: function () {
        const namePart = elements.nameInput.value.trim();
        const surnamesPart = elements.surnamesInput ? elements.surnamesInput.value.trim() : "";
        return {
          name: [namePart, surnamesPart].filter(Boolean).join(" "),
          max_weekly_hours: Number(elements.maxWeeklyHoursInput.value) || 0,
          max_weekly_minutes: Number(elements.maxWeeklyMinutesInput ? elements.maxWeeklyMinutesInput.value : 0),
          weekly_hours_exact: elements.weeklyHoursExactInput.value === "true",
          working_hours: Number(elements.workingHoursInput.value),
          time_preferences: admin.parsePreferences(elements.timePreferencesInput.value),
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
