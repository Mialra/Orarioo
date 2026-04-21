/**
 * Schedule analysis: calls the constraint-analysis backend endpoint and renders
 * defects in a Bootstrap modal.
 * Output: window.ScheduleAnalysis — { analyzeSchedules, showAnalysisModal }
 */
(function () {
  /**
   * Calls the backend analysis endpoint and returns the defect list or an error object.
   * Input: scheduleIds - array of integer schedule IDs
   *        apiJson     - authenticated HTTP function (path, method, body) => Promise<{ok, data}>
   * Output: Promise resolving to defect[] or { error: true, message: string }
   */
  async function analyzeSchedules(scheduleIds, apiJson) {
    const result = await apiJson("/schedules/analyze/", "POST", {
      schedule_ids: scheduleIds,
    });

    if (!result.ok) {
      return { error: true, message: (result.data && result.data.detail) || "Error desconocido" };
    }

    return (result.data && result.data.defects) || [];
  }

  /**
   * Creates (or reuses) a Bootstrap modal, fills it with the analysis result, and opens it.
   * Input: scheduleIds - array of integer schedule IDs to analyze
   *        modalId     - DOM id to use for the modal element
   *        modalTitle  - string shown in the modal header
   *        contentId   - DOM id of the content container inside the modal body
   *        apiJson     - authenticated HTTP function passed to analyzeSchedules
   * Output: void; opens the modal as a side effect
   */
  async function showAnalysisModal(scheduleIds, modalId, modalTitle, contentId, apiJson) {
    const result = await analyzeSchedules(scheduleIds, apiJson);

    let modal = document.getElementById(modalId);
    if (!modal) {
      modal = document.createElement("div");
      modal.id = modalId;
      modal.className = "modal fade";
      modal.setAttribute("tabindex", "-1");
      modal.setAttribute("aria-hidden", "true");
      modal.innerHTML =
        '<div class="modal-dialog modal-dialog-centered modal-lg">' +
        '<div class="modal-content">' +
        '<div class="modal-header">' +
        '<h5 class="modal-title">' + modalTitle + "</h5>" +
        '<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Cerrar"></button>' +
        "</div>" +
        '<div class="modal-body"><div id="' + contentId + '"></div></div>' +
        '<div class="modal-footer">' +
        '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cerrar</button>' +
        "</div></div></div>";
      document.body.appendChild(modal);
    }

    const content = modal.querySelector("#" + contentId);
    if (!content) {
      return;
    }

    const escapeHtml =
      window.OrariooErrorHandler && window.OrariooErrorHandler.escapeHtml
        ? window.OrariooErrorHandler.escapeHtml
        : function (s) { return String(s || ""); };

    if (result.error) {
      content.innerHTML =
        '<div class="alert alert-danger" role="alert">Se ha producido un error analizando el horario. Por favor, inténtelo de nuevo.</div>';
    } else if (!Array.isArray(result) || result.length === 0) {
      content.innerHTML =
        '<p class="text-success text-center py-4">El horario parece estar bien distribuido sin problemas evidentes.</p>';
    } else {
      var html =
        '<h6 class="mb-3">Se encontraron los siguientes problemas:</h6>' +
        '<ul style="list-style: none; padding: 0;">';

      result.forEach(function (defect) {
        html +=
          '<li style="margin-bottom: 12px; padding: 12px; background: #fff8f0; border-left: 3px solid #ff9800; border-radius: 4px;">' +
          '<strong style="color: #d97706;">' + escapeHtml(defect.entity_name) + "</strong><br>" +
          '<small style="color: #92400e;">' + escapeHtml(defect.description) + "</small>" +
          "</li>";
      });

      html += "</ul>";
      content.innerHTML = html;
    }

    if (window.bootstrap && window.bootstrap.Modal) {
      new window.bootstrap.Modal(modal).show();
    }
  }

  window.ScheduleAnalysis = {
    analyzeSchedules: analyzeSchedules,
    showAnalysisModal: showAnalysisModal,
  };
})();
