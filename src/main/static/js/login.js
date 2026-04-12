(function () {
  const form = document.getElementById("login-form");
  const submitButton = document.getElementById("login-submit");
  const alertBox = document.getElementById("auth-alert");
  const errorHandler = window.OrariooErrorHandler || {};

  function setLoadingState(isLoading) {
    submitButton.classList.toggle("is-loading", isLoading);
    submitButton.disabled = isLoading;
  }

  function showAlert(message, type) {
    alertBox.textContent = message;
    alertBox.classList.remove("error", "info");
    alertBox.classList.add(type);
  }

  function clearAlert() {
    alertBox.textContent = "";
    alertBox.classList.remove("error", "info");
  }

  function getFriendlyLoginError(responseData) {
    if (errorHandler && typeof errorHandler.parseApiError === "function") {
      return errorHandler.parseApiError(responseData, {
        fallbackMessage: "No se pudo iniciar sesion. Intentalo de nuevo.",
      }).message;
    }

    if (!responseData) {
      return "No se pudo iniciar sesión. Inténtelo de nuevo.";
    }

    if (typeof responseData.detail === "string") {
      return responseData.detail;
    }

    if (Array.isArray(responseData.non_field_errors) && responseData.non_field_errors.length > 0) {
      return responseData.non_field_errors[0];
    }

    if (Array.isArray(responseData.email) && responseData.email.length > 0) {
      return responseData.email[0];
    }

    if (Array.isArray(responseData.password) && responseData.password.length > 0) {
      return responseData.password[0];
    }

    return "Credenciales inválidas. Revisa tu correo y contraseña.";
  }

  async function submitLogin(event) {
    event.preventDefault();
    clearAlert();

    const emailInput = document.getElementById("email");
    const passwordInput = document.getElementById("password");

    const email = emailInput.value.trim();
    const password = passwordInput.value;

    if (!email || !password) {
      showAlert("Completa correo y contraseña.", "error");
      return;
    }

    if (email.length > window.ValidationConstants.MAX_LENGTH_EXTENDED) {
      showAlert(
        "El correo no puede tener más de " + window.ValidationConstants.MAX_LENGTH_EXTENDED + " caracteres.",
        "error",
      );
      return;
    }

    setLoadingState(true);

    try {
      const response = await fetch("/api/login/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email: email, password: password }),
      });

      const data = await response.json().catch(function () {
        return null;
      });

      if (!response.ok) {
        showAlert(getFriendlyLoginError(data), "error");
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
        window.location.assign("/dashboard/");
        return;
      }

      window.orariooAuth.clearAuthSession();
    } catch (error) {
      window.orariooAuth.clearAuthSession();
    }
  }

  // Event listeners
  window.orariooAuth.initPasswordToggle({
    inputId: "password",
    buttonId: "password-toggle",
  });

  form.addEventListener("submit", submitLogin);
  redirectIfAlreadyAuthenticated();
})();
