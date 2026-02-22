$REPO = "Mialra/Orarioo"
$ASSIGNEE = "@me"

function Create-Issue($title, $body, $milestone, $label1, $label2) {
    gh issue create `
        --repo $REPO `
        --title $title `
        --body $body `
        --milestone $milestone `
        --label $label1 `
        --label $label2 `
        --assignee $ASSIGNEE
}

# ==========================
# M1
# ==========================

Create-Issue "[1.1.1.1] Definir la arquitectura del sistema" "Diagramas UML de componentes y paquetes." "M1" "doc" "MVP"
Create-Issue "[1.1.1.2] Diseñar modelo de clases UML" "Diagrama UML de clases." "M1" "doc" "MVP"
Create-Issue "[1.1.1.3] Definir mockups" "Prototipos visuales de la interfaz." "M1" "doc" "MVP"
Create-Issue "[1.1.1.4] Revisión de diseño" "Verificación de resultados del diseño." "M1" "doc" "MVP"
Create-Issue "[1.1.1.5] Preparación entorno desarrollo" "Configuración inicial del proyecto." "M1" "feature" "MVP"
Create-Issue "[1.1.1.6] Implementar CI/CD" "Pipelines de integración y despliegue continuo." "M1" "feature" "MVP"
Create-Issue "[1.1.1.7] Carga inicial de datos" "Importación inicial de datos." "M1" "feature" "MVP"

# ==========================
# M2
# ==========================

Create-Issue "[1.1.2.1] Backend usuarios" "Autenticación y roles." "M2" "feature" "MVP"
Create-Issue "[1.1.2.2] Backend profesores" "CRUD profesores." "M2" "feature" "MVP"
Create-Issue "[1.1.2.3] Backend aulas" "CRUD aulas." "M2" "feature" "MVP"
Create-Issue "[1.1.2.4] Backend cursos" "CRUD cursos." "M2" "feature" "MVP"
Create-Issue "[1.1.2.5] Backend asignaturas" "CRUD asignaturas." "M2" "feature" "MVP"
Create-Issue "[1.1.2.6] Backend horarios" "CRUD horarios." "M2" "feature" "MVP"
Create-Issue "[1.1.2.7] Generación automática horarios" "Algoritmo con restricciones." "M2" "feature" "MVP"
Create-Issue "[1.1.2.8] Configuración seguridad" "Cifrado y control accesos." "M2" "feature" "MVP"

# ==========================
# M3
# ==========================

Create-Issue "[1.1.2.9] Backend sustituciones" "Recomendaciones automáticas." "M3" "feature" "extra"
Create-Issue "[1.1.2.10] Validaciones backend" "Reglas negocio y errores." "M3" "feature" "MVP"
Create-Issue "[1.1.3.1] Exportación horarios" "PDF y CSV." "M3" "feature" "MVP"
Create-Issue "[1.1.3.2] Auditoría" "Registro cambios." "M3" "feature" "MVP"
Create-Issue "[1.1.3.3] Exportación auditoría" "Exportar auditoría." "M3" "feature" "MVP"
Create-Issue "[1.1.3.4] Recordatorios" "Google Calendar." "M3" "feature" "extra"
Create-Issue "[1.1.3.5] Frontend responsive" "Interfaz adaptativa." "M3" "feature" "MVP"
Create-Issue "[1.1.3.6] Panel administración" "CRUD con permisos." "M3" "feature" "MVP"
Create-Issue "[1.1.3.7] Visualización horarios" "Consulta por filtros." "M3" "feature" "MVP"
Create-Issue "[1.1.3.8] Login frontend" "Formulario login." "M3" "feature" "MVP"
Create-Issue "[1.1.3.9] Multilenguaje" "Español e inglés." "M3" "feature" "extra"
Create-Issue "[1.1.3.10] Política privacidad" "Cumplimiento RGPD." "M3" "doc" "MVP"
Create-Issue "[1.1.3.11] Copias seguridad" "Exportación e importación completa." "M3" "feature" "extra"
Create-Issue "[1.1.3.12] Visualización sustituciones" "Aceptar/rechazar sugerencias." "M3" "feature" "extra"
Create-Issue "[1.1.3.13] Validaciones frontend" "Mensajes de error claros." "M3" "feature" "MVP"

# ==========================
# M4
# ==========================

Create-Issue "[1.1.4.1] Pruebas unitarias backend" "Testing backend." "M4" "doc" "MVP"
Create-Issue "[1.1.4.2] Pruebas frontend" "Testing frontend." "M4" "doc" "MVP"
Create-Issue "[1.1.4.3] Pruebas integración" "Interacción completa sistema." "M4" "doc" "MVP"
Create-Issue "[1.1.4.4] Documentación sprint" "Backlog, review y retrospective." "M4" "doc" "MVP"
Create-Issue "[1.1.4.5] Pruebas finales" "Verificación completa." "M4" "doc" "MVP"
Create-Issue "[1.1.4.6] Manual usuario" "Redacción manual." "M4" "doc" "MVP"
Create-Issue "[2.1.1.1] Registro incidencias" "Listado problemas proyecto." "M4" "doc" "MVP"
Create-Issue "[2.1.1.2] Registro decisiones" "Historial decisiones." "M4" "doc" "MVP"
Create-Issue "[2.1.1.3] Registro cambios" "Control modificaciones." "M4" "doc" "MVP"
Create-Issue "[2.1.2.1] Informes desempeño" "Informe diario." "M4" "doc" "MVP"
Create-Issue "[2.1.2.2] Seguimiento cronograma y costes" "Informe por sprint." "M4" "doc" "MVP"
Create-Issue "[3.1.1.1] Lecciones aprendidas" "Aprendizajes del proyecto." "M4" "doc" "MVP"
Create-Issue "[3.1.2.1] Informe cierre" "Informe final proyecto." "M4" "doc" "MVP"