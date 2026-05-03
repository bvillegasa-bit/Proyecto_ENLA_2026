# Guia de Despliegue Completo — ENLA 2026 Callao

> **De la subida de datos a los dashboards de Looker Studio**
> Ultima actualizacion: 2026-05-03

---

## 🎯 ARQUITECTURA SIN FACTURACIÓN (RECOMENDADO)

Este proyecto está configurado para funcionar **SIN necesidad de activar billing**:

| Componente | Servicio | Costo | Requiere Tarjeta? |
|------------|----------|-------|-------------------|
| Almacenamiento | **BigQuery Sandbox** | Gratis (10 GB + 1 TB/mes) | ❌ No |
| Orquestación | **GitHub Actions** | Gratis (2000 min/mes) | ❌ No |
| Dashboards | **Looker Studio** | Gratis | ❌ No |
| Staging | **MongoDB Atlas M0** | Gratis (512 MB) | ❌ No |
| Alertas | **SendGrid Free** | Gratis (100 emails/día) | ❌ No |

**Cloud Functions está DESHABILITADO** (requiere billing). GitHub Actions ejecuta el pipeline automáticamente.

### Inicio Rápido (Sin Billing)

1. **BigQuery Sandbox**: Ve a https://console.cloud.google.com/bigquery → Crea proyecto → Sandbox se activa automáticamente
2. **GitHub Actions**: Los workflows `run-notebook.yml` y `pipeline-trigger.yml` ya están configurados
3. **Looker Studio**: Conecta a tu BigQuery Sandbox para dashboards

---

---

## FASE 0: Preparacion del Entorno

### 0.1. Herramientas requeridas

```bash
# Verificar herramientas instaladas
python --version          # >= 3.9
pip --version
git --version
gcloud --version          # Google Cloud SDK (opcional)
```

Si falta alguna:

```bash
# Google Cloud SDK (Windows)
# Descargar: https://cloud.google.com/sdk/docs/install#windows
# O usar: choco install googlecloudsdk

# Python dependencies
pip install --upgrade pip
```

### 0.2. Configurar Cuenta de Google (Sin Tarjeta — Opcion C)

> **NOTA**: En la Opcion C **NO necesitas Google Cloud SDK (gcloud)** ni cuenta de facturacion.
> Solo necesitas una cuenta de Gmail para usar Google Sheets, Colab y Looker Studio.

```powershell
# NO necesitas instalar gcloud ni habilitar APIs de GCP
# Solo verifica que tengas acceso a estos servicios gratuitos:

# 1. Google Sheets — abre en el navegador:
Start-Process "https://sheets.google.com"

# 2. Google Colab — abre en el navegador:
Start-Process "https://colab.research.google.com"

# 3. Looker Studio — abre en el navegador:
Start-Process "https://lookerstudio.google.com"

# 4. Google Drive — verifica tu espacio (15 GB gratis):
Start-Process "https://drive.google.com"
```

**Si quieres usar Google Cloud CLI opcionalmente** (solo para consultas BigQuery si tienes acceso):

```powershell
# Descargar Google Cloud SDK: https://cloud.google.com/sdk/docs/install#windows
# O usar Chocolatey:
choco install googlecloudsdk

# Autenticar (solo si tienes proyecto GCP con billing):
gcloud auth login
gcloud config set project TU_PROJECT_ID

# Verificar servicios habilitados:
gcloud services list --filter="state:ENABLED"
```

### 0.3. Tabla de Equivalencias: GCP vs Alternativas Sin Tarjeta

| Servicio GCP (requiere billing) | Lo que usamos ahora | Tarjeta? |
|--------------------------------|---------------------|----------|
| BigQuery (con billing) | **BigQuery Sandbox** | ❌ No |
| Cloud Functions | **Google Colab** | ❌ No |
| Cloud Storage | **MongoDB Atlas M0** | ❌ No |
| Secret Manager | **GitHub Secrets** | ❌ No |
| BigQuery ML | **scikit-learn en Colab** | ❌ No |
| Cloud Build | **GitHub Actions** | ❌ No |

**Como se activan las alternativas:**

```powershell
# BigQuery Sandbox — Ve a: https://console.cloud.google.com/bigquery
#                    Crea un proyecto, el Sandbox se activa automaticamente

# MongoDB Atlas M0 — Ve a: https://www.mongodb.com/cloud/atlas
#                      Registrate, crea cluster M0 (gratis, sin tarjeta)

# GitHub Actions — Solo necesitas repo, se activa solo
# Ve a tu repo > pestaña Actions > listo

# Google Colab — Solo necesitas Gmail, se activa solo
# Ve a: https://colab.research.google.com > "New notebook" > listo

# GitHub Secrets — Configura en tu repo
# Ve a: Settings > Secrets and variables > Actions > New secret
```

