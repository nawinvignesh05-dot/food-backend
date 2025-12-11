# Backend (Flask) for Food Recommendation App

1. Copy files into `backend/` preserving structure.
2. Create `.env` from `.env.example` and set keys:
   - GEMINI_API_KEY or OPENAI_API_KEY
   - FOURSQUARE_API_KEY
   - MONGODB_URI (optional)

3. Create virtual env and install:
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

4. Run:
   export FLASK_APP=app.main:create_app
   flask run --host=0.0.0.0 --port=8000

Or:
   python -m app.main

5. Test:
   POST http://localhost:8000/api/recommend
   Body:
   {
     "query": "spicy cheesy fast food under 200 near Guindy",
     "lat": 12.9959,
     "lng": 80.2200,
     "limit": 5
   }
