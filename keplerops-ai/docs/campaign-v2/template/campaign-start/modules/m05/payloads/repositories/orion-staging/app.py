from fastapi import FastAPI

app = FastAPI(title="Orion staging inference")


@app.get("/health/ready")
def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.post("/v1/models/orion-release-risk:predict")
def predict(body: dict[str, object]) -> dict[str, object]:
    return {"predictions": [{"label": "review", "input": body}]}
