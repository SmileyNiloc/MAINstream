from fastapi import FastAPI, Request, WebSocket  # pyright: ignore[reportMissingImports]
from fastapi.middleware.cors import (
    CORSMiddleware,
)

app = FastAPI()

# List of origins that are allowed to make requests
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/hello")
def hello():
    return {"message": "Hello, World!"}


@app.get("/")
def root():
    return {"message": "Welcome to the CradleWave API"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5000)
