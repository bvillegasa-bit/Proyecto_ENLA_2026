# Guia de Despliegue 100% Gratuito en la Nube (GUI-based)

> **IMPORTANTE**: Esta guia usa exclusivamente servicios con capa gratuita (Free Tier). No se requiere tarjeta de credito obligatoria y el costo total es **$0.00/mes** para el uso tipico de este proyecto educativo.

---

### IMPORTANTE: Google Cloud y la Cuenta de Facturacion

Google Cloud Platform (GCP) requiere que vincules una cuenta de facturacion (tarjeta de credito) para poder habilitar CUALQUIER API, incluso si el servicio es gratuito. Esto es un requisito tecnico de Google, no un cobro.

A continuacion se presentan tres opciones para manejar este requerimiento:

#### OPCION A: Google Cloud Free Tier (Requiere tarjeta, pero NO se cobra nada)

- GCP **REQUIERE** vincular una tarjeta de credito para habilitar CUALQUIER API
- Esto es un requisito tecnico de Google, no un cobro
- Recibes **$300 USD en creditos gratuitos** por 90 dias
- El proyecto usa **~$0.00/mes** (dentro del Free Tier permanente)
- Con budget alert a $1, nunca se te cobrara nada

**Pasos claros para configurar sin riesgo:**
1. Vincula tu tarjeta de credito a GCP (solo verificacion de identidad)
2. Recibiras $300 USD en creditos gratuitos por 90 dias
3. Configura una alerta de presupuesto de $1 USD (Seccion 1.2)
4. El proyecto usa ~$0.00/mes, nunca superaras el limite gratuito
5. Al finalizar los 90 dias, los creditos expiran pero el Free Tier permanente continua

#### OPCION B: Usar una Cuenta Educativa GCP (Sin tarjeta personal)

- Si tu universidad tiene Google Workspace for Education, puede tener creditos GCP
- Pedir al area de TI de tu universidad que creen un proyecto GCP
- Muchas universidades tienen convenios con Google Cloud for Education

**Pasos para solicitarlo:**
1. Contacta al area de TI o computo de tu universidad
2. Pregunta si tienen Google Workspace for Education con creditos GCP
3. Si es asi, solicita que te creen un proyecto GCP institucional
4. El proyecto sera administrado por la universidad, sin necesidad de tu tarjeta personal
5. Una vez creado, sigue esta guia desde la Seccion 1.1 (usando el proyecto institucional)

#### OPCION C: Alternativa sin Google Cloud (Cero tarjeta, 100% gratis)

- Reemplazar BigQuery con **Google Sheets** (gratis, sin tarjeta)
- Reemplazar Cloud Functions con **GitHub Actions** (gratis, ya configurado)
- Reemplazar Cloud Storage con **GitHub repo** (para archivos pequenos)
- Usar **Python local + Google Colab** (gratis) para ML en lugar de BigQuery ML
- Looker Studio se conecta directamente a Google Sheets

**Flujo alternativo completo:** Excel → GitHub → Google Sheets → Python/Colab → Looker Studio

##### Arquitectura Alternativa (Sin GCP)

```
Excel (DRE Callao)
  → GitHub Actions (CI/CD)
    → Google Sheets (gratis, sin tarjeta)
      → Python local / Google Colab (gratis)
        → JSON/CSV en GitHub repo (gratis)
          → Looker Studio (gratis, conecta a Google Sheets)
```

##### Limites gratuitos de la alternativa:

| Servicio | Plan Gratuito | Limite | Notas |
|----------|--------------|--------|-------|
| **Google Sheets** | Free | 10 millones de celdas por hoja | Suficiente para ~100,000 registros ENLA |
| **GitHub** | Free Plan | 2,000 min Actions/mes (public) | ~20-50 min/mes para este proyecto |
| **Google Colab** | Free | 12 horas sesion, 1 GPU disponible | Para entrenamiento ML ocasional |
| **Looker Studio** | Free | Ilimitado | Conecta directamente a Google Sheets |

##### Paso a Paso: Implementacion sin GCP

**Paso 1: Preparar datos en Google Sheets**
1. Abre [Google Sheets](https://sheets.google.com)
2. Crea una hoja de calculo: `ENLA-2026-Callao-Datos`
3. Sube los archivos Excel de DRE Callao a Google Sheets
4. Configura las columnas: `institution_id`, `nom_ie`, `avg_score_2023`, `area`, etc.

**Paso 2: Configurar GitHub Actions para procesar datos**
1. Modifica `.github/workflows/pipeline-trigger.yml` para:
   - Leer datos de Google Sheets (usando `gspread` o API de Google Sheets)
   - Procesar con Python (sin BigQuery)
   - Generar predicciones con scikit-learn (en lugar de BigQuery ML)
2. Los resultados se guardan como JSON/CSV en el repositorio GitHub

**Paso 3: Entrenamiento ML sin BigQuery**
1. Usa Google Colab (gratis): [colab.research.google.com](https://colab.research.google.com)
2. Carga los datos desde Google Sheets o GitHub
3. Entrena modelos con scikit-learn o pandas
4. Exporta predicciones a JSON/CSV
5. Sube resultados al repositorio GitHub (o directo a Google Sheets)

**Paso 4: Conectar Looker Studio a Google Sheets**
1. En Looker Studio, crea un reporte
2. Fuente de datos: **Google Sheets**
3. Selecciona la hoja `ENLA-2026-Callao-Datos`
4. Crea visualizaciones igual que en la Seccion 8

##### Limitaciones de la Opcion C

- **Menos escalable**: Google Sheets tiene limite de 10M celdas
- **Mas manual**: Requiere ejecutar Colab manualmente (o GitHub Actions con mas configuracion)
- **Sin BigQuery ML**: Usar scikit-learn requiere mas codigo Python
- **Datos en hojas**: Menos seguro que base de datos para datos sensibles
- **Ideal para**: Prototipos educativos, proyectos pequenos (<10,000 registros)

---

## Tabla de Contenido
1. [Resumen de Servicios Gratuitos](#resumen-de-servicios-gratuitos)
2. [Configuracion de Google Cloud Console (Free Tier)](#1-configuracion-de-google-cloud-console-free-tier)
3. [Configuracion de MongoDB Atlas (Free Tier)](#2-configuracion-de-mongodb-atlas-free-tier)
4. [Configuracion de SendGrid (Free Tier)](#3-configuracion-de-sendgrid-free-tier)
5. [Configuracion del Repositorio GitHub (Free)](#4-configuracion-del-repositorio-github-free)
6. [Flujos de Trabajo GitHub Actions (Free)](#5-flujos-de-trabajo-github-actions-free)
7. [Como Ejecutar Pipelines Manualmente](#6-como-ejecutar-pipelines-manualmente)
8. [Monitoreo de Ejecuciones](#7-monitoreo-de-ejecuciones)
9. [Creacion de Dashboard en Looker Studio (Gratis)](#8-creacion-de-dashboard-en-looker-studio-gratis)
10. [Control de Costos (Evitar Cobros)](#9-control-de-costos-evitar-cobros)
11. [Solucion de Problemas](#10-solucion-de-problemas)

---

## Resumen de Servicios Gratuitos

### Arquitectura del Sistema (100% Gratis)

```
Excel (DRE Callao) 
  → GitHub Actions (CI/CD) 
    → MongoDB Atlas M0 (512 MB gratis)
      → BigQuery (1 TB consultas/mes gratis)
        → BigQuery ML (incluido en BigQuery gratis)
          → Cloud Functions (2M invocaciones/mes gratis)
            → SendGrid (100 emails/dia gratis)
              → Looker Studio (gratis, ilimitado)
```

### Detalle de Limites Gratuitos

> **NOTA**: Todas las APIs de Google Cloud requieren cuenta de facturacion vinculada (ver tabla en seccion "Que Necesitas para Empezar"). El Free Tier asegura **$0 de costo** si te mantienes dentro de los limites.

| Servicio | Plan Gratuito | Limite | Uso del Proyecto | Requiere Billing | Costo |
|----------|--------------|--------|------------------|-----------------|-------|
| **Google Cloud** | Free Tier | BigQuery: 1 TB consultas/mes | ~1-5 GB/mes | ✅ SÍ | **$0** |
| **Google Cloud** | Free Tier | BigQuery storage: 10 GB | ~10-50 MB | ✅ SÍ | **$0** |
| **Google Cloud** | Free Tier | Cloud Functions: 2M invocaciones/mes | ~30/mes (1 diaria) | ✅ SÍ | **$0** |
| **Google Cloud** | Free Tier | Cloud Storage: 5 GB regional | ~50 MB | ✅ SÍ | **$0** |
| **Google Cloud** | Free Tier | Cloud Build: 120 min/dia | ~5 min/build | ✅ SÍ | **$0** |
| **Google Cloud** | Free Tier | Secret Manager: 6 versiones activas | 4 secretos | ✅ SÍ | **$0** |
| **Google Cloud** | Free Tier | Pub/Sub: 10 GB/mes | ~1 MB | ✅ SÍ | **$0** |
| **MongoDB Atlas** | M0 Sandbox | 512 MB almacenamiento | ~5-10 MB | **$0** |
| **SendGrid** | Free Plan | 100 emails/dia | ~1-5/dia | **$0** |
| **GitHub** | Free Plan | 2,000 min Actions/mes (public) | ~20-50 min/mes | **$0** |
| **Looker Studio** | Free | Ilimitado | 5 dashboards | **$0** |

### Que Necesitas para Empezar

| Requisito | Costo | Requiere Tarjeta? | Notas |
|-----------|-------|-------------------|-------|
| Cuenta de Google (Gmail) | Gratis | ❌ NO | Para GCP y Looker Studio |
| Cuenta de GitHub | Gratis | ❌ NO | Para repositorio y Actions |
| Cuenta de MongoDB Atlas | Gratis | ❌ NO | Solo email, no requiere tarjeta |
| Cuenta de SendGrid | Gratis | ❌ NO | Solo email, no requiere tarjeta |
| **Google Cloud Billing** | **$0** | ✅ **SÍ** | Requiere tarjeta para activar APIs. **No se cobra nada** si te mantienes dentro de los limites (ver tabla abajo) |

> **⚠️ REQUERIMIENTO TECNICO DE GOOGLE CLOUD**: Todas las APIs de GCP requieren una cuenta de facturacion (tarjeta de credito) vinculada. Esto es un requisito tecnico de Google, no un cobro. Recibes $300 USD en creditos gratuitos + Free Tier permanente.
>
> **ALTERNATIVAS SIN TARJETA**: Si no puedes/puedes usar tarjeta, consulta la seccion **"IMPORTANTE: Google Cloud y la Cuenta de Facturacion"** (al inicio de esta guia) para opciones educativas o arquitectura alternativa sin GCP.

> **NOTA IMPORTANTE SOBRE GOOGLE CLOUD**: GCP requiere asociar una tarjeta de credito para activar la cuenta, pero ofrece **$300 en creditos gratuitos** por 90 dias para cuentas nuevas + Free Tier permanente. Este proyecto usa tan poco que ni siquiera consumira los creditos gratuitos. Si quieres **cero riesgo de cobro**, configura alertas de presupuesto (se explica en la Seccion 9).

### Tabla de APIs de GCP: Requiere Billing?

| API | Requiere Billing? | Free Tier? | Alternativa sin billing |
|-----|-------------------|------------|------------------------|
| BigQuery | **SÍ** (pero $0 si <1TB) | 1 TB/mes | Google Sheets |
| Cloud Functions | **SÍ** (pero gratis 2M/mes) | 2M invocaciones/mes | GitHub Actions |
| Cloud Storage | **SÍ** (pero gratis 5GB) | 5 GB | Google Drive / GitHub |
| Secret Manager | **SÍ** (pero gratis 6 secrets) | 6 versiones | GitHub Secrets |
| Pub/Sub | **SÍ** (pero gratis 10GB/mes) | 10 GB/mes | GitHub Actions triggers |
| Cloud Build | **SÍ** (pero gratis 120min/dia) | 120 min/dia | GitHub Actions |
| BigQuery ML | **SÍ** (incluido en BigQuery) | 1 TB procesamiento | Python/Colab local |
| Looker Studio | **NO** | Ilimitado | Looker Studio (no requiere billing) |
| IAM API | **SÍ** (requerido para todo) | Gratis | N/A (obligatorio) |
| Cloud Resource Manager | **SÍ** (requerido para todo) | Gratis | N/A (obligatorio) |

> **IMPORTANTE**: Todas las APIs de GCP requieren una cuenta de facturacion vinculada, incluso las que tienen Free Tier. Esto es un requisito tecnico de Google. El Free Tier asegura que no se cobre nada si te mantienes dentro de los limites.

---

## 1. Configuracion de Google Cloud Console (Free Tier)

### 1.1 Crear Cuenta y Proyecto en GCP

1. Abre [Google Cloud Console](https://console.cloud.google.com)
2. Inicia sesion con tu cuenta de Gmail
3. Si es tu primera vez, acepta los terminos y configura la facturacion:
   - Agrega una tarjeta de credito (se requiere para verificar identidad)
   - **Tranquilo/a**: No se te cobrara nada si usas solo servicios del Free Tier
   - Recibiras **$300 en creditos gratuitos** por 90 dias
4. En la barra superior, haz clic en el selector de proyectos
5. Haz clic en **NEW PROJECT**
6. Completa:
   - **Project name**: `enla-2026-callao`
   - **Billing account**: Selecciona tu cuenta (los creditos gratuitos cubren todo)
7. Haz clic en **CREATE**
8. Espera a que se cree y selecciona el proyecto

### 1.2 Configurar Alerta de Presupuesto (Evitar Cobros Sorpresa)

> **PASO CRITICO**: Esto te asegura que nunca se te cobre nada sin saberlo.

1. En el menu lateral, ve a **Billing** > **Budgets & alerts**
2. Haz clic en **CREATE BUDGET**
3. Configura:
   - **Budget name**: `ENLA-Free-Tier-Limit`
   - **Budget amount**: `$1.00` (si supera $1, te avisa — esto nunca deberia pasar)
   - **Alert triggers**:
     - ✅ 50% ($0.50)
     - ✅ 90% ($0.90)
     - ✅ 100% ($1.00)
   - **Manage costs**: Configura que se envien alertas a tu email
4. Haz clic en **CREATE**

Ahora, si por algun motivo el gasto supera $1 USD, recibiras un email inmediatamente.

### 1.3 Habilitar APIs Necesarias (Requieren Billing, pero son Gratis)

> **NOTA**: Todas las APIs de GCP requieren una cuenta de facturacion vinculada (tarjeta de credito), incluso las que tienen uso gratuito. Esto es un requisito tecnico de Google. Ver la tabla en la Seccion "Que Necesitas para Empezar" para detalles de Free Tier.

1. En el menu lateral, ve a **APIs & Services** > **Library**
2. Busca y habilita las siguientes APIs (una por una):
   - **BigQuery API** — ✅ Requiere billing | 1 TB consultas/mes gratis
   - **Cloud Functions API** — ✅ Requiere billing | 2M invocaciones/mes gratis
   - **Cloud Build API** — ✅ Requiere billing | 120 min/dia gratis
   - **Secret Manager API** — ✅ Requiere billing | 6 versiones activas gratis
   - **Cloud Storage API** — ✅ Requiere billing | 5 GB gratis
   - **Cloud Run API** — ✅ Requiere billing | 2M solicitudes/mes gratis
   - **IAM Service Account Credentials API** — ✅ Requiere billing | Gratis
   - **Cloud Resource Manager API** — ✅ Requiere billing | Gratis

3. Para cada API:
   - Escribe el nombre en la barra de busqueda
   - Haz clic en el resultado
   - **Si es tu primera vez**: Google te pedira confirmar la cuenta de facturacion
   - Haz clic en **ENABLE**

> **ALTERNATIVA SIN BILLING**: Si no puedes/puedes vincular una tarjeta, consulta la "OPCION C" en la seccion "IMPORTANTE: Google Cloud y la Cuenta de Facturacion" al inicio de esta guia.

### 1.4 Crear Cuenta de Servicio (Service Account)

1. En el menu lateral, ve a **IAM & Admin** > **Service Accounts**
2. Haz clic en **+ CREATE SERVICE ACCOUNT**
3. Completa:
   - **Service account name**: `enla-pipeline-sa`
   - **Service account ID**: Se autocompleta (dejalo asi)
   - **Description**: `Service account for ENLA 2026 Callao ML Pipeline`
4. Haz clic en **CREATE AND CONTINUE**
5. **Paso 2: Grant this service account access to project**
   - Haz clic en **Select a role**
   - Agrega estos roles (uno a la vez):
     - `BigQuery Admin`
     - `Cloud Functions Developer`
     - `Storage Admin`
     - `Secret Manager Admin`
     - `Service Account User`
   - Para agregar multiples roles, haz clic en **+ Add another role**
6. Haz clic en **DONE**

### 1.5 Generar Clave JSON de la Cuenta de Servicio

1. En la pagina de **Service Accounts**, haz clic en `enla-pipeline-sa@...`
2. Ve a la pestaña **KEYS**
3. Haz clic en **ADD KEY** > **Create new key**
4. Selecciona **JSON**
5. Haz clic en **CREATE**
6. Se descargara un archivo `.json` automaticamente
7. **Guarda este archivo de forma segura** — Lo necesitas para GitHub Secrets

> **IMPORTANTE**: Esta clave da acceso a tu proyecto. No la compartas ni la subas a Git. El archivo `.gitignore` ya excluye archivos `.json`.

### 1.6 Crear Bucket en Cloud Storage (5 GB Gratis)

1. En el menu lateral, ve a **Cloud Storage** > **Buckets**
2. Haz clic en **CREATE BUCKET**
3. Configura para usar Free Tier:
   - **Name**: `enla-2026-callao-data` (debe ser unico globalmente)
   - **Location type**: Region
   - **Location**: `us-central1` (region incluida en Free Tier)
   - **Storage class**: **Standard** — ✅ incluido en Free Tier (5 GB gratis)
   - ⚠️ **NO selecciones** Nearline, Coldline ni Archive — esos tienen costo
   - **Access control**: Uniform
   - **Protection tools**: Deja las casillas **desmarcadas** (Object Lock tiene costo)
4. Haz clic en **CREATE**
5. Ve a la pestaña **PERMISSIONS**
6. Haz clic en **GRANT ACCESS**
7. Agrega `enla-pipeline-sa@...` con rol `Storage Object Admin`

### 1.7 Configurar BigQuery (1 TB consultas/mes + 10 GB storage gratis)

1. En el menu lateral, ve a **BigQuery**
2. En el explorador (panel izquierdo), haz clic en tu proyecto
3. Haz clic en los tres puntos junto al nombre del proyecto
4. Selecciona **Create dataset**
5. Configura:
   - **Dataset ID**: `BI_ENLA`
   - **Data location**: `US` (1 TB consultas/mes gratis)
   - **Default table expiration**: **No expiration** (las tablas pequenas no cuestan nada)
6. Haz clic en **CREATE DATASET**

> **NOTA DE COSTO**: BigQuery cobra $0.02 por GB de almacenamiento despues de 10 GB gratis. Este proyecto usa ~10-50 MB, asi que **nunca superara el limite gratuito**.

---

## 2. Configuracion de MongoDB Atlas (Free Tier — M0 Sandbox)

> **✅ VENTAJA**: MongoDB Atlas **NO requiere tarjeta de credito** para el plan M0 (Free Tier). Solo necesitas email para registrarte.

### 2.1 Crear Cuenta y Cluster Gratuito

1. Abre [MongoDB Atlas](https://www.mongodb.com/cloud/atlas/register)
2. Registrate con email o cuenta de Google (no requiere tarjeta de credito)
3. Haz clic en **Build a Database**
4. Selecciona **M0 FREE** (la opcion mas pequena, marcada como "Free")
5. Configura:
   - **Cloud Provider**: **AWS** (tiene Free Tier en mas regiones)
   - **Region**: `us-east-1 (N. Virginia)` — la mas cercana a GCP us-central1
   - **Cluster Name**: `ENLA-2026-Callao`
6. Haz clic en **Create** (el boton dira "Create Cluster" o "Deploy")
7. Espera 2-3 minutos a que el cluster se despliegue

> **Limite Free Tier M0**:
> - 512 MB almacenamiento (suficiente para ~100,000 registros ENLA)
> - 5 GB transferencia/mes
> - No se puede hacer backup automatico (no lo necesitas para datos publicos)
> - Se pausa despues de 10 dias de inactividad (se reactiva automaticamente al conectar)

### 2.2 Crear Usuario de Base de Datos

1. En el panel izquierdo, ve a **Database Access** (bajo Security)
2. Haz clic en **+ ADD NEW DATABASE USER**
3. Completa:
   - **Authentication Method**: Password
   - **Username**: `enla_app_user`
   - **Password**: Haz clic en **Autogenerate Secure Password** y copiala
   - **Database User Privileges**: Selecciona `Read and write to any database`
4. Haz clic en **Add User**

> Guarda la contraseña — la necesitas para la URI de conexion.

### 2.3 Configurar Acceso de Red (IP Whitelist)

1. En el panel izquierdo, ve a **Network Access** (bajo Security)
2. Haz clic en **+ ADD IP ADDRESS**
3. Selecciona **Allow Access from Anywhere** (0.0.0.0/0)
   - ⚠️ Esto permite conexiones desde cualquier IP (incluyendo GitHub Actions)
   - Para datos educacionales publicos/agregados como ENLA, esto es aceptable
   - **NO almacenes datos personales** en esta base de datos
4. Haz clic en **Confirm**

### 2.4 Obtener URI de Conexion

1. En el dashboard principal, haz clic en **Connect** en tu cluster
2. Selecciona **Connect your application**
3. **Driver**: Python
4. **Version**: 3.6 or later
5. Copia la **Connection String**:
   ```
   mongodb+srv://<username>:<password>@enla-2026-callao.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```
6. Reemplaza `<username>` con `enla_app_user`
7. Reemplaza `<password>` con la contraseña generada
8. **Esta es tu MONGODB_URI** — Guardala para GitHub Secrets

---

## 3. Configuracion de SendGrid (Free Tier — 100 emails/dia)

> **✅ VENTAJA**: SendGrid **NO requiere tarjeta de credito** para el plan Free (100 emails/dia). Solo necesitas email para registrarte.

### 3.1 Crear Cuenta Gratuita

1. Abre [SendGrid](https://signup.sendgrid.com/)
2. Registrate con email (no requiere tarjeta de credito)
3. Completa el formulario con datos basicos:
   - **Email**: Tu email de contacto
   - **Password**: Contraseña segura
   - **What will you use SendGrid for?**: Selecciona "Transactional"
4. Completa la verificacion de email (revisa tu bandeja de entrada)

### 3.2 Verificar Remitente (Single Sender)

1. Ve a [SendGrid Dashboard](https://app.sendgrid.com/)
2. En el menu lateral, ve a **Settings** > **Sender Authentication**
3. Haz clic en **Verify a Single Sender**
4. Completa:
   - **From Email**: `enla-alertas@tu-email.com` (usa un email real tuyo)
   - **From Name**: `ENLA 2026 Callao - Alertas`
   - **Reply-To Email**: Tu email de contacto
   - Demas campos: Completa con datos basicos
5. Haz clic en **Create**
6. Recibiras un email de verificacion — haz clic en el enlace para confirmar

> **Limite Free Tier**: 100 emails/dia. Este proyecto usa ~1-5 emails/dia (solo cuando hay predicciones de riesgo), asi que nunca superaras el limite.

### 3.3 Generar API Key

1. En el menu lateral, ve a **Settings** > **API Keys**
2. Haz clic en **Create API Key**
3. Configura:
   - **API Key Name**: `enla-pipeline-alerts`
   - **Permissions**: Selecciona **Restricted Access**
     - Expande **Mail Send** y marca `Full Access`
     - No necesitas otros permisos
4. Haz clic en **Create & View**
5. **Copia la API Key inmediatamente** — solo se muestra una vez
6. **Esta es tu SENDGRID_API_KEY** — Guardala para GitHub Secrets

---

## 4. Configuracion del Repositorio GitHub (Free)

### 4.1 Crear Repositorio

1. Ve a [GitHub](https://github.com)
2. Haz clic en el boton **+** > **New repository**
3. Completa:
   - **Repository name**: `enla-2026-callao`
   - **Description**: `ENLA 2026 Callao - ML Prediction Pipeline (100% Free Tier)`
   - **Public**: ✅ Selecciona **Public** (los repositorios publicos tienen 2,000 min Actions/mes gratis vs 500 min en privados)
   - Marca **Add a README file**
   - **Add .gitignore**: Selecciona **Python**
4. Haz clic en **Create repository**

> **Limite GitHub Free**:
> - Repositorios publicos: **2,000 minutos Actions/mes** (suficiente para este proyecto)
> - Repositorios privados: **500 minutos Actions/mes**
> - Este proyecto usa ~20-50 min/mes, asi que no hay problema con ninguno

### 4.2 Subir Codigo al Repositorio

**Opcion A: GitHub Desktop (recomendado)**
1. Descarga [GitHub Desktop](https://desktop.github.com/) (gratis)
2. En tu repositorio web, haz clic en **Code** > **Open with GitHub Desktop**
3. Clona el repositorio
4. Copia todos los archivos del proyecto a la carpeta clonada
5. GitHub Desktop detectara los cambios
6. Escribe: `feat: ENLA 2026 pipeline - 100% free tier deployment`
7. Haz clic en **Commit to main**
8. Haz clic en **Push origin**

**Opcion B: Web (para pocos archivos)**
1. En tu repositorio, haz clic en **Add file** > **Upload files**
2. Arrastra los archivos/carpetas
3. Haz clic en **Commit changes**

### 4.3 Configurar GitHub Secrets

1. En tu repositorio, ve a **Settings** > **Secrets and variables** > **Actions**
2. Haz clic en **New repository secret**
3. Agrega estos 4 secretos:

| Nombre del Secreto | Valor | Donde obtenerlo |
|-------------------|-------|-----------------|
| `GCP_PROJECT_ID` | ID de tu proyecto GCP | GCP Console > Project Selector |
| `GCP_SA_KEY` | Contenido del archivo JSON descargado | Archivo descargado en paso 1.5 |
| `MONGODB_URI` | URI de MongoDB Atlas | Atlas > Connect > Connection String |
| `SENDGRID_API_KEY` | API Key de SendGrid | SendGrid > Settings > API Keys |

4. Para cada secreto:
   - Escribe el **Name** exactamente como aparece
   - Pega el **Value**
   - Haz clic en **Add secret**

> **NOTA**: El secreto `GCP_SA_KEY` debe ser el contenido COMPLETO del archivo JSON (incluye las llaves `{}`). No agregues comillas extra.

---

## 5. Flujos de Trabajo GitHub Actions (Free)

Una vez subidos los archivos `.github/workflows/*.yml`, GitHub Actions se activara automaticamente.

### 5.1 Workflows Disponibles

| Workflow | Archivo | Cuando se ejecuta | Minutos consumidos |
|----------|---------|-------------------|-------------------|
| **CI Pipeline** | `ci.yml` | Cada push/PR a main/develop | ~2-3 min por ejecucion |
| **Terraform CI/CD** | `terraform.yml` | Push a main en `terraform/**` | ~3-5 min |
| **Deploy Cloud Function** | `deploy-cloud-function.yml` | Push a main en `gcp/functions/**` o `src/**` | ~5-8 min |
| **Deploy dbt Models** | `dbt.yml` | Push a main en `dbt/**` | ~3-5 min |
| **Trigger Full Pipeline** | `pipeline-trigger.yml` | Manual O diario 10 PM Peru | ~10-15 min |

**Consumo estimado mensual**: ~30-50 minutos (de 2,000 disponibles gratis).

### 5.2 Estructura de Archivos

Verifica que estos archivos existan en tu repositorio:

```
.github/
  workflows/
    ci.yml                      ✅ Tests automaticos
    terraform.yml               ✅ Infraestructura automatica
    deploy-cloud-function.yml   ✅ Deploy Cloud Function
    dbt.yml                     ✅ Deploy dbt models
    pipeline-trigger.yml        ✅ Pipeline completo (manual + diario)
  ISSUE_TEMPLATE/
    bug-report.md
    feature-request.md
  PULL_REQUEST_TEMPLATE.md
SECRETS_SETUP.md
docs/
  GUIA_DESPLEGUE_CLOUD.md       ✅ Esta guia
```

---

## 6. Como Ejecutar Pipelines Manualmente

### 6.1 Ejecutar Pipeline Completo Manualmente

1. En tu repositorio GitHub, ve a la pestaña **Actions**
2. En el panel izquierdo, selecciona **Trigger Full Pipeline**
3. Haz clic en **Run workflow** (boton desplegable a la derecha)
4. Configura:
   - **Branch**: `main`
   - **model_version**: `v1`
   - **email_recipients**: Tu email para recibir la alerta de prueba
5. Haz clic en **Run workflow** (boton verde)
6. Veras una nueva ejecucion en la lista — haz clic para ver el progreso

### 6.2 Ejecucion Programada (Cron)

El pipeline se ejecuta automaticamente todos los dias a las **03:00 UTC** (10:00 PM hora Peru).
- No requiere intervencion manual
- Consume ~10-15 minutos de tu cuota gratuita diaria
- Revisa la pestana **Actions** para ver las ejecuciones

> **Si quieres desactivar el cron** para ahorrar minutos de GitHub Actions:
> 1. Edita `.github/workflows/pipeline-trigger.yml`
> 2. Elimina o comenta la seccion `schedule:`
> 3. Haz commit del cambio
> 4. El pipeline solo se ejecutara cuando lo actives manualmente

---

## 7. Monitoreo de Ejecuciones

### 7.1 Ver Estado de Workflows (GitHub)

1. Ve a la pestana **Actions** en tu repositorio
2. Veras todas las ejecuciones:
   - ✅ **Verde**: Exitosa
   - ❌ **Rojo**: Fallo
   - 🟡 **Amarillo**: En progreso

### 7.2 Ver Logs Detallados

1. Haz clic en una ejecucion especifica
2. Haz clic en un **job** para expandirlo
3. Haz clic en un **step** para ver sus logs

### 7.3 Monitoreo en Google Cloud Console (Gratis)

#### Cloud Functions Logs
1. Ve a **Cloud Functions** en GCP Console
2. Haz clic en `enla-pipeline-orchestrator`
3. Ve a la pestana **LOGS** — aqui veras todas las invocaciones (gratis con Cloud Logging Free Tier: 50 GB ingestion/mes)

#### BigQuery Data
1. Ve a **BigQuery** en GCP Console
2. Navega a `BI_ENLA`
3. Haz clic en una tabla > **Preview** para ver los datos
4. Haz clic en **Query** para ejecutar consultas SQL (gratis dentro del 1 TB mensual)

#### Verificacion de Costos (Importante)
1. Ve a **Billing** > **Cost management** > **Costs**
2. Revisa el grafico — deberia mostrar **$0.00** o centavos minimos
3. Si ves algo mayor a $0.10, revisa que no haya recursos innecesarios

---

## 8. Creacion de Dashboard en Looker Studio (Gratis)

### 8.1 Conectar BigQuery con Looker Studio

1. Abre [Looker Studio](https://lookerstudio.google.com/) (gratis con tu cuenta Gmail)
2. Haz clic en **Create** > **Report**
3. Selecciona **BigQuery** como fuente de datos
4. Autoriza la conexion (es gratis)
5. Selecciona:
   - **Project**: Tu proyecto GCP
   - **Dataset**: `BI_ENLA`
   - **Table**: Las vistas creadas por dbt:
     - `v_callao_comunicacion_2026`
     - `v_callao_matematica_2026`
     - `v_callao_ccss_2026`
     - `v_callao_cyt_2026`
     - `v_callao_resumen_todas_areas`
6. Haz clic en **Add to Report**

### 8.2 Crear Dashboard por Area (Ejemplo: Comunicacion)

**Paso 1: Titulo**
1. Haz clic en el titulo del reporte
2. Cambialo a: `ENLA 2026 - Comunicacion - Callao`

**Paso 2: KPI Cards (4 metricas principales)**
1. **Add a chart** > **Scorecard**
2. Configura 4 scorecards con:
   - **Total instituciones**: `COUNT(institution_id)`
   - **% Riesgo ALTO**: Crea campo calculado `alto_risk_pct`
   - **Promedio confianza**: `AVG(confidence)`
   - **Score promedio 2023**: `AVG(avg_score_2023)`

**Paso 3: Grafico de Distribucion de Riesgo**
1. **Add a chart** > **Bar chart**
2. Configura:
   - **Dimension**: `risk_level`
   - **Metric**: `COUNT(institution_id)`
   - Colores: Rojo (ALTO), Amarillo (MEDIO), Verde (BAJO)

**Paso 4: Tabla de Instituciones**
1. **Add a chart** > **Table**
2. Columnas: `nom_ie`, `avg_score_2023`, `trend`, `risk_level`, `confidence`
3. Ordena por `confidence` ascendente (las mas inciertas primero)

**Paso 5: Filtros**
1. **Add a control** > **Drop-down list**
2. Campo: `risk_level`
3. Label: "Filtrar por nivel de riesgo"

### 8.3 Duplicar para las Otras Areas

1. En Looker Studio, ve a **File** > **Make a copy**
2. Cambia la fuente de datos a la vista del area siguiente
3. Cambia el titulo
4. Repite para las 4 areas

### 8.4 Dashboard Ejecutivo (Resumen)

1. Crea nuevo reporte
2. Conecta a `v_callao_resumen_todas_areas`
3. Configura:
   - **Tabla resumen**: area, total, alto_risk_count, medio_risk_count, bajo_risk_count
   - **Grafico comparativo**: Bar chart con area vs avg_score_2023
   - **Heatmap**: Tabla con formato condicional de riesgo por area

### 8.5 Compartir el Dashboard

1. Haz clic en **Share** (esquina superior derecha)
2. Agrega emails de DRE Callao con acceso **Can view** (solo lectura)
3. O copia el enlace y compartelo

> **Looker Studio es 100% gratuito** — no hay limite de dashboards, usuarios ni consultas.

---

## 9. Control de Costos (Evitar Cobros)

### 9.1 Checklist de Seguridad Financiera

Antes de cualquier despliegue, verifica:

- [ ] **Budget alert** configurado a $1.00 en GCP (paso 1.2)
- [ ] **Cloud Storage**: Solo clase Standard, max 5 GB
- [ ] **BigQuery**: Solo consultas necesarias (evita `SELECT *` en tablas grandes)
- [ ] **Cloud Functions**: Solo 1 funcion, timeout 540s (maximo gratuito)
- [ ] **MongoDB Atlas**: Solo cluster M0 (512 MB), no upgrades
- [ ] **SendGrid**: Solo 100 emails/dia, no upgrades
- [ ] **GitHub**: Repositorio publico (2,000 min Actions vs 500 en privado)

### 9.2 Como Nunca Pagar Nada en GCP

1. **Nunca hagas clic en "Upgrade"** en ningun servicio
2. **Nunca crees instancias de Compute Engine** (VMs tienen costo)
3. **Nunca uses Cloud SQL** (base de datos gestionada tiene costo)
4. **Nunca actives Dataflow o Dataproc** (procesamiento distribuido tiene costo)
5. **Siempre revisa Billing > Costs** antes de dormir
6. **Si ves un cargo**, ve a Billing > Payments y solicita reembolso dentro de los primeros 30 dias

### 9.3 Recursos a Eliminar si Dejas de Usar el Proyecto

Si quieres asegurarte de que no haya cobros futuros:

1. **Cloud Functions**: Ve a Cloud Functions > selecciona la funcion > clic en **Delete**
2. **Cloud Storage bucket**: Ve al bucket > vacia el contenido > clic en **Delete**
3. **BigQuery dataset**: Ve a BigQuery > dataset `BI_ENLA` > clic en **Delete dataset**
4. **Secret Manager**: Ve a Secret Manager > borra los secretos
5. **Service Account**: Ve a IAM > Service Accounts > elimina `enla-pipeline-sa`

> **MongoDB Atlas, SendGrid y GitHub** no cobran nada si no los usas. Puedes dejar las cuentas abiertas sin riesgo.

### 9.4 Verificacion Rapida de Costos

```
GCP Console > Billing > Cost management > Costs
→ Deberia mostrar: $0.00 o centavos (menos de $0.01)

Si ves mas de $0.10:
1. Revisa Billing > Reports > Group by: Service
2. Identifica que servicio esta generando costo
3. Elimina el recurso innecesario
```

---

## 10. Solucion de Problemas

### Error: `Could not load default credentials`

**Causa**: El secreto `GCP_SA_KEY` esta mal configurado

**Solucion**:
1. Ve a **Settings** > **Secrets and variables** > **Actions**
2. Edita `GCP_SA_KEY`
3. Asegurate de que sea JSON valido (empieza con `{` y termina con `}`)
4. No agregues comillas extra ni espacios

### Error: `MongoDB connection timeout`

**Causa 1**: IP no whitelisteada

**Solucion**:
1. MongoDB Atlas > **Network Access**
2. Verifica que `0.0.0.0/0` este en la lista

**Causa 2**: URI incorrecta

**Solucion**:
1. Verifica que `MONGODB_URI` tenga el formato correcto
2. Asegurate de haber reemplazado `<username>` y `<password>`

### Error: `SendGrid API key invalid`

**Solucion**:
1. SendGrid > **Settings** > **API Keys**
2. Verifica que la API key exista y no este revocada
3. Si es necesario, crea una nueva y actualiza el secreto
4. Verifica que el remitente este verificado en **Sender Authentication**

### Error: `Permission denied` en GCP

**Solucion**:
1. GCP Console > **IAM & Admin** > **IAM**
2. Busca `enla-pipeline-sa@...`
3. Verifica que tenga estos roles:
   - `BigQuery Admin`
   - `Cloud Functions Developer`
   - `Storage Admin`
   - `Secret Manager Admin`

### Error: GitHub Actions consume muchos minutos

**Solucion**:
1. Edita `.github/workflows/pipeline-trigger.yml`
2. Comenta o elimina la seccion `schedule:` para desactivar el cron diario
3. Ejecuta el pipeline solo manualmente cuando lo necesites

### Error: MongoDB Atlas se pauso por inactividad

**Solucion**:
1. Ve a MongoDB Atlas
2. Haz clic en el cluster pausado
3. Haz clic en **Resume** (es gratis, tarda 1-2 minutos)
4. Esto pasa solo despues de 10 dias sin uso — es normal del Free Tier

---

## Apendice: Checklist Pre-Despliegue

### Checklist Completo (Todo Gratis)

- [ ] Cuenta Gmail creada
- [ ] Cuenta GCP creada con $300 creditos gratuitos
- [ ] Budget alert configurado a $1.00
- [ ] APIs habilitadas (BigQuery, Cloud Functions, etc.)
- [ ] Service Account `enla-pipeline-sa` creada con clave JSON
- [ ] Cloud Storage bucket creado (clase Standard, 5 GB gratis)
- [ ] Dataset `BI_ENLA` creado en BigQuery
- [ ] MongoDB Atlas cluster M0 creado (512 MB gratis)
- [ ] Usuario MongoDB creado (`enla_app_user`)
- [ ] Network Access configurado (0.0.0.0/0)
- [ ] SendGrid cuenta creada (100 emails/dia gratis)
- [ ] Remitente verificado en SendGrid
- [ ] API Key de SendGrid generada
- [ ] Repositorio GitHub creado (Public = 2,000 min Actions gratis)
- [ ] Codigo subido (incluyendo `.github/workflows/`)
- [ ] GitHub Secrets configurados (4 secretos):
  - [ ] `GCP_PROJECT_ID`
  - [ ] `GCP_SA_KEY`
  - [ ] `MONGODB_URI`
  - [ ] `SENDGRID_API_KEY`

---

## Resumen de Consolas Gratuitas

| Servicio | URL | Plan Gratuito | Limite |
|----------|-----|--------------|--------|
| **Google Cloud Console** | https://console.cloud.google.com | Free Tier + $300 creditos | BigQuery 1 TB/mes, CF 2M/mes, Storage 5 GB |
| **MongoDB Atlas** | https://cloud.mongodb.com | M0 Sandbox | 512 MB, 5 GB transferencia/mes |
| **GitHub** | https://github.com | Free Plan | 2,000 min Actions/mes (public) |
| **SendGrid** | https://app.sendgrid.com | Free Plan | 100 emails/dia |
| **Looker Studio** | https://lookerstudio.google.com | Free | Ilimitado |

### Costo Total Estimado

| Concepto | Costo Mensual |
|----------|--------------|
| Google Cloud (dentro de Free Tier) | **$0.00** |
| MongoDB Atlas M0 | **$0.00** |
| SendGrid Free | **$0.00** |
| GitHub Free | **$0.00** |
| Looker Studio | **$0.00** |
| **TOTAL** | **$0.00** |

---

**Documento preparado para**: Direccion Regional de Educacion de Callao (DRE Callao)
**Proyecto**: ENLA 2026 Callao - Prediccion de Resultados ENLA
**Fecha**: Mayo 2026
**Version**: 2.0 (100% Free Tier)
**Costo total**: **$0.00**
