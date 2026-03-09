from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routes import auth_routes, repo_routes, data_routes
from app.config import FRONTEND_URL

# Create all tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="GitHub Developer Metrics Dashboard")

# CORS — allow frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(auth_routes.router)
app.include_router(repo_routes.router)
app.include_router(data_routes.router)


@app.get("/")
def root():
    return {"message": "GitHub Metrics API is running"}
