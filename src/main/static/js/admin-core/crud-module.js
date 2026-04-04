(function () {
    const root = window.OrariooAdmin = window.OrariooAdmin || {};
    const api = root.api;
    const uiState = root.uiState;
    const formUtils = root.formUtils;
    const modalUtils = root.modalUtils;
    const listRenderer = root.listRenderer;
    const pagination = root.pagination;

    function toItemMap(items, getId) {
        return (items || []).reduce(function (acc, item) {
            acc[String(getId(item))] = item;
            return acc;
        }, {});
    }

    function defaultParseList(data) {
        if (Array.isArray(data)) {
            return data;
        }
        if (data && Array.isArray(data.results)) {
            return data.results;
        }
        return [];
    }

    function initCrudModule(config) {
        const state = {
            itemsById: {},
            pendingDeleteId: "",
            allItems: [],
            currentItems: [],
        };

        const getId = config.getItemId || function (item) { return item.id; };
        const parseList = config.parseList || defaultParseList;

        const listContainer = config.list.container;
        const paginationContainer = config.list.paginationContainer || null;
        const alertBox = config.alertElement;
        const useServerPagination = config.list.serverPagination !== false;
        const pageQueryKey = config.list.pageQueryKey || "page";
        const pageSizeQueryKey = config.list.pageSizeQueryKey || "page_size";
        const syncPageInUrl = config.list.syncPageInUrl !== false;
        const paginationController = pagination && pagination.createPaginationController
            ? pagination.createPaginationController({
                container: paginationContainer,
                pageSize: config.list.pageSize || 5,
            })
            : null;

        const formController = modalUtils.createFormModalController({
            modalElement: config.form.modalElement,
            modeInput: config.form.modeInput,
            titleElement: config.form.titleElement,
            submitTextElement: config.form.submitTextElement,
            labels: config.form.labels,
        });

        const confirmController = modalUtils.createConfirmModalController({
            modalElement: config.deleteConfirm.modalElement,
            nameElement: config.deleteConfirm.nameElement,
            actionTextElement: config.deleteConfirm.actionTextElement,
            labels: config.deleteConfirm.labels,
        });

        function setSubmitLoading(isLoading) {
            const submitButton = config.form.submitButton;
            const submitSpinner = config.form.submitSpinner;
            const submitText = config.form.submitTextElement;
            if (!submitButton) {
                return;
            }
            submitButton.disabled = isLoading;
            if (submitSpinner) {
                submitSpinner.classList.toggle("d-none", !isLoading);
            }
            if (submitText && isLoading) {
                submitText.textContent = config.form.messages.saving;
            }
        }

        function setDeleteLoading(isLoading) {
            const deleteButton = config.deleteConfirm.confirmButton;
            const deleteSpinner = config.deleteConfirm.spinnerElement;
            if (!deleteButton) {
                return;
            }
            deleteButton.disabled = isLoading;
            if (deleteSpinner) {
                deleteSpinner.classList.toggle("d-none", !isLoading);
            }
        }

        function clearFormUiState() {
            formUtils.clearErrors(config.form.fields);
            setSubmitLoading(false);
            config.form.resetValues();
        }

        function renderCurrentPage() {
            const sourceItems = useServerPagination ? state.currentItems : state.allItems;

            if (!sourceItems.length) {
                uiState.renderEmptyState(listContainer, {
                    icon: config.list.emptyIcon,
                    title: config.list.emptyTitle,
                    message: config.list.emptyMessage,
                });
                if (paginationContainer) {
                    paginationContainer.innerHTML = "";
                }
                return;
            }

            const pageItems = useServerPagination
                ? sourceItems
                : (paginationController ? paginationController.getPageSlice(sourceItems) : sourceItems);

            listRenderer.renderCollection(listContainer, pageItems, function (item) {
                return config.renderItem(item);
            });
            uiState.refreshIconsIfNeeded(listContainer);

            if (paginationController) {
                paginationController.render(function (nextPage) {
                    if (useServerPagination) {
                        fetchList(nextPage);
                    } else {
                        renderCurrentPage();
                    }
                });
            }
        }

        function getInitialPageFromRoute() {
            const params = new URLSearchParams(window.location.search);
            const raw = Number(params.get(pageQueryKey));
            if (!Number.isFinite(raw) || raw < 1) {
                return 1;
            }
            return Math.floor(raw);
        }

        function syncRoutePage(page) {
            if (!syncPageInUrl) {
                return;
            }
            const url = new URL(window.location.href);
            if (page <= 1) {
                url.searchParams.delete(pageQueryKey);
            } else {
                url.searchParams.set(pageQueryKey, String(page));
            }
            window.history.replaceState({}, "", url.toString());
        }

        function buildListUrl(page) {
            if (typeof config.list.buildPageUrl === "function") {
                return config.list.buildPageUrl(page, paginationController ? paginationController.pageSize : config.list.pageSize);
            }
            const url = new URL(config.endpoint, window.location.origin);
            if (useServerPagination) {
                url.searchParams.set(pageQueryKey, String(page));
                if (pageSizeQueryKey && paginationController && paginationController.pageSize) {
                    url.searchParams.set(pageSizeQueryKey, String(paginationController.pageSize));
                }
            }
            return url.pathname + url.search;
        }

        async function fetchList(requestedPage) {
            const targetPage = requestedPage || (paginationController ? paginationController.getCurrentPage() : 1);
            uiState.setBusy(listContainer, true);
            uiState.renderLoadingState(listContainer, config.list.loadingMessage);

            const response = await api.get(buildListUrl(targetPage));
            if (!response.ok) {
                uiState.showAlert(alertBox, config.messages.loadError, "danger");
                uiState.renderEmptyState(listContainer, {
                    icon: config.list.emptyIcon,
                    title: config.list.emptyTitle,
                    message: config.list.emptyMessage,
                });
                uiState.setBusy(listContainer, false);
                return;
            }

            if (Array.isArray(response.data)) {
                state.allItems = response.data;
                state.currentItems = response.data;
                state.itemsById = toItemMap(response.data, getId);

                if (paginationController) {
                    paginationController.setTotalItems(response.data.length);
                    paginationController.setPage(targetPage);
                }
                renderCurrentPage();
                uiState.setBusy(listContainer, false);
                return;
            }

            const pageItems = parseList(response.data);
            const totalItems = response.data && typeof response.data.count === "number"
                ? response.data.count
                : pageItems.length;

            state.currentItems = pageItems;
            state.itemsById = toItemMap(pageItems, getId);

            if (paginationController) {
                paginationController.setTotalItems(totalItems);
                paginationController.setPage(targetPage);
            }

            syncRoutePage(paginationController ? paginationController.getCurrentPage() : targetPage);
            renderCurrentPage();
            uiState.setBusy(listContainer, false);
        }

        async function openEdit(id) {
            let item = state.itemsById[String(id)] || null;
            if (!item && config.getDetailEndpoint) {
                const response = await api.get(config.getDetailEndpoint(id));
                if (response.ok) {
                    item = response.data;
                    state.itemsById[String(id)] = item;
                }
            }

            if (!item) {
                uiState.showAlert(alertBox, config.messages.loadItemError, "danger");
                return;
            }

            formController.setMode("edit");
            config.form.setEditingId(id);
            config.form.fillValues(item);
            formUtils.clearErrors(config.form.fields);
            formController.show();
            if (config.form.focusInput) {
                config.form.focusInput.focus();
            }
        }

        function openCreate() {
            formController.setMode("create");
            config.form.setEditingId("");
            clearFormUiState();
            formController.show();
        }

        async function submitForm(event) {
            event.preventDefault();
            uiState.hideAlert(alertBox);

            const payload = config.form.buildPayload();
            const isValid = formUtils.validateFields(config.form.fields, payload);
            if (!isValid) {
                uiState.showAlert(alertBox, config.messages.validationError, "warning");
                return;
            }

            setSubmitLoading(true);

            const isEdit = formController.getMode() === "edit" && config.form.getEditingId();
            const response = isEdit
                ? await api.patch(config.getDetailEndpoint(config.form.getEditingId()), payload)
                : await api.post(config.createEndpoint || config.endpoint, payload);

            if (!response.ok) {
                formUtils.applyServerErrors(config.form.fields, response.data);
                const detail = response.data && response.data.detail;
                uiState.showAlert(alertBox, detail || config.messages.saveError, "danger");
                setSubmitLoading(false);
                return;
            }

            clearFormUiState();
            formController.hide();
            uiState.showAlert(alertBox, isEdit ? config.messages.updated : config.messages.created, "success");
            const pageToReload = isEdit && paginationController ? paginationController.getCurrentPage() : 1;
            await fetchList(pageToReload);
            setSubmitLoading(false);
        }

        function openDelete(id) {
            state.pendingDeleteId = String(id);
            const item = state.itemsById[state.pendingDeleteId] || null;
            const name = item ? config.getItemName(item) : "";
            confirmController.open(state.pendingDeleteId, name);
        }

        async function confirmDelete() {
            const id = confirmController.getPendingId();
            if (!id) {
                return;
            }

            setDeleteLoading(true);
            const response = await api.del(config.getDetailEndpoint(id));

            if (!response.ok) {
                uiState.showAlert(alertBox, config.messages.deleteError, "danger");
                setDeleteLoading(false);
                return;
            }

            confirmController.hide();
            confirmController.clear();
            setDeleteLoading(false);
            uiState.showAlert(alertBox, config.messages.deleted, "success");

            let pageToReload = paginationController ? paginationController.getCurrentPage() : 1;
            if (useServerPagination && paginationController && state.currentItems.length === 1 && pageToReload > 1) {
                pageToReload -= 1;
            }
            await fetchList(pageToReload);
        }

        function handleListClick(event) {
            const row = event.target.closest(config.list.rowSelector);
            if (!row) {
                return;
            }
            const id = row.dataset[config.list.rowIdDataset];
            if (!id) {
                return;
            }

            if (event.target.closest(config.list.editSelector)) {
                openEdit(id);
                return;
            }
            if (event.target.closest(config.list.deleteSelector)) {
                openDelete(id);
            }
        }

        if (config.addButton) {
            config.addButton.addEventListener("click", openCreate);
        }

        config.form.formElement.addEventListener("submit", submitForm);

        if (config.form.cancelButton) {
            config.form.cancelButton.addEventListener("click", function () {
                clearFormUiState();
                uiState.hideAlert(alertBox);
            });
        }

        if (formController.element) {
            formController.element.addEventListener("hidden.bs.modal", function () {
                clearFormUiState();
                uiState.hideAlert(alertBox);
            });
        }

        if (confirmController.element) {
            confirmController.element.addEventListener("hidden.bs.modal", function () {
                state.pendingDeleteId = "";
                confirmController.clear();
                setDeleteLoading(false);
            });
        }

        if (listContainer) {
            listContainer.addEventListener("click", handleListClick);
        }

        if (config.deleteConfirm.confirmButton) {
            config.deleteConfirm.confirmButton.addEventListener("click", confirmDelete);
        }

        (config.form.clearValidationOnInput || []).forEach(function (entry) {
            entry.input.addEventListener(entry.event || "input", function () {
                formUtils.clearFieldError(entry.input, entry.feedback);
            });
        });

        const initialPage = getInitialPageFromRoute();
        if (paginationController) {
            paginationController.setPage(initialPage);
        }
        fetchList(initialPage);
    }

    root.initCrudModule = initCrudModule;
})();
