/**
 * Admin page entrypoint for read-only user list with pagination.
 */
(function () {
  const admin = window.AdminBase || {};
  const api = admin.api;
  const uiState = admin.uiState;
  const listRenderer = admin.listRenderer;
  const dom = admin.dom;

  const listContainer = document.getElementById("admin-users-list");
  const paginationContainer = document.getElementById("admin-users-pagination");
  const alertBox = document.getElementById("admin-users-alert");
  const emptyMessageNode = document.getElementById("admin-users-empty-message");

  if (!listContainer || !api || !uiState || !listRenderer || !dom || !admin.setupPagination) {
    return;
  }

  const paginationController = admin.setupPagination({
    container: paginationContainer,
    pageSize: 9,
  });

  /**
   * Returns the best available display name for a user object.
   * Input: user - user object with given_name, family_name, and email fields
   * Output: display name string, falling back through full name → given name → email → "Usuario"
   */
  function resolveUserName(user) {
    const fullName = ((user.given_name || "") + (user.family_name ? " " + user.family_name : "")).trim();
    return fullName || user.given_name || user.email || "Usuario";
  }

  /**
   * Builds the card DOM node for a single user list item.
   * Input: user - user object with given_name, family_name, and email fields
   * Output: col div element containing the user card
   */
  function renderUserItem(user) {
    return dom.createElement("div", {
      className: "col",
      children: [
        dom.createElement("article", {
          className: "card border-0 shadow-sm admin-card admin-user-card",
          children: [
            dom.createElement("div", {
              className: "card-body admin-card-body",
              children: [
                dom.createElement("div", {
                  className: "admin-card-content admin-card-content-center",
                  children: [
                    dom.createElement("div", {
                      className: "admin-avatar variant-blue",
                      children: [dom.createLucideIcon("user")],
                    }),
                    dom.createElement("div", {
                      className: "admin-card-main",
                      children: [
                        dom.createElement("h3", {
                          className: "h6 mb-1 text-truncate",
                          text: resolveUserName(user),
                        }),
                        dom.createElement("p", {
                          className: "admin-card-copy mb-1 text-truncate",
                          text: user.email || "",
                        }),
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
   * Renders an array of user objects into the list container and refreshes Lucide icons.
   * Input: users - array of user objects
   */
  function renderUsers(users) {
    listRenderer.renderCollection(listContainer, users, renderUserItem);
    uiState.refreshIconsIfNeeded(listContainer);
  }

  /**
   * Fetches a paginated user list from the API and renders it into the list container.
   * Input: page - page number to fetch (defaults to the current pagination controller page)
   */
  async function loadUsers(page) {
    const targetPage = Number(page) || paginationController.getCurrentPage() || 1;
    uiState.hideAlert(alertBox);
    uiState.setBusy(listContainer, true);
    uiState.renderLoadingState(listContainer, "Cargando usuarios...");

    const response = await api.get("/api/users/?page=" + targetPage + "&page_size=" + paginationController.pageSize);

    if (!response.ok) {
      uiState.showAlert(alertBox, "No se pudieron cargar los usuarios del equipo.", "danger");
      uiState.renderEmptyState(listContainer, {
        icon: "users-round",
        title: "No hay usuarios",
        message: emptyMessageNode ? emptyMessageNode.textContent.trim() : "No hay usuarios en el equipo activo.",
      });
      if (paginationContainer) {
        paginationContainer.innerHTML = "";
      }
      uiState.setBusy(listContainer, false);
      return;
    }

    const data = response.data || {};
    const results = Array.isArray(data.results) ? data.results : [];
    const totalItems = typeof data.count === "number" ? data.count : results.length;

    paginationController.setTotalItems(totalItems);
    paginationController.setPage(targetPage);

    if (!results.length) {
      uiState.renderEmptyState(listContainer, {
        icon: "users-round",
        title: "No hay usuarios",
        message: emptyMessageNode ? emptyMessageNode.textContent.trim() : "No hay usuarios en el equipo activo.",
      });
    } else {
      renderUsers(results);
    }

    paginationController.render(function (nextPage) {
      loadUsers(nextPage);
    });

    uiState.setBusy(listContainer, false);
  }

  loadUsers(1);
})();
