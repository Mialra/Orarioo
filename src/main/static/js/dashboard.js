(function () {
    const logoutButton = document.getElementById("logout-button");
    const avatar = document.getElementById("dashboard-user-initials");

    if (window.lucide && typeof window.lucide.createIcons === "function") {
        window.lucide.createIcons();
    }

    function getInitials(userData) {
        const givenName = (userData && userData.given_name) || "";
        const familyName = (userData && userData.family_name) || "";
        const fallback = (userData && userData.email) || "";

        const nameInitial = givenName.trim().charAt(0);
        const familyInitial = familyName.trim().charAt(0);

        if (nameInitial || familyInitial) {
            return (nameInitial + familyInitial).toUpperCase();
        }

        return fallback.trim().charAt(0).toUpperCase() || "US";
    }

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
                return;
            }

            const userData = await response.json();
            if (avatar) {
                avatar.textContent = getInitials(userData);
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
            // Ignore server-side logout errors. Local cleanup is enough.
        } finally {
            window.orariooAuth.clearAuthSession();
            window.location.replace("/sign-in/");
        }
    }

    if (logoutButton) {
        logoutButton.addEventListener("click", logout);
    }

    ensureAuthenticated();
})();
