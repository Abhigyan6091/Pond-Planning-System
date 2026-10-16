"""
backend/telemetry.py
====================
Comprehensive OpenTelemetry Observability Subsystem for the
AI-based Village Pond Planning System (Terrain Analyzer).

Components:
1. Distributed Tracing:
   - Resource configuration (service.name, service.namespace, service.version, deployment.environment)
   - OTLP Span Exporter (HTTP to Jaeger collector at http://localhost:4318/v1/traces)
   - In-Memory Ring Buffer Span Recorder for immediate local inspection & API queries
   - Automatic FastAPI instrumentation via FastAPIInstrumentor
   - Trace correlation headers (X-Trace-ID, X-Span-ID)
2. Metrics:
   - PrometheusMetricReader exposing /metrics
   - Custom business & operational metrics:
     * village_pond_requests_total (Counter)
     * village_pond_request_duration_seconds (Histogram)
     * village_pond_analysis_duration_seconds (Histogram)
     * village_pond_candidates_found_total (Counter)
     * village_pond_catchment_area_m2 (Histogram)
     * village_pond_active_requests (UpDownCounter)
     * village_pond_contours_parsed_total (Counter)
     * village_pond_dem_cells_processed_total (Counter)
3. Logging:
   - Python logging integration with OpenTelemetry trace_id & span_id injection
   - In-memory ring buffer for recent correlated logs
   - Persistent file logging to storage/opentelemetry.log
4. Embedded Observability Dashboard:
   - /telemetry HTML UI for visual inspection of Traces, Metrics, and Logs
   - /api/telemetry/overview, /api/telemetry/spans, /api/telemetry/logs REST endpoints
"""

import os
import time
import logging
import collections
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# OpenTelemetry Tracing
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider, ReadableSpan
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.trace import Status, StatusCode, get_current_span

# OpenTelemetry Metrics
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.prometheus import PrometheusMetricReader
import prometheus_client

# OpenTelemetry Instrumentation
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor

logger = logging.getLogger("village_pond.telemetry")

