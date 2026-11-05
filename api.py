
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from database import engine
from models import ChargingRequestDB

from scheduler import schedule_charging, evaluate_schedule


app = FastAPI(title="Voltiva API", version="1.0")


# Input models

class ChargingRequest(BaseModel):
    household: str = Field(min_length=1, max_length=50)
    energy: float = Field(gt=0)
    power: float = Field(gt=0)
    deadline: int = Field(ge=19, le=30)


class ScheduleInput(BaseModel):
    requests: list[ChargingRequest]
    capacity: float = Field(gt=0)
    strategy: Literal["fcfs", "edf", "greedy"] = "greedy"
    essential_demand: dict[int, float] = Field(default_factory=dict)


# Helper: convert database row into scheduler input

def request_to_dict(request):
    return {
        "household": request.household,
        "energy": request.energy,
        "power": request.power,
        "deadline": request.deadline
    }


# Helper: validate essential demand

def validate_essential_demand(demand):
    if any(
        hour < 18 or hour >= 30 or value < 0
        for hour, value in demand.items()
    ):
        raise HTTPException(
            status_code=422,
            detail="Essential demand must be non-negative for hours 18-29"
        )


# Home endpoint

@app.get("/")
def home():
    return {"message": "Voltiva API is running"}


# Save a request in PostgreSQL

@app.post("/requests", status_code=201)
def add_request(request: ChargingRequest):

    with Session(engine) as session:

        new_request = ChargingRequestDB(
            household=request.household,
            energy=request.energy,
            power=request.power,
            deadline=request.deadline
        )

        session.add(new_request)

        try:
            session.commit()
            session.refresh(new_request)

        except IntegrityError:
            session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Household already has a request"
            )

        return {
            "message": "Charging request saved",
            "id": new_request.id,
            "request": request_to_dict(new_request)
        }


# Retrieve requests from PostgreSQL

@app.get("/requests")
def get_requests():

    with Session(engine) as session:

        requests = session.scalars(
            select(ChargingRequestDB).order_by(
                ChargingRequestDB.id
            )
        ).all()

        return {
            "total": len(requests),
            "requests": [
                {
                    "id": request.id,
                    **request_to_dict(request)
                }
                for request in requests
            ]
        }


# Schedule directly supplied requests (old endpoint)

@app.post("/schedule")
def create_schedule(data: ScheduleInput):

    validate_essential_demand(data.essential_demand)

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

    return {
        "strategy": data.strategy,
        "schedule": result,
        "metrics": evaluate_schedule(result)
    }


# Schedule requests stored in PostgreSQL

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

    with Session(engine) as session:

        stored_requests = session.scalars(
            select(ChargingRequestDB).order_by(
                ChargingRequestDB.id
            )
        ).all()

        requests = [
            request_to_dict(request)
            for request in stored_requests
        ]

    if not requests:
        raise HTTPException(
            status_code=400,
            detail="No charging requests available"
        )

    result = schedule_charging(
        requests=requests,
        capacity=capacity,
        strategy=strategy
    )

    return {
        "strategy": strategy,
        "schedule": result,
        "metrics": evaluate_schedule(result)
    }