### 0.4. Configurar Autenticacion Google Sheets + Colab

```powershell
# NO necesitas service account ni claves JSON
# La autenticacion se hace via navegador con tu cuenta Gmail

# 1. Abre Google Colab
Start-Process "https://colab.research.google.com"

# 2. Al ejecutar la primera celda de autenticacion, te pedira:
#    - "Authorize access" > clic
#    - Selecciona tu cuenta Gmail
#    - "Allow" permisos para Google Sheets
#    - Copia el codigo de autorizacion y pegalo

# 3. ¡Listo! No necesitas generar claves ni configurar IAM
```

### 0.5. Configurar MongoDB Atlas

1. Ir a https://www.mongodb.com/cloud/atlas
2. Registrarse con email (no requiere tarjeta)
3. Crear cluster **M0 FREE** (512 MB)
4. Crear usuario de base de datos
5. Network Access: `0.0.0.0/0` (permitir acceso desde cualquier IP)
6. Obtener connection string:

```
mongodb+srv://<usuario>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
```

### 0.6. Configurar SendGrid (para alertas por email)

1. Ir a https://signup.sendgrid.com/
2. Registrarse con email (no requiere tarjeta)
3. Plan **Free** (100 emails/dia gratis)
4. Generar API Key en Settings > API Keys
5. Verificar remitente: Settings > Sender Authentication > Verify a Single Sender

### 0.7. Configurar variables de entorno

```powershell
# En el directorio del proyecto
cd "C:\Users\BernabeA.LAPTOP-KB1N2IHM\BERNA\UCV\VII CICLO\BUSINESS INTELLIGENCE AND BIG DATA\enla-2026-callao"

# Copiar template
Copy-Item config\.env.example config\.env

# Editar config\.env con tu editor:
# MONGODB_URI=mongodb+srv://user:pass@cluster0.xxxxx.mongodb.net/
# BQ_PROJECT=enla-2026-callao
# SENDGRID_API_KEY=SG.xxxxxxxxxxxxx
# EMAIL_FROM=tu-email@domain.com
# EMAIL_TO=destinatario@domain.com
```

---

## FASE 1: Subida a GitHub

### 1.1. Inicializar repositorio

```powershell
cd "C:\Users\BernabeA.LAPTOP-KB1N2IHM\BERNA\UCV\VII CICLO\BUSINESS INTELLIGENCE AND BIG DATA\enla-2026-callao"

# Inicializar git
git init

# Verificar que .gitignore funciona (no debe mostrar datos ni credenciales)
git status
```

### 1.2. Crear repositorio en GitHub

```powershell
# Via web: ir a https://github.com/new
# Nombre: enla-2026-callao
# Descripcion: "ML Pipeline para prediccion ENLA 2026 - Region Callao"
# Private (recomendado, contiene datos educacionales)
# NO inicializar con README, .gitignore o license (ya los tenemos)
```

### 1.3. Conectar y subir

```powershell
# Agregar remote
git remote add origin https://github.com/TU_USUARIO/enla-2026-callao.git

# Agregar todos los archivos
git add .

# Commit inicial
git commit -m "feat: ENLA 2026 Callao ML pipeline - complete 6-sprint implementation

- Sprint 1: Data ingestion (Excel -> MongoDB)
- Sprint 2: ETL (MongoDB -> BigQuery Sandbox)
- Sprint 3: Feature engineering (trend, variance, normalization)
- Sprint 4: ML model training (scikit-learn en Colab, 4 area models)
- Sprint 5: Alerting (SendGrid email)
- Sprint 6: Documentation and automation

Stack: Python, MongoDB Atlas M0, BigQuery Sandbox, Looker Studio, GitHub Actions
Tests: 160+ unit tests across all modules"

# Subir a GitHub
git branch -M main
git push -u origin main
```

### 1.4. Verificar en GitHub

```powershell
# Verificar estructura
gh repo view TU_USUARIO/enla-2026-callao

# El .gitignore debe haber excluido:
# - data/raw/*.xlsx
# - config/.env
# - credentials.json
# - *.log
```

---

## FASE 2: Configurar BigQuery Sandbox (Sin Tarjeta de Credito)

> **BigQuery Sandbox es 100% GRATIS y NO requiere tarjeta de credito.**
> Solo necesitas una cuenta de Google (Gmail) y un proyecto en GCP.

### 2.1. ¿Que es BigQuery Sandbox?

BigQuery Sandbox te permite usar BigQuery sin cuenta de facturacion:
- **10 GB** de almacenamiento gratis
- **1 TB** de consultas por mes gratis
- **NO requiere tarjeta de credito**
- **NO requiere billing account**