# ---------------------------------------------------------------------------
# In-Memory Telemetry Storage (for local verification, dashboards & reports)
# ---------------------------------------------------------------------------
class InMemorySpanRecorder(SpanExporter):
    """
    Span exporter that captures recent completed spans in a thread-safe deque
    for inspection via REST API and the local observability dashboard.
    """
    def __init__(self, max_spans: int = 200):
        self.spans = collections.deque(maxlen=max_spans)

    def export(self, spans: List[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            trace_id_hex = f"{span.context.trace_id:032x}" if span.context else ""
            span_id_hex = f"{span.context.span_id:016x}" if span.context else ""
            parent_id_hex = f"{span.parent.span_id:016x}" if span.parent else None

            duration_ms = 0.0
            if span.end_time and span.start_time:
                duration_ms = round((span.end_time - span.start_time) / 1e6, 2)

            events_data = []
            for ev in span.events:
                events_data.append({
                    "name": ev.name,
                    "timestamp": datetime.fromtimestamp(ev.timestamp / 1e9).strftime("%H:%M:%S.%f")[:-3],
                    "attributes": dict(ev.attributes or {})
                })

            span_record = {
                "name": span.name,
                "trace_id": trace_id_hex,
                "span_id": span_id_hex,
                "parent_span_id": parent_id_hex,
                "kind": str(span.kind).replace("SpanKind.", ""),
                "start_time": datetime.fromtimestamp(span.start_time / 1e9).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] if span.start_time else "",
                "duration_ms": duration_ms,
                "status": span.status.status_code.name if span.status else "UNSET",
                "status_description": span.status.description or "",
                "attributes": dict(span.attributes or {}),
                "events": events_data
            }
            self.spans.appendleft(span_record)
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


class InMemoryLogHandler(logging.Handler):
    """
    Logging handler that buffers recent log records with trace context
    for display in the telemetry dashboard.
    """
    def __init__(self, max_logs: int = 300):
        super().__init__()
        self.logs = collections.deque(maxlen=max_logs)

    def emit(self, record: logging.LogRecord):
        try:
            current_span = get_current_span()
            ctx = current_span.get_span_context() if current_span else None
            trace_id_hex = f"{ctx.trace_id:032x}" if ctx and ctx.is_valid else getattr(record, "otelTraceID", "00000000000000000000000000000000")
            span_id_hex = f"{ctx.span_id:016x}" if ctx and ctx.is_valid else getattr(record, "otelSpanID", "0000000000000000")

            entry = {
                "timestamp": datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "trace_id": trace_id_hex if trace_id_hex != "0" else "",
                "span_id": span_id_hex if span_id_hex != "0" else "",
                "module": record.module,
                "lineno": record.lineno
            }
            self.logs.appendleft(entry)
        except Exception:
            self.handleError(record)


# Global instances
span_recorder = InMemorySpanRecorder(max_spans=250)
log_recorder = InMemoryLogHandler(max_logs=300)

# Global Metrics references
metric_instruments: Dict[str, Any] = {}

def get_tracer(name: str = "village-pond-planner"):
    """Helper to obtain an OpenTelemetry tracer with standard instrumentation scope."""
    return trace.get_tracer(name, "1.0.0")


# ---------------------------------------------------------------------------
# Telemetry Initialization
# ---------------------------------------------------------------------------
def setup_telemetry(app: FastAPI, jaeger_host: str = "localhost", jaeger_port: int = 4318) -> None:
    """
    Initialize OpenTelemetry Tracing, Metrics, and Logging for the FastAPI application.
    """
    # 1. Define standard semantic resource attributes
    resource = Resource.create({
        "service.name": "village-pond-planning-system",
        "service.namespace": "hydrology-dem-ai",
        "service.version": "1.0.0",
        "deployment.environment": "production",
        "host.name": os.getenv("COMPUTERNAME", "localhost")
    })

    # 2. Setup TracerProvider
    tracer_provider = TracerProvider(resource=resource)

    # In-memory recorder for live inspection
    tracer_provider.add_span_processor(BatchSpanProcessor(span_recorder))

    # OTLP HTTP Exporter to Jaeger (port 4318)
    otlp_endpoint = f"http://{jaeger_host}:{jaeger_port}/v1/traces"
    try:
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, timeout=5)
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        logger.info(f"OpenTelemetry OTLP trace exporter configured -> {otlp_endpoint}")
    except Exception as e:
        logger.warning(f"Could not initialize OTLP exporter to {otlp_endpoint}: {e}")

    trace.set_tracer_provider(tracer_provider)

    # 3. Setup Metrics with Prometheus Reader
    prom_reader = PrometheusMetricReader()
    meter_provider = MeterProvider(resource=resource, metric_readers=[prom_reader])
    metrics.set_meter_provider(meter_provider)

    meter = metrics.get_meter("village_pond_planning_system", "1.0.0")

    # Define custom OpenTelemetry Metrics
    global metric_instruments
    metric_instruments = {
        "requests_total": meter.create_counter(
            name="village_pond_requests_total",
            description="Total count of incoming HTTP API requests",
            unit="1"
        ),
        "request_duration": meter.create_histogram(
            name="village_pond_request_duration_seconds",
            description="HTTP request processing latency in seconds",
            unit="s"
        ),
        "analysis_duration": meter.create_histogram(
            name="village_pond_analysis_duration_seconds",
            description="End-to-end village pond contour analysis latency",
            unit="s"
        ),
        "candidates_found": meter.create_counter(
            name="village_pond_candidates_found_total",
            description="Total number of pond candidate sites detected",
            unit="1"
        ),
        "catchment_area": meter.create_histogram(
            name="village_pond_catchment_area_m2",
            description="Calculated catchment watershed area in square meters",
            unit="m2"
        ),
        "active_requests": meter.create_up_down_counter(
            name="village_pond_active_requests",
            description="Currently in-flight concurrent API requests",
            unit="1"
        ),
        "contours_parsed": meter.create_counter(
            name="village_pond_contours_parsed_total",
            description="Total number of raw contour lines parsed from KML/KMZ",
            unit="1"
        ),
        "dem_cells_processed": meter.create_counter(
            name="village_pond_dem_cells_processed_total",
            description="Total raster elevation cells processed across analyses",
            unit="1"
        )
    }

    # 4. Setup Logging Instrumentation
    try:
        LoggingInstrumentor().instrument(set_logging_format=True)
    except Exception as e:
        logger.debug(f"LoggingInstrumentor already active or note: {e}")

    root_logger = logging.getLogger()
    log_recorder.setLevel(logging.INFO)
    root_logger.addHandler(log_recorder)

    # File log handler in storage/
    try:
        storage_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage")
        os.makedirs(storage_dir, exist_ok=True)
        file_handler = logging.FileHandler(os.path.join(storage_dir, "opentelemetry.log"), encoding="utf-8")
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] [trace_id=%(otelTraceID)s span_id=%(otelSpanID)s] %(name)s: %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.INFO)
        root_logger.addHandler(file_handler)
    except Exception as err:
        logger.warning(f"Could not attach opentelemetry.log file handler: {err}")

    # 5. Instrument FastAPI (excluding internal observability & proxy endpoints)
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        excluded_urls="telemetry,metrics,jaeger,docs,openapi.json,favicon.ico"
    )

    # 6. Add HTTP Middleware for Trace-ID header propagation & active requests
    class OpenTelemetryHeaderMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            endpoint = request.url.path
            method = request.method
            is_internal = endpoint.startswith(("/telemetry", "/metrics", "/jaeger"))

            # Increment active requests
            active_counter = metric_instruments.get("active_requests")
            if active_counter and not is_internal:
                active_counter.add(1, {"endpoint": endpoint, "method": method})

            start_time = time.time()
            try:
                response: Response = await call_next(request)
            except Exception as exc:
                # Record error status on active span
                current_span = get_current_span()
                if current_span and current_span.is_recording():
                    current_span.set_status(Status(StatusCode.ERROR, str(exc)))
                    current_span.record_exception(exc)
                raise exc
            finally:
                duration = time.time() - start_time
                if active_counter and not is_internal:
                    active_counter.add(-1, {"endpoint": endpoint, "method": method})

            # Record custom metrics
            if not is_internal:
                req_counter = metric_instruments.get("requests_total")
                if req_counter:
                    req_counter.add(1, {
                        "endpoint": endpoint,
                        "method": method,
                        "status_code": str(response.status_code)
                    })

                req_duration = metric_instruments.get("request_duration")
                if req_duration:
                    req_duration.record(duration, {
                        "endpoint": endpoint,
                        "method": method
                    })

            # Attach X-Trace-ID & X-Span-ID headers for direct tracing verification
            current_span = get_current_span()
            if current_span:
                ctx = current_span.get_span_context()
                if ctx and ctx.is_valid:
                    response.headers["X-Trace-ID"] = f"{ctx.trace_id:032x}"
                    response.headers["X-Span-ID"] = f"{ctx.span_id:016x}"

            return response

    app.add_middleware(OpenTelemetryHeaderMiddleware)

    # 7. Mount Observability & Telemetry Endpoints
    _register_telemetry_routes(app)
    logger.info("OpenTelemetry full instrumentation successfully mounted on FastAPI app.")


