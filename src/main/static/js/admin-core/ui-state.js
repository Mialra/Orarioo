(function () {
    const root = window.OrariooAdmin = window.OrariooAdmin || {};
    const dom = root.dom;

    function showAlert(alertElement, message, type) {
        if (!alertElement) {
            return;
        }
        alertElement.textContent = message;
        alertElement.classList.remove("d-none", "alert-success", "alert-danger", "alert-warning", "alert-info");
        alertElement.classList.add("alert-" + type);
    }

    function hideAlert(alertElement) {
        if (!alertElement) {
            return;
        }
        alertElement.textContent = "";
        alertElement.classList.add("d-none");
        alertElement.classList.remove("alert-success", "alert-danger", "alert-warning", "alert-info");
    }

    function setBusy(element, isBusy) {
        if (!element) {
            return;
        }
        element.setAttribute("aria-busy", isBusy ? "true" : "false");
    }

    function refreshIconsIfNeeded(scopeElement) {
        if (!scopeElement || !window.lucide || typeof window.lucide.createIcons !== "function") {
            return;
        }
        if (!scopeElement.querySelector("[data-lucide]")) {
            return;
        }
        window.lucide.createIcons();
    }

    function renderLoadingState(container, message) {
        if (!container) {
            return;
        }
        dom.clearElement(container);
        container.appendChild(
            dom.createElement("div", {
                className: "card border-0 bg-light-subtle",
                children: [
                    dom.createElement("div", {
                        className: "card-body py-5 text-center",
                        children: [
                            dom.createElement("div", {
                                className: "spinner-border text-primary mb-3",
                                attrs: { role: "status", "aria-hidden": "true" },
                            }),
                            dom.createElement("p", {
                                className: "text-body-secondary mb-0",
                                text: message || "Cargando...",
                            }),
                        ],
                    }),
                ],
            })
        );
    }

    function renderEmptyState(container, options) {
        if (!container) {
            return;
        }
        const config = options || {};
        dom.clearElement(container);
        container.appendChild(
            dom.createElement("div", {
                className: "card border-0 bg-light-subtle",
                children: [
                    dom.createElement("div", {
                        className: "card-body py-5 text-center",
                        children: [
                            dom.createElement("div", {
                                className: "admin-list-state-icon mx-auto mb-3",
                                children: [dom.createLucideIcon(config.icon || "inbox")],
                            }),
                            dom.createElement("h3", {
                                className: "h6 mb-1",
                                text: config.title || "Sin datos",
                            }),
                            dom.createElement("p", {
                                className: "text-body-secondary mb-0",
                                text: config.message || "No hay elementos para mostrar.",
                            }),
                        ],
                    }),
                ],
            })
        );
        refreshIconsIfNeeded(container);
    }

    root.uiState = {
        showAlert: showAlert,
        hideAlert: hideAlert,
        setBusy: setBusy,
        renderLoadingState: renderLoadingState,
        renderEmptyState: renderEmptyState,
        refreshIconsIfNeeded: refreshIconsIfNeeded,
    };
})();