**Limitaciones importantes:**
- ❌ NO tiene BigQuery ML (usaremos scikit-learn en Colab)
- ❌ NO permite DML (INSERT/UPDATE/DELETE) — usaremos `load_table_from_dataframe`
- ❌ Las tablas expiran despues de 60 dias (puedes extenderlas)
- ✅ SI permite: crear datasets, cargar datos (batch), consultas SQL, conectar Looker Studio

### 2.2. Paso a Paso: Activar BigQuery Sandbox

**Paso 1: Ir directamente a BigQuery**
1. Abre tu navegador y ve a: https://console.cloud.google.com/bigquery
   - **IMPORTANTE**: Usa esta URL directa, NO vayas al console general
2. Si no tienes un proyecto, crea uno:
   - Clic en el selector de proyectos (arriba a la izquierda)
   - Clic en **NUEVO PROYECTO**
   - Nombre: `enla-2026-callao`
   - Clic en **CREAR**

**Paso 2: Verificar que Sandbox esta activo**
- Una vez en la interfaz de BigQuery, busca el texto **"Sandbox mode"** o **"Modo Sandbox"** cerca del nombre del proyecto
- Si lo ves, ¡felicidades! Sandbox esta activo sin billing

**Paso 3: Crear el dataset `BI_ENLA`**
1. En el panel izquierdo, clic en tu proyecto (`enla-2026-callao`)
2. Clic en los 3 puntos `⋮` → **Crear dataset**
3. Configuracion:
   - **ID del dataset**: `BI_ENLA`
   - **Ubicacion**: `US` (o `southamerica-east1` para menor latencia en Peru)
   - **Tiempo de expiracion de la tabla**: 60 dias (puedes cambiarlo despues)
4. Clic en **CREAR DATASET**

**Paso 4: Verificar que funciona**
1. En el editor de SQL, ejecuta esta consulta:
   ```sql
   SELECT "BigQuery Sandbox funciona correctamente" AS mensaje
   ```
2. Deberias ver el resultado en la parte inferior

### 2.3. Verificar Configuracion

- [x] Proyecto creado en GCP (ej. `enla-2026-callao`)
- [x] Sandbox activo (ves el texto "Sandbox" en la consola)
- [x] Dataset `BI_ENLA` creado
- [x] Consulta de prueba ejecutada exitosamente
- [x] Guarda tu **PROJECT_ID** (lo necesitaras para el notebook)

---

## FASE 3: MongoDB Atlas + Google Colab Setup

### 3.1. Configurar MongoDB Atlas (ya deberias tenerlo de FASE 0.5)

Si no lo has hecho:
1. Ir a https://www.mongodb.com/cloud/atlas
2. Registrarse (no requiere tarjeta)
3. Crear cluster **M0 FREE** (512 MB)
4. Crear usuario de base de datos
5. Network Access: `0.0.0.0/0`
6. Obtener connection string

### 3.2. Configurar Google Colab

1. Ir a https://colab.research.google.com
2. Iniciar sesion con tu cuenta Google
3. Crear nuevo notebook: **Nuevo cuaderno**
4. Renombrar: `enla_2026_pipeline_bq.ipynb`

**Autenticacion en Colab (sin service account key):**

En la primera celda del notebook, usa:
```python
from google.colab import auth
auth.authenticate_user()
```

Esto abrira un popup para autorizar tu cuenta Google. No necesitas descargar claves JSON.

### 3.3. Verificar Configuracion

- [x] MongoDB Atlas M0 cluster creado
- [x] Connection string guardado
- [x] Google Colab accesible
- [x] Cuenta Google autenticada

---

## FASE 4: Importar Excel a MongoDB

### 4.1. Desde el notebook de Colab

```python
# Celda 1: Instalar dependencias
!pip install pandas pymongo openpyxl -q

# Celda 2: Subir el archivo Excel
from google.colab import files
uploaded = files.upload()  # Sube BD_2SENLAmuestral2023.xlsx
nombre_archivo = list(uploaded.keys())[0]
# Celda 3: Leer Excel y filtrar por CALLAO
import pandas as pd
from pymongo import MongoClient
import re

# Leer Excel

df = pd.read_excel(nombre_archivo)
anio = int(re.search(r'\d{4}', nombre_archivo).group())
df['ano_evaluacion'] = anio
# Filtrar: CALLAO, anos 2021-2023
df_filtered = df[
    (df['nom_dre'] == 'Callao') 
]

print(f"Registros filtrados: {len(df_filtered)}")

# Celda 4: Conectar a MongoDB Atlas
MONGODB_URI = "mongodb+srv://*****CREDENTIALS_REMOVED*****@cluster01.ik7af2k.mongodb.net/?appName=Cluster01"

client = MongoClient(MONGODB_URI)
db = client['enla_db']
collection = db['enla_callao_raw']

# Limpiar coleccion anterior (opcional)
collection.delete_many({})

# Insertar datos
records = df_filtered.to_dict('records')
result = collection.insert_many(records)

print(f"Documentos insertados: {len(result.inserted_ids)}")

```

