/**
 * Time-preference grid manager: renders, resets, and serializes slot states for scheduling forms.
 */
(function () {
    const root = window.OrariooAdmin = window.OrariooAdmin || {};

    /**
     * Parses a raw preference value into a slot-state map object.
     * Input: rawValue - JSON string, plain object, or empty/null value
     * Output: object mapping slot keys to preference state strings; empty object on parse failure
     */
    function parsePreferences(rawValue) {
        if (rawValue && typeof rawValue === "object") {
            return rawValue;
        }
        if (!rawValue || !String(rawValue).trim()) {
            return {};
        }
        try {
            return JSON.parse(String(rawValue));
        } catch (e) {
            return {};
        }
    }

    /**
     * Creates a preferences grid manager that renders an interactive day/hour slot grid.
     * Input: config - object with gridContainer, brushInput, timePreferencesInput, and optional defaultBrushState
     * Output: object with render() and reset(preferences) methods
     */
    function createPreferencesManager(config) {
        const constants = root.constants;
        const DAYS = constants.DAYS;
        const HOURS = constants.HOURS;
        const PREFERENCE_STATES = constants.PREFERENCE_STATES;
        const DAY_LABELS = constants.DAY_LABELS;
        const defaultBrushState = config.defaultBrushState || "PREFER_YES";

        const preferenceStateBySlot = {};

        function slotKey(day, hour) {
            return day + "_" + hour;
        }

        function applyStateToCell(cell, state) {
            if (!cell) {
                return;
            }
            PREFERENCE_STATES.forEach(function (s) {
                cell.classList.remove("state-" + s);
                cell.classList.remove("pref-state-" + s);
            });
            cell.classList.add("state-" + state);
            cell.classList.add("pref-state-" + state);
            cell.dataset.state = state;
        }

        function syncInput() {
            if (!config.timePreferencesInput) {
                return;
            }
            const payload = {};
            Object.keys(preferenceStateBySlot).forEach(function (slot) {
                if (preferenceStateBySlot[slot] !== "AVAILABLE") {
                    payload[slot] = preferenceStateBySlot[slot];
                }
            });
            config.timePreferencesInput.value = JSON.stringify(payload);
        }

        function getBrushState() {
            const value = config.brushInput ? config.brushInput.value : defaultBrushState;
            return PREFERENCE_STATES.indexOf(value) >= 0 ? value : defaultBrushState;
        }

        function setSlotState(slot, state) {
            preferenceStateBySlot[slot] = state;
            const cell = config.gridContainer
                ? config.gridContainer.querySelector('[data-slot="' + slot + '"]')
                : null;
            applyStateToCell(cell, state);
            syncInput();
        }

        function reset(preferences) {
            DAYS.forEach(function (day) {
                HOURS.forEach(function (hour) {
                    const key = slotKey(day, hour);
                    const nextState =
                        preferences && PREFERENCE_STATES.indexOf(preferences[key]) >= 0
                            ? preferences[key]
                            : "AVAILABLE";
                    preferenceStateBySlot[key] = nextState;
                    const cell = config.gridContainer
                        ? config.gridContainer.querySelector('[data-slot="' + key + '"]')
                        : null;
                    applyStateToCell(cell, nextState);
                });
            });
            syncInput();
        }

        function render() {
            if (!config.gridContainer) {
                return;
            }

            const headCells = DAYS.map(function (day) {
                return '<div class="pref-grid-header">' + DAY_LABELS[day] + "</div>";
            }).join("");

            const bodyCells = HOURS.map(function (hour) {
                const rowCells = DAYS.map(function (day) {
                    const key = slotKey(day, hour);
                    return (
                        '<button type="button" class="subject-pref-cell pref-cell state-AVAILABLE pref-state-AVAILABLE" data-slot="' +
                        key +
                        '" title="' +
                        DAY_LABELS[day] +
                        " " +
                        hour +
                        '"></button>'
                    );
                }).join("");
                return '<div class="pref-hour">' + hour + "</div>" + rowCells;
            }).join("");

            config.gridContainer.innerHTML =
                '<div class="pref-grid">' +
                '<div class="pref-grid-header pref-hour">Hora</div>' +
                headCells +
                bodyCells +
                "</div>";

            config.gridContainer.addEventListener("click", function (event) {
                const cell = event.target.closest("[data-slot]");
                if (!cell) {
                    return;
                }
                setSlotState(cell.dataset.slot, getBrushState());
            });

            reset({});
        }

        return { render: render, reset: reset };
    }

    root.createPreferencesManager = createPreferencesManager;
    root.parsePreferences = parsePreferences;
})();
