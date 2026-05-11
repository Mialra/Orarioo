/**
 * Global loading overlay that intercepts every authenticated API call via window.orariooAuth.apiFetch.
 * Exposed as window.OrariooSpinner for manual control.
 */
(function () {
    var activeRequests = 0;
    var overlayEl = null;
    var pendingShow = false;

    /**
     * Creates the overlay spinner element and appends it to the document body.
     * Output: the created overlay DOM element
     */
    function createOverlay() {
        var overlay = document.createElement("div");
        overlay.id = "orarioo-global-spinner";
        overlay.setAttribute("aria-hidden", "true");
        overlay.setAttribute("aria-label", "Cargando");

        var wrapper = document.createElement("div");
        wrapper.className = "orarioo-spinner-wrapper";

        var spinner = document.createElement("div");
        spinner.className = "spinner-border text-light";
        spinner.setAttribute("role", "status");

        var sr = document.createElement("span");
        sr.className = "visually-hidden";
        sr.textContent = "Cargando...";

        var label = document.createElement("span");
        label.className = "orarioo-spinner-label";
        label.textContent = "Cargando...";

        spinner.appendChild(sr);
        wrapper.appendChild(spinner);
        wrapper.appendChild(label);
        overlay.appendChild(wrapper);
        document.body.appendChild(overlay);
        return overlay;
    }

    /**
     * Increments the active request counter and shows the overlay when the first request starts.
     * If the overlay element is not yet in the DOM, marks a pending show for onDomReady.
     */
    function show() {
        activeRequests++;
        if (activeRequests === 1) {
            if (!overlayEl) {
                pendingShow = true;
            } else {
                overlayEl.classList.add("active");
            }
        }
    }

    /**
     * Decrements the active request counter and hides the overlay when all requests complete.
     */
    function hide() {
        if (activeRequests > 0) {
            activeRequests--;
        }
        if (activeRequests === 0 && overlayEl) {
            overlayEl.classList.remove("active");
        }
    }

    /**
     * Wraps window.orariooAuth.apiFetch to call show/hide around every authenticated request.
     * Callers can pass { _skipSpinner: true } in fetch options to opt out; the flag is stripped
     * before forwarding to the original fetch so it does not reach the browser Fetch API.
     */
    function installInterceptor() {
        var auth = window.orariooAuth;
        if (!auth || typeof auth.apiFetch !== "function") {
            return;
        }

        var originalFetch = auth.apiFetch.bind(auth);

        auth.apiFetch = async function (url, options) {
            if (options && options._skipSpinner) {
                var opts = Object.assign({}, options);
                delete opts._skipSpinner;
                return originalFetch(url, opts);
            }
            show();
            try {
                return await originalFetch(url, options);
            } finally {
                hide();
            }
        };
    }

    /**
     * Creates the overlay element once the DOM is ready and applies any pending show state.
     */
    function onDomReady() {
        overlayEl = createOverlay();
        if (pendingShow) {
            pendingShow = false;
            overlayEl.classList.add("active");
        }
    }

    installInterceptor();

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", onDomReady);
    } else {
        onDomReady();
    }

    window.OrariooSpinner = { show: show, hide: hide };
})();
