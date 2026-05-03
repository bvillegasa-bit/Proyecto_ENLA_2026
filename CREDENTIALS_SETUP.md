# Guía de Configuración de Credenciales - ENLA 2026 Callao

## Índice
- [Pre-requisitos](#pre-requisitos)
- [1. MongoDB Atlas](#1-mongodb-atlas)
- [2. SendGrid](#2-sendgrid)
- [3. Google Cloud Platform y BigQuery](#3-google-cloud-platform-y-bigquery)
- [4. Configuración del archivo .env](#4-configuración-del-archivo-env)
- [5. Configuración de GitHub Secrets](#5-configuración-de-github-secrets)
- [6. Verificación de Credenciales](#6-verificación-de-credenciales)
- [Solución de Problemas](#solución-de-problemas)

---

## Pre-requisitos

Antes de comenzar, asegúrate de tener:
- ✅ Una cuenta de correo electrónico activa
- ✅ Acceso a una tarjeta de crédito (para Google Cloud Platform - tiene periodo gratuito)
- ✅ Permisos de administrador en el repositorio de GitHub (si vas a configurar CI/CD)
- ✅ Python 3.11 instalado localmente
- ✅ Acceso al archivo `config/.env.example` del proyecto

---

## 1. MongoDB Atlas

MongoDB Atlas es el servicio de base de datos en la nube donde se almacenan los datos crudos de ENLA y los logs de ingesta.

### Paso 1: Crear cuenta / Iniciar sesión

1. Ve a [https://www.mongodb.com/cloud/atlas/register](https://www.mongodb.com/cloud/atlas/register)
2. Haz clic en **"Try Free"** (Probar gratis)
3. Completa el registro con tu email, Google o GitHub
4. Verifica tu correo electrónico si es necesario
5. Una vez verificado, serás redirigido al panel de control de Atlas

📸 **Pantalla esperada**: Verás el botón verde "Create" o "Build a Cluster" en el centro de la página.

### Paso 2: Crear cluster

1. Haz clic en **"Create"** o **"Build a Cluster"**
2. Selecciona el plan **"FREE"** (M0 Sandbox - gratuito, 512 MB)
   - Desplázate hacia abajo para ver las opciones de planes
   - El plan M0 es suficiente para este proyecto
3. En **"Cloud Provider & Region"**:
   - Selecciona **Google Cloud Platform**
   - Elige la región más cercana: `us-central1` (Iowa) o `southamerica-east1` (São Paulo)
   - Esto minimizará la latencia con los servicios de Google Cloud
4. En **"Cluster Name"**:
   - Mantén el nombre por defecto o cámbialo a `Cluster-ENLA-2026`
5. Haz clic en **"Create Cluster"** (botón verde abajo a la derecha)

⏳ **Tiempo estimado**: El cluster tardará unos 3-5 minutos en crearse. Verás una animación de construcción.

📸 **Pantalla esperada**: Un círculo girando que dice "We're creating your cluster..." y luego verás tu cluster en la lista con estado "Active".

### Paso 3: Crear usuario de base de datos

1. En el panel izquierdo, haz clic en **"Database Access"** (debajo de "SECURITY")
2. Haz clic en el botón verde **"+ Add New Database User"**
3. Completa los campos:
   - **Authentication Method**: Selecciona "Password"
   - **Username**: Ingresa un nombre, ejemplo: `enla-app-user`
   - **Password**: Haz clic en "Autogenerate Secure Password" o crea una contraseña segura
     - ⚠️ **IMPORTANTE**: Guarda esta contraseña en un lugar seguro (la necesitarás para el URI de conexión)
   - **User Privileges**: Selecciona "Atlas Admin" (para tener permisos completos)
4. En la sección "Database User Privileges", asegúrate de que dice "Atlas Admin"
5. Haz clic en **"Add User"** (botón verde abajo)

📸 **Pantalla esperada**: Verás el nuevo usuario en la lista de "Database Users" con rol "Atlas Admin".

### Paso 4: Obtener URI de conexión

1. Ve a **"Database"** en el menú superior
2. Haz clic en el botón **"Connect"** de tu cluster
3. Selecciona **"Drivers"** (la tercera opción - conectar tu aplicación)
4. Configura los parámetros:
   - **Driver**: Selecciona "Python"
   - **Version**: Selecciona "3.12 or later" (o la versión que tengas)
5. Copia el **Connection String** que aparece:
   ```
   mongodb+srv://<username>:<password>@cluster01.abc123.mongodb.net/?retryWrites=true&w=majority
   ```
6. Reemplaza `<username>` con tu usuario (`enla-app-user`) y `<password>` con tu contraseña
7. Agrega el parámetro `appName` al final si no está:
   ```
   mongodb+srv://enla-app-user:tupassword@cluster01.abc123.mongodb.net/?retryWrites=true&w=majority&appName=Cluster01
   ```

📸 **Pantalla esperada**: Un cuadro con el código de conexión en Python y el URI resaltado.

### Paso 5: Configurar acceso de red (IP Allowlist)

1. En el panel izquierdo, haz clic en **"Network Access"** (debajo de "SECURITY")
2. Haz clic en **"+ Add IP Address"**
3. Para desarrollo local, selecciona **"Allow Access from Anywhere"** (0.0.0.0/0)
   - ⚠️ **NOTA DE SEGURIDAD**: Esto es útil para desarrollo, pero en producción deberías usar solo las IPs específicas
4. Haz clic en **"Confirm"**

📸 **Pantalla esperada**: Verás "0.0.0.0/0" en la lista de IP addresses permitidas con estado "Active".

**✅ Ya tienes tu MONGODB_URI listo para usar.**

---

## 2. SendGrid

SendGrid es el servicio de envío de correos electrónicos para las alertas de instituciones en riesgo.

### Paso 1: Crear cuenta / Iniciar sesión

1. Ve a [https://signup.sendgrid.com/](https://signup.sendgrid.com/)
2. Completa el formulario de registro:
   - **Email**: Tu correo electrónico
   - **Password**: Crea una contraseña segura
   - **First Name** y **Last Name**: Tu nombre
   - **Company**: "DRE Callao" o tu institución
   - **Website**: Opcional
   - **Job Role**: Selecciona "Developer" o "Data Scientist"
3. Marca la casilla de términos y condiciones
4. Haz clic en **"Create Account"**
5. Verifica tu correo electrónico (revisa tu bandeja de entrada y spam)

📸 **Pantalla esperada**: Un asistente de configuración (setup wizard) después de verificar tu email.

### Paso 2: Configurar remitente verificado (Sender Verification)

1. En el menú lateral, ve a **"Settings"** → **"Sender Authentication"**
2. En "Single Sender Verification", haz clic en **"Verify a Single Sender"**
3. Completa el formulario:
   - **From Name**: "ENLA 2026 Callao Alerts"
   - **From Email**: Usa un correo que tengas acceso (ej. `enla-alerts@dre-callao.gob.pe` o tu correo personal)
   - **Reply To**: El mismo correo
   - **Address**: Dirección de tu institución
   - **City**: Callao
   - **Country**: Perú
4. Haz clic en **"Create"**
5. Revisa tu correo y haz clic en el enlace de verificación

📸 **Pantalla esperada**: El remitente aparecerá con una marca verde de "Verified" en la lista.

### Paso 3: Crear API Key

1. En el menú lateral, ve a **"Settings"** → **"API Keys"**
2. Haz clic en **"Create API Key"** (botón azul arriba a la derecha)
3. Completa los campos:
   - **API Key Name**: `enla-2026-callao-api-key`
   - **API Key Permissions**: Selecciona **"Full Access"** (para poder enviar correos)
4. Haz clic en **"Create & View"**
5. ⚠️ **IMPORTANTE**: Copia la API Key inmediatamente (empieza con `SG.`)
   - **Esta es la única vez que verás la clave completa**
   - Guárdala en un lugar seguro
   - Ejemplo: `SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

📸 **Pantalla esperada**: Un cuadro negro con tu API Key y un botón para copiar. Después de cerrar, no podrás ver la clave completa otra vez.

**✅ Ya tienes tu SENDGRID_API_KEY listo para usar.**

---

## 3. Google Cloud Platform y BigQuery

Google Cloud Platform (GCP) proporciona BigQuery para el almacenamiento y análisis de datos.
**IMPORTANTE**: Este proyecto está configurado para funcionar **SIN necesidad de activar la facturación (billing)**,
usando **BigQuery Sandbox** (gratis) + **GitHub Actions** (gratis) + **Looker Studio** (gratis).

### Opción A: BigQuery Sandbox (RECOMENDADO - Sin Tarjeta de Crédito)

BigQuery Sandbox te permite usar BigQuery **sin cuenta de facturación**:
- **10 GB** de almacenamiento gratis
- **1 TB** de consultas por mes gratis
- **NO requiere tarjeta de crédito**
- **NO requiere billing account**

**Limitaciones**:
- ❌ No tiene BigQuery ML (usamos scikit-learn en Colab)
- ❌ No permite DML (INSERT/UPDATE/DELETE) después de 90 días — usamos `load_table_from_dataframe`
- ❌ Las tablas expiran después de 60 días (puedes extenderlas)
- ✅ SÍ permite: crear datasets, cargar datos (batch), consultas SQL, conectar Looker Studio

#### Paso 1: Activar BigQuery Sandbox

1. Ve directamente a: [https://console.cloud.google.com/bigquery](https://console.cloud.google.com/bigquery)
   - **IMPORTANTE**: Usa esta URL directa, NO vayas al console general
2. Si no tienes un proyecto, crea uno:
   - Clic en el selector de proyectos (arriba a la izquierda)
   - Clic en **NUEVO PROYECTO**
   - Nombre: `enla-2026-callao`
   - Clic en **CREAR**
3. Verifica que Sandbox está activo:
   - Una vez en la interfaz de BigQuery, busca el texto **"Sandbox mode"** o **"Modo Sandbox"**
   - Si lo ves, ¡felicidades! Sandbox está activo sin billing

#### Paso 2: Crear el dataset `BI_ENLA`

1. En el panel izquierdo, clic en tu proyecto (`enla-2026-callao`)
2. Clic en los 3 puntos `⋮` → **Crear dataset**
3. Configuración:
   - **ID del dataset**: `BI_ENLA`
   - **Ubicación**: `US` (o `southamerica-east1` para menor latencia en Perú)
   - **Tiempo de expiración de la tabla**: 60 días (puedes cambiarlo después)
4. Clic en **CREAR DATASET**

#### Paso 3: Verificar que funciona

1. En el editor de SQL, ejecuta esta consulta:
   ```sql
   SELECT "BigQuery Sandbox funciona correctamente" AS mensaje
   ```
2. Deberías ver el resultado en la parte inferior

---

### Opción B: Con Facturación (NO RECOMENDADO para este proyecto)

Si deseas usar todas las funcionalidades de BigQuery (incluyendo DML después de 90 días y scheduled queries),
puedes activar la facturación:

1. Ve a [https://console.cloud.google.com/](https://console.cloud.google.com/)
2. Inicia sesión con tu cuenta de Google
3. Crea un proyecto:
   - **Project Name**: `enla-2026-callao`
   - **Billing Account**: Selecciona o crea una cuenta de facturación
     - Requiere tarjeta de crédito (se te dan $300 USD de crédito gratuito)
4. Habilita estas APIs:
   - `BigQuery API`
   - `BigQuery Connection API`
   - `Cloud Resource Manager API` (si usas Cloud Functions, que requiere billing)

---

### Sobre Cloud Functions (OPCIONAL - Requiere Billing)

⚠️ **Cloud Functions NO está disponible en BigQuery Sandbox** (requiere billing).
El proyecto está configurado para usar **GitHub Actions** en su lugar, que es gratuito.

Si deseas usar Cloud Functions (no recomendado para este proyecto académico):
1. Debes activar billing en tu proyecto
2. Habilitar `Cloud Functions API`
3. El workflow `deploy-cloud-function.yml` ha sido deshabilitado (renombrado a `.DISABLED`)
4. Para reactivarlo, renómbralo eliminando la extensión `.DISABLED`

### Paso 4: Crear cuenta de servicio (Service Account)

1. En la barra de búsqueda, escribe: `Service Accounts`
2. Haz clic en **"Service Accounts"** bajo "IAM & Admin"
3. Haz clic en **"+ CREATE SERVICE ACCOUNT"** (botón azul arriba)
4. Completa el paso 1:
   - **Service account name**: `enla-pipeline-service-account`
   - **Service account ID**: Se autocompletará
   - **Description**: `Cuenta de servicio para el pipeline ENLA 2026 Callao`
5. Haz clic en **"CREATE AND CONTINUE"**
6. En "Grant this service account access to project", asigna estos roles (haz clic en "+ Add Role" para cada uno):
   - `BigQuery Admin`
   - `Cloud Functions Developer`
   - `Pub/Sub Admin`
   - `Storage Admin`
   - `Service Account User`
   - `Service Usage Admin` ⚠️ **CRÍTICO** - Permite habilitar APIs (requerido para GitHub Actions)
7. Haz clic en **"CONTINUE"** y luego en **"DONE"**

📸 **Pantalla esperada**: La cuenta de servicio aparecerá en la lista con los roles asignados.

⚠️ **NOTA PARA GITHUB ACTIONS**: Si ya tienes una cuenta de servicio creada y usas GitHub Actions,
asegúrate de agregar el rol `Service Usage Admin` a la cuenta de servicio:
1. Ve a: https://console.cloud.google.com/iam-admin/iam?project=enla-2026-callao
2. Busca tu cuenta de servicio en la lista
3. Haz clic en el lápiz (edit) para editar roles
4. Agrega el rol `Service Usage Admin`
5. Haz clic en "SAVE"

### Paso 5: Generar clave JSON de la cuenta de servicio

1. En la lista de Service Accounts, haz clic en el email de la cuenta que acabas de crear
2. Ve a la pestaña **"KEYS"** (arriba)
3. Haz clic en **"ADD KEY"** → **"Create new key"**
4. Selecciona **"JSON"** como tipo de clave
5. Haz clic en **"CREATE"**
6. Se descargará automáticamente un archivo `.json` a tu computadora
   - ⚠️ **GUÁRDALO BIEN**: Este archivo contiene las credenciales completas
   - Guárdalo en una ubicación segura, ejemplo: `C:\Users\TuUsuario\credentials\enla-gcp-sa-key.json`
   - No lo subas a GitHub (agrega `*.json` a tu `.gitignore`)

📸 **Pantalla esperada**: Una descarga automática del archivo JSON y un mensaje "The key has been created".

**✅ Ya tienes tu GCP_PROJECT_ID y GCP_CREDENTIALS_PATH listos.**

- **GCP_PROJECT_ID**: `enla-2026-callao` (el nombre de tu proyecto)
- **GCP_CREDENTIALS_PATH**: La ruta donde guardaste el archivo JSON (ej. `C:\Users\TuUsuario\credentials\enla-gcp-sa-key.json`)

---

## 4. Configuración del archivo .env

Ahora que tienes todas las credenciales, vamos a configurar el archivo de entorno.

### Paso 1: Crear el archivo .env

1. Navega a la carpeta `config/` de tu proyecto
2. Copia el archivo `.env.example` y renómbralo como `.env`:
   ```bash
   cd config
   cp .env.example .env
   ```
   O manualmente: crea un archivo nuevo llamado `.env`

### Paso 2: Completar las variables

Abre el archivo `config/.env` con tu editor de texto y completa las variables:

```env
# ==========================================
# MongoDB Configuration
# ==========================================
# MongoDB connection string (MongoDB Atlas)
# Reemplaza <username> y <password> con tus credenciales de MongoDB Atlas
MONGODB_URI=mongodb+srv://enla-app-user:tu_password@cluster01.abc123.mongodb.net/?retryWrites=true&w=majority&appName=Cluster01

# ==========================================
# GCP Configuration
# ==========================================
# Google Cloud Platform project ID
GCP_PROJECT_ID=enla-2026-callao

# Path to GCP service account credentials JSON file
# Reemplaza con la ruta donde guardaste tu archivo JSON
GCP_CREDENTIALS_PATH=C:\Users\TuUsuario\credentials\enla-gcp-sa-key.json

# ==========================================
# Logging Configuration
# ==========================================
# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# ==========================================
# Alert Configuration
# ==========================================
# Email address for sending alerts (debe coincidir con el remitente verificado en SendGrid)
ALERT_EMAIL_FROM=enla-alerts@dre-callao.gob.pe

# SendGrid API key (empieza con SG.)
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Paso 3: Verificar que el archivo no se suba a Git

Asegúrate de que tu archivo `.env` NO se suba a GitHub:

1. Verifica que el archivo `.gitignore` en la raíz del proyecto contenga:
   ```
   # Environment variables
   config/.env
   .env
   *.json
   credentials/
   ```
2. Si no está, agrégalo:
   ```bash
   echo "config/.env" >> .gitignore
   echo "*.json" >> .gitignore
   ```

---

## 5. Configuración de GitHub Secrets

Si vas a usar GitHub Actions para CI/CD, necesitas configurar los "Secrets" del repositorio.

### Paso 1: Acceder a la configuración de Secrets

1. Ve a tu repositorio en GitHub: [https://github.com/tu-usuario/enla-2026-callao](https://github.com/tu-usuario/enla-2026-callao)
2. Haz clic en **"Settings"** (pestaña superior)
3. En el menú lateral, ve a **"Secrets and variables"** → **"Actions"**

📸 **Pantalla esperada**: Una lista de "Repository secrets" (probablemente vacía al inicio).

### Paso 2: Agregar cada Secret

Haz clic en **"New repository secret"** para cada uno:

#### Secret 1: GCP_PROJECT_ID
- **Name**: `GCP_PROJECT_ID`
- **Value**: `enla-2026-callao`
- Haz clic en **"Add secret"**

#### Secret 2: GCP_SA_KEY
- **Name**: `GCP_SA_KEY`
- **Value**: Abre tu archivo JSON de credenciales de GCP, copia TODO el contenido (debería empezar con `{` y terminar con `}`), y pégalo aquí
  - Ejemplo: `{"type": "service_account", "project_id": "enla-2026-callao", ...}`
- Haz clic en **"Add secret"**

⚠️ **NOTA**: El archivo JSON debe ser una sola línea o puedes pegarlo con saltos de línea (GitHub lo maneja correctamente).

#### Secret 3: MONGODB_URI
- **Name**: `MONGODB_URI`
- **Value**: Tu URI completo de MongoDB Atlas (el mismo que en `.env`)
- Haz clic en **"Add secret"**

#### Secret 4: SENDGRID_API_KEY
- **Name**: `SENDGRID_API_KEY`
- **Value**: Tu API Key de SendGrid (empieza con `SG.`)
- Haz clic en **"Add secret"**

📸 **Pantalla esperada**: Los 4 secrets aparecerán en la lista con una marca de tiempo reciente.

---

## 6. Verificación de Credenciales

Después de configurar todo, es importante verificar que las credenciales funcionan correctamente.

### Verificación 1: MongoDB Atlas

Crea un archivo temporal `test_mongodb.py` en la raíz del proyecto:

```python
# test_mongodb.py
import os
from dotenv import load_dotenv

load_dotenv('config/.env')

from src.database.mongo_client import MongoClientManager

try:
    manager = MongoClientManager()
    client = manager.connect()
    print("✅ MongoDB connection successful!")
    print(f"   Server info: {client.server_info()['version']}")
    manager.disconnect()
except Exception as e:
    print(f"❌ MongoDB connection failed: {e}")
```

Ejecuta:
```bash
python test_mongodb.py
```

**Resultado esperado**: `✅ MongoDB connection successful!`

### Verificación 2: SendGrid

Crea un archivo `test_sendgrid.py`:

```python
# test_sendgrid.py
import os
from dotenv import load_dotenv

load_dotenv('config/.env')

import sendgrid
from sendgrid.helpers.mail import *

try:
    sg = sendgrid.SendGridAPIClient(api_key=os.getenv('SENDGRID_API_KEY'))
    response = sg.client.mail.send.post(
        request_body=Mail(
            from_email=Email(os.getenv('ALERT_EMAIL_FROM')),
            to_emails=To('tu-correo@test.com'),
            subject='Test SendGrid - ENLA 2026',
            html_content=Content("text/html", "<p>✅ SendGrid is working!</p>")
        ).get()
    )
    print(f"✅ SendGrid test successful! Status: {response.status_code}")
except Exception as e:
    print(f"❌ SendGrid test failed: {e}")
```

Ejecuta:
```bash
python test_sendgrid.py
```

**Resultado esperado**: `✅ SendGrid test successful! Status: 202`

### Verificación 3: Google Cloud Platform y BigQuery

Crea un archivo `test_gcp.py`:

```python
# test_gcp.py
import os
from dotenv import load_dotenv

load_dotenv('config/.env')

from google.oauth2 import service_account
from google.cloud import bigquery

try:
    # Cargar credenciales
    credentials_path = os.getenv('GCP_CREDENTIALS_PATH')
    credentials = service_account.Credentials.from_service_account_file(
        credentials_path
    )
    
    # Conectar a BigQuery
    client = bigquery.Client(
        credentials=credentials,
        project=os.getenv('GCP_PROJECT_ID')
    )
    
    # Query de prueba
    query = "SELECT 1 as test"
    result = client.query(query).result()
    
    print("✅ GCP BigQuery connection successful!")
    print(f"   Project: {client.project}")
    for row in result:
        print(f"   Test query result: {row.test}")
        
except Exception as e:
    print(f"❌ GCP BigQuery connection failed: {e}")
```

Ejecuta:
```bash
python test_gcp.py
```

**Resultado esperado**: `✅ GCP BigQuery connection successful!`

### Verificación 4: Pipeline completo (Integración)

Ejecuta el pipeline de prueba:

```bash
# Asegúrate de tener el archivo de datos ENLA
python -m src.ingestion.ingest_enla

# O ejecuta el pipeline ETL completo
python -c "from src.etl.transform import run_etl_pipeline; print(run_etl_pipeline())"
```

---

## Solución de Problemas

### Error: "MONGODB_URI not provided"
- ✅ Verifica que el archivo `config/.env` existe
- ✅ Verifica que cargaste las variables con `load_dotenv('config/.env')`
- ✅ Asegúrate de que no hay espacios extra en el archivo `.env`

### Error: "SendGrid API key not configured"
- ✅ Verifica que tu API Key empieza con `SG.`
- ✅ No incluyas comillas en el valor del `.env`
- ✅ Verifica que el remitente esté verificado en SendGrid

### Error: "GCP_PROJECT_ID not provided"
- ✅ Verifica que el archivo JSON de credenciales existe en la ruta especificada
- ✅ Asegúrate de que las APIs de BigQuery estén habilitadas
- ✅ Verifica que la cuenta de servicio tenga los roles correctos

### Error: "BigQuery connection failed - 403 Forbidden"
- ✅ Verifica que la cuenta de servicio tenga el rol `BigQuery Admin`
- ✅ Asegúrate de que el proyecto en GCP_PROJECT_ID sea correcto

### Error en GitHub Actions: "GCP_SA_KEY not found"
- ✅ Verifica que el secret esté agregado en "Settings > Secrets and variables > Actions"
- ✅ Asegúrate de que el archivo JSON esté completo (copia todo el contenido)

### Error: "cloudresourcemanager.googleapis.com not enabled"
Este error ocurre durante el despliegue de Cloud Functions en GitHub Actions:
```
API [cloudresourcemanager.googleapis.com] not enabled on project [318247247954].
Would you like to enable and retry? (y/N)?
```

**Solución**:
1. Habilita el API manualmente visitando:
   https://console.developers.google.com/apis/api/cloudresourcemanager.googleapis.com/overview?project=318247247954
2. Haz clic en "ENABLE"
3. Espera unos minutos y vuelve a ejecutar el workflow
4. Asegúrate de que la cuenta de servicio tenga el rol `Service Usage Admin` para habilitar APIs automáticamente

### Error: "does not have permission to access projects instance"
Este error indica que la cuenta de servicio no tiene los permisos necesarios:
```
[service-account@...] does not have permission to access projects instance
```

**Solución**:
1. Ve a: https://console.cloud.google.com/iam-admin/iam?project=318247247954
2. Busca la cuenta de servicio que usa GitHub Actions (del secret GCP_SA_KEY)
3. Agrega estos roles:
   - `Cloud Functions Developer` (desplegar funciones)
   - `Service Account User` (ejecutar funciones)
   - `Service Usage Admin` (habilitar APIs)
   - `Storage Admin` (acceder a código fuente en Cloud Storage)

### Error 403: "Read access to project denied: please check billing account"

Este error ocurre cuando intentas usar servicios que **requieren facturación (billing)** en un proyecto que no la tiene activada.

**Ejemplo del error**:
```
ERROR: (gcloud.functions.deploy) ResponseError: status=[403], code=[],
message=[Read access to project '***' was denied: please check billing account associated and retry]
```

**SOLUCIÓN RECOMENDADA: Usar BigQuery Sandbox (Sin Billing)**

Para este proyecto académico, **NO necesitas activar billing**. En su lugar:

1. **Usa BigQuery Sandbox** (gratis, sin tarjeta):
   - Ve a: https://console.cloud.google.com/bigquery
   - Sigue los pasos en la sección "Opción A: BigQuery Sandbox" al inicio de este documento
   - Sandbox te da 10 GB + 1 TB consultas/mes GRATIS

2. **Usa GitHub Actions para el pipeline** (ya configurado):
   - El workflow `run-notebook.yml` ejecuta el pipeline automáticamente
   - El workflow `pipeline-trigger.yml` permite ejecución manual y programada
   - Ambos son GRATUITOS (2000 min/mes en repos públicos)

3. **Cloud Functions está deshabilitado**:
   - El archivo `deploy-cloud-function.yml` fue renombrado a `.DISABLED`
   - Cloud Functions requiere billing, NO es necesario para este proyecto

---

**SI PREFIERES USAR BILLING** (NO recomendado para este proyecto):

#### a. VERIFICAR CUENTA DE FACTURACIÓN:
1. Ve a: https://console.cloud.google.com/billing/linked?project=318247247954
2. Asegúrate de que una cuenta de facturación válida esté vinculada
3. Verifica que tenga fondos disponibles

#### b. OTORGAR PERMISOS A LA CUENTA DE SERVICIO:
1. Ve a: https://console.cloud.google.com/iam-admin/iam?project=318247247954
2. Busca la cuenta de servicio (del secret GCP_SA_KEY)
3. Agrega el rol: **"Viewer" (roles/viewer)**
4. Mantén los roles existentes

#### c. HABILITAR APIS REQUERIDOS:
- Cloud Resource Manager API
- Cloud Functions API
- Cloud Billing API
- Compute Engine API
- Artifact Registry API

---

## Resumen de Variables de Entorno

| Variable | Descripción | Ejemplo | ¿Obligatorio? |
|----------|-------------|---------|----------------|
| `MONGODB_URI` | URI de conexión a MongoDB Atlas | `mongodb+srv://user:pass@...` | ✅ Sí |
| `GCP_PROJECT_ID` | ID del proyecto en Google Cloud | `enla-2026-callao` | ✅ Sí |
| `GCP_CREDENTIALS_PATH` | Ruta al archivo JSON de credenciales | `C:\path\to\key.json` | ✅ Sí |
| `LOG_LEVEL` | Nivel de logging | `INFO` | ❌ No (por defecto: INFO) |
| `ALERT_EMAIL_FROM` | Correo remitente para alertas | `enla-alerts@...` | ✅ Sí |
| `SENDGRID_API_KEY` | API Key de SendGrid | `SG.xxxxx` | ✅ Sí |

### GitHub Secrets adicionales (solo para CI/CD):

| Secret | Descripción |
|--------|-------------|
| `GCP_SA_KEY` | Contenido completo del archivo JSON de credenciales de GCP |
| `MONGODB_URI` | Mismo valor que en `.env` |
| `SENDGRID_API_KEY` | Mismo valor que en `.env` |

---

## Referencias Útiles

- 📚 [Documentación de MongoDB Atlas](https://docs.atlas.mongodb.com/)
- 📚 [Documentación de SendGrid](https://docs.sendgrid.com/)
- 📚 [Documentación de Google Cloud BigQuery](https://cloud.google.com/bigquery/docs)
- 📚 [Documentación de Google Cloud IAM](https://cloud.google.com/iam/docs)
- 📚 [Documentación de Python-dotenv](https://github.com/theskumar/python-dotenv)

---

**Última actualización**: Mayo 2026  
**Versión**: 1.0  
**Mantenido por**: Equipo ENLA 2026 Callao
