
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

from scheduler import schedule_charging, evaluate_schedule

app = FastAPI(title="Voltiva API", version="1.0")
# Temporary storage (will be replaced by PostgreSQL)
saved_requests = []

# Structure of a charging request
class ChargingRequest(BaseModel):
    household: str
    energy: float = Field(gt=0)
    power: float = Field(gt=0)
    deadline: int = Field(ge=19, le=30)


# Structure of the API input
class ScheduleInput(BaseModel):
    requests: list[ChargingRequest]
    capacity: float = Field(gt=0)
    strategy: Literal["fcfs", "edf", "greedy"] = "greedy"
    essential_demand: dict[int, float] = Field(default_factory=dict)


@app.get("/")
def home():
    return {"message": "Voltiva API is running"}


@app.post("/schedule")
def create_schedule(data: ScheduleInput):

    if any(
        hour < 18 or hour >= 30 or demand < 0
        for hour, demand in data.essential_demand.items()
    ):
        raise HTTPException(
            status_code=422,
            detail="Essential demand must be non-negative for hours 18–29"
        )

    requests = [
        request.model_dump()
        for request in data.requests
    ]

    result = schedule_charging(
        requests=requests,
        capacity=data.capacity,
        strategy=data.strategy,
        essential_demand=data.essential_demand
    )

    metrics = evaluate_schedule(result)

    return {
        "strategy": data.strategy,
        "schedule": result,
        "metrics": metrics
    }


@app.post("/requests", status_code=201)
def add_request(request: ChargingRequest):

    # Prevent duplicate household requests for now
    for saved in saved_requests:
        if saved["household"] == request.household:
            raise HTTPException(
                status_code=409,
                detail="Household already has a request"
            )

    saved_requests.append(request.model_dump())

    return {
        "message": "Charging request saved",
        "request": request.model_dump()
    }


@app.get("/requests")
def get_requests():
    return {
        "total": len(saved_requests),
        "requests": saved_requests
    }


@app.post("/schedule/saved")
def schedule_saved_requests(
    capacity: float = 20,
    strategy: Literal["fcfs", "edf", "greedy"] = "greedy"
):
    if capacity <= 0:
        raise HTTPException(
            status_code=422,
            detail="Capacity must be positive"
        )

    if not saved_requests:
        raise HTTPException(
            status_code=400,
            detail="No charging requests available"
        )

    result = schedule_charging(
        requests=saved_requests,
        capacity=capacity,
        strategy=strategy
    )

    return {
        "strategy": strategy,
        "schedule": result,
        "metrics": evaluate_schedule(result)
    }
