# Demo Run Commands

Run the React + FastAPI application from the project root in two terminals.

## 1. Start the FastAPI backend

In Terminal 1 (PowerShell), run from the outer project folder:

```powershell
cd "C:\Users\shivr\Downloads\BDA project"
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.app.main:app --app-dir "C:\Users\shivr\Downloads\BDA project\BDA project" --reload --port 8000
```

If the project virtual environment does not exist yet, create and prepare it from the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r ".\BDA project\requirements.txt"
```

Check the backend health endpoint in another terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

Expected response:

```text
status
------
ok
```

## 2. Start the React frontend

In Terminal 2:

```powershell
Set-Location "C:\Users\shivr\Downloads\BDA project\BDA project\frontend"
npm install
npm run dev
```

Open the Vite URL printed in the terminal (normally `http://localhost:5173/`).
Keep both terminals running while using the application.

The API documentation is available at `http://localhost:8000/docs`.

## 3. Demo flow

1. Enter **Koramangala** as the start and **Whitefield** as the destination.
2. Select the real Nominatim autocomplete suggestions, then click **Find Routes**.
3. Compare available OSRM routes and view their road-network distance, estimated duration, and map geometry.
4. Scroll to **Historical Traffic Intelligence** and select a historical corridor.
5. Review its historical metrics and persisted advisory, including the historical-data disclaimer.

Route estimates are based on the OSRM road network and are not live traffic. Historical corridor
metrics and advisories are not matched to the selected route.
