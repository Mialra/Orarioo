/**
 * Audit log page: filterable, paginated change-history table with date-range picker and CSV/PDF export.
 */
(function () {
    const filtersForm = document.getElementById("audit-filters-form");
    const entityFilter = document.getElementById("audit-filter-entity");
    const actionFilter = document.getElementById("audit-filter-action");
    const userFilter = document.getElementById("audit-filter-user");
    const dateRangeFilter = document.getElementById("audit-filter-date-range");
    const datePresetButtons = Array.from(
        document.querySelectorAll("[data-audit-range-preset]")
    );
    const resetFiltersButton = document.getElementById("audit-reset-filters");
    const tableBody = document.getElementById("audit-table-body");
    const errorNode = document.getElementById("audit-error");
    const paginationNode = document.getElementById("audit-pagination");
    const detailModalElement = document.getElementById("auditDetailModal");
    const detailSubtitle = document.getElementById("auditDetailModalSubtitle");
    const detailBody = document.getElementById("auditDetailModalBody");

    if (!filtersForm || !tableBody) {
        return;
    }

    const state = {
        page: 1,
        count: 0,
        pageSize: 10,
        currentResults: [],
        dateFrom: "",
        dateTo: "",
        datePickerInstance: null,
        dateAbsoluteMin: null,
        dateAbsoluteMax: null,
    };

    const detailModal =
        detailModalElement && window.bootstrap
            ? new window.bootstrap.Modal(detailModalElement)
            : null;

    /**
     * Shows or hides the page-level error banner with the given message.
     * Input: message - error string; empty string clears the banner
     */
    function setError(message) {
        if (!errorNode) {
            return;
        }

        if (!message) {
            errorNode.classList.add("d-none");
            errorNode.textContent = "";
            return;
        }

        errorNode.textContent = message;
        errorNode.classList.remove("d-none");
    }

    /**
     * Replaces the table body with a single full-width loading/message row.
     * Input: message - text to display in the placeholder row
     */
    function setLoading(message) {
        tableBody.innerHTML = "";
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 6;
        cell.className = "text-center text-secondary py-4";
        cell.textContent = message;
        row.appendChild(cell);
        tableBody.appendChild(row);
    }

    /**
     * Formats an ISO date string as a localised es-ES date-time string.
     * Input: value - ISO date string or null/undefined
     * Output: formatted date string, or "-" for empty/invalid input
     */
    function toDisplayDate(value) {
        if (!value) {
            return "-";
        }

        const parsed = new Date(value);
        if (Number.isNaN(parsed.getTime())) {
            return value;
        }

        return parsed.toLocaleString("es-ES", {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    }

    function normalizeToken(value) {
        return String(value || "")
            .toLowerCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .trim();
    }

    function isTeamFieldName(rawField) {
        const field = normalizeToken(rawField);
        return (
            field === "team" ||
            field === "equipo" ||
            field === "active_team" ||
            field === "collaboration_team"
        );
    }

    function localizeDisplayToken(rawValue) {
        const value = normalizeToken(rawValue);
        if (value === "secondary") {
            return "Secundaria";
        }
        if (value === "primary") {
            return "Primaria";
        }
        if (value === "preschool") {
            return "Infantil";
        }
        return String(rawValue || "");
    }

    /**
     * Converts an audit field value (scalar, array, or object) to a human-readable string.
     * Input: value - any audit field value
     * Output: display string, or "-" for null/empty values
     */
    function formatAuditValue(value) {
        if (Array.isArray(value)) {
            return value.length
                ? value.map(function (item) {
                    return formatAuditValue(item);
                }).join(", ")
                : "-";
        }

        if (value && typeof value === "object") {
            const entries = Object.entries(value).filter(function (entry) {
                return !isTeamFieldName(entry[0]);
            });

            if (!entries.length) {
                return "-";
            }

            if (
                entries.every(function (entry) {
                    return /^[A-Z]{3}_\d{2}:\d{2}$/.test(entry[0]);
                })
            ) {
                const dayNames = {
                    MON: "Lunes",
                    TUE: "Martes",
                    WED: "Miércoles",
                    THU: "Jueves",
                    FRI: "Viernes",
                };
                const stateNames = {
                    AVAILABLE: "disponible",
                    UNAVAILABLE: "no disponible",
                    PREFER_YES: "preferida",
                    PREFER_NO: "poco preferida",
                };

                return entries
                    .sort(function (left, right) {
                        return left[0].localeCompare(right[0], "es");
                    })
                    .map(function (entry) {
                        const parts = entry[0].split("_");
                        const dayCode = parts[0];
                        const hour = parts[1];
                        const stateValue = entry[1];
                        return (
                            (dayNames[dayCode] || dayCode) +
                            " a las " +
                            hour +
                            ": " +
                            (stateNames[stateValue] || stateValue)
                        );
                    })
                    .join("; ");
            }

            return entries
                .map(function (entry) {
                    return entry[0] + ": " + formatAuditValue(entry[1]);
                })
                .join("; ");
        }

        if (value === null || typeof value === "undefined" || value === "") {
            return "-";
        }

        return localizeDisplayToken(value);
    }

    /**
     * Formats a single audit change object into a field name and descriptive text pair.
     * Input: change - object with campo, valor_anterior, and/or valor_nuevo
     * Output: object with field and text string properties
     */
    function formatAuditChangeLine(change) {
        const field = change.campo || "Campo";
        const previousValue = formatAuditValue(change.valor_anterior);
        const newValue = formatAuditValue(change.valor_nuevo);

        if (
            Object.prototype.hasOwnProperty.call(change, "valor_anterior") &&
            Object.prototype.hasOwnProperty.call(change, "valor_nuevo")
        ) {
            return {
                field: field,
                text: "cambio de " + previousValue + " a " + newValue + ".",
            };
        }

        if (Object.prototype.hasOwnProperty.call(change, "valor_nuevo")) {
            return {
                field: field,
                text: newValue + ".",
            };
        }

        return {
            field: field,
            text: previousValue + ".",
        };
    }

    /**
     * Filters team-related changes and formats the remaining entries into display line objects.
     * Input: changes - array of change objects with campo, valor_anterior, valor_nuevo
     * Output: array of { field, text } objects, or "-" if no displayable changes
     */
    function formatAuditChanges(changes) {
        if (!Array.isArray(changes) || !changes.length) {
            return "-";
        }

        const normalizedChanges = changes
            .filter(function (change) {
                return !isTeamFieldName(change && change.campo);
            })
            .map(function (change) {
                return formatAuditChangeLine(change);
            });

        return normalizedChanges.length ? normalizedChanges : "-";
    }

    function formatDetailTextForDisplay(detail) {
        const text = String(detail || "").trim();
        if (!text) {
            return "-";
        }

        const withoutTeam = text
            .replace(/\s*Team:\s*[^.]+\.?/gi, "")
            .replace(/\s{2,}/g, " ")
            .trim();

        if (!withoutTeam) {
            return "-";
        }

        // Normalize UPDATE details to the pattern:
        // "Se modificó ..." + newline + "Campos modificados: ..."
        const hasModificationIntro = /Se modific[oó]/i.test(withoutTeam);
        if (hasModificationIntro) {
            const introMatch = withoutTeam.match(/Se modific[oó] [^.]+\./i);
            const introSentence = introMatch ? introMatch[0].trim() : "";

            const collectedFields = [];

            const updatedFieldRegex = /Se actualiz[oó] el campo\s+([^.]+)\./gi;
            let updatedFieldMatch = updatedFieldRegex.exec(withoutTeam);
            while (updatedFieldMatch) {
                const rawField = String(updatedFieldMatch[1] || "").trim();
                if (rawField) {
                    collectedFields.push(rawField);
                }
                updatedFieldMatch = updatedFieldRegex.exec(withoutTeam);
            }

            const camposRegex = /Campos modificados:\s*([^.]*)\.?/i;
            const camposMatch = withoutTeam.match(camposRegex);
            if (camposMatch && camposMatch[1]) {
                camposMatch[1]
                    .split(",")
                    .map(function (field) {
                        return field.trim();
                    })
                    .filter(Boolean)
                    .forEach(function (field) {
                        collectedFields.push(field);
                    });
            }

            const uniqueFields = Array.from(new Set(collectedFields));
            if (introSentence && uniqueFields.length) {
                return (
                    introSentence +
                    "\nCampos modificados: " +
                    uniqueFields.join(", ") +
                    "."
                );
            }
        }

        return withoutTeam
            .replace(/\.\s*(Campos modificados:)/i, ".\n$1")
            .replace(/\s+(Campos modificados:)/i, "\n$1");
    }

    /**
     * Opens the audit detail modal for the entry at the given index in currentResults.
     * Input: index - numeric index into state.currentResults
     */
    function openAuditDetailModal(index) {
        const entry = state.currentResults[index];
        if (!entry || !detailModal || !detailBody || !detailSubtitle) {
            return;
        }

        detailSubtitle.textContent =
            (entry.tipo_entidad || "Entidad") +
            " · " +
            (entry.tipo_accion || "-");

        const changeLines = formatAuditChanges(entry.cambios);
        if (changeLines === "-") {
            detailBody.innerHTML = "<p>No hay detalle adicional disponible.</p>";
        } else {
            detailBody.innerHTML =
                '<ul class="audit-detail-list">' +
                changeLines
                    .map(function (line) {
                        return (
                            "<li><strong>" +
                            window.OrariooErrorHandler.escapeHtml(line.field) +
                            ":</strong> " +
                            window.OrariooErrorHandler.escapeHtml(line.text) +
                            "</li>"
                        );
                    })
                    .join("") +
                "</ul>";
        }

        detailModal.show();
    }

    /**
     * Returns the CSS class string for an audit action badge based on the action type.
     * Input: action - action type string (e.g. "creacion", "modificacion", "borrado")
     * Output: CSS class string
     */
    function getActionBadgeClass(action) {
        const normalized = normalizeToken(action);

        if (normalized === "creacion" || normalized === "create") {
            return "audit-action-badge audit-action-create";
        }

        if (normalized === "modificacion" || normalized === "update") {
            return "audit-action-badge audit-action-update";
        }

        if (
            normalized === "borrado" ||
            normalized === "delete" ||
            normalized === "eliminacion"
        ) {
            return "audit-action-badge audit-action-delete";
        }

        return "audit-action-badge";
    }

    function updatePagination() {
        if (!paginationNode) {
            return;
        }

        paginationNode.innerHTML = "";
        if (!state.count) {
            return;
        }

        const totalPages = Math.max(
            1,
            Math.ceil(state.count / Math.max(1, state.pageSize || 1))
        );
        if (totalPages <= 1) {
            return;
        }

        const nav = document.createElement("nav");
        nav.setAttribute("aria-label", "Paginación del listado");

        const ul = document.createElement("ul");
        ul.className = "pagination pagination-sm justify-content-center mb-0";

        function createPageButton(label, targetPage, disabled, active) {
            const li = document.createElement("li");
            li.className =
                "page-item" + (disabled ? " disabled" : "") + (active ? " active" : "");

            const button = document.createElement("button");
            button.type = "button";
            button.className = "page-link";
            button.textContent = label;

            if (active) {
                button.setAttribute("aria-current", "page");
            }

            if (disabled) {
                button.setAttribute("tabindex", "-1");
                button.setAttribute("aria-disabled", "true");
            } else {
                button.setAttribute("data-page", String(targetPage));
            }

            li.appendChild(button);
            ul.appendChild(li);
        }

        function createEllipsis() {
            const li = document.createElement("li");
            li.className = "page-item disabled";
            const span = document.createElement("span");
            span.className = "page-link";
            span.textContent = "...";
            span.setAttribute("aria-hidden", "true");
            li.appendChild(span);
            ul.appendChild(li);
        }

        createPageButton("Anterior", state.page - 1, state.page <= 1, false);

        const windowStart = Math.max(1, state.page - 1);
        const windowEnd = Math.min(totalPages, state.page + 1);

        createPageButton("1", 1, false, state.page === 1);

        if (windowStart > 2) {
            createEllipsis();
        }

        for (let index = windowStart; index <= windowEnd; index += 1) {
            if (index === 1 || index === totalPages) {
                continue;
            }
            createPageButton(String(index), index, false, index === state.page);
        }

        if (windowEnd < totalPages - 1) {
            createEllipsis();
        }

        if (totalPages > 1) {
            createPageButton(String(totalPages), totalPages, false, state.page === totalPages);
        }

        createPageButton("Siguiente", state.page + 1, state.page >= totalPages, false);

        nav.appendChild(ul);
        paginationNode.appendChild(nav);
    }

    function renderRows(results) {
        tableBody.innerHTML = "";
        state.currentResults = Array.isArray(results) ? results : [];

        if (!state.currentResults.length) {
            setLoading("No hay actividad para los filtros seleccionados.");
            return;
        }

        state.currentResults.forEach(function (entry, index) {
            const actionLabel = entry.tipo_accion || "-";
            const detailText = formatDetailTextForDisplay(entry.detalle);

            const row = document.createElement("tr");
            row.innerHTML =
                "<td>" +
                window.OrariooErrorHandler.escapeHtml(toDisplayDate(entry.fecha)) +
                "</td>" +
                "<td>" +
                window.OrariooErrorHandler.escapeHtml(entry.usuario || "-") +
                "</td>" +
                "<td>" +
                window.OrariooErrorHandler.escapeHtml(entry.tipo_entidad || "-") +
                "</td>" +
                "<td><span class=\"" +
                getActionBadgeClass(actionLabel) +
                "\">" +
                window.OrariooErrorHandler.escapeHtml(actionLabel) +
                "</span></td>" +
                "<td class=\"audit-cell-detail\">" +
                window.OrariooErrorHandler.escapeHtml(detailText) +
                "</td>" +
                "<td><button type=\"button\" class=\"btn btn-sm btn-outline-secondary audit-detail-button\" data-audit-detail-index=\"" +
                String(index) +
                "\" aria-label=\"Ver detalle\" title=\"Ver detalle\"><i data-lucide=\"info\" class=\"audit-detail-icon\" aria-hidden=\"true\"></i></button></td>";

            tableBody.appendChild(row);
        });

        if (window.lucide && typeof window.lucide.createIcons === "function") {
            window.lucide.createIcons();
        }
    }

    function buildQueryParams(overrides) {
        const params = new URLSearchParams();
        const page = typeof overrides.page === "number" ? overrides.page : state.page;
        const effectiveRange = getEffectiveDateRangeSelection();

        if (entityFilter && entityFilter.value) {
            params.set("tipo_entidad", entityFilter.value);
        }
        if (actionFilter && actionFilter.value) {
            params.set("tipo_accion", actionFilter.value);
        }
        if (userFilter && userFilter.value) {
            params.set("usuario_id", userFilter.value);
        }
        if (effectiveRange.dateFrom) {
            params.set("fecha_desde", toStartOfDayDateTime(effectiveRange.dateFrom));
        }
        if (effectiveRange.dateTo) {
            params.set("fecha_hasta", toEndOfDayDateTime(effectiveRange.dateTo));
        }

        params.set("page", String(page));
        params.set("page_size", "10");

        return params;
    }

    function toIsoDate(dateValue) {
        if (!(dateValue instanceof Date) || Number.isNaN(dateValue.getTime())) {
            return "";
        }

        const year = dateValue.getFullYear();
        const month = String(dateValue.getMonth() + 1).padStart(2, "0");
        const day = String(dateValue.getDate()).padStart(2, "0");
        return year + "-" + month + "-" + day;
    }

    function setDateRangeSelection(startDate, endDate) {
        state.dateFrom = startDate || "";
        state.dateTo = endDate || "";
    }

    function toStartOfDayDateTime(isoDate) {
        return isoDate ? isoDate + "T00:00:00" : "";
    }

    function toEndOfDayDateTime(isoDate) {
        return isoDate ? isoDate + "T23:59:59" : "";
    }

    function getEffectiveDateRangeSelection() {
        if (state.datePickerInstance && Array.isArray(state.datePickerInstance.selectedDates)) {
            const selectedDates = state.datePickerInstance.selectedDates
                .filter(function (dateValue) {
                    return dateValue instanceof Date && !Number.isNaN(dateValue.getTime());
                })
                .slice()
                .sort(function (left, right) {
                    return left.getTime() - right.getTime();
                });

            if (selectedDates.length) {
                const start = toIsoDate(selectedDates[0]);
                const fallbackEnd =
                    state.dateAbsoluteMax instanceof Date
                        ? state.dateAbsoluteMax
                        : withTimeReset(new Date());
                const end = toIsoDate(selectedDates[1] || fallbackEnd);

                return {
                    dateFrom: start,
                    dateTo: end,
                };
            }
        }

        return {
            dateFrom: state.dateFrom || "",
            dateTo: state.dateTo || "",
        };
    }

    function withTimeReset(dateValue) {
        const result = new Date(dateValue);
        result.setHours(0, 0, 0, 0);
        return result;
    }

    function applyPresetRange(preset) {
        if (!state.datePickerInstance || !(state.dateAbsoluteMax instanceof Date)) {
            return;
        }

        const endDate = withTimeReset(state.dateAbsoluteMax);
        let startDate = withTimeReset(state.dateAbsoluteMax);

        if (preset === "last7") {
            startDate.setDate(startDate.getDate() - 6);
        } else if (preset === "last30") {
            startDate.setDate(startDate.getDate() - 29);
        } else if (preset === "month") {
            startDate = new Date(endDate.getFullYear(), endDate.getMonth(), 1);
        }

        if (state.dateAbsoluteMin instanceof Date && startDate < state.dateAbsoluteMin) {
            startDate = withTimeReset(state.dateAbsoluteMin);
        }

        state.datePickerInstance.setDate([startDate, endDate], true);
    }

    function setActivePresetButton(preset) {
        if (!datePresetButtons.length) {
            return;
        }

        datePresetButtons.forEach(function (button) {
            const isActive = button.getAttribute("data-audit-range-preset") === preset;
            button.classList.toggle("is-active", isActive);
            if (isActive) {
                button.setAttribute("aria-pressed", "true");
            } else {
                button.setAttribute("aria-pressed", "false");
            }
        });
    }

    function bindCalendarWheelNavigation(calendarInstance) {
        if (!calendarInstance || !calendarInstance.calendarContainer) {
            return;
        }

        calendarInstance.calendarContainer.addEventListener(
            "wheel",
            function (event) {
                if (event.deltaY === 0) {
                    return;
                }

                event.preventDefault();
                event.stopPropagation();

                if (event.deltaY > 0) {
                    calendarInstance.changeMonth(1);
                } else {
                    calendarInstance.changeMonth(-1);
                }
            },
            { passive: false }
        );
    }

    function initDateRangePicker() {
        if (!dateRangeFilter) {
            return;
        }

        if (window.flatpickr) {
            const today = withTimeReset(new Date());
            const minDate = withTimeReset(new Date(today));
            minDate.setFullYear(minDate.getFullYear() - 10);
            state.dateAbsoluteMin = minDate;
            state.dateAbsoluteMax = today;

            state.datePickerInstance = window.flatpickr(dateRangeFilter, {
                mode: "range",
                dateFormat: "d/m/Y",
                locale: (window.flatpickr.l10ns && window.flatpickr.l10ns.es) || "es",
                minDate: minDate,
                maxDate: today,
                showMonths: 1,
                allowInput: false,
                clickOpens: true,
                disableMobile: true,
                onReady: function (selectedDates, dateStr, instance) {
                    bindCalendarWheelNavigation(instance);
                },
                onChange: function (selectedDates) {
                    if (!Array.isArray(selectedDates) || selectedDates.length === 0) {
                        setActivePresetButton("");
                        if (state.datePickerInstance) {
                            state.datePickerInstance.set("minDate", state.dateAbsoluteMin);
                        }
                        setDateRangeSelection("", "");
                        fetchAuditEntries(1).catch(function (error) {
                            setError(error.message || "No se pudo cargar el registro de cambios.");
                        });
                        return;
                    }

                    if (selectedDates.length === 1 && state.datePickerInstance) {
                        state.datePickerInstance.set("minDate", selectedDates[0]);
                    }

                    const start = toIsoDate(selectedDates[0]);
                    const end = selectedDates[1] ? toIsoDate(selectedDates[1]) : "";
                    setDateRangeSelection(start, end);
                    setActivePresetButton("");

                    if (selectedDates.length === 2 && state.datePickerInstance) {
                        state.datePickerInstance.set("minDate", state.dateAbsoluteMin);
                        fetchAuditEntries(1).catch(function (error) {
                            setError(error.message || "No se pudo cargar el registro de cambios.");
                        });
                    }
                },
                onClose: function (selectedDates) {
                    if (Array.isArray(selectedDates) && selectedDates.length === 1) {
                        setDateRangeSelection(toIsoDate(selectedDates[0]), "");
                        fetchAuditEntries(1).catch(function (error) {
                            setError(error.message || "No se pudo cargar el registro de cambios.");
                        });
                    }
                },
            });
            return;
        }

        // Fallback if flatpickr is unavailable.
        dateRangeFilter.readOnly = false;
        dateRangeFilter.placeholder = "YYYY-MM-DD a YYYY-MM-DD";
        dateRangeFilter.addEventListener("change", function () {
            const rawValue = String(dateRangeFilter.value || "").trim();
            if (!rawValue) {
                setDateRangeSelection("", "");
                return;
            }

            const parts = rawValue.split(/\s+a\s+/i).map(function (value) {
                return value.trim();
            });
            setDateRangeSelection(parts[0] || "", parts[1] || "");
        });
    }

    async function fetchUsers() {
        const response = await window.orariooAuth.apiFetch(
            "/api/audit-entries/filter-users/",
            {
                method: "GET",
            }
        );
        const payload = await response.json().catch(function () {
            return null;
        });

        if (!response.ok) {
            throw new Error(window.OrariooErrorHandler.parseApiError(payload, { fallbackMessage: "No se pudieron cargar los usuarios." }).message);
        }

        if (!userFilter) {
            return;
        }

        userFilter.innerHTML = '<option value="">Todos</option>';
        payload.forEach(function (user) {
            const option = document.createElement("option");
            option.value = String(user.id);
            option.textContent = user.nombre;
            userFilter.appendChild(option);
        });
    }

    async function fetchAuditEntries(page) {
        setError("");
        setLoading("Cargando actividad...");

        const params = buildQueryParams({ page: page });
        const response = await window.orariooAuth.apiFetch(
            "/api/audit-entries/?" + params.toString(),
            {
                method: "GET",
            }
        );
        const payload = await response.json().catch(function () {
            return null;
        });

        if (!response.ok) {
            throw new Error(
                window.OrariooErrorHandler.parseApiError(payload, { fallbackMessage: "No se pudo cargar el registro de cambios." }).message
            );
        }

        state.page = page;
        state.count = payload && typeof payload.count === "number" ? payload.count : 0;
        state.pageSize = 10;

        renderRows(payload && payload.results ? payload.results : []);
        updatePagination();
    }

    async function exportAudit(format, selectedColumns) {
        const params = buildQueryParams({ page: 1 });
        params.set("export_format", format);
        params.delete("page");
        if (Array.isArray(selectedColumns) && selectedColumns.length > 0) {
            selectedColumns.forEach(function (col) {
                params.append("columns", col);
            });
        }

        const response = await window.orariooAuth.apiFetch(
            "/api/audit-entries/export/?" + params.toString(),
            {
                method: "GET",
            }
        );

        if (!response.ok) {
            const payload = await response.json().catch(function () {
                return null;
            });
            throw new Error(
                window.OrariooErrorHandler.parseApiError(payload, { fallbackMessage: "No se pudo exportar el registro de cambios." }).message
            );
        }

        const blob = await response.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        const disposition = response.headers.get("Content-Disposition") || "";
        const matched = /filename="?([^";]+)"?/i.exec(disposition);
        link.href = downloadUrl;
        link.download = matched ? matched[1] : "registro_cambios." + format;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(downloadUrl);
    }

    [entityFilter, actionFilter, userFilter].forEach(function (select) {
        if (select) {
            select.addEventListener("change", function () {
                fetchAuditEntries(1).catch(function (error) {
                    setError(error.message || "No se pudo cargar el registro de cambios.");
                    setLoading("No se pudo cargar la actividad.");
                });
            });
        }
    });

    if (resetFiltersButton) {
        resetFiltersButton.addEventListener("click", function () {
            filtersForm.reset();
            setActivePresetButton("");
            setDateRangeSelection("", "");
            if (state.datePickerInstance) {
                state.datePickerInstance.clear();
                state.datePickerInstance.set("minDate", state.dateAbsoluteMin);
            }
            fetchAuditEntries(1).catch(function (error) {
                setError(error.message || "No se pudo cargar el registro de cambios.");
                setLoading("No se pudo cargar la actividad.");
            });
        });
    }

    if (datePresetButtons.length) {
        datePresetButtons.forEach(function (button) {
            button.addEventListener("click", function () {
                const preset = button.getAttribute("data-audit-range-preset");
                setActivePresetButton(preset || "");
                applyPresetRange(preset);
                fetchAuditEntries(1).catch(function (error) {
                    setError(error.message || "No se pudo aplicar el rango de fechas.");
                });
            });
        });
    }

    if (paginationNode) {
        paginationNode.addEventListener("click", function (event) {
            const button = event.target.closest("button.page-link[data-page]");
            if (!button) {
                return;
            }

            const targetPage = Number(button.getAttribute("data-page"));
            if (
                !Number.isInteger(targetPage) ||
                targetPage < 1 ||
                targetPage === state.page
            ) {
                return;
            }

            fetchAuditEntries(targetPage).catch(function (error) {
                setError(error.message || "No se pudo cambiar de página.");
            });
        });
    }

    (function () {
        const auditExportModalElement = document.getElementById("auditExportModal");
        const auditExportConfirmBtn = document.getElementById("auditExportConfirmBtn");
        const auditExportColCards = auditExportModalElement
            ? Array.from(auditExportModalElement.querySelectorAll("[data-audit-export-col]"))
            : [];

        auditExportColCards.forEach(function (card) {
            card.addEventListener("click", function () {
                const isActive = card.classList.toggle("active");
                card.setAttribute("aria-pressed", isActive ? "true" : "false");
            });
        });

        if (auditExportModalElement) {
            auditExportModalElement.addEventListener("hidden.bs.modal", function () {
                auditExportColCards.forEach(function (card) {
                    card.classList.remove("active");
                    card.setAttribute("aria-pressed", "false");
                });
            });
        }

        if (auditExportConfirmBtn) {
            auditExportConfirmBtn.addEventListener("click", function () {
                const format = document.getElementById("auditExportFormat")
                    ? document.getElementById("auditExportFormat").value
                    : "csv";

                const selectedColumns = auditExportColCards
                    .filter(function (card) { return card.classList.contains("active"); })
                    .map(function (card) { return card.getAttribute("data-audit-export-col"); });

                if (auditExportModalElement && window.bootstrap) {
                    window.bootstrap.Modal.getInstance(auditExportModalElement).hide();
                }

                exportAudit(format, selectedColumns).catch(function (error) {
                    setError(error.message || "No se pudo exportar el registro de cambios.");
                });
            });
        }
    }());

    tableBody.addEventListener("click", function (event) {
        const button = event.target.closest(".audit-detail-button");
        if (!button) {
            return;
        }

        const rawIndex = button.getAttribute("data-audit-detail-index");
        const index = Number(rawIndex);
        if (!Number.isInteger(index) || index < 0) {
            return;
        }

        openAuditDetailModal(index);
    });

    initDateRangePicker();

    Promise.all([fetchUsers(), fetchAuditEntries(1)]).catch(function (error) {
        setError(error.message || "No se pudo inicializar el registro de cambios.");
        setLoading("No se pudo cargar la actividad.");
    });
})();
