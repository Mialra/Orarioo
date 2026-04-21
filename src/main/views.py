"""
Core view functions: root redirect, dashboard sections, admin tab renderer, and legal pages.
"""

from urllib.parse import unquote

from django.shortcuts import redirect, render

_SCHEDULE_SCRIPTS = [
    "js/schedule-utils.js",
    "js/schedule-board.js",
    "js/schedule-filter-dropdown.js",
    "js/schedule-workspace.js",
    "js/schedule-analysis.js",
    "js/schedule-saved.js",
    "js/schedule-export.js",
    "js/schedules.js",
]

SECTION_CONFIG = {
    "schedules": {
        "title": "Horarios",
        "template": "main/tabs/schedules.html",
        "extra_css": ["css/schedules.css"],
        "extra_scripts": _SCHEDULE_SCRIPTS,
    },
    "saved": {
        "title": "Guardados",
        "template": "main/tabs/saved.html",
        "extra_css": ["css/schedules.css"],
        "extra_scripts": _SCHEDULE_SCRIPTS,
    },
    "audit": {
        "title": "Registro de cambios",
        "template": "main/tabs/audit.html",
        "extra_css": ["css/audit.css"],
        "extra_scripts": ["js/audit.js"],
    },
}

_ADMIN_CORE_SCRIPTS = [
    "js/admin-core/constants.js",
    "js/admin-core/dom-helpers.js",
    "js/admin-core/api.js",
    "js/admin-core/ui-state.js",
    "js/admin-core/form-utils.js",
    "js/admin-core/modal-utils.js",
    "js/admin-core/list-renderer.js",
    "js/admin-core/pagination.js",
    "js/admin-core/preferences-manager.js",
    "js/admin-core/crud-module.js",
    "js/admin-base.js",
]

ADMIN_ROUTE_CONFIG = {
    "users": {
        "template": "administration_users.html",
        "extra_css": [],
        "extra_scripts": [*_ADMIN_CORE_SCRIPTS, "js/users.js"],
    },
    "teachers": {
        "template": "administration_teachers.html",
        "extra_css": ["css/preferences-grid.css"],
        "extra_scripts": [*_ADMIN_CORE_SCRIPTS, "js/teachers.js"],
    },
    "groups": {
        "template": "administration_groups.html",
        "extra_css": [],
        "extra_scripts": [*_ADMIN_CORE_SCRIPTS, "js/groups.js"],
    },
    "subjects": {
        "template": "administration_subjects.html",
        "extra_css": ["css/preferences-grid.css"],
        "extra_scripts": [*_ADMIN_CORE_SCRIPTS, "js/subjects.js"],
    },
    "classrooms": {
        "template": "administration_classrooms.html",
        "extra_css": [],
        "extra_scripts": [*_ADMIN_CORE_SCRIPTS, "js/classrooms.js"],
    },
}

ADMIN_BASE_CSS = [
    "css/administration_navigation.css",
    "css/admin.css",
]

ADMIN_TAB_CONFIG = {
    "users": {
        "title": "Usuarios del equipo",
        "description": "Consulta los usuarios de tu equipo activo.",
        "count_label": "0 usuarios en el equipo activo",
        "empty_message": "No hay usuarios en el equipo activo.",
    },
    "teachers": {
        "title": "Gestión de Profesores",
        "description": "Administra el personal docente y su disponibilidad.",
        "count_label": "0 profesores registrados",
        "empty_message": "No hay profesores registrados. Añade el primero para comenzar.",
        "add_cta": "Añadir Profesor",
    },
    "groups": {
        "title": "Gestión de Cursos",
        "description": "Administra los grupos y cursos académicos.",
        "count_label": "0 cursos registrados",
        "empty_message": "No hay cursos registrados. Añade el primero para comenzar.",
        "add_cta": "Añadir Curso",
    },
    "subjects": {
        "title": "Gestión de Asignaturas",
        "description": "Administra las asignaturas y sus relaciones académicas.",
        "count_label": "0 asignaturas registradas",
        "empty_message": "No hay asignaturas registradas. Añade la primera para comenzar.",
        "add_cta": "Añadir Asignatura",
    },
    "classrooms": {
        "title": "Gestión de Aulas",
        "description": "Administra las aulas disponibles para el horario.",
        "count_label": "0 aulas registradas",
        "empty_message": "No hay aulas registradas. Añade la primera para comenzar.",
        "add_cta": "Añadir Aula",
    },
}


def root_redirect(request):
    """Redirect the root URL to the sign-in page.
    Input: request - the incoming HTTP request
    Output: HTTP redirect response to the sign-in URL
    """
    return redirect("sign-in")


def render_admin_dashboard(request, admin_tab, extra_context=None):
    """Render the administration dashboard for the given tab.
    Input: request - the incoming HTTP request; admin_tab - key from ADMIN_TAB_CONFIG;
           extra_context - optional dict merged into the template context
    Output: HTTP response rendering main/tabs/dashboard.html with administration context
    """
    current_admin_tab = admin_tab if admin_tab in ADMIN_TAB_CONFIG else "users"
    route_config = ADMIN_ROUTE_CONFIG[current_admin_tab]
    context = {
        "dashboard_section": "administration",
        "dashboard_section_title": "Administración",
        "dashboard_admin_tab": current_admin_tab,
        "dashboard_admin_state": ADMIN_TAB_CONFIG[current_admin_tab],
        "dashboard_route_template": route_config["template"],
        "dashboard_extra_css": ADMIN_BASE_CSS + route_config["extra_css"],
        "dashboard_extra_scripts": route_config["extra_scripts"],
        "show_authenticated_footer": True,
    }

    if extra_context:
        context.update(extra_context)

    return render(
        request,
        "main/tabs/dashboard.html",
        context,
    )


def dashboard(request, section="schedules", timetable_name=""):
    """Render the main dashboard for the given section.
    Input: request - the incoming HTTP request; section - key from SECTION_CONFIG;
           timetable_name - URL-encoded timetable name used only in the 'saved' section
    Output: HTTP response rendering main/tabs/dashboard.html with section context
    """
    current_section = section if section in SECTION_CONFIG else "schedules"
    route_config = SECTION_CONFIG[current_section]
    selected_saved_timetable = ""

    if current_section == "saved" and timetable_name:
        selected_saved_timetable = unquote(str(timetable_name)).strip()

    return render(
        request,
        "main/tabs/dashboard.html",
        {
            "dashboard_section": current_section,
            "dashboard_section_title": route_config["title"],
            "dashboard_route_template": route_config["template"],
            "dashboard_extra_css": route_config.get("extra_css", []),
            "dashboard_extra_scripts": route_config.get("extra_scripts", []),
            "dashboard_saved_timetable_name": selected_saved_timetable,
            "show_authenticated_footer": True,
        },
    )


def privacy_policy(request):
    """Render the privacy policy legal page.
    Input: request - the incoming HTTP request
    Output: HTTP response rendering legal/privacy_policy.html
    """
    return render(request, "legal/privacy_policy.html")


def terms_and_conditions(request):
    """Render the terms and conditions legal page.
    Input: request - the incoming HTTP request
    Output: HTTP response rendering legal/terms_and_conditions.html
    """
    return render(request, "legal/terms_and_conditions.html")


def security_protocol(request):
    """Render the security protocol legal page.
    Input: request - the incoming HTTP request
    Output: HTTP response rendering legal/security_protocol.html
    """
    return render(request, "legal/security_protocol.html")
