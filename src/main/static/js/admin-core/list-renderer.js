(function () {
    const root = window.OrariooAdmin = window.OrariooAdmin || {};
    const dom = root.dom;

    function renderCollection(container, items, renderItem) {
        if (!container) {
            return;
        }

        dom.clearElement(container);
        const fragment = document.createDocumentFragment();

        (items || []).forEach(function (item) {
            const node = renderItem(item);
            if (node) {
                fragment.appendChild(node);
            }
        });

        container.appendChild(fragment);
    }

    root.listRenderer = {
        renderCollection: renderCollection,
    };
})();
