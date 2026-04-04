(function () {
  const STORAGE = {
    access: "orarioo_access_token",
    refresh: "orarioo_refresh_token",
    user: "orarioo_user",
  };

  function getTokens() {
    return {
      access: window.localStorage.getItem(STORAGE.access),
      refresh: window.localStorage.getItem(STORAGE.refresh),
    };
  }

  function setAuthSession(payload) {
    if (payload.access) {
      window.localStorage.setItem(STORAGE.access, payload.access);
    }

    if (payload.refresh) {
      window.localStorage.setItem(STORAGE.refresh, payload.refresh);
    }

    if (payload.user) {
      window.localStorage.setItem(STORAGE.user, JSON.stringify(payload.user));
    }
  }

  function clearAuthSession() {
    window.localStorage.removeItem(STORAGE.access);
    window.localStorage.removeItem(STORAGE.refresh);
    window.localStorage.removeItem(STORAGE.user);
  }

  async function refreshAccessToken() {
    const refresh = window.localStorage.getItem(STORAGE.refresh);
    if (!refresh) {
      throw new Error("No hay refresh token disponible.");
    }

    const response = await fetch("/api/token/refresh/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ refresh: refresh }),
    });

    if (!response.ok) {
      clearAuthSession();
      throw new Error("No se pudo renovar la sesion.");
    }

    const data = await response.json();
    setAuthSession({ access: data.access, refresh: data.refresh || refresh });
    return data.access;
  }

  async function apiFetch(url, options) {
    const requestOptions = Object.assign({}, options || {});
    requestOptions.headers = Object.assign({}, requestOptions.headers || {});

    const tokens = getTokens();
    if (tokens.access) {
      requestOptions.headers.Authorization = "Bearer " + tokens.access;
    }

    let response = await fetch(url, requestOptions);

    if (response.status === 401 && tokens.refresh) {
      const newAccess = await refreshAccessToken();
      requestOptions.headers.Authorization = "Bearer " + newAccess;
      response = await fetch(url, requestOptions);
    }

    return response;
  }

  function initLucideIcons() {
    if (window.lucide && typeof window.lucide.createIcons === "function") {
      window.lucide.createIcons();
    }
  }

  function initBootstrapTooltips() {
    if (!window.bootstrap || typeof window.bootstrap.Tooltip !== "function") {
      return;
    }

    const tooltipElements = document.querySelectorAll(
      '[data-bs-toggle="tooltip"]',
    );
    tooltipElements.forEach(function (element) {
      if (!window.bootstrap.Tooltip.getInstance(element)) {
        new window.bootstrap.Tooltip(element);
      }
    });
  }

  function initPasswordToggle(options) {
    const input = document.getElementById(options.inputId);
    const button = document.getElementById(options.buttonId);
    const iconSlot = button
      ? button.querySelector(".password-toggle-icon-slot")
      : null;

    if (!input || !button) {
      return;
    }

    function syncIcon() {
      if (!iconSlot) {
        return;
      }

      const hidden = input.type === "password";
      const iconName = hidden ? "eye" : "eye-off";
      iconSlot.innerHTML =
        '<i data-lucide="' +
        iconName +
        '" class="password-toggle-icon" aria-hidden="true"></i>';
      initLucideIcons();
    }

    function syncCopy() {
      const hidden = input.type === "password";
      const text = hidden ? "Mostrar contraseña" : "Ocultar contraseña";
      button.setAttribute("title", text);
      button.setAttribute("aria-label", text);
      syncIcon();
    }

    syncCopy();

    button.addEventListener("click", function (event) {
      event.preventDefault();
      const hidden = input.type === "password";
      input.type = hidden ? "text" : "password";
      syncCopy();
    });
  }

  window.orariooAuth = {
    STORAGE: STORAGE,
    getTokens: getTokens,
    setAuthSession: setAuthSession,
    clearAuthSession: clearAuthSession,
    apiFetch: apiFetch,
    refreshAccessToken: refreshAccessToken,
    initLucideIcons: initLucideIcons,
    initBootstrapTooltips: initBootstrapTooltips,
    initPasswordToggle: initPasswordToggle,
  };
})();
