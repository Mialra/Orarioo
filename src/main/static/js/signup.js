(function () {
  const form = document.getElementById("signup-form");
  const submitButton = document.getElementById("signup-submit");
  const alertBox = document.getElementById("auth-alert");

  window.orariooAuth.initBootstrapTooltips();

  function setLoadingState(isLoading) {
    submitButton.classList.toggle("is-loading", isLoading);
    submitButton.disabled = isLoading;
  }

  function showAlert(message, type) {
    alertBox.textContent = message;
    alertBox.classList.remove("error", "info", "success");
    alertBox.classList.add(type);
  }

  function clearAlert() {
    alertBox.textContent = "";
    alertBox.classList.remove("error", "info", "success");
  }

  function normalizeKnownError(message) {
    if (!message) {
      return message;
    }

    const lower = String(message).toLowerCase();
    if (lower.includes("user with this email already exists") || lower.includes("this email is already registered")) {
      return "Ya existe una cuenta con este correo electrónico.";
    }

    return message;
  }

  function getFriendlySignupError(responseData) {
    if (!responseData) {
      return "No se pudo crear la cuenta. Inténtelo de nuevo.";
    }

    if (typeof responseData.detail === "string") {
      return normalizeKnownError(responseData.detail);
    }

    if (Array.isArray(responseData.password) && responseData.password.length > 0) {
      return normalizeKnownError(responseData.password[0]);
    }

    if (Array.isArray(responseData.password_confirm) && responseData.password_confirm.length > 0) {
      return normalizeKnownError(responseData.password_confirm[0]);
    }

    if (Array.isArray(responseData.email) && responseData.email.length > 0) {
      return normalizeKnownError(responseData.email[0]);
    }

    if (Array.isArray(responseData.given_name) && responseData.given_name.length > 0) {
      return normalizeKnownError(responseData.given_name[0]);
    }

    if (Array.isArray(responseData.family_name) && responseData.family_name.length > 0) {
      return normalizeKnownError(responseData.family_name[0]);
    }

    if (typeof responseData === "object") {
      const firstKey = Object.keys(responseData)[0];
      if (firstKey && Array.isArray(responseData[firstKey]) && responseData[firstKey].length > 0) {
        return normalizeKnownError(responseData[firstKey][0]);
      }
    }

    return "No se pudo crear la cuenta. Revisa los datos e inténtalo de nuevo.";
  }

  async function redirectIfAlreadyAuthenticated() {
    const tokens = window.orariooAuth.getTokens();
    if (!tokens.access && !tokens.refresh) {
      return;
    }

    try {
      const response = await window.orariooAuth.apiFetch("/api/users/me/", {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (response.ok) {
        window.location.replace("/dashboard/");
        return;
      }

      window.orariooAuth.clearAuthSession();
    } catch (error) {
      window.orariooAuth.clearAuthSession();
    }
  }

  async function submitSignup(event) {
    event.preventDefault();
    clearAlert();

    const payload = {
      given_name: document.getElementById("given_name").value.trim(),
      family_name: document.getElementById("family_name").value.trim(),
      email: document.getElementById("email").value.trim(),
      password: document.getElementById("password").value,
      password_confirm: document.getElementById("password_confirm").value,
    };

    if (
      !payload.given_name ||
      !payload.family_name ||
      !payload.email ||
      !payload.password ||
      !payload.password_confirm
    ) {
      showAlert("Completa todos los campos obligatorios.", "error");
      return;
    }

    if (payload.password !== payload.password_confirm) {
      showAlert("Las contraseñas no coinciden.", "error");
      return;
    }

    setLoadingState(true);

    try {
      const response = await fetch("/api/signup/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json().catch(function () {
        return null;
      });

      if (!response.ok) {
        showAlert(getFriendlySignupError(data), "error");
        return;
      }

      window.orariooAuth.setAuthSession(data);
      window.location.assign("/dashboard/");
    } catch (error) {
      showAlert("No hay conexión con el servidor. Inténtelo en unos segundos.", "error");
    } finally {
      setLoadingState(false);
    }
  }

  window.orariooAuth.initPasswordToggle({
    inputId: "password",
    buttonId: "password-toggle",
  });

  window.orariooAuth.initPasswordToggle({
    inputId: "password_confirm",
    buttonId: "password-confirm-toggle",
  });

  form.addEventListener("submit", submitSignup);
  redirectIfAlreadyAuthenticated();
})();
