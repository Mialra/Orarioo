from django.shortcuts import redirect, render

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


def render_admin_dashboard(request, admin_tab):
    current_admin_tab = admin_tab if admin_tab in ADMIN_TAB_CONFIG else "users"

    return render(
        request,
        "main/dashboard.html",
        {
            "dashboard_section": "administration",
            "dashboard_section_title": "Administración",
            "dashboard_admin_tab": current_admin_tab,
            "dashboard_admin_state": ADMIN_TAB_CONFIG[current_admin_tab],
        },
    )


def dashboard(request, section="schedules"):
    allowed_sections = {
        "schedules": "Horarios",
        "saved": "Guardados",
        "audit": "Auditoría",
    }

    current_section = section if section in allowed_sections else "schedules"

    return render(
        request,
        "main/dashboard.html",
        {
            "dashboard_section": current_section,
            "dashboard_section_title": allowed_sections[current_section],
        },
    )
