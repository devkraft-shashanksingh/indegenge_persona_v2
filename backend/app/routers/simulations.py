from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import schemas, crud
from ..database import get_db

router = APIRouter(
    prefix="/simulations",
    tags=["simulations"]
)

@router.get("/saved", response_model=List[schemas.SavedSimulation])
def list_saved_simulations(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all saved simulations.
    """
    return crud.get_saved_simulations(db, skip=skip, limit=limit)

@router.post("/save", response_model=schemas.SavedSimulation)
def save_simulation(
    simulation: schemas.SavedSimulationCreate,
    db: Session = Depends(get_db)
):
    """
    Save a simulation.
    """
    try:
        return crud.create_saved_simulation(db, simulation)
    except Exception as e:
        # Catch unique constraint violation or generic errors
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/saved/{simulation_id}", response_model=schemas.SavedSimulation)
def get_saved_simulation(
    simulation_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific saved simulation by ID.
    """
    simulation = crud.get_saved_simulation(db, simulation_id)
    if simulation is None:
        raise HTTPException(status_code=404, detail="Saved simulation not found")
    return simulation

@router.delete("/saved/{simulation_id}")
def delete_saved_simulation(
    simulation_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a saved simulation by ID.
    """
    success = crud.delete_saved_simulation(db, simulation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Saved simulation not found")
    return {"message": "Simulation deleted successfully"}
