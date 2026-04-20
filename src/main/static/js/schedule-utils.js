/**
 * Schedule utility functions: pure helpers for string normalization,
 * subject-type checks, date/time formatting, and teacher workload calculations.
 * Output: window.ScheduleUtils — all exports are stateless and have no DOM side effects.
 */
(function () {
  const WORK_CENTER_SUBJECT = "Trabajo de Centro";

  /**
   * Lowercases, strips diacritics, and trims a string for accent-insensitive comparison.
   * Input: value - any value coercible to string
   * Output: normalized string
   */
  function normalizeForCompare(value) {
    return String(value || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .trim();
  }

  /**
   * Returns true when value matches the "Trabajo de Centro" subject name.
   * Input: value - subject name string
   * Output: boolean
   */
  function isWorkCenterSubjectValue(value) {
    return normalizeForCompare(value) === normalizeForCompare(WORK_CENTER_SUBJECT);
  }

  /**
   * Extracts the subject_type or type field from a session or subject object.
   * Input: item - object with subject_type or type property
   * Output: uppercase string type code, or empty string
   */
  function getSubjectTypeValue(item) {
    if (!item || typeof item !== "object") {
      return "";
    }
    return String(item.subject_type || item.type || "")
      .trim()
      .toUpperCase();
  }

  /**
   * Formats a UTC Date to "HH:MM".
   * Input: date - Date object
   * Output: "HH:MM" string using UTC hours and minutes
   */
  function toUtcHM(date) {
    return String(date.getUTCHours()).padStart(2, "0") + ":" + String(date.getUTCMinutes()).padStart(2, "0");
  }

  /**
   * Formats an ISO date string to a localized Spanish datetime or "-" on invalid input.
   * Input: value - ISO date string or falsy
   * Output: formatted "DD/MM/YYYY, HH:MM" string, or "-"
   */
  function toIsoDateDisplay(value) {
    if (!value) {
      return "-";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "-";
    }
    return date.toLocaleString("es-ES", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  /**
   * Parses an ISO date string to milliseconds since epoch, or 0 on invalid input.
   * Input: value - ISO date string or falsy
   * Output: number of milliseconds
   */
  function toDateMillis(value) {
    if (!value) {
      return 0;
    }
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? 0 : parsed.getTime();
  }

  /**
   * Formats a raw hours number to a human-readable string like "3 h" or "1,5 h".
   * Input: rawHours - number
   * Output: formatted string with "h" suffix, or "0 h" for non-positive values
   */
  function formatTeacherWorkloadHours(rawHours) {
    const numericHours = Number(rawHours);
    if (!Number.isFinite(numericHours) || numericHours <= 0) {
      return "0 h";
    }
    const rounded = Math.round(numericHours * 100) / 100;
    if (Number.isInteger(rounded)) {
      return String(rounded) + " h";
    }
    const text = rounded
      .toFixed(2)
      .replace(/\.00$/, "")
      .replace(/(\.[1-9])0$/, "$1")
      .replace(".", ",");
    return text + " h";
  }

  /**
   * Builds a teacher-name → total-hours map from an API workload array.
   * Input: workloads - array of { teacher_name, total_hours } objects
   * Output: object mapping teacher name strings to hour numbers
   */
  function buildTeacherWorkloadsByNameFromApi(workloads) {
    const byName = {};
    (workloads || []).forEach(function (item) {
      const teacherName = String((item && item.teacher_name) || "").trim();
      if (!teacherName) {
        return;
      }
      const totalHours = Number(item.total_hours);
      if (!Number.isFinite(totalHours) || totalHours <= 0) {
        return;
      }
      byName[teacherName] = totalHours;
    });
    return byName;
  }

  /**
   * Calculates a teacher-name → total-hours map by summing session durations.
   * Input: sessions - array of raw schedule session objects with teacher_name, start_time, end_time
   * Output: object mapping teacher name strings to hour numbers
   */
  function buildTeacherWorkloadsByNameFromSessions(sessions) {
    const minutesByName = {};
    (sessions || []).forEach(function (session) {
      const teacherName = String((session && session.teacher_name) || "").trim();
      if (!teacherName) {
        return;
      }
      const startTime = new Date(session.start_time);
      const endTime = new Date(session.end_time);
      if (Number.isNaN(startTime.getTime()) || Number.isNaN(endTime.getTime())) {
        return;
      }
      const durationMinutes = Math.round((endTime.getTime() - startTime.getTime()) / 60000);
      if (!Number.isFinite(durationMinutes) || durationMinutes <= 0) {
        return;
      }
      minutesByName[teacherName] = (minutesByName[teacherName] || 0) + durationMinutes;
    });
    return Object.keys(minutesByName).reduce(function (acc, teacherName) {
      acc[teacherName] = minutesByName[teacherName] / 60;
      return acc;
    }, {});
  }

  /**
   * Appends the formatted workload in parentheses to a teacher name, or returns the name alone.
   * Input: teacherName - string; workloadsByName - object from buildTeacherWorkloadsByName*
   * Output: string like "Ana García (6 h)", or just the name, or "-" when empty
   */
  function resolveTeacherLabelWithWorkload(teacherName, workloadsByName) {
    const normalizedName = String(teacherName || "").trim();
    if (!normalizedName) {
      return "-";
    }
    const totalHours = workloadsByName && workloadsByName[normalizedName];
    if (!Number.isFinite(Number(totalHours)) || Number(totalHours) <= 0) {
      return normalizedName;
    }
    return normalizedName + " (" + formatTeacherWorkloadHours(totalHours) + ")";
  }

  /**
   * Parses "HH:MM" to total minutes from midnight; returns MAX_SAFE_INTEGER on invalid input.
   * Input: value - "HH:MM" string
   * Output: number of minutes
   */
  function parseHourKey(value) {
    const tokens = String(value || "").split(":");
    if (tokens.length !== 2) {
      return Number.MAX_SAFE_INTEGER;
    }
    const hour = Number.parseInt(tokens[0], 10);
    const minute = Number.parseInt(tokens[1], 10);
    if (Number.isNaN(hour) || Number.isNaN(minute)) {
      return Number.MAX_SAFE_INTEGER;
    }
    return hour * 60 + minute;
  }

  /**
   * Comparator for sorting board rows by start time, then by end time.
   * Input: left, right - row objects with start/end "HH:MM" strings
   * Output: negative, zero, or positive number for Array.sort
   */
  function compareRowsByTime(left, right) {
    const startCompare = parseHourKey(left.start) - parseHourKey(right.start);
    if (startCompare !== 0) {
      return startCompare;
    }
    return parseHourKey(left.end) - parseHourKey(right.end);
  }

  /**
   * Builds the composite board-cell identifier from day and time range.
   * Input: dayName - Spanish weekday string; startHm, endHm - "HH:MM" strings
   * Output: "dayName|HH:MM|HH:MM" string used as data-board-key attributes
   */
  function createBoardCellKey(dayName, startHm, endHm) {
    return dayName + "|" + startHm + "|" + endHm;
  }

  /**
   * Parses "HH:MM" to total minutes from midnight; returns NaN on invalid input.
   * Input: value - "HH:MM" string
   * Output: number of minutes, or NaN
   */
  function parseHmToMinutes(value) {
    const parts = String(value || "").split(":");
    if (parts.length !== 2) {
      return Number.NaN;
    }
    const hour = Number.parseInt(parts[0], 10);
    const minute = Number.parseInt(parts[1], 10);
    if (Number.isNaN(hour) || Number.isNaN(minute)) {
      return Number.NaN;
    }
    return hour * 60 + minute;
  }

  /**
   * Returns true when two HH:MM time ranges overlap (exclusive endpoints).
   * Input: leftStart, leftEnd, rightStart, rightEnd - "HH:MM" strings
   * Output: boolean
   */
  function hmRangesOverlap(leftStart, leftEnd, rightStart, rightEnd) {
    const leftStartMinutes = parseHmToMinutes(leftStart);
    const leftEndMinutes = parseHmToMinutes(leftEnd);
    const rightStartMinutes = parseHmToMinutes(rightStart);
    const rightEndMinutes = parseHmToMinutes(rightEnd);
    if (
      Number.isNaN(leftStartMinutes) ||
      Number.isNaN(leftEndMinutes) ||
      Number.isNaN(rightStartMinutes) ||
      Number.isNaN(rightEndMinutes)
    ) {
      return false;
    }
    return leftStartMinutes < rightEndMinutes && rightStartMinutes < leftEndMinutes;
  }

  /**
   * Returns true when any item in the array has a TC subject type.
   * Input: items - array of session or subject objects
   * Output: boolean
   */
  function hasWorkCenterSubjects(items) {
    return (items || []).some(function (item) {
      return getSubjectTypeValue(item) === "TC";
    });
  }

  /**
   * Returns the total count from a paginated payload, or falls back to the array length.
   * Input: payload - API response with optional count field; fallbackItems - fallback array
   * Output: number
   */
  function getCollectionCount(payload, fallbackItems) {
    if (payload && typeof payload.count === "number") {
      return payload.count;
    }
    return Array.isArray(fallbackItems) ? fallbackItems.length : 0;
  }

  /**
   * Appends a summary query parameter to a URL path.
   * Input: path - base URL path string; summary - summary type string
   * Output: URL string with summary param appended
   */
  function buildSummaryPath(path, summary) {
    return path + (path.indexOf("?") >= 0 ? "&" : "?") + "summary=" + encodeURIComponent(summary);
  }

  window.ScheduleUtils = {
    normalizeForCompare: normalizeForCompare,
    isWorkCenterSubjectValue: isWorkCenterSubjectValue,
    getSubjectTypeValue: getSubjectTypeValue,
    toUtcHM: toUtcHM,
    toIsoDateDisplay: toIsoDateDisplay,
    toDateMillis: toDateMillis,
    formatTeacherWorkloadHours: formatTeacherWorkloadHours,
    buildTeacherWorkloadsByNameFromApi: buildTeacherWorkloadsByNameFromApi,
    buildTeacherWorkloadsByNameFromSessions: buildTeacherWorkloadsByNameFromSessions,
    resolveTeacherLabelWithWorkload: resolveTeacherLabelWithWorkload,
    parseHourKey: parseHourKey,
    compareRowsByTime: compareRowsByTime,
    createBoardCellKey: createBoardCellKey,
    parseHmToMinutes: parseHmToMinutes,
    hmRangesOverlap: hmRangesOverlap,
    hasWorkCenterSubjects: hasWorkCenterSubjects,
    getCollectionCount: getCollectionCount,
    buildSummaryPath: buildSummaryPath,
  };
})();
