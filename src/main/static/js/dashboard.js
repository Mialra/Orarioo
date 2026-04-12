(function () {
    const logoutButton = document.getElementById("logout-button");
    const avatar = document.getElementById("dashboard-user-initials");
    const currentTeamName = document.getElementById("dashboard-current-team-name");
    const teamSwitchList = document.getElementById("dashboard-team-switch-list");
    const createTeamButton = document.getElementById("dashboard-create-team");
    const inviteTeamMemberButton = document.getElementById("dashboard-invite-team-member");
    const viewPendingInvitationsButton = document.getElementById("dashboard-view-pending-invitations");
    const pendingInvitationsBadge = document.getElementById("dashboard-pending-invitations-badge");
    const leaveTeamButton = document.getElementById("dashboard-leave-team");

    const createTeamModalElement = document.getElementById("dashboardCreateTeamModal");
    const inviteTeamModalElement = document.getElementById("dashboardInviteTeamModal");
    const invitationsModalElement = document.getElementById("dashboardInvitationsModal");

    const createTeamInput = document.getElementById("dashboard-new-team-name");
    const createTeamSubmit = document.getElementById("dashboard-create-team-submit");
    const createTeamError = document.getElementById("dashboard-create-team-error");

    const inviteEmailInput = document.getElementById("dashboard-invite-email");
    const inviteSubmit = document.getElementById("dashboard-invite-team-submit");
    const inviteError = document.getElementById("dashboard-invite-team-error");
    const errorHandler = window.OrariooErrorHandler || {};

    const invitationsEmpty = document.getElementById("dashboard-invitations-empty");
    const invitationsList = document.getElementById("dashboard-invitations-list");

    let profileUserData = null;
    let invitationsCache = [];

    const createTeamModal =
        createTeamModalElement && window.bootstrap
            ? new window.bootstrap.Modal(createTeamModalElement)
            : null;
    const inviteTeamModal =
        inviteTeamModalElement && window.bootstrap
            ? new window.bootstrap.Modal(inviteTeamModalElement)
            : null;
    const invitationsModal =
        invitationsModalElement && window.bootstrap
            ? new window.bootstrap.Modal(invitationsModalElement)
            : null;

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

    function renderTeamMenu(userData) {
        if (!teamSwitchList || !currentTeamName) {
            return;
        }

        const teams = (userData && userData.collaboration_teams) || [];
        const activeTeamId = userData && userData.active_team ? String(userData.active_team.id) : "";

        currentTeamName.textContent = userData && userData.active_team
            ? userData.active_team.name
            : "Sin equipo activo";

        teamSwitchList.innerHTML = "";

        if (!teams.length) {
            const emptyState = document.createElement("div");
            emptyState.className = "small text-secondary";
            emptyState.textContent = "Sin equipos disponibles";
            teamSwitchList.appendChild(emptyState);
            if (inviteTeamMemberButton) {
                inviteTeamMemberButton.disabled = true;
            }
            if (leaveTeamButton) {
                leaveTeamButton.disabled = true;
            }
            return;
        }

        teams.forEach(function (team) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "dash-team-switch-item";
            button.textContent = team.name;
            if (String(team.id) === activeTeamId) {
                button.classList.add("is-active");
            }
            button.addEventListener("click", function () {
                setActiveTeam(team.id)
                    .catch(function (error) {
                        window.alert(error.message || "No se pudo cambiar el equipo activo.");
                    });
            });
            teamSwitchList.appendChild(button);
        });

        if (inviteTeamMemberButton) {
            inviteTeamMemberButton.disabled = !teams.length;
        }
        if (leaveTeamButton) {
            leaveTeamButton.disabled = !teams.length;
        }
    }

    function normalizeApiMessage(payload, fallbackMessage) {
        if (errorHandler && typeof errorHandler.parseApiError === "function") {
            return errorHandler.parseApiError(payload, {
                fallbackMessage: fallbackMessage,
            }).message;
        }

        return fallbackMessage;
    }

    function buildHandledError(payload, fallbackMessage) {
        const message = normalizeApiMessage(payload, fallbackMessage);
        const error = new Error(message);
        error.payload = payload || null;
        return error;
    }

    async function createCollaborationTeam(teamName) {
        const response = await window.orariooAuth.apiFetch("/api/collaboration-teams/create/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ name: teamName }),
        });

        const payload = await response.json().catch(function () {
            return null;
        });

        if (!response.ok) {
            throw buildHandledError(payload, "No se pudo crear el equipo.");
        }

        window.orariooAuth.setAuthSession(payload);
        return payload;
    }

    async function inviteMemberByEmail(email, teamId) {
        const requestData = { email: email };
        if (teamId) {
            requestData.team_id = Number(teamId);
        }

        const response = await window.orariooAuth.apiFetch("/api/collaboration-teams/invite/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(requestData),
        });

        const payload = await response.json().catch(function () {
            return null;
        });

        if (!response.ok) {
            throw buildHandledError(payload, "No se pudo invitar al usuario.");
        }

        return payload;
    }

    async function fetchInvitations() {
        const response = await window.orariooAuth.apiFetch("/api/collaboration-teams/invitations/", {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
            },
        });
        const payload = await response.json().catch(function () {
            return null;
        });
        if (!response.ok) {
            throw buildHandledError(payload, "No se pudieron cargar las invitaciones.");
        }
        invitationsCache = payload && payload.results ? payload.results : [];
        renderInvitationCount(payload && typeof payload.pending_count === "number" ? payload.pending_count : 0);
        return invitationsCache;
    }

    async function respondInvitation(invitationId, action) {
        const response = await window.orariooAuth.apiFetch(
            "/api/collaboration-teams/invitations/" + String(invitationId) + "/respond/",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ action: action }),
            }
        );
        const payload = await response.json().catch(function () {
            return null;
        });
        if (!response.ok) {
            throw buildHandledError(payload, "No se pudo responder la invitacion.");
        }
        return payload;
    }

    async function leaveCurrentTeam() {
        const activeTeamId = profileUserData && profileUserData.active_team ? profileUserData.active_team.id : null;
        if (!activeTeamId) {
            return;
        }

        const response = await window.orariooAuth.apiFetch("/api/collaboration-teams/leave/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ team_id: activeTeamId }),
        });
        const payload = await response.json().catch(function () {
            return null;
        });
        if (!response.ok) {
            throw buildHandledError(payload, "No se pudo salir del equipo.");
        }
        window.orariooAuth.setAuthSession(payload);
        window.location.reload();
    }

    function renderInvitationCount(pendingCount) {
        if (!pendingInvitationsBadge) {
            return;
        }
        pendingInvitationsBadge.textContent = String(pendingCount);
        pendingInvitationsBadge.classList.toggle("text-bg-secondary", pendingCount === 0);
        pendingInvitationsBadge.classList.toggle("text-bg-primary", pendingCount > 0);
    }

    function renderInvitationsList(items) {
        if (!invitationsList || !invitationsEmpty) {
            return;
        }

        invitationsList.innerHTML = "";
        const pendingItems = items.filter(function (item) {
            return item.status === "pending";
        });

        invitationsEmpty.classList.toggle("d-none", pendingItems.length > 0);

        pendingItems.forEach(function (item) {
            const row = document.createElement("div");
            row.className = "dash-invitation-row";

            const title = document.createElement("div");
            title.className = "fw-semibold";
            title.textContent = item.team.name;

            const meta = document.createElement("div");
            meta.className = "small text-secondary mb-2";
            meta.textContent = "Invita " + (item.invited_by_name || item.invited_by_email || "Usuario");

            const actions = document.createElement("div");
            actions.className = "d-flex gap-2";

            const acceptButton = document.createElement("button");
            acceptButton.type = "button";
            acceptButton.className = "btn btn-sm btn-primary";
            acceptButton.textContent = "Aceptar";

            const rejectButton = document.createElement("button");
            rejectButton.type = "button";
            rejectButton.className = "btn btn-sm btn-outline-secondary";
            rejectButton.textContent = "Rechazar";

            acceptButton.addEventListener("click", function () {
                acceptButton.disabled = true;
                rejectButton.disabled = true;
                respondInvitation(item.id, "accept")
                    .then(function () {
                        return Promise.all([refreshProfileData(), fetchInvitations()]);
                    })
                    .then(function (results) {
                        renderInvitationsList(results[1]);
                    })
                    .catch(function (error) {
                        window.alert(error.message || "No se pudo aceptar la invitacion.");
                    });
            });

            rejectButton.addEventListener("click", function () {
                acceptButton.disabled = true;
                rejectButton.disabled = true;
                respondInvitation(item.id, "reject")
                    .then(function () {
                        return fetchInvitations();
                    })
                    .then(function (itemsAfterReject) {
                        renderInvitationsList(itemsAfterReject);
                    })
                    .catch(function (error) {
                        window.alert(error.message || "No se pudo rechazar la invitacion.");
                    });
            });

            actions.appendChild(acceptButton);
            actions.appendChild(rejectButton);

            row.appendChild(title);
            row.appendChild(meta);
            row.appendChild(actions);
            invitationsList.appendChild(row);
        });
    }

    async function setActiveTeam(teamId) {
        if (!teamId) {
            return;
        }

        const response = await window.orariooAuth.apiFetch("/api/set-active-team/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ team_id: Number(teamId) }),
        });

        const payload = await response.json().catch(function () {
            return null;
        });

        if (!response.ok) {
            throw buildHandledError(payload, "No se pudo cambiar el equipo activo.");
        }

        window.orariooAuth.setAuthSession(payload);
        window.location.reload();
    }

    async function refreshProfileData() {
        const response = await window.orariooAuth.apiFetch("/api/users/me/", {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
            },
        });

        if (!response.ok) {
            throw new Error("No se pudo cargar el perfil.");
        }

        profileUserData = await response.json();
        window.orariooAuth.setAuthSession({ user: profileUserData });
        if (avatar) {
            avatar.textContent = getInitials(profileUserData);
        }
        renderTeamMenu(profileUserData);
        return profileUserData;
    }

    async function ensureAuthenticated() {
        const tokens = window.orariooAuth.getTokens();
        if (!tokens.access && !tokens.refresh) {
            window.location.replace("/sign-in/");
            return;
        }

        let userData = null;
        try {
            userData = await refreshProfileData();
        } catch (error) {
            window.orariooAuth.clearAuthSession();
            window.location.replace("/sign-in/");
            return;
        }

        const teams = (userData && userData.collaboration_teams) || [];
        if (!teams.length) {
            try {
                window.alert("No tenias equipo de colaboracion. Se creara uno para que puedas trabajar.");
                const baseName = (userData && userData.given_name) || "Mi";
                await createCollaborationTeam("Equipo de " + baseName);
                window.location.reload();
                return;
            } catch (error) {
                // Keep session alive and let user retry from profile menu.
                console.warn("Auto-create team failed:", error);
            }
        }

        try {
            await fetchInvitations();
        } catch (error) {
            // Invitation loading is secondary and must not trigger forced logout.
            renderInvitationCount(0);
            console.warn("Invitations could not be loaded:", error);
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

    if (createTeamButton) {
        createTeamButton.addEventListener("click", function () {
            if (createTeamError) {
                createTeamError.classList.add("d-none");
                createTeamError.textContent = "";
            }
            if (createTeamInput) {
                createTeamInput.value = "";
            }
            if (createTeamModal) {
                createTeamModal.show();
            }
        });
    }

    if (createTeamSubmit) {
        createTeamSubmit.addEventListener("click", function () {
            const teamName = createTeamInput ? createTeamInput.value.trim() : "";
            if (!teamName) {
                if (createTeamError) {
                    createTeamError.textContent = "Debes indicar un nombre de equipo.";
                    createTeamError.classList.remove("d-none");
                }
                return;
            }

            createTeamSubmit.disabled = true;
            createCollaborationTeam(teamName)
                .then(function () {
                    window.location.reload();
                })
                .catch(function (error) {
                    if (createTeamError) {
                        createTeamError.textContent = error.message || "No se pudo crear el equipo.";
                        createTeamError.classList.remove("d-none");
                    }
                })
                .finally(function () {
                    createTeamSubmit.disabled = false;
                });
        });
    }

    if (inviteTeamMemberButton) {
        inviteTeamMemberButton.addEventListener("click", function () {
            if (inviteError) {
                inviteError.classList.add("d-none");
                inviteError.textContent = "";
            }
            if (inviteEmailInput) {
                inviteEmailInput.value = "";
            }
            if (inviteTeamModal) {
                inviteTeamModal.show();
            }
        });
    }

    if (inviteSubmit) {
        inviteSubmit.addEventListener("click", function () {
            const email = inviteEmailInput ? inviteEmailInput.value.trim() : "";
            if (!email) {
                if (inviteError) {
                    inviteError.textContent = "Debes indicar un email.";
                    inviteError.classList.remove("d-none");
                }
                return;
            }

            const activeTeamId = profileUserData && profileUserData.active_team
                ? profileUserData.active_team.id
                : null;

            inviteSubmit.disabled = true;
            inviteMemberByEmail(email, activeTeamId)
                .then(function () {
                    if (inviteTeamModal) {
                        inviteTeamModal.hide();
                    }
                })
                .catch(function (error) {
                    if (inviteError) {
                        inviteError.textContent = error.message || "No se pudo invitar al usuario.";
                        inviteError.classList.remove("d-none");
                    }
                })
                .finally(function () {
                    inviteSubmit.disabled = false;
                });
        });
    }

    if (viewPendingInvitationsButton) {
        viewPendingInvitationsButton.addEventListener("click", function () {
            fetchInvitations()
                .then(function (items) {
                    renderInvitationsList(items);
                    if (invitationsModal) {
                        invitationsModal.show();
                    }
                })
                .catch(function (error) {
                    window.alert(error.message || "No se pudieron cargar las invitaciones.");
                });
        });
    }

    if (leaveTeamButton) {
        leaveTeamButton.addEventListener("click", function () {
            if (!window.confirm("¿Seguro que quieres salir del equipo actual?")) {
                return;
            }

            leaveTeamButton.disabled = true;
            leaveCurrentTeam()
                .catch(function (error) {
                    window.alert(error.message || "No se pudo salir del equipo.");
                })
                .finally(function () {
                    leaveTeamButton.disabled = false;
                });
        });
    }

    ensureAuthenticated();
})();
