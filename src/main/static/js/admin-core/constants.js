(function () {
    const root = window.OrariooAdmin = window.OrariooAdmin || {};

    root.constants = {
        DAYS: ["MON", "TUE", "WED", "THU", "FRI"],
        HOURS: [
            "08:00", "08:30", "09:00", "09:30",
            "10:00", "10:30", "11:00", "11:30",
            "12:00", "12:30", "13:00", "13:30",
            "14:00", "14:30",
        ],
        PREFERENCE_STATES: ["AVAILABLE", "PREFER_YES", "PREFER_NO", "UNAVAILABLE"],
        DAY_LABELS: {
            MON: "Lunes",
            TUE: "Martes",
            WED: "Miércoles",
            THU: "Jueves",
            FRI: "Viernes",
        },
    };
})();