### 4.2. Verificar en MongoDB

```python
# Verificar conteo
count = collection.count_documents({})
print(f"Total documentos en MongoDB: {count}")

# Ver un documento
sample = collection.find_one()
print(sample)
```

**Checkpoints:**
- [x] Archivo Excel subido a Colab
- [x] Filtrado por CALLAO, 2do Secundaria, anos 2021-2023
- [x] Datos insertados en MongoDB Atlas
- [x] Conteo verificado (> 0 documentos)

---

## FASE 5: ETL - MongoDB -> BigQuery (via Colab Batch Load)

### 5.1. Leer de MongoDB y transformar a formato largo

```python
# Celda: ETL Transformation
import pandas as pd
from pymongo import MongoClient
from google.cloud import bigquery
from google.colab import auth

# Autenticar Google Cloud
auth.authenticate_user()
client_bq = bigquery.Client()

# Conectar a MongoDB
MONGODB_URI = "mongodb+srv://*****CREDENTIALS_REMOVED*****@cluster01.ik7af2k.mongodb.net/?appName=Cluster01"
client_mongo = MongoClient(MONGODB_URI)
db = client_mongo['enla_db']
collection = db['enla_callao_raw']

# Leer datos de MongoDB
data = list(collection.find())
df = pd.DataFrame(data)

print(f"Datos leidos de MongoDB: {len(df)}")
column_map = {
    'comunicacion': 'M500_EM_2S_2023_CT',
    'matematica': 'M500_EM_2S_2023_MA',
    'ccss': 'M500_EM_2S_2023_CS'
}
# Transformar a formato largo (fact table)
fact_rows = []

for _, row in df.iterrows():
    for area, col in column_map.items():
        if col in df.columns and pd.notna(row[col]):
            fact_rows.append({
                'id_ie': row.get('ID_IE'),
                'nom_ie': row.get('nom_ie'),
                'year': 2023,  
                'area': area,
                'score': float(row[col]),
                'area_display': area.capitalize()
            })

fact_df = pd.DataFrame(fact_rows)

print(f"Fact table creada: {len(fact_df)} filas")
print(fact_df.head())
fact_df = pd.DataFrame(fact_rows)
print(f"Fact table creada: {len(fact_df)} filas")
print(fact_df.head())
```

### 5.2. Cargar a BigQuery Sandbox (batch load, no DML)

```python
# Celda: Load to BigQuery
BQ_PROJECT = "enla-2026-callao"  # Tu PROJECT_ID
BQ_DATASET = "BI_ENLA"

# Configurar cliente de BigQuery
client_bq = bigquery.Client(project=BQ_PROJECT)

# Cargar fact_enla usando load_table_from_dataframe (batch load)
table_id = f"{BQ_PROJECT}.{BQ_DATASET}.fact_enla"
# Convertir tipos correctamente
fact_df['id_ie'] = fact_df['id_ie'].astype(str)
fact_df['nom_ie'] = fact_df['nom_ie'].astype(str)
fact_df['area'] = fact_df['area'].astype(str)
fact_df['area_display'] = fact_df['area_display'].astype(str)
fact_df['year'] = fact_df['year'].astype(int)
fact_df['score'] = fact_df['score'].astype(float)

job = client_bq.load_table_from_dataframe(
    fact_df,
    table_id,
    job_config=bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",  # Sobrescribe si existe
        schema=[
            bigquery.SchemaField("id_ie", "STRING"),
            bigquery.SchemaField("nom_ie", "STRING"),
            bigquery.SchemaField("year", "INTEGER"),
            bigquery.SchemaField("area", "STRING"),
            bigquery.SchemaField("score", "FLOAT"),
            bigquery.SchemaField("area_display", "STRING"),
        ]
    )
)

job.result()  # Esperar a que termine

# Verificar
table = client_bq.get_table(table_id)
print(f"Tabla fact_enla cargada: {table.num_rows} filas")
```

### 5.3. Verificar en BigQuery

```python
# Consultar BigQuery para verificar
query = f"""
SELECT area, year, COUNT(*) as count, AVG(score) as avg_score
FROM `{BQ_PROJECT}.{BQ_DATASET}.fact_enla`
GROUP BY area, year
ORDER BY area, year
"""

results = client_bq.query(query).result()
for row in results:
    print(dict(row))
```

**Checkpoints:**
- [x] Datos leidos de MongoDB
- [x] Transformacion a formato largo exitosa
- [x] Tabla `fact_enla` cargada en BigQuery
- [x] Verificacion con query SQL exitosa

---

## FASE 6: Feature Engineering (en Colab, resultados a BigQuery)

### 6.1. Calcular features

