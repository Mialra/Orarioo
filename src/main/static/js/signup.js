/**
 * Sign-up page: field validation, server error mapping, and account creation flow.
 */
(function () {
  const ONBOARDING_ENTRY_KEY = "orarioo_onboarding_entry";
  const form = document.getElementById("signup-form");
  const submitButton = document.getElementById("signup-submit");
  const alertBox = document.getElementById("auth-alert");
  const privacyCheckbox = document.getElementById("privacy_policy_accepted");
  const termsCheckbox = document.getElementById("terms_conditions_accepted");

  const elements = {
    givenName: document.getElementById("given_name"),
    familyName: document.getElementById("family_name"),
    email: document.getElementById("email"),
    password: document.getElementById("password"),
    passwordConfirm: document.getElementById("password_confirm"),
    givenNameError: document.getElementById("given_name_error"),
    familyNameError: document.getElementById("family_name_error"),
    emailError: document.getElementById("email_error"),
    passwordError: document.getElementById("password_error"),
    passwordConfirmError: document.getElementById("password_confirm_error"),
    privacyError: document.getElementById("privacy_policy_accepted_error"),
    termsError: document.getElementById("terms_conditions_accepted_error"),
  };

  const fields = [
    {
      name: "given_name",
      input: elements.givenName,
      feedback: elements.givenNameError,
      rules: [{ type: "required", message: window.OrariooErrorHandler.translateEntry({ code: "REQUIRED_FIELD" }) }],
      validator: function (value) {
        if (value && value.length > window.ValidationConstants.STRING_MAX_LENGTH) {
          return "Este campo no puede tener más de " + window.ValidationConstants.STRING_MAX_LENGTH + " caracteres.";
        }
        return "";
      },
    },
    {
      name: "family_name",
      input: elements.familyName,
      feedback: elements.familyNameError,
      rules: [],
    },
    {
      name: "email",
      input: elements.email,
      feedback: elements.emailError,
      rules: [
        { type: "required", message: window.OrariooErrorHandler.translateEntry({ code: "REQUIRED_FIELD" }) },
        { type: "email", message: window.OrariooErrorHandler.translateEntry({ code: "INVALID_EMAIL" }) },
      ],
      validator: function (value) {
        if (value && value.length > window.ValidationConstants.MAX_LENGTH_EXTENDED) {
          return "Este campo no puede tener más de " + window.ValidationConstants.MAX_LENGTH_EXTENDED + " caracteres.";
        }
        return "";
      },
    },
    {
      name: "password",
      input: elements.password,
      feedback: elements.passwordError,
      rules: [{ type: "required", message: window.OrariooErrorHandler.translateEntry({ code: "REQUIRED_FIELD" }) }],
      validator: function (value) {
        const result = window.OrariooValidators.rules.password(value);
        if (result === true) return "";
        return window.OrariooErrorHandler.translateEntry({ code: result[0] });
      },
    },
    {
      name: "password_confirm",
      input: elements.passwordConfirm,
      feedback: elements.passwordConfirmError,
      rules: [{ type: "required", message: window.OrariooErrorHandler.translateEntry({ code: "REQUIRED_FIELD" }) }],
      validator: function (value) {
        if (value !== elements.password.value) {
          return window.OrariooErrorHandler.translateEntry({ code: "PASSWORD_MISMATCH" });
        }
        return "";
      },
    },
    {
      name: "privacy_policy_accepted",
      input: privacyCheckbox,
      feedback: elements.privacyError,
      event: "change",
      rules: [{ type: "checked", message: window.OrariooErrorHandler.translateEntry({ code: "POLICY_NOT_ACCEPTED" }) }],
    },
    {
      name: "terms_conditions_accepted",
      input: termsCheckbox,
      feedback: elements.termsError,
      event: "change",
      rules: [{ type: "checked", message: window.OrariooErrorHandler.translateEntry({ code: "TERMS_NOT_ACCEPTED" }) }],
    },
  ];

  window.orariooAuth.initBootstrapTooltips();
  window.orariooAuth.initPasswordToggle({ inputId: "password", buttonId: "password-toggle" });
  window.orariooAuth.initPasswordToggle({ inputId: "password_confirm", buttonId: "password-confirm-toggle" });

  function showAlert(message, type) {
    alertBox.textContent = message;
    alertBox.classList.remove("error", "info", "success");
    alertBox.classList.add(type);
  }

  function clearAlert() {
    alertBox.textContent = "";
    alertBox.classList.remove("error", "info", "success");
  }

  function clearFieldErrors() {
    fields.forEach(function (field) {
      window.OrariooValidators.clearFieldValidity(field.input, field.feedback);
    });
  }

  function validateForm(payload) {
    clearFieldErrors();
    return window.OrariooValidators.validateFields(fields, payload);
  }

  function syncLegalControls() {
    const accepted = privacyCheckbox?.checked && termsCheckbox?.checked;
    submitButton.disabled = !accepted;
    submitButton.setAttribute("aria-disabled", accepted ? "false" : "true");
  }

  function setLoadingState(isLoading) {
    submitButton.classList.toggle("is-loading", isLoading);
    const accepted = privacyCheckbox?.checked && termsCheckbox?.checked;
    submitButton.disabled = isLoading || !accepted;
  }

  function hasFieldErrors(data) {
    if (!data || typeof data !== "object") {
      return false;
    }

    const formFieldNames = fields.map(function (field) {
      return field.name;
    });

    const structuredErrors = data.errors;
    if (structuredErrors && typeof structuredErrors === "object") {
      return formFieldNames.some(function (name) {
        return Array.isArray(structuredErrors[name]) && structuredErrors[name].length > 0;
      });
    }

    return formFieldNames.some(function (name) {
      return Array.isArray(data[name]) && data[name].length > 0;
    });
  }

  function getFriendlySignupError(data) {
    if (hasFieldErrors(data)) {
      return "";
    }

    return window.OrariooErrorHandler.parseApiError(data, {
      fallbackMessage: "No se pudo crear la cuenta. Revisa los datos e inténtalo de nuevo.",
    }).message;
  }

  async function submitSignup(event) {
    event.preventDefault();
    clearAlert();

    const payload = {
      given_name: elements.givenName.value.trim(),
      family_name: elements.familyName.value.trim(),
      email: elements.email.value.trim(),
      password: elements.password.value,
      password_confirm: elements.passwordConfirm.value,
      privacy_policy_accepted: privacyCheckbox.checked,
      terms_conditions_accepted: termsCheckbox.checked,
    };

    if (!validateForm(payload)) {
      return;
    }

    setLoadingState(true);

    try {
      const response = await fetch("/api/signup/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await response.json().catch(() => null);

      if (!response.ok) {
        window.OrariooErrorHandler.applyFormErrors(fields, data);
        const alertMessage = getFriendlySignupError(data);
        if (alertMessage) {
          showAlert(alertMessage, "error");
        } else {
          clearAlert();
        }
        return;
      }

      window.orariooAuth.setAuthSession(data);
      try {
        window.sessionStorage.setItem(ONBOARDING_ENTRY_KEY, "signup");
      } catch (_error) {
        // If sessionStorage is unavailable, the onboarding page will fall back to its guard.
      }
      window.location.href = "/onboarding/";
    } catch (e) {
      showAlert("No hay conexión con el servidor.", "error");
    } finally {
      setLoadingState(false);
    }
  }

  form.addEventListener("submit", submitSignup);
  privacyCheckbox?.addEventListener("change", syncLegalControls);
  termsCheckbox?.addEventListener("change", syncLegalControls);

  syncLegalControls();
})();