def _register_telemetry_routes(app: FastAPI):
    """Register Prometheus metrics and interactive OpenTelemetry dashboard endpoints."""

    @app.get("/metrics", summary="OpenTelemetry Prometheus Metrics", tags=["Observability"])
    def prometheus_metrics():
        """Expose current OpenTelemetry & runtime metrics in Prometheus exposition format."""
        data = prometheus_client.generate_latest()
        return Response(content=data, media_type="text/plain; version=0.0.4; charset=utf-8")

    @app.get("/api/telemetry/overview", summary="OpenTelemetry Overview Stats", tags=["Observability"])
    def telemetry_overview():
        """Get summary statistics of captured traces, spans, and metrics."""
        spans_list = list(span_recorder.spans)
        logs_list = list(log_recorder.logs)
        unique_traces = set(s["trace_id"] for s in spans_list if s["trace_id"])

        avg_latency = 0.0
        if spans_list:
            avg_latency = round(sum(s["duration_ms"] for s in spans_list) / len(spans_list), 2)

        return {
            "status": "active",
            "service_name": "village-pond-planning-system",
            "service_version": "1.0.0",
            "environment": "production",
            "jaeger_url": "/jaeger/",
            "metrics_url": "/metrics",
            "total_captured_spans": len(spans_list),
            "total_captured_traces": len(unique_traces),
            "total_captured_logs": len(logs_list),
            "average_span_latency_ms": avg_latency,
            "recorded_instruments": list(metric_instruments.keys())
        }

    @app.api_route("/jaeger/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"], include_in_schema=False)
    @app.get("/jaeger", include_in_schema=False)
    async def jaeger_proxy(request: Request, path: str = ""):
        """
        Transparent reverse proxy to Jaeger UI & Query API on 127.0.0.1:16686/jaeger/...
        Enables access to full Jaeger UI remotely via port 5240 even when port 16686 is not forwarded.
        """
        if not path and not request.url.path.endswith("/"):
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url="/jaeger/")

        jaeger_target = f"http://127.0.0.1:16686/jaeger/{path}"
        query_str = request.url.query

        # Compensate for client-to-server clock/timezone skew (e.g. browser in IST vs container in UTC epoch)
        if path == "api/traces" and query_str and ("start=" in query_str or "end=" in query_str):
            try:
                from urllib.parse import parse_qs, urlencode
                params = parse_qs(query_str)
                server_now_us = int(time.time() * 1e6)
                client_end_us = int(params["end"][0]) if "end" in params else server_now_us
                client_start_us = int(params["start"][0]) if "start" in params else (client_end_us - 300 * 1000000)

                # If client clock differs from server clock by more than 5 minutes (e.g. 5.5 hour IST/UTC skew)
                if abs(server_now_us - client_end_us) > 300 * 1000000:
                    duration_us = max(client_end_us - client_start_us, 60 * 1000000)
                    params["end"] = [str(server_now_us + 60 * 1000000)] # 1-min future buffer
                    params["start"] = [str(server_now_us - duration_us)]
                    query_str = urlencode(params, doseq=True)
            except Exception as ex:
                logger.debug(f"Time normalization ignored: {ex}")

        if query_str:
            jaeger_target += f"?{query_str}"

        body = await request.body()
        req_headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}

        try:
            import requests
            resp = requests.request(
                method=request.method,
                url=jaeger_target,
                headers=req_headers,
                data=body if body else None,
                allow_redirects=False,
                timeout=15
            )

            resp_headers = {
                k: v for k, v in resp.headers.items()
                if k.lower() not in ("content-encoding", "transfer-encoding", "content-length")
            }

            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=resp_headers,
                media_type=resp.headers.get("content-type")
            )
        except Exception as e:
            logger.error(f"Error proxying request to Jaeger at {jaeger_target}: {e}")
            return HTMLResponse(
                f"""<!DOCTYPE html>
<html>
<head><title>Jaeger Unavailable</title><style>body{{font-family:sans-serif;background:#0f172a;color:#f8fafc;padding:2rem;}}</style></head>
<body>
  <h2>Jaeger Backend Unavailable</h2>
  <p>Could not connect to Jaeger All-In-One at <code>http://127.0.0.1:16686</code>: {e}</p>
  <p>Please ensure Jaeger is running with <code>--query.base-path=/jaeger</code></p>
  <p><a href="/telemetry" style="color:#38bdf8;">Return to Telemetry Dashboard</a></p>
</body>
</html>""",
                status_code=502
            )

    @app.get("/api/telemetry/spans", summary="Query OpenTelemetry Spans", tags=["Observability"])
    def get_captured_spans(limit: int = 50, trace_id: Optional[str] = None):
        """Retrieve recent OpenTelemetry spans, optionally filtered by trace_id."""
        spans = list(span_recorder.spans)
        if trace_id:
            spans = [s for s in spans if s["trace_id"] == trace_id]
        return spans[:limit]

    @app.get("/api/telemetry/logs", summary="Query OpenTelemetry Correlated Logs", tags=["Observability"])
    def get_captured_logs(limit: int = 100, trace_id: Optional[str] = None):
        """Retrieve recent logs correlated with OpenTelemetry trace contexts."""
        logs = list(log_recorder.logs)
        if trace_id:
            logs = [l for l in logs if l["trace_id"] == trace_id]
        return logs[:limit]

    @app.get("/telemetry", summary="OpenTelemetry Observability Dashboard", tags=["Observability"], response_class=HTMLResponse)
    def telemetry_dashboard():
        """Render a rich interactive HTML/CSS Observability Dashboard."""
        return _render_dashboard_html()


