# ENLA 2026 Callao - Looker Studio Dashboard Specification

> **Dashboard Design Document**
> Last Updated: 2026-05-01

## Table of Contents

1. [Overview](#overview)
2. [Data Sources](#data-sources)
3. [Dashboard Specifications](#dashboard-specifications)
4. [Chart Configurations](#chart-configurations)
5. [Filters and Controls](#filters-and-controls)
6. [Refresh Schedule](#refresh-schedule)
7. [Access Control](#access-control)
8. [Implementation Checklist](#implementation-checklist)

---

## Overview

The ENLA 2026 Callao project includes 5 Looker Studio dashboards for visualizing ML predictions across 4 academic areas.

### Dashboard List

| # | Dashboard Name | Data Source | Target Audience |
|---|----------------|-------------|-----------------|
| 1 | Comunicación Dashboard | `v_callao_comunicacion_2026` | Teachers, Administrators |
| 2 | Matemática Dashboard | `v_callao_matematica_2026` | Teachers, Administrators |
| 3 | CCSS Dashboard | `v_callao_ccss_2026` | Teachers, Administrators |
| 4 | CyT Dashboard | `v_callao_cyt_2026` | Teachers, Administrators |
| 5 | Executive Summary | `v_callao_resumen_todas_areas` | Principals, District Admin |

---

## Data Sources

### BigQuery Views (dbt Models)

All dashboards connect to materialized views in BigQuery:

| View Name | Full Table ID | Refresh Schedule |
|-----------|---------------|------------------|
| Comunicación | `YOUR_PROJECT_ID.BI_ENLA.v_callao_comunicacion_2026` | Daily 03:00 UTC |
| Matemática | `YOUR_PROJECT_ID.BI_ENLA.v_callao_matematica_2026` | Daily 03:00 UTC |
| CCSS | `YOUR_PROJECT_ID.BI_ENLA.v_callao_ccss_2026` | Daily 03:00 UTC |
| CyT | `YOUR_PROJECT_ID.BI_ENLA.v_callao_cyt_2026` | Daily 03:00 UTC |
| Executive Summary | `YOUR_PROJECT_ID.BI_ENLA.v_callao_resumen_todas_areas` | Daily 03:00 UTC |

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `institution_id` | String | Unique institution identifier |
| `nom_ie` | String | Institution name |
| `avg_score_2023` | Float | Average score in 2023 |
| `avg_score_2022` | Float | Average score in 2022 |
| `avg_score_2021` | Float | Average score in 2021 |
| `trend` | Float | Score trend (positive = improving) |
| `variance` | Float | Score variance |
| `predicted_success` | Integer | 1 = success, 0 = at risk |
| `confidence` | Float | Prediction confidence (0-1) |
| `risk_level` | String | ALTO / MEDIO / BAJO |
| `model_version` | String | Model version used |
| `prediction_ts` | Timestamp | When prediction was made |

---

## Dashboard Specifications

### 1. Comunicación Dashboard

**Purpose**: Monitor academic performance and predictions for Comunicación area.

#### Layout (Top to Bottom)

```
┌─────────────────────────────────────────────────────────────┐
│  HEADER: Comunicación - ENLA 2026 Callao Predictions       │
│  Last Updated: [timestamp from prediction_ts]              │
├─────────────────────────────────────────────────────────────┤
│  KPI ROW (3 columns)                                      │
│  [Total Institutions: 150] [Avg Confidence: 0.85] [%ALTO: 15%] │
├─────────────────────────────────────────────────────────────┤
│  CHART ROW (2 columns)                                     │
│  ┌─────────────────────┐  ┌──────────────────────────────┐ │
│  │ Risk Distribution   │  │  Historical Trend (2021-2023)│ │
│  │ (Bar Chart)         │  │  (Line Chart)                │ │
│  │ ALTO: 23 (15%)      │  │                              │ │
│  │ MEDIO: 45 (30%)     │  │                              │ │
│  │ BAJO: 82 (55%)      │  │                              │ │
│  └─────────────────────┘  └──────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  SCORE CARD                                                │
│  [Predicted Success Rate: 68%]                             │
├─────────────────────────────────────────────────────────────┤
│  TABLE: Institution Details (with filters)                 │
│  ID | Name | 2023 Score | Trend | Risk | Confidence        │
└─────────────────────────────────────────────────────────────┘
```

#### Chart Details

**KPI Cards (3 cards in row)**:
- **Total Institutions**: `COUNT(institution_id)`
- **Avg Confidence**: `AVG(confidence)`
- **% High Risk**: `COUNTIF(risk_level="ALTO") / COUNT(*) * 100`

**Risk Distribution Bar Chart**:
- Dimension: `risk_level`
- Metric: `COUNT(institution_id)`
- Colors: ALTO=Red, MEDIO=Yellow, BAJO=Green

**Historical Trend Line Chart**:
- Dimensions: Year (2021, 2022, 2023)
- Metrics: `avg_score_2021`, `avg_score_2022`, `avg_score_2023`
- Line per institution (or aggregate)

**Score Card**:
- Metric: `AVG(predicted_success) * 100`
- Display as percentage

**Institution Table**:
- Columns: `institution_id`, `nom_ie`, `avg_score_2023`, `trend`, `risk_level`, `confidence`
- Sort by: `risk_level` (ALTO first), then `confidence` (ascending)
- Page size: 20 rows

---

### 2. Matemática Dashboard

**Purpose**: Monitor academic performance and predictions for Matemática area.

*Same layout and chart configuration as Comunicación Dashboard, using `v_callao_matematica_2026` as data source.*

---

### 3. CCSS Dashboard

**Purpose**: Monitor academic performance and predictions for CCSS area.

*Same layout and chart configuration as Comunicación Dashboard, using `v_callao_ccss_2026` as data source.*

---

### 4. CyT Dashboard

**Purpose**: Monitor academic performance and predictions for Ciencia y Tecnología area.

*Same layout and chart configuration as Comunicación Dashboard, using `v_callao_cyt_2026` as data source.*

---

### 5. Executive Summary Dashboard

**Purpose**: Aggregate view across all 4 areas for district-level decision making.

#### Layout (Top to Bottom)

```
┌─────────────────────────────────────────────────────────────┐
│  HEADER: ENLA 2026 Callao - Executive Summary               │
│  All Areas Overview                                         │
├─────────────────────────────────────────────────────────────┤
│  KPI ROW (4 columns - one per area)                         │
│  [Com: 150 inst] [Mat: 148 inst] [CCSS: 152 inst] [CyT: 145 inst] │
├─────────────────────────────────────────────────────────────┤
│  KPI ROW 2 (4 columns - risk % per area)                   │
│  [Com: 15% ALTO] [Mat: 18% ALTO] [CCSS: 12% ALTO] [CyT: 14% ALTO] │
├─────────────────────────────────────────────────────────────┤
│  HEAT MAP: Risk Level × Area                               │
│  (Area on Y-axis, Risk Level on X-axis, Count as metric)   │
├─────────────────────────────────────────────────────────────┤
│  BAR CHART: Success Rate Comparison by Area                 │
│  (Horizontal bar chart, areas on Y-axis)                   │
├─────────────────────────────────────────────────────────────┤
│  TABLE: All High-Risk Institutions (across all areas)      │
│  Area | ID | Name | 2023 Score | Risk | Confidence         │
└─────────────────────────────────────────────────────────────┘
```

#### Chart Details

**KPI Cards (Row 1 - 4 columns)**:
- Per area: `COUNT(institution_id)` as "Total Institutions"

**KPI Cards (Row 2 - 4 columns)**:
- Per area: `COUNTIF(risk_level="ALTO") / COUNT(*) * 100` as "% High Risk"

**Heat Map**:
- Rows: `area`
- Columns: `risk_level`
- Metric: `COUNT(institution_id)`
- Color scale: Green (BAJO) to Red (ALTO)

**Comparison Bar Chart**:
- Dimension: `area`
- Metric: `AVG(avg_score_2023)` or `AVG(predicted_success) * 100`
- Sort: Descending by metric

**High-Risk Table**:
- Filter: `risk_level = "ALTO"`
- Columns: `area`, `institution_id`, `nom_ie`, `avg_score_2023`, `risk_level`, `confidence`
- Sort: `area` ASC, `confidence` ASC
- Page size: 50 rows

---

## Chart Configurations

### Standard Chart Settings

| Setting | Value |
|---------|-------|
| Theme | Light (default) |
| Font | Roboto (default) |
| Color Palette | Category 20 (default) |
| Date Format | DD/MM/YYYY |
| Number Format | Decimal places: 2 |

### Risk Level Colors

| Risk Level | Hex Code | RGB |
|------------|----------|-----|
| ALTO | #E74C3C | 231, 76, 60 |
| MEDIO | #F39C12 | 243, 156, 18 |
| BAJO | #27AE60 | 39, 174, 96 |

### Area Colors

| Area | Hex Code | RGB |
|------|----------|-----|
| Comunicación | #3498DB | 52, 152, 219 |
| Matemática | #9B59B6 | 155, 89, 182 |
| CCSS | #2ECC71 | 46, 204, 113 |
| CyT | #E67E22 | 230, 126, 34 |

---

## Filters and Controls

### Per-Area Dashboard Filters

| Filter | Type | Field | Default |
|--------|------|-------|---------|
| Risk Level | Dropdown | `risk_level` | All |
| Min Confidence | Slider (0-1) | `confidence` | 0 |
| Institution Search | Text Input | `nom_ie` | (empty) |
| Prediction Version | Dropdown | `model_version` | latest |

### Executive Summary Filters

| Filter | Type | Field | Default |
|--------|------|-------|---------|
| Area | Multi-select | `area` | All |
| Risk Level | Multi-select | `risk_level` | All |
| Min Score 2023 | Slider (0-20) | `avg_score_2023` | 0 |

---

## Refresh Schedule

### BigQuery Scheduled Queries

Configure in BigQuery console:

| Schedule | Query | Destination |
|----------|-------|-------------|
| Daily 03:00 UTC | `CREATE OR REPLACE VIEW ...` | Each dashboard view |

### Looker Studio Cache

- Data freshness: Live (BigQuery direct)
- Cache duration: 4 hours (Looker Studio default)
- Manual refresh: Use refresh button in dashboard

---

## Access Control

### Sharing Settings

| Role | Permissions | Audience |
|------|-------------|----------|
| Viewer | View only | Teachers, Staff |
| Editor | Edit charts/layout | Data Team |
| Owner | Full access | Admin only |

### Data Security

- BigQuery: IAM-based access (service account)
- Looker Studio: Share via email/link
- No PII exposed (institution names only)
- Data sourced from materialized views (read-only)

---

## Implementation Checklist

### Pre-Implementation

- [ ] Verify dbt models run successfully (`dbt run`)
- [ ] Verify BigQuery views exist and have data
- [ ] Document BigQuery table IDs
- [ ] Get list of dashboard viewers' email addresses

### Dashboard Creation (per dashboard)

- [ ] Create new report in Looker Studio
- [ ] Connect to BigQuery data source
- [ ] Add KPI score cards (3 cards)
- [ ] Add risk distribution bar chart
- [ ] Add historical trend line chart
- [ ] Add predicted success score card
- [ ] Add institution details table
- [ ] Add filters (risk level, confidence, search)
- [ ] Apply color scheme and formatting
- [ ] Add header with title and timestamp
- [ ] Test with sample data
- [ ] Share with stakeholders
- [ ] Document dashboard URL in `RUNBOOK.md`

### Executive Summary Only

- [ ] Create KPI cards for all 4 areas (2 rows)
- [ ] Add heat map (risk × area)
- [ ] Add comparison bar chart
- [ ] Add high-risk institutions table
- [ ] Add area and risk level filters

### Post-Implementation

- [ ] Set up BigQuery scheduled queries (03:00 UTC)
- [ ] Verify data refreshes correctly
- [ ] Train users on dashboard interpretation
- [ ] Document feedback and improvement items

---

## Appendix: Sample Looker Studio Calculated Fields

### Risk Percentage

```
Risk Pct = COUNTIF(risk_level="ALTO") / COUNT(*) * 100
```

### Success Rate

```
Success Rate = AVG(predicted_success) * 100
```

### Trend Indicator

```
Trend Indicator = IF(trend > 0, "Improving", IF(trend < 0, "Declining", "Stable"))
```

### Confidence Level

```
Confidence Level = CASE
  WHEN confidence >= 0.8 THEN "High"
  WHEN confidence >= 0.6 THEN "Medium"
  ELSE "Low"
END
```
