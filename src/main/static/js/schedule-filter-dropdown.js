/**
 * Accessible custom filter dropdown widget for schedule toolbars.
 * Wraps native <select> elements with keyboard-navigable, ARIA-compliant dropdowns.
 * Depends on window.OrariooErrorHandler.escapeHtml.
 * Output: window.ScheduleFilterDropdown — { closeScheduleFilterDropdown,
 *   closeAllScheduleFilterDropdowns, syncScheduleFilterDropdown,
 *   enhanceScheduleFilterSelect, initScheduleFilterDropdowns }
 */
(function () {
  /**
   * Removes the is-open class and updates aria-expanded on a filter dropdown.
   * Input: dropdown - .schedule-filter-dropdown element
   * Output: void
   */
  function closeScheduleFilterDropdown(dropdown) {
    if (!dropdown) {
      return;
    }
    dropdown.classList.remove("is-open");
    const trigger = dropdown.querySelector(".schedule-filter-trigger");
    if (trigger) {
      trigger.setAttribute("aria-expanded", "false");
    }
  }

  /**
   * Closes all open filter dropdowns except an optional exclusion.
   * Input: exceptDropdown - optional element to leave open
   * Output: void
   */
  function closeAllScheduleFilterDropdowns(exceptDropdown) {
    document.querySelectorAll(".schedule-filter-dropdown.is-open").forEach(function (dropdown) {
      if (exceptDropdown && dropdown === exceptDropdown) {
        return;
      }
      closeScheduleFilterDropdown(dropdown);
    });
  }

  /**
   * Returns all enabled .schedule-filter-option buttons inside a dropdown.
   * Input: dropdown - .schedule-filter-dropdown element
   * Output: array of button elements
   */
  function getScheduleFilterOptionButtons(dropdown) {
    if (!dropdown) {
      return [];
    }
    return Array.from(dropdown.querySelectorAll(".schedule-filter-option:not(:disabled)"));
  }

  /**
   * Focuses the option button at the given index, clamped to available options.
   * Input: dropdown - .schedule-filter-dropdown element; index - target option index
   * Output: void
   */
  function focusScheduleFilterOption(dropdown, index) {
    const options = getScheduleFilterOptionButtons(dropdown);
    if (!options.length) {
      return;
    }
    const boundedIndex = Math.max(0, Math.min(index, options.length - 1));
    options[boundedIndex].focus();
  }

  /**
   * Focuses the currently selected option in a filter dropdown, or the first option.
   * Input: dropdown - .schedule-filter-dropdown element
   * Output: void
   */
  function focusSelectedScheduleFilterOption(dropdown) {
    if (!dropdown) {
      return;
    }
    const selectedOption = dropdown.querySelector(".schedule-filter-option.is-selected");
    if (selectedOption) {
      selectedOption.focus();
      return;
    }
    focusScheduleFilterOption(dropdown, 0);
  }

  /**
   * Scrolls the page to ensure the dropdown menu is not clipped by the viewport bottom.
   * Input: dropdown - .schedule-filter-dropdown element
   * Output: void
   */
  function ensureScheduleFilterMenuVisible(dropdown) {
    if (!dropdown) {
      return;
    }
    const menu = dropdown.querySelector(".schedule-filter-menu");
    if (!menu) {
      return;
    }
    const menuRect = menu.getBoundingClientRect();
    const viewportBottom = window.innerHeight || document.documentElement.clientHeight || 0;
    const overflowBottom = menuRect.bottom - viewportBottom;
    if (overflowBottom > 0) {
      window.scrollBy({ top: overflowBottom + 12, left: 0, behavior: "smooth" });
    }
  }

  /**
   * Opens a filter dropdown and positions its menu in the viewport.
   * Input: dropdown - .schedule-filter-dropdown element
   * Output: void
   */
  function openScheduleFilterDropdown(dropdown) {
    if (!dropdown) {
      return;
    }
    closeAllScheduleFilterDropdowns(dropdown);
    dropdown.classList.add("is-open");
    const trigger = dropdown.querySelector(".schedule-filter-trigger");
    if (trigger) {
      trigger.setAttribute("aria-expanded", "true");
    }
    window.requestAnimationFrame(function () {
      ensureScheduleFilterMenuVisible(dropdown);
    });
  }

  /**
   * Toggles a filter dropdown between open and closed.
   * Input: dropdown - .schedule-filter-dropdown element
   * Output: void
   */
  function toggleScheduleFilterDropdown(dropdown) {
    if (!dropdown) {
      return;
    }
    if (dropdown.classList.contains("is-open")) {
      closeScheduleFilterDropdown(dropdown);
      return;
    }
    openScheduleFilterDropdown(dropdown);
  }

  /**
   * Synchronizes the custom dropdown UI to match the current native select value and options.
   * Input: select - native <select> element inside a .schedule-filter-dropdown
   * Output: void; updates trigger label and option buttons
   */
  function syncScheduleFilterDropdown(select) {
    if (!select) {
      return;
    }
    const dropdown = select.closest(".schedule-filter-dropdown");
    if (!dropdown) {
      return;
    }
    const triggerLabel = dropdown.querySelector(".schedule-filter-trigger-label");
    const menu = dropdown.querySelector(".schedule-filter-menu");
    if (!triggerLabel || !menu) {
      return;
    }
    const selectedOption = select.options[select.selectedIndex >= 0 ? select.selectedIndex : 0] || null;
    const selectedLabel = selectedOption ? String(selectedOption.textContent || "").trim() : "";
    triggerLabel.textContent = selectedLabel || "Selecciona una opción";
    const escapeHtml =
      window.OrariooErrorHandler && window.OrariooErrorHandler.escapeHtml
        ? window.OrariooErrorHandler.escapeHtml
        : function (s) { return String(s || ""); };
    menu.innerHTML = Array.from(select.options)
      .map(function (option) {
        const label = String(option.textContent || "").trim();
        const selectedClass = option.selected ? " is-selected" : "";
        const selectedAttr = option.selected ? "true" : "false";
        const disabledAttr = option.disabled ? " disabled" : "";
        return (
          '<button type="button" class="schedule-filter-option' +
          selectedClass +
          '" role="option" aria-selected="' +
          selectedAttr +
          '" data-filter-value="' +
          escapeHtml(option.value) +
          '"' +
          disabledAttr +
          ">" +
          escapeHtml(label) +
          "</button>"
        );
      })
      .join("");
  }

  /**
   * Wraps a native select with a fully accessible custom dropdown widget.
   * Input: select - native <select> element with class schedule-toolbar-select
   * Output: void; replaces the select in the DOM with a wrapped custom component
   */
  function enhanceScheduleFilterSelect(select) {
    if (!select || select.dataset.customFilterReady === "true") {
      return;
    }
    const wrapper = document.createElement("div");
    const trigger = document.createElement("button");
    const triggerLabel = document.createElement("span");
    const triggerIcon = document.createElement("span");
    const menu = document.createElement("div");

    wrapper.className = "schedule-filter-dropdown";
    trigger.type = "button";
    trigger.className = "schedule-filter-trigger";
    trigger.setAttribute("aria-expanded", "false");
    trigger.setAttribute("aria-haspopup", "listbox");
    triggerLabel.className = "schedule-filter-trigger-label";
    triggerIcon.className = "schedule-filter-trigger-icon";
    triggerIcon.setAttribute("aria-hidden", "true");
    triggerIcon.textContent = "▾";
    menu.className = "schedule-filter-menu";
    menu.setAttribute("role", "listbox");

    trigger.appendChild(triggerLabel);
    trigger.appendChild(triggerIcon);
    wrapper.appendChild(trigger);
    wrapper.appendChild(menu);

    select.parentNode.insertBefore(wrapper, select);
    wrapper.appendChild(select);

    select.classList.add("schedule-toolbar-select-native");
    select.tabIndex = -1;
    select.setAttribute("aria-hidden", "true");
    select.dataset.customFilterReady = "true";

    trigger.addEventListener("click", function () {
      toggleScheduleFilterDropdown(wrapper);
    });

    trigger.addEventListener("keydown", function (event) {
      if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openScheduleFilterDropdown(wrapper);
        focusSelectedScheduleFilterOption(wrapper);
        return;
      }
      if (event.key === "Escape") {
        closeScheduleFilterDropdown(wrapper);
      }
    });

    menu.addEventListener("click", function (event) {
      const optionButton = event.target.closest(".schedule-filter-option[data-filter-value]");
      if (!optionButton) {
        return;
      }
      const nextValue = optionButton.dataset.filterValue || "";
      const hasChanged = select.value !== nextValue;
      select.value = nextValue;
      syncScheduleFilterDropdown(select);
      closeScheduleFilterDropdown(wrapper);
      trigger.focus();
      if (hasChanged) {
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });

    menu.addEventListener("keydown", function (event) {
      const activeElement = document.activeElement;
      if (!(activeElement instanceof HTMLElement)) {
        return;
      }
      const options = getScheduleFilterOptionButtons(wrapper);
      const currentIndex = options.indexOf(activeElement);
      if (event.key === "Escape") {
        event.preventDefault();
        closeScheduleFilterDropdown(wrapper);
        trigger.focus();
        return;
      }
      if (event.key === "ArrowDown") {
        event.preventDefault();
        focusScheduleFilterOption(wrapper, currentIndex + 1);
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        if (currentIndex <= 0) {
          trigger.focus();
          return;
        }
        focusScheduleFilterOption(wrapper, currentIndex - 1);
      }
    });

    select.addEventListener("change", function () {
      syncScheduleFilterDropdown(select);
    });

    syncScheduleFilterDropdown(select);
  }

  /**
   * Enhances all .schedule-toolbar-select elements and wires global close-on-outside-click.
   * Input: none
   * Output: void; modifies the DOM and adds document-level event listeners
   */
  function initScheduleFilterDropdowns() {
    document.querySelectorAll(".schedule-toolbar-select").forEach(function (select) {
      enhanceScheduleFilterSelect(select);
    });
    document.addEventListener("click", function (event) {
      const target = event.target;
      if (target instanceof HTMLElement && target.closest(".schedule-filter-dropdown")) {
        return;
      }
      closeAllScheduleFilterDropdowns();
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        closeAllScheduleFilterDropdowns();
      }
    });
    window.addEventListener("resize", function () {
      closeAllScheduleFilterDropdowns();
    });
  }

  window.ScheduleFilterDropdown = {
    closeScheduleFilterDropdown: closeScheduleFilterDropdown,
    closeAllScheduleFilterDropdowns: closeAllScheduleFilterDropdowns,
    syncScheduleFilterDropdown: syncScheduleFilterDropdown,
    enhanceScheduleFilterSelect: enhanceScheduleFilterSelect,
    initScheduleFilterDropdowns: initScheduleFilterDropdowns,
  };
})();
