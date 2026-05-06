/**
 * Alert, busy-state, and loading/empty state rendering utilities for admin list views.
 */
(function () {
  const root = (window.OrariooAdmin = window.OrariooAdmin || {});
  const dom = root.dom;

  /**
   * Shows a Bootstrap alert element with the given message and contextual type.
   * Input: alertElement - alert DOM element
   *        message - string to display
   *        type - Bootstrap contextual type string (success, danger, warning, info)
   */
  function showAlert(alertElement, message, type) {
    if (!alertElement) {
      return;
    }
    alertElement.textContent = message;
    alertElement.classList.remove("d-none", "alert-success", "alert-danger", "alert-warning", "alert-info");
    alertElement.classList.add("alert-" + type);
  }

  /**
   * Hides a Bootstrap alert element and clears its text.
   * Input: alertElement - alert DOM element to hide
   */
  function hideAlert(alertElement) {
    if (!alertElement) {
      return;
    }
    alertElement.textContent = "";
    alertElement.classList.add("d-none");
    alertElement.classList.remove("alert-success", "alert-danger", "alert-warning", "alert-info");
  }

  /**
   * Toggles the aria-busy attribute on a container element.
   * Input: element - DOM element to mark as busy or idle
   *        isBusy - boolean; true sets aria-busy="true", false sets aria-busy="false"
   */
  function setBusy(element, isBusy) {
    if (!element) {
      return;
    }
    element.setAttribute("aria-busy", isBusy ? "true" : "false");
  }

  /**
   * Calls lucide.createIcons() if the scope element contains unresolved icon elements.
   * Input: scopeElement - DOM element to check for [data-lucide] descendants
   */
  function refreshIconsIfNeeded(scopeElement) {
    if (!scopeElement || !window.lucide || typeof window.lucide.createIcons !== "function") {
      return;
    }
    if (!scopeElement.querySelector("[data-lucide]")) {
      return;
    }
    window.lucide.createIcons();
  }

  /**
   * Replaces the container's content with a centered spinner and optional message.
   * Input: container - list container DOM element
   *        message - optional loading text (defaults to "Cargando...")
   */
  function renderLoadingState(container, message) {
    if (!container) {
      return;
    }
    container.classList.add("justify-content-center");
    dom.clearElement(container);
    container.appendChild(
      dom.createElement("div", {
        className: "col-12",
        children: [
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
          }),
        ],
      }),
    );
  }

  /**
   * Replaces the container's content with a centered icon, title, and message for empty lists.
   * Input: container - list container DOM element
   *        options - object with icon (Lucide name), title, and message strings
   */
  function renderEmptyState(container, options) {
    if (!container) {
      return;
    }
    const config = options || {};
    dom.clearElement(container);
    container.classList.add("justify-content-center");
    container.appendChild(
      dom.createElement("div", {
        className: "col-12",
        children: [
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
          }),
        ],
      }),
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
