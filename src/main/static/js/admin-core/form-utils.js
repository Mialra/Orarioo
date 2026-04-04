(function () {
    const root = window.OrariooAdmin = window.OrariooAdmin || {};

    function setFieldError(input, feedback, message) {
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
        clearErrors(fields);
        let isValid = true;

        (fields || []).forEach(function (field) {
            const value = payload[field.name];
            let message = "";

            if (field.required && !value) {
                message = field.requiredMessage || "Campo obligatorio.";
            } else if (field.validator && value) {
                message = field.validator(value) || "";
            }

            if (message) {
                setFieldError(field.input, field.feedback, message);
                isValid = false;
            }
        });

        return isValid;
    }

    function applyServerErrors(fields, responseData) {
        if (!responseData || typeof responseData !== "object") {
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
