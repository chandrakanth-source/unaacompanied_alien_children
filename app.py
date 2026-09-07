from fastapi import FastAPI

app = FastAPI(title="UAC Care Transition Analytics")


@app.get("/")
def health_check():
    return {"status": "ok", "service": "UAC Care Transition Analytics"}