```python
# Celda: Feature Engineering
import pandas as pd
from google.cloud import bigquery

BQ_PROJECT = "enla-2026-callao"
BQ_DATASET = "BI_ENLA"

client_bq = bigquery.Client(project=BQ_PROJECT)

query = f"""
SELECT *
FROM `{BQ_PROJECT}.{BQ_DATASET}.fact_enla`
ORDER BY id_ie, area, year
"""

df = client_bq.query(query).to_dataframe()

# Pivot
pivot = df.pivot_table(
    index=['id_ie', 'nom_ie', 'area'],
    columns='year',
    values='score',
    aggfunc='first'
).reset_index()

# Limpiar nombre de columnas
pivot.columns.name = None

# Renombrar SOLO si existen
rename_dict = {}
if 2021 in pivot.columns:
    rename_dict[2021] = 'avg_score_2021'
if 2022 in pivot.columns:
    rename_dict[2022] = 'avg_score_2022'
if 2023 in pivot.columns:
    rename_dict[2023] = 'avg_score_2023'

pivot = pivot.rename(columns=rename_dict)

# Crear columnas faltantes (clave para evitar errores)
for col in ['avg_score_2021', 'avg_score_2022', 'avg_score_2023']:
    if col not in pivot.columns:
        pivot[col] = None

# Features
features_df = pivot.copy()

features_df['trend'] = (
    features_df['avg_score_2023'].fillna(0) -
    features_df['avg_score_2021'].fillna(0)
)

features_df['variance'] = features_df[
    ['avg_score_2021', 'avg_score_2022', 'avg_score_2023']
].fillna(0).var(axis=1)

features_df['target'] = (
    features_df['avg_score_2023'].fillna(0) >= 12.5
).astype(int)

print(f"Features calculadas: {len(features_df)} filas")
print(features_df.head())
```

### 6.2. Cargar features a BigQuery

```python
# Celda: Load features to BigQuery
table_id = f"{BQ_PROJECT}.{BQ_DATASET}.features"

job = client_bq.load_table_from_dataframe(
    features_df,
    table_id,
    job_config=bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE"
    )
)

job.result()

# Verificar
table = client_bq.get_table(table_id)
print(f"Tabla features cargada: {table.num_rows} filas")
```

**Checkpoints:**
- [x] Features calculadas (trend, variance, target)
- [x] Tabla `features` cargada en BigQuery
- [x] Verificacion exitosa

---

## FASE 7: ML Training (scikit-learn en Colab, metrics a BigQuery)

### 7.1. Entrenar modelos con scikit-learn

```python
# Celda: Install ML libraries
!pip install scikit-learn -q

# Celda: Train ML Models
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from google.cloud import bigquery

BQ_PROJECT = "enla-2026-callao"
BQ_DATASET = "BI_ENLA"

client_bq = bigquery.Client(project=BQ_PROJECT)

# Leer features de BigQuery
query = f"""
SELECT *
FROM `{BQ_PROJECT}.{BQ_DATASET}.features`
"""
features_df = client_bq.query(query).to_dataframe()

# 🔧 LIMPIEZA CLAVE
features_df = features_df.fillna(0)

# 🔧 TARGET DINÁMICO (evita una sola clase)
threshold = features_df['avg_score_2023'].mean()
features_df['target'] = (features_df['avg_score_2023'] >= threshold).astype(int)

# Entrenar un modelo por área
areas = features_df['area'].unique()
model_metrics = []

for area in areas:
    print(f"\nEntrenando modelo para: {area}")

    area_data = features_df[features_df['area'] == area]

    # 🔧 Features válidas (en tu caso)
    X = area_data[['avg_score_2023']].fillna(0)
    y = area_data['target']

    # 🔍 Verificar clases
    print("Distribución target:")
    print(y.value_counts())

    if len(y.unique()) < 2:
        print(f"⚠️ Área {area} omitida (solo una clase)")
        continue

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42
    )

    # Modelo
    model = LogisticRegression(max_iter=1000)
    model.fit(X_train, y_train)

    # Predicción
    y_pred = model.predict(X_test)

    # Métricas
    metrics = {
        'area': area,
        'model_name': f'LogisticRegression_{area}',
        'accuracy': accuracy_score(y_test, y_pred),
        'precision': precision_score(y_test, y_pred, zero_division=0),
        'recall': recall_score(y_test, y_pred, zero_division=0),
        'f1_score': f1_score(y_test, y_pred, zero_division=0),
        'training_date': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    model_metrics.append(metrics)

    print(f"  Accuracy: {metrics['accuracy']:.3f}")
    print(f"  Precision: {metrics['precision']:.3f}")
    print(f"  Recall: {metrics['recall']:.3f}")
    print(f"  F1-Score: {metrics['f1_score']:.3f}")

# Resultados finales
metrics_df = pd.DataFrame(model_metrics)

print("\n📊 Métricas de todos los modelos:")
print(metrics_df)
```

