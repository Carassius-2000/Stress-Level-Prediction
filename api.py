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
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.staticfiles import StaticFiles
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
    environment_variables: dict[str, str] = dotenv_values()
    db_username: str = environment_variables["DB_USERNAME"]
    db_password: str = environment_variables["DB_PASSWORD"]
    return db_username, db_password


db_username: str
db_password: str
db_username, db_password = get_database_credentials()
DATABASE_URL: str = (
    f"postgresql+asyncpg://{db_username}:{db_password}@localhost/antistress"
)
database: Database = Database(DATABASE_URL)


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


app: FastAPI = FastAPI(
    title="Stress Level Prediction",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html() -> str:
    """
    Serves custom Swagger UI HTML page.

    Returns
    ----------
        str: HTML content of custom Swagger UI page.
    """
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
    )


@app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
async def swagger_ui_redirect() -> str:
    """
    Redirects user to Swagger UI OAuth2 redirect page.

    Returns
    ----------
        str: HTML content of Swagger UI OAuth2 redirect page.
    """
    return get_swagger_ui_oauth2_redirect_html()


@app.get("/redoc", include_in_schema=False)
async def redoc_html() -> str:
    """
    Retrieves HTML content for the ReDoc documentation page.

    Returns
    ----------
        str: HTML content of the ReDoc documentation page.
    """
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="/static/redoc.standalone.js",
    )


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
    values: dict[str, str | int | bool] = worker.dict()
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
    values: dict[str, str | int | bool] = worker.dict()
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
    values: dict[str, str] = worker.dict()
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
    X: pd.DataFrame = pd.DataFrame([parse_features(worker)], dtype="int8")
    prediction: str = get_prediction(X)
    worker_prediction: WorkerWithPrediction = WorkerWithPrediction(
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
    values: dict[str, str | bool] = worker.dict()
    try:
        await database.execute(query=query, values=values)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Не удалось добавить работника")
    result: dict[str, str] = {
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
    values: dict[str, str] = worker.dict()
    try:
        await database.execute(query=query, values=values)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Не удалось удалить работника")
    result: dict[str, str] = {
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
