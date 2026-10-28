
import json
import time

from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal, QueryHistory
from gis_data import LAYER_FILES, load_layer
from query_planner import plan_query
from qwen_service import check_qwen_connection
from spatial_query import execute_query_plan


# --------------------------------------------------
# Configuration
# --------------------------------------------------

load_dotenv(Path(__file__).resolve().parent / ".env")

app = FastAPI(
    title="GeoAsk",
    description="Natural-language GIS query and visualization API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Database dependency
# --------------------------------------------------

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# --------------------------------------------------
# Request model
# --------------------------------------------------

class QueryRequest(BaseModel):
    query: str


# --------------------------------------------------
# General endpoints
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "message": "GeoAsk-Thodupuzha API is running"
    }


@app.get("/api/ai/health")
def qwen_health():
    try:
        return check_qwen_connection()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not check Qwen connection: {exc}",
        )


# --------------------------------------------------
# GIS layer endpoints
# --------------------------------------------------

@app.get("/api/layers")
def get_layers():
    """
    Return available GIS layers with feature counts.

    Each successful layer contains:
    - name
    - feature_count

    Failed layers contain an error field.
    """

    layers = []

    for layer_name in LAYER_FILES.keys():
        try:
            gdf = load_layer(layer_name)

            # Count features in the loaded layer.
            layers.append({
                "name": layer_name,
                "feature_count": len(gdf),
            })

        except Exception as exc:
            layers.append({
                "name": layer_name,
                "feature_count": 0,
                "error": str(exc),
            })

    return {
        "layers": layers
    }


@app.get("/api/layers/{layer_name}")
def get_layer_data(layer_name: str):
    """Return one GIS layer as GeoJSON in WGS84 coordinates."""

    if layer_name not in LAYER_FILES:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown GIS layer: {layer_name}",
        )

    try:
        gdf = load_layer(layer_name)

        # Leaflet expects geographic coordinates.
        if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)

        # Remove missing and empty geometries.
        gdf = gdf[
            gdf.geometry.notna()
            & ~gdf.geometry.is_empty
        ].copy()

        geojson = json.loads(gdf.to_json())

        return jsonable_encoder(geojson)

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not load GIS layer '{layer_name}': {exc}",
        )


# --------------------------------------------------
# Query history endpoint
# --------------------------------------------------

@app.get("/api/history")
def get_query_history(
    db: Session = Depends(get_db),
):
    """Return the 50 most recent GIS queries."""

    try:
        records = (
            db.query(QueryHistory)
            .order_by(QueryHistory.id.desc())
            .limit(50)
            .all()
        )

        return [
            {
                "id": record.id,
                "query_text": record.query_text,
                "status": record.status,
            }
            for record in records
        ]

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not retrieve query history: {exc}",
        )


# --------------------------------------------------
# Natural-language GIS query endpoint
# --------------------------------------------------

@app.post("/api/query")
def process_query(
    req: QueryRequest,
    db: Session = Depends(get_db),
):
    """Plan and execute a natural-language GIS query."""

    query = req.query.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Please enter a GIS query.",
        )

    try:
        # Interpret the user's natural-language query.
        plan = plan_query(query)

        # Execute the query using the existing GIS query engine.
        result = execute_query_plan(plan)

        # Save the query execution status.
        history_status = (
            "Completed"
            if isinstance(result, dict)
            and result.get("status") == "success"
            else "Failed"
        )

        history = QueryHistory(
            query_text=query,
            status=history_status,
        )

        db.add(history)
        db.commit()

        return jsonable_encoder(result)

    except HTTPException:
        db.rollback()
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Could not process GIS query: {exc}",
        )