### 7.2. Guardar metricas en BigQuery

```python
# Celda: Save metrics to BigQuery
table_id = f"{BQ_PROJECT}.{BQ_DATASET}.model_metrics"

job = client_bq.load_table_from_dataframe(
    metrics_df,
    table_id,
    job_config=bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE"
    )
)

job.result()

print("Metricas guardadas en BigQuery")
```

**Checkpoints:**
- [x] 4 modelos entrenados (uno por area)
- [x] Accuracy >= 70% (idealmente >= 75%)
- [x] Metricas guardadas en tabla `model_metrics`
- [x] Verificacion exitosa

---

## FASE 8: Generar Predicciones (Colab -> BigQuery)

### 8.1. Generar predicciones para 2026

```python
# Celda: Generate Predictions
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from google.cloud import bigquery

BQ_PROJECT = "enla-2026-callao"
BQ_DATASET = "BI_ENLA"

client_bq = bigquery.Client(project=BQ_PROJECT)

# Leer features
query = f"""
SELECT *
FROM `{BQ_PROJECT}.{BQ_DATASET}.features`
"""
features_df = client_bq.query(query).to_dataframe()

# 🔧 Limpieza clave
features_df = features_df.fillna(0)

# 🔧 Target dinámico (evita una sola clase)
threshold = features_df['avg_score_2023'].mean()
features_df['target'] = (features_df['avg_score_2023'] >= threshold).astype(int)

predictions = []

for area in features_df['area'].unique():
    print(f"\nGenerando predicciones para: {area}")

    area_data = features_df[features_df['area'] == area].reset_index(drop=True)

    # 🔧 Usar solo variables válidas
    X = area_data[['avg_score_2023']].fillna(0)
    y = area_data['target']

    # 🔍 Validar clases
    if len(y.unique()) < 2:
        print(f"⚠️ Área {area} omitida (solo una clase)")
        continue

    # Modelo
    model = LogisticRegression(max_iter=1000)
    model.fit(X, y)

    # Predicciones
    probas = model.predict_proba(X)
    predicted_success = model.predict(X)
    confidence = np.max(probas, axis=1)

    # Construcción de resultados (sin error de índice)
    for i in range(len(area_data)):
        row = area_data.iloc[i]

        if confidence[i] > 0.75:
            risk_level = 'BAJO'
        elif confidence[i] > 0.55:
            risk_level = 'MEDIO'
        else:
            risk_level = 'ALTO'

        predictions.append({
            'prediction_id': f"PRED_{row['area']}_{row['id_ie']}_2026",
            'institution_id': row['id_ie'],
            'nom_ie': row['nom_ie'],
            'area': row['area'],
            'predicted_success': int(predicted_success[i]),
            'confidence': float(confidence[i]),
            'risk_level': risk_level,
            'model_version': f'LogisticRegression_{area}_v1'
        })

# DataFrame final
predictions_df = pd.DataFrame(predictions)

print(f"\nTotal predicciones: {len(predictions_df)}")
print("\nDistribución de riesgo:")
print(predictions_df['risk_level'].value_counts())
```

### 8.2. Cargar predicciones a BigQuery

```python
# Celda: Load predictions to BigQuery
table_id = f"{BQ_PROJECT}.{BQ_DATASET}.predictions"

job = client_bq.load_table_from_dataframe(
    predictions_df,
    table_id,
    job_config=bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE"
    )
)

job.result()

print("Predicciones guardadas en BigQuery")

# Verificar distribucion de riesgo
query = f"""
SELECT risk_level, COUNT(*) as count
FROM `{BQ_PROJECT}.{BQ_DATASET}.predictions`
GROUP BY risk_level
ORDER BY risk_level
"""
results = client_bq.query(query).result()
for row in results:
    print(dict(row))
```

**Checkpoints:**
- [x] Predicciones generadas para las 4 areas
- [x] Niveles de riesgo: ALTO, MEDIO, BAJO
- [x] Tabla `predictions` cargada en BigQuery
- [x] Instituciones de alto riesgo identificadas

---

## FASE 9: Alertas por Email (SendGrid en Colab)

### 9.1. Configurar SendGrid

```python
# Celda: SendGrid Setup
!pip install sendgrid -q

import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import *

# Configurar API Key (usar GitHub Secrets en produccion)
SENDGRID_API_KEY = "SG.xxxxxxxxxxxxx"  # Tu API Key de SendGrid
EMAIL_FROM = "tu-email@domain.com"
EMAIL_TO = ["destinatario@domain.com"]

# Verificar que SendGrid funciona
print("SendGrid configurado")
```

### 9.2. Enviar alertas para instituciones de alto riesgo

