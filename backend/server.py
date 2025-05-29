from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Any
import uuid
from datetime import datetime, timedelta
import asyncio
import json
import math
import random
from datetime import datetime as dt_class

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Custom JSON encoder for datetime objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, dt_class):
            return obj.isoformat()
        return super().default(obj)

def safe_json_dumps(data):
    """Safely serialize data to JSON, handling datetime objects"""
    return json.dumps(data, cls=DateTimeEncoder)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = ConnectionManager()

# Physics Constants
EARTH_RADIUS = 6371000  # meters
GRAVITY = 9.81  # m/s^2
AIR_DENSITY = 1.225  # kg/m^3 at sea level

# Define Models
class Missile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    launch_lat: float
    launch_lon: float
    target_lat: float
    target_lon: float
    launch_time: datetime
    missile_type: str  # ICBM, IRBM, SRBM, Hypersonic
    speed: float  # m/s
    altitude: float  # meters
    current_lat: float
    current_lon: float
    current_altitude: float
    threat_level: int  # 1-10
    status: str  # Active, Intercepted, Impact
    trajectory_points: List[Dict[str, float]] = []

class ThreatAssessment(BaseModel):
    missile_id: str
    threat_score: int
    impact_probability: float
    time_to_impact: float
    recommended_interceptor: str
    priority_level: str

class InterceptorSite(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    lat: float
    lon: float
    interceptor_type: str  # Patriot, THAAD, Aegis
    range_km: float
    ready_interceptors: int
    status: str  # Active, Maintenance, Offline

# Missile Physics Calculations
class MissilePhysics:
    @staticmethod
    def calculate_distance(lat1, lon1, lat2, lon2):
        """Calculate great circle distance between two points"""
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = EARTH_RADIUS * c
        
        return distance

    @staticmethod
    def calculate_bearing(lat1, lon1, lat2, lon2):
        """Calculate bearing from point 1 to point 2"""
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlon_rad = math.radians(lon2 - lon1)
        
        y = math.sin(dlon_rad) * math.cos(lat2_rad)
        x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon_rad)
        
        bearing = math.atan2(y, x)
        return math.degrees(bearing)

    @staticmethod
    def calculate_trajectory_point(launch_lat, launch_lon, target_lat, target_lon, progress, missile_type):
        """Calculate current position along trajectory"""
        # Great circle interpolation
        lat1_rad = math.radians(launch_lat)
        lon1_rad = math.radians(launch_lon)
        lat2_rad = math.radians(target_lat)
        lon2_rad = math.radians(target_lon)
        
        d = math.acos(math.sin(lat1_rad) * math.sin(lat2_rad) + 
                     math.cos(lat1_rad) * math.cos(lat2_rad) * math.cos(lon2_rad - lon1_rad))
        
        if d == 0:
            return launch_lat, launch_lon, 0
            
        a = math.sin((1-progress) * d) / math.sin(d)
        b = math.sin(progress * d) / math.sin(d)
        
        x = a * math.cos(lat1_rad) * math.cos(lon1_rad) + b * math.cos(lat2_rad) * math.cos(lon2_rad)
        y = a * math.cos(lat1_rad) * math.sin(lon1_rad) + b * math.cos(lat2_rad) * math.sin(lon2_rad)
        z = a * math.sin(lat1_rad) + b * math.sin(lat2_rad)
        
        current_lat = math.degrees(math.atan2(z, math.sqrt(x**2 + y**2)))
        current_lon = math.degrees(math.atan2(y, x))
        
        # Calculate altitude based on missile type and trajectory progress
        max_altitude = {
            "ICBM": 1200000,  # 1200 km
            "IRBM": 400000,   # 400 km
            "SRBM": 150000,   # 150 km
            "Hypersonic": 60000  # 60 km
        }.get(missile_type, 200000)
        
        # Parabolic trajectory for altitude
        current_altitude = max_altitude * 4 * progress * (1 - progress)
        
        return current_lat, current_lon, current_altitude

