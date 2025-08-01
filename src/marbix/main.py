from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from marbix.api.v1 import api_router as main_router
import os

load_dotenv(dotenv_path=os.path.join(os.getcwd(), ".env"))


app = FastAPI(
    title="Marbix API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/")
async def root():
    return {"message": "Marbix API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
    
app.include_router(main_router)





