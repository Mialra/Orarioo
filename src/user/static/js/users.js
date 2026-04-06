(function () {
  const listContainer = document.getElementById("admin-users-list");
  const paginationContainer = document.getElementById("admin-users-pagination");
  const alertBox = document.getElementById("admin-users-alert");
  const emptyMessageNode = document.getElementById("admin-users-empty-message");

  if (!listContainer || !window.orariooAuth || !window.orariooAuth.apiFetch) {
    return;
  }

  const pageSize = 9;
  let currentPage = 1;
  let totalCount = 0;

  function resolveUserName(user) {
    const fullName = ((user.given_name || "") + (user.family_name ? " " + user.family_name : "")).trim();
    return fullName || user.given_name || user.email || "Usuario";
  }

  function showAlert(message, variant) {
    if (!alertBox) {
      return;
    }
    alertBox.textContent = message;
    alertBox.className = "alert mb-3";
    alertBox.classList.add("alert-" + (variant || "danger"));
  }

  function clearAlert() {
    if (!alertBox) {
      return;
    }
    alertBox.textContent = "";
    alertBox.classList.add("d-none");
  }

  function renderEmpty() {
    listContainer.innerHTML = "";
    if (emptyMessageNode) {
      emptyMessageNode.classList.remove("d-none");
    }
  }

  function createCardHtml(user) {
    return (
      '<div class="col">' +
      '  <article class="card border-0 shadow-sm admin-card admin-user-card">' +
      '    <div class="card-body admin-card-body">' +
      '      <div class="admin-card-content admin-card-content-center">' +
      '        <div class="admin-avatar variant-blue"><i data-lucide="user"></i></div>' +
      '        <div class="admin-card-main">' +
      '          <h3 class="h6 mb-1 text-truncate">' +
      resolveUserName(user) +
      "</h3>" +
      '          <p class="admin-card-copy mb-1 text-truncate">' +
      (user.email || "") +
      "</p>" +
      "        </div>" +
      "      </div>" +
      "    </div>" +
      "  </article>" +
      "</div>"
    );
  }

  function renderUsers(users) {
    if (!users.length) {
      renderEmpty();
      return;
    }

    if (emptyMessageNode) {
      emptyMessageNode.classList.add("d-none");
    }

    listContainer.innerHTML = users.map(createCardHtml).join("");
    if (window.lucide && window.lucide.createIcons) {
      window.lucide.createIcons({ attrs: { "stroke-width": 1.8 } });
    }
  }

  function buildPagination() {
    if (!paginationContainer) {
      return;
    }

    const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
    if (totalPages <= 1) {
      paginationContainer.innerHTML = "";
      return;
    }

    const prevDisabled = currentPage <= 1 ? "disabled" : "";
    const nextDisabled = currentPage >= totalPages ? "disabled" : "";

    paginationContainer.innerHTML =
      '<div class="d-flex justify-content-center align-items-center gap-2">' +
      '  <button class="btn btn-sm btn-outline-secondary" id="admin-users-prev" ' +
      prevDisabled +
      ">Anterior</button>" +
      '  <span class="small text-secondary">Pagina ' +
      currentPage +
      " de " +
      totalPages +
      "</span>" +
      '  <button class="btn btn-sm btn-outline-secondary" id="admin-users-next" ' +
      nextDisabled +
      ">Siguiente</button>" +
      "</div>";

    const prevButton = document.getElementById("admin-users-prev");
    const nextButton = document.getElementById("admin-users-next");

    if (prevButton) {
      prevButton.addEventListener("click", function () {
        if (currentPage > 1) {
          loadUsers(currentPage - 1);
        }
      });
    }

    if (nextButton) {
      nextButton.addEventListener("click", function () {
        const total = Math.ceil(totalCount / pageSize);
        if (currentPage < total) {
          loadUsers(currentPage + 1);
        }
      });
    }
  }

  async function loadUsers(page) {
    currentPage = page || 1;
    clearAlert();
    listContainer.setAttribute("aria-busy", "true");

    try {
      const response = await window.orariooAuth.apiFetch("/api/users/?page=" + currentPage + "&page_size=" + pageSize, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      });

      const data = await response.json().catch(function () {
        return {};
      });

      if (!response.ok) {
        throw new Error((data && data.detail) || "No se pudieron cargar los usuarios del equipo.");
      }

      const results = Array.isArray(data.results) ? data.results : [];
      totalCount = Number(data.count || results.length || 0);
      renderUsers(results);
      buildPagination();
    } catch (error) {
      renderEmpty();
      showAlert(error.message || "No se pudieron cargar los usuarios del equipo.", "danger");
      if (paginationContainer) {
        paginationContainer.innerHTML = "";
      }
    } finally {
      listContainer.setAttribute("aria-busy", "false");
    }
  }

  loadUsers(1);
})();
