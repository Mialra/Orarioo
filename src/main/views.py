from urllib.parse import unquote

from django.shortcuts import redirect, render

SECTION_CONFIG = {
    "schedules": {
        "title": "Horarios",
        "template": "main/tabs/schedules.html",
        "extra_css": ["css/schedules.css"],
        "extra_scripts": ["js/schedules.js"],
    },
    "saved": {
        "title": "Guardados",
        "template": "main/tabs/saved.html",
        "extra_css": ["css/schedules.css"],
        "extra_scripts": ["js/schedules.js"],
    },
    "audit": {
        "title": "Registro de cambios",
        "template": "main/tabs/audit.html",
        "extra_css": ["css/audit.css"],
        "extra_scripts": ["js/audit.js"],
    },
}

ADMIN_ROUTE_CONFIG = {
    "users": {
        "template": "administration_users.html",
        "extra_css": [],
        "extra_scripts": [
            "js/admin-core/dom-helpers.js",
            "js/admin-core/api.js",
            "js/admin-core/ui-state.js",
            "js/admin-core/form-utils.js",
            "js/admin-core/modal-utils.js",
            "js/admin-core/list-renderer.js",
            "js/admin-core/pagination.js",
            "js/admin-core/crud-module.js",
            "js/admin-base.js",
            "js/users.js",
        ],
    },
    "teachers": {
        "template": "administration_teachers.html",
        "extra_css": ["css/preferences-grid.css"],
        "extra_scripts": [
            "js/admin-core/dom-helpers.js",
            "js/admin-core/api.js",
            "js/admin-core/ui-state.js",
            "js/admin-core/form-utils.js",
            "js/admin-core/modal-utils.js",
            "js/admin-core/list-renderer.js",
            "js/admin-core/pagination.js",
            "js/admin-core/crud-module.js",
            "js/admin-base.js",
            "js/teachers.js",
        ],
    },
    "groups": {
        "template": "administration_groups.html",
        "extra_css": [],
        "extra_scripts": [
            "js/admin-core/dom-helpers.js",
            "js/admin-core/api.js",
            "js/admin-core/ui-state.js",
            "js/admin-core/form-utils.js",
            "js/admin-core/modal-utils.js",
            "js/admin-core/list-renderer.js",
            "js/admin-core/pagination.js",
            "js/admin-core/crud-module.js",
            "js/admin-base.js",
            "js/groups.js",
        ],
    },
    "subjects": {
        "template": "administration_subjects.html",
        "extra_css": ["css/preferences-grid.css"],
        "extra_scripts": [
            "js/admin-core/dom-helpers.js",
            "js/admin-core/api.js",
            "js/admin-core/ui-state.js",
            "js/admin-core/form-utils.js",
            "js/admin-core/modal-utils.js",
            "js/admin-core/list-renderer.js",
            "js/admin-core/pagination.js",
            "js/admin-core/crud-module.js",
            "js/admin-base.js",
            "js/subjects.js",
        ],
    },
    "classrooms": {
        "template": "administration_classrooms.html",
        "extra_css": [],
        "extra_scripts": [
            "js/admin-core/dom-helpers.js",
            "js/admin-core/api.js",
            "js/admin-core/ui-state.js",
            "js/admin-core/form-utils.js",
            "js/admin-core/modal-utils.js",
            "js/admin-core/list-renderer.js",
            "js/admin-core/pagination.js",
            "js/admin-core/crud-module.js",
            "js/admin-base.js",
            "js/classrooms.js",
        ],
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
    return redirect("sign-in")


def render_admin_dashboard(request, admin_tab, extra_context=None):
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
    return render(request, "legal/privacy_policy.html")
