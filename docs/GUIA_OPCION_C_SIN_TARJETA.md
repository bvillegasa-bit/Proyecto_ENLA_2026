# Guia de Despliegue 100% Gratis — SIN Tarjeta de Credito

## Resumen

Todo funciona con servicios gratuitos que NO requieren tarjeta de credito.

Arquitectura:
Excel → Google Sheets → Google Colab (ML) → Looker Studio
  ↕           ↕              ↕
GitHub    MongoDB Atlas   SendGrid
Actions   (gratis M0)     (100 emails/dia)

## Tabla de Servicios (Sin Tarjeta)

| Servicio | Funcion | Costo | Tarjeta? |
|----------|---------|-------|----------|
| Google Sheets | Data Warehouse | Gratis | ❌ No |
| Google Colab | Python + ML (scikit-learn) | Gratis | ❌ No |
| GitHub Actions | CI/CD + automatizacion | 2000 min/mes | ❌ No |
| MongoDB Atlas M0 | Staging (512 MB) | Gratis | ❌ No |
| SendGrid Free | Email alerts (100/dia) | Gratis | ❌ No |
| Looker Studio | Dashboards | Gratis | ❌ No |
| Google Drive | Almacenamiento archivos | 15 GB | ❌ No |

## Paso 1: Preparar Google Sheets como Data Warehouse

### 1.1 Crear la Hoja de Calculo Principal
1. Ve a https://sheets.google.com
2. Crea una nueva hoja de calculo
3. Renombrala: "ENLA 2026 - Callao - Data Warehouse"
4. Crea las siguientes pestañas (tabs):
   - `raw_data` — Datos crudos importados del Excel
   - `fact_enla` — Datos limpios en formato largo
   - `features` — Features calculadas (avg, trend, variance)
   - `predictions` — Predicciones del modelo ML
   - `model_metrics` — Metricas de evaluacion del modelo
   - `alerts_log` — Registro de alertas enviadas

### 1.2 Configurar Estructura de Cada Pestaña

**raw_data** (columnas A-J):
| id_ie | id_seccion | nom_ie | nom_dre | ano_evaluacion | cor_est_comunicacion | cor_est_matematica | cor_est_ccss | cor_est_cyt | grado_evaluacion |

**fact_enla** (columnas A-G):
| fact_id | id_ie | nom_ie | year | area | score | area_display |

**features** (columnas A-L):
| institution_id | nom_ie | area | avg_score_2023 | avg_score_2022 | avg_score_2021 | trend | variance | target | norm_avg_2023 | norm_trend | norm_variance |

**predictions** (columnas A-H):
| prediction_id | institution_id | nom_ie | area | predicted_success | confidence | risk_level | model_version |

**model_metrics** (columnas A-G):
| area | model_name | accuracy | precision | recall | f1_score | training_date |

**alerts_log** (columnas A-F):
| alert_id | alert_type | area | recipients | send_timestamp | status |

### 1.3 Compartir la Hoja
1. Clic en "Compartir" (esquina superior derecha)
2. Configura como "Cualquier persona con el enlace puede editar"
   (O mas restrictivo si prefieres)
3. Copia el enlace — lo necesitas para el Colab notebook

## Paso 2: Configurar Google Colab para ML

### 2.1 Crear el Notebook
1. Ve a https://colab.research.google.com
2. Clic en "Nuevo notebook"
3. Renombralo: "ENLA 2026 - Pipeline ML"
4. Guarda en tu Google Drive

### 2.2 Ejecutar el Notebook
El notebook (que ya esta creado en este proyecto) hace todo automaticamente:
1. Lee datos de Google Sheets
2. Limpia y transforma datos
3. Calcula features (trend, variance, normalizacion)
4. Entrena 4 modelos Logistic Regression (scikit-learn)
5. Genera predicciones con nivel de riesgo
6. Escribe resultados de vuelta a Google Sheets
7. Envia alertas por email (si hay riesgo ALTO)

### 2.3 Configurar Credenciales en Colab
1. La primera vez que ejecutes el notebook, te pedira autorizar acceso a Google Sheets
2. Haz clic en "Autorizar acceso"
3. Selecciona tu cuenta de Google
4. Acepta los permisos
5. Copia el codigo de autorizacion y pegalo en el notebook

## Paso 3: Subir Datos desde Excel

### 3.1 Importar Excel a Google Sheets
1. Abre tu Google Sheet creada en Paso 1
2. Ve a la pestaña `raw_data`
3. Menu: Archivo > Importar > Subir
4. Selecciona el archivo `BD_2SENLAmuestral2023.xlsx`
5. Configura:
   - Tipo de importacion: "Reemplazar hoja de calculo" o "Insertar nuevas hojas"
   - Separador: Automatico
6. Clic en "Importar datos"

### 3.2 Verificar Importacion
- Deberias ver los datos en la pestaña `raw_data`
- Filtra por nom_dre = "CALLAO" y grado_evaluacion = 2
- Deberias tener datos de los anos 2021, 2022, 2023

## Paso 4: Ejecutar el Pipeline ML en Colab

### 4.1 Abrir el Notebook
1. Abre el notebook "ENLA 2026 - Pipeline ML" en Google Colab
2. O sube el archivo `.ipynb` del proyecto a Google Drive y abrelo desde Colab

