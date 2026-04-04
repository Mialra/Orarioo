(function () {
    const admin = window.AdminBase || {};
    const dom = admin.dom;

    const formElement = document.getElementById("admin-subject-form");
    if (!formElement || !admin.createEntityManager || !admin.api || !dom) {
        return;
    }

    const DAYS = ["MON", "TUE", "WED", "THU", "FRI"];
    const HOURS = ["08:00", "08:30", "09:00", "09:30", "10:00", "10:30", "11:00", "11:30", "12:00", "12:30", "13:00", "13:30", "14:00", "14:30"];
    const PREFERENCE_STATES = ["AVAILABLE", "PREFER_YES", "PREFER_NO", "UNAVAILABLE"];
    const DAY_LABELS = {
        MON: "Lunes",
        TUE: "Martes",
        WED: "Miércoles",
        THU: "Jueves",
        FRI: "Viernes",
    };

    const relationState = {
        teachers: [],
        groups: [],
        classrooms: [],
        loaded: false,
    };

    const preferenceStateBySlot = {};

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
        typeInput: document.getElementById("admin-subject-type"),
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
        typeError: document.getElementById("admin-subject-type-error"),
        teacherError: document.getElementById("admin-subject-teacher-error"),
        groupError: document.getElementById("admin-subject-group-error"),
        timePreferencesError: document.getElementById("admin-subject-time-preferences-error"),
    };

    function parseList(data) {
        if (Array.isArray(data)) {
            return data;
        }
        return data && Array.isArray(data.results) ? data.results : [];
    }

    function resolveSubjectName(subject) {
        return subject.name || "Asignatura";
    }

    function normalizeStage(stage) {
        const value = (stage || "").toString().trim().toUpperCase();
        if (value === "PRESCHOOL" || value === "PRIMARY" || value === "SECONDARY") {
            return value;
        }
        return "PRIMARY";
    }

    function normalizeType(subjectType) {
        const value = (subjectType || "").toString().trim().toUpperCase();
        if (value === "NORMAL" || value === "TC") {
            return value;
        }
        return "NORMAL";
    }

    function getStageMeta(stage) {
        const value = normalizeStage(stage);
        if (value === "PRESCHOOL") {
            return { label: "Infantil", variant: "variant-gray" };
        }
        if (value === "SECONDARY") {
            return { label: "Secundaria", variant: "variant-purple" };
        }
        return { label: "Primaria", variant: "variant-blue" };
    }

    function getTypeMeta(subjectType) {
        const value = normalizeType(subjectType);
        if (value === "TC") {
            return { label: "Trabajo de Centro", variant: "variant-purple" };
        }
        return { label: "Normal", variant: "variant-gray" };
    }

    function slotKey(day, hour) {
        return day + "_" + hour;
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

    function getBrushState() {
        const value = elements.preferenceBrushInput ? elements.preferenceBrushInput.value : "PREFER_YES";
        return PREFERENCE_STATES.indexOf(value) >= 0 ? value : "PREFER_YES";
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
                const key = slotKey(day, hour);
                const nextState = preferences && PREFERENCE_STATES.indexOf(preferences[key]) >= 0
                    ? preferences[key]
                    : "AVAILABLE";
                preferenceStateBySlot[key] = nextState;
                const cell = elements.preferencesGridContainer
                    ? elements.preferencesGridContainer.querySelector('[data-slot="' + key + '"]')
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
            return '<div class="pref-grid-header">' + DAY_LABELS[day] + "</div>";
        }).join("");

        const bodyCells = HOURS.map(function (hour) {
            const rowCells = DAYS.map(function (day) {
                const key = slotKey(day, hour);
                return (
                    '<button type="button" class="subject-pref-cell pref-cell state-AVAILABLE pref-state-AVAILABLE" data-slot="' +
                    key +
                    '" title="' + DAY_LABELS[day] + " " + hour + '"></button>'
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

    function renderSubjectItem(subject) {
        const stageMeta = getStageMeta(subject.stage);
        const typeMeta = getTypeMeta(subject.type);

        return dom.createElement("article", {
            className: "card border-0 shadow-sm admin-card admin-subject-card",
            dataset: {
                subjectId: String(subject.id),
            },
            children: [
                dom.createElement("div", {
                    className: "card-body p-3 p-md-4",
                    children: [
                        dom.createElement("div", {
                            className: "d-flex align-items-start justify-content-between gap-3",
                            children: [
                                dom.createElement("div", {
                                    className: "flex-grow-1",
                                    children: [
                                        dom.createElement("h3", {
                                            className: "h6 fw-semibold mb-2",
                                            text: resolveSubjectName(subject),
                                        }),
                                        dom.createElement("p", {
                                            className: "mb-1 text-body-secondary small",
                                            text: (subject.weekly_hours || 0) + " h semanales",
                                        }),
                                        dom.createElement("p", {
                                            className: "mb-1 text-body-secondary small",
                                            text: "Profesor: " + (subject.teacher_name || "Sin asignar"),
                                        }),
                                        dom.createElement("p", {
                                            className: "mb-2 text-body-secondary small",
                                            text: "Curso: " + (subject.group_name || "Sin asignar"),
                                        }),
                                        dom.createElement("div", {
                                            className: "d-flex flex-wrap gap-2",
                                            children: [
                                                dom.createElement("span", {
                                                    className: "admin-pill " + stageMeta.variant,
                                                    text: stageMeta.label,
                                                }),
                                                dom.createElement("span", {
                                                    className: "admin-pill " + typeMeta.variant,
                                                    text: typeMeta.label,
                                                }),
                                            ],
                                        }),
                                    ],
                                }),
                                dom.createElement("div", {
                                    className: "admin-actions",
                                    children: [
                                        createActionButton(
                                            "btn btn-link text-primary p-0 admin-action-btn admin-subject-edit-btn",
                                            "Editar asignatura",
                                            "pencil"
                                        ),
                                        createActionButton(
                                            "btn btn-link text-danger p-0 admin-action-btn admin-subject-delete-btn",
                                            "Eliminar asignatura",
                                            "trash-2"
                                        ),
                                    ],
                                }),
                            ],
                        }),
                    ],
                }),
            ],
        });
    }

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
    }

    function fillAllowedClassrooms(selectElement, items) {
        if (!selectElement) {
            return;
        }

        const selected = new Set(
            Array.from(selectElement.querySelectorAll('input[type="checkbox"]:checked')).map(function (input) {
                return String(input.value);
            })
        );

        selectElement.innerHTML = items
            .map(function (item) {
                const id = "admin-subject-allowed-classroom-" + item.id;
                const checked = selected.has(String(item.id)) ? " checked" : "";
                return (
                    '<div class="form-check mb-1">' +
                    '<input class="form-check-input" type="checkbox" id="' + id + '" value="' + item.id + '"' + checked + '>' +
                    '<label class="form-check-label" for="' + id + '">' + item.name + "</label>" +
                    "</div>"
                );
            })
            .join("");
    }

    function setMultiSelectValues(selectElement, values) {
        if (!selectElement) {
            return;
        }
        const selected = new Set((values || []).map(function (value) {
            return String(value);
        }));

        Array.from(selectElement.querySelectorAll('input[type="checkbox"]')).forEach(function (input) {
            input.checked = selected.has(String(input.value));
        });
    }

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

    async function loadRelationData() {
        const endpoints = [
            "/api/teachers/?page=1&page_size=200",
            "/api/groups/?page=1&page_size=200",
            "/api/classrooms/?page=1&page_size=200",
        ];

        const responses = await Promise.all(endpoints.map(function (endpoint) {
            return admin.api.get(endpoint);
        }));

        const teachersResponse = responses[0];
        const groupsResponse = responses[1];
        const classroomsResponse = responses[2];

        if (teachersResponse.ok) {
            relationState.teachers = parseList(teachersResponse.data);
        }
        if (groupsResponse.ok) {
            relationState.groups = parseList(groupsResponse.data);
        }
        if (classroomsResponse.ok) {
            relationState.classrooms = parseList(classroomsResponse.data);
        }

        fillSelect(elements.teacherInput, relationState.teachers, "Selecciona profesor");
        fillSelect(elements.groupInput, relationState.groups, "Selecciona curso");
        fillAllowedClassrooms(elements.allowedClassroomsInput, relationState.classrooms);

        relationState.loaded = teachersResponse.ok || groupsResponse.ok || classroomsResponse.ok;
    }

    renderPreferencesGrid();

    if (elements.preferenceClearButton) {
        elements.preferenceClearButton.addEventListener("click", function () {
            resetPreferencesGrid({});
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
        parseList: parseList,
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
            pageSize: 15,
            loadingMessage: "Cargando asignaturas...",
            emptyIcon: "book-open-text",
            emptyTitle: "No hay asignaturas",
            emptyMessage: elements.emptyMessageNode ? elements.emptyMessageNode.textContent.trim() : "No hay asignaturas registradas.",
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
                    required: true,
                    requiredMessage: "El nombre es obligatorio.",
                },
                {
                    name: "weekly_hours",
                    input: elements.weeklyHoursInput,
                    feedback: elements.weeklyHoursError,
                    required: true,
                    requiredMessage: "Las horas semanales son obligatorias.",
                },
                {
                    name: "stage",
                    input: elements.stageInput,
                    feedback: elements.stageError,
                    required: true,
                    requiredMessage: "La etapa es obligatoria.",
                },
                {
                    name: "type",
                    input: elements.typeInput,
                    feedback: elements.typeError,
                    required: true,
                    requiredMessage: "El tipo es obligatorio.",
                },
                {
                    name: "teacher",
                    input: elements.teacherInput,
                    feedback: elements.teacherError,
                    required: true,
                    requiredMessage: "Selecciona un profesor.",
                },
                {
                    name: "group",
                    input: elements.groupInput,
                    feedback: elements.groupError,
                    required: true,
                    requiredMessage: "Selecciona un curso.",
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
                { input: elements.typeInput, feedback: elements.typeError, event: "change" },
                { input: elements.teacherInput, feedback: elements.teacherError, event: "change" },
                { input: elements.groupInput, feedback: elements.groupError, event: "change" },
                { input: elements.timePreferencesInput, feedback: elements.timePreferencesError, event: "input" },
            ],
            resetValues: function () {
                elements.subjectIdInput.value = "";
                elements.nameInput.value = "";
                elements.weeklyHoursInput.value = "5";
                elements.stageInput.value = "PRIMARY";
                elements.typeInput.value = "NORMAL";
                elements.teacherInput.value = "";
                elements.groupInput.value = "";
                setMultiSelectValues(elements.allowedClassroomsInput, []);
                resetPreferencesGrid({});
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
                elements.stageInput.value = normalizeStage(item.stage);
                elements.typeInput.value = normalizeType(item.type);
                elements.teacherInput.value = item.teacher ? String(item.teacher) : "";
                elements.groupInput.value = item.group ? String(item.group) : "";
                setMultiSelectValues(elements.allowedClassroomsInput, item.allowed_classrooms || []);
                resetPreferencesGrid(item.time_preferences || {});
            },
            buildPayload: function () {
                return {
                    name: elements.nameInput.value.trim(),
                    weekly_hours: Number(elements.weeklyHoursInput.value),
                    preferred_time_slot: "",
                    time_preferences: parsePreferences(elements.timePreferencesInput.value),
                    stage: normalizeStage(elements.stageInput.value),
                    type: normalizeType(elements.typeInput.value),
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
})();
