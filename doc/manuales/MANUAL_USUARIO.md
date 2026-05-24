# Manual de Usuario — Orarioo

## Índice

0. [Introducción](#0-introducción)
1. [Primeros pasos: Registro y acceso](#1-primeros-pasos-registro-y-acceso)
2. [Configuración inicial del centro](#2-configuración-inicial-del-centro)
3. [Equipos de colaboración](#3-equipos-de-colaboración)
4. [Administración de profesores](#4-administración-de-profesores)
5. [Administración de cursos](#5-administración-de-cursos)
6. [Administración de aulas](#6-administración-de-aulas)
7. [Administración de asignaturas](#7-administración-de-asignaturas)
8. [Generación automática del horario](#8-generación-automática-del-horario)
9. [Gestión de horarios guardados](#9-gestión-de-horarios-guardados)
10. [Visualización y edición del horario](#10-visualización-y-edición-del-horario)
11. [Registro de cambios (Auditoría)](#11-registro-de-cambios-auditoría)
12. [Gestión de la cuenta](#12-gestión-de-la-cuenta)
13. [Preguntas frecuentes](#13-preguntas-frecuentes)

## 0. Introducción

Orarioo es una herramienta web para la gestión y generación automática de horarios escolares. A partir de los datos de tu centro (profesores, cursos, asignaturas, aulas y tramos), su algoritmo genera horarios completos respetando las disponibilidades y preferencias que hayas configurado.

Este manual está dirigido al personal de administración y dirección de centros educativos que utiliza Orarioo para crear y gestionar los horarios del equipo. No se requieren conocimientos técnicos.

El manual está organizado siguiendo el flujo natural de trabajo: desde el registro y la configuración del centro hasta la generación, edición y exportación del horario. Si es la primera vez que usas Orarioo, te recomendamos seguirlo en orden, ya que cada sección da por hecho que las anteriores están configuradas.

---

## 1. Primeros pasos: Registro y acceso

Esta sección cubre todo lo relacionado con la creación de tu cuenta en Orarioo y el acceso a la plataforma. Después de registrarte, la aplicación te guiará por un asistente inicial para configurar tu centro.

### 1.1 Registro de usuario

1. Ve a la página de inicio de Orarioo (https://orarioo.onrender.com/) y haz clic en **Regístrate**.
2. Completa el formulario con los siguientes datos:
   - **Nombre**
   - **Apellidos** _(opcional)_
   - **Correo electrónico**
   - **Contraseña**: mínimo 8 caracteres, incluyendo al menos una letra y un número.
   - **Confirmar contraseña**
3. Revisa la **Política de Privacidad** y **Términos y Condiciones de Uso**.
4. Si estás de acuerdo, marca las casillas.
5. Haz clic en **Crear cuenta**.

ℹ️ **Nota:** El botón **Crear cuenta** permanece desactivado hasta que ambas casillas de aceptación estén marcadas.

![alt text](/doc/manuales/img/register.png)
_Figura 1. Formulario de registro de nuevo usuario._

### 1.2 Inicio de sesión

1. Ve a la página de inicio de Orarioo.
2. Introduce tu **Correo electrónico** y **Contraseña**.
3. Haz clic en **Iniciar sesión**.

ℹ️ **Nota:** Puedes usar el botón del ojo junto al campo de contraseña para mostrar u ocultar los caracteres que escribes.

### 1.3 Cierre de sesión

1. En cualquier pantalla de la aplicación, haz clic en tu avatar (iniciales) en la esquina superior derecha.
2. En el menú desplegable, selecciona **Cerrar sesión**.

---

## 2. Configuración inicial del centro

La primera vez que creas un equipo, Orarioo te guía por un asistente de dos pasos para configurar el centro educativo. Esta configuración determina los tramos horarios que usará el generador de horarios.

### 2.1 Paso 1: Nombre del centro

1. Introduce el **Nombre del centro**, por ejemplo: "IES Ejemplo".
2. Haz clic en **Continuar →**.

![alt text](/doc/manuales/img/onboarding_school.png)
_Figura 2. Paso 1 del asistente inicial: nombre del centro._

### 2.2 Paso 2: Configurar etapas educativas

En este paso defines los tramos horarios para cada etapa educativa de tu centro. Las etapas predefinidas son **Infantil**, **Primaria**, **ESO** y **Bachillerato**, pero puedes añadir etapas personalizadas.

**Para añadir una etapa:**

1. Haz clic en **+ Añadir etapa**.
2. Introduce el **Nombre** de la etapa, por ejemplo: "FP Básica".
3. Selecciona un **Color** para identificar visualmente la etapa en los horarios.
4. Haz clic en **Crear etapa**.

**Para configurar los tramos de cada etapa:**

Dentro de cada etapa, define:

- **Hora de entrada** y **hora de salida**.
- **Recreos**: hora de inicio y hora de fin de cada recreo. Puedes añadir tantos recreos como tenga la etapa.

Una vez configuradas todas las etapas, haz clic en **Guardar y continuar →**.

ℹ️ **Nota:** Puedes saltar este paso haciendo clic en **Saltar paso** y configurar los tramos más adelante desde la sección **Administración**.

![alt text](/doc/manuales/img/onboarding_stages.png)
_Figura 3. Paso 2 del asistente inicial: configuración de etapas educativas y tramos horarios._

### 2.3 Modificar los tramos horarios después de la configuración inicial

Si necesitas ajustar los tramos horarios una vez finalizada la configuración inicial:

1. Accede a la sección **Administración** desde la barra de navegación superior.
2. Selecciona la pestaña **Tramos** para configurar las etapas.

---

## 3. Equipos de colaboración

Los equipos de colaboración son la unidad de trabajo en Orarioo. Todos los datos del centro (profesores, cursos, asignaturas, aulas y horarios) pertenecen a un equipo. Todos los miembros de un equipo tienen acceso completo a sus datos. Puedes pertenecer a varios equipos y cambiar entre ellos en cualquier momento.

### 3.1 Crear un equipo

1. Haz clic en tu avatar en la barra de navegación superior.
2. En el menú desplegable, selecciona **Crear equipo**.
3. Introduce el **Nombre del equipo**, por ejemplo: "Equipo de Jefatura".
4. Haz clic en **Crear**.

ℹ️ **Nota:** Si es la primera vez que accedes tras registrarte, la aplicación te llevará automáticamente al asistente de configuración inicial, donde crearás tu primer equipo.

### 3.2 Cambiar de equipo activo

1. Haz clic en tu avatar en la barra de navegación superior.
2. En la sección **Cambiar de equipo**, verás la lista de equipos a los que perteneces.
3. Haz clic en el nombre del equipo al que quieres cambiar.

ℹ️ **Nota:** El nombre del equipo activo aparece siempre en la parte superior del menú, bajo la etiqueta **Equipo actual**.

### 3.3 Invitar usuarios al equipo

1. Haz clic en tu avatar en la barra de navegación superior.
2. Selecciona **Invitar usuarios**.
3. Introduce el **Email del usuario existente**. El usuario debe tener ya una cuenta en Orarioo.
4. Haz clic en **Enviar invitación**.

ℹ️ **Nota:** La invitación solo se enviará si el correo electrónico corresponde a una cuenta registrada en Orarioo.

![alt text](/doc/manuales/img/invite_user.png)
_Figura 4. Formulario para invitar a un usuario al equipo._

### 3.4 Ver invitaciones recibidas y responder

1. Haz clic en tu avatar en la barra de navegación superior.
2. Selecciona **Ver invitaciones pendientes**. El número junto al botón indica cuántas tienes sin revisar.
3. Para cada invitación pendiente, puedes **aceptar** o **rechazar**.

![alt text](/doc/manuales/img/invite_pending.png)

_Figura 5. Lista de invitaciones pendientes de respuesta._

### 3.5 Ver miembros del equipo

1. Haz clic en **Administración** en la barra de navegación superior.
2. Selecciona **Usuarios**.

Verás el listado de todos los miembros que pertenecen al equipo activo.

### 3.6 Abandonar el equipo

1. Haz clic en tu avatar en la barra de navegación superior.
2. Selecciona **Salir del equipo**.
3. Lee el aviso de confirmación y haz clic en **Confirmar y salir**.

⚠️ **Advertencia:** Si eres el último miembro del equipo, al salir se eliminarán permanentemente todos los datos del equipo: horarios, cursos, asignaturas, profesores y aulas. Esta acción no se puede deshacer.

ℹ️ **Nota:** Para volver a un equipo que has abandonado, necesitarás que otro miembro te invite de nuevo.

---

## 4. Administración de profesores

Antes de generar un horario, debes dar de alta a todos los profesores del centro con su carga lectiva semanal. Además, puedes definir su disponibilidad y preferencias horarias para que el algoritmo las tenga en cuenta.

Accede a esta sección desde **Administración → Profesores** en la barra de navegación superior.

![alt text](/doc/manuales/img/teachers_tab.png)
_Figura 6. Pantalla de administración de profesores._

### 4.1 Crear un profesor

1. Haz clic en el botón **Añadir profesor**.
2. Completa el formulario:
   - **Nombre**
   - **Apellidos** _(opcional)_
   - Selecciona el modo de carga semanal:
     - **Hasta un máximo**: el profesor puede tener hasta esa carga, pero el algoritmo no está obligado a asignarle exactamente ese total.
     - **Exactamente**: el algoritmo intentará asignarle exactamente ese número de horas. Si no es posible, se mostrará una advertencia de horas no cumplidas.
   - Configura la **Disponibilidad semanal** usando la cuadrícula:
     - Selecciona el estado a pintar en el desplegable **Estado a pintar**:
       - **Preferiblemente sí**: franja preferida por el profesor.
       - **Disponible**: el profesor puede dar clase en ese tramo.
       - **Preferiblemente no**: el profesor prefiere no impartir en ese tramo.
       - **No disponible**: el profesor no puede dar clase en ese tramo.
     - Haz clic en una celda individual para aplicar el estado seleccionado a ese tramo.
     - Haz clic en el encabezado de un **día** (por ejemplo, "Lunes") para rellenar de golpe todos los tramos de ese día con el estado seleccionado.
     - Haz clic en el encabezado de una **hora** para rellenar todos los días de esa franja horaria con el estado seleccionado.
     - Haz clic en **Reiniciar cuadrícula** para borrar toda la disponibilidad y empezar de nuevo.
3. Haz clic en **Crear**.

ℹ️ **Nota:** El nombre de cada elemento (profesor, curso, asignatura o aula) debe ser único dentro del equipo. No pueden existir dos elementos del mismo tipo con el mismo nombre (la comparación no distingue mayúsculas de minúsculas).

![alt text](/doc/manuales/img/teachers_create.png)

_Figura 7. Modal de creación de profesor con cuadrícula de disponibilidad semanal._

### 4.2 Ver el detalle y editar un profesor

1. Localiza al profesor en la lista.
2. Haz clic en su icono de edición (lápiz).
3. Modifica los campos que necesites.
4. Haz clic en **Guardar**.

### 4.3 Eliminar un profesor

1. Localiza al profesor en la lista.
2. Haz clic en el icono de eliminar (papelera).
3. Confirma la acción en el diálogo de confirmación.

⚠️ **Advertencia:** Eliminar un profesor también eliminará todas las asignaturas asociadas a ese profesor y las sesiones de horario vinculadas. Esta acción no se puede deshacer.

---

## 5. Administración de cursos

Los cursos representan los cursos del centro (por ejemplo, "1º ESO A", "3º Primaria"). Cada curso pertenece a una etapa educativa, lo que determina su tramo horario.

Accede a esta sección desde **Administración → Cursos** en la barra de navegación superior.

![alt text](/doc/manuales/img/groups_tab.png)
_Figura 8. Pantalla de administración de cursos._

### 5.1 Crear un curso

1. Haz clic en **Añadir curso**.
2. Completa el formulario:
   - **Nombre**: por ejemplo, "1º ESO".
   - **Etapa educativa**: Infantil, Primaria, ESO, Bachillerato u otra etapa personalizada.
3. Haz clic en **Crear**.

![alt text](/doc/manuales/img/groups_create.png)
_Figura 9. Modal de creación de curso._

### 5.2 Listar, ver detalle, editar y eliminar cursos

El proceso es idéntico al descrito para profesores (apartados 4.2 y 4.3).

⚠️ **Advertencia:** Eliminar un curso también eliminará todas las asignaturas y sesiones de horario asociadas a ese curso. Esta acción no se puede deshacer.

---

## 6. Administración de aulas

Las aulas son los espacios físicos donde se imparten las clases. El generador las asigna automáticamente a las sesiones, garantizando que no haya dos sesiones simultáneas en la misma aula.

Accede a esta sección desde **Administración → Aulas** en la barra de navegación superior.

![alt text](/doc/manuales/img/classrooms_tab.png)
_Figura 10. Pantalla de administración de aulas._

### 6.1 Crear un aula

1. Haz clic en **Añadir aula**.
2. Introduce el **Nombre**: por ejemplo, "Aula 1º ESO" o "Laboratorio de Ciencias".
3. Haz clic en **Crear**.

![alt text](/doc/manuales/img/classrooms_create.png)
_Figura 11. Modal de creación de aula._

### 6.2 Listar, ver detalle, editar y eliminar aulas

El proceso es idéntico al descrito para profesores (apartados 4.2 y 4.3).

---

## 7. Administración de asignaturas

Las asignaturas vinculan un profesor, un curso y un número de horas semanales. Son el elemento central a partir del cual el algoritmo construye el horario.

Accede a esta sección desde **Administración → Asignaturas** en la barra de navegación superior.

![alt text](/doc/manuales/img/subjects_tab.png)
_Figura 12. Pantalla de administración de asignaturas._

### 7.1 Crear una asignatura

1. Haz clic en **Añadir asignatura**.
2. Completa el formulario:
   - **Nombre**: por ejemplo, "Matemáticas".
   - **Horas semanales**: número entero positivo de sesiones por semana.
   - **Profesor**: selecciona de la lista de profesores del equipo.
   - **Curso**: selecciona de la lista de cursos del equipo.
   - **Aula obligatoria**: selecciona de la lista de aulas del equipo.
   - **Disponibilidad semanal**: mismo funcionamiento que la disponibilidad semanal para profesores (apartado 4.1).
3. Haz clic en **Crear**.

![alt text](/doc/manuales/img/subjects_create.png)

_Figura 13. Modal de creación de asignatura con cuadrícula de disponibilidad._

### 7.2 Listar, ver detalle, editar y eliminar asignaturas

El proceso es idéntico al descrito para profesores (apartados 4.2 y 4.3).

⚠️ **Advertencia:** Eliminar una asignatura también eliminará las sesiones de horario vinculadas a ella. Esta acción no se puede deshacer.

---

## 8. Generación automática del horario

Una vez dados de alta profesores, cursos, asignaturas y aulas, ya puedes generar el horario. El generador usa un algoritmo de programación con restricciones para encontrar la solución más óptima dado un tiempo máximo según los criterios que elijas.

Accede a esta sección desde la pestaña **Generador** en la barra de navegación superior.

![alt text](/doc/manuales/img/dashboard.png)
_Figura 14. Panel de control del generador de horarios._

### 8.1 Lanzar la generación

1. En el panel **Panel de control**, haz clic en **Generar horario**.
2. Se abrirá el modal de configuración de la generación (ver apartado 8.2).
3. Ajusta las opciones que necesites y haz clic en **Generar horario** (botón de confirmación del modal).

El sistema lanzará la generación en segundo plano. Verás una barra de progreso con tres fases:

- **Fase 1 — Buscando solución válida:** el algoritmo comprueba que el horario es factible con las restricciones activas.
- **Fase 2 — Optimizando el horario:** con una solución válida encontrada, el algoritmo mejora la distribución durante el tiempo de optimización configurado.
- **Fase 3 — Ultimando detalles:** validación final y preparación para mostrar el resultado.

![alt text](/doc/manuales/img/schedule_generate.png)

_Figura 15. Barra de progreso de la generación con sus tres fases._

### 8.2 Opciones de configuración de la generación

Al hacer clic en **Generar horario**, el modal te ofrece estas opciones:

#### Restricciones siempre activas (no modificables)

Estas restricciones se aplican siempre, independientemente de la configuración:

- Cada sesión ocupa exactamente un hueco del horario semanal.
- Las sesiones de cada etapa solo se asignan dentro del horario definido para ella.
- Sin solapamiento de sesiones, profesores ni aulas.
- Máximo de sesiones por día por curso (5 para Infantil/Primaria, 6 para Secundaria).
- Máximo de horas semanales por profesor y curso.

#### Restricciones de factibilidad (todas activas por defecto)

Estas restricciones son obligatorias cuando están marcadas. Si alguna hace el problema irresoluble, desactívala para obtener igualmente un horario:

- **Los cursos no pueden tener huecos entre sus sesiones:** garantiza bloques contiguos para cada curso en el día.
- **Respetar horarios no disponibles de asignaturas:** el algoritmo no asigna sesiones en las franjas marcadas como "No disponible" en las asignaturas.
- **Respetar horarios no disponibles de profesores:** el algoritmo no asigna sesiones en las franjas marcadas como "No disponible" en los profesores.

#### Preferencias de optimización (todas activas por defecto)

Estas opciones guían la fase de optimización. Desactiva aquellas que no consideres relevantes para tu horario.

- **Preferencias horarias de asignaturas:** respeta las franjas marcadas como "Prefiere sí" o "Prefiere no" en las asignaturas.
- **Preferencias horarias de profesores:** respeta las franjas marcadas como "Prefiere sí" o "Prefiere no" en los profesores.
- **Distribuir sesiones de la misma asignatura en días distintos:** evita que todas las sesiones de una asignatura caigan el mismo día.
- **Minimizar huecos en la jornada del profesor:** penaliza los huecos intermedios en el horario de cada profesor.

#### Horas de guardia TC

- **Docentes de guardia (TC) por franja:** número de profesores que deben estar de guardia en cada franja horaria (0 = no generar horas TC). Rango: 0–20.

#### Tiempo de ejecución

- **Minutos de optimización:** tiempo dedicado a la fase de optimización una vez encontrada una solución válida. Valor por defecto: **15 minutos** (suficiente para la mayoría de casos). Rango: 0–720 minutos. Haz clic en el icono de lápiz para editarlo.

#### Opciones avanzadas

- **Semilla (reproducibilidad):** introduce un número entero para obtener siempre el mismo horario con la misma configuración. Déjalo vacío para obtener un resultado diferente en cada generación.

![alt text](/doc/manuales/img/schedule_configuration.png)

_Figura 16. Modal de configuración de la generación del horario._

### 8.3 Guardar el horario generado

Una vez finalizada la generación con éxito, el horario aparece como **Borrador** en el espacio de trabajo. Si el resultado te convence, guárdalo para conservarlo. Tanto en estado borrador como una vez guardado, puedes seguir editando el horario libremente en cualquier momento.

1. Haz clic en **Guardar** (botón en la cabecera del horario generado).
2. Introduce un **Nombre del horario**: por ejemplo, "Semana Base".
3. Haz clic en **Guardar**.

El horario quedará almacenado en la sección **Guardados**.

![alt text](/doc/manuales/img/schedule_save.png)

_Figura 17. Modal para guardar el horario generado._

---

## 9. Gestión de horarios guardados

En la sección **Guardados** puedes consultar, renombrar, eliminar y trabajar sobre todos los horarios que has guardado.

Accede desde la pestaña **Guardados** en la barra de navegación superior.

![alt text](/doc/manuales/img/schedule_tab.png)
_Figura 18. Pantalla de horarios guardados._

### 9.1 Listar horarios guardados

La pantalla **Guardados** muestra todos los horarios almacenados del equipo activo, con su nombre y fecha de generación.

### 9.2 Ver el resumen de un horario guardado

Haz clic sobre el nombre del horario guardado para acceder a su vista detallada.

### 9.3 Renombrar un horario guardado

1. Localiza el horario en la lista.
2. Haz clic en el icono de edición (lápiz) junto al nombre.
3. Escribe el nuevo nombre.
4. Haz clic en **Renombrar**.

### 9.4 Eliminar un horario guardado

1. Localiza el horario en la lista.
2. Haz clic en el icono de eliminar (papelera).
3. Haz clic en **Eliminar**.

⚠️ **Advertencia:** Eliminar un horario guardado es irreversible. Se perderán todas las sesiones asociadas a ese horario.

---

## 10. Visualización y edición del horario

Una vez generado (o cargado desde los guardados), el horario se muestra en una tabla semanal interactiva donde puedes revisar las sesiones y ajustarlas manualmente.

![alt text](/doc/manuales/img/schedule_view.png)
_Figura 19. Vista principal del horario semanal interactivo._

### 10.1 Visualizar el horario

El horario se presenta como una cuadrícula con los días de la semana en columnas y los tramos horarios en filas. Cada sesión muestra la asignatura, el profesor, el curso y el aula.

Puedes filtrar la vista por:

- **Curso**
- **Profesor**
- **Aula**
- **Asignatura**
- **Horas de guardia**: accesible mediante el icono de escudo amarillo situado junto al botón **Exportar**.

Debajo de la cuadrícula, la página muestra automáticamente un **listado de sesiones** con el detalle de todas las sesiones visibles. Este listado se actualiza en tiempo real según los filtros activos, lo que te permite revisar la información de cada sesión con más detalle.

ℹ️ **Nota:** Para consultar la carga horaria de los profesores, haz clic en el botón para filtrar por profesor. El listado resultante muestra las horas asignadas a ese profesor.

![alt text](/doc/manuales/img/schedule_teachers_hours.png)

_Figura 20. Listado de sesiones filtrado por profesor para revisar su carga horaria._

### 10.2 Intercambiar una sesión por otra

1. Filtra la vista por curso, profesor, aula o asignatura para localizar la sesión que quieres mover.
2. Haz clic sobre la sesión y manténla pulsada. El sistema resaltará en verde todas las sesiones con las que es posible realizar el intercambio.
3. Arrastra la sesión hasta cualquiera de las posiciones marcadas en verde y suéltala para confirmar el intercambio.

ℹ️ **Nota:** Si no aparece ninguna opción verde, significa que no existe ningún intercambio válido para esa sesión con las restricciones actuales.

![alt text](/doc/manuales/img/schedule_move_sessions.png)
_Figura 21. Intercambio de sesiones: posiciones válidas resaltadas en verde._

### 10.3 Exportar el horario

1. Desde el horario generado o guardado, haz clic en el botón **Exportar**.
2. Se abrirá el modal **Exportar horario**.
3. Selecciona el **Formato**:
   - **CSV**: archivo de texto separado por comas, compatible con Excel, LibreOffice Calc, etc.
   - **PDF**: documento listo para imprimir.
4. Selecciona la **Información a exportar**:
   - **Todos los cursos**: exporta el horario de todos los cursos.
   - **Todos los profesores**: exporta el horario de todos los profesores.
   - **Todas las aulas**: exporta el horario de todas las aulas.
   - **Horas de guardia**: exporta las sesiones de guardia asignadas.
   - También puedes seleccionar **cursos, profesores o aulas concretas** usando las listas de selección individual.
5. Haz clic en **Exportar**.

ℹ️ **Nota:** Puedes combinar varios tipos de información en una misma exportación seleccionando más de una opción.

![alt text](/doc/manuales/img/schedule_export.png)

_Figura 22. Modal de exportación del horario._

### 10.4 Guardias TC (Trabajo de Centro)

Las guardias TC son horas en las que un profesor está disponible en el centro pero no imparte clase.

**Asignación automática:** si en el modal de generación introduces un número mayor que 0 en el campo **Docentes de guardia (TC) por franja**, el algoritmo asignará guardias TC automáticamente tras generar el horario lectivo.

![alt text](/doc/manuales/img/schedule_tc_view.png)
_Figura 23. Vista del horario con sesiones de guardia TC asignadas._

**Crear una guardia manualmente:**

1. Filtra la vista por un **profesor** concreto.
2. Haz clic en el icono de escudo amarillo con el símbolo **+** que aparece en el tramo donde deseas añadir una sesión de guardia.
3. La guardia se crea inmediatamente, sin necesidad de confirmar.

ℹ️ **Nota:** El sistema no permite que una guardia TC se solape con otra sesión lectiva ni con otra guardia del mismo profesor en el mismo hueco.

**Eliminar una guardia:**

1. Localiza la guardia en el horario. Puedes hacerlo sin filtros, filtrando por profesor, o usando el botón de **Horas de guardia** (icono de escudo amarillo junto al botón Exportar).
2. Haz clic en el icono de papelera que aparece en la esquina superior derecha de la sesión.
3. La guardia se elimina inmediatamente, sin necesidad de confirmar.

## 11. Registro de cambios (Auditoría)

El registro de cambios guarda automáticamente un historial de todas las acciones realizadas en el equipo: creación, modificación y borrado de cualquier elemento (profesores, cursos, asignaturas, aulas, horarios, usuarios y tramos de configuración).

Accede desde la pestaña **Registro de cambios** en la barra de navegación superior.

![alt text](/doc/manuales/img/audit_tab.png)
_Figura 24. Pantalla del registro de cambios con filtros disponibles._

### 11.1 Filtrar el registro

Usa los filtros disponibles para localizar cambios concretos:

- **Elemento**: filtra por tipo de entidad modificada: Profesor, Aula, Curso, Asignatura, Horario, Usuario o Tramo.
- **Acción**: filtra por tipo de cambio: Creación, Modificación o Borrado.
- **Usuario**: filtra por el miembro del equipo que realizó la acción.
- **Rango de fechas**: selecciona un periodo concreto usando el selector de fechas. Puedes usar los accesos rápidos: **Hoy**, **7 días**, **30 días** o **Este mes**.

Para limpiar todos los filtros y volver a ver el registro completo, haz clic en **Limpiar**.

ℹ️ **Nota:** El registro de cambios solo muestra los eventos del equipo activo. Si cambias de equipo activo, verás el registro de ese otro equipo.

### 11.2 Exportar el registro de cambios

1. Aplica los filtros que necesites (ver apartado 11.1).
2. Haz clic en el botón de exportación del registro.
3. Se abrirá el modal **Exportar registro**.
4. Selecciona el **Formato** (CSV o PDF).
5. En **Información opcional**, selecciona las columnas adicionales que quieres incluir. Las columnas **Resumen** y **Detalle** se incluyen siempre. Las columnas opcionales son:
   - **Fecha**
   - **Usuario**
   - **Elemento**
   - **Acción**
6. Haz clic en **Exportar**.

ℹ️ **Nota:** La exportación incluirá únicamente los registros que coincidan con los filtros activos en ese momento.

![alt text](/doc/manuales/img/audit_export.png)

_Figura 25. Modal de exportación del registro de cambios._

---

## 12. Gestión de la cuenta

Esta sección cubre las acciones relacionadas con tu cuenta personal de usuario en Orarioo: actualizar datos, cambiar contraseña, descargar tus datos o eliminar la cuenta.

Accede a esta sección desde tu avatar en la barra de navegación → **Mi perfil**.

![alt text](/doc/manuales/img/profile_view.png)
_Figura 26. Página de perfil de usuario._

### 12.1 Actualizar el perfil de usuario

1. En la sección **Información personal**, haz clic en **Editar**.
2. Modifica tu **Nombre** y/o **Apellidos**.
3. Haz clic en **Guardar cambios**.

ℹ️ **Nota:** El correo electrónico no se puede modificar por motivos de seguridad. Si necesitas cambiarlo, contacta con el soporte de Orarioo.

### 12.2 Cambiar la contraseña

1. En la sección **Seguridad**, haz clic en **Editar**.
2. Introduce tu **Contraseña actual**.
3. Escribe la **Nueva contraseña** y repítela en **Repite la nueva contraseña**.
   - Mínimo 8 caracteres, incluyendo al menos una letra y un número.
4. Haz clic en **Actualizar contraseña**.

### 12.3 Descarga de datos personales (GDPR)

1. En la sección **Descarga tus datos**, haz clic en **Descargar mis datos**.
2. El sistema generará y descargará automáticamente un archivo JSON con la siguiente información:
   - **Datos personales**: nombre, apellidos, correo electrónico y nombre del equipo activo en el momento de la descarga.
   - **Actividad**: las últimas 100 acciones realizadas por ti en la plataforma.

ℹ️ **Nota:** Existe un límite de seguridad de **1 solicitud cada 10 minutos**. Si lo superas, el sistema te informará de que debes esperar antes de volver a solicitarlo.

### 12.4 Eliminar la cuenta

⚠️ **Advertencia:** Esta acción es irreversible. Al eliminar tu cuenta se borran permanentemente todos tus datos personales de la plataforma. No se puede deshacer.

1. En la sección **Eliminar cuenta**, haz clic en **Eliminar cuenta**.
2. Lee el aviso de confirmación en el modal que aparece.
3. En el campo de confirmación, escribe exactamente tu **dirección de correo electrónico**.
4. El botón **Eliminar cuenta** se activará una vez que el email introducido coincida exactamente.
5. Haz clic en **Eliminar cuenta**.

ℹ️ **Nota:** La eliminación es una anonimización: tus datos personales (nombre, email, contraseña) quedan borrados, pero los registros de auditoría del equipo conservan un identificador anonimizado por motivos de seguridad.

![alt text](/doc/manuales/img/profile_delete.png)

_Figura 27. Modal de confirmación de eliminación de cuenta._

---

## 13. Preguntas frecuentes

### ¿Por qué el algoritmo no encuentra ningún horario?

El generador puede fallar en la fase 1 si las restricciones activas hacen el problema irresoluble. Las causas más habituales son:

- Un profesor tiene marcadas como "No disponible" demasiadas franjas y no puede cubrir todas sus asignaturas.
- Una asignatura tiene más horas semanales de las que permite su horario disponible.
- Los tramos horarios de una etapa son insuficientes para todas las sesiones asignadas a sus cursos.

Prueba a desactivar alguna restricción de factibilidad en el modal de generación (ver apartado 8.2) para identificar cuál es el conflicto.

### ¿Puedo tener varios horarios guardados a la vez?

Sí. Puedes guardar tantos horarios como necesites. Todos quedan almacenados en la sección **Guardados** y puedes abrirlos, compararlos o editarlos en cualquier momento (ver sección 9).

### ¿Puedo editar el horario después de guardarlo?

Sí. Tanto el borrador como un horario ya guardado son editables. Puedes intercambiar sesiones y gestionar guardias TC sin restricciones adicionales (ver sección 10).

### ¿Qué diferencia hay entre los modos "Hasta un máximo" y "Exactamente"?

- **Hasta un máximo**: el algoritmo puede asignarle al profesor menos horas de las configuradas si la distribución lo requiere.
- **Exactamente**: el algoritmo intentará asignarle exactamente ese número de horas. Si no es posible cumplirlo, lo indicará en el listado de sesiones al filtrar por ese profesor.

### ¿Qué ocurre si elimino un profesor que tiene asignaturas asignadas?

Al eliminar un profesor se eliminan también todas sus asignaturas y las sesiones de horario vinculadas a ellas. Esta acción no se puede deshacer (ver apartado 4.3).

### ¿Puedo pertenecer a varios equipos a la vez?

Sí. Puedes pertenecer a tantos equipos como quieras y cambiar entre ellos en cualquier momento desde el menú de tu avatar. Cada equipo tiene sus propios datos y horarios completamente independientes (ver sección 3).

### ¿Qué es la semilla de reproducibilidad?

Es un número que fija el punto de partida del algoritmo. Si introduces la misma semilla con la misma configuración, obtendrás exactamente el mismo horario en cada generación. Déjala vacía si prefieres que el algoritmo explore soluciones distintas en cada ejecución (ver apartado 8.2).

### ¿Qué pasa si el horario lleva mucho tiempo generándose?

Si una generación lleva en ejecución más tiempo del esperado, el sistema la detecta como interrumpida y muestra un aviso. Puedes lanzar una nueva generación en cualquier momento. Si el problema persiste, prueba a reducir el tiempo de optimización o simplifica las restricciones activas.
