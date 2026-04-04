(function () {
    const core = window.OrariooAdmin || {};

    function createEntityManager(config) {
        if (!core.initCrudModule) {
            throw new Error("Admin CRUD core is not available.");
        }
        return core.initCrudModule(config);
    }

    window.AdminBase = {
        api: core.api,
        uiState: core.uiState,
        formUtils: core.formUtils,
        modalUtils: core.modalUtils,
        listRenderer: core.listRenderer,
        pagination: core.pagination,
        dom: core.dom,
        createEntityManager: createEntityManager,
        paginate: function (items, page, pageSize) {
            const list = items || [];
            const safePage = Math.max(1, Number(page) || 1);
            const safePageSize = Math.max(1, Number(pageSize) || 1);
            const start = (safePage - 1) * safePageSize;
            return list.slice(start, start + safePageSize);
        },
        renderList: function (container, items, renderItem) {
            return core.listRenderer.renderCollection(container, items, renderItem);
        },
        setupPagination: function (config) {
            return core.pagination.createPaginationController(config);
        },
    };
})();