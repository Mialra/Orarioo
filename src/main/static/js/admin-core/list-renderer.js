/**
 * Renders an array of data items into a container using a caller-supplied item renderer.
 */
(function () {
    const root = window.OrariooAdmin = window.OrariooAdmin || {};
    const dom = root.dom;

    /**
     * Clears the container and appends a DOM node for each item in the array.
     * Input: container - parent DOM element to render into
     *        items - array of data objects to render
     *        renderItem - function(item) returning a DOM node or null
     */
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
