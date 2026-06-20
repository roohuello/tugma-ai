from fastapi import FastAPI

app = FastAPI(title="tugma-ai", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok"}
