/**
 * DOM creation and manipulation utilities for building admin UI elements declaratively.
 */
(function () {
    const root = window.OrariooAdmin = window.OrariooAdmin || {};

    /**
     * Appends a list of child nodes or text strings to a DOM element.
     * Input: element - parent DOM element
     *        children - array of DOM nodes or strings to append
     */
    function appendChildren(element, children) {
        (children || []).forEach(function (child) {
            if (child === null || child === undefined) {
                return;
            }
            if (typeof child === "string") {
                element.appendChild(document.createTextNode(child));
                return;
            }
            element.appendChild(child);
        });
    }

    /**
     * Creates a DOM element with optional class, text, attributes, dataset, and children.
     * Input: tag - HTML tag name string
     *        options - object with className, text, html, attrs, dataset, and children
     * Output: configured DOM element
     */
    function createElement(tag, options) {
        const config = options || {};
        const element = document.createElement(tag);

        if (config.className) {
            element.className = config.className;
        }
        if (config.text !== undefined) {
            element.textContent = config.text;
        }
        if (config.html !== undefined) {
            element.innerHTML = config.html;
        }
        Object.entries(config.attrs || {}).forEach(function (entry) {
            element.setAttribute(entry[0], entry[1]);
        });
        Object.entries(config.dataset || {}).forEach(function (entry) {
            element.dataset[entry[0]] = entry[1];
        });
        appendChildren(element, config.children || []);

        return element;
    }

    /**
     * Removes all child nodes from a DOM element.
     * Input: element - DOM element to clear
     */
    function clearElement(element) {
        if (!element) {
            return;
        }
        element.innerHTML = "";
    }

    /**
     * Creates a Lucide icon element with aria-hidden set.
     * Input: iconName - Lucide icon identifier string
     * Output: DOM <i> element with data-lucide attribute
     */
    function createLucideIcon(iconName) {
        return createElement("i", {
            attrs: {
                "data-lucide": iconName,
                "aria-hidden": "true",
            },
        });
    }

    /**
     * Creates a button element with a Lucide icon, accessible title, and aria-label.
     * Input: className - CSS class string for the button
     *        title - accessible label and tooltip text
     *        icon - Lucide icon identifier string
     * Output: DOM button element
     */
    function createActionButton(className, title, icon) {
        return createElement("button", {
            className: className,
            attrs: {
                type: "button",
                title: title,
                "aria-label": title,
            },
            children: [createLucideIcon(icon)],
        });
    }

    root.dom = {
        createElement: createElement,
        clearElement: clearElement,
        createLucideIcon: createLucideIcon,
        createActionButton: createActionButton,
    };
})();