# Threat Assessment AI (Simulated)
class ThreatAssessmentAI:
    @staticmethod
    def assess_threat(missile: Missile, interceptor_sites: List[InterceptorSite]) -> ThreatAssessment:
        # Calculate threat score based on multiple factors
        threat_factors = {
            "ICBM": 10,
            "IRBM": 7,
            "SRBM": 5,
            "Hypersonic": 9
        }
        
        base_threat = threat_factors.get(missile.missile_type, 5)
        
        # Calculate time to impact
        distance = MissilePhysics.calculate_distance(
            missile.current_lat, missile.current_lon,
            missile.target_lat, missile.target_lon
        )
        time_to_impact = distance / missile.speed
        
        # Calculate impact probability (simulated)
        impact_probability = min(0.95, 0.7 + (base_threat / 20))
        
        # Find best interceptor
        best_interceptor = "None Available"
        min_distance = float('inf')
        
        for site in interceptor_sites:
            if site.ready_interceptors > 0 and site.status == "Active":
                site_distance = MissilePhysics.calculate_distance(
                    site.lat, site.lon, missile.current_lat, missile.current_lon
                )
                if site_distance < site.range_km * 1000 and site_distance < min_distance:
                    min_distance = site_distance
                    best_interceptor = f"{site.name} ({site.interceptor_type})"
        
        # Determine priority level
        if time_to_impact < 300 and impact_probability > 0.8:  # < 5 minutes, high probability
            priority = "CRITICAL"
        elif time_to_impact < 600 and impact_probability > 0.6:  # < 10 minutes
            priority = "HIGH"
        elif time_to_impact < 1200:  # < 20 minutes
            priority = "MEDIUM"
        else:
            priority = "LOW"
        
        return ThreatAssessment(
            missile_id=missile.id,
            threat_score=min(10, base_threat + int(impact_probability * 3)),
            impact_probability=impact_probability,
            time_to_impact=time_to_impact,
            recommended_interceptor=best_interceptor,
            priority_level=priority
        )

# Global missile storage
active_missiles: Dict[str, Missile] = {}
interceptor_sites: List[InterceptorSite] = []

# Initialize interceptor sites
def initialize_interceptor_sites():
    global interceptor_sites
    interceptor_sites = [
        InterceptorSite(name="Norfolk Naval Base", lat=36.9467, lon=-76.3284, interceptor_type="Aegis", range_km=500, ready_interceptors=12, status="Active"),
        InterceptorSite(name="Ramstein Air Base", lat=49.4369, lon=7.6003, interceptor_type="Patriot", range_km=160, ready_interceptors=8, status="Active"),
        InterceptorSite(name="Yokosuka Naval Base", lat=35.2928, lon=139.6675, interceptor_type="Aegis", range_km=500, ready_interceptors=10, status="Active"),
        InterceptorSite(name="Guam Defense Site", lat=13.4443, lon=144.7937, interceptor_type="THAAD", range_km=200, ready_interceptors=6, status="Active"),
        InterceptorSite(name="Fort Sill", lat=34.6515, lon=-98.4020, interceptor_type="Patriot", range_km=160, ready_interceptors=15, status="Active"),
    ]

# Background task to update missile positions
async def update_missile_positions():
    while True:
        current_time = datetime.utcnow()
        updated_data = []
        
        for missile_id, missile in list(active_missiles.items()):
            # Calculate elapsed time since launch
            elapsed_seconds = (current_time - missile.launch_time).total_seconds()
            
            # Calculate total flight time
            total_distance = MissilePhysics.calculate_distance(
                missile.launch_lat, missile.launch_lon,
                missile.target_lat, missile.target_lon
            )
            total_flight_time = total_distance / missile.speed
            
            if elapsed_seconds >= total_flight_time:
                # Missile has reached target
                missile.status = "Impact"
                missile.current_lat = missile.target_lat
                missile.current_lon = missile.target_lon
                missile.current_altitude = 0
                # Remove from active tracking after impact
                del active_missiles[missile_id]
            else:
                # Update missile position
                progress = elapsed_seconds / total_flight_time
                current_lat, current_lon, current_altitude = MissilePhysics.calculate_trajectory_point(
                    missile.launch_lat, missile.launch_lon,
                    missile.target_lat, missile.target_lon,
                    progress, missile.missile_type
                )
                
                missile.current_lat = current_lat
                missile.current_lon = current_lon
                missile.current_altitude = current_altitude
                
                # Add to trajectory points
                missile.trajectory_points.append({
                    "lat": current_lat,
                    "lon": current_lon,
                    "alt": current_altitude,
                    "time": current_time.isoformat()
                })
                
                # Keep only last 100 trajectory points to prevent memory issues
                if len(missile.trajectory_points) > 100:
                    missile.trajectory_points = missile.trajectory_points[-100:]
                
                # Generate threat assessment
                threat_assessment = ThreatAssessmentAI.assess_threat(missile, interceptor_sites)
                
                updated_data.append({
                    "type": "missile_update",
                    "missile": missile.dict(),
                    "threat_assessment": threat_assessment.dict()
                })
        
        # Broadcast updates to all connected clients
        if updated_data:
            await manager.broadcast(safe_json_dumps({
                "type": "missile_updates",
                "data": updated_data
            }))
        
        await asyncio.sleep(2)  # Update every 2 seconds

