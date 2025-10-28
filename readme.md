# Fedo Callback Service

FastAPI service to receive and store Fedo scan callback results.

## Features

- ✅ Receive POST callbacks from Fedo scan integration
- ✅ Store results in SQLite database
- ✅ Backup results to JSON file
- ✅ Query results by customer ID
- ✅ Pagination support
- ✅ Comprehensive logging
- ✅ Ready for Render deployment

## Local Development

### Installation

```bash
pip install -r requirements.txt
```

### Run Locally

```bash
python main.py
```

Or with uvicorn:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### Root
- `GET /` - Service information

### Health Check
- `GET /health` - Health check endpoint

### Callback (Main)
- `POST /consint/demo-callback` - Receive Fedo scan callbacks

**Request Body:**
```json
{
  "customerID": "CUST_12345",
  "scanID": "SCN_001",
  "status": "completed",
  "data": { ... },
  "metadata": { ... },
  "timestamp": "2025-10-28T10:00:00Z"
}
```

### Query Results
- `GET /results?limit=100&offset=0` - Get all results with pagination
- `GET /results/{customer_id}` - Get results for specific customer
- `DELETE /results/{callback_id}` - Delete a specific result

## Deployment on Render

### Steps:

1. Push code to GitHub repository

2. Create new Web Service on Render:
   - Connect your GitHub repo
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`

3. Add Environment Variable (optional):
   - `DATABASE_URL` (if using PostgreSQL)

4. Deploy!

Your callback URL will be:
```
https://your-service.onrender.com/consint/demo-callback
```

## Testing

Test the callback endpoint:

```bash
curl -X POST https://your-service.onrender.com/consint/demo-callback \
  -H "Content-Type: application/json" \
  -d '{
    "customerID": "CUST_12345",
    "scanID": "SCN_001",
    "status": "completed",
    "data": {"heartRate": 75, "bloodPressure": "120/80"},
    "metadata": {"age": 35, "gender": "male"}
  }'
```

## Data Storage

- **SQLite Database:** `fedo_callbacks.db` (primary storage)
- **JSON Backup:** `callback_results.json` (backup)
- **Logs:** `callback_logs.log`

## Switching to PostgreSQL (Render)

If you want to use Render's PostgreSQL:

1. Add PostgreSQL add-on in Render dashboard
2. Update database connection in `main.py` (use environment variable)
3. Redeploy

Let me know if you need the PostgreSQL version!