# Guía: Configuración SIN Facturación (BigQuery Sandbox)

> **Para el proyecto ENLA 2026 Callao**
> Última actualización: 2026-05-03

---

## 🎯 Resumen

Esta guía explica cómo configurar todo el proyecto **SIN necesidad de activar billing** en Google Cloud Platform.

### Arquitectura Sin Billing

```
Excel/Google Sheets
       ↓
MongoDB Atlas M0 (staging - 512 MB gratis)
       ↓
GitHub Actions (orquestación - 2000 min/mes gratis)
       ↓
BigQuery Sandbox (Data Warehouse - 10 GB + 1 TB consultas/mes)
       ↓
Looker Studio (Dashboards - gratis)
       ↓
SendGrid (Alertas - 100 emails/día gratis)
```

### Tabla de Servicios (Sin Tarjeta)

| Servicio | Función | Costo | ¿Requiere Tarjeta? |
|----------|---------|-------|---------------------|
| **BigQuery Sandbox** | Data Warehouse | Gratis (10 GB + 1 TB/mes) | ❌ No |
| **GitHub Actions** | CI/CD + Orquestación | 2000 min/mes | ❌ No |
| **Looker Studio** | Dashboards | Gratis | ❌ No |
| **MongoDB Atlas M0** | Staging | 512 MB | ❌ No |
| **SendGrid Free** | Alertas email | 100/día | ❌ No |
| **Google Colab** | ML (scikit-learn) | Gratis | ❌ No |

---

## ✅ Paso 1: Activar BigQuery Sandbox

BigQuery Sandbox te permite usar BigQuery **sin cuenta de facturación**.

### 1.1. Crear proyecto y activar Sandbox

1. Ve a: https://console.cloud.google.com/bigquery
   - **IMPORTANTE**: Usa esta URL directa, NO vayas al console general
2. Si no tienes un proyecto, crea uno:
   - Clic en el selector de proyectos (arriba a la izquierda)
   - Clic en **NUEVO PROYECTO**
   - Nombre: `enla-2026-callao`
   - Clic en **CREAR**
3. Verifica que Sandbox está activo:
   - Busca el texto **"Sandbox mode"** o **"Modo Sandbox"** cerca del nombre del proyecto
   - Si lo ves, ¡felicidades! Sandbox está activo sin billing

### 1.2. Crear el dataset `BI_ENLA`

1. En el panel izquierdo, clic en tu proyecto (`enla-2026-callao`)
2. Clic en los 3 puntos `⋮` → **Crear dataset**
3. Configuración:
   - **ID del dataset**: `BI_ENLA`
   - **Ubicación**: `US` (o `southamerica-east1` para menor latencia en Perú)
   - **Tiempo de expiración de la tabla**: 60 días (puedes cambiarlo después)
4. Clic en **CREAR DATASET**

### 1.3. Verificar que funciona

Ejecuta esta consulta en el editor de SQL:
```sql
SELECT "BigQuery Sandbox funciona correctamente" AS mensaje
```

---

## ✅ Paso 2: Configurar GitHub Actions (Ya Listo)

Los workflows ya están configurados en `.github/workflows/`:

| Workflow | Propósito | Activación |
|----------|------------|-------------|
| `run-notebook.yml` | Ejecuta pipeline ETL | Manual + Diario 03:00 UTC |
| `pipeline-trigger.yml` | Orquestación completa (ETL+ML+Alerts) | Manual + Diario 03:00 UTC |
| `dbt.yml` | Ejecuta modelos dbt en BigQuery | Al hacer push a `dbt/**` |

### 2.1. Configurar Secrets en GitHub

En tu repositorio de GitHub:
1. Ve a **Settings > Secrets and variables > Actions**
2. Agrega estos secrets:
   - `GCP_SA_KEY`: Contenido del archivo JSON de credenciales de GCP (o usa autenticación OAuth en Colab)
   - `GCP_PROJECT_ID`: `enla-2026-callao`
   - `MONGODB_URI`: Tu connection string de MongoDB Atlas
   - `SENDGRID_API_KEY`: Tu API key de SendGrid
   - `EMAIL_FROM`: Tu email remitente verificado
   - `EMAIL_TO`: Email(s) destinatario(s)

> **NOTA**: Para BigQuery Sandbox, puedes usar autenticación OAuth desde Google Colab sin necesidad del archivo JSON de credenciales.

---

## ✅ Paso 3: Cloud Functions DESHABILITADO

⚠️ **Cloud Functions requiere billing** y ha sido **DESHABILITADO**:

- El archivo `.github/workflows/deploy-cloud-function.yml` fue renombrado a `.DISABLED`
- **GitHub Actions maneja toda la orquestación** del pipeline
- No necesitas Cloud Functions para este proyecto académico

