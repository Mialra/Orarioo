# ==========================================
# CREACIÓN DE ISSUES DE REQUISITOS
# Labels usados:
# - feature (implementación)
# - doc (documentación)
# - MVP (Must have)
# - extra (Should / Could)
# ==========================================

$requirements = @(

# ---------------- FUNCIONALES ----------------
@{Id="F-01"; Type="feature"; Priority="Must have";
Title="Generación automática de horarios";
Description="Generar horario basado en restricciones.";
Criteria="Horario sin conflictos."},

@{Id="F-02"; Type="feature"; Priority="Must have";
Title="Visualización filtrada";
Description="Visualizar por curso/profesor/aula.";
Criteria="Filtrado correcto."},

@{Id="F-03"; Type="feature"; Priority="Must have";
Title="Modificación con auditoría";
Description="Registrar cambios.";
Criteria="Fecha, usuario y detalle."},

@{Id="F-04"; Type="feature"; Priority="Must have";
Title="Exportación PDF/CSV";
Description="Exportar horarios.";
Criteria="Exportación fiel."},

@{Id="F-05"; Type="feature"; Priority="Must have";
Title="Login seguro";
Description="Autenticación con correo y contraseña.";
Criteria="Acceso autenticado."},

@{Id="F-06"; Type="feature"; Priority="Must have";
Title="Consulta historial";
Description="Ver historial de cambios.";
Criteria="Auditoría completa."},

@{Id="F-07"; Type="feature"; Priority="Must have";
Title="Panel administración";
Description="CRUD usuarios, profesores, aulas...";
Criteria="Gestión segura."},

@{Id="F-08"; Type="feature"; Priority="Must have";
Title="Roles diferenciados";
Description="Administrador y dirección.";
Criteria="Permisos por rol."},

@{Id="F-09"; Type="feature"; Priority="Must have";
Title="Exportación auditoría";
Description="Exportar historial completo.";
Criteria="Filtro por fecha y usuario."},

@{Id="F-10"; Type="feature"; Priority="Should have";
Title="Sustituciones automáticas";
Description="Sugerir profesores disponibles.";
Criteria="Muestra sustitutos."},

@{Id="F-11"; Type="feature"; Priority="Should have";
Title="Integración Google Calendar";
Description="Recordatorios sincronizados.";
Criteria="Sincronización correcta."},

@{Id="F-12"; Type="feature"; Priority="Could have";
Title="Multilenguaje";
Description="Soporte español/inglés.";
Criteria="Cambio funcional."},

@{Id="F-13"; Type="doc"; Priority="Must have";
Title="Política de privacidad";
Description="Documento de política de privacidad.";
Criteria="Información clara sobre tratamiento de datos."},

@{Id="F-14"; Type="feature"; Priority="Could have";
Title="Gestión clases de refuerzo";
Description="Administrar clases de refuerzo.";
Criteria="Afecta carga horaria."},

@{Id="F-15"; Type="feature"; Priority="Must have";
Title="Validaciones y errores";
Description="Control de errores.";
Criteria="Feedback comprensible."},

@{Id="F-16"; Type="feature"; Priority="Should have";
Title="Copias de seguridad";
Description="Exportación e importación.";
Criteria="Restauración completa."},

# ---------------- INFORMACIÓN (MODELOS / ENTIDADES) ----------------
@{Id="I-01"; Type="feature"; Priority="Must have"; Title="Entidad Usuario"; Description="Modelo Usuario."; Criteria="Datos guardados correctamente."},
@{Id="I-02"; Type="feature"; Priority="Must have"; Title="Entidad Profesor"; Description="Modelo Profesor."; Criteria="Datos guardados correctamente."},
@{Id="I-03"; Type="feature"; Priority="Must have"; Title="Entidad Aula"; Description="Modelo Aula."; Criteria="Datos guardados correctamente."},
@{Id="I-04"; Type="feature"; Priority="Must have"; Title="Entidad Asignatura"; Description="Modelo Asignatura."; Criteria="Datos guardados correctamente."},
@{Id="I-05"; Type="feature"; Priority="Must have"; Title="Entidad Curso"; Description="Modelo Curso."; Criteria="Datos guardados correctamente."},
@{Id="I-06"; Type="feature"; Priority="Must have"; Title="Entidad Horario"; Description="Modelo Horario."; Criteria="Datos guardados correctamente."},
@{Id="I-07"; Type="feature"; Priority="Must have"; Title="Entidad Auditoría Horarios"; Description="Modelo Auditoría."; Criteria="Datos guardados correctamente."},
@{Id="I-08"; Type="feature"; Priority="Must have"; Title="Entidad Auditoría Entidades"; Description="Modelo Auditoría entidades."; Criteria="Datos guardados correctamente."},
@{Id="I-09"; Type="feature"; Priority="Should have"; Title="Entidad Notificaciones"; Description="Modelo Notificación."; Criteria="Datos guardados correctamente."},
@{Id="I-10"; Type="feature"; Priority="Could have"; Title="Entidad Refuerzos"; Description="Modelo Refuerzo."; Criteria="Datos correctos."},

# ---------------- SEGURIDAD ----------------
@{Id="S-01"; Type="feature"; Priority="Must have"; Title="Cifrado de datos"; Description="Cifrado información sensible."; Criteria="Datos cifrados."},
@{Id="S-02"; Type="feature"; Priority="Must have"; Title="Control acceso por roles"; Description="Restricción por rol."; Criteria="Permisos correctos."},
@{Id="S-03"; Type="feature"; Priority="Must have"; Title="Auditoría acciones críticas"; Description="Registro cambios críticos."; Criteria="Registro completo."},

# ---------------- TÉCNICOS ----------------
@{Id="T-01"; Type="feature"; Priority="Must have"; Title="Aplicación responsive"; Description="Interfaz adaptativa."; Criteria="Funciona en todos los dispositivos."},
@{Id="T-02"; Type="feature"; Priority="Must have"; Title="Desarrollo en Django"; Description="Backend en Django."; Criteria="Proyecto Django funcional."},
@{Id="T-03"; Type="feature"; Priority="Should have"; Title="Integración Google Calendar"; Description="Sincronización calendario."; Criteria="Sincronización correcta."},
@{Id="T-04"; Type="feature"; Priority="Should have"; Title="Sistema recomendación sustituciones"; Description="Algoritmo recomendación."; Criteria="Recomendaciones coherentes."},
@{Id="T-05"; Type="feature"; Priority="Should have"; Title="Formato propio de intercambio"; Description="Exportar/importar sistema."; Criteria="Sin pérdida de datos."}

)

foreach ($req in $requirements) {

    $priorityLabel = if ($req.Priority -eq "Must have") { "MVP" } else { "extra" }

$body = @"
## 📌 $($req.Id)

### 📝 Descripción
$($req.Description)

### ✅ Criterios de aceptación
$($req.Criteria)
"@

    gh issue create `
        --title "$($req.Id) - $($req.Title)" `
        --body $body `
        --label "$($req.Type),$priorityLabel"
}

Write-Host "✅ Issues creadas con labels correctos."
