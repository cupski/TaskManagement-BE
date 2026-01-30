from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import time

from app.config import settings
from app.database import init_db, close_db
from app.routers import auth, users, tasks


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(" Starting Task Management API...")
    print(f" Debug mode: {settings.DEBUG}")
    print(f" JWT Algorithm: {settings.ALGORITHM}")
    
    # Initialize database
    try:
        await init_db()
        print(" Database initialized successfully")
    except Exception as e:
        print(f" Database initialization failed: {e}")
    
    yield
    
    # Shutdown
    print("👋 Shutting down Task Management API...")
    await close_db()
    print("✅ Database connections closed")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add X-Process-Time header to responses"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(round(process_time, 3))
    return response


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    errors = {}
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        errors[field] = error["msg"]
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "Validation error",
            "detail": {"field_errors": errors}
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    if settings.DEBUG:
        import traceback
        error_detail = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc()
        }
    else:
        error_detail = {"message": "Internal server error"}
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": error_detail
        }
    )


app.include_router(auth.router, prefix=f"/api/{settings.API_VERSION}")
app.include_router(users.router, prefix=f"/api/{settings.API_VERSION}")
app.include_router(tasks.router, prefix=f"/api/{settings.API_VERSION}")


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint - API information
    """
    return {
        "success": True,
        "data": {
            "name": settings.APP_NAME,
            "version": settings.API_VERSION,
            "status": "running",
            "docs": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json"
        },
        "message": "Task Management API is running"
    }



if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        log_level="info"
    )
