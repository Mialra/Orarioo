(function () {
    const root = window.OrariooAdmin = window.OrariooAdmin || {};

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

    function clearElement(element) {
        if (!element) {
            return;
        }
        element.innerHTML = "";
    }

    function createLucideIcon(iconName) {
        return createElement("i", {
            attrs: {
                "data-lucide": iconName,
                "aria-hidden": "true",
            },
        });
    }

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
