# Manual de instalación

Este manual describe el proceso de instalación y configuración de **Orarioo**
en un entorno local de desarrollo. Está dirigido a usuarios técnicos con
conocimientos de Python, PostgreSQL y línea de comandos.

## Requisitos del sistema

Para ejecutar Orarioo en local se necesita:

- **Python 3.12 o superior.**
- **PostgreSQL 15 o superior.**
- **Git**: necesario para clonar el repositorio.
- **pip 21 o superior**: requerido por la dependencia OR-Tools.
- **Espacio en disco**: se recomienda disponer de al menos 1 GB de espacio libre
  para el entorno virtual, las dependencias y los archivos del proyecto.

## Proceso de instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/Mialra/Orarioo.git
cd Orarioo
```

### 2. Crear y activar el entorno virtual

```bash
python -m venv venv
```

En Windows:

```bash
venv\Scripts\activate
```

En Linux / Mac:

```bash
source venv/bin/activate
```

### 3. Instalar las dependencias

```bash
pip install -r src/requirements.txt
```

### 4. Crear la base de datos en PostgreSQL

Antes de ejecutar las migraciones es necesario crear la base de datos
manualmente. Ejecutar el siguiente comando desde la terminal:

```bash
psql -U postgres -c "CREATE DATABASE orarioo_db;"
```

Se solicitará la contraseña del usuario `postgres` establecida durante la
instalación de PostgreSQL. En Windows, si `psql` no está disponible en el
PATH del sistema, puede ejecutarse indicando la ruta completa al binario.
La ruta habitual es `C:\Program Files\PostgreSQL\17\bin`.

En PowerShell:

```bash
& "tu-ruta-a-postgresql\bin\psql.exe" -U postgres -c "CREATE DATABASE orarioo_db;"
```

En CMD:

```bash
"tu-ruta-a-postgresql\bin\psql.exe" -U postgres -c "CREATE DATABASE orarioo_db;"
```

### 5. Configurar las variables de entorno

Crear un archivo `.env` en la raíz del proyecto (`Orarioo/.env`) con el
siguiente contenido:

```
SECRET_KEY='una-clave-de-django-secreta-larga-y-aleatoria'
DB_NAME='orarioo_db'
DB_USER='postgres'
DB_PASSWORD='tu-password-de-postgresql'
DB_HOST='localhost'
DB_PORT='5432'
DB_SSLMODE='disable'
ALLOWED_HOSTS='localhost,127.0.0.1'
DEBUG=True
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

Para generar un valor seguro para `SECRET_KEY`, ejecutar el siguiente comando
con el entorno virtual activado:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Las variables de seguridad HTTPS (`SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`,
etc.) no deben incluirse en el `.env` local, ya que son gestionadas
automáticamente por la aplicación en función del valor de `DEBUG`.

### 6. Aplicar las migraciones

Todos los comandos siguientes deben ejecutarse desde el directorio `src/`:

```bash
cd src
python manage.py migrate
```

### 7. Cargar los datos de prueba

Este paso es altamente recomendado para poder probar la aplicación, ya que sin
él no existirá ningún usuario con el que iniciar sesión. El script es
idempotente y puede ejecutarse múltiples veces sin riesgo.

```bash
python load_test_data.py
```

El script crea los siguientes datos de prueba:

- Dos usuarios: `direccion.academica@test.com` y `jefatura.estudios@test.com`,
  ambos con contraseña `direccion123`.
- Un equipo de colaboración.
- 23 profesores con preferencias horarias variadas.
- 13 grupos de alumnos (de 1º de Infantil a 4º de ESO).
- 18 aulas.
- 112 asignaturas con restricciones y preferencias.

Si se prefiere no usar datos de prueba, es necesario crear un superusuario
manualmente:

```bash
python manage.py createsuperuser
```

### 8. Arrancar el servidor

```bash
python manage.py runserver
```

La aplicación estará disponible en <http://127.0.0.1:8000>.
