/**
 * Bootstrap modal controller factories for form (create/edit) and confirm (delete) dialogs.
 */
(function () {
    const root = window.OrariooAdmin = window.OrariooAdmin || {};

    /**
     * Returns a Bootstrap Modal instance for the given element, creating it if necessary.
     * Input: element - modal DOM element
     * Output: Bootstrap.Modal instance, or null if Bootstrap is unavailable
     */
    function getModalInstance(element) {
        if (!window.bootstrap || !element) {
            return null;
        }
        return window.bootstrap.Modal.getOrCreateInstance(element);
    }

    /**
     * Creates a controller for a create/edit form modal that swaps titles and button labels by mode.
     * Input: config - object with modalElement, modeInput, titleElement, submitTextElement, and labels
     * Output: object with show, hide, setMode, getMode, and element
     */
    function createFormModalController(config) {
        const modalElement = config.modalElement;
        const modeInput = config.modeInput;
        const titleElement = config.titleElement;
        const submitTextElement = config.submitTextElement;
        const labels = config.labels || {
            createTitle: "Añadir",
            editTitle: "Editar",
            createSubmit: "Crear",
            editSubmit: "Guardar",
        };
        const instance = getModalInstance(modalElement);

        function setMode(mode) {
            if (modeInput) {
                modeInput.value = mode;
            }
            if (titleElement) {
                titleElement.textContent = mode === "edit" ? labels.editTitle : labels.createTitle;
            }
            if (submitTextElement) {
                submitTextElement.textContent = mode === "edit" ? labels.editSubmit : labels.createSubmit;
            }
        }

        function show() {
            if (instance) {
                instance.show();
            }
        }

        function hide() {
            if (instance) {
                instance.hide();
            }
        }

        return {
            show: show,
            hide: hide,
            setMode: setMode,
            getMode: function () {
                return modeInput ? modeInput.value : "create";
            },
            element: modalElement,
        };
    }

    /**
     * Creates a controller for a delete-confirmation modal that tracks the pending item ID.
     * Input: config - object with modalElement, nameElement, actionTextElement, and labels
     * Output: object with open, hide, clear, getPendingId, and element
     */
    function createConfirmModalController(config) {
        const modalElement = config.modalElement;
        const nameElement = config.nameElement;
        const actionTextElement = config.actionTextElement;
        const instance = getModalInstance(modalElement);
        const labels = config.labels || {
            defaultName: "seleccionado",
            defaultAction: "Eliminar",
            withName: function (name) {
                return "Eliminar " + name;
            },
        };
        let pendingId = "";

        function open(id, name) {
            pendingId = id;
            const resolvedName = name || labels.defaultName;
            if (nameElement) {
                nameElement.textContent = resolvedName;
            }
            if (actionTextElement) {
                actionTextElement.textContent = name ? labels.withName(name) : labels.defaultAction;
            }
            if (instance) {
                instance.show();
            }
        }

        function hide() {
            if (instance) {
                instance.hide();
            }
        }

        function clear() {
            pendingId = "";
            if (actionTextElement) {
                actionTextElement.textContent = labels.defaultAction;
            }
        }

        return {
            open: open,
            hide: hide,
            clear: clear,
            getPendingId: function () {
                return pendingId;
            },
            element: modalElement,
        };
    }

    root.modalUtils = {
        createFormModalController: createFormModalController,
        createConfirmModalController: createConfirmModalController,
    };
})();
