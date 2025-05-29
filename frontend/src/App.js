import React, { useState, useEffect, useRef } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline, CircleMarker } from 'react-leaflet';
import L from 'leaflet';
import "leaflet/dist/leaflet.css";
import "./App.css";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const WS_URL = BACKEND_URL.replace('https://', 'wss://').replace('http://', 'ws://');

// Fix for default markers in react-leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// Custom icons
const missileIcon = new L.Icon({
  iconUrl: 'data:image/svg+xml;base64,' + btoa(`
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 2L14 8L12 14L10 8L12 2Z" fill="#ff4444"/>
      <circle cx="12" cy="12" r="2" fill="#ff0000"/>
    </svg>
  `),
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

const interceptorIcon = new L.Icon({
  iconUrl: 'data:image/svg+xml;base64,' + btoa(`
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="6" y="6" width="12" height="12" fill="#4CAF50"/>
      <circle cx="12" cy="12" r="4" fill="#2E7D32"/>
    </svg>
  `),
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

const targetIcon = new L.Icon({
  iconUrl: 'data:image/svg+xml;base64,' + btoa(`
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="12" cy="12" r="8" fill="none" stroke="#ff6b6b" stroke-width="2"/>
      <circle cx="12" cy="12" r="4" fill="none" stroke="#ff6b6b" stroke-width="2"/>
      <circle cx="12" cy="12" r="1" fill="#ff6b6b"/>
    </svg>
  `),
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

function App() {
  const [missiles, setMissiles] = useState([]);
  const [interceptorSites, setInterceptorSites] = useState([]);
  const [threats, setThreats] = useState([]);
  const [selectedMissile, setSelectedMissile] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [systemStatus, setSystemStatus] = useState('OPERATIONAL');
  const wsRef = useRef(null);

  useEffect(() => {
    // Connect to WebSocket
    const connectWebSocket = () => {
      wsRef.current = new WebSocket(`${WS_URL}/ws`);
      
      wsRef.current.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        setSystemStatus('OPERATIONAL');
      };
      
      wsRef.current.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'initial_data') {
          setMissiles(data.missiles || []);
          setInterceptorSites(data.interceptor_sites || []);
        } else if (data.type === 'missile_updates') {
          // Update missiles and threats
          const updatedMissiles = [];
          const updatedThreats = [];
          
          data.data.forEach(update => {
            updatedMissiles.push(update.missile);
            updatedThreats.push(update.threat_assessment);
          });
          
          setMissiles(prev => {
            const missileMap = new Map(prev.map(m => [m.id, m]));
            updatedMissiles.forEach(missile => {
              missileMap.set(missile.id, missile);
            });
            return Array.from(missileMap.values()).filter(m => m.status === 'Active');
          });
          
          setThreats(updatedThreats);
        } else if (data.type === 'intercept_event') {
          // Handle intercept events
          setMissiles(prev => prev.filter(m => m.id !== data.missile_id));
        }
      };
      
      wsRef.current.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);
        setSystemStatus('DISCONNECTED');
        // Attempt to reconnect after 3 seconds
        setTimeout(connectWebSocket, 3000);
      };
      
      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setSystemStatus('ERROR');
      };
    };

    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const launchTestMissile = async () => {
    const testMissile = {
      launch_lat: 39.0458 + Math.random() * 10 - 5,
      launch_lon: 125.7625 + Math.random() * 10 - 5,
      target_lat: 37.5665 + Math.random() * 10 - 5,
      target_lon: -122.4194 + Math.random() * 10 - 5,
      name: `Test-Missile-${Date.now()}`,
      missile_type: 'ICBM'
    };

    try {
      await fetch(`${API}/missiles/launch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(testMissile)
      });
    } catch (error) {
      console.error('Error launching missile:', error);
    }
  };

  const simulateMassAttack = async () => {
    try {
      await fetch(`${API}/simulate/mass-attack`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
    } catch (error) {
      console.error('Error simulating mass attack:', error);
    }
  };

  const interceptMissile = async (missileId) => {
    // Find nearest interceptor site
    const missile = missiles.find(m => m.id === missileId);
    if (!missile) return;

    const activeSites = interceptorSites.filter(site => 
      site.status === 'Active' && site.ready_interceptors > 0
    );

    if (activeSites.length === 0) {
      alert('No active interceptor sites available!');
      return;
    }

    // Use first available site for simplicity
    const interceptorSite = activeSites[0];

    try {
      await fetch(`${API}/intercept/${missileId}?interceptor_site_id=${interceptorSite.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
    } catch (error) {
      console.error('Error intercepting missile:', error);
    }
  };

  const getThreatLevel = (priority) => {
    const levels = {
      'CRITICAL': { color: '#ff0000', text: 'CRITICAL' },
      'HIGH': { color: '#ff6600', text: 'HIGH' },
      'MEDIUM': { color: '#ffaa00', text: 'MEDIUM' },
      'LOW': { color: '#66bb6a', text: 'LOW' }
    };
    return levels[priority] || levels['LOW'];
  };

  const getTrajectoryColor = (missile) => {
    const colors = {
      'ICBM': '#ff4444',
      'IRBM': '#ff8844',
      'SRBM': '#ffaa44',
      'Hypersonic': '#ff0088'
    };
    return colors[missile.missile_type] || '#ff4444';
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 p-4">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-blue-400">GMDCSS</h1>
            <p className="text-sm text-gray-400">Global Missile Defense Command & Simulation System</p>
          </div>
          <div className="flex items-center space-x-4">
            <div className={`px-3 py-1 rounded-full text-sm font-medium ${
              systemStatus === 'OPERATIONAL' ? 'bg-green-600' :
              systemStatus === 'DISCONNECTED' ? 'bg-yellow-600' : 'bg-red-600'
            }`}>
              {systemStatus}
            </div>
            <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
          </div>
        </div>
      </div>

      <div className="flex h-screen">
        {/* Sidebar */}
        <div className="w-80 bg-gray-800 p-4 overflow-y-auto">
          {/* Control Panel */}
          <div className="mb-6">
            <h2 className="text-lg font-semibold mb-3 text-blue-400">Mission Control</h2>
            <div className="space-y-2">
              <button
                onClick={launchTestMissile}
                className="w-full bg-red-600 hover:bg-red-700 px-4 py-2 rounded transition-colors"
              >
                Launch Test Missile
              </button>
              <button
                onClick={simulateMassAttack}
                className="w-full bg-orange-600 hover:bg-orange-700 px-4 py-2 rounded transition-colors"
              >
                Simulate Mass Attack
              </button>
            </div>
          </div>

          {/* Active Threats */}
          <div className="mb-6">
            <h2 className="text-lg font-semibold mb-3 text-red-400">Active Threats ({missiles.length})</h2>
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {missiles.map((missile) => {
                const threat = threats.find(t => t.missile_id === missile.id);
                const threatLevel = getThreatLevel(threat?.priority_level || 'LOW');
                
                return (
                  <div
                    key={missile.id}
                    className={`p-3 rounded border-l-4 cursor-pointer transition-colors ${
                      selectedMissile === missile.id ? 'bg-gray-600' : 'bg-gray-700 hover:bg-gray-600'
                    }`}
                    style={{ borderLeftColor: threatLevel.color }}
                    onClick={() => setSelectedMissile(missile.id)}
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <p className="font-medium">{missile.name}</p>
                        <p className="text-sm text-gray-400">{missile.missile_type}</p>
                        <p className="text-xs text-gray-500">
                          Alt: {Math.round(missile.current_altitude / 1000)}km
                        </p>
                      </div>
                      <div className="text-right">
                        <span className="text-xs px-2 py-1 rounded" style={{ backgroundColor: threatLevel.color }}>
                          {threatLevel.text}
                        </span>
                        {threat && (
                          <p className="text-xs text-gray-400 mt-1">
                            ETA: {Math.round(threat.time_to_impact / 60)}min
                          </p>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        interceptMissile(missile.id);
                      }}
                      className="w-full mt-2 bg-blue-600 hover:bg-blue-700 px-2 py-1 rounded text-xs transition-colors"
                    >
                      INTERCEPT
                    </button>
                  </div>
                );
              })}
              {missiles.length === 0 && (
                <p className="text-gray-500 text-center py-4">No active threats detected</p>
              )}
            </div>
          </div>

          {/* Interceptor Sites */}
          <div>
            <h2 className="text-lg font-semibold mb-3 text-green-400">Interceptor Sites ({interceptorSites.length})</h2>
            <div className="space-y-2 max-h-40 overflow-y-auto">
              {interceptorSites.map((site) => (
                <div key={site.id} className="p-2 bg-gray-700 rounded">
                  <div className="flex justify-between items-center">
                    <div>
                      <p className="text-sm font-medium">{site.name}</p>
                      <p className="text-xs text-gray-400">{site.interceptor_type}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm">{site.ready_interceptors}</p>
                      <p className="text-xs text-gray-400">Ready</p>
                    </div>
                  </div>
                  <div className={`w-full h-1 rounded mt-1 ${
                    site.status === 'Active' ? 'bg-green-500' : 'bg-red-500'
                  }`}></div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Main Map */}
        <div className="flex-1 relative">
          <MapContainer
            center={[40, 0]}
            zoom={2}
            style={{ height: '100%', width: '100%' }}
            className="z-0"
          >
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            />
            
            {/* Interceptor Sites */}
            {interceptorSites.map((site) => (
              <Marker
                key={site.id}
                position={[site.lat, site.lon]}
                icon={interceptorIcon}
              >
                <Popup>
                  <div>
                    <h3 className="font-bold">{site.name}</h3>
                    <p>Type: {site.interceptor_type}</p>
                    <p>Range: {site.range_km}km</p>
                    <p>Ready Interceptors: {site.ready_interceptors}</p>
                    <p>Status: {site.status}</p>
                  </div>
                </Popup>
              </Marker>
            ))}

            {/* Missiles and Trajectories */}
            {missiles.map((missile) => {
              const threat = threats.find(t => t.missile_id === missile.id);
              
              return (
                <React.Fragment key={missile.id}>
                  {/* Launch Point */}
                  <CircleMarker
                    center={[missile.launch_lat, missile.launch_lon]}
                    radius={6}
                    color="#ff0000"
                    fillColor="#ff0000"
                    fillOpacity={0.8}
                  >
                    <Popup>Launch Point: {missile.name}</Popup>
                  </CircleMarker>

                  {/* Target Point */}
                  <Marker
                    position={[missile.target_lat, missile.target_lon]}
                    icon={targetIcon}
                  >
                    <Popup>Target: {missile.name}</Popup>
                  </Marker>

                  {/* Current Missile Position */}
                  <Marker
                    position={[missile.current_lat, missile.current_lon]}
                    icon={missileIcon}
                  >
                    <Popup>
                      <div>
                        <h3 className="font-bold">{missile.name}</h3>
                        <p>Type: {missile.missile_type}</p>
                        <p>Altitude: {Math.round(missile.current_altitude / 1000)}km</p>
                        <p>Speed: {missile.speed}m/s</p>
                        <p>Status: {missile.status}</p>
                        {threat && (
                          <>
                            <p>Threat Level: {threat.priority_level}</p>
                            <p>Time to Impact: {Math.round(threat.time_to_impact / 60)}min</p>
                            <p>Recommended: {threat.recommended_interceptor}</p>
                          </>
                        )}
                      </div>
                    </Popup>
                  </Marker>

                  {/* Trajectory Line */}
                  <Polyline
                    positions={[
                      [missile.launch_lat, missile.launch_lon],
                      [missile.current_lat, missile.current_lon],
                      [missile.target_lat, missile.target_lon]
                    ]}
                    color={getTrajectoryColor(missile)}
                    weight={3}
                    opacity={0.7}
                    dashArray={selectedMissile === missile.id ? null : "5, 10"}
                  />

                  {/* Trajectory Points */}
                  {missile.trajectory_points && missile.trajectory_points.slice(-10).map((point, index) => (
                    <CircleMarker
                      key={index}
                      center={[point.lat, point.lon]}
                      radius={2}
                      color={getTrajectoryColor(missile)}
                      fillOpacity={0.6}
                    />
                  ))}
                </React.Fragment>
              );
            })}
          </MapContainer>

          {/* Legend */}
          <div className="absolute top-4 right-4 bg-gray-800 bg-opacity-90 p-4 rounded-lg z-1000">
            <h3 className="font-bold mb-2">Legend</h3>
            <div className="space-y-2 text-sm">
              <div className="flex items-center space-x-2">
                <div className="w-4 h-4 bg-red-500 rounded"></div>
                <span>Missile</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-4 h-4 bg-green-500 rounded"></div>
                <span>Interceptor Site</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-4 h-4 border-2 border-red-500 rounded-full"></div>
                <span>Target</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-6 h-1 bg-red-500"></div>
                <span>ICBM</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-6 h-1 bg-orange-500"></div>
                <span>IRBM</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-6 h-1 bg-yellow-500"></div>
                <span>SRBM</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-6 h-1 bg-pink-500"></div>
                <span>Hypersonic</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;