---

## ✅ Paso 4: Ejecutar el Pipeline (Opciones)

### Opción A: Google Colab (Recomendado para desarrollo)

1. Abre el notebook: `notebooks/enla_2026_pipeline_bq.ipynb` en Google Colab
2. Autentícate con tu cuenta de Google (sin necesidad de archivo JSON)
3. Configura las credenciales en el notebook:
   ```python
   MONGODB_URI = "mongodb+srv://user:pass@cluster.mongodb.net/"
   SENDGRID_API_KEY = "SG.xxxxx"
   GCP_PROJECT_ID = "enla-2026-callao"
   ```
4. Ejecuta todas las celdas: **Runtime > Run all**

### Opción B: GitHub Actions (Automatizado)

1. Ve a tu repositorio GitHub > pestaña **Actions**
2. Selecciona "Trigger Full Pipeline"
3. Clic en **Run workflow**
4. El pipeline se ejecutará automáticamente

---

## ✅ Paso 5: Crear Dashboards en Looker Studio

1. Abre https://lookerstudio.google.com
2. Clic en **Crear > Informe**
3. Fuente de datos: **BigQuery**
4. Navega: `enla-2026-callao > BI_ENLA > predictions`
5. Clic en **Conectar**

### 5.1. Dashboard de Resumen Ejecutivo

| Fila | Elemento | Configuración |
|------|----------|---------------|
| 1 | Título | "Resumen Ejecutivo ENLA 2026 - Callao" |
| 2 | KPI cards (4 columnas) | Comunicación, Matemática, CCSS, CyT |
| 3 | Tabla de riesgo por área | Dimensión: `area`, Métricas: count por `risk_level` |
| 4 | Comparativa de score | Bar chart: area vs avg score |
| 5 | Heatmap de riesgo | Table heatmap: area × risk_level |

---

## 🔧 Limitaciones de BigQuery Sandbox

| Limitación | Detalle | Solución |
|------------|---------|-----------|
| **Almacenamiento** | 10 GB máximo | Suficiente para este proyecto académico |
| **Consultas** | 1 TB/mes | Monitorea en GCP Console |
| **DML después de 90 días** | No permite INSERT/UPDATE/DELETE | Usar `load_table_from_dataframe` con `WRITE_TRUNCATE` |
| **Tablas expiran** | 60 días por defecto | Extender en BigQuery Console o recargar datos |
| **Scheduled queries** | No disponible | Usar GitHub Actions para programar ejecuciones |
| **BigQuery ML** | No disponible | Usar scikit-learn en Google Colab |

---

## 📊 Verificar Configuración

- [x] Proyecto creado en GCP (`enla-2026-callao`)
- [x] Sandbox activo (ves el texto "Sandbox" en la consola)
- [x] Dataset `BI_ENLA` creado
- [x] Consulta de prueba ejecutada exitosamente
- [x] GitHub Actions configurado (secrets agregados)
- [x] Cloud Functions deshabilitado (`.DISABLED`)
- [x] MongoDB Atlas M0 configurado
- [x] SendGrid configurado

---

## 🆘 Solución de Problemas

### Error: "Sandbox mode - DML operations not allowed"

**Causa**: BigQuery Sandbox no permite operaciones DML (INSERT/UPDATE/DELETE) después de 90 días.

**Solución**: Usar `load_table_from_dataframe` con `WRITE_TRUNCATE`:
```python
job = client.load_table_from_dataframe(
    df,
    table_id,
    job_config=bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE"
    )
)
```

### Error: "Table expired" en BigQuery

**Causa**: Las tablas en Sandbox expiran en 60 días.

**Solución**:
1. En BigQuery Console: clic en la tabla > Details > Edit > Expiration time
2. O volver a cargar los datos periódicamente

### Error en GitHub Actions: "GCP_SA_KEY not found"

**Solución**:
1. Ve a Settings > Secrets and variables > Actions
2. Verifica que el secret `GCP_SA_KEY` esté agregado
3. El archivo JSON debe ser una sola línea válida de JSON

---

## 📚 Referencias

- **BigQuery Sandbox Docs**: https://cloud.google.com/bigquery/docs/sandbox
- **GitHub Actions Docs**: https://docs.github.com/en/actions
- **Looker Studio Help**: https://support.google.com/looker-studio
- **MongoDB Atlas Docs**: https://docs.atlas.mongodb.com/
- **SendGrid Docs**: https://docs.sendgrid.com/

---

**Documentación preparada para arquitectura sin facturación (BigQuery Sandbox + GitHub Actions).**
**Costo total: $0.00/mes para el uso típico de este proyecto académico.**
