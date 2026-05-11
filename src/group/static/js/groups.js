/**
 * Admin page entrypoint for group CRUD management.
 */
(function () {
  const admin = window.AdminBase || {};
  const dom = admin.dom;
  const fv = admin.formUtils && admin.formUtils.validators;

  const formElement = document.getElementById("admin-group-form");
  if (!formElement || !admin.createEntityManager || !dom) {
    return;
  }

  const elements = {
    addButton: document.getElementById("admin-add-group-btn"),
    alertBox: document.getElementById("admin-groups-alert"),
    listContainer: document.getElementById("admin-groups-list"),
    paginationContainer: document.getElementById("admin-groups-pagination"),
    emptyMessageNode: document.getElementById("admin-groups-empty-message"),
    formModal: document.getElementById("admin-group-modal"),
    formTitle: document.getElementById("admin-group-modal-title"),
    modeInput: document.getElementById("admin-group-mode"),
    groupIdInput: document.getElementById("admin-group-id"),
    nameInput: document.getElementById("admin-group-name"),
    stageInput: document.getElementById("admin-group-stage"),
    submitButton: document.getElementById("admin-group-submit-btn"),
    submitText: document.getElementById("admin-group-submit-text"),
    submitSpinner: document.getElementById("admin-group-submit-spinner"),
    cancelButton: document.getElementById("admin-group-cancel-btn"),
    deleteModal: document.getElementById("admin-group-delete-modal"),
    deleteName: document.getElementById("admin-group-delete-name"),
    deleteConfirmButton: document.getElementById("admin-group-delete-confirm-btn"),
    deleteText: document.getElementById("admin-group-delete-text"),
    deleteSpinner: document.getElementById("admin-group-delete-spinner"),
    nameError: document.getElementById("admin-group-name-error"),
    stageError: document.getElementById("admin-group-stage-error"),
  };

  /**
   * Returns the display name for a group.
   * Input: group - group object from the API
   * Output: string display name, defaults to "Curso" if missing
   */
  function resolveGroupName(group) {
    return group.name || "Curso";
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
      // Labels not yet loaded — show placeholders and update when ready
      fillStageSelect((constants && constants.FALLBACK_STAGE_LABELS) || { PRESCHOOL: "Infantil", PRIMARY: "Primaria", SECONDARY: "ESO", ALEVELS: "Bachillerato" });
      if (constants && typeof constants.onStageLabelsReady === "function") {
        constants.onStageLabelsReady(fillStageSelect);
      }
    }
  }

  /**
   * Builds a pill badge for the given stage.
   * Input: stage - stage string from the API
   * Output: DOM span element with the appropriate admin-pill variant
   */
  function stagePill(stage, explicitColor) {
    const meta = getStageMeta(stage, explicitColor);
    return dom.createElement("span", {
      className: "admin-pill admin-stage-pill stage-color-" + meta.color,
      dataset: {
        stageCode: normalizeStage(stage),
      },
      text: meta.label,
    });
  }

  /**
   * Refreshes stage pills already rendered in the list when metadata changes.
   */
  function refreshStagePills() {
    document.querySelectorAll(".admin-group-card .admin-stage-pill").forEach(function (pill) {
      const code = normalizeStage(pill.dataset.stageCode);
      const meta = getStageMeta(code);
      pill.className = "admin-pill admin-stage-pill stage-color-" + meta.color;
      pill.textContent = meta.label;
    });
  }

  /**
   * Renders a single group card for the admin list.
   * Input: group - group object from the API
   * Output: DOM div element representing the group card
   */
  function renderGroupItem(group) {
    return dom.createElement("div", {
      className: "col",
      children: [
        dom.createElement("article", {
          className: "card border-0 shadow-sm admin-card admin-group-card",
          dataset: {
            groupId: String(group.id),
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
                          text: resolveGroupName(group),
                        }),
                        dom.createElement("div", {
                          className: "admin-card-meta",
                          children: [stagePill(group.stage, group.stage_color)],
                        }),
                      ],
                    }),
                    dom.createElement("div", {
                      className: "admin-actions",
                      children: [
                        dom.createActionButton(
                          "btn btn-link text-primary p-0 admin-action-btn admin-action-btn--edit admin-group-edit-btn",
                          "Editar curso",
                          "pencil",
                        ),
                        dom.createActionButton(
                          "btn btn-link text-danger p-0 admin-action-btn admin-action-btn--delete admin-group-delete-btn",
                          "Eliminar curso",
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

  admin.createEntityManager({
    endpoint: "/api/groups/",
    getDetailEndpoint: function (id) {
      return "/api/groups/" + id + "/";
    },
    getItemId: function (item) {
      return item.id;
    },
    getItemName: function (item) {
      return resolveGroupName(item);
    },
    parseList: admin.api.parseList,
    renderItem: renderGroupItem,
    addButton: elements.addButton,
    alertElement: elements.alertBox,
    messages: {
      loadError: "No se pudieron cargar los cursos.",
      loadItemError: "No se pudo cargar el curso.",
      validationError: "Revisa los campos marcados en rojo.",
      saveError: "No se pudo guardar el curso.",
      deleteError: "No se pudo eliminar el curso.",
      created: "Curso creado correctamente.",
      updated: "Curso actualizado correctamente.",
      deleted: "Curso eliminado correctamente.",
    },
    list: {
      container: elements.listContainer,
      paginationContainer: elements.paginationContainer,
      pageSize: 9,
      loadingMessage: "Cargando cursos...",
      emptyIcon: "users-round",
      emptyTitle: "No hay cursos",
      emptyMessage: elements.emptyMessageNode
        ? elements.emptyMessageNode.textContent.trim()
        : "No hay cursos registrados.",
      rowSelector: ".admin-group-card",
      rowIdDataset: "groupId",
      editSelector: ".admin-group-edit-btn",
      deleteSelector: ".admin-group-delete-btn",
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
        createTitle: "Añadir curso",
        editTitle: "Editar curso",
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
          name: "stage",
          input: elements.stageInput,
          feedback: elements.stageError,
          rules: [fv.requiredSelect(function () { return elements.stageInput; })],
        },
      ],
      clearValidationOnInput: [
        { input: elements.nameInput, feedback: elements.nameError, event: "input" },
        { input: elements.stageInput, feedback: elements.stageError, event: "change" },
      ],
      resetValues: function () {
        elements.groupIdInput.value = "";
        elements.nameInput.value = "";
        populateStageSelect();
        if (elements.stageInput.options.length > 0) {
          elements.stageInput.value = elements.stageInput.options[0].value;
        }
        refreshCustomSelect(elements.stageInput);
      },
      setEditingId: function (id) {
        elements.groupIdInput.value = id || "";
      },
      getEditingId: function () {
        return elements.groupIdInput.value;
      },
      fillValues: function (item) {
        elements.nameInput.value = item.name || "";
        populateStageSelect();
        elements.stageInput.value = normalizeStage(item.stage);
        refreshCustomSelect(elements.stageInput);
      },
      buildPayload: function () {
        return {
          name: elements.nameInput.value.trim(),
          stage: normalizeStage(elements.stageInput.value),  // uppercase pass-through
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
        defaultName: "curso seleccionado",
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
