# Technical Lab Report: OpenTelemetry Integration & System Observability
## Project: AI-based Village Pond Planning System (Terrain Analyzer)

---

### Student & Submission Information
- **Project Title:** AI-based Village Pond Planning System (Terrain Analyzer)
- **Component Evaluated:** OpenTelemetry Distributed Tracing, Metrics, and Correlated Logging
- **Environment:** Windows 11 x64, Python 3.13, FastAPI, Jaeger All-In-One v1.60, Prometheus Exporter

---

## 1. Executive Summary & Objective

Modern distributed systems, microservices, and compute-heavy geospatial backend services rely on observability to answer critical questions: *What happened? Where was the time spent? Which exact subsystem failed and why?*

The objective of this assignment is to integrate the **OpenTelemetry (OTel)** open standard into the existing **AI-based Village Pond Planning System (Terrain Analyzer)**. OpenTelemetry provides vendor-neutral APIs, SDKs, and tooling to capture and export the three primary pillars of observability:
1. **Distributed Tracing:** Microsecond-resolution execution graphs with parent-child span hierarchies, tags, and events.
2. **Application Metrics:** Counters, histograms, and gauges exposing computational throughput, latency distributions, and resource utilization.
3. **Correlated Logging:** Log events automatically enriched with active `trace_id` and `span_id` contexts to eliminate guesswork during forensic debugging.

This report details the design, implementation, and empirical verification of OpenTelemetry within the project, complete with data captured directly from the running system, screenshot demonstrations, and an architectural analysis of system behavior.

---

## 2. System Architecture & Observability Topology

### 2.1 Backend Workflow & Core Pipeline

The Village Pond Planning System processes complex topographic inputs (KML/KMZ contour lines) to identify optimal water harvesting pond locations and delineate hydrologic catchment areas. Its pipeline consists of five intensive computational stages:
1. **Contour Extraction & Parsing:** Extracts raw KML from KMZ ZIP archives and parses multi-geometry elevation contours.
2. **DEM Reconstruction:** Interpolates irregular vector contours into a dense raster Digital Elevation Model (DEM) grid.
3. **Pond Suitability Evaluation:** Evaluates candidate topographic depressions using slope, flow accumulation, depression depth, and runoff potential.
4. **Hydrologic Watershed Delineation:** Executes D8 flow routing from the recommended pond outlet to compute contributing catchment area.
5. **Geospatial Overlay Generation:** Renders hillshade and hypsometric elevation overlays for spatial mapping.

### 2.2 Observability Architecture Diagram

```mermaid
graph TD
    Client["Client / Evaluator Browser"] -->|HTTP POST /api/analyzeContour| FastAPI["FastAPI Application (Port 5240)"]
    
    subgraph "FastAPI Instrumentation Layer"
        FastAPI --> FastApiInst["FastAPIInstrumentor"]
        FastAPI --> Middleware["OpenTelemetry Trace & Metric Middleware"]
        FastAPI --> Pipeline["Contour Analysis Pipeline"]
    end

    subgraph "Domain Spans"
        Pipeline --> Span1["parse_contour_kml_kmz"]
        Pipeline --> Span2["reconstruct_terrain_dem"]
        Pipeline --> Span3["evaluate_pond_suitability"]
        Pipeline --> Span4["delineate_catchment_watershed"]
        Pipeline --> Span5["generate_dem_overlays"]
    end

    subgraph "OpenTelemetry SDK Engine"
        Span1 & Span2 & Span3 & Span4 & Span5 --> TracerProvider["TracerProvider (BatchSpanProcessor)"]
        Middleware --> MeterProvider["MeterProvider (PrometheusMetricReader)"]
        Pipeline --> LoggerInst["Python Logging (trace_id & span_id injection)"]
    end

    subgraph "Exporters & Backends"
        TracerProvider -->|OTLP HTTP (Port 4318)| Jaeger["Jaeger All-In-One (Port 16686)"]
        TracerProvider -->|In-Memory Buffer| MemTrace["Internal Spans Storage"]
        MeterProvider -->|Scrape Endpoint| PromEndpoint["/metrics (Prometheus Format)"]
        LoggerInst --> StorageLog["storage/opentelemetry.log"]
    end

    subgraph "Visualization & Inspection"
        Jaeger --> JaegerUI["Jaeger Web UI (http://localhost:16686)"]
        MemTrace & StorageLog --> TelemetryUI["Telemetry Center Dashboard (http://localhost:5240/telemetry)"]
        PromEndpoint --> PromUI["Prometheus Scrape Client / Direct Inspection"]
    end
```