```python
# Celda: Send Alerts
from google.cloud import bigquery
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import *

client_bq = bigquery.Client()

# Obtener instituciones de alto riesgo
query = f"""
SELECT nom_ie, area, confidence
FROM `{BQ_PROJECT}.{BQ_DATASET}.predictions`
WHERE risk_level = 'ALTO'
ORDER BY confidence ASC
"""
high_risk = client_bq.query(query).to_dataframe()

print(f"Instituciones en riesgo ALTO: {len(high_risk)}")

if len(high_risk) > 0:
    # Crear reporte HTML
    html_content = """
    <h2>Alerta: Instituciones en Riesgo ALTO - ENLA 2026 Callao</h2>
    <p>Se han identificado {} instituciones con riesgo ALTO de fracaso:</p>
    <table border="1" cellpadding="5">
        <tr><th>Institucion</th><th>Area</th><th>Confianza</th></tr>
    """.format(len(high_risk))

    for _, row in high_risk.iterrows():
        html_content += f"""
        <tr>
            <td>{row['nom_ie']}</td>
            <td>{row['area']}</td>
            <td>{row['confidence']:.2%}</td>
        </tr>
        """

    html_content += """
    </table>
    <p><strong>Recomendacion:</strong> Implementar intervenciones pedagogicas inmediatas.</p>
    """

    # Enviar email
    sg = SendGridAPIClient(SENDGRID_API_KEY)

    mail = Mail(
        from_email=EMAIL_FROM,
        to_emails=EMAIL_TO,
        subject="ALERTA: Instituciones en Riesgo ALTO - ENLA 2026 Callao",
        html_content=Content("text/html", html_content)
    )

    response = sg.send(mail)
    print(f"Email enviado: status {response.status_code}")
else:
    print("No hay instituciones en riesgo ALTO para alertar")
```

**Checkpoints:**
- [x] SendGrid configurado
- [x] Instituciones de alto riesgo identificadas
- [x] Email de alerta enviado exitosamente

---

## FASE 10: Dashboards en Looker Studio (Conecta a BigQuery Sandbox)

### 10.1. Conectar BigQuery a Looker Studio

1. Abrir https://lookerstudio.google.com/
2. Click en **Crear > Informe**
3. Seleccionar **BigQuery** como fuente de datos
4. Navegar: `TU_PROJECT_ID > BI_ENLA > predictions`
5. Click en **Conectar**

### 10.2. Dashboard de Resumen Ejecutivo

**Layout recomendado:**

| Fila | Elemento | Configuracion |
|------|----------|---------------|
| 1 | Titulo | "Resumen Ejecutivo ENLA 2026 - Callao" |
| 2 | KPI cards (4 columnas) | Comunicacion, Matematica, CCSS, CyT (total instituciones) |
| 3 | Tabla de riesgo por area | Dimension: `area`, Metricas: count por `risk_level` |
| 4 | Comparativa de score | Bar chart: area vs avg score (desde tabla `features`) |
| 5 | Heatmap de riesgo | Table heatmap: area × risk_level con colores |
| 6 | Instituciones en riesgo | Tabla filtrada: risk_level = 'ALTO' |

### 10.3. Dashboard por Area

Repetir para cada area (comunicacion, matematica, ccss, cyt):
1. Crear nuevo informe
2. Conectar a `predictions` con filtro por area
3. Agregar:
   - KPI: Total instituciones
   - KPI: % Riesgo ALTO
   - Grafico: Distribucion de riesgo
   - Tabla: Instituciones con detalles

### 10.4. Configurar acceso compartido

1. Click en **Compartir** (esquina superior derecha)
2. Agregar emails de DRE Callao
3. Permiso: **Puede ver** (solo lectura)

**Checkpoints:**
- [ ] 5 dashboards creados (1 resumen + 4 por area)
- [ ] Conexion a BigQuery Sandbox exitosa
- [ ] Visualizacion de datos correcta
- [ ] Compartido con stakeholders

---

## FASE 11: Automatizacion con GitHub Actions

> **NOTA**: Cloud Functions requiere billing y ha sido **DESHABILITADO** (renombrado a `.DISABLED`).
> GitHub Actions maneja todo el pipeline automáticamente sin costo.

### 11.1. Workflows Configurados (Sin Billing)

El proyecto ya tiene estos workflows configurados:

| Workflow | Propósito | Activación |
|----------|------------|-------------|
| `run-notebook.yml` | Ejecuta pipeline ETL completo | Manual + Diario 03:00 UTC |
| `pipeline-trigger.yml` | Orquestación completa (ETL+ML+Alerts) | Manual + Diario 03:00 UTC |
| `dbt.yml` | Ejecuta modelos dbt en BigQuery | Al hacer push a `dbt/**` |

**Cloud Functions deshabilitado**: `deploy-cloud-function.yml.DISABLED`

