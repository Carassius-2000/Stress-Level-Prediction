from contextlib import asynccontextmanager
from functools import lru_cache

from dotenv import dotenv_values
from pydantic_models import (
    WorkerWithHistory,
    WorkerBase,
    WorkerWithPrediction,
    WorkerWithFeatures,
)
from fastapi import FastAPI, HTTPException
from databases import Database
import uvicorn
import joblib
import pandas as pd


@lru_cache
def get_database_credentials() -> tuple[str, str]:
    """
    Retrieves database credentials from environment variables.

    Returns
    ----------
        A tuple containing database username and password.
    """
    environment_variables = dotenv_values()
    db_username = environment_variables["DB_USERNAME"]
    db_password = environment_variables["DB_PASSWORD"]
    return db_username, db_password


db_username, db_password = get_database_credentials()
DATABASE_URL: str = (
    f"postgresql+asyncpg://{db_username}:{db_password}@localhost/antistress"
)
database = Database(DATABASE_URL)


@asynccontextmanager
async def lifespan(app: FastAPI) -> None:
    """
    Asynchronous context manager that handles lifespan of FastAPI application.

    Parameters
    ----------
        app (FastAPI): FastAPI application instance.
    """
    await database.connect()
    yield
    await database.disconnect()


app = FastAPI(title="Stress Level Prediction", version="1.0.0", lifespan=lifespan)


def get_prediction(data) -> str:
    """
    Predicts stress level based on given data using a pre-trained model.

    Parameters
    ----------
        data (array-like): Input data to make a prediction on.

    Returns
    ----------
        str: Predicted stress level.
    """
    model = joblib.load("prediction.model")
    prediction = model.predict(data)
    STRESS_LEVEL: list[str] = [
        "Низкий уровень стресса",
        "Средний уровень стресса",
        "Высокий уровень стресса",
    ]
    return STRESS_LEVEL[prediction[0]]


def parse_features(worker: WorkerWithFeatures) -> dict[str, int]:
    """
    Parses worker's features.

    Parameters
    ----------
        worker (WorkerWithFeatures): Pydantic worker object containing features.

    Returns
    ----------
        dict[str, int]: Parsed features, where keys are feature names \
            and values are corresponding integer values.
    """
    values = worker.dict()
    excluded: list[str] = ["first_name", "last_name", "surname", "info_date"]
    features: dict[str, int] = {
        key: int(value) for key, value in values.items() if key not in excluded
    }
    return features


async def save_features(worker: WorkerWithFeatures) -> None:
    """
    Saves worker's features to database.

    Parameters
    ----------
        worker (WorkerWithFeatures): Pydantic worker object containing features.

    Raises
    ----------
        HTTPException: If there is an error while executing database query.
    """
    values = worker.dict()
    del values["mental_health_history"]
    query: str = (
        "CALL save_features(:first_name, :last_name, :surname, :info_date, \
        :anxiety, :self_esteem, :depression, :headache, :blood_pressure,\
        :sleep_quality, :breathing_problem, :noise_level, :social_support,\
        :extracurricular_activities);"
    )
    try:
        await database.execute(query=query, values=values)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Не удалось сохранить показатели работника"
        )


async def save_prediction(worker: WorkerWithPrediction) -> None:
    """
    Saves worker's prediction to database.

    Parameters
    ----------
        worker (WorkerWithPrediction): Pydantic worker object containing prediction.

    Raises
    ----------
        HTTPException: If there is an error while executing database query.
    """
    query: str = (
        "CALL save_prediction(:first_name, :last_name, :surname, :stress_level);"
    )
    values = worker.dict()
    try:
        await database.execute(query=query, values=values)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Не удалось сохранить прогноз")


@app.post("/worker_stress_level/", response_model=WorkerWithPrediction)
async def get_worker_stress_level(worker: WorkerWithFeatures) -> dict[str, str]:
    """
    Retrieves worker's stress level based on their features.

    Parameters
    ----------
        worker (WorkerWithFeatures): Pydantic worker object containing features.

    Returns
    ----------
        dict[str, str]: Worker's first name, last name, surname and predicted stress level.
    """
    await save_features(worker)
    X = pd.DataFrame([parse_features(worker)], dtype="int8")
    prediction: str = get_prediction(X)
    worker_prediction = WorkerWithPrediction(
        first_name=worker.first_name,
        last_name=worker.last_name,
        surname=worker.surname,
        stress_level=prediction,
    )
    await save_prediction(worker_prediction)
    return worker_prediction


@app.post("/create_worker/")
async def create_worker(worker: WorkerWithHistory, status_code=201) -> dict[str, str]:
    """
    Creates new worker in database.

    Parameters
    ----------
        worker (WorkerWithHistory): Pydantic worker object containing mental health history.

    Returns
    ----------
        dict[str, str]: Success message with worker's first name and last name.

    Raises
    ----------
        HTTPException: If there was an error executing database query.
    """
    query: str = (
        "CALL add_worker(:first_name, :last_name, :surname, :mental_health_history);"
    )
    values = worker.dict()
    try:
        await database.execute(query=query, values=values)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Не удалось добавить работника")
    result = {
        "message": f"Работник {worker.first_name} {worker.last_name} был успешно добавлен"
    }
    return result


@app.delete("/delete_worker/")
async def delete_worker(worker: WorkerBase) -> dict[str, str]:
    """
    Deletes worker from database.

    Parameters
    ----------
        worker (WorkerBase): Worker object to be deleted.

    Returns
    ----------
        dict[str, str]: Success message with worker's first name and last name.

    Raises
    ----------
        HTTPException: If there is an error executing database query.
    """
    query: str = "CALL delete_worker(:first_name, :last_name, :surname);"
    values = worker.dict()
    try:
        await database.execute(query=query, values=values)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Не удалось удалить работника")
    result = {
        "message": f"Работник {worker.first_name} {worker.last_name} был успешно удален"
    }
    return result


@app.get("/")
async def root() -> dict[str, str]:
    """
    Main endpoint.
    """
    return {"message": "Сервер запущен"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