---

## 3. Implementation Details

The OpenTelemetry subsystem is implemented cleanly and modularly in [`backend/telemetry.py`](file:///c:/Users/Abhigyan%20Sharma/OneDrive/Desktop/Contour/backend/telemetry.py) and seamlessly integrated into the application lifecycle in [`backend/main.py`](file:///c:/Users/Abhigyan%20Sharma/OneDrive/Desktop/Contour/backend/main.py) and [`backend/api/contour_analysis_routes.py`](file:///c:/Users/Abhigyan%20Sharma/OneDrive/Desktop/Contour/backend/api/contour_analysis_routes.py).

### 3.1 Distributed Tracing Implementation
- **Resource Definition:** Standard OpenTelemetry semantic resource attributes:
  ```python
  resource = Resource.create({
      "service.name": "village-pond-planning-system",
      "service.namespace": "hydrology-dem-ai",
      "service.version": "1.0.0",
      "deployment.environment": "production",
      "host.name": os.getenv("COMPUTERNAME", "localhost")
  })
  ```
- **OTLP Trace Exporter:** Batched export via `OTLPSpanExporter(endpoint="http://localhost:4318/v1/traces")` communicating directly with Jaeger's native OpenTelemetry HTTP receiver on port 4318.
- **In-Memory Ring Buffer:** An `InMemorySpanRecorder` collects recent finished spans (up to 250) for immediate querying via `/api/telemetry/spans` and live dashboard rendering.
- **FastAPI Auto-Instrumentation:** `FastAPIInstrumentor.instrument_app(app)` instruments every HTTP route, capturing:
  - `http.method` (e.g. `POST`, `GET`)
  - `http.route` (e.g. `/api/analyzeContour`, `/findCatchment`)
  - `http.status_code` (e.g. `200`, `400`, `422`, `500`)
  - `http.target` and client parameters.
- **Domain Child Spans:** Manual spans instrumenting each critical algorithmic step using `tracer.start_as_current_span(...)`:
  - `parse_contour_kml_kmz`: Captures `file.name`, `file.format`, `file.size_bytes`, `contour.count`, and elevation bounds.
  - `reconstruct_terrain_dem`: Captures raster `dem.grid_rows`, `dem.grid_cols`, `dem.total_cells`, and spatial `dem.pixel_size_m`.
  - `evaluate_pond_suitability`: Captures `suitability.num_candidates`, `suitability.top_score`, and optimal coordinates.
  - `delineate_catchment_watershed`: Captures `catchment.area_m2`, `catchment.area_km2`, and watershed slope.
  - `generate_dem_overlays`: Captures visualization rendering performance.

### 3.2 Metrics Collection Implementation
- **Meter Provider & Reader:** Configured with `PrometheusMetricReader()`, exposing live metrics at `http://localhost:5240/metrics`.
- **Custom Business & Operational Instruments:**
  | Metric Name | Instrument Type | Unit | Description |
  | :--- | :--- | :--- | :--- |
  | `village_pond_requests_total` | Counter | `1` | Total API requests grouped by method, route, and HTTP status code |
  | `village_pond_request_duration_seconds` | Histogram | `s` | Latency distribution of HTTP endpoints across logarithmic buckets |
  | `village_pond_analysis_duration_seconds` | Histogram | `s` | End-to-end contour analysis and pond modeling processing latency |
  | `village_pond_candidates_found_total` | Counter | `1` | Number of viable pond candidate sites discovered per analysis |
  | `village_pond_catchment_area_m2` | Histogram | `m²` | Distribution of watershed catchment areas calculated |
  | `village_pond_active_requests` | UpDownCounter | `1` | Real-time gauge of in-flight concurrent calculations |
  | `village_pond_contours_parsed_total` | Counter | `1` | Cumulative vector contour lines ingested from KML/KMZ files |
  | `village_pond_dem_cells_processed_total` | Counter | `1` | Cumulative raster elevation cells processed |

### 3.3 Correlated Logging Implementation
- **Context Injection:** Python's standard `logging` library is configured via `LoggingInstrumentor().instrument(set_logging_format=True)`.
- **Log Format:**
  `%(asctime)s [%(levelname)s] [trace_id=%(otelTraceID)s span_id=%(otelSpanID)s] %(name)s: %(message)s`
- **Correlation Benefit:** Whenever a log message is emitted during a request, OpenTelemetry extracts the active `trace_id` and `span_id` from the thread-local context and embeds them into the log line.
- **Dual Persistence:** Logs are persisted to `storage/opentelemetry.log` and captured in an in-memory buffer (`InMemoryLogHandler`) for real-time inspection in the web dashboard.

### 3.4 Context Propagation & Response Headers
To facilitate end-to-end verification, custom middleware automatically injects tracing headers into all HTTP responses:
- `X-Trace-ID`: Hex-encoded 128-bit trace ID (e.g., `f585c3b465a43cc4f08a400a71ceeb83`)
- `X-Span-ID`: Hex-encoded 64-bit root span ID (e.g., `4ac0f4a5945400a4`)

---

## 4. Tools, Libraries, and Backend Services Used

| Component | Tool / Library | Version | Role in Architecture |
| :--- | :--- | :--- | :--- |
| **Telemetry API** | `opentelemetry-api` | 1.45.1 | Abstract interface for tracing, metrics, and context propagation |
| **Telemetry SDK** | `opentelemetry-sdk` | 1.45.1 | Concrete tracer/meter implementations, batching, and span processing |
| **FastAPI Instrumentation** | `opentelemetry-instrumentation-fastapi` | 0.66b1 | Automatic HTTP request/response span and latency tracking |
| **Logging Instrumentation** | `opentelemetry-instrumentation-logging` | 0.66b1 | Trace context injection into Python standard loggers |
| **OTLP Exporter** | `opentelemetry-exporter-otlp` | 1.45.1 | Exporting telemetry to Jaeger over HTTP (Port 4318) |
| **Prometheus Exporter** | `opentelemetry-exporter-prometheus` | 0.66b1 | Translating OpenTelemetry metrics into Prometheus exposition format |
| **Prometheus Client** | `prometheus_client` | 0.21.1 | Serving `/metrics` scrape endpoint |
| **Distributed Tracing Backend** | **Jaeger All-In-One** | v1.60.0 | High-performance distributed tracing backend, collector, and web UI |
| **Observability Dashboard** | **Telemetry Center UI** | 1.0.0 | Embedded real-time web portal hosted directly on the application |

---

## 5. Screenshot Demonstrations & Results Analysis

The screenshots below were captured directly from the live running project during execution of contour analysis on `contours_1m.kml` and `contours_1m.kmz`. All screenshot files are stored in [`telemetry_screenshots/`](file:///c:/Users/Abhigyan%20Sharma/OneDrive/Desktop/Contour/telemetry_screenshots/).

---

### Screenshot 1: Jaeger Service Discovery & Trace Query
![Screenshot 1: Jaeger Service Discovery](file:///c:/Users/Abhigyan%20Sharma/OneDrive/Desktop/Contour/telemetry_screenshots/01_jaeger_service_selection.png)

- **Source URL:** `http://localhost:16686`
- **What this demonstrates:**
  - The Jaeger UI running on port 16686 has successfully discovered the instrumented service: `village-pond-planning-system`.
  - The operation dropdown reflects all auto-instrumented endpoints as well as internal domain spans (`parse_contour_kml_kmz`, `reconstruct_terrain_dem`, `evaluate_pond_suitability`, `delineate_catchment_watershed`, `generate_dem_overlays`).
  - This verifies that the OTLP exporter is actively transmitting registered service metadata and span definitions to the Jaeger backend.

---

### Screenshot 2: Jaeger Traces List & Latency Timeline
![Screenshot 2: Jaeger Traces List](file:///c:/Users/Abhigyan%20Sharma/OneDrive/Desktop/Contour/telemetry_screenshots/02_jaeger_traces_list.png)

- **Source URL:** `http://localhost:16686/search?service=village-pond-planning-system`
- **What this demonstrates:**
  - A comprehensive query result showing all captured traces across different user interactions.
  - Each entry lists the trace duration, timestamp, total span count, and HTTP operation.
  - Demonstrates both successful analysis requests (e.g. `POST /api/analyzeContour`, 61 spans, duration ~709 ms) and client error validation traces (e.g. `POST /api/analyzeContour`, 5 spans, 400 Bad Request for unsupported file types), proving robust error recording.

---

### Screenshot 3: Deep Trace Waterfall & Nested Span Hierarchy
![Screenshot 3: Deep Trace Waterfall](file:///c:/Users/Abhigyan%20Sharma/OneDrive/Desktop/Contour/telemetry_screenshots/03_jaeger_distributed_trace_waterfall.png)

- **Source URL:** `http://localhost:16686/trace/f585c3b465a43cc4f08a400a71ceeb83`
- **What this demonstrates:**
  - The distributed trace waterfall view for Trace ID `f585c3b465a43cc4f08a400a71ceeb83`.
  - **Span Breakdown:**
    - Root Span: `POST /api/analyzeContour` (709.43 ms)
    - Child 1: `parse_contour_kml_kmz` (298.95 ms) – reading XML, extracting coordinates.
    - Child 2: `reconstruct_terrain_dem` (130.67 ms) – raster interpolation of 1,355 contours.
    - Child 3: `evaluate_pond_suitability` (107.26 ms) – multi-criteria candidate ranking.
    - Child 4: `delineate_catchment_watershed` (56.89 ms) – D8 flow accumulation and polygon tracing.
    - Child 5: `generate_dem_overlays` (30.46 ms) – rendering PNG hillshade/elevation overlays.
  - This waterfall proves the parent-child relationship between HTTP routing and internal business logic.

---

### Screenshot 4: Embedded OpenTelemetry Observability Dashboard
![Screenshot 4: Observability Dashboard Overview](file:///c:/Users/Abhigyan%20Sharma/OneDrive/Desktop/Contour/telemetry_screenshots/04_telemetry_dashboard_overview.png)

- **Source URL:** `http://localhost:5240/telemetry`
- **What this demonstrates:**
  - The project's native Observability Center dashboard.
  - Top-level KPI cards show live statistics: **Total Captured Spans (50+)**, **Distinct Traces (5)**, **Correlated Logs (12)**, and **Average Span Latency (65.2 ms)**.
  - The Spans table shows real-time tabular data with direct clickable links to open the exact trace in Jaeger (`http://localhost:16686/trace/<trace_id>`).

---

### Screenshot 5: Trace-Correlated Application Logs
![Screenshot 5: Trace-Correlated Logs](file:///c:/Users/Abhigyan%20Sharma/OneDrive/Desktop/Contour/telemetry_screenshots/05_telemetry_correlated_logs.png)

- **Source URL:** `http://localhost:5240/telemetry` (Correlated Logs tab)
- **What this demonstrates:**
  - The application logs emitted by `village_pond.contour_analysis`.
  - Crucially, every single log message is bound to its parent `trace_id` (e.g. `f585c3b465...`) and specific child `span_id`.
  - For example, when parsing finishes, the log `Successfully parsed 1355 contours from contours_1m.kml` carries `span_id=99e12d69...`, which matches the exact `parse_contour_kml_kmz` span in the waterfall!
  - Clicking any trace ID instantly navigates to that trace in the Jaeger UI.

---

### Screenshot 6: Registered OpenTelemetry Metric Instruments
![Screenshot 6: Metric Instruments Tab](file:///c:/Users/Abhigyan%20Sharma/OneDrive/Desktop/Contour/telemetry_screenshots/06_telemetry_registered_metrics.png)

- **Source URL:** `http://localhost:5240/telemetry` (Prometheus Metrics tab)
- **What this demonstrates:**
  - Overview of all active OpenTelemetry metric instruments (`village_pond_requests_total`, `village_pond_request_duration_seconds`, `village_pond_analysis_duration_seconds`, `village_pond_candidates_found_total`, `village_pond_catchment_area_m2`, `village_pond_active_requests`, `village_pond_contours_parsed_total`, `village_pond_dem_cells_processed_total`).
  - Right panel displays live preview of the Prometheus scrape buffer.

---

### Screenshot 7: Raw Prometheus Exposition Format (/metrics)
![Screenshot 7: Prometheus Raw Metrics](file:///c:/Users/Abhigyan%20Sharma/OneDrive/Desktop/Contour/telemetry_screenshots/07_prometheus_raw_metrics.png)

- **Source URL:** `http://localhost:5240/metrics`
- **What this demonstrates:**
  - The standard Prometheus text exposition format (version 0.0.4).
  - Shows `# HELP` and `# TYPE` declarations for gauges, counters, and cumulative histogram buckets with boundary labels (`le="5.0"`, `le="10.0"`, `le="+Inf"`).
  - Can be directly ingested by Prometheus servers, Grafana Agent, or Datadog collectors.

---

## 6. Analytical Understanding & Practical Value of OpenTelemetry

### 6.1 Performance Profiling & Latency Diagnostics
In geospatial hydrological modeling, processing times can vary dramatically depending on the number of contour vertices and DEM resolution.
- **Before OpenTelemetry:** The developer only knew that an upload request took ~700 ms. If a request slowed down to 5 seconds, there was no visibility into which algorithm caused the delay.
- **With OpenTelemetry:** The span breakdown reveals exact timing:
  - Vector Parsing: **42.1%** of total runtime (298.9 ms).
  - DEM Interpolation: **18.4%** of runtime (130.7 ms).
  - Candidate Scoring: **15.1%** of runtime (107.3 ms).
  - Watershed Delineation: **8.0%** of runtime (56.9 ms).
  - Overlay Generation: **4.3%** of runtime (30.5 ms).
  This proves that parsing large KML XML trees is the primary computational bottleneck. Optimization efforts should target vector parsing (e.g. streaming SAX/iterparse) rather than the hydrology algorithms.

### 6.2 Root Cause Analysis & Error Pinpointing
When an invalid or corrupt file is submitted:
1. The root HTTP span records status `400 Bad Request` or `422 Unprocessable Entity`.
2. The failing span (`parse_contour_kml_kmz`) captures the exception stack trace and sets `status=ERROR`.
3. The correlated logs immediately display the error message alongside the `trace_id`.
4. An on-call engineer can take the `X-Trace-ID` returned to the user, enter it into Jaeger or the Telemetry Center, and immediately see the exact line of code and input data that failed, without sifting through gigabytes of unrelated logs.

### 6.3 Capacity Planning & SLA Monitoring via Metrics
The collected metrics provide continuous health tracking:
- **`village_pond_requests_total`** allows calculation of request rates (QPS) and error percentages ($4xx/5xx$ ratio).
- **`village_pond_request_duration_seconds`** allows calculating p50, p95, and p99 Service Level Objectives (SLOs).
- **`village_pond_dem_cells_processed_total`** tracks backend computation volume over time, aiding server sizing and memory allocation.

---

## 7. How to Run and Verify the Implementation

### 7.1 Single-Script Launch
The repository includes automated launch scripts for Windows:
```powershell
# In PowerShell:
.\start.ps1

# Or in Command Prompt:
start.bat
```
This automatically starts:
1. **Jaeger All-In-One Tracing Backend:** `http://localhost:16686` (OTLP port 4318)
2. **FastAPI Backend (Instrumented):** `http://localhost:5240`
3. **React Frontend:** `http://localhost:3000`

### 7.2 Verification Endpoints
- **Observability Dashboard:** Navigate to [`/telemetry`](http://localhost:5240/telemetry) (or deployed at `http://10.1.75.79:5240/telemetry`).
- **Jaeger UI (Reverse-Proxied):** Directly available at [`/jaeger/`](http://localhost:5240/jaeger/) (or deployed at `http://10.1.75.79:5240/jaeger/`). This transparent FastAPI proxy routes all trace queries to internal Jaeger query backend without requiring external port forwarding for port 16686.
- **Standalone Jaeger UI:** `http://localhost:16686/jaeger/` (when running locally or via SSH port forward).
- **Prometheus Metrics:** Navigate to [`/metrics`](http://localhost:5240/metrics) (or `http://10.1.75.79:5240/metrics`).

### 7.3 Executing Sample Analysis Requests
To generate fresh traces, execute the included test contour files:
```powershell
# Test KML analysis
python -c "import requests; r = requests.post('http://localhost:5240/api/analyzeContour', files={'file': open('contours_1m.kml', 'rb')}); print('Status:', r.status_code, 'Trace-ID:', r.headers.get('X-Trace-ID'))"

# Test KMZ analysis
python -c "import requests; r = requests.post('http://localhost:5240/findCatchment', files={'file': open('contours_1m.kmz', 'rb')}); print('Status:', r.status_code, 'Trace-ID:', r.headers.get('X-Trace-ID'))"
```

---

## 8. Conclusion

OpenTelemetry integration transforms the AI-based Village Pond Planning System from an opaque backend service into a fully observable, production-ready system. By capturing distributed traces across the entire contour analysis pipeline, recording domain-specific Prometheus metrics, and correlating log statements with unique TraceIDs and SpanIDs, the system provides total transparency into performance, resource usage, and error states.

All assignment requirements—instrumenting the existing Assignment 1 project, capturing traces, metrics, and logs, running live backends, and validating the output with empirical screenshots—have been successfully achieved and verified.