# Start the background task
@app.on_event("startup")
async def startup_event():
    initialize_interceptor_sites()
    asyncio.create_task(update_missile_positions())

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send initial data
        await websocket.send_text(safe_json_dumps({
            "type": "initial_data",
            "missiles": [missile.dict() for missile in active_missiles.values()],
            "interceptor_sites": [site.dict() for site in interceptor_sites]
        }))
        
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# API Routes
@api_router.get("/")
async def root():
    return {"message": "GMDCSS - Global Missile Defense Command & Simulation System"}

@api_router.post("/missiles/launch")
async def launch_missile(missile_data: dict):
    # Create a new missile
    missile_types = ["ICBM", "IRBM", "SRBM", "Hypersonic"]
    missile_speeds = {"ICBM": 7000, "IRBM": 3000, "SRBM": 1500, "Hypersonic": 6000}  # m/s
    
    missile_type = missile_data.get("missile_type", random.choice(missile_types))
    
    missile = Missile(
        name=missile_data.get("name", f"Missile-{len(active_missiles)+1}"),
        launch_lat=missile_data["launch_lat"],
        launch_lon=missile_data["launch_lon"],
        target_lat=missile_data["target_lat"],
        target_lon=missile_data["target_lon"],
        launch_time=datetime.utcnow(),
        missile_type=missile_type,
        speed=missile_speeds[missile_type],
        altitude=0,
        current_lat=missile_data["launch_lat"],
        current_lon=missile_data["launch_lon"],
        current_altitude=0,
        threat_level=random.randint(5, 10),
        status="Active"
    )
    
    active_missiles[missile.id] = missile
    
    # Store in database
    await db.missiles.insert_one(missile.dict())
    
    return {"message": "Missile launched", "missile_id": missile.id}

@api_router.get("/missiles")
async def get_active_missiles():
    return {"missiles": [missile.dict() for missile in active_missiles.values()]}

@api_router.get("/interceptors")
async def get_interceptor_sites():
    return {"interceptor_sites": [site.dict() for site in interceptor_sites]}

@api_router.post("/intercept/{missile_id}")
async def intercept_missile(missile_id: str, interceptor_site_id: str):
    if missile_id in active_missiles:
        active_missiles[missile_id].status = "Intercepted"
        
        # Find interceptor site and reduce ready interceptors
        for site in interceptor_sites:
            if site.id == interceptor_site_id and site.ready_interceptors > 0:
                site.ready_interceptors -= 1
                break
        
        # Broadcast intercept event
        await manager.broadcast(json.dumps({
            "type": "intercept_event",
            "missile_id": missile_id,
            "interceptor_site_id": interceptor_site_id,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        return {"message": f"Intercept command issued for missile {missile_id}"}
    
    return {"error": "Missile not found"}

@api_router.post("/simulate/mass-attack")
async def simulate_mass_attack():
    """Simulate a coordinated missile attack for demonstration"""
    # Launch multiple missiles from different locations
    attack_scenarios = [
        {"launch_lat": 39.0458, "launch_lon": 125.7625, "target_lat": 37.5665, "target_lon": -122.4194, "name": "ICBM-Alpha"},  # North Korea -> SF
        {"launch_lat": 35.6762, "launch_lon": 139.6503, "target_lat": 34.0522, "target_lon": -118.2437, "name": "IRBM-Beta"},  # Tokyo -> LA
        {"launch_lat": 55.7558, "launch_lon": 37.6173, "target_lat": 40.7128, "target_lon": -74.0060, "name": "Hypersonic-Gamma"},  # Moscow -> NYC
        {"launch_lat": 31.2304, "launch_lon": 121.4737, "target_lat": 47.6062, "target_lon": -122.3321, "name": "SRBM-Delta"},  # Shanghai -> Seattle
    ]
    
    launched_missiles = []
    for scenario in attack_scenarios:
        missile_id = await launch_missile(scenario)
        launched_missiles.append(missile_id)
    
    return {"message": "Mass attack simulation initiated", "missiles": launched_missiles}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
