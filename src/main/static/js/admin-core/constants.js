/**
 * Shared admin constants and stage-metadata helpers.
 */
(function () {
    var root = window.OrariooAdmin = window.OrariooAdmin || {};

    /**
     * Returns the default slot-start collection used before loading team config.
     * Output: array of HH:MM strings
     */
    function createDefaultHours() {
        return [
            "08:00", "08:30", "09:00", "09:30",
            "10:00", "10:30", "11:00", "11:30",
            "12:00", "12:30", "13:00", "13:30",
            "14:00", "14:30",
        ];
    }

    /**
     * Returns the built-in fallback labels for the default educational stages.
     * Output: object keyed by stage code
     */
    function createFallbackStageLabels() {
        return {
            PRESCHOOL: "Infantil",
            PRIMARY: "Primaria",
            SECONDARY: "ESO",
            ALEVELS: "Bachillerato",
        };
    }

    /**
     * Returns the built-in fallback colors for the default educational stages.
     * Output: object keyed by stage code
     */
    function createFallbackStageColors() {
        return {
            PRESCHOOL: "green",
            PRIMARY: "blue",
            SECONDARY: "orange",
            ALEVELS: "purple",
        };
    }

    /**
     * Returns the localized labels used for weekday codes.
     * Output: object keyed by day code
     */
    function createDayLabels() {
        return {
            MON: "Lunes",
            TUE: "Martes",
            WED: "Miércoles",
            THU: "Jueves",
            FRI: "Viernes",
        };
    }

    /**
     * Returns true when the provided value is a non-empty plain object.
     * Input: value - any value to validate
     * Output: boolean
     */
    function hasEntries(value) {
        return !!value && typeof value === "object" && Object.keys(value).length > 0;
    }

    /**
     * Resolves any pending callbacks waiting for a metadata map.
     * Input: callbacks - array of callback functions; value - metadata object to emit
     * Output: void; empties the callbacks array
     */
    function flushCallbacks(callbacks, value) {
        callbacks.splice(0).forEach(function (cb) {
            cb(value);
        });
    }

    /**
     * Emits the shared browser event used to notify stage-metadata updates.
     * Output: void
     */
    function dispatchStageMetadataChanged() {
        window.dispatchEvent(new CustomEvent("orarioo:stage-metadata-changed"));
    }

    /**
     * Returns a callback-registration function for a metadata key.
     * Input: stateKey - object key storing the current metadata map
     *        callbacksKey - object key storing the pending callback queue
     * Output: function(cb) that resolves immediately or queues the callback
     */
    function createReadyHandler(stateKey, callbacksKey) {
        return function (cb) {
            if (hasEntries(root.constants[stateKey])) {
                cb(root.constants[stateKey]);
                return;
            }
            root.constants[callbacksKey].push(cb);
        };
    }

    /**
     * Returns a metadata setter that stores the map and notifies listeners.
     * Input: stateKey - object key storing the current metadata map
     *        callbacksKey - object key storing the pending callback queue
     * Output: function(value) that persists metadata when valid
     */
    function createMetadataSetter(stateKey, callbacksKey) {
        return function (value) {
            if (!value || typeof value !== "object") {
                return;
            }
            root.constants[stateKey] = value;
            flushCallbacks(root.constants[callbacksKey], value);
            dispatchStageMetadataChanged();
        };
    }

    /**
     * Returns the current or fallback stage metadata value for a given stage code.
     * Input: primaryMap - latest metadata map from the API
     *        fallbackMap - local fallback metadata map
     *        stageCode - stage identifier to resolve
     *        defaultValue - value returned when stageCode is unknown
     * Output: resolved metadata value
     */
    function resolveStageMetadata(primaryMap, fallbackMap, stageCode, defaultValue) {
        return primaryMap[stageCode] || fallbackMap[stageCode] || defaultValue;
    }

    /**
     * Replaces the shared HOURS collection with the configured slot starts when available.
     * Input: slotStartTimes - array of HH:MM strings from the API
     * Output: void; mutates root.constants.HOURS when the payload is valid
     */
    function setHoursFromConfig(slotStartTimes) {
        if (Array.isArray(slotStartTimes) && slotStartTimes.length > 0) {
            root.constants.HOURS = slotStartTimes;
        }
    }

    /**
     * Returns the best display label for a stage code.
     * Input: stageCode - stage identifier
     * Output: string display label
     */
    function getStageLabel(stageCode) {
        return resolveStageMetadata(
            root.constants.STAGE_LABELS,
            root.constants.FALLBACK_STAGE_LABELS,
            stageCode,
            stageCode,
        );
    }

    /**
     * Returns the best pill color for a stage code.
     * Input: stageCode - stage identifier
     * Output: string color key
     */
    function getStageColor(stageCode) {
        return resolveStageMetadata(
            root.constants.STAGE_COLORS,
            root.constants.FALLBACK_STAGE_COLORS,
            stageCode,
            "blue",
        );
    }

    root.constants = {
        DAYS: ["MON", "TUE", "WED", "THU", "FRI"],
        HOURS: createDefaultHours(),
        FALLBACK_STAGE_LABELS: createFallbackStageLabels(),
        FALLBACK_STAGE_COLORS: createFallbackStageColors(),
        PREFERENCE_STATES: ["AVAILABLE", "PREFER_YES", "PREFER_NO", "UNAVAILABLE"],
        DAY_LABELS: createDayLabels(),
        STAGE_LABELS: {},
        STAGE_COLORS: {},
        _stageLabelsCallbacks: [],
        _stageColorsCallbacks: [],
        setHoursFromConfig: setHoursFromConfig,
        onStageLabelsReady: createReadyHandler("STAGE_LABELS", "_stageLabelsCallbacks"),
        onStageColorsReady: createReadyHandler("STAGE_COLORS", "_stageColorsCallbacks"),
        setStageLabels: createMetadataSetter("STAGE_LABELS", "_stageLabelsCallbacks"),
        setStageColors: createMetadataSetter("STAGE_COLORS", "_stageColorsCallbacks"),
        getStageLabel: getStageLabel,
        getStageColor: getStageColor,
    };
})();
