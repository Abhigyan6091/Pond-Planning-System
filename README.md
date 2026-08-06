# TERRAIN ANALYZER 🏔️💧

> High-Precision GIS Terrain Analysis Platform powered by OpenZenith GLO-30 DEMs, Fast Marching Contours, D8 Hydrological Flow, Priority-Flood Pond Storage Estimation, and Interactive 3D Surface Rendering.

---

## 🌟 Features Overview

- **Interactive ROI Selection**: Map Point (with adjustable radius), Bounding Box, or Polygon ROI selection.
- **OpenZenith DEM Pipeline**: Fetches 30m resolution Copernicus (GLO-30) Digital Elevation Models on-the-fly.
- **Marching Squares Contour Generation**: Fast contour polyline extraction at customizable intervals (10m, 20m, 50m, 100m) with polyline length (m/km), vertex count, and enclosed area (m²/km² via Shoelace formula).
- **Slope & Aspect Engine**: Finite difference gradient field calculation producing interactive YlOrRd slope heatmap overlays.
- **D8 Water Flow & Droplet Simulation**: Traces downhill flow paths step-by-step from any clicked starting location with real-time animated droplet visualization.
- **Watershed Catchment Delineation**: Priority-queue BFS upstream traversal from selected stream outlets computing total catchment area (km²), perimeter (km), and average slope (°).
- **Pond Depth & Storage Volume**: Priority-Flood sink filling algorithm detecting terrain depressions with 3D horizontal layer trapezoidal volume integration.
- **Elevation Profile Transect**: Interactive line transect sampling using sub-pixel bilinear interpolation, displaying elevation gain/loss metrics and interactive Plotly distance vs. elevation charts.
- **3D Terrain Surface Engine**: Full 3D surface mesh visualization with camera orbit controls and dynamic color scale selection.
- **Data Exporting**: One-click download of Contours as GeoJSON / CSV, and Elevation Profiles as CSV.

---

## 📐 Mathematical Foundations

### 1. Contour Generation (Marching Squares)
Each grid cell formed by 4 neighboring DEM elevation values $[E_{00}, E_{01}, E_{10}, E_{11}]$ is classified against a target elevation threshold $C$. Each vertex produces a 1-bit binary flag:
$$
b_i = \begin{cases} 1 & \text{if } E_i \ge C \\ 0 & \text{if } E_i < C \end{cases}
$$
The 4-bit index $k = \sum_{i=0}^3 b_i 2^i \in [0, 15]$ indexes a lookup table to place interpolated contour line segment endpoints along cell edges via linear interpolation:
$$
t = \frac{C - E_A}{E_B - E_A} \implies P = (1 - t)P_A + t P_B
$$

### 2. Polyline Enclosed Area (Shoelace Formula)
For closed contour polylines with vertices $(x_1, y_1), (x_2, y_2), \dots, (x_n, y_n)$:
$$
\text{Area} = \frac{1}{2} \left| \sum_{i=1}^{n-1} (x_i y_{i+1} - x_{i+1} y_i) + (x_n y_1 - x_1 y_n) \right|
$$

### 3. Slope & Aspect Field
Local elevation gradients $\frac{\partial E}{\partial x}$ and $\frac{\partial E}{\partial y}$ are computed using central finite differences:
$$
\text{Slope (radians)} = \arctan \sqrt{\left(\frac{\partial E}{\partial x}\right)^2 + \left(\frac{\partial E}{\partial y}\right)^2} \implies \text{Slope (°)} = \text{Slope (rad)} \times \frac{180}{\pi}
$$
$$
\text{Aspect (radians)} = \text{atan2}\left(-\frac{\partial E}{\partial x}, \frac{\partial E}{\partial y}\right)
$$

### 4. D8 Flow Direction Matrix
Each cell flows to its neighbor in the $3 \times 3$ neighborhood that maximizes the downward slope:
$$
\text{Drop}_{i,j} = \frac{E_{\text{center}} - E_{i,j}}{\text{Distance}_{i,j}}
$$

### 5. Pond Storage Volume (Trapezoidal Layer Integration)
Depression sinks filled via Priority-Flood (Wang & Liu 2006). For each cell in a labeled depression:
$$
V_{\text{total}} = \sum_{(r,c) \in \text{Pond}} \max(0, E_{\text{water\_level}} - E_{r,c}) \times A_{\text{pixel}}
$$

---

## 🛠️ Technology Stack

- **Backend**: Python 3.12, FastAPI, NumPy, SciPy, Rasterio, Pillow, OpenCV, Pydantic.
- **Frontend**: React 18, Vite, TypeScript, Tailwind CSS, Leaflet, React-Leaflet, Plotly.js, Lucide-React.
- **Packaging**: Docker, Docker Compose.

---

## 🚀 Quick Start (Local Setup)

### Prerequisites
- Python 3.10+
- Node.js 18+

### 1. Clone & Setup Backend
```bash
# Navigate to project root
cd Contour

# Install Python dependencies
pip install -r requirements.txt

# Launch FastAPI server
python -m uvicorn backend.main:app --port 8000 --host 0.0.0.0
```
Backend API interactive docs: `http://localhost:8000/docs`

### 2. Setup & Launch Frontend
```bash
cd frontend

# Install Node dependencies
npm install

# Start Vite dev server
npm run dev
```
Open browser at: `http://localhost:3000`

---

## 🐳 Docker Deployment

To build and run the entire platform in a single container:

```bash
docker-compose up --build
```
Access application at `http://localhost:8000`

---

## 📡 API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/dem/download-dem` | Fetches DEM raster data for point, rect, or polygon ROI |
| `POST` | `/api/contours/generate-contours` | Runs Marching Squares contour polyline extraction |
| `POST` | `/api/terrain/slope` | Computes slope heatmap PNG overlay |
| `POST` | `/api/hydrology/flow-droplet` | Traces D8 steepest descent water droplet path |
| `POST` | `/api/hydrology/watershed` | Delineates upstream watershed catchment polygon |
| `POST` | `/api/analysis/pond` | Calculates pond depth & storage volume via Priority-Flood |
| `POST` | `/api/analysis/elevation-profile` | Samples DEM along transect line using bilinear interpolation |
| `POST` | `/api/analysis/terrain-3d` | Generates 3D surface mesh for Plotly rendering |
| `POST` | `/api/export/contours/geojson` | Downloads contours as standard GeoJSON |
| `POST` | `/api/export/contours/csv` | Downloads contour statistics table as CSV |
| `POST` | `/api/export/profile/csv` | Downloads elevation profile transect points as CSV |

---

## 📜 License
MIT License. Built for advanced GIS and hydrology analysis.
