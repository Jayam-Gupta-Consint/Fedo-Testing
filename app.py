from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
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

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with HTML interface"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Fedo Callback Service</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            h1 { color: #2c3e50; }
            .endpoint { background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; }
            .method { color: #28a745; font-weight: bold; }
            .post { color: #007bff; }
            .get { color: #28a745; }
            .delete { color: #dc3545; }
            a { color: #007bff; text-decoration: none; }
            a:hover { text-decoration: underline; }
            code { background: #e9ecef; padding: 2px 6px; border-radius: 3px; }
        </style>
    </head>
    <body>
        <h1>🏥 Fedo Callback Service</h1>
        <p><strong>Status:</strong> ✅ Running</p>
        
        <h2>📡 API Endpoints</h2>
        
        <div class="endpoint">
            <span class="method post">POST</span> <code>/consint/demo-callback</code>
            <p>Main callback endpoint to receive Fedo scan results</p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span> <a href="/results"><code>/results</code></a>
            <p>View all callback results (with pagination)</p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span> <code>/results/{customer_id}</code>
            <p>View results for specific customer</p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span> <a href="/health"><code>/health</code></a>
            <p>Health check endpoint</p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span> <a href="/docs"><code>/docs</code></a>
            <p>Interactive API documentation (Swagger UI)</p>
        </div>
        
        <div class="endpoint">
            <span class="method delete">DELETE</span> <code>/results/{callback_id}</code>
            <p>Delete a specific callback result</p>
        </div>
        
        <hr>
        <p><small>Fedo Testing Service v1.0.0</small></p>
    </body>
    </html>
    """
    return html_content

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Fedo Callback Service",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "callback": "/consint/demo-callback (POST only)",
            "results": "/results",
            "docs": "/docs"
        }
    }

# Handle GET requests to callback endpoint (informational only)
@app.get("/consint/demo-callback")
async def callback_info():
    """
    Information endpoint for callback URL
    This endpoint only accepts POST requests for actual callbacks
    """
    return {
        "message": "This endpoint accepts POST requests only",
        "method": "POST",
        "endpoint": "/consint/demo-callback",
        "expected_payload": {
            "customerID": "string",
            "scanID": "string",
            "status": "string (optional)",
            "data": "object (optional)",
            "metadata": "object (optional)",
            "timestamp": "string (optional)"
        },
        "example": {
            "customerID": "CUST_12345",
            "scanID": "SCN_001",
            "status": "completed",
            "data": {"heartRate": 75, "spo2": 98},
            "metadata": {"age": 35, "gender": "male"}
        }
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

@app.get("/results", response_class=HTMLResponse)
async def get_all_results_html(request: Request, limit: int = 100, offset: int = 0):
    """
    Retrieve all stored callback results with HTML interface
    """
    try:
        # Check if request wants JSON (API call)
        accept_header = request.headers.get("accept", "")
        if "application/json" in accept_header or "json" in request.url.query:
            return await get_all_results_json(limit, offset)
        
        # Return HTML for browser
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
            
            cursor.execute("SELECT COUNT(*) as count FROM callbacks")
            total = cursor.fetchone()["count"]
            
            # Generate HTML
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Callback Results</title>
                <style>
                    body {{ font-family: Arial, sans-serif; max-width: 1200px; margin: 20px auto; padding: 20px; }}
                    h1 {{ color: #2c3e50; }}
                    .stats {{ background: #f8f9fa; padding: 15px; margin: 20px 0; border-radius: 5px; }}
                    .result {{ background: #fff; border: 1px solid #dee2e6; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                    .result-header {{ font-weight: bold; color: #495057; margin-bottom: 10px; }}
                    pre {{ background: #f8f9fa; padding: 10px; border-radius: 3px; overflow-x: auto; }}
                    .status {{ padding: 3px 8px; border-radius: 3px; font-size: 12px; }}
                    .status-received {{ background: #d1ecf1; color: #0c5460; }}
                    .status-completed {{ background: #d4edda; color: #155724; }}
                    a {{ color: #007bff; text-decoration: none; }}
                    a:hover {{ text-decoration: underline; }}
                </style>
            </head>
            <body>
                <h1>📊 Callback Results</h1>
                
                <div class="stats">
                    <strong>Total Callbacks:</strong> {total} | 
                    <strong>Showing:</strong> {offset + 1} - {min(offset + limit, total)} |
                    <a href="/">← Back to Home</a> | 
                    <a href="/results?format=json">View as JSON</a>
                </div>
            """
            
            if not results:
                html_content += "<p>No callbacks received yet.</p>"
            else:
                for result in results:
                    status_class = f"status-{result['status']}" if result['status'] in ['received', 'completed'] else 'status-received'
                    html_content += f"""
                    <div class="result">
                        <div class="result-header">
                            <strong>Customer:</strong> {result['customer_id']} | 
                            <strong>Scan:</strong> {result['scan_id']} | 
                            <span class="status {status_class}">{result['status']}</span>
                        </div>
                        <div><strong>Received:</strong> {result['created_at']}</div>
                        <details>
                            <summary style="cursor: pointer; margin-top: 10px;">View Full Data</summary>
                            <pre>{json.dumps(result['callback_data'], indent=2)}</pre>
                        </details>
                    </div>
                    """
            
            html_content += """
                <div style="margin-top: 20px;">
                    <a href="/">← Back to Home</a>
                </div>
            </body>
            </html>
            """
            
            return html_content
            
    except Exception as e:
        logger.error(f"Error retrieving results: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving results: {str(e)}")

async def get_all_results_json(limit: int = 100, offset: int = 0):
    """JSON API for results"""
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