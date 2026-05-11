/**
 * Form validation helpers and field-level validator factories for admin CRUD forms.
 */
(function () {
    const root = window.OrariooAdmin = window.OrariooAdmin || {};
    const validators = window.OrariooValidators || {};
    const errorHandler = window.OrariooErrorHandler || {};

    /**
     * Sets or clears the invalid state and feedback text for a form field.
     * Input: input - form input DOM element
     *        feedback - feedback DOM element for error text
     *        message - error string; empty string clears the error
     */
    function setFieldError(input, feedback, message) {
        if (validators && typeof validators.setFieldValidity === "function") {
            validators.setFieldValidity(input, message, feedback);
            return;
        }

        if (!input) {
            return;
        }

        const hasError = Boolean(message);
        input.classList.toggle("is-invalid", hasError);
        if (feedback) {
            feedback.textContent = message || "";
        }
    }

    /**
     * Clears the invalid state for a form field.
     * Input: input - form input DOM element
     *        feedback - feedback DOM element to clear
     */
    function clearFieldError(input, feedback) {
        setFieldError(input, feedback, "");
    }

    /**
     * Clears validation errors for an array of field descriptors.
     * Input: fields - array of objects with input and feedback properties
     */
    function clearErrors(fields) {
        (fields || []).forEach(function (field) {
            clearFieldError(field.input, field.feedback);
        });
    }

    /**
     * Validates an array of fields against a payload and sets error states.
     * Input: fields - array of field descriptors with rules and validator functions
     *        payload - object mapping field names to their current values
     * Output: boolean true if all fields are valid
     */
    function validateFields(fields, payload) {
        if (validators && typeof validators.validateFields === "function") {
            return validators.validateFields(fields, payload);
        }

        clearErrors(fields);
        return true;
    }

    /**
     * Applies server-side validation errors to form fields.
     * Input: fields - array of field descriptors with input and feedback elements
     *        responseData - API error response object
     */
    function applyServerErrors(fields, responseData) {
        if (!responseData || typeof responseData !== "object") {
            return;
        }

        if (errorHandler && typeof errorHandler.applyFormErrors === "function") {
            errorHandler.applyFormErrors(fields, responseData);
            return;
        }

        (fields || []).forEach(function (field) {
            const rawError = responseData[field.name];
            const message = Array.isArray(rawError) ? rawError[0] : rawError;
            if (message) {
                setFieldError(field.input, field.feedback, message);
            }
        });
    }

    /**
     * Returns a validator rule that checks a text input is non-empty and within max length.
     * Input: getInput - function returning the input DOM element
     *        getMaxLength - function or value for the maximum character count
     * Output: validator rule object
     */
    function requiredString(getInput, getMaxLength) {
        return {
            validator: function () {
                const input = getInput();
                if (!input.value.trim()) {
                    return window.OrariooErrorHandler.translateEntry({ code: "REQUIRED_FIELD" });
                }
                const limit = typeof getMaxLength === "function" ? getMaxLength() : getMaxLength;
                if (limit && input.value.length > limit) {
                    return "Este campo no puede tener más de " + limit + " caracteres.";
                }
                return "";
            },
        };
    }

    /**
     * Returns a validator rule that checks a select input has a non-empty value.
     * Input: getInput - function returning the select DOM element
     * Output: validator rule object
     */
    function requiredSelect(getInput) {
        return {
            validator: function () {
                const input = getInput();
                if (!input || !input.value.trim()) {
                    return window.OrariooErrorHandler.translateEntry({ code: "REQUIRED_FIELD" });
                }
                return "";
            },
        };
    }

    /**
     * Returns a validator rule that checks an input holds a positive integer.
     * Input: getInput - function returning the input DOM element
     * Output: validator rule object
     */
    function requiredPositiveInt(getInput) {
        return {
            validator: function () {
                const input = getInput();
                const value = input ? input.value.trim() : "";
                if (!value || !window.OrariooValidators.rules.positiveInteger(value)) {
                    return window.OrariooErrorHandler.translateEntry({ code: "REQUIRED_FIELD" });
                }
                return "";
            },
        };
    }

    /**
     * Returns a validator rule that checks a weekly-hours input is a non-negative integer below 168.
     * Accepts 0 to allow expressing load in minutes only (e.g. 0 h 30 min); the server
     * rejects a combined total of 0 h 0 min with ZERO_WEEKLY_LOAD.
     * Input: getInput - function returning the input DOM element
     * Output: validator rule object
     */
    function weeklyHours(getInput) {
        return {
            validator: function () {
                const input = getInput();
                const raw = input.value.trim();
                if (!raw) {
                    return window.OrariooErrorHandler.translateEntry({ code: "REQUIRED_FIELD" });
                }
                if (!window.OrariooValidators.rules.nonNegativeInteger(raw)) {
                    return window.OrariooErrorHandler.translateEntry({ code: "INVALID_INTEGER" });
                }
                if (Number(raw) >= 168) {
                    return window.OrariooErrorHandler.translateEntry({ code: "WEEKLY_HOURS_EXCEEDS_LIMIT" });
                }
                return "";
            },
        };
    }

    root.formUtils = {
        setFieldError: setFieldError,
        clearFieldError: clearFieldError,
        clearErrors: clearErrors,
        validateFields: validateFields,
        applyServerErrors: applyServerErrors,
        validators: {
            requiredString: requiredString,
            requiredSelect: requiredSelect,
            requiredPositiveInt: requiredPositiveInt,
            weeklyHours: weeklyHours,
        },
    };
})();
