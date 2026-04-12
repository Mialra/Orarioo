(function () {
    const root = window.OrariooAdmin = window.OrariooAdmin || {};
    const errorHandler = window.OrariooErrorHandler || {};

    async function safeJson(response) {
        try {
            return await response.json();
        } catch (error) {
            return null;
        }
    }

    async function request(url, options) {
        const config = options || {};
        const method = config.method || "GET";
        const headers = Object.assign({ "Content-Type": "application/json" }, config.headers || {});

        try {
            const response = await window.orariooAuth.apiFetch(url, {
                method: method,
                headers: headers,
                body: config.data ? JSON.stringify(config.data) : undefined,
            });
            const data = await safeJson(response);

            return {
                ok: response.ok,
                status: response.status,
                data: data,
                errorInfo: response.ok || !errorHandler || typeof errorHandler.parseApiError !== "function"
                    ? null
                    : errorHandler.parseApiError(data, {}),
            };
        } catch (error) {
            return {
                ok: false,
                status: 0,
                data: null,
                error: error,
            };
        }
    }

    root.api = {
        request: request,
        get: function (url) { return request(url, { method: "GET" }); },
        post: function (url, data) { return request(url, { method: "POST", data: data }); },
        patch: function (url, data) { return request(url, { method: "PATCH", data: data }); },
        del: function (url) { return request(url, { method: "DELETE" }); },
    };
})();
