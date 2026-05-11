/**
 * Application shell: guards authenticated routes and handles logout on every page.
 */
(function () {
  const logoutButton = document.getElementById("logout-button");

  /**
   * Redirects to sign-in if no valid session exists or the /api/users/me/ check fails.
   */
  async function ensureAuthenticated() {
    const tokens = window.orariooAuth.getTokens();
    if (!tokens.access && !tokens.refresh) {
      window.location.replace("/sign-in/");
      return;
    }
    try {
      await window.orariooAuth.fetchCurrentUser();
    } catch (error) {
      window.orariooAuth.clearAuthSession();
      window.location.replace("/sign-in/");
    }
  }

  /**
   * Calls the logout endpoint, clears the local auth session, and redirects to sign-in.
   */
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
