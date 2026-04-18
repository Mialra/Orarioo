(function () {
    const admin = window.AdminBase || {};
    const dom = admin.dom;
    const fv = admin.formUtils && admin.formUtils.validators;

    const formElement = document.getElementById("admin-classroom-form");
    if (!formElement || !admin.createEntityManager || !dom) {
        return;
    }

    const elements = {
        addButton: document.getElementById("admin-add-classroom-btn"),
        alertBox: document.getElementById("admin-classrooms-alert"),
        listContainer: document.getElementById("admin-classrooms-list"),
        paginationContainer: document.getElementById("admin-classrooms-pagination"),
        emptyMessageNode: document.getElementById("admin-classrooms-empty-message"),
        formModal: document.getElementById("admin-classroom-modal"),
        formTitle: document.getElementById("admin-classroom-modal-title"),
        modeInput: document.getElementById("admin-classroom-mode"),
        classroomIdInput: document.getElementById("admin-classroom-id"),
        nameInput: document.getElementById("admin-classroom-name"),
        isSharedInput: document.getElementById("admin-classroom-is-shared"),
        submitButton: document.getElementById("admin-classroom-submit-btn"),
        submitText: document.getElementById("admin-classroom-submit-text"),
        submitSpinner: document.getElementById("admin-classroom-submit-spinner"),
        cancelButton: document.getElementById("admin-classroom-cancel-btn"),
        deleteModal: document.getElementById("admin-classroom-delete-modal"),
        deleteName: document.getElementById("admin-classroom-delete-name"),
        deleteConfirmButton: document.getElementById("admin-classroom-delete-confirm-btn"),
        deleteText: document.getElementById("admin-classroom-delete-text"),
        deleteSpinner: document.getElementById("admin-classroom-delete-spinner"),
        nameError: document.getElementById("admin-classroom-name-error"),
    };

    function resolveClassroomName(classroom) {
        return classroom.name || "Aula";
    }

    function sharedPill(isShared) {
        return dom.createElement("span", {
            className: "admin-pill " + (isShared ? "variant-blue" : "variant-gray"),
            text: isShared ? "Compartida" : "No compartida",
        });
    }

    function renderClassroomItem(classroom) {
        return dom.createElement("div", {
            className: "col",
            children: [
                dom.createElement("article", {
                    className: "card border-0 shadow-sm admin-card admin-classroom-card",
                    dataset: {
                        classroomId: String(classroom.id),
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
                                                    text: resolveClassroomName(classroom),
                                                }),
                                                dom.createElement("div", {
                                                    className: "admin-card-meta",
                                                    children: [sharedPill(classroom.is_shared)],
                                                }),
                                            ],
                                        }),
                                        dom.createElement("div", {
                                            className: "admin-actions",
                                            children: [
                                                dom.createActionButton(
                                                    "btn btn-link text-primary p-0 admin-action-btn admin-action-btn--edit admin-classroom-edit-btn",
                                                    "Editar aula",
                                                    "pencil"
                                                ),
                                                dom.createActionButton(
                                                    "btn btn-link text-danger p-0 admin-action-btn admin-action-btn--delete admin-classroom-delete-btn",
                                                    "Eliminar aula",
                                                    "trash-2"
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
        endpoint: "/api/classrooms/",
        getDetailEndpoint: function (id) {
            return "/api/classrooms/" + id + "/";
        },
        getItemId: function (item) {
            return item.id;
        },
        getItemName: function (item) {
            return resolveClassroomName(item);
        },
        parseList: admin.api.parseList,
        renderItem: renderClassroomItem,
        addButton: elements.addButton,
        alertElement: elements.alertBox,
        messages: {
            loadError: "No se pudieron cargar las aulas.",
            loadItemError: "No se pudo cargar el aula.",
            validationError: "Revisa los campos marcados en rojo.",
            saveError: "No se pudo guardar el aula.",
            deleteError: "No se pudo eliminar el aula.",
            created: "Aula creada correctamente.",
            updated: "Aula actualizada correctamente.",
            deleted: "Aula eliminada correctamente.",
        },
        list: {
            container: elements.listContainer,
            paginationContainer: elements.paginationContainer,
            pageSize: 9,
            loadingMessage: "Cargando aulas...",
            emptyIcon: "school",
            emptyTitle: "No hay aulas",
            emptyMessage: elements.emptyMessageNode ? elements.emptyMessageNode.textContent.trim() : "No hay aulas registradas.",
            rowSelector: ".admin-classroom-card",
            rowIdDataset: "classroomId",
            editSelector: ".admin-classroom-edit-btn",
            deleteSelector: ".admin-classroom-delete-btn",
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
                createTitle: "Añadir aula",
                editTitle: "Editar aula",
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
            ],
            clearValidationOnInput: [
                { input: elements.nameInput, feedback: elements.nameError, event: "input" },
            ],
            resetValues: function () {
                elements.classroomIdInput.value = "";
                elements.nameInput.value = "";
                elements.isSharedInput.checked = true;
            },
            setEditingId: function (id) {
                elements.classroomIdInput.value = id || "";
            },
            getEditingId: function () {
                return elements.classroomIdInput.value;
            },
            fillValues: function (item) {
                elements.nameInput.value = item.name || "";
                elements.isSharedInput.checked = Boolean(item.is_shared);
            },
            buildPayload: function () {
                return {
                    name: elements.nameInput.value.trim(),
                    is_shared: Boolean(elements.isSharedInput.checked),
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
                defaultName: "aula seleccionada",
                defaultAction: "Eliminar",
                withName: function () {
                    return "Eliminar";
                },
            },
        },
    });
})();
