from fastapi import FastAPI


app = FastAPI(title="Job Agent Backend")


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}

