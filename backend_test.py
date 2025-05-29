
import requests
import json
import time
import websocket
import threading
import sys
from datetime import datetime

class GMDCSSAPITester:
    def __init__(self, base_url):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.ws_url = base_url.replace('https://', 'wss://').replace('http://', 'ws://')
        self.tests_run = 0
        self.tests_passed = 0
        self.ws_connected = False
        self.ws_messages = []
        self.ws = None

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, params=params)
            
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return success, response.json()
                except:
                    return success, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    print(f"Response: {response.text}")
                    return False, response.json()
                except:
                    return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def connect_websocket(self):
        """Connect to WebSocket and listen for messages"""
        def on_message(ws, message):
            data = json.loads(message)
            self.ws_messages.append(data)
            print(f"📡 WebSocket message received: {data['type']}")
        
        def on_error(ws, error):
            print(f"❌ WebSocket error: {error}")
        
        def on_close(ws, close_status_code, close_msg):
            print("📡 WebSocket connection closed")
            self.ws_connected = False
        
        def on_open(ws):
            print("📡 WebSocket connection established")
            self.ws_connected = True
        
        # Connect to WebSocket
        ws_endpoint = f"{self.ws_url}/ws"
        print(f"📡 Connecting to WebSocket at {ws_endpoint}")
        
        self.ws = websocket.WebSocketApp(
            ws_endpoint,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        
        # Start WebSocket connection in a separate thread
        self.ws_thread = threading.Thread(target=self.ws.run_forever)
        self.ws_thread.daemon = True
        self.ws_thread.start()
        
        # Wait for connection to establish
        time.sleep(2)
        return self.ws_connected

    def test_base_endpoint(self):
        """Test the base API endpoint"""
        success, response = self.run_test(
            "Base API Endpoint",
            "GET",
            "",
            200
        )
        if success:
            print(f"Response message: {response.get('message', '')}")
        return success

    def test_launch_missile(self, missile_data):
        """Test missile launch endpoint"""
        success, response = self.run_test(
            "Missile Launch",
            "POST",
            "missiles/launch",
            200,
            data=missile_data
        )
        if success:
            print(f"Missile launched with ID: {response.get('missile_id', '')}")
            return response.get('missile_id')
        return None

    def test_get_active_missiles(self):
        """Test get active missiles endpoint"""
        success, response = self.run_test(
            "Get Active Missiles",
            "GET",
            "missiles",
            200
        )
        if success:
            missiles = response.get('missiles', [])
            print(f"Active missiles: {len(missiles)}")
            return missiles
        return []

    def test_get_interceptor_sites(self):
        """Test get interceptor sites endpoint"""
        success, response = self.run_test(
            "Get Interceptor Sites",
            "GET",
            "interceptors",
            200
        )
        if success:
            sites = response.get('interceptor_sites', [])
            print(f"Interceptor sites: {len(sites)}")
            return sites
        return []

    def test_intercept_missile(self, missile_id, interceptor_site_id):
        """Test intercept missile endpoint"""
        success, response = self.run_test(
            f"Intercept Missile {missile_id}",
            "POST",
            f"intercept/{missile_id}",
            200,
            params={"interceptor_site_id": interceptor_site_id}
        )
        return success

    def test_simulate_mass_attack(self):
        """Test mass attack simulation endpoint"""
        success, response = self.run_test(
            "Simulate Mass Attack",
            "POST",
            "simulate/mass-attack",
            200
        )
        if success:
            print(f"Mass attack simulation initiated with missiles: {response.get('missiles', [])}")
        return success

    def wait_for_websocket_updates(self, timeout=10, expected_type=None):
        """Wait for WebSocket updates"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if expected_type:
                for msg in self.ws_messages:
                    if msg.get('type') == expected_type:
                        return True
            elif self.ws_messages:
                return True
            time.sleep(0.5)
        return False

    def close_websocket(self):
        """Close WebSocket connection"""
        if self.ws:
            self.ws.close()
            time.sleep(1)  # Give it time to close

def main():
    # Get the backend URL from command line or use default
    if len(sys.argv) > 1:
        backend_url = sys.argv[1]
    else:
        backend_url = "https://28159629-7ee7-4d08-903a-6cf08eb66ab9.preview.emergentagent.com"
    
    print(f"🚀 Testing GMDCSS API at {backend_url}")
    
    # Initialize tester
    tester = GMDCSSAPITester(backend_url)
    
    # Test base endpoint
    if not tester.test_base_endpoint():
        print("❌ Base API test failed, stopping tests")
        return 1
    
    # Connect to WebSocket
    print("\n📡 Testing WebSocket connection...")
    if not tester.connect_websocket():
        print("❌ WebSocket connection failed, continuing with API tests")
    else:
        print("✅ WebSocket connection successful")
        
        # Wait for initial data
        print("📡 Waiting for initial data from WebSocket...")
        if tester.wait_for_websocket_updates(timeout=5, expected_type="initial_data"):
            print("✅ Received initial data from WebSocket")
        else:
            print("❌ Did not receive initial data from WebSocket")
    
    # Test get interceptor sites
    interceptor_sites = tester.test_get_interceptor_sites()
    if not interceptor_sites:
        print("❌ Failed to get interceptor sites")
    
    # Test get active missiles (before launching any)
    initial_missiles = tester.test_get_active_missiles()
    
    # Test missile launch
    test_missile = {
        "launch_lat": 39.0458,
        "launch_lon": 125.7625,
        "target_lat": 37.5665,
        "target_lon": -122.4194,
        "name": f"Test-ICBM-{datetime.now().strftime('%H%M%S')}",
        "missile_type": "ICBM"
    }
    
    missile_id = tester.test_launch_missile(test_missile)
    if not missile_id:
        print("❌ Missile launch failed")
    else:
        # Wait for WebSocket updates
        if tester.ws_connected:
            print("📡 Waiting for missile updates from WebSocket...")
            if tester.wait_for_websocket_updates(timeout=5, expected_type="missile_updates"):
                print("✅ Received missile updates from WebSocket")
            else:
                print("❌ Did not receive missile updates from WebSocket")
        
        # Test get active missiles (after launching)
        time.sleep(2)  # Give the server time to process
        updated_missiles = tester.test_get_active_missiles()
        
        if len(updated_missiles) > len(initial_missiles):
            print("✅ Missile count increased after launch")
        else:
            print("❌ Missile count did not increase after launch")
        
        # Test intercept missile if we have a missile ID and interceptor sites
        if missile_id and interceptor_sites:
            interceptor_site_id = interceptor_sites[0]['id']
            if tester.test_intercept_missile(missile_id, interceptor_site_id):
                print("✅ Missile intercept command successful")
                
                # Wait for intercept event on WebSocket
                if tester.ws_connected:
                    print("📡 Waiting for intercept event from WebSocket...")
                    if tester.wait_for_websocket_updates(timeout=5, expected_type="intercept_event"):
                        print("✅ Received intercept event from WebSocket")
                    else:
                        print("❌ Did not receive intercept event from WebSocket")
            else:
                print("❌ Missile intercept command failed")
    
    # Test mass attack simulation
    if tester.test_simulate_mass_attack():
        print("✅ Mass attack simulation successful")
        
        # Wait for WebSocket updates
        if tester.ws_connected:
            print("📡 Waiting for missile updates from mass attack...")
            if tester.wait_for_websocket_updates(timeout=5):
                print("✅ Received updates from mass attack")
            else:
                print("❌ Did not receive updates from mass attack")
    else:
        print("❌ Mass attack simulation failed")
    
    # Close WebSocket connection
    if tester.ws_connected:
        tester.close_websocket()
    
    # Print test results
    print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())
