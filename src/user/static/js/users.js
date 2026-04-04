(function () {
    const admin = window.AdminBase || {};
    const dom = admin.dom;

    const formElement = document.getElementById("admin-user-form");
    if (!formElement || !admin.createEntityManager || !dom) {
        return;
    }

    const elements = {
        addButton: document.getElementById("admin-add-user-btn"),
        alertBox: document.getElementById("admin-users-alert"),
        listContainer: document.getElementById("admin-users-list"),
        paginationContainer: document.getElementById("admin-users-pagination"),
        emptyMessageNode: document.getElementById("admin-users-empty-message"),
        formModal: document.getElementById("admin-user-modal"),
        formTitle: document.getElementById("admin-user-modal-title"),
        modeInput: document.getElementById("admin-user-mode"),
        userIdInput: document.getElementById("admin-user-id"),
        givenNameInput: document.getElementById("admin-user-given-name"),
        familyNameInput: document.getElementById("admin-user-family-name"),
        emailInput: document.getElementById("admin-user-email"),
        roleInput: document.getElementById("admin-user-role"),
        submitButton: document.getElementById("admin-user-submit-btn"),
        submitText: document.getElementById("admin-user-submit-text"),
        submitSpinner: document.getElementById("admin-user-submit-spinner"),
        cancelButton: document.getElementById("admin-user-cancel-btn"),
        deleteModal: document.getElementById("admin-user-delete-modal"),
        deleteName: document.getElementById("admin-user-delete-name"),
        deleteConfirmButton: document.getElementById("admin-user-delete-confirm-btn"),
        deleteText: document.getElementById("admin-user-delete-text"),
        deleteSpinner: document.getElementById("admin-user-delete-spinner"),
        givenNameError: document.getElementById("admin-user-given-name-error"),
        emailError: document.getElementById("admin-user-email-error"),
        roleError: document.getElementById("admin-user-role-error"),
    };

    function resolveRoleLabel(user) {
        if (user.role === "direccion") {
            return "Dirección";
        }
        if (user.role === "administrator") {
            return "Administrador";
        }
        return user.role_display || "";
    }

    function resolveUserName(user) {
        const fullName = ((user.given_name || "") + (user.family_name ? " " + user.family_name : "")).trim();
        return fullName || user.given_name || user.email || "Usuario";
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

    function renderUserItem(user) {
        const isAdmin = user.role === "administrator";

        return dom.createElement("article", {
            className: "card border-0 shadow-sm admin-user-card",
            dataset: {
                userId: String(user.id),
            },
            children: [
                dom.createElement("div", {
                    className: "card-body p-3 p-md-4",
                    children: [
                        dom.createElement("div", {
                            className: "d-flex align-items-center gap-3",
                            children: [
                                dom.createElement("div", {
                                    className: "admin-user-avatar " + (isAdmin ? "avatar-purple" : "avatar-blue"),
                                    children: [dom.createLucideIcon(isAdmin ? "shield" : "user")],
                                }),
                                dom.createElement("div", {
                                    className: "flex-grow-1 min-w-0",
                                    children: [
                                        dom.createElement("h3", {
                                            className: "h6 mb-1 text-truncate",
                                            text: resolveUserName(user),
                                        }),
                                        dom.createElement("p", {
                                            className: "text-body-secondary mb-1 text-truncate",
                                            text: user.email || "",
                                        }),
                                        dom.createElement("span", {
                                            className: "badge rounded-pill admin-role-pill " + (isAdmin ? "role-purple" : "role-blue"),
                                            text: resolveRoleLabel(user),
                                        }),
                                    ],
                                }),
                                dom.createElement("div", {
                                    className: "d-flex align-items-center gap-2 ms-auto",
                                    children: [
                                        createActionButton(
                                            "btn btn-link text-primary p-0 admin-icon-btn admin-user-edit-btn",
                                            "Editar usuario",
                                            "pencil"
                                        ),
                                        createActionButton(
                                            "btn btn-link text-danger p-0 admin-icon-btn admin-user-delete-btn",
                                            "Eliminar usuario",
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

    admin.createEntityManager({
        endpoint: "/api/users/",
        createEndpoint: "/api/users/managed_create/",
        getDetailEndpoint: function (id) {
            return "/api/users/" + id + "/";
        },
        getItemId: function (item) {
            return item.id;
        },
        getItemName: function (item) {
            return resolveUserName(item);
        },
        parseList: function (data) {
            if (Array.isArray(data)) {
                return data;
            }
            return data && Array.isArray(data.results) ? data.results : [];
        },
        renderItem: renderUserItem,
        addButton: elements.addButton,
        alertElement: elements.alertBox,
        messages: {
            loadError: "No se pudieron cargar los usuarios.",
            loadItemError: "No se pudo cargar el usuario.",
            validationError: "Revisa los campos marcados en rojo.",
            saveError: "No se pudo guardar el usuario.",
            deleteError: "No se pudo eliminar el usuario.",
            created: "Usuario creado correctamente.",
            updated: "Usuario actualizado correctamente.",
            deleted: "Usuario eliminado correctamente.",
        },
        list: {
            container: elements.listContainer,
            paginationContainer: elements.paginationContainer,
            pageSize: 9,
            loadingMessage: "Cargando usuarios...",
            emptyIcon: "users",
            emptyTitle: "No hay usuarios",
            emptyMessage: elements.emptyMessageNode ? elements.emptyMessageNode.textContent.trim() : "No hay usuarios registrados.",
            rowSelector: ".admin-user-card",
            rowIdDataset: "userId",
            editSelector: ".admin-user-edit-btn",
            deleteSelector: ".admin-user-delete-btn",
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
            focusInput: elements.givenNameInput,
            labels: {
                createTitle: "Añadir usuario",
                editTitle: "Editar usuario",
                createSubmit: "Crear",
                editSubmit: "Guardar",
            },
            messages: {
                saving: "Guardando...",
            },
            fields: [
                {
                    name: "given_name",
                    input: elements.givenNameInput,
                    feedback: elements.givenNameError,
                    required: true,
                    requiredMessage: "El nombre es obligatorio.",
                },
                {
                    name: "email",
                    input: elements.emailInput,
                    feedback: elements.emailError,
                    required: true,
                    requiredMessage: "El correo electrónico es obligatorio.",
                    validator: function () {
                        return elements.emailInput.checkValidity() ? "" : "Introduce un correo electrónico válido.";
                    },
                },
                {
                    name: "role",
                    input: elements.roleInput,
                    feedback: elements.roleError,
                    required: true,
                    requiredMessage: "Selecciona un rol.",
                },
            ],
            clearValidationOnInput: [
                { input: elements.givenNameInput, feedback: elements.givenNameError, event: "input" },
                { input: elements.emailInput, feedback: elements.emailError, event: "input" },
                { input: elements.roleInput, feedback: elements.roleError, event: "change" },
            ],
            resetValues: function () {
                elements.userIdInput.value = "";
                elements.givenNameInput.value = "";
                elements.familyNameInput.value = "";
                elements.emailInput.value = "";
                elements.roleInput.value = "direccion";
            },
            setEditingId: function (id) {
                elements.userIdInput.value = id || "";
            },
            getEditingId: function () {
                return elements.userIdInput.value;
            },
            fillValues: function (item) {
                elements.givenNameInput.value = item.given_name || "";
                elements.familyNameInput.value = item.family_name || "";
                elements.emailInput.value = item.email || "";
                elements.roleInput.value = item.role || "direccion";
            },
            buildPayload: function () {
                return {
                    given_name: elements.givenNameInput.value.trim(),
                    family_name: elements.familyNameInput.value.trim(),
                    email: elements.emailInput.value.trim(),
                    role: elements.roleInput.value,
                    can_login: false,
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
                defaultName: "usuario seleccionado",
                defaultAction: "Eliminar",
                withName: function () {
                    return "Eliminar";
                },
            },
        },
    });
})();