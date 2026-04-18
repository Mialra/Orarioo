(function () {
    const root = window.OrariooAdmin = window.OrariooAdmin || {};
    const validators = window.OrariooValidators || {};
    const errorHandler = window.OrariooErrorHandler || {};

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

    function clearFieldError(input, feedback) {
        setFieldError(input, feedback, "");
    }

    function clearErrors(fields) {
        (fields || []).forEach(function (field) {
            clearFieldError(field.input, field.feedback);
        });
    }

    function validateFields(fields, payload) {
        if (validators && typeof validators.validateFields === "function") {
            return validators.validateFields(fields, payload);
        }

        clearErrors(fields);
        return true;
    }

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

    function weeklyHours(getInput) {
        return {
            validator: function () {
                const input = getInput();
                const raw = input.value.trim();
                if (!raw) {
                    return window.OrariooErrorHandler.translateEntry({ code: "REQUIRED_FIELD" });
                }
                if (!window.OrariooValidators.rules.positiveInteger(raw)) {
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