### 4.2 Configurar Parametros
En la primera celda del notebook, modifica:
```python
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/TU_SHEET_ID/edit"
MONGODB_URI = "mongodb+srv://user:pass@cluster.mongodb.net/"
SENDGRID_API_KEY = "SG.xxxxx.yyyyy"
ALERT_EMAILS = ["tu-email@gmail.com"]
```

### 4.3 Ejecutar Todo
1. Menu: Tiempo de ejecucion > Ejecutar todo
2. O ejecuta celda por celda con Shift+Enter
3. El proceso tarda ~3-5 minutos

### 4.4 Verificar Resultados
- Vuelve a tu Google Sheet
- Revisa las pestañas `features`, `predictions`, `model_metrics`
- Deberias ver los datos generados automaticamente

## Paso 5: Crear Dashboards en Looker Studio

### 5.1 Conectar Looker Studio a Google Sheets
1. Abre https://lookerstudio.google.com
2. Clic en "Crear" > "Informe"
3. Selecciona "Hojas de calculo de Google" como fuente
4. Selecciona tu hoja "ENLA 2026 - Callao - Data Warehouse"
5. Selecciona la pestaña `predictions`
6. Clic en "Añadir al informe"

### 5.2 Crear Dashboard por Area
Para cada area (Comunicacion, Matematica, CCSS, CyT):

1. **Titulo**: "ENLA 2026 - [Area] - Callao"
2. **KPI Cards**:
   - Total instituciones: COUNT(institution_id)
   - % Riesgo ALTO: COUNTIF(risk_level="ALTO") / COUNT * 100
   - Promedio confianza: AVG(confidence)
3. **Grafico de barras**: Distribucion de riesgo (ALTO/MEDIO/BAJO)
4. **Tabla**: institution_id, nom_ie, confidence, risk_level

### 5.3 Dashboard Ejecutivo
1. Crea nuevo informe
2. Conecta a la pestaña `predictions`
3. Agrega filtro por area
4. Crea tabla resumen por area

### 5.4 Compartir
1. Clic en "Compartir"
2. Agrega emails con acceso "Puede ver"

## Paso 6: Automatizar con GitHub Actions

### 6.1 Configurar Workflow Diario
El archivo `.github/workflows/pipeline-trigger.yml` ya esta configurado para:
- Ejecutarse manualmente desde la pestaña Actions
- O automaticamente todos los dias a las 10:00 PM Peru

### 6.2 Ejecutar Manualmente
1. Ve a tu repositorio GitHub > pestana Actions
2. Selecciona "Trigger Full Pipeline"
3. Clic en "Run workflow"
4. El workflow:
   - Descarga el notebook de Colab
   - Lo ejecuta con Python
   - Actualiza Google Sheets con nuevos datos

## Paso 7: Configurar MongoDB Atlas (Staging)

### 7.1 Crear Cluster Gratuito
1. Ve a https://cloud.mongodb.com
2. Registrate (no requiere tarjeta)
3. Crea cluster M0 FREE (512 MB)
4. Crea usuario de base de datos
5. Configura Network Access: 0.0.0.0/0
6. Copia la URI de conexion

### 7.2 Uso en el Pipeline
MongoDB se usa como cache intermedio:
- El notebook de Colab lee de Sheets → escribe a MongoDB
- La siguiente ejecucion lee de MongoDB → compara con Sheets
- Esto evita duplicados y permite historial

## Paso 8: Configurar SendGrid (Alertas)

### 8.1 Crear Cuenta Gratuita
1. Ve a https://signup.sendgrid.com
2. Registrate (no requiere tarjeta)
3. Verifica tu email
4. Verifica un remitente (Single Sender)
5. Genera API Key

### 8.2 Uso en el Pipeline
El notebook de Colab envia alertas automaticamente cuando:
- Detecta instituciones con riesgo ALTO
- El modelo tiene baja confianza (<55%)
- Hay errores en el pipeline

## Solucion de Problemas

### Error de autorizacion de Google Sheets
- Solucion: Vuelve a ejecutar la celda de autenticacion y acepta los permisos

### Error de conexion a MongoDB
- Solucion: Verifica que la URI sea correcta y que 0.0.0.0/0 este en Network Access

### Error de SendGrid
- Solucion: Verifica que el remitente este verificado y la API Key sea valida

### Looker Studio no muestra datos
- Solucion: Verifica que Google Sheets tenga datos en las pestañas correctas
- Refresca la conexion de datos en Looker Studio

## Resumen de Costos

| Servicio | Costo Mensual |
|----------|--------------|
| Google Sheets | $0.00 |
| Google Colab | $0.00 |
| GitHub Actions | $0.00 |
| MongoDB Atlas M0 | $0.00 |
| SendGrid Free | $0.00 |
| Looker Studio | $0.00 |
| Google Drive (15 GB) | $0.00 |
| **TOTAL** | **$0.00** |

## Limitaciones de esta Opcion

- Google Sheets: Maximo 10 millones de celdas (suficiente para este proyecto)
- Google Colab: Se desconecta despues de 12 horas de inactividad (no afecta, el pipeline corre en ~5 min)
- GitHub Actions: 2,000 minutos/mes para repos publicos (usamos ~20-50 min)
- MongoDB Atlas M0: 512 MB almacenamiento (~5-10 MB usados)