def _render_dashboard_html() -> str:
    """Generate modern, rich, responsive HTML dashboard for inspecting OpenTelemetry data."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OpenTelemetry Observability Center | Village Pond Planning System</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #090d16;
      --card-bg: rgba(18, 24, 38, 0.85);
      --card-border: rgba(255, 255, 255, 0.08);
      --primary: #38bdf8;
      --primary-glow: rgba(56, 189, 248, 0.25);
      --accent: #818cf8;
      --success: #34d399;
      --warning: #fbbf24;
      --danger: #f87171;
      --text-main: #f1f5f9;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      --font-sans: 'Outfit', -apple-system, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text-main);
      font-family: var(--font-sans);
      min-height: 100vh;
      overflow-x: hidden;
      background-image: 
        radial-gradient(circle at 15% 15%, rgba(56, 189, 248, 0.08) 0%, transparent 40%),
        radial-gradient(circle at 85% 85%, rgba(129, 140, 248, 0.08) 0%, transparent 40%);
    }
    header {
      padding: 1.5rem 2.5rem;
      border-bottom: 1px solid var(--card-border);
      backdrop-filter: blur(12px);
      background: rgba(9, 13, 22, 0.8);
      position: sticky;
      top: 0;
      z-index: 50;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 1rem;
    }
    .logo-badge {
      width: 44px;
      height: 44px;
      border-radius: 12px;
      background: linear-gradient(135deg, #0284c7, #6366f1);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      font-size: 1.25rem;
      color: white;
      box-shadow: 0 0 20px var(--primary-glow);
    }
    .brand h1 {
      font-size: 1.25rem;
      font-weight: 700;
      letter-spacing: -0.02em;
    }
    .brand p {
      font-size: 0.8rem;
      color: var(--text-muted);
    }
    .nav-actions {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .btn {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.5rem 1rem;
      border-radius: 8px;
      font-size: 0.85rem;
      font-weight: 600;
      text-decoration: none;
      cursor: pointer;
      transition: all 0.2s ease;
      border: 1px solid var(--card-border);
    }
    .btn-primary {
      background: linear-gradient(135deg, #0284c7, #4f46e5);
      color: white;
      border: none;
      box-shadow: 0 4px 14px var(--primary-glow);
    }
    .btn-primary:hover {
      transform: translateY(-1px);
      box-shadow: 0 6px 20px rgba(56, 189, 248, 0.4);
    }
    .btn-secondary {
      background: rgba(255, 255, 255, 0.05);
      color: var(--text-main);
    }
    .btn-secondary:hover {
      background: rgba(255, 255, 255, 0.1);
    }
    .status-pill {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.4rem 0.85rem;
      background: rgba(52, 211, 153, 0.1);
      border: 1px solid rgba(52, 211, 153, 0.3);
      border-radius: 999px;
      font-size: 0.75rem;
      color: var(--success);
      font-weight: 600;
    }
    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--success);
      box-shadow: 0 0 10px var(--success);
      animation: pulse 2s infinite;
    }
    @keyframes pulse { 0% { opacity: 0.5; } 50% { opacity: 1; } 100% { opacity: 0.5; } }
    main {
      padding: 2rem 2.5rem;
      max-width: 1600px;
      margin: 0 auto;
    }
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1.25rem;
      margin-bottom: 2rem;
    }
    .stat-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 1.25rem;
      backdrop-filter: blur(10px);
      transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .stat-card:hover {
      transform: translateY(-2px);
      border-color: rgba(56, 189, 248, 0.3);
    }
    .stat-label {
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--text-muted);
      margin-bottom: 0.5rem;
    }
    .stat-value {
      font-size: 1.85rem;
      font-weight: 700;
      color: var(--text-main);
      font-family: var(--font-mono);
    }
    .stat-meta {
      font-size: 0.75rem;
      color: var(--text-dim);
      margin-top: 0.4rem;
    }
    .tabs {
      display: flex;
      gap: 0.5rem;
      border-bottom: 1px solid var(--card-border);
      margin-bottom: 1.5rem;
    }
    .tab-btn {
      padding: 0.75rem 1.25rem;
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-weight: 600;
      font-size: 0.9rem;
      cursor: pointer;
      position: relative;
      transition: color 0.2s ease;
      font-family: var(--font-sans);
    }
    .tab-btn.active {
      color: var(--primary);
    }
    .tab-btn.active::after {
      content: '';
      position: absolute;
      bottom: -1px;
      left: 0;
      right: 0;
      height: 2px;
      background: var(--primary);
      box-shadow: 0 0 10px var(--primary);
    }
    .tab-content { display: none; }
    .tab-content.active { display: block; }

    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 1.5rem;
      backdrop-filter: blur(10px);
      margin-bottom: 1.5rem;
    }
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.25rem;
    }
    .card-title {
      font-size: 1.1rem;
      font-weight: 700;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.85rem;
    }
    th {
      text-align: left;
      padding: 0.75rem 1rem;
      color: var(--text-muted);
      border-bottom: 1px solid var(--card-border);
      font-weight: 600;
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    td {
      padding: 0.85rem 1rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      color: var(--text-main);
    }
    tr:hover td {
      background: rgba(255, 255, 255, 0.02);
    }
    .badge {
      display: inline-block;
      padding: 0.2rem 0.5rem;
      border-radius: 6px;
      font-size: 0.7rem;
      font-weight: 600;
      font-family: var(--font-mono);
    }
    .badge-get { background: rgba(56, 189, 248, 0.15); color: #38bdf8; }
    .badge-post { background: rgba(52, 211, 153, 0.15); color: #34d399; }
    .badge-ok { background: rgba(52, 211, 153, 0.15); color: #34d399; }
    .badge-err { background: rgba(248, 113, 113, 0.15); color: #f87171; }
    .mono { font-family: var(--font-mono); font-size: 0.8rem; }
    .code-box {
      background: rgba(0, 0, 0, 0.5);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 1rem;
      font-family: var(--font-mono);
      font-size: 0.8rem;
      max-height: 400px;
      overflow-y: auto;
      white-space: pre-wrap;
      color: #cbd5e1;
    }
    .trace-link {
      color: var(--primary);
      text-decoration: none;
      transition: text-decoration 0.2s;
    }
    .trace-link:hover { text-decoration: underline; }
    .grid-2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1.5rem;
    }
    @media (max-width: 900px) {
      .grid-2 { grid-template-columns: 1fr; }
      header { padding: 1rem; flex-direction: column; gap: 1rem; }
      main { padding: 1rem; }
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="logo-badge">OTel</div>
      <div>
        <h1>OpenTelemetry Observability Center</h1>
        <p>Village Pond Planning System &bull; Terrain Analyzer Architecture</p>
      </div>
    </div>
    <div class="nav-actions">
      <div class="status-pill">
        <span class="status-dot"></span>
        <span>OTel Active</span>
      </div>
      <a href="/jaeger/" target="_blank" class="btn btn-primary" title="Open Jaeger Tracing UI">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
        Open Jaeger UI
      </a>
      <a href="/metrics" target="_blank" class="btn btn-secondary">Prometheus /metrics</a>
      <button class="btn btn-secondary" onclick="refreshData()">&#x21bb; Refresh</button>
    </div>
  </header>

  <main>
    <!-- Metric Stat Cards -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Captured Spans</div>
        <div class="stat-value" id="stat-spans">-</div>
        <div class="stat-meta">In-memory telemetry buffer</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Distinct Traces</div>
        <div class="stat-value" id="stat-traces" style="color: var(--primary);">-</div>
        <div class="stat-meta">End-to-end user workflows</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Correlated Logs</div>
        <div class="stat-value" id="stat-logs" style="color: var(--accent);">-</div>
        <div class="stat-meta">Logs with trace & span IDs</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Avg Span Latency</div>
        <div class="stat-value" id="stat-latency" style="color: var(--success);">-</div>
        <div class="stat-meta">Microsecond-level precision</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">OTLP & Jaeger UI</div>
        <div class="stat-value" style="font-size: 1.25rem; color: var(--success);">ACTIVE</div>
        <div class="stat-meta"><a href="/jaeger/" target="_blank" style="color:var(--primary); text-decoration:none;">Open /jaeger/ &rarr;</a></div>
      </div>
    </div>

    <!-- Navigation Tabs -->
    <div class="tabs">
      <button class="tab-btn active" onclick="switchTab('tab-spans')">Distributed Traces & Spans</button>
      <button class="tab-btn" onclick="switchTab('tab-logs')">Correlated Logs</button>
      <button class="tab-btn" onclick="switchTab('tab-metrics')">Prometheus Metrics</button>
      <button class="tab-btn" onclick="switchTab('tab-architecture')">Observability Architecture</button>
    </div>

    <!-- TAB 1: SPANS -->
    <div id="tab-spans" class="tab-content active">
      <div class="card">
        <div class="card-header">
          <h2 class="card-title">Captured Spans & Tracing Waterfall</h2>
          <span style="font-size: 0.8rem; color: var(--text-muted);">Real-time instrumentation of FastAPI routes & hydrology services</span>
        </div>
        <div style="overflow-x: auto;">
          <table>
            <thead>
              <tr>
                <th>Operation / Span Name</th>
                <th>Kind</th>
                <th>Trace ID</th>
                <th>Span ID</th>
                <th>Duration</th>
                <th>Status</th>
                <th>Timestamp</th>
              </tr>
            </thead>
            <tbody id="spans-tbody">
              <tr><td colspan="7" style="text-align:center; color: var(--text-dim);">Loading spans...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- TAB 2: LOGS -->
    <div id="tab-logs" class="tab-content">
      <div class="card">
        <div class="card-header">
          <h2 class="card-title">Trace-Correlated Application Logs</h2>
          <span style="font-size: 0.8rem; color: var(--text-muted);">Every log message carries its parent TraceID and SpanID</span>
        </div>
        <div style="overflow-x: auto;">
          <table>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Level</th>
                <th>Logger / Module</th>
                <th>Trace ID</th>
                <th>Span ID</th>
                <th>Log Message</th>
              </tr>
            </thead>
            <tbody id="logs-tbody">
              <tr><td colspan="6" style="text-align:center; color: var(--text-dim);">Loading logs...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- TAB 3: METRICS -->
    <div id="tab-metrics" class="tab-content">
      <div class="grid-2">
        <div class="card">
          <div class="card-header">
            <h2 class="card-title">Registered OpenTelemetry Instruments</h2>
            <span class="badge badge-ok">Prometheus Reader</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>Instrument Name</th>
                <th>Type</th>
                <th>Unit</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td class="mono" style="color:var(--primary);">village_pond_requests_total</td>
                <td><span class="badge badge-get">Counter</span></td>
                <td>1</td>
                <td>Count of HTTP requests broken down by route and status</td>
              </tr>
              <tr>
                <td class="mono" style="color:var(--primary);">village_pond_request_duration_seconds</td>
                <td><span class="badge badge-post">Histogram</span></td>
                <td>s</td>
                <td>HTTP API latency distribution</td>
              </tr>
              <tr>
                <td class="mono" style="color:var(--primary);">village_pond_analysis_duration_seconds</td>
                <td><span class="badge badge-post">Histogram</span></td>
                <td>s</td>
                <td>Pond candidate & catchment computation latency</td>
              </tr>
              <tr>
                <td class="mono" style="color:var(--primary);">village_pond_candidates_found_total</td>
                <td><span class="badge badge-get">Counter</span></td>
                <td>1</td>
                <td>Identified viable pond candidate depression sites</td>
              </tr>
              <tr>
                <td class="mono" style="color:var(--primary);">village_pond_catchment_area_m2</td>
                <td><span class="badge badge-post">Histogram</span></td>
                <td>m²</td>
                <td>Catchment area calculated by D8 flow routing</td>
              </tr>
              <tr>
                <td class="mono" style="color:var(--primary);">village_pond_active_requests</td>
                <td><span class="badge badge-ok">UpDownCounter</span></td>
                <td>1</td>
                <td>Current concurrent in-flight computations</td>
              </tr>
              <tr>
                <td class="mono" style="color:var(--primary);">village_pond_contours_parsed_total</td>
                <td><span class="badge badge-get">Counter</span></td>
                <td>1</td>
                <td>Total raw KML/KMZ contour lines parsed</td>
              </tr>
              <tr>
                <td class="mono" style="color:var(--primary);">village_pond_dem_cells_processed_total</td>
                <td><span class="badge badge-get">Counter</span></td>
                <td>1</td>
                <td>Total raster elevation cells analyzed</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="card">
          <div class="card-header">
            <h2 class="card-title">Live Prometheus Scrape Preview</h2>
            <a href="/metrics" target="_blank" class="btn btn-secondary" style="font-size:0.75rem;">Raw /metrics</a>
          </div>
          <div class="code-box" id="metrics-preview">Fetching Prometheus metrics...</div>
        </div>
      </div>
    </div>

    <!-- TAB 4: ARCHITECTURE -->
    <div id="tab-architecture" class="tab-content">
      <div class="card">
        <h2 class="card-title" style="margin-bottom:1rem;">OpenTelemetry Observability Stack Architecture</h2>
        <p style="color: var(--text-muted); line-height: 1.6; margin-bottom: 1.5rem;">
          This system instruments the <strong>AI-based Village Pond Planning System (Terrain Analyzer)</strong> using the official OpenTelemetry (OTel) Python SDK, implementing the three primary pillars of observability:
        </p>
        <div class="grid-2">
          <div style="background: rgba(255,255,255,0.02); padding: 1.25rem; border-radius: 10px; border: 1px solid var(--card-border);">
            <h3 style="color: var(--primary); margin-bottom: 0.5rem;">1. Distributed Tracing</h3>
            <ul style="color: var(--text-muted); font-size: 0.85rem; padding-left: 1.25rem; line-height: 1.6;">
              <li><strong>FastAPI Auto-Instrumentation:</strong> Captures incoming HTTP requests, routes, methods, and status codes.</li>
              <li><strong>Custom Spans:</strong> Trace internal pipeline stages: KML contour parsing, DEM reconstruction, suitability evaluation, and D8 watershed catchment delineation.</li>
              <li><strong>OTLP Exporter:</strong> Batched traces exported to Jaeger All-In-One at <code>http://localhost:4318/v1/traces</code>.</li>
              <li><strong>Trace Propagation:</strong> W3C <code>traceparent</code> and custom <code>X-Trace-ID</code> returned in response headers.</li>
            </ul>
          </div>
          <div style="background: rgba(255,255,255,0.02); padding: 1.25rem; border-radius: 10px; border: 1px solid var(--card-border);">
            <h3 style="color: var(--success); margin-bottom: 0.5rem;">2. Application Metrics</h3>
            <ul style="color: var(--text-muted); font-size: 0.85rem; padding-left: 1.25rem; line-height: 1.6;">
              <li><strong>Prometheus Metric Reader:</strong> Metrics exposed natively at <code>/metrics</code> in Prometheus exposition format.</li>
              <li><strong>Domain Counters & Histograms:</strong> Counts parsed contours, pond candidates, catchment areas, and execution latency.</li>
              <li><strong>Active Request Gauges:</strong> Real-time concurrency tracking for heavy geospatial computations.</li>
            </ul>
          </div>
          <div style="background: rgba(255,255,255,0.02); padding: 1.25rem; border-radius: 10px; border: 1px solid var(--card-border);">
            <h3 style="color: var(--accent); margin-bottom: 0.5rem;">3. Correlated Logging</h3>
            <ul style="color: var(--text-muted); font-size: 0.85rem; padding-left: 1.25rem; line-height: 1.6;">
              <li><strong>Trace Context Injection:</strong> Python logging is injected with <code>otelTraceID</code> and <code>otelSpanID</code>.</li>
              <li><strong>Ring Buffer & File Storage:</strong> Correlated logs persisted to <code>storage/opentelemetry.log</code> and streamed live to this dashboard.</li>
            </ul>
          </div>
          <div style="background: rgba(255,255,255,0.02); padding: 1.25rem; border-radius: 10px; border: 1px solid var(--card-border);">
            <h3 style="color: var(--warning); margin-bottom: 0.5rem;">4. Visualization & Inspection</h3>
            <ul style="color: var(--text-muted); font-size: 0.85rem; padding-left: 1.25rem; line-height: 1.6;">
              <li><strong>Jaeger UI (/jaeger/ & Port 16686):</strong> Interactive timeline waterfalls, span drill-down, and dependency graphs proxied directly via FastAPI.</li>
              <li><strong>Observability Hub (Port 5240):</strong> Native in-app real-time dashboard for comprehensive VIVA and submission review.</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </main>

  <script>
    function switchTab(tabId) {
      document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      event.target.classList.add('active');
      document.getElementById(tabId).classList.add('active');
      if (tabId === 'tab-metrics') fetchMetricsPreview();
    }

    async function refreshData() {
      try {
        const [overviewRes, spansRes, logsRes] = await Promise.all([
          fetch('/api/telemetry/overview'),
          fetch('/api/telemetry/spans?limit=50'),
          fetch('/api/telemetry/logs?limit=100')
        ]);
        const overview = await overviewRes.json();
        const spans = await spansRes.json();
        const logs = await logsRes.json();

        document.getElementById('stat-spans').textContent = overview.total_captured_spans || 0;
        document.getElementById('stat-traces').textContent = overview.total_captured_traces || 0;
        document.getElementById('stat-logs').textContent = overview.total_captured_logs || 0;
        document.getElementById('stat-latency').textContent = (overview.average_span_latency_ms || 0) + ' ms';

        renderSpansTable(spans);
        renderLogsTable(logs);
      } catch (err) {
        console.error('Error fetching telemetry data:', err);
      }
    }

    function renderSpansTable(spans) {
      const tbody = document.getElementById('spans-tbody');
      if (!spans || spans.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color: var(--text-dim);">No spans recorded yet. Send an API request to generate traces!</td></tr>';
        return;
      }
      tbody.innerHTML = spans.map(s => {
        const isOk = s.status === 'OK' || s.status === 'UNSET';
        const jaegerLink = '/jaeger/trace/' + s.trace_id;
        return `<tr>
          <td style="font-weight:600; color:var(--text-main);">${escapeHtml(s.name)}</td>
          <td><span class="badge ${s.kind === 'SERVER' ? 'badge-post' : 'badge-get'}">${s.kind}</span></td>
          <td><a href="${jaegerLink}" target="_blank" class="trace-link mono">${s.trace_id.substring(0, 10)}...</a></td>
          <td class="mono">${s.span_id.substring(0, 8)}...</td>
          <td class="mono" style="color:var(--primary); font-weight:600;">${s.duration_ms} ms</td>
          <td><span class="badge ${isOk ? 'badge-ok' : 'badge-err'}">${s.status}</span></td>
          <td style="color:var(--text-muted); font-size:0.8rem;">${s.start_time}</td>
        </tr>`;
      }).join('');
    }

    function renderLogsTable(logs) {
      const tbody = document.getElementById('logs-tbody');
      if (!logs || logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-dim);">No logs captured yet.</td></tr>';
        return;
      }
      tbody.innerHTML = logs.map(l => {
        const isErr = l.level === 'ERROR';
        const isWarn = l.level === 'WARNING';
        const jaegerLink = l.trace_id ? 'http://localhost:16686/trace/' + l.trace_id : '#';
        return `<tr>
          <td style="color:var(--text-muted); font-size:0.8rem;">${l.timestamp}</td>
          <td><span class="badge ${isErr ? 'badge-err' : isWarn ? 'badge-get' : 'badge-ok'}">${l.level}</span></td>
          <td style="color:var(--accent); font-weight:500;">${escapeHtml(l.logger)}</td>
          <td>${l.trace_id ? `<a href="${jaegerLink}" target="_blank" class="trace-link mono">${l.trace_id.substring(0, 10)}...</a>` : '<span style="color:var(--text-dim);">-</span>'}</td>
          <td class="mono">${l.span_id ? l.span_id.substring(0, 8) + '...' : '<span style="color:var(--text-dim);">-</span>'}</td>
          <td style="color:var(--text-main); font-family:var(--font-mono); font-size:0.8rem;">${escapeHtml(l.message)}</td>
        </tr>`;
      }).join('');
    }

    async function fetchMetricsPreview() {
      try {
        const res = await fetch('/metrics');
        const text = await res.text();
        const filtered = text.split('\\n').filter(line => line.includes('village_pond_') || line.startsWith('# HELP village_pond_') || line.startsWith('# TYPE village_pond_')).join('\\n');
        document.getElementById('metrics-preview').textContent = filtered || text.slice(0, 2000);
      } catch (err) {
        document.getElementById('metrics-preview').textContent = 'Error fetching /metrics: ' + err;
      }
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // Initial load and periodic poll
    refreshData();
    setInterval(refreshData, 3000);
  </script>
</body>
</html>
"""