```yaml
name: Run ENLA 2026 Pipeline

on:
  schedule:
    - cron: '0 3 * * *'  # Diario a las 03:00 UTC (10pm Peru)
  workflow_dispatch:  # Permite ejecucion manual

jobs:
  run-pipeline:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'

    - name: Install dependencies
      run: |
        pip install pandas pymongo scikit-learn google-cloud-bigquery sendgrid

    - name: Run pipeline script
      env:
        MONGODB_URI: ${{ secrets.MONGODB_URI }}
        BQ_PROJECT: ${{ secrets.BQ_PROJECT }}
        SENDGRID_API_KEY: ${{ secrets.SENDGRID_API_KEY }}
        EMAIL_FROM: ${{ secrets.EMAIL_FROM }}
        EMAIL_TO: ${{ secrets.EMAIL_TO }}
      run: |
        python scripts/run_pipeline.py

    - name: Commit and push if changed
      uses: stefanzweifel/git-auto-commit-action@v4
      with:
        commit_message: "Auto-update predictions"
```

### 11.2. Configurar GitHub Secrets

En tu repositorio de GitHub:
1. Ir a **Settings > Secrets and variables > Actions**
2. Agregar estos secrets:
   - `MONGODB_URI`: tu connection string de MongoDB
   - `BQ_PROJECT`: tu PROJECT_ID de GCP
   - `SENDGRID_API_KEY`: tu API key de SendGrid
   - `EMAIL_FROM`: tu email remitente
   - `EMAIL_TO`: email(s) destinatario(s)

**Checkpoints:**
- [ ] Workflow creado en `.github/workflows/`
- [ ] Secrets configurados en GitHub
- [ ] Ejecucion manual probada (workflow_dispatch)
- [ ] Pipeline ejecutandose automaticamente

---

## Referencia Rapida de Comandos

```powershell
# ============ BIGQUERY SANDBOX ============
# Abrir BigQuery Console
Start-Process "https://console.cloud.google.com/bigquery"

# Verificar datasets (via gcloud si tienes instalado)
# gcloud config set project TU_PROJECT_ID
# bq ls TU_PROJECT_ID:

# ============ MONGODB ATLAS ============
# Abrir MongoDB Atlas
Start-Process "https://cloud.mongodb.com"

# Verificar conexion (desde local, requiere pymongo)
# python -c "from pymongo import MongoClient; client = MongoClient('mongodb+srv://...'); print(client.admin.command('ping'))"

# ============ GOOGLE COLAB ============
# Abrir Google Colab
Start-Process "https://colab.research.google.com"

# Ejecutar notebook
# 1. Abre notebooks/enla_2026_pipeline_bq.ipynb en Colab
# 2. Clic en "Runtime" > "Run all"
# 3. Espera ~5-10 minutos

# ============ LOOKER STUDIO ============
# Abrir Looker Studio
Start-Process "https://lookerstudio.google.com"

# ============ GITHUB ============
# Verificar estado
git status
git add .
git commit -m "feat: update deployment guide for BigQuery Sandbox"
git push origin main

# Ver Actions (CI/CD)
Start-Process "https://github.com/TU_USUARIO/enla-2026-callao/actions"

# ============ SENDGRID ============
# Abrir SendGrid
Start-Process "https://app.sendgrid.com"
```

---

## Solucion de Problemas

### Error: "Sandbox mode - DML operations not allowed"
```python
# BigQuery Sandbox NO permite INSERT/UPDATE/DELETE
# Solucion: Usar load_table_from_dataframe con WRITE_TRUNCATE
job = client.load_table_from_dataframe(
    df,
    table_id,
    job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
)
```

### Error: "Not authenticated" en Colab
```python
# Re-ejecutar autenticacion
from google.colab import auth
auth.authenticate_user()
```

### Error: "MongoDB connection timeout"
```python
# Verificar que:
# 1. Network Access en Atlas tiene 0.0.0.0/0
# 2. Usuario tiene permisos correctos
# 3. Connection string es correcto (sin errores de tipografia)
```

### Error: "Table expired" en BigQuery
```python
# Las tablas en Sandbox expiran en 60 dias
# Solucion: Volver a cargar los datos o extender la expiracion
# En BigQuery Console: clic en la tabla > Details > Edit > Expiration time
```

---

**Documentacion actualizada para arquitectura BigQuery Sandbox + MongoDB Atlas.**
**NO se requiere tarjeta de credito en ninguna parte del pipeline.**

Para dudas, consultar:
- `docs/GUIA_DESPLEGUE.md` — Esta guia completa
- `notebooks/enla_2026_pipeline_bq.ipynb` — Notebook de Colab listo para usar
- `https://cloud.google.com/bigquery/docs/sandbox` — Documentacion oficial de BigQuery Sandbox
