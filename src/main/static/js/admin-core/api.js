/**
 * Authenticated HTTP client for admin API requests with structured response objects.
 */
(function () {
    const root = window.OrariooAdmin = window.OrariooAdmin || {};
    const errorHandler = window.OrariooErrorHandler || {};

    /**
     * Safely parses a response as JSON without throwing.
     * Input: response - Fetch Response object
     * Output: parsed JSON object, or null if parsing fails
     */
    async function safeJson(response) {
        try {
            return await response.json();
        } catch (error) {
            return null;
        }
    }

    /**
     * Sends an authenticated HTTP request and returns a structured result.
     * Input: url - endpoint path string
     *        options - object with method, headers, and optional data payload
     * Output: object with ok, status, data, and errorInfo fields
     */
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

    /**
     * Extracts a flat array of items from a paginated or plain list response.
     * Input: data - API response body (array or paginated object with results)
     * Output: array of items
     */
    function parseList(data) {
        if (Array.isArray(data)) {
            return data;
        }
        return data && Array.isArray(data.results) ? data.results : [];
    }

    root.api = {
        request: request,
        get: function (url) { return request(url, { method: "GET" }); },
        post: function (url, data) { return request(url, { method: "POST", data: data }); },
        patch: function (url, data) { return request(url, { method: "PATCH", data: data }); },
        del: function (url) { return request(url, { method: "DELETE" }); },
        parseList: parseList,
    };
})();
