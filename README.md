# ENLA 2026 Callao 🚢

[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-pytest-green.svg)](https://pytest.org/)
[![MongoDB Atlas](https://img.shields.io/badge/MongoDB%20Atlas-M0%20Free-success.svg)](https://www.mongodb.com/cloud/atlas)
[![Google Cloud](https://img.shields.io/badge/Google%20Cloud-Platform-yellow.svg)](https://cloud.google.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## 📋 Descripción

**ENLA 2026 Callao** es una plataforma de Machine Learning diseñada para predecir el éxito académico de instituciones educativas en la región del Callao, Perú. El sistema procesa datos históricos de evaluaciones académicas y genera predicciones para el año 2026 en cuatro áreas fundamentales: **Comunicación, Matemática, Ciencias Sociales (CCSS) y Ciencia y Tecnología (CyT)**.

El proyecto implementa un pipeline completo de datos que abarca desde la ingestión de archivos Excel hasta la visualización de resultados en dashboards interactivos. Utiliza exclusivamente **servicios gratuitos sin necesidad de tarjeta de crédito**, aprovechando Google Sheets, Google Colab, MongoDB Atlas (capa M0), SendGrid y Looker Studio.

La arquitectura está diseñada para ser escalable y mantenible, utilizando las mejores prácticas de ingeniería de datos: procesamiento ETL, ingeniería de features, entrenamiento de modelos predictivos, sistema de alertas automáticas y visualización ejecutiva mediante 5 dashboards especializados.

## ✨ Características Principales

- **📊 Predicción Académica**: Modelos de Machine Learning (Logistic Regression) para 4 áreas académicas
- **🔄 Pipeline ETL Completo**: Ingestión → Transformación → Features → Modelos → Predicción
- **☁️ Arquitectura Cloud-Native**: Integración con Google Cloud Platform (BigQuery, Cloud Functions)
- **📧 Sistema de Alertas**: Notificaciones automáticas por email via SendGrid para casos de riesgo ALTO
- **📈 5 Dashboards Looker Studio**: Visualización ejecutiva por área y resumen general
- **🗄️ Múltiples Almacenamientos**: MongoDB Atlas (staging) y BigQuery (Data Warehouse)
- **🧪 Testing Robusto**: Más de 100 tests unitarios e integración con pytest
- **🚀 CI/CD Automatizado**: GitHub Actions para despliegue continuo
- **📓 Notebooks Colab**: Ejecución del pipeline completo sin configuración local
- **🏗️ Infraestructura como Código**: Terraform para gestión de recursos cloud
- **🔧 Transformaciones dbt**: Modelos dbt para BigQuery con vistas materializadas

## 🏗️ Arquitectura

### Estructura del Proyecto

```
enla-2026-callao/
├── src/                          # Código fuente principal
│   ├── ingestion/                # Ingesta de datos (Excel → MongoDB)
│   │   ├── ingest_enla.py        # Script principal de ingesta
│   │   ├── validators.py         # Reglas de validación de datos
│   │   └── config.py             # Configuración de ingesta
│   ├── etl/                      # Transformación ETL (MongoDB → BigQuery)
│   │   ├── bigquery_client.py    # Cliente de BigQuery
│   │   ├── transform.py          # Lógica de transformación
│   │   └── schemas.py           # Esquemas de tablas BigQuery
│   ├── features/                 # Ingeniería de features
│   │   ├── engineer.py           # Cálculo de features (promedios, tendencias)
│   │   └── schemas.py           # Esquemas de features
│   ├── models/                   # Modelos predictivos ML
│   │   ├── trainer.py            # Entrenamiento de modelos
│   │   ├── predictor.py          # Generación de predicciones
│   │   └── schemas.py           # Esquemas de modelos
│   ├── database/                 # Clientes de bases de datos
│   │   ├── mongo_client.py       # Conexión a MongoDB Atlas
│   │   └── bigquery_client.py    # Conexión a BigQuery
│   ├── alerting/                 # Sistema de alertas
│   │   ├── email_alert.py        # Alertas por email (SendGrid)
│   │   └── schemas.py           # Esquemas de alertas
│   └── logging/                  # Configuración de logs
│       └── setup.py              # Configuración de structlog
├── notebooks/                    # Jupyter Notebooks
│   ├── enla_2026_pipeline.ipynb              # Pipeline completo en Google Colab
│   └── enla_2026_pipeline_bq.ipynb          # Pipeline con BigQuery
├── gcp/                          # Google Cloud Functions
│   ├── bigquery/                 # Funciones para BigQuery
│   └── functions/                # Cloud Functions deployables
├── dbt/                          # Transformaciones dbt
│   └── models/                   # Modelos dbt para BigQuery
├── docs/                         # Documentación
│   ├── ARCHITECTURE.md           # Documento de arquitectura completa
│   ├── DASHBOARD_SPEC.md         # Especificación de dashboards Looker
│   ├── GUIA_DESPLEGUE.md         # Guía de despliegue completa
│   ├── GUIA_DESPLEGUE_CLOUD.md   # Guía de despliegue cloud
│   ├── GUIA_OPCION_C_SIN_TARJETA.md  # Alternativas sin tarjeta
│   └── RUNBOOK.md                # Runbook operativo
├── tests/                        # Tests unitarios e integración
│   ├── unit/                     # Tests unitarios
│   └── integration/              # Tests de integración
├── config/                       # Configuración
│   ├── .env.example              # Ejemplo de variables de entorno
│   └── .env                      # Variables de entorno (no versionado)
├── terraform/                    # Infraestructura como código
├── .github/                      # GitHub Actions workflows
├── requirements.txt              # Dependencias Python
└── README.md                     # Este archivo
```

### Flujo de Datos

```
Excel/Google Sheets → Ingesta (src/ingestion) → MongoDB Atlas (staging)
         ↓
ETL (src/etl) → BigQuery (Data Warehouse) → dbt (transformaciones)
         ↓
Features (src/features) → Models (src/models) → Predicciones
         ↓
Alerting (src/alerting) → SendGrid (emails) → Looker Studio (dashboards)
```

## 🚀 Instalación Rápida

### Pre-requisitos

- **Python 3.9+** ([descargar](https://www.python.org/downloads/))
- **Cuenta en MongoDB Atlas** (capa M0 gratuita, [registrarse](https://www.mongodb.com/cloud/atlas/register))
- **Cuenta en Google Cloud Platform** (para BigQuery Sandbox, [crear proyecto](https://console.cloud.google.com/))
- **Cuenta en SendGrid** (plan gratuito 100 emails/día, [registrarse](https://sendgrid.com/free/))
- **Git** ([descargar](https://git-scm.com/downloads))

### Pasos de Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/bvillegasa-bit/Proyecto_ENLA_2026.git
cd enla-2026-callao

# 2. Crear y activar entorno virtual
python -m venv venv

# Windows:
venv\Scripts\activate
# Linux/Mac:
# source venv/bin/activate

# 3. Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt

# 4. Configurar credenciales
cp config\.env.example config\.env
# Editar config\.env con tus credenciales reales

# 5. Ejecutar tests para verificar instalación
pytest tests/ -v

# 6. (Opcional) Configurar pre-commit hooks
# pip install pre-commit
# pre-commit install
```

### Configuración de Variables de Entorno (.env)

Edita el archivo `config/.env` con tus credenciales:

```bash
# MongoDB Atlas
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/

# Google Cloud Platform
GCP_PROJECT_ID=tu-project-id
GCP_CREDENTIALS_PATH=/path/to/service-account-key.json

# Email Alerts (SendGrid)
SENDGRID_API_KEY=SG.xxxxx
ALERT_EMAIL_FROM=tu-email@gmail.com

# Logging
LOG_LEVEL=INFO
```

## 📖 Guía de Uso

### Ejecución del Pipeline Completo (Google Colab - Recomendado)

La forma más sencilla de ejecutar el pipeline es usando el notebook en Google Colab:

1. Abre [Google Colab](https://colab.research.google.com)
2. Sube el archivo `notebooks/enla_2026_pipeline.ipynb`
3. Configura las credenciales en la sección "CONFIGURACIÓN"
4. Ejecuta las celdas secuencialmente

### Ejecución Local (Python)

```bash
# Ingesta de datos (Excel → MongoDB)
python src/ingestion/ingest_enla.py --input data/raw/enla_2023.xlsx

# ETL (MongoDB → BigQuery)
python src/etl/transform.py

# Ingeniería de features
python src/features/engineer.py

# Entrenamiento de modelos
python src/models/trainer.py

# Generar predicciones
python src/models/predictor.py

# Enviar alertas
python src/alerting/email_alert.py
```

### Uso de dbt para Transformaciones

```bash
# Instalar dbt-bigquery
pip install dbt-bigquery

# Configurar perfil de dbt
# Editar ~/.dbt/profiles.yml

# Ejecutar modelos dbt
cd dbt
dbt run

# Generar documentación
dbt docs generate
dbt docs serve
```

## 🧪 Ejecutar Tests

```bash
# Ejecutar todos los tests
pytest tests/ -v

# Ejecutar con cobertura
pytest --cov=src tests/

# Ejecutar tests específicos
pytest tests/unit/test_ingestion.py -v

# Ejecutar tests de integración
pytest tests/integration/ -v
```

## 📚 Documentación

- **[Guía de Despliegue Completa](docs/GUIA_DESPLEGUE.md)** - Instrucciones paso a paso para desplegar todo el sistema
- **[Arquitectura del Sistema](docs/ARCHITECTURE.md)** - Documento técnico de arquitectura
- **[Especificación de Dashboards](docs/DASHBOARD_SPEC.md)** - Detalles de los 5 dashboards Looker Studio
- **[Guía Cloud](docs/GUIA_DESPLEGUE_CLOUD.md)** - Despliegue en Google Cloud Platform
- **[Opción C (Sin Tarjeta)](docs/GUIA_OPCION_C_SIN_TARJETA.md)** - Alternativas gratuitas sin tarjeta de crédito
- **[Runbook Operativo](docs/RUNBOOK.md)** - Procedimientos operativos

## 🤝 Contribución

Las contribuciones son bienvenidas. Por favor sigue estos pasos:

1. Haz fork del repositorio
2. Crea una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. Haz commit de tus cambios (`git commit -m 'Add: nueva funcionalidad'`)
4. Haz push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

### Estándares de Código

- Sigue PEP 8 para código Python
- Escribe tests para nuevas funcionalidades
- Actualiza la documentación según corresponda
- Usa conventional commits para los mensajes de commit

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo [LICENSE](LICENSE) para más detalles.

## 👥 Autores

- **Equipo ENLA 2026 Callao** - *Desarrollo inicial*
- **Bernabe Villegas** - *Investigación y documentación*

## 🙏 Agradecimientos

- A la **DRE Callao** por proporcionar los datos históricos académicos
- A **Google Cloud Platform** por los servicios gratuitos (BigQuery Sandbox, Colab)
- A **MongoDB Atlas** por la capa gratuita M0
- A **SendGrid** por el plan gratuito de emails
- A la comunidad de **Open Source** por las librerías utilizadas

## 📞 Contacto

Para preguntas o soporte, por favor abre un issue en el repositorio o contacta al equipo en:
- Email: enla-alerts@dre-callao.gob.pe
- GitHub Issues: [https://github.com/bvillegasa-bit/Proyecto_ENLA_2026/issues](https://github.com/bvillegasa-bit/Proyecto_ENLA_2026/issues)

---

<p align="center">
  <i>Desarrollado con ❤️ para la educación en el Callao 🇵🇪</i>
</p>
