/**
 * Client-side field validator: rule primitives, per-field validation, and live-binding helpers.
 * Exposed as window.OrariooValidators.
 */
(function () {
  const root = (window.OrariooValidators = window.OrariooValidators || {});

  function normalizeText(value) {
    if (value === null || value === undefined) {
      return "";
    }
    return String(value);
  }

  function normalizeBoolean(value) {
    return Boolean(value);
  }

  const rules = {
    required: function (value) {
      return normalizeText(value).trim() !== "";
    },
    email: function (value) {
      const text = normalizeText(value).trim();
      if (!text) {
        return false;
      }
      return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(text);
    },
    password: function (value) {
      const text = normalizeText(value);
      const errors = [];

      if (text.length < 8) {
        errors.push("PASSWORD_MIN_LENGTH");
      }

      if (!/[A-Za-z]/.test(text)) {
        errors.push("PASSWORD_REQUIRES_LETTER");
      }

      if (!/\d/.test(text)) {
        errors.push("PASSWORD_REQUIRES_NUMBER");
      }

      return errors.length ? errors : true;
    },
    noSpaces: function (value) {
      return !/\s/.test(normalizeText(value));
    },
    positiveInteger: function (value) {
      const text = normalizeText(value).trim();
      if (!text) {
        return false;
      }
      return /^[1-9]\d*$/.test(text);
    },
    nonNegativeInteger: function (value) {
      const text = normalizeText(value).trim();
      if (!text) {
        return false;
      }
      return /^\d+$/.test(text);
    },
    checked: function (value) {
      return normalizeBoolean(value);
    },
  };

  /**
   * Applies or clears the is-invalid class and feedback text on a form input.
   * Input: input - form input DOM element
   *        message - error string; empty string clears the error
   *        feedback - feedback DOM element for error text
   */
  function setFieldValidity(input, message, feedback) {
    if (!input) {
      return;
    }

    const hasError = Boolean(message);
    input.classList.toggle("is-invalid", hasError);

    if (feedback) {
      feedback.textContent = message || "";
      feedback.classList.toggle("d-block", hasError);
    }
  }

  function clearFieldValidity(input, feedback) {
    setFieldValidity(input, "", feedback);
  }

  /**
   * Evaluates a single rule against a value and returns an error string, array, or empty string.
   * Input: rule - function, rule object with type/message, or rule object with validator function
   *        value - current field value
   *        fieldName - field name string (passed to custom validators)
   * Output: error string, array of error strings, or empty string on success
   */
  function resolveRule(rule, value, fieldName) {
    if (typeof rule === "function") {
      return rule(value, fieldName);
    }

    if (!rule || typeof rule !== "object") {
      return "";
    }

    if (typeof rule.validator === "function") {
      return rule.validator(value, fieldName);
    }

    const validator = rules[rule.type];
    if (typeof validator !== "function") {
      return "";
    }

    const validationResult = validator(value, fieldName);

    if (validationResult === true) {
      return "";
    }

    if (validationResult === false) {
      if (typeof rule.message === "function") {
        return rule.message("", value, fieldName) || "Revisa este campo.";
      }
      return rule.message || "Revisa este campo.";
    }

    if (typeof validationResult === "string") {
      if (typeof rule.message === "function") {
        return rule.message(validationResult, value, fieldName) || "Revisa este campo.";
      }
      return validationResult;
    }

    if (Array.isArray(validationResult)) {
      if (typeof rule.message === "function") {
        return validationResult
          .map(function (code) {
            return rule.message(code, value, fieldName) || "Revisa este campo.";
          })
          .filter(Boolean);
      }
      return validationResult;
    }

    return "Revisa este campo.";
  }

  /**
   * Runs an ordered list of rules against one value and returns a validity result.
   * Input: fieldName - field name string
   *        value - current field value
   *        fieldRules - array of rule descriptors
   *        options - object with optional collectAllErrors boolean
   * Output: object with valid boolean and error string
   */
  function validateField(fieldName, value, fieldRules, options) {
    const normalizedRules = Array.isArray(fieldRules) ? fieldRules : [];
    const collectAllErrors = Boolean(options && options.collectAllErrors);
    const errors = [];

    for (let index = 0; index < normalizedRules.length; index += 1) {
      const result = resolveRule(normalizedRules[index], value, fieldName);

      if (Array.isArray(result)) {
        if (result.length) {
          errors.push.apply(errors, result);
          if (!collectAllErrors) {
            return {
              valid: false,
              error: String(result[0]),
            };
          }
        }
        continue;
      }

      if (typeof result === "string" && result) {
        errors.push(result);
        if (!collectAllErrors) {
          return {
            valid: false,
            error: result,
          };
        }
      }
    }

    if (errors.length) {
      return {
        valid: false,
        error: errors.join(" "),
      };
    }

    return {
      valid: true,
      error: "",
    };
  }

  /**
   * Validates all fields in the array against the payload and applies error states to their inputs.
   * Input: fields - array of field descriptor objects with name, input, feedback, and rules
   *        payload - object mapping field names to current values
   * Output: boolean true if all fields passed validation
   */
  function validateFields(fields, payload) {
    let isValid = true;

    (fields || []).forEach(function (field) {
      const value = payload[field.name];
      const fieldRules = [];

      if (field.required) {
        fieldRules.push({
          type: field.input && field.input.type === "checkbox" ? "checked" : "required",
          message: field.requiredMessage || "Este campo es obligatorio.",
        });
      }

      if (Array.isArray(field.rules)) {
        fieldRules.push.apply(fieldRules, field.rules);
      }

      if (typeof field.validator === "function") {
        fieldRules.push({
          validator: function (currentValue) {
            return field.validator(currentValue, payload) || "";
          },
        });
      }

      const result = validateField(field.name, value, fieldRules, {
        collectAllErrors: field.collectAllErrors,
      });
      setFieldValidity(field.input, result.error, field.feedback);
      if (!result.valid) {
        isValid = false;
      }
    });

    return isValid;
  }

  /**
   * Attaches a live validation listener to a field's input element.
   * Input: field - field descriptor object
   *        valueGetter - optional function() returning the current value; defaults to input.value
   */
  function bindLiveValidation(field, valueGetter) {
    if (!field || !field.input) {
      return;
    }

    const eventName = field.event || "input";
    field.input.addEventListener(eventName, function () {
      const currentValue =
        typeof valueGetter === "function"
          ? valueGetter()
          : field.input.type === "checkbox"
            ? field.input.checked
            : field.input.value;

      const fieldRules = [];
      if (field.required) {
        fieldRules.push({
          type: field.input.type === "checkbox" ? "checked" : "required",
          message: field.requiredMessage || "Este campo es obligatorio.",
        });
      }
      if (Array.isArray(field.rules)) {
        fieldRules.push.apply(fieldRules, field.rules);
      }
      if (typeof field.validator === "function") {
        fieldRules.push({ validator: field.validator });
      }

      const result = validateField(field.name, currentValue, fieldRules, {
        collectAllErrors: field.collectAllErrors,
      });
      setFieldValidity(field.input, result.error, field.feedback);
    });
  }

  root.rules = rules;
  root.normalizeText = normalizeText;
  root.setFieldValidity = setFieldValidity;
  root.clearFieldValidity = clearFieldValidity;
  root.validateField = validateField;
  root.validateFields = validateFields;
  root.bindLiveValidation = bindLiveValidation;
})();
