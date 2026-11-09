
from pathlib import Path
from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from travel_assistant import agent

app = FastAPI(
    title="AI Travel Assistant",
    description="An AI-powered travel planning application",
    version="1.0.0"
)

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"


class TravelRequest(BaseModel):
    query: str
    departure_date: date
    return_date: date


@app.get("/")
def home():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/plan-trip")
def plan_trip(request: TravelRequest):

    if request.return_date < request.departure_date:
        raise HTTPException(
            status_code=400,
            detail="Return date cannot be before departure date."
        )

    trip_query = (
        f"{request.query}\n"
        f"Departure date: {request.departure_date}\n"
        f"Return date: {request.return_date}\n"
        f"Plan the itinerary specifically for these dates."
    )

    response = agent(trip_query)

    return {
        "query": request.query,
        "departure_date": str(request.departure_date),
        "return_date": str(request.return_date),
        "travel_plan": str(response)
    }
