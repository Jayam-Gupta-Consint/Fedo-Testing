from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import json
import logging
from pathlib import Path
import sqlite3
from contextlib import contextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('callback_logs.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Fedo Callback Service",
    description="Service to receive and store Fedo scan callback results",
    version="1.0.0"
)

# Database setup
DB_PATH = "fedo_callbacks.db"

def init_db():
    """Initialize SQLite database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS callbacks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT,
            scan_id TEXT,
            timestamp TEXT,
            status TEXT,
            callback_data TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# Initialize database on startup
init_db()

# Pydantic models
class CallbackData(BaseModel):
    customerID: str
    scanID: str
    status: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None

class CallbackResponse(BaseModel):
    success: bool
    message: str
    received_at: str

@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    logger.info("Fedo Callback Service started")
    init_db()

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Fedo Callback Service",
        "status": "running",
        "endpoints": {
            "callback": "/consint/demo-callback",
            "health": "/health",
            "results": "/results",
            "results_by_customer": "/results/{customer_id}"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/consint/demo-callback", response_model=CallbackResponse)
async def receive_callback(request: Request, callback_data: CallbackData):
    """
    Receive and store callback results from Fedo scan
    """
    try:
        received_at = datetime.utcnow().isoformat()
        
        # Log the incoming request
        logger.info(f"Received callback for Customer: {callback_data.customerID}, Scan: {callback_data.scanID}")
        logger.info(f"Callback data: {callback_data.model_dump_json()}")
        
        # Store in database
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO callbacks 
                (customer_id, scan_id, timestamp, status, callback_data, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                callback_data.customerID,
                callback_data.scanID,
                callback_data.timestamp or received_at,
                callback_data.status or "received",
                callback_data.model_dump_json(),
                received_at
            ))
            conn.commit()
            
        # Also save to JSON file as backup
        log_file = Path("callback_results.json")
        results = []
        if log_file.exists():
            with open(log_file, 'r') as f:
                results = json.load(f)
        
        results.append({
            "received_at": received_at,
            **callback_data.model_dump()
        })
        
        with open(log_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Successfully stored callback for {callback_data.customerID}")
        
        return CallbackResponse(
            success=True,
            message="Callback received and stored successfully",
            received_at=received_at
        )
        
    except Exception as e:
        logger.error(f"Error processing callback: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing callback: {str(e)}")

@app.get("/results")
async def get_all_results(limit: int = 100, offset: int = 0):
    """
    Retrieve all stored callback results with pagination
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM callbacks 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, (limit, offset))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "id": row["id"],
                    "customer_id": row["customer_id"],
                    "scan_id": row["scan_id"],
                    "timestamp": row["timestamp"],
                    "status": row["status"],
                    "callback_data": json.loads(row["callback_data"]),
                    "created_at": row["created_at"]
                })
            
            # Get total count
            cursor.execute("SELECT COUNT(*) as count FROM callbacks")
            total = cursor.fetchone()["count"]
            
            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "results": results
            }
    except Exception as e:
        logger.error(f"Error retrieving results: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving results: {str(e)}")

@app.get("/results/{customer_id}")
async def get_results_by_customer(customer_id: str):
    """
    Retrieve callback results for a specific customer
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM callbacks 
                WHERE customer_id = ? 
                ORDER BY created_at DESC
            """, (customer_id,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "id": row["id"],
                    "customer_id": row["customer_id"],
                    "scan_id": row["scan_id"],
                    "timestamp": row["timestamp"],
                    "status": row["status"],
                    "callback_data": json.loads(row["callback_data"]),
                    "created_at": row["created_at"]
                })
            
            if not results:
                raise HTTPException(status_code=404, detail=f"No results found for customer {customer_id}")
            
            return {
                "customer_id": customer_id,
                "total_scans": len(results),
                "results": results
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving results for customer {customer_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving results: {str(e)}")

@app.delete("/results/{callback_id}")
async def delete_result(callback_id: int):
    """
    Delete a specific callback result
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM callbacks WHERE id = ?", (callback_id,))
            conn.commit()
            
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"Result with ID {callback_id} not found")
            
            return {"success": True, "message": f"Result {callback_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting result {callback_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting result: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)