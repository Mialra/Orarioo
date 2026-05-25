/**
 * Public facade that re-exports OrariooAdmin admin-core utilities as window.AdminBase.
 */
(function () {
    const core = window.OrariooAdmin || {};

    async function loadScheduleConfig() {
        try {
            const res = await core.api.get("/api/schedule-config/");
            if (res.ok && res.data) {
                if (res.data.slot_start_times) {
                    core.constants.setHoursFromConfig(res.data.slot_start_times);
                }
                if (res.data.stage_labels) {
                    core.constants.setStageLabels(res.data.stage_labels);
                }
                if (res.data.stage_colors) {
                    core.constants.setStageColors(res.data.stage_colors);
                }
            }
        } catch (_) {
            // silently fall back to default HOURS and STAGE_LABELS
        }
    }

    loadScheduleConfig();

    /**
     * Delegates to core.initCrudModule, throwing if the admin-core library is not loaded.
     * Input: config - initCrudModule configuration object
     */
    function createEntityManager(config) {
        if (!core.initCrudModule) {
            throw new Error("El módulo de administración no está disponible.");
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
        constants: core.constants,
        createPreferencesManager: core.createPreferencesManager,
        parsePreferences: core.parsePreferences,
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
