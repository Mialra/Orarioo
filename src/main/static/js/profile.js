(function () {
  const personalForm = document.getElementById("profile-personal-form");
  const passwordForm = document.getElementById("profile-password-form");
  const personalEditTrigger = document.getElementById("profile-personal-edit-trigger");
  const passwordEditTrigger = document.getElementById("profile-password-edit-trigger");
  const personalActions = document.getElementById("profile-personal-actions");
  const passwordActions = document.getElementById("profile-password-actions");
  const cancelEditBtn = document.getElementById("profile-cancel-btn");
  const cancelPasswordBtn = document.getElementById("profile-password-cancel-btn");
  const saveProfileBtn = document.getElementById("profile-save-btn");

  const givenNameEl = document.getElementById("profile-given-name");
  const familyNameEl = document.getElementById("profile-family-name");
  const emailEl = document.getElementById("profile-email");
  const displayNameEl = document.getElementById("profile-display-name");
  const displayEmailEl = document.getElementById("profile-display-email");
  const avatarEl = document.getElementById("profile-avatar");
  const roleBadgeEl = document.getElementById("profile-role-badge");

  const personalAlertEl = document.getElementById("profile-personal-alert");
  const passwordAlertEl = document.getElementById("profile-password-alert");
  const exportAlertEl = document.getElementById("profile-export-alert");
  const deletePageAlertEl = document.getElementById("profile-delete-page-alert");
  const deleteModalAlertEl = document.getElementById("profile-delete-modal-alert");
  const deleteConfirmationEmailLabelEl = document.getElementById("profile-delete-confirmation-email-label");

  const currentPasswordEl = document.getElementById("profile-current-password");
  const newPasswordEl = document.getElementById("profile-new-password");
  const confirmPasswordEl = document.getElementById("profile-confirm-password");
  const passwordSubmitBtn = document.getElementById("profile-password-submit");

  const exportButton = document.getElementById("profile-export-btn");
  const deleteAccountForm = document.getElementById("profile-delete-account-form");
  const deleteConfirmationEl = document.getElementById("profile-delete-confirmation");
  const deleteConfirmationFeedbackEl = document.getElementById("profile-delete-confirmation-feedback");
  const deleteAccountSubmitBtn = document.getElementById("profile-delete-account-submit");
  const deleteAccountModalEl = document.getElementById("profileDeleteAccountModal");

  let currentUser = null;

  function setControlDisabled(control, disabled) {
    if (control) {
      control.disabled = disabled;
    }
  }

  function resetAlert(alertEl) {
    if (!alertEl) {
      return;
    }
    alertEl.textContent = "";
    alertEl.classList.add("d-none");
    alertEl.classList.remove("alert-danger", "alert-success", "alert-info");
  }

  function showAlert(alertEl, message, type) {
    if (!alertEl) {
      return;
    }
    alertEl.textContent = message;
    alertEl.classList.remove("d-none", "alert-danger", "alert-success", "alert-info");
    alertEl.classList.add(type || "alert-info");
  }

  function getInitials(givenName, familyName) {
    const first = (givenName || "").trim().charAt(0);
    const second = (familyName || "").trim().charAt(0);
    const initials = (first + second).toUpperCase();
    return initials || "--";
  }

  function getFullName(givenName, familyName) {
    const fullName = [givenName, familyName].filter(Boolean).join(" ").trim();
    return fullName || "Usuario";
  }

  function setPersonalEditMode(enabled) {
    setControlDisabled(givenNameEl, !enabled);
    setControlDisabled(familyNameEl, !enabled);

    if (personalActions) {
      personalActions.classList.toggle("d-none", !enabled);
    }

    if (personalEditTrigger) {
      personalEditTrigger.setAttribute("aria-pressed", enabled ? "true" : "false");
      personalEditTrigger.disabled = enabled;
    }
  }

  function setPasswordEditMode(enabled) {
    setControlDisabled(currentPasswordEl, !enabled);
    setControlDisabled(newPasswordEl, !enabled);
    setControlDisabled(confirmPasswordEl, !enabled);

    if (passwordActions) {
      passwordActions.classList.toggle("d-none", !enabled);
    }

    if (passwordEditTrigger) {
      passwordEditTrigger.setAttribute("aria-pressed", enabled ? "true" : "false");
      passwordEditTrigger.disabled = enabled;
    }
  }

  function setPersonalLoading(isLoading) {
    if (saveProfileBtn) {
      saveProfileBtn.disabled = isLoading;
      saveProfileBtn.textContent = isLoading ? "Guardando..." : "Guardar cambios";
    }
  }

  function setPasswordLoading(isLoading) {
    if (passwordSubmitBtn) {
      passwordSubmitBtn.disabled = isLoading;
      passwordSubmitBtn.textContent = isLoading ? "Actualizando..." : "Actualizar contraseña";
    }
  }

  function setExportLoading(isLoading) {
    if (!exportButton) {
      return;
    }
    exportButton.disabled = isLoading;
    exportButton.textContent = isLoading ? "Preparando descarga..." : "Descargar mis datos (JSON)";
  }

  function setDeleteLoading(isLoading) {
    if (deleteAccountSubmitBtn) {
      deleteAccountSubmitBtn.disabled = isLoading;
      deleteAccountSubmitBtn.textContent = isLoading ? "Eliminando..." : "Eliminar cuenta";
    }
    if (deleteConfirmationEl) {
      deleteConfirmationEl.disabled = isLoading;
    }
  }

  function setDeleteFeedback(message) {
    if (!deleteConfirmationFeedbackEl) {
      return;
    }
    if (!message) {
      deleteConfirmationFeedbackEl.textContent = "";
      deleteConfirmationFeedbackEl.classList.add("d-none");
      if (deleteConfirmationEl) {
        deleteConfirmationEl.classList.remove("is-invalid");
      }
      return;
    }

    deleteConfirmationFeedbackEl.textContent = message;
    deleteConfirmationFeedbackEl.classList.remove("d-none");
    if (deleteConfirmationEl) {
      deleteConfirmationEl.classList.add("is-invalid");
    }
  }

  function syncDeleteButtonState() {
    if (!deleteAccountSubmitBtn || !deleteConfirmationEl) {
      return;
    }

    const expectedEmail = (
      deleteConfirmationEmailLabelEl && deleteConfirmationEmailLabelEl.textContent
        ? deleteConfirmationEmailLabelEl.textContent
        : currentUser && currentUser.email
          ? currentUser.email
          : ""
    ).trim();
    const confirmation = deleteConfirmationEl.value.trim();
    const isExact = confirmation.toLowerCase() === expectedEmail.toLowerCase();
    deleteAccountSubmitBtn.disabled = !isExact;

    if (!confirmation) {
      setDeleteFeedback("");
      return;
    }

    if (!isExact) {
      setDeleteFeedback("Debes escribir exactamente tu correo electrónico para confirmar la eliminación.");
      return;
    }

    setDeleteFeedback("");
  }

  function resetDeleteModalState() {
    resetAlert(deleteModalAlertEl);
    if (deleteAccountForm) {
      deleteAccountForm.reset();
    }
    setDeleteFeedback("");
    setDeleteLoading(false);
    syncDeleteButtonState();
  }

  async function ensureAuthenticatedProfile() {
    const tokens = window.orariooAuth.getTokens();
    if (!tokens.access && !tokens.refresh) {
      window.location.assign("/sign-in/");
      return null;
    }

    const response = await window.orariooAuth.apiFetch("/api/users/me/", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      window.orariooAuth.clearAuthSession();
      window.location.assign("/sign-in/");
      return null;
    }

    return response.json();
  }

  function renderProfile(userData) {
    if (!userData) {
      return;
    }

    currentUser = userData;
    const givenName = userData.given_name || "";
    const familyName = userData.family_name || "";
    const email = userData.email || "";

    if (deleteConfirmationEmailLabelEl) {
      deleteConfirmationEmailLabelEl.textContent = email || "tu correo electrónico";
    }
    if (deleteConfirmationEl) {
      deleteConfirmationEl.placeholder = email || "usuario@dominio.com";
    }

    if (givenNameEl) {
      givenNameEl.value = givenName;
    }
    if (familyNameEl) {
      familyNameEl.value = familyName;
    }
    if (emailEl) {
      emailEl.value = email;
    }

    if (displayNameEl) {
      displayNameEl.textContent = getFullName(givenName, familyName);
    }
    if (displayEmailEl) {
      displayEmailEl.textContent = email || "-";
    }
    if (avatarEl) {
      avatarEl.textContent = getInitials(givenName, familyName);
    }
    if (roleBadgeEl) {
      roleBadgeEl.textContent = userData.is_superuser ? "Administrador" : "Usuario";
    }

    syncDeleteButtonState();
  }

  function resetPersonalFields() {
    if (!currentUser) {
      return;
    }
    renderProfile(currentUser);
  }

  function resetPasswordFields() {
    if (passwordForm) {
      passwordForm.reset();
    }
  }

  function parseErrorDetail(payload, fallbackMessage) {
    if (!payload) {
      return fallbackMessage;
    }
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
    if (Array.isArray(payload.non_field_errors) && payload.non_field_errors.length) {
      return payload.non_field_errors[0];
    }
    const firstKey = Object.keys(payload)[0];
    if (!firstKey) {
      return fallbackMessage;
    }
    const value = payload[firstKey];
    if (Array.isArray(value) && value.length) {
      return value[0];
    }
    if (typeof value === "string") {
      return value;
    }
    return fallbackMessage;
  }

  async function savePersonalData(event) {
    event.preventDefault();
    resetAlert(personalAlertEl);

    const givenName = givenNameEl ? givenNameEl.value.trim() : "";
    const familyName = familyNameEl ? familyNameEl.value.trim() : "";

    if (!givenName || !familyName) {
      showAlert(personalAlertEl, "Nombre y apellidos son obligatorios.", "alert-danger");
      return;
    }

    setPersonalLoading(true);

    try {
      const response = await window.orariooAuth.apiFetch("/api/users/me/update/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          given_name: givenName,
          family_name: familyName,
        }),
      });

      const payload = await response.json().catch(function () {
        return null;
      });

      if (!response.ok) {
        const message = parseErrorDetail(payload, "No se pudo actualizar el perfil.");
        showAlert(personalAlertEl, message, "alert-danger");
        return;
      }

      renderProfile(payload);
      setPersonalEditMode(false);
      showAlert(personalAlertEl, "Perfil actualizado correctamente.", "alert-success");
    } catch (_error) {
      showAlert(personalAlertEl, "No se pudo actualizar el perfil. Inténtalo de nuevo.", "alert-danger");
    } finally {
      setPersonalLoading(false);
    }
  }

  async function updatePassword(event) {
    event.preventDefault();
    resetAlert(passwordAlertEl);

    const currentPassword = currentPasswordEl ? currentPasswordEl.value : "";
    const newPassword = newPasswordEl ? newPasswordEl.value : "";
    const passwordConfirm = confirmPasswordEl ? confirmPasswordEl.value : "";

    if (!currentPassword || !newPassword || !passwordConfirm) {
      showAlert(passwordAlertEl, "Completa los tres campos de contraseña.", "alert-danger");
      return;
    }

    if (newPassword.length < 8) {
      showAlert(passwordAlertEl, "La nueva contraseña debe tener al menos 8 caracteres.", "alert-danger");
      return;
    }

    if (newPassword !== passwordConfirm) {
      showAlert(passwordAlertEl, "Las nuevas contraseñas no coinciden.", "alert-danger");
      return;
    }

    setPasswordLoading(true);

    try {
      const response = await window.orariooAuth.apiFetch("/api/users/change_password/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
          password_confirm: passwordConfirm,
        }),
      });

      const payload = await response.json().catch(function () {
        return null;
      });

      if (!response.ok) {
        const message = parseErrorDetail(payload, "No se pudo cambiar la contraseña.");
        showAlert(passwordAlertEl, message, "alert-danger");
        return;
      }

      if (payload && payload.access) {
        window.orariooAuth.setAuthSession(payload);
      }

      if (passwordForm) {
        passwordForm.reset();
      }
      setPasswordEditMode(false);
      showAlert(passwordAlertEl, "Contraseña actualizada correctamente.", "alert-success");
    } catch (_error) {
      showAlert(passwordAlertEl, "No se pudo cambiar la contraseña. Inténtalo de nuevo.", "alert-danger");
    } finally {
      setPasswordLoading(false);
    }
  }

  async function exportData() {
    resetAlert(exportAlertEl);
    setExportLoading(true);

    try {
      const response = await window.orariooAuth.apiFetch("/profile/export-data/", {
        method: "POST",
      });

      if (!response.ok) {
        const payload = await response.json().catch(function () {
          return null;
        });
        const detail = payload && payload.detail ? payload.detail : "No se pudo generar la exportación de datos.";
        showAlert(exportAlertEl, detail, "alert-danger");
        return;
      }

      const disposition = response.headers.get("Content-Disposition") || "";
      let filename = "orarioo-personal-data.json";
      const match = disposition.match(/filename="?([^";]+)"?/i);
      if (match && match[1]) {
        filename = match[1];
      }

      const blob = await response.blob();
      const objectUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(objectUrl);
      showAlert(exportAlertEl, "Exportación completada correctamente.", "alert-success");
    } catch (_error) {
      showAlert(exportAlertEl, "No se pudo completar la descarga. Inténtalo de nuevo.", "alert-danger");
    } finally {
      setExportLoading(false);
    }
  }

  async function deleteAccount(event) {
    event.preventDefault();
    resetAlert(deleteModalAlertEl);
    resetAlert(deletePageAlertEl);

    const expectedEmail = (
      deleteConfirmationEmailLabelEl && deleteConfirmationEmailLabelEl.textContent
        ? deleteConfirmationEmailLabelEl.textContent
        : currentUser && currentUser.email
          ? currentUser.email
          : ""
    ).trim();
    const confirmationText = deleteConfirmationEl ? deleteConfirmationEl.value.trim() : "";

    if (confirmationText.toLowerCase() !== expectedEmail.toLowerCase()) {
      setDeleteFeedback("Debes escribir exactamente tu correo electrónico para confirmar la eliminación.");
      showAlert(deleteModalAlertEl, "Revisa la confirmación antes de continuar.", "alert-danger");
      return;
    }

    setDeleteLoading(true);

    try {
      const response = await window.orariooAuth.apiFetch("/api/users/me/delete-account/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          confirmation_text: confirmationText,
        }),
      });

      const payload = await response.json().catch(function () {
        return null;
      });

      if (!response.ok) {
        const message = parseErrorDetail(payload, "No se pudo eliminar la cuenta.");
        showAlert(deleteModalAlertEl, message, "alert-danger");
        return;
      }

      const modalInstance =
        window.bootstrap && typeof window.bootstrap.Modal === "function"
          ? window.bootstrap.Modal.getInstance(deleteAccountModalEl) || new window.bootstrap.Modal(deleteAccountModalEl)
          : null;
      if (modalInstance) {
        modalInstance.hide();
      }

      showAlert(
        deletePageAlertEl,
        "Tu cuenta ha sido eliminada correctamente. Se cerrará la sesión en unos segundos.",
        "alert-success",
      );
      window.orariooAuth.clearAuthSession();
      window.setTimeout(function () {
        window.location.assign("/sign-in/");
      }, 1800);
    } catch (_error) {
      showAlert(deleteModalAlertEl, "No se pudo eliminar la cuenta. Inténtalo de nuevo.", "alert-danger");
    } finally {
      setDeleteLoading(false);
    }
  }

  async function initializeProfilePage() {
    resetAlert(personalAlertEl);
    resetAlert(passwordAlertEl);
    resetAlert(exportAlertEl);

    setPersonalEditMode(false);
    setPasswordEditMode(false);
    setPersonalLoading(false);
    setPasswordLoading(false);
    setExportLoading(true);

    const userData = await ensureAuthenticatedProfile();
    if (!userData) {
      return;
    }

    renderProfile(userData);
    setExportLoading(false);

    if (window.orariooAuth && typeof window.orariooAuth.initLucideIcons === "function") {
      window.orariooAuth.initLucideIcons();
    }

    if (personalEditTrigger) {
      personalEditTrigger.addEventListener("click", function () {
        resetAlert(personalAlertEl);
        setPersonalEditMode(true);
        if (givenNameEl) {
          givenNameEl.focus();
        }
      });
    }

    if (cancelEditBtn) {
      cancelEditBtn.addEventListener("click", function () {
        resetAlert(personalAlertEl);
        resetPersonalFields();
        setPersonalEditMode(false);
      });
    }

    if (passwordEditTrigger) {
      passwordEditTrigger.addEventListener("click", function () {
        resetAlert(passwordAlertEl);
        setPasswordEditMode(true);
        if (currentPasswordEl) {
          currentPasswordEl.focus();
        }
      });
    }

    if (cancelPasswordBtn) {
      cancelPasswordBtn.addEventListener("click", function () {
        resetAlert(passwordAlertEl);
        resetPasswordFields();
        setPasswordEditMode(false);
      });
    }

    if (personalForm) {
      personalForm.addEventListener("submit", savePersonalData);
    }

    if (passwordForm) {
      passwordForm.addEventListener("submit", updatePassword);
    }

    if (exportButton) {
      exportButton.addEventListener("click", exportData);
    }

    if (deleteConfirmationEl) {
      deleteConfirmationEl.addEventListener("input", syncDeleteButtonState);
      deleteConfirmationEl.addEventListener("change", syncDeleteButtonState);
      deleteConfirmationEl.addEventListener("keyup", syncDeleteButtonState);
      deleteConfirmationEl.addEventListener("paste", function () {
        window.setTimeout(syncDeleteButtonState, 0);
      });
    }

    if (deleteAccountForm) {
      deleteAccountForm.addEventListener("submit", deleteAccount);
    }

    if (deleteAccountModalEl) {
      deleteAccountModalEl.addEventListener("show.bs.modal", function () {
        resetAlert(deletePageAlertEl);
        resetDeleteModalState();
        if (deleteConfirmationEl) {
          deleteConfirmationEl.focus();
        }
      });
      deleteAccountModalEl.addEventListener("hidden.bs.modal", resetDeleteModalState);
    }
  }

  initializeProfilePage();
})();
