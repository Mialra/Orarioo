/**
 * Centralised API error handler: code translation, form error mapping, and alert rendering.
 * Exposed as window.OrariooErrorHandler.
 */
(function () {
  const root = (window.OrariooErrorHandler = window.OrariooErrorHandler || {});

  /**
   * Escapes special HTML characters in a string to prevent XSS in innerHTML contexts.
   * Input: value - any value; coerced to string
   * Output: escaped string safe for HTML insertion
   */
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

  function collectDiagnostics(payload) {
    if (!payload || typeof payload !== "object") {
      return [];
    }
    if (payload.errors && Array.isArray(payload.errors.non_field_errors) && payload.errors.non_field_errors.length) {
      return payload.errors.non_field_errors;
    }
    const context = payload._error && payload._error.context ? payload._error.context : {};
    return Array.isArray(context.diagnostics) ? context.diagnostics : [];
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
      if (context.field === "email") {
        return "Ya existe un usuario con este correo electrónico.";
      }
      return "Este nombre ya existe.";
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
    BREAK_OUTSIDE_STAGE_RANGE: function () {
      return "El recreo debe estar dentro de la hora de entrada y salida de la etapa.";
    },
    INVALID_BREAK_RANGE: function () {
      return "La hora de fin del recreo debe ser posterior a la hora de inicio.";
    },
    OVERLAPPING_BREAKS: function () {
      return "Los recreos no pueden solaparse entre si.";
    },
    INVALID_SESSION_DURATION: function () {
      return "La duracion de la sesion debe ser exactamente de 60 minutos.";
    },
    INVALID_SCHEDULE_CONFIG: function () {
      return "La configuracion de tramos no es valida.";
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
    LAST_TEAM_CANNOT_LEAVE: function () {
      return "No puedes salir de tu único equipo. Crea o únete a otro equipo primero.";
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
    MISSING_SUBJECTS: function () {
      return "No puedes generar el horario sin haber creado antes al menos una asignatura.";
    },
    GROUP_WEEKLY_CAPACITY_EXCEEDED: function (entry) {
      const context = entry && entry.context ? entry.context : {};
      return (
        'El curso "' +
        (context.group_name || "sin nombre") +
        '" tiene ' +
        (context.assigned_sessions || 0) +
        " sesiones, pero su límite semanal es " +
        (context.capacity || 0) +
        "."
      );
    },
    GROUP_DAILY_CAPACITY_EXCEEDED: function (entry) {
      const context = entry && entry.context ? entry.context : {};
      return (
        'El curso "' +
        (context.group_name || "sin nombre") +
        '" no puede encajar tantas sesiones sin superar su límite diario de ' +
        (context.daily_capacity || 0) +
        "."
      );
    },
    TEACHER_WEEKLY_CAPACITY_EXCEEDED: function (entry) {
      const context = entry && entry.context ? entry.context : {};
      return (
        'El profesor "' +
        (context.teacher_name || "sin nombre") +
        '" tiene ' +
        (context.assigned_sessions || 0) +
        " sesiones, pero su límite semanal es " +
        (context.capacity || 0) +
        "."
      );
    },
    TC_SLOT_CAPACITY_EXCEEDED: function (entry) {
      const context = entry && entry.context ? entry.context : {};
      return (
        "Las sesiones TC requieren " +
        (context.required_sessions || 0) +
        " huecos, pero la capacidad actual solo permite " +
        (context.capacity || 0) +
        "."
      );
    },
    SUBJECT_NO_AVAILABLE_SLOTS: function (entry) {
      const context = entry && entry.context ? entry.context : {};
      return 'La asignatura "' + (context.subject_name || "sin nombre") + '" no tiene ningún hueco disponible.';
    },
    TEACHER_NO_AVAILABLE_SLOTS: function (entry) {
      const context = entry && entry.context ? entry.context : {};
      return 'El profesor "' + (context.teacher_name || "sin nombre") + '" no tiene ningún hueco disponible.';
    },
    GROUP_NO_AVAILABLE_SLOTS: function (entry) {
      const context = entry && entry.context ? entry.context : {};
      return 'El curso "' + (context.group_name || "sin nombre") + '" no tiene ningún hueco compatible.';
    },
    SUBJECT_INSUFFICIENT_AVAILABLE_SLOTS: function (entry) {
      const context = entry && entry.context ? entry.context : {};
      return (
        'La asignatura "' +
        (context.subject_name || "sin nombre") +
        '" necesita ' +
        (context.required_sessions || 0) +
        " sesiones, pero solo tiene " +
        (context.available_slots || 0) +
        " huecos compatibles."
      );
    },
    TEACHER_INSUFFICIENT_AVAILABLE_SLOTS: function (entry) {
      const context = entry && entry.context ? entry.context : {};
      return (
        'El profesor "' +
        (context.teacher_name || "sin nombre") +
        '" necesita ' +
        (context.required_sessions || 0) +
        " sesiones, pero solo tiene " +
        (context.available_slots || 0) +
        " huecos compatibles."
      );
    },
    GROUP_INSUFFICIENT_AVAILABLE_SLOTS: function (entry) {
      const context = entry && entry.context ? entry.context : {};
      return (
        'El curso "' +
        (context.group_name || "sin nombre") +
        '" necesita ' +
        (context.required_sessions || 0) +
        " sesiones, pero solo tiene " +
        (context.available_slots || 0) +
        " huecos compatibles."
      );
    },
    TEACHER_OVERLAPPED_DEMAND: function (entry) {
      const context = entry && entry.context ? entry.context : {};
      return (
        'El profesor "' +
        (context.teacher_name || "sin nombre") +
        '" tiene varias asignaturas compitiendo por muy pocos huecos.'
      );
    },
    GROUP_OVERLAPPED_DEMAND: function (entry) {
      const context = entry && entry.context ? entry.context : {};
      return (
        'El curso "' +
        (context.group_name || "sin nombre") +
        '" tiene varias asignaturas compitiendo por muy pocos huecos.'
      );
    },
    CLASSROOM_BOTTLENECK: function (entry) {
      const context = entry && entry.context ? entry.context : {};
      if (Array.isArray(context.subject_names) && context.subject_names.length) {
        return "Las asignaturas " + context.subject_names.join(", ") + " dependen de muy pocas aulas compatibles.";
      }
      return "Hay demasiadas sesiones compitiendo por muy pocas aulas compatibles.";
    },
    SUBJECT_TEACHER_AVAILABILITY_MISMATCH: function (entry) {
      const context = entry && entry.context ? entry.context : {};
      return (
        'La asignatura "' +
        (context.subject_name || "sin nombre") +
        '" y el profesor "' +
        (context.teacher_name || "sin nombre") +
        '" apenas comparten huecos compatibles.'
      );
    },
    SUBJECT_GROUP_AVAILABILITY_MISMATCH: function (entry) {
      const context = entry && entry.context ? entry.context : {};
      return (
        'La asignatura "' +
        (context.subject_name || "sin nombre") +
        '" y el curso "' +
        (context.group_name || "sin nombre") +
        '" apenas comparten huecos compatibles.'
      );
    },
    NO_GAP_CONSTRAINT_TOO_STRICT: function (entry) {
      const context = entry && entry.context ? entry.context : {};
      return (
        'La restricción de no dejar huecos intermedios está bloqueando al curso "' +
        (context.group_name || "sin nombre") +
        '".'
      );
    },
    STAGE_SLOT_WINDOW_TOO_NARROW: function (entry) {
      const context = entry && entry.context ? entry.context : {};
      return (
        'La etapa del curso "' +
        (context.group_name || "sin nombre") +
        '" solo deja ' +
        (context.available_slots || 0) +
        " huecos utilizables para " +
        (context.required_sessions || 0) +
        " sesiones."
      );
    },
    SCHEDULE_INFEASIBLE: function () {
      return "No se puede generar el horario con las restricciones obligatorias actuales.";
    },
    SCHEDULE_SOLVER_TIMEOUT: function () {
      return "El generador no ha podido terminar a tiempo con las restricciones actuales.";
    },
    SCHEDULE_MODEL_INVALID: function () {
      return "La configuración actual produce un modelo de horario no válido.";
    },
    SCHEDULE_INCOMPLETE_ASSIGNMENT: function () {
      return "El generador devolvió una asignación incompleta.";
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

  /**
   * Extracts the first error entry for a specific field from a structured or legacy API response.
   * Input: payload - API error response object
   *        fieldName - field key string to look up
   * Output: error entry object with code, message, and context; or null if no error found
   */
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

  /**
   * Extracts a general (non-field) error entry from a structured API response.
   * Input: payload - API error response object or null
   *        fallbackMessage - string to use when no specific message is found
   * Output: error entry object with code, message, and context
   */
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

    if (payload.errors && typeof payload.errors === "object") {
      const keys = Object.keys(payload.errors);
      for (let i = 0; i < keys.length; i++) {
        const entries = payload.errors[keys[i]];
        if (Array.isArray(entries) && entries.length && entries[0] && entries[0].code) {
          return entries[0];
        }
      }
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

  /**
   * Translates a structured error entry into a localised user-facing string.
   * Input: entry - error entry object with code, message, and context
   *        fallbackMessage - string returned when no translation matches
   * Output: localised error string
   */
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

    if (/enter a valid email address/i.test(rawMessage)) {
      return "Introduce un email válido.";
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

    if (/already exists/i.test(rawMessage)) {
      return "Este nombre ya existe.";
    }

    if (safeEntry.message) {
      return rawMessage;
    }

    return fallbackMessage || "Se ha producido un error.";
  }

  /**
   * Parses a full API error response into a structured error object.
   * Input: payload - API error response body object or null
   *        options - object with optional fallbackMessage string
   * Output: object with code, message, backendMessage, suggestions, status, and raw fields
   */
  function parseApiError(payload, options) {
    const config = options || {};
    const fallbackMessage = config.fallbackMessage || "Se ha producido un error.";
    const generalEntry = getGeneralEntry(payload, fallbackMessage);
    const translatedMessage = translateEntry(generalEntry, fallbackMessage);
    const diagnostics = collectDiagnostics(payload).map(function (entry) {
      return {
        code: normalizeCode(entry && entry.code),
        message: translateEntry(entry, entry && entry.message ? String(entry.message) : fallbackMessage),
        backendMessage: String((entry && entry.message) || ""),
        context: entry && entry.context ? entry.context : {},
        suggestions: Array.isArray(entry && entry.suggestions) ? entry.suggestions : [],
        severity: entry && entry.severity ? entry.severity : "error",
        scope: entry && entry.scope ? entry.scope : "",
      };
    });

    return {
      code: normalizeCode(generalEntry.code || (payload && payload._error ? payload._error.code : "")),
      message: translatedMessage,
      backendMessage: generalEntry.message || "",
      suggestions: Array.isArray(payload && payload.suggestions) ? payload.suggestions : [],
      diagnostics: diagnostics,
      status: payload && payload._meta ? payload._meta.status_code : 0,
      raw: payload || null,
    };
  }

  /**
   * Applies per-field server errors from an API response to matching form field elements.
   * Input: fields - array of field descriptor objects with name, input, and feedback
   *        payload - API error response body object
   */
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

  /**
   * Builds an HTML string for an alert from a parsed error info object, including suggestions.
   * Input: errorInfo - object with message string and optional suggestions array
   * Output: HTML string safe to set as innerHTML of an alert element
   */
  function renderAlertContent(errorInfo) {
    const info = errorInfo || {};
    const parts = ["<div>" + escapeHtml(info.message || "Se ha producido un error.") + "</div>"];
    const diagnostics = Array.isArray(info.diagnostics) ? info.diagnostics : [];
    // The headline already shows the first diagnostic, so skip it in the list.
    const remainingDiagnostics = diagnostics.length > 0 ? diagnostics.slice(1) : [];
    const visibleDiagnostics = remainingDiagnostics.slice(0, 5);
    const extraDiagnostics = remainingDiagnostics.slice(5);

    if (visibleDiagnostics.length) {
      parts.push('<ul class="mb-0 mt-2">');
      visibleDiagnostics.forEach(function (item) {
        parts.push(
          "<li>" + escapeHtml(item.message || item.backendMessage || "Se ha detectado un problema.") + "</li>",
        );
      });
      parts.push("</ul>");
    }

    if (extraDiagnostics.length) {
      parts.push('<details class="mt-2"><summary>Ver más problemas detectados</summary><ul class="mb-0 mt-2">');
      extraDiagnostics.forEach(function (item) {
        parts.push(
          "<li>" + escapeHtml(item.message || item.backendMessage || "Se ha detectado un problema.") + "</li>",
        );
      });
      parts.push("</ul></details>");
    }

    if (diagnostics.length) {
      info.suggestions = Array.isArray(info.suggestions) ? info.suggestions.slice() : [];
      diagnostics.forEach(function (item) {
        (item.suggestions || []).forEach(function (suggestion) {
          if (info.suggestions.indexOf(suggestion) === -1) {
            info.suggestions.push(suggestion);
          }
        });
      });
    }

    if (Array.isArray(info.suggestions) && info.suggestions.length) {
      parts.push('<details class="mt-2"><summary>Cómo resolverlo</summary><ul class="mb-0 mt-2">');
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
