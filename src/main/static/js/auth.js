/**
 * Core authentication client: JWT token storage, auto-refresh, and shared UI utilities.
 * Exposed as window.orariooAuth.
 */
(function () {
  const STORAGE = {
    access: "orarioo_access_token",
    refresh: "orarioo_refresh_token",
    user: "orarioo_user",
  };
  let currentUserRequest = null;

  /**
   * Returns the current access and refresh tokens from localStorage.
   * Output: object with access and refresh string fields (null if absent)
   */
  function getTokens() {
    return {
      access: window.localStorage.getItem(STORAGE.access),
      refresh: window.localStorage.getItem(STORAGE.refresh),
    };
  }

  /**
   * Persists access token, refresh token, and user object to localStorage.
   * Input: payload - object with optional access, refresh, and user fields
   */
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

  /**
   * Removes all auth tokens and user data from localStorage.
   */
  function clearAuthSession() {
    window.localStorage.removeItem(STORAGE.access);
    window.localStorage.removeItem(STORAGE.refresh);
    window.localStorage.removeItem(STORAGE.user);
  }

  /**
   * Returns the last serialized user stored in localStorage, if it can be parsed safely.
   * Output: user object, or null when absent/invalid
   */
  function getStoredUser() {
    const rawUser = window.localStorage.getItem(STORAGE.user);
    if (!rawUser) {
      return null;
    }

    try {
      return JSON.parse(rawUser);
    } catch (_error) {
      return null;
    }
  }

  /**
   * Exchanges the stored refresh token for a new access token via /api/token/refresh/.
   * Output: new access token string; throws and clears session on failure
   */
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

  /**
   * Authenticated fetch wrapper that injects Bearer tokens and retries once on 401 after refreshing.
   * Input: url - endpoint path string
   *        options - standard fetch RequestInit options
   * Output: Fetch Response object
   */
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

  /**
   * Fetches /api/users/me/ once per concurrent bootstrap and refreshes the stored user payload.
   * Output: Promise resolving to the current user object
   */
  async function fetchCurrentUser() {
    if (currentUserRequest) {
      return currentUserRequest;
    }

    currentUserRequest = (async function () {
      const response = await apiFetch("/api/users/me/", {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error("No se pudo cargar el perfil.");
      }

      const user = await response.json();
      setAuthSession({ user: user });
      return user;
    })();

    try {
      return await currentUserRequest;
    } finally {
      currentUserRequest = null;
    }
  }

  /**
   * Calls lucide.createIcons() to render all [data-lucide] elements on the page.
   */
  function initLucideIcons() {
    if (window.lucide && typeof window.lucide.createIcons === "function") {
      window.lucide.createIcons();
    }
  }

  /**
   * Initialises Bootstrap tooltips on all [data-bs-toggle="tooltip"] elements not yet initialised.
   */
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

  /**
   * Wires a show/hide password toggle button to its associated input field.
   * Input: options - object with inputId and buttonId strings
   */
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
    getStoredUser: getStoredUser,
    apiFetch: apiFetch,
    fetchCurrentUser: fetchCurrentUser,
    refreshAccessToken: refreshAccessToken,
    initLucideIcons: initLucideIcons,
    initBootstrapTooltips: initBootstrapTooltips,
    initPasswordToggle: initPasswordToggle,
  };
})();
