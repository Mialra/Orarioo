/**
 * Admin page entrypoint for subject CRUD management with relation data loading.
 */
(function () {
  const admin = window.AdminBase || {};
  const dom = admin.dom;
  const fv = admin.formUtils && admin.formUtils.validators;

  const formElement = document.getElementById("admin-subject-form");
  if (!formElement || !admin.createEntityManager || !admin.api || !dom) {
    return;
  }

  const relationState = {
    teachers: [],
    groups: [],
    classrooms: [],
    loaded: false,
    loadPromise: null,
  };

  const elements = {
    addButton: document.getElementById("admin-add-subject-btn"),
    alertBox: document.getElementById("admin-subjects-alert"),
    listContainer: document.getElementById("admin-subjects-list"),
    paginationContainer: document.getElementById("admin-subjects-pagination"),
    emptyMessageNode: document.getElementById("admin-subjects-empty-message"),
    formModal: document.getElementById("admin-subject-modal"),
    formTitle: document.getElementById("admin-subject-modal-title"),
    modeInput: document.getElementById("admin-subject-mode"),
    subjectIdInput: document.getElementById("admin-subject-id"),
    nameInput: document.getElementById("admin-subject-name"),
    weeklyHoursInput: document.getElementById("admin-subject-weekly-hours"),
    stageInput: document.getElementById("admin-subject-stage"),
    teacherInput: document.getElementById("admin-subject-teacher"),
    groupInput: document.getElementById("admin-subject-group"),
    allowedClassroomsInput: document.getElementById("admin-subject-allowed-classrooms"),
    timePreferencesInput: document.getElementById("admin-subject-time-preferences"),
    preferenceBrushInput: document.getElementById("admin-subject-preference-brush"),
    preferenceClearButton: document.getElementById("admin-subject-preference-clear-btn"),
    preferencesGridContainer: document.getElementById("admin-subject-preferences-grid"),
    submitButton: document.getElementById("admin-subject-submit-btn"),
    submitText: document.getElementById("admin-subject-submit-text"),
    submitSpinner: document.getElementById("admin-subject-submit-spinner"),
    cancelButton: document.getElementById("admin-subject-cancel-btn"),
    deleteModal: document.getElementById("admin-subject-delete-modal"),
    deleteName: document.getElementById("admin-subject-delete-name"),
    deleteConfirmButton: document.getElementById("admin-subject-delete-confirm-btn"),
    deleteText: document.getElementById("admin-subject-delete-text"),
    deleteSpinner: document.getElementById("admin-subject-delete-spinner"),
    nameError: document.getElementById("admin-subject-name-error"),
    weeklyHoursError: document.getElementById("admin-subject-weekly-hours-error"),
    stageError: document.getElementById("admin-subject-stage-error"),
    teacherError: document.getElementById("admin-subject-teacher-error"),
    groupError: document.getElementById("admin-subject-group-error"),
    timePreferencesError: document.getElementById("admin-subject-time-preferences-error"),
  };

  const prefManager = admin.createPreferencesManager({
    gridContainer: elements.preferencesGridContainer,
    brushInput: elements.preferenceBrushInput,
    timePreferencesInput: elements.timePreferencesInput,
    defaultBrushState: "PREFER_YES",
  });

  /**
   * Returns the display name for a subject.
   * Input: subject - subject object from the API
   * Output: string display name, defaults to "Asignatura" if missing
   */
  function resolveSubjectName(subject) {
    return subject.name || "Asignatura";
  }

  /**
   * Normalizes a stage value to uppercase, passing through any custom code.
   * Input: stage - raw stage string from the API or form
   * Output: string uppercased stage code
   */
  function normalizeStage(stage) {
    return (stage || "").toString().trim().toUpperCase();
  }

  /**
   * Refreshes a custom select UI widget after its value changes programmatically.
   * Input: selectElement - native select DOM element to refresh
   */
  function refreshCustomSelect(selectElement) {
    if (window.OrariooSelects && typeof window.OrariooSelects.refresh === "function" && selectElement) {
      window.OrariooSelects.refresh(selectElement);
    }
  }

  /**
   * Refreshes all custom select inputs in the subject form.
   */
  function refreshSubjectSelects() {
    [elements.stageInput, elements.teacherInput, elements.groupInput].forEach(refreshCustomSelect);
  }

  /**
   * Returns the display label and configured color for a stage value.
   * Input: stage - stage string
   * Output: object with label (string) and color (palette key)
   */
  function getStageMeta(stage, explicitColor) {
    const code = normalizeStage(stage);
    const stageConstants = window.OrariooAdmin && window.OrariooAdmin.constants;
    const label = stageConstants && typeof stageConstants.getStageLabel === "function"
      ? stageConstants.getStageLabel(code)
      : code;
    const color = explicitColor || (stageConstants && typeof stageConstants.getStageColor === "function"
      ? stageConstants.getStageColor(code)
      : "blue");
    return { label: label, color: color };
  }

  /**
   * Populates the stage select from STAGE_LABELS constants.
   * Input: none
   * Output: options are added to elements.stageInput
   */
  function fillStageSelect(stageLabels) {
    const entries = Object.entries(stageLabels);
    while (elements.stageInput.options.length > 0) { elements.stageInput.remove(0); }
    entries.forEach(function ([code, label]) {
      var opt = document.createElement("option"); opt.value = code; opt.textContent = label; elements.stageInput.appendChild(opt);
    });
    refreshCustomSelect(elements.stageInput);
  }

  function populateStageSelect() {
    const constants = window.OrariooAdmin && window.OrariooAdmin.constants;
    const stageLabels = (constants && constants.STAGE_LABELS) || {};
    if (Object.keys(stageLabels).length > 0) {
      fillStageSelect(stageLabels);
    } else {
      fillStageSelect((constants && constants.FALLBACK_STAGE_LABELS) || { PRESCHOOL: "Infantil", PRIMARY: "Primaria", SECONDARY: "ESO", ALEVELS: "Bachillerato" });
      if (constants && typeof constants.onStageLabelsReady === "function") {
        constants.onStageLabelsReady(fillStageSelect);
      }
    }
  }

  /**
   * Refreshes stage pills already rendered in the list when metadata changes.
   */
  function refreshStagePills() {
    document.querySelectorAll(".admin-subject-card .admin-stage-pill").forEach(function (pill) {
      const code = normalizeStage(pill.dataset.stageCode);
      const meta = getStageMeta(code);
      pill.className = "admin-pill admin-stage-pill stage-color-" + meta.color;
      pill.textContent = meta.label;
    });
  }

  /**
   * Renders a single subject card for the admin list.
   * Input: subject - subject object from the API
   * Output: DOM div element representing the subject card
   */
  function renderSubjectItem(subject) {
    const stageMeta = getStageMeta(subject.stage, subject.stage_color);

    return dom.createElement("div", {
      className: "col",
      children: [
        dom.createElement("article", {
          className: "card border-0 shadow-sm admin-card admin-subject-card",
          dataset: {
            subjectId: String(subject.id),
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
                          className: "h6 fw-semibold mb-0",
                          text: resolveSubjectName(subject),
                        }),
                        dom.createElement("p", {
                          className: "admin-card-copy mb-1",
                          text: (subject.weekly_hours || 0) + " h semanales",
                        }),
                        dom.createElement("p", {
                          className: "admin-card-copy mb-1",
                          text: "Profesor: " + (subject.teacher_name || "Sin asignar"),
                        }),
                        dom.createElement("p", {
                          className: "admin-card-copy mb-0",
                          text: "Curso: " + (subject.group_name || "Sin asignar"),
                        }),
                        dom.createElement("div", {
                          className: "admin-card-meta",
                          children: [
                            dom.createElement("span", {
                              className: "admin-pill admin-stage-pill stage-color-" + stageMeta.color,
                              dataset: {
                                stageCode: normalizeStage(subject.stage),
                              },
                              text: stageMeta.label,
                            }),
                          ],
                        }),
                      ],
                    }),
                    dom.createElement("div", {
                      className: "admin-actions",
                      children: [
                        dom.createActionButton(
                          "btn btn-link text-primary p-0 admin-action-btn admin-action-btn--edit admin-subject-edit-btn",
                          "Editar asignatura",
                          "pencil",
                        ),
                        dom.createActionButton(
                          "btn btn-link text-danger p-0 admin-action-btn admin-action-btn--delete admin-subject-delete-btn",
                          "Eliminar asignatura",
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

  /**
   * Populates a select element with items from a list, preserving the current selection.
   * Input: selectElement - native select DOM element to populate
   *        items - array of objects with id and name properties
   *        placeholder - optional string for the empty first option
   */
  function fillSelect(selectElement, items, placeholder) {
    if (!selectElement) {
      return;
    }

    const currentValue = selectElement.value;
    const options = [];
    if (placeholder) {
      options.push('<option value="">' + placeholder + "</option>");
    }

    items.forEach(function (item) {
      options.push('<option value="' + item.id + '">' + item.name + "</option>");
    });

    selectElement.innerHTML = options.join("");
    if (currentValue && selectElement.querySelector('option[value="' + currentValue + '"]')) {
      selectElement.value = currentValue;
    }
    refreshCustomSelect(selectElement);
  }

  /**
   * Populates the allowed-classrooms checkbox list, preserving current checked state.
   * Input: selectElement - container DOM element for the checkbox list
   *        items - array of classroom objects with id and name properties
   */
  function fillAllowedClassrooms(selectElement, items) {
    if (!selectElement) {
      return;
    }

    const selected = new Set(
      Array.from(selectElement.querySelectorAll('input[type="checkbox"]:checked')).map(function (input) {
        return String(input.value);
      }),
    );

    selectElement.innerHTML = items
      .map(function (item) {
        const id = "admin-subject-allowed-classroom-" + item.id;
        const checked = selected.has(String(item.id)) ? " checked" : "";
        return (
          '<div class="form-check mb-1">' +
          '<input class="form-check-input" type="checkbox" id="' +
          id +
          '" value="' +
          item.id +
          '"' +
          checked +
          ">" +
          '<label class="form-check-label" for="' +
          id +
          '">' +
          item.name +
          "</label>" +
          "</div>"
        );
      })
      .join("");
  }

  /**
   * Sets the checked state of checkboxes in a container to match the given values.
   * Input: selectElement - container DOM element with checkbox inputs
   *        values - array of values to mark as checked
   */
  function setMultiSelectValues(selectElement, values) {
    if (!selectElement) {
      return;
    }
    const selected = new Set(
      (values || []).map(function (value) {
        return String(value);
      }),
    );

    Array.from(selectElement.querySelectorAll('input[type="checkbox"]')).forEach(function (input) {
      input.checked = selected.has(String(input.value));
    });
  }

  /**
   * Returns the IDs of all checked classrooms in the allowed-classrooms container.
   * Input: selectElement - container DOM element with checkbox inputs
   * Output: array of positive integers representing selected classroom IDs
   */
  function getSelectedAllowedClassrooms(selectElement) {
    if (!selectElement) {
      return [];
    }

    return Array.from(selectElement.querySelectorAll('input[type="checkbox"]:checked'))
      .map(function (input) {
        return Number(input.value);
      })
      .filter(function (value) {
        return Number.isFinite(value) && value > 0;
      });
  }

  /**
   * Loads teachers, groups, and classrooms from the API and populates the form selects.
   * Output: populates relationState and form select/checkbox inputs; resolves when all requests complete
   */
  async function loadRelationData() {
    if (relationState.loaded) {
      return relationState;
    }
    if (relationState.loadPromise) {
      return relationState.loadPromise;
    }

    const endpoints = [
      "/api/teachers/?summary=options",
      "/api/groups/?summary=options",
      "/api/classrooms/?summary=options",
    ];

    relationState.loadPromise = Promise.all(
      endpoints.map(function (endpoint) {
        return admin.api.get(endpoint);
      }),
    )
      .then(function (responses) {
        const teachersResponse = responses[0];
        const groupsResponse = responses[1];
        const classroomsResponse = responses[2];

        if (teachersResponse.ok) {
          relationState.teachers = admin.api.parseList(teachersResponse.data);
        }
        if (groupsResponse.ok) {
          relationState.groups = admin.api.parseList(groupsResponse.data);
        }
        if (classroomsResponse.ok) {
          relationState.classrooms = admin.api.parseList(classroomsResponse.data);
        }

        fillSelect(elements.teacherInput, relationState.teachers, "Selecciona profesor");
        fillSelect(elements.groupInput, relationState.groups, "Selecciona curso");
        fillAllowedClassrooms(elements.allowedClassroomsInput, relationState.classrooms);

        relationState.loaded = teachersResponse.ok && groupsResponse.ok && classroomsResponse.ok;
        return relationState;
      })
      .finally(function () {
        relationState.loadPromise = null;
      });

    return relationState.loadPromise;
  }

  prefManager.render();

  if (elements.preferenceClearButton) {
    elements.preferenceClearButton.addEventListener("click", function () {
      prefManager.reset({});
    });
  }

  if (elements.formModal) {
    elements.formModal.addEventListener("show.bs.modal", function () {
      loadRelationData();
    });
  }

  loadRelationData();

  admin.createEntityManager({
    endpoint: "/api/subjects/",
    getDetailEndpoint: function (id) {
      return "/api/subjects/" + id + "/";
    },
    getItemId: function (item) {
      return item.id;
    },
    getItemName: function (item) {
      return resolveSubjectName(item);
    },
    parseList: admin.api.parseList,
    renderItem: renderSubjectItem,
    addButton: elements.addButton,
    alertElement: elements.alertBox,
    messages: {
      loadError: "No se pudieron cargar las asignaturas.",
      loadItemError: "No se pudo cargar la asignatura.",
      validationError: "Revisa los campos marcados en rojo.",
      saveError: "No se pudo guardar la asignatura.",
      deleteError: "No se pudo eliminar la asignatura.",
      created: "Asignatura creada correctamente.",
      updated: "Asignatura actualizada correctamente.",
      deleted: "Asignatura eliminada correctamente.",
    },
    list: {
      container: elements.listContainer,
      paginationContainer: elements.paginationContainer,
      pageSize: 9,
      loadingMessage: "Cargando asignaturas...",
      emptyIcon: "book-open-text",
      emptyTitle: "No hay asignaturas",
      emptyMessage: elements.emptyMessageNode
        ? elements.emptyMessageNode.textContent.trim()
        : "No hay asignaturas registradas.",
      rowSelector: ".admin-subject-card",
      rowIdDataset: "subjectId",
      editSelector: ".admin-subject-edit-btn",
      deleteSelector: ".admin-subject-delete-btn",
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
        createTitle: "Añadir asignatura",
        editTitle: "Editar asignatura",
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
              function () { return window.ValidationConstants.MAX_LENGTH_EXTENDED; },
            ),
          ],
        },
        {
          name: "weekly_hours",
          input: elements.weeklyHoursInput,
          feedback: elements.weeklyHoursError,
          rules: [fv.weeklyHours(function () { return elements.weeklyHoursInput; })],
        },
        {
          name: "stage",
          input: elements.stageInput,
          feedback: elements.stageError,
          rules: [fv.requiredSelect(function () { return elements.stageInput; })],
        },
        {
          name: "teacher",
          input: elements.teacherInput,
          feedback: elements.teacherError,
          rules: [fv.requiredPositiveInt(function () { return elements.teacherInput; })],
        },
        {
          name: "group",
          input: elements.groupInput,
          feedback: elements.groupError,
          rules: [fv.requiredPositiveInt(function () { return elements.groupInput; })],
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
        { input: elements.weeklyHoursInput, feedback: elements.weeklyHoursError, event: "input" },
        { input: elements.stageInput, feedback: elements.stageError, event: "change" },
        { input: elements.teacherInput, feedback: elements.teacherError, event: "change" },
        { input: elements.groupInput, feedback: elements.groupError, event: "change" },
        { input: elements.timePreferencesInput, feedback: elements.timePreferencesError, event: "input" },
      ],
      resetValues: function () {
        elements.subjectIdInput.value = "";
        elements.nameInput.value = "";
        elements.weeklyHoursInput.value = "";
        populateStageSelect();
        if (elements.stageInput.options.length > 0) {
          elements.stageInput.value = elements.stageInput.options[0].value;
        }
        elements.teacherInput.value = "";
        elements.groupInput.value = "";
        setMultiSelectValues(elements.allowedClassroomsInput, []);
        prefManager.reset({});
        refreshSubjectSelects();
      },
      setEditingId: function (id) {
        elements.subjectIdInput.value = id || "";
      },
      getEditingId: function () {
        return elements.subjectIdInput.value;
      },
      fillValues: function (item) {
        elements.nameInput.value = item.name || "";
        elements.weeklyHoursInput.value = item.weekly_hours ?? "";
        populateStageSelect();
        elements.stageInput.value = normalizeStage(item.stage);
        elements.teacherInput.value = item.teacher ? String(item.teacher) : "";
        elements.groupInput.value = item.group ? String(item.group) : "";
        setMultiSelectValues(elements.allowedClassroomsInput, item.allowed_classrooms || []);
        prefManager.reset(item.time_preferences || {});
        refreshSubjectSelects();
      },
      buildPayload: function () {
        return {
          name: elements.nameInput.value.trim(),
          weekly_hours: Number(elements.weeklyHoursInput.value),
          preferred_time_slot: "",
          time_preferences: admin.parsePreferences(elements.timePreferencesInput.value),
          stage: normalizeStage(elements.stageInput.value),
          teacher: Number(elements.teacherInput.value),
          group: Number(elements.groupInput.value),
          allowed_classrooms: getSelectedAllowedClassrooms(elements.allowedClassroomsInput),
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
        defaultName: "asignatura seleccionada",
        defaultAction: "Eliminar",
        withName: function () {
          return "Eliminar";
        },
      },
    },
  });

  window.addEventListener("orarioo:stage-metadata-changed", function () {
    populateStageSelect();
    refreshStagePills();
  });
})();
