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

    root.formUtils = {
        setFieldError: setFieldError,
        clearFieldError: clearFieldError,
        clearErrors: clearErrors,
        validateFields: validateFields,
        applyServerErrors: applyServerErrors,
    };
})();
