(function () {
  const root = (window.OrariooErrorHandler = window.OrariooErrorHandler || {});

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function normalizeCode(code) {
    return String(code || "")
      .trim()
      .toUpperCase();
  }

  const codeMessages = {
    REQUIRED_FIELD: function () {
      return "Este campo es obligatorio.";
    },
    BLANK_FIELD: function () {
      return "Este campo no puede estar vacío.";
    },
    INVALID_EMAIL: function () {
      return "Introduce un correo electrónico válido.";
    },
    DUPLICATE_VALUE: function (entry) {
      const context = entry && entry.context ? entry.context : {};
      const value = context.value || "";
      if (context.field === "email") {
        return "Ya existe un usuario con este correo electrónico.";
      }
      if (value) {
        return 'Ya existe un registro con el valor "' + value + '".';
      }
      return "Ya existe un registro con este valor.";
    },
    REQUIRED_COLLECTION: function () {
      return "Debes seleccionar al menos un elemento.";
    },
    NULL_NOT_ALLOWED: function () {
      return "Este campo no puede quedar vacío.";
    },
    INVALID_TIME_RANGE: function () {
      return "La hora de fin debe ser posterior a la hora de inicio.";
    },
    INVALID_HOUR_RANGE: function () {
      return "Las horas de trabajo no pueden superar el máximo semanal.";
    },
    INVALID_TIME_PREFERENCE_STATE: function () {
      return "Hay preferencias horarias con valores no válidos.";
    },
    INVALID_TIME_PREFERENCE_KEY: function () {
      return "Hay franjas horarias mal definidas en las preferencias.";
    },
    PASSWORD_MISMATCH: function () {
      return "Las contraseñas no coinciden.";
    },
    PASSWORD_MIN_LENGTH: function () {
      return "La contraseña debe cumplir: mínimo 8 caracteres, al menos 1 letra y al menos 1 número.";
    },
    PASSWORD_REQUIRES_LETTER: function () {
      return "La contraseña debe cumplir: mínimo 8 caracteres, al menos 1 letra y al menos 1 número.";
    },
    PASSWORD_REQUIRES_NUMBER: function () {
      return "La contraseña debe cumplir: mínimo 8 caracteres, al menos 1 letra y al menos 1 número.";
    },
    PASSWORD_TOO_COMMON: function () {
      return "La contraseña es demasiado común. Elige una contraseña más segura.";
    },
    POLICY_NOT_ACCEPTED: function () {
      return "Debes aceptar la Política de Privacidad.";
    },
    TERMS_NOT_ACCEPTED: function () {
      return "Debes aceptar los Términos y Condiciones.";
    },
    INVALID_CREDENTIALS: function () {
      return "Las credenciales no son correctas.";
    },
    USER_DISABLED: function () {
      return "Esta cuenta está desactivada.";
    },
    INVALID_CONFIRMATION_TEXT: function () {
      return "Debes escribir exactamente tu correo electrónico actual.";
    },
    TEAM_NOT_MEMBER: function () {
      return "No puedes usar ese equipo porque no formas parte de él.";
    },
    ACTIVE_TEAM_REQUIRED: function () {
      return "Selecciona un equipo antes de continuar.";
    },
    INVITED_USER_NOT_FOUND: function () {
      return "No existe un usuario activo con ese correo electrónico.";
    },
    USER_ALREADY_IN_TEAM: function () {
      return "Ese usuario ya pertenece al equipo seleccionado.";
    },
    INVITATION_ALREADY_PENDING: function () {
      return "Ya hay una invitación pendiente para ese usuario en este equipo.";
    },
    INVALID_INTEGER: function () {
      return "Debes introducir un número entero válido.";
    },
    WEEKLY_HOURS_EXCEEDS_LIMIT: function () {
      return "Las horas semanales no pueden ser superior a 168.";
    },
    MAX_LENGTH_EXCEEDED: function (entry) {
      const context = entry && entry.context ? entry.context : {};
      const maxLength = context.max_length || "";
      if (maxLength) {
        return "Este campo no puede tener más de " + maxLength + " caracteres.";
      }
      return "Este campo excede la longitud máxima permitida.";
    },
    INVALID_GENERATION_OPTION: function () {
      return "Hay opciones de generación del horario no válidas.";
    },
    MISSING_TEACHERS: function () {
      return "No puedes generar el horario sin haber creado antes al menos un profesor.";
    },
    SCHEDULE_CAPACITY_EXCEEDED: function (entry) {
      const context = entry && entry.context ? entry.context : {};
      const resourceType = context.resource_type === "teacher" ? "profesor" : "curso";
      const resourceName = context.resource_name || "sin nombre";
      return (
        "No se puede generar el horario porque el " +
        resourceType +
        ' "' +
        resourceName +
        '" supera su capacidad disponible.'
      );
    },
    NO_COMPATIBLE_CLASSROOM: function (entry) {
      const context = entry && entry.context ? entry.context : {};
      if (context.subject) {
        return "No hay ningún aula compatible para la asignatura " + context.subject + ".";
      }
      return "No hay aulas compatibles para completar la generación del horario.";
    },
    GROUP_SLOT_CAPACITY_EXCEEDED: function () {
      return "No hay suficientes huecos disponibles para ubicar todas las sesiones.";
    },
    RECESS_SUPERVISION_UNAVAILABLE: function () {
      return "No se puede cubrir la vigilancia de recreo con la configuración actual.";
    },
    SCHEDULE_SOLVER_UNAVAILABLE: function () {
      return "El motor de generación de horarios no está disponible en este momento.";
    },
    SCHEDULE_CONFLICT: function (entry) {
      const context = entry && entry.context ? entry.context : {};
      if (context.subject && context.day && context.time && context.teacher && context.conflicting_subject) {
        return (
          "No se puede asignar " +
          context.subject +
          " el " +
          context.day +
          " a las " +
          context.time +
          " porque " +
          context.teacher +
          " ya tiene " +
          context.conflicting_subject +
          " en ese horario."
        );
      }
      return "Existe un conflicto al intentar ubicar una sesión en el horario.";
    },
    SCHEDULE_GENERATION_FAILED: function () {
      return "No se ha podido generar el horario con las restricciones actuales.";
    },
    INTERNAL_ERROR: function () {
      return "Se ha producido un error interno. Inténtalo de nuevo en unos minutos.";
    },
    THROTTLED: function (entry) {
      const raw = String((entry && entry.message) || "");
      const match = raw.match(/Expected available in\s+(\d+)\s+seconds?/i);
      if (match && match[1]) {
        return "Has realizado demasiados intentos. Inténtalo de nuevo en " + match[1] + " segundos.";
      }
      return "Has realizado demasiados intentos. Inténtalo de nuevo en unos minutos.";
    },
  };

  function getFirstFieldEntry(payload, fieldName) {
    if (!payload || typeof payload !== "object") {
      return null;
    }

    const errors = payload.errors;
    if (errors && typeof errors === "object" && Array.isArray(errors[fieldName]) && errors[fieldName].length) {
      return errors[fieldName][0];
    }

    const legacyValue = payload[fieldName];

    if (Array.isArray(legacyValue) && legacyValue.length) {
      const raw = String(legacyValue[0]);
      const lower = raw.toLowerCase();
      const code = lower.includes("email") && lower.includes("exist") ? "DUPLICATE_VALUE" : "";

      return {
        code: code,
        message: raw,
        context: { field: fieldName, value: "" },
      };
    }

    if (typeof legacyValue === "string" && legacyValue.trim()) {
      return {
        code: normalizeCode(payload && payload._error ? payload._error.code : ""),
        message: legacyValue,
        context: { field: fieldName },
      };
    }

    return null;
  }

  function getGeneralEntry(payload, fallbackMessage) {
    if (!payload || typeof payload !== "object") {
      return {
        code: "",
        message: fallbackMessage,
        context: {},
      };
    }

    const code = normalizeCode(payload && payload._error ? payload._error.code : "");
    const nonFieldErrors = payload.errors && payload.errors.non_field_errors;
    if (Array.isArray(nonFieldErrors) && nonFieldErrors.length) {
      return nonFieldErrors[0];
    }

    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return {
        code: code,
        message: payload.detail,
        context: {},
      };
    }

    return {
      code: code,
      message: fallbackMessage,
      context: {},
    };
  }

  function translateEntry(entry, fallbackMessage) {
    const safeEntry = entry || {};
    const code = normalizeCode(safeEntry.code);
    const translator = codeMessages[code];
    const context = safeEntry.context || {};
    const rawMessage = String(safeEntry.message || "");

    if (typeof translator === "function") {
      return translator(safeEntry);
    }

    if (/request was throttled/i.test(rawMessage)) {
      return codeMessages.THROTTLED(safeEntry);
    }

    if (context.field === "email" && /with this email already exists|already exists/i.test(rawMessage)) {
      return codeMessages.DUPLICATE_VALUE({ context: { field: "email" } });
    }

    if (context.field === "password" && /this password is too common/i.test(rawMessage)) {
      return codeMessages.PASSWORD_TOO_COMMON();
    }

    var minMatch = rawMessage.match(/ensure this value is greater than or equal to (\d+)/i);
    if (minMatch) {
      var minValue = parseInt(minMatch[1], 10);
      if (minValue === 0) {
        return "El valor no puede ser negativo.";
      }
      return "El valor mínimo permitido es " + minValue + ".";
    }

    var maxMatch = rawMessage.match(/ensure this value is less than or equal to (\d+)/i);
    if (maxMatch) {
      return "El valor máximo permitido es " + parseInt(maxMatch[1], 10) + ".";
    }

    var maxLengthMatch = rawMessage.match(/ensure this field has at most (\d+) character/i);
    if (maxLengthMatch) {
      var maxLength = parseInt(maxLengthMatch[1], 10);
      return "Este campo no puede tener más de " + maxLength + " caracteres.";
    }

    var cannotBeLogerMatch = rawMessage.match(/cannot be longer than (\d+) character/i);
    if (cannotBeLogerMatch) {
      var maxLength = parseInt(cannotBeLogerMatch[1], 10);
      return "Este campo no puede tener más de " + maxLength + " caracteres.";
    }

    if (safeEntry.message) {
      return rawMessage;
    }

    return fallbackMessage || "Se ha producido un error.";
  }

  function parseApiError(payload, options) {
    const config = options || {};
    const fallbackMessage = config.fallbackMessage || "Se ha producido un error.";
    const generalEntry = getGeneralEntry(payload, fallbackMessage);
    const translatedMessage = translateEntry(generalEntry, fallbackMessage);

    return {
      code: normalizeCode(generalEntry.code || (payload && payload._error ? payload._error.code : "")),
      message: translatedMessage,
      backendMessage: generalEntry.message || "",
      suggestions: Array.isArray(payload && payload.suggestions) ? payload.suggestions : [],
      status: payload && payload._meta ? payload._meta.status_code : 0,
      raw: payload || null,
    };
  }

  function applyFormErrors(fields, payload) {
    const validators = window.OrariooValidators;

    (fields || []).forEach(function (field) {
      const entry = getFirstFieldEntry(payload, field.name);
      const message = entry ? translateEntry(entry, "") : "";

      if (validators && typeof validators.setFieldValidity === "function") {
        validators.setFieldValidity(field.input, message, field.feedback);
        return;
      }

      if (field.input) {
        field.input.classList.toggle("is-invalid", Boolean(message));
      }
      if (field.feedback) {
        field.feedback.textContent = message;
      }
    });
  }

  function renderAlertContent(errorInfo) {
    const info = errorInfo || {};
    const parts = ["<div>" + escapeHtml(info.message || "Se ha producido un error.") + "</div>"];

    if (Array.isArray(info.suggestions) && info.suggestions.length) {
      parts.push('<details class="mt-2"><summary>Como resolverlo</summary><ul class="mb-0 mt-2">');
      info.suggestions.forEach(function (item) {
        parts.push("<li>" + escapeHtml(item) + "</li>");
      });
      parts.push("</ul></details>");
    }

    return parts.join("");
  }

  root.escapeHtml = escapeHtml;
  root.normalizeCode = normalizeCode;
  root.parseApiError = parseApiError;
  root.translateEntry = translateEntry;
  root.applyFormErrors = applyFormErrors;
  root.renderAlertContent = renderAlertContent;
})();
