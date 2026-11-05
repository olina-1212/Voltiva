
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from database import engine
from models import ChargingRequestDB, EssentialDemandDB

from scheduler import schedule_charging, evaluate_schedule

import time
from optimizer import optimize_schedule


app = FastAPI(title="Voltiva API", version="1.0")


# Input models

class ChargingRequest(BaseModel):
    household: str = Field(min_length=1, max_length=50)
    energy: float = Field(gt=0)
    power: float = Field(gt=0)
    deadline: int = Field(ge=19, le=30)

class EssentialDemandInput(BaseModel):
    hour: int = Field(ge=18, le=29)
    demand: float = Field(ge=0)


class ScheduleInput(BaseModel):
    requests: list[ChargingRequest]
    capacity: float = Field(gt=0)
    strategy: Literal["fcfs", "edf", "greedy", "ortools"] = "greedy"
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


def run_scheduler(requests, capacity, strategy, essential_demand):

    start_time = time.perf_counter()

    if strategy == "ortools":
        result = optimize_schedule(
            requests=requests,
            capacity=capacity,
            essential_demand=essential_demand
        )

        schedule = result["schedule"]
        metrics = result["metrics"]
        status = result["status"]

    else:
        schedule = schedule_charging(
            requests=requests,
            capacity=capacity,
            strategy=strategy,
            essential_demand=essential_demand
        )

        metrics = evaluate_schedule(schedule)
        status = "completed"

    execution_time = (time.perf_counter() - start_time) * 1000

    return {
        "strategy": strategy,
        "status": status,
        "schedule": schedule,
        "metrics": metrics,
        "execution_time_ms": round(execution_time, 3)
    }

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

    if len({
        request.household
        for request in data.requests
    }) != len(data.requests):
        raise HTTPException(
            status_code=422,
            detail="Duplicate household identifiers"
        )

    requests = [
        request.model_dump()
        for request in data.requests
    ]

    if any(
        demand > data.capacity
        for demand in data.essential_demand.values()
    ):
        raise HTTPException(
            status_code=422,
            detail="Essential demand exceeds capacity"
        )

    if data.strategy == "ortools":
        for request in requests:
            if abs(
                request["energy"] / request["power"]
                - round(request["energy"] / request["power"])
            ) > 1e-9:
                raise HTTPException(
                    status_code=422,
                    detail="OR-Tools requires energy to be a multiple of power"
                )

    return run_scheduler(
        requests=requests,
        capacity=data.capacity,
        strategy=data.strategy,
        essential_demand=data.essential_demand
    )



# Schedule requests stored in PostgreSQL


@app.post("/schedule/saved")
def schedule_saved_requests(
    capacity: float = 20,
    strategy: Literal[
        "fcfs", "edf", "greedy", "ortools"
    ] = "greedy"
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

        demand_records = session.scalars(
            select(EssentialDemandDB)
        ).all()

        essential_demand = {
            record.hour: record.demand
            for record in demand_records
        }

    if not requests:
        raise HTTPException(
            status_code=400,
            detail="No charging requests available"
        )

    missing_hours = [
        hour for hour in range(18, 30)
        if hour not in essential_demand
    ]

    if missing_hours:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Essential demand data is incomplete",
                "missing_hours": missing_hours
            }
        )

    if any(
        demand > capacity
        for demand in essential_demand.values()
    ):
        raise HTTPException(
            status_code=400,
            detail="Essential demand exceeds community capacity"
        )

    if strategy == "ortools":
        for request in requests:
            if abs(
                request["energy"] / request["power"]
                - round(request["energy"] / request["power"])
            ) > 1e-9:
                raise HTTPException(
                    status_code=422,
                    detail="OR-Tools requires energy to be a multiple of power"
                )

    return run_scheduler(
        requests=requests,
        capacity=capacity,
        strategy=strategy,
        essential_demand=essential_demand
    )


@app.post("/essential-demand")
def save_essential_demand(data: EssentialDemandInput):

    with Session(engine) as session:

        existing = session.get(
            EssentialDemandDB,
            data.hour
        )

        if existing:
            existing.demand = data.demand

        else:
            new_demand = EssentialDemandDB(
                hour=data.hour,
                demand=data.demand
            )
            session.add(new_demand)

        session.commit()

    return {
        "message": "Essential demand saved",
        "hour": data.hour,
        "demand": data.demand
    }


@app.get("/essential-demand")
def get_essential_demand():

    with Session(engine) as session:

        records = session.scalars(
            select(EssentialDemandDB)
        ).all()

        return {
            str(record.hour): record.demand
            for record in records
        }
