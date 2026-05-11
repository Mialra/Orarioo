/**
 * Client-side pagination controller that renders a Bootstrap pagination nav into a container.
 */
(function () {
    const root = window.OrariooAdmin = window.OrariooAdmin || {};
    const dom = root.dom;

    /**
     * Clamps a numeric value between min and max (inclusive).
     * Input: value, min, max - numbers
     * Output: number within [min, max]
     */
    function clamp(value, min, max) {
        return Math.max(min, Math.min(max, value));
    }

    /**
     * Creates a pagination controller that manages page state and renders Bootstrap nav buttons.
     * Input: config - object with container (DOM element) and pageSize (number, default 5)
     * Output: object with setTotalItems, getPageSlice, setPage, getCurrentPage, render, and pageSize
     */
    function createPaginationController(config) {
        const options = config || {};
        const container = options.container;
        const pageSize = options.pageSize || 5;
        let page = 1;
        let totalItems = 0;

        function getTotalPages() {
            return Math.max(1, Math.ceil(totalItems / pageSize));
        }

        function setTotalItems(count) {
            totalItems = count || 0;
            page = clamp(page, 1, getTotalPages());
        }

        function setPage(nextPage) {
            page = clamp(nextPage, 1, getTotalPages());
        }

        function getPageSlice(items) {
            const list = items || [];
            const start = (page - 1) * pageSize;
            return list.slice(start, start + pageSize);
        }

        function render(onPageChange) {
            if (!container) {
                return;
            }

            dom.clearElement(container);
            if (totalItems <= pageSize) {
                return;
            }

            const totalPages = getTotalPages();
            const nav = dom.createElement("nav", {
                attrs: {
                    "aria-label": "Paginación del listado",
                },
            });
            const ul = dom.createElement("ul", {
                className: "pagination pagination-sm justify-content-center mb-0",
            });

            function createPageButton(label, targetPage, disabled, active) {
                const li = dom.createElement("li", {
                    className: "page-item" + (disabled ? " disabled" : "") + (active ? " active" : ""),
                });
                const button = dom.createElement("button", {
                    className: "page-link",
                    text: label,
                    attrs: {
                        type: "button",
                    },
                });

                if (!disabled) {
                    button.addEventListener("click", function () {
                        setPage(targetPage);
                        onPageChange(page);
                    });
                } else {
                    button.setAttribute("tabindex", "-1");
                    button.setAttribute("aria-disabled", "true");
                }

                if (active) {
                    button.setAttribute("aria-current", "page");
                }

                li.appendChild(button);
                ul.appendChild(li);
            }

            createPageButton("Anterior", page - 1, page <= 1, false);

            function createEllipsis() {
                const li = dom.createElement("li", {
                    className: "page-item disabled",
                });
                const span = dom.createElement("span", {
                    className: "page-link",
                    text: "...",
                    attrs: {
                        "aria-hidden": "true",
                    },
                });
                li.appendChild(span);
                ul.appendChild(li);
            }

            const windowStart = Math.max(1, page - 1);
            const windowEnd = Math.min(totalPages, page + 1);

            createPageButton("1", 1, false, page === 1);

            if (windowStart > 2) {
                createEllipsis();
            }

            for (let index = windowStart; index <= windowEnd; index += 1) {
                if (index === 1 || index === totalPages) {
                    continue;
                }
                createPageButton(String(index), index, false, index === page);
            }

            if (windowEnd < totalPages - 1) {
                createEllipsis();
            }

            if (totalPages > 1) {
                createPageButton(String(totalPages), totalPages, false, page === totalPages);
            }

            createPageButton("Siguiente", page + 1, page >= totalPages, false);

            nav.appendChild(ul);
            container.appendChild(nav);
        }

        return {
            pageSize: pageSize,
            setTotalItems: setTotalItems,
            getPageSlice: getPageSlice,
            setPage: setPage,
            getCurrentPage: function () {
                return page;
            },
            render: render,
        };
    }

    root.pagination = {
        createPaginationController: createPaginationController,
    };
})();
