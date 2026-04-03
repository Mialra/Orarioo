(function () {
    const logoutButton = document.getElementById("logout-button");

    async function ensureAuthenticated() {
        const tokens = window.orariooAuth.getTokens();
        if (!tokens.access && !tokens.refresh) {
            window.location.replace("/sign-in/");
            return;
        }

        try {
            const response = await window.orariooAuth.apiFetch("/api/users/me/", {
                method: "GET",
                headers: {
                    "Content-Type": "application/json",
                },
            });

            if (!response.ok) {
                window.orariooAuth.clearAuthSession();
                window.location.replace("/sign-in/");
            }
        } catch (error) {
            window.orariooAuth.clearAuthSession();
            window.location.replace("/sign-in/");
        }
    }

    async function logout() {
        const tokens = window.orariooAuth.getTokens();

        try {
            if (tokens.refresh) {
                await window.orariooAuth.apiFetch("/api/users/logout/", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({ refresh: tokens.refresh }),
                });
            }
        } catch (error) {
            // Ignore server errors on logout, local session cleanup is still required.
        } finally {
            window.orariooAuth.clearAuthSession();
            window.location.replace("/sign-in/");
        }
    }

    logoutButton.addEventListener("click", logout);
    ensureAuthenticated();
})();
