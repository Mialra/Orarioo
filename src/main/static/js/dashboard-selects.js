/**
 * Custom accessible select widget: replaces native <select> elements with a styled dropdown.
 * Exposed as window.OrariooSelects.
 */
(function () {
    const SELECTOR = "select.orarioo-custom-select";

    /**
     * Resolves a native select element from an HTMLSelectElement or an ID string.
     * Input: selectOrId - HTMLSelectElement or string ID
     * Output: HTMLSelectElement, or null if not found
     */
    function getSelectFromInput(selectOrId) {
        if (selectOrId instanceof HTMLSelectElement) {
            return selectOrId;
        }

        if (typeof selectOrId === "string") {
            const element = document.getElementById(selectOrId);
            return element instanceof HTMLSelectElement ? element : null;
        }

        return null;
    }

    function getWrapper(select) {
        if (!select) {
            return null;
        }
        return select.closest(".orarioo-select-dropdown");
    }

    function closeDropdown(wrapper) {
        if (!wrapper) {
            return;
        }

        wrapper.classList.remove("is-open");
        const trigger = wrapper.querySelector(".orarioo-select-trigger");
        if (trigger) {
            trigger.setAttribute("aria-expanded", "false");
        }
    }

    function closeAllDropdowns(exceptWrapper) {
        document.querySelectorAll(".orarioo-select-dropdown.is-open").forEach(function (wrapper) {
            if (exceptWrapper && wrapper === exceptWrapper) {
                return;
            }
            closeDropdown(wrapper);
        });
    }

    function getOptionButtons(wrapper) {
        if (!wrapper) {
            return [];
        }

        return Array.from(wrapper.querySelectorAll(".orarioo-select-option:not(:disabled)"));
    }

    function focusOption(wrapper, index) {
        const options = getOptionButtons(wrapper);
        if (!options.length) {
            return;
        }

        const boundedIndex = Math.max(0, Math.min(index, options.length - 1));
        options[boundedIndex].focus();
    }

    function focusSelectedOption(wrapper) {
        if (!wrapper) {
            return;
        }

        const selectedOption = wrapper.querySelector(".orarioo-select-option.is-selected");
        if (selectedOption) {
            selectedOption.focus();
            return;
        }

        focusOption(wrapper, 0);
    }

    function getScrollContainer(element) {
        let current = element ? element.parentElement : null;

        while (current) {
            const styles = window.getComputedStyle(current);
            const canScrollY =
                /(auto|scroll|overlay)/.test(styles.overflowY) &&
                current.scrollHeight > current.clientHeight + 1;

            if (canScrollY) {
                return current;
            }

            current = current.parentElement;
        }

        return window;
    }

    function ensureMenuVisible(wrapper) {
        if (!wrapper) {
            return;
        }

        const menu = wrapper.querySelector(".orarioo-select-menu");
        if (!menu) {
            return;
        }

        const scrollContainer = getScrollContainer(wrapper);
        const menuRect = menu.getBoundingClientRect();
        const containerRect =
            scrollContainer === window
                ? {
                    top: 0,
                    bottom: window.innerHeight || document.documentElement.clientHeight || 0,
                }
                : scrollContainer.getBoundingClientRect();

        const overflowBottom = menuRect.bottom - containerRect.bottom;
        if (overflowBottom <= 0) {
            return;
        }

        if (scrollContainer === window) {
            window.scrollBy({
                top: overflowBottom + 12,
                left: 0,
                behavior: "smooth",
            });
            return;
        }

        scrollContainer.scrollTop += overflowBottom + 12;
    }

    function openDropdown(wrapper) {
        if (!wrapper || wrapper.classList.contains("is-disabled")) {
            return;
        }

        closeAllDropdowns(wrapper);
        wrapper.classList.add("is-open");

        const trigger = wrapper.querySelector(".orarioo-select-trigger");
        if (trigger) {
            trigger.setAttribute("aria-expanded", "true");
        }

        window.requestAnimationFrame(function () {
            ensureMenuVisible(wrapper);
        });
    }

    function toggleDropdown(wrapper) {
        if (!wrapper) {
            return;
        }

        if (wrapper.classList.contains("is-open")) {
            closeDropdown(wrapper);
            return;
        }

        openDropdown(wrapper);
    }

    /**
     * Rebuilds the custom dropdown trigger label and menu to match the native select's current state.
     * Input: select - the native HTMLSelectElement to synchronise
     */
    function syncSelect(select) {
        const wrapper = getWrapper(select);
        if (!wrapper) {
            return;
        }

        const trigger = wrapper.querySelector(".orarioo-select-trigger");
        const triggerLabel = wrapper.querySelector(".orarioo-select-trigger-label");
        const menu = wrapper.querySelector(".orarioo-select-menu");
        if (!trigger || !triggerLabel || !menu) {
            return;
        }

        const selectedOption = select.options[select.selectedIndex >= 0 ? select.selectedIndex : 0] || null;
        const selectedLabel = selectedOption ? String(selectedOption.textContent || "").trim() : "";

        triggerLabel.textContent = selectedLabel || "Selecciona una opción";
        trigger.title = selectedLabel || "";
        trigger.disabled = select.disabled;
        wrapper.classList.toggle("is-disabled", select.disabled);
        wrapper.classList.toggle("is-invalid", select.classList.contains("is-invalid"));

        menu.innerHTML = Array.from(select.options)
            .map(function (option, index) {
                const label = String(option.textContent || "").trim();
                const selectedClass = option.selected ? " is-selected" : "";
                const selectedAttr = option.selected ? "true" : "false";
                const disabledAttr = option.disabled ? " disabled" : "";

                return (
                    '<button type="button" class="orarioo-select-option' +
                    selectedClass +
                    '" role="option" aria-selected="' +
                    selectedAttr +
                    '" data-select-index="' +
                    index +
                    '"' +
                    disabledAttr +
                    ">" +
                    window.OrariooErrorHandler.escapeHtml(label) +
                    "</button>"
                );
            })
            .join("");

        if (select.disabled) {
            closeDropdown(wrapper);
        }
    }

    function attachLabelOpenBehavior(select, wrapper) {
        if (!select || !select.id || !wrapper) {
            return;
        }

        document.querySelectorAll('label[for="' + select.id + '"]').forEach(function (label) {
            if (label.dataset.orariooSelectLabelReady === "true") {
                return;
            }

            label.dataset.orariooSelectLabelReady = "true";
            label.addEventListener("click", function (event) {
                event.preventDefault();
                const trigger = wrapper.querySelector(".orarioo-select-trigger");
                if (!trigger || trigger.disabled) {
                    return;
                }
                trigger.focus();
                openDropdown(wrapper);
            });
        });
    }

    /**
     * Wraps a native select with the custom dropdown markup and wires all event listeners.
     * Input: select - the native HTMLSelectElement to enhance
     * Output: the wrapper div element
     */
    function enhanceSelect(select) {
        const existingWrapper = getWrapper(select);
        if (select.dataset.orariooSelectReady === "true" && existingWrapper) {
            syncSelect(select);
            return existingWrapper;
        }

        const wrapper = document.createElement("div");
        const trigger = document.createElement("button");
        const triggerLabel = document.createElement("span");
        const triggerIcon = document.createElement("span");
        const menu = document.createElement("div");

        wrapper.className = "orarioo-select-dropdown";
        trigger.type = "button";
        trigger.className = "orarioo-select-trigger";
        trigger.setAttribute("aria-expanded", "false");
        trigger.setAttribute("aria-haspopup", "listbox");
        triggerLabel.className = "orarioo-select-trigger-label";
        triggerIcon.className = "orarioo-select-trigger-icon";
        triggerIcon.setAttribute("aria-hidden", "true");
        triggerIcon.textContent = "▾";
        menu.className = "orarioo-select-menu";
        menu.setAttribute("role", "listbox");

        trigger.appendChild(triggerLabel);
        trigger.appendChild(triggerIcon);
        wrapper.appendChild(trigger);
        wrapper.appendChild(menu);

        select.parentNode.insertBefore(wrapper, select);
        wrapper.appendChild(select);

        select.classList.add("orarioo-select-native");
        select.tabIndex = -1;
        select.setAttribute("aria-hidden", "true");
        select.dataset.orariooSelectReady = "true";

        trigger.addEventListener("click", function () {
            toggleDropdown(wrapper);
        });

        trigger.addEventListener("keydown", function (event) {
            if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                openDropdown(wrapper);
                focusSelectedOption(wrapper);
                return;
            }

            if (event.key === "Escape") {
                closeDropdown(wrapper);
            }
        });

        menu.addEventListener("click", function (event) {
            const target = event.target;
            if (!(target instanceof HTMLElement)) {
                return;
            }

            const optionButton = target.closest(".orarioo-select-option[data-select-index]");
            if (!optionButton) {
                return;
            }

            const nextIndex = Number.parseInt(optionButton.dataset.selectIndex || "", 10);
            if (Number.isNaN(nextIndex) || !select.options[nextIndex]) {
                return;
            }

            const hasChanged = select.selectedIndex !== nextIndex;
            select.selectedIndex = nextIndex;
            syncSelect(select);
            closeDropdown(wrapper);
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

            const options = getOptionButtons(wrapper);
            const currentIndex = options.indexOf(activeElement);

            if (event.key === "Escape") {
                event.preventDefault();
                closeDropdown(wrapper);
                trigger.focus();
                return;
            }

            if (event.key === "ArrowDown") {
                event.preventDefault();
                focusOption(wrapper, currentIndex + 1);
                return;
            }

            if (event.key === "ArrowUp") {
                event.preventDefault();
                if (currentIndex <= 0) {
                    trigger.focus();
                    return;
                }
                focusOption(wrapper, currentIndex - 1);
            }
        });

        select.addEventListener("change", function () {
            syncSelect(select);
        });

        const observer = new MutationObserver(function () {
            syncSelect(select);
        });
        observer.observe(select, {
            childList: true,
            subtree: true,
            characterData: true,
            attributes: true,
            attributeFilter: ["class", "disabled", "label", "selected"],
        });

        attachLabelOpenBehavior(select, wrapper);
        syncSelect(select);
        return wrapper;
    }

    /**
     * Returns all matching native select elements within the given root element.
     * Input: root - DOM element or document to search within
     * Output: array of HTMLSelectElement instances
     */
    function collectSelects(root) {
        if (!root) {
            return [];
        }

        if (root instanceof HTMLSelectElement && root.matches(SELECTOR)) {
            return [root];
        }

        if (typeof root.querySelectorAll === "function") {
            return Array.from(root.querySelectorAll(SELECTOR));
        }

        return [];
    }

    /**
     * Enhances all matching select elements within root (defaults to document).
     * Input: root - optional DOM element or document to scope the initialisation
     */
    function init(root) {
        collectSelects(root || document).forEach(function (select) {
            enhanceSelect(select);
        });
    }

    /**
     * Re-enhances and re-syncs a single select identified by element or ID string.
     * Input: selectOrId - HTMLSelectElement or string ID
     */
    function refresh(selectOrId) {
        const select = getSelectFromInput(selectOrId);
        if (!select || !select.matches(SELECTOR)) {
            return;
        }

        enhanceSelect(select);
        syncSelect(select);
    }

    /**
     * Re-enhances and re-syncs all matching selects within root (defaults to document).
     * Input: root - optional DOM element to scope the refresh
     */
    function refreshAll(root) {
        collectSelects(root || document).forEach(function (select) {
            refresh(select);
        });
    }

    document.addEventListener("click", function (event) {
        const target = event.target;
        if (target instanceof HTMLElement && target.closest(".orarioo-select-dropdown")) {
            return;
        }
        closeAllDropdowns();
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            closeAllDropdowns();
        }
    });

    document.addEventListener("reset", function (event) {
        const target = event.target;
        if (!(target instanceof HTMLFormElement)) {
            return;
        }

        window.requestAnimationFrame(function () {
            refreshAll(target);
        });
    });

    window.addEventListener("resize", function () {
        closeAllDropdowns();
    });

    window.OrariooSelects = {
        init: init,
        refresh: refresh,
        refreshAll: refreshAll,
        closeAll: closeAllDropdowns,
    };

    init(document);
})();
