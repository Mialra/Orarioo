from django.shortcuts import redirect, render

SECTION_CONFIG = {
    "schedules": {
        "title": "Horarios",
        "template": "main/tabs/schedules.html",
    },
    "saved": {
        "title": "Guardados",
        "template": "main/tabs/saved.html",
    },
    "audit": {
        "title": "Auditoría",
        "template": "main/tabs/audit.html",
    },
}

ADMIN_ROUTE_CONFIG = {
    "users": {
        "template": "administration_users.html",
        "extra_css": ["css/admin_users.css"],
        "extra_scripts": [
            "js/admin-core/dom-helpers.js",
            "js/admin-core/api.js",
            "js/admin-core/ui-state.js",
            "js/admin-core/form-utils.js",
            "js/admin-core/modal-utils.js",
            "js/admin-core/list-renderer.js",
            "js/admin-core/pagination.js",
            "js/admin-core/crud-module.js",
            "js/admin_users.js",
        ],
    },
    "teachers": {
        "template": "administration_teachers.html",
        "extra_css": [],
        "extra_scripts": [],
    },
    "groups": {
        "template": "administration_groups.html",
        "extra_css": [],
        "extra_scripts": [],
    },
    "subjects": {
        "template": "administration_subjects.html",
        "extra_css": [],
        "extra_scripts": [],
    },
    "classrooms": {
        "template": "administration_classrooms.html",
        "extra_css": [],
        "extra_scripts": [],
    },
}

ADMIN_BASE_CSS = [
    "css/administration_navigation.css",
]

ADMIN_TAB_CONFIG = {
    "users": {
        "title": "Gestión de Usuarios",
        "count_label": "0 usuarios registrados",
        "empty_message": "No hay usuarios registrados. Añade el primero para comenzar.",
        "add_cta": "Añadir Usuario",
    },
    "teachers": {
        "title": "Gestión de Profesores",
        "count_label": "0 profesores registrados",
        "empty_message": "No hay profesores registrados. Añade el primero para comenzar.",
        "add_cta": "Añadir Profesor",
    },
    "groups": {
        "title": "Gestión de Cursos",
        "count_label": "0 cursos registrados",
        "empty_message": "No hay cursos registrados. Añade el primero para comenzar.",
        "add_cta": "Añadir Curso",
    },
    "subjects": {
        "title": "Gestión de Asignaturas",
        "count_label": "0 asignaturas registradas",
        "empty_message": "No hay asignaturas registradas. Añade la primera para comenzar.",
        "add_cta": "Añadir Asignatura",
    },
    "classrooms": {
        "title": "Gestión de Aulas",
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
    }

    if extra_context:
        context.update(extra_context)

    return render(
        request,
        "main/tabs/dashboard.html",
        context,
    )


def dashboard(request, section="schedules"):
    current_section = section if section in SECTION_CONFIG else "schedules"
    route_config = SECTION_CONFIG[current_section]

    return render(
        request,
        "main/tabs/dashboard.html",
        {
            "dashboard_section": current_section,
            "dashboard_section_title": route_config["title"],
            "dashboard_route_template": route_config["template"],
            "dashboard_extra_css": [],
            "dashboard_extra_scripts": [],
        },
    )
