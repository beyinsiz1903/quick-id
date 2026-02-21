#!/usr/bin/env python3
"""
Backend API Testing Script for Quick ID Reader Hotel App v3.0
Tests all new backend endpoints for KVKK, TC Kimlik, Pre-Checkin, Multi-Property, Kiosk, Offline, and Biometric features
"""

import requests
import json
import base64
import io
from PIL import Image
import sys
import time

# Backend URL from environment
BACKEND_URL = "https://yuz-eslestir.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"

class APITester:
    def __init__(self):
        self.token = None
        self.test_results = []
        self.property_id = None
        self.precheckin_token_id = None
        self.sync_id = None
        
    def log_result(self, test_name, success, details="", response_data=None):
        """Log test results"""
        result = {
            "test": test_name,
            "success": success, 
            "details": details,
            "response_data": response_data
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")
        if details:
            print(f"    {details}")
        if not success and response_data:
            print(f"    Response: {json.dumps(response_data, indent=2)[:200]}...")
            
    def create_test_image(self):
        """Create a simple test image in base64 format"""
        img = Image.new('RGB', (200, 200), color='blue')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        img_data = buffer.getvalue()
        return base64.b64encode(img_data).decode()

    def test_login(self):
        """Test authentication"""
        print("\n=== AUTHENTICATION TEST ===")
        
        try:
            response = requests.post(f"{API_BASE}/auth/login", json={
                "email": "admin@quickid.com",
                "password": "admin123"
            })
            
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("token")
                self.log_result("Admin Login", True, f"Token received, user role: {data.get('user', {}).get('role')}")
                return True
            else:
                self.log_result("Admin Login", False, f"Status {response.status_code}", response.json())
                return False
                
        except Exception as e:
            self.log_result("Admin Login", False, f"Exception: {str(e)}")
            return False
    
    def get_headers(self):
        """Get authorization headers"""
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    def test_kvkk_public_consent(self):
        """Test KVKK public consent info endpoint (no auth required)"""
        print("\n=== KVKK PUBLIC CONSENT INFO ===")
        
        try:
            response = requests.get(f"{API_BASE}/kvkk/consent-info")
            
            if response.status_code == 200:
                data = response.json()
                has_required_fields = all(key in data for key in ["consent_required", "consent_text", "rights"])
                if has_required_fields:
                    self.log_result("KVKK Public Consent Info", True, 
                                  f"Consent required: {data.get('consent_required')}, {len(data.get('rights', []))} rights listed")
                else:
                    self.log_result("KVKK Public Consent Info", False, "Missing required fields", data)
            else:
                self.log_result("KVKK Public Consent Info", False, f"Status {response.status_code}", response.json())
                
        except Exception as e:
            self.log_result("KVKK Public Consent Info", False, f"Exception: {str(e)}")

    def test_tc_kimlik_validation(self):
        """Test TC Kimlik No validation endpoint"""
        print("\n=== TC KIMLIK VALIDATION ===")
        
        # Test valid TC number
        try:
            response = requests.post(f"{API_BASE}/tc-kimlik/validate", 
                                   headers=self.get_headers(),
                                   json={"tc_no": "10000000146"})
            
            if response.status_code == 200:
                data = response.json()
                if data.get("is_valid") == True:
                    self.log_result("TC Kimlik Valid Number", True, "Valid TC number accepted")
                else:
                    self.log_result("TC Kimlik Valid Number", False, "Valid TC rejected", data)
            else:
                self.log_result("TC Kimlik Valid Number", False, f"Status {response.status_code}", response.json())
                
        except Exception as e:
            self.log_result("TC Kimlik Valid Number", False, f"Exception: {str(e)}")

        # Test invalid TC number
        try:
            response = requests.post(f"{API_BASE}/tc-kimlik/validate", 
                                   headers=self.get_headers(),
                                   json={"tc_no": "12345678901"})
            
            if response.status_code == 200:
                data = response.json()
                if data.get("is_valid") == False:
                    self.log_result("TC Kimlik Invalid Number", True, "Invalid TC number correctly rejected")
                else:
                    self.log_result("TC Kimlik Invalid Number", False, "Invalid TC incorrectly accepted", data)
            else:
                self.log_result("TC Kimlik Invalid Number", False, f"Status {response.status_code}", response.json())
                
        except Exception as e:
            self.log_result("TC Kimlik Invalid Number", False, f"Exception: {str(e)}")

        # Test too short TC number
        try:
            response = requests.post(f"{API_BASE}/tc-kimlik/validate", 
                                   headers=self.get_headers(),
                                   json={"tc_no": "123"})
            
            if response.status_code == 200:
                data = response.json()
                if data.get("is_valid") == False and "11 haneli" in str(data.get("errors", [])):
                    self.log_result("TC Kimlik Short Number", True, "Short TC number correctly rejected")
                else:
                    self.log_result("TC Kimlik Short Number", False, "Short TC not properly validated", data)
            else:
                self.log_result("TC Kimlik Short Number", False, f"Status {response.status_code}", response.json())
                
        except Exception as e:
            self.log_result("TC Kimlik Short Number", False, f"Exception: {str(e)}")

    def test_multi_property_management(self):
        """Test multi-property management endpoints"""
        print("\n=== MULTI-PROPERTY MANAGEMENT ===")
        
        # Test create property
        try:
            response = requests.post(f"{API_BASE}/properties", 
                                   headers=self.get_headers(),
                                   json={
                                       "name": "Test Otel", 
                                       "city": "Istanbul",
                                       "address": "Test Mahallesi", 
                                       "phone": "02123334455"
                                   })
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and "property" in data:
                    self.property_id = data["property"]["property_id"]
                    self.log_result("Create Property", True, f"Property created: {data['property']['name']}")
                else:
                    self.log_result("Create Property", False, "Property not created properly", data)
            else:
                self.log_result("Create Property", False, f"Status {response.status_code}", response.json())
                
        except Exception as e:
            self.log_result("Create Property", False, f"Exception: {str(e)}")

        # Test list properties
        try:
            response = requests.get(f"{API_BASE}/properties", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                if "properties" in data and len(data["properties"]) > 0:
                    self.log_result("List Properties", True, f"Found {len(data['properties'])} properties")
                    # Set property_id if not set from creation
                    if not self.property_id and data["properties"]:
                        self.property_id = data["properties"][0]["property_id"]
                else:
                    self.log_result("List Properties", False, "No properties found", data)
            else:
                self.log_result("List Properties", False, f"Status {response.status_code}", response.json())
                
        except Exception as e:
            self.log_result("List Properties", False, f"Exception: {str(e)}")

        # Test get specific property
        if self.property_id:
            try:
                response = requests.get(f"{API_BASE}/properties/{self.property_id}", headers=self.get_headers())
                
                if response.status_code == 200:
                    data = response.json()
                    if "property" in data and data["property"]["property_id"] == self.property_id:
                        self.log_result("Get Property", True, f"Property details retrieved: {data['property']['name']}")
                    else:
                        self.log_result("Get Property", False, "Property details incorrect", data)
                else:
                    self.log_result("Get Property", False, f"Status {response.status_code}", response.json())
                    
            except Exception as e:
                self.log_result("Get Property", False, f"Exception: {str(e)}")

        # Test update property  
        if self.property_id:
            try:
                response = requests.patch(f"{API_BASE}/properties/{self.property_id}", 
                                        headers=self.get_headers(),
                                        json={"phone": "05551112233"})
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success") and data.get("property", {}).get("phone") == "05551112233":
                        self.log_result("Update Property", True, "Property phone updated successfully")
                    else:
                        self.log_result("Update Property", False, "Property update failed", data)
                else:
                    self.log_result("Update Property", False, f"Status {response.status_code}", response.json())
                    
            except Exception as e:
                self.log_result("Update Property", False, f"Exception: {str(e)}")

    def test_precheckin_qr_system(self):
        """Test pre-checkin QR system endpoints"""
        print("\n=== PRE-CHECKIN QR SYSTEM ===")
        
        if not self.property_id:
            self.log_result("Pre-Checkin System", False, "No property_id available for testing")
            return
        
        # Test create pre-checkin token
        try:
            response = requests.post(f"{API_BASE}/precheckin/create", 
                                   headers=self.get_headers(),
                                   json={
                                       "property_id": self.property_id,
                                       "guest_name": "Test Misafir",
                                       "reservation_ref": "RES123"
                                   })
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and "token" in data:
                    self.precheckin_token_id = data["token"]["token_id"]
                    self.log_result("Create Pre-Checkin Token", True, f"Token created: {self.precheckin_token_id[:8]}...")
                else:
                    self.log_result("Create Pre-Checkin Token", False, "Token not created properly", data)
            else:
                self.log_result("Create Pre-Checkin Token", False, f"Status {response.status_code}", response.json())
                
        except Exception as e:
            self.log_result("Create Pre-Checkin Token", False, f"Exception: {str(e)}")

        # Test get token info (public endpoint, no auth)
        if self.precheckin_token_id:
            try:
                response = requests.get(f"{API_BASE}/precheckin/{self.precheckin_token_id}")
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("token_id") == self.precheckin_token_id:
                        self.log_result("Get Pre-Checkin Token (Public)", True, f"Token info retrieved for guest: {data.get('guest_name')}")
                    else:
                        self.log_result("Get Pre-Checkin Token (Public)", False, "Token info incorrect", data)
                else:
                    self.log_result("Get Pre-Checkin Token (Public)", False, f"Status {response.status_code}", response.json())
                    
            except Exception as e:
                self.log_result("Get Pre-Checkin Token (Public)", False, f"Exception: {str(e)}")

        # Test get QR code image (requires auth)
        if self.precheckin_token_id:
            try:
                response = requests.get(f"{API_BASE}/precheckin/{self.precheckin_token_id}/qr", 
                                      headers=self.get_headers())
                
                if response.status_code == 200 and response.headers.get('content-type') == 'image/png':
                    self.log_result("Get QR Code Image", True, f"QR code PNG received, size: {len(response.content)} bytes")
                else:
                    self.log_result("Get QR Code Image", False, f"Status {response.status_code}, content-type: {response.headers.get('content-type')}")
                    
            except Exception as e:
                self.log_result("Get QR Code Image", False, f"Exception: {str(e)}")

        # Test list pre-checkin tokens
        try:
            response = requests.get(f"{API_BASE}/precheckin/list", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                if "tokens" in data:
                    self.log_result("List Pre-Checkin Tokens", True, f"Found {len(data['tokens'])} tokens")
                else:
                    self.log_result("List Pre-Checkin Tokens", False, "Token list not properly formatted", data)
            else:
                self.log_result("List Pre-Checkin Tokens", False, f"Status {response.status_code}", response.json())
                
        except Exception as e:
            self.log_result("List Pre-Checkin Tokens", False, f"Exception: {str(e)}")

    def test_kiosk_mode(self):
        """Test kiosk mode endpoints"""
        print("\n=== KIOSK MODE ===")
        
        if not self.property_id:
            self.log_result("Kiosk Mode", False, "No property_id available for testing")
            return
            
        # Test create kiosk session
        try:
            response = requests.post(f"{API_BASE}/kiosk/session", 
                                   headers=self.get_headers(),
                                   json={
                                       "property_id": self.property_id,
                                       "kiosk_name": "Lobby Terminal 1"
                                   })
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and "session" in data:
                    session_id = data["session"]["session_id"]
                    self.log_result("Create Kiosk Session", True, f"Session created: {session_id[:8]}...")
                else:
                    self.log_result("Create Kiosk Session", False, "Session not created properly", data)
            else:
                self.log_result("Create Kiosk Session", False, f"Status {response.status_code}", response.json())
                
        except Exception as e:
            self.log_result("Create Kiosk Session", False, f"Exception: {str(e)}")

        # Test list kiosk sessions
        try:
            response = requests.get(f"{API_BASE}/kiosk/sessions", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                if "sessions" in data:
                    self.log_result("List Kiosk Sessions", True, f"Found {len(data['sessions'])} sessions")
                else:
                    self.log_result("List Kiosk Sessions", False, "Sessions list not properly formatted", data)
            else:
                self.log_result("List Kiosk Sessions", False, f"Status {response.status_code}", response.json())
                
        except Exception as e:
            self.log_result("List Kiosk Sessions", False, f"Exception: {str(e)}")

    def test_offline_sync(self):
        """Test offline sync endpoints"""
        print("\n=== OFFLINE SYNC ===")
        
        if not self.property_id:
            self.log_result("Offline Sync", False, "No property_id available for testing")
            return
            
        # Test upload offline data
        try:
            response = requests.post(f"{API_BASE}/sync/upload", 
                                   headers=self.get_headers(),
                                   json={
                                       "property_id": self.property_id,
                                       "data_type": "guests",
                                       "data": [{"first_name": "Test", "last_name": "Offline"}],
                                       "device_id": "device001"
                                   })
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and "sync" in data:
                    self.sync_id = data["sync"]["sync_id"]
                    self.log_result("Upload Offline Data", True, f"Sync uploaded: {self.sync_id[:8]}...")
                else:
                    self.log_result("Upload Offline Data", False, "Sync not created properly", data)
            else:
                self.log_result("Upload Offline Data", False, f"Status {response.status_code}", response.json())
                
        except Exception as e:
            self.log_result("Upload Offline Data", False, f"Exception: {str(e)}")

        # Test get pending syncs
        try:
            response = requests.get(f"{API_BASE}/sync/pending", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                if "syncs" in data:
                    self.log_result("Get Pending Syncs", True, f"Found {len(data['syncs'])} pending syncs")
                else:
                    self.log_result("Get Pending Syncs", False, "Syncs list not properly formatted", data)
            else:
                self.log_result("Get Pending Syncs", False, f"Status {response.status_code}", response.json())
                
        except Exception as e:
            self.log_result("Get Pending Syncs", False, f"Exception: {str(e)}")

        # Test process sync
        if self.sync_id:
            try:
                response = requests.post(f"{API_BASE}/sync/{self.sync_id}/process", 
                                       headers=self.get_headers(),
                                       json={"status": "processed"})
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success") and data.get("sync", {}).get("status") == "processed":
                        self.log_result("Process Sync", True, "Sync processed successfully")
                    else:
                        self.log_result("Process Sync", False, "Sync not processed properly", data)
                else:
                    self.log_result("Process Sync", False, f"Status {response.status_code}", response.json())
                    
            except Exception as e:
                self.log_result("Process Sync", False, f"Exception: {str(e)}")

    def test_biometric_endpoints(self):
        """Test biometric face matching endpoints (structure only)"""
        print("\n=== BIOMETRIC ENDPOINTS ===")
        
        # Test get liveness challenge (no auth required)
        try:
            response = requests.get(f"{API_BASE}/biometric/liveness-challenge")
            
            if response.status_code == 200:
                data = response.json()
                if "session_id" in data and "challenge" in data:
                    self.log_result("Get Liveness Challenge", True, f"Challenge: {data['challenge']['challenge_id']}")
                else:
                    self.log_result("Get Liveness Challenge", False, "Challenge not properly formatted", data)
            else:
                self.log_result("Get Liveness Challenge", False, f"Status {response.status_code}", response.json())
                
        except Exception as e:
            self.log_result("Get Liveness Challenge", False, f"Exception: {str(e)}")

    def test_emniyet_bildirimleri(self):
        """Test Emniyet bildirimleri endpoint"""
        print("\n=== EMNIYET BILDIRIMLERI ===")
        
        try:
            response = requests.get(f"{API_BASE}/tc-kimlik/emniyet-bildirimleri", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                if "forms" in data:
                    self.log_result("Get Emniyet Bildirimleri", True, f"Found {len(data['forms'])} forms")
                else:
                    self.log_result("Get Emniyet Bildirimleri", False, "Forms list not properly formatted", data)
            else:
                self.log_result("Get Emniyet Bildirimleri", False, f"Status {response.status_code}", response.json())
                
        except Exception as e:
            self.log_result("Get Emniyet Bildirimleri", False, f"Exception: {str(e)}")

    def test_health_and_guide(self):
        """Test health and API guide endpoints"""
        print("\n=== HEALTH & API GUIDE ===")
        
        # Test health endpoint
        try:
            response = requests.get(f"{API_BASE}/health")
            
            if response.status_code == 200:
                data = response.json()
                if data.get("version") == "3.0.0" and data.get("status") == "healthy":
                    self.log_result("Health Check", True, f"Version: {data.get('version')}, Status: {data.get('status')}")
                else:
                    self.log_result("Health Check", False, "Health check response incorrect", data)
            else:
                self.log_result("Health Check", False, f"Status {response.status_code}", response.json())
                
        except Exception as e:
            self.log_result("Health Check", False, f"Exception: {str(e)}")

        # Test API guide endpoint
        try:
            response = requests.get(f"{API_BASE}/guide")
            
            if response.status_code == 200:
                data = response.json()
                if data.get("version") == "3.0.0" and "endpoints" in data:
                    endpoint_count = len(data.get("endpoints", {}))
                    has_v3_endpoints = any(endpoint in data["endpoints"] for endpoint in 
                                         ["biyometrik", "tc_kimlik", "on_checkin", "multi_property", "kiosk", "offline_sync"])
                    if has_v3_endpoints:
                        self.log_result("API Guide", True, f"v3.0 guide with {endpoint_count} endpoint groups, includes new v3 features")
                    else:
                        self.log_result("API Guide", False, "Missing v3 endpoints in guide", data)
                else:
                    self.log_result("API Guide", False, "API guide response incorrect", data)
            else:
                self.log_result("API Guide", False, f"Status {response.status_code}", response.json())
                
        except Exception as e:
            self.log_result("API Guide", False, f"Exception: {str(e)}")

    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting Quick ID Reader v3.0 Backend API Tests")
        print(f"Backend URL: {BACKEND_URL}")
        
        # Login first
        if not self.test_login():
            print("❌ Login failed, cannot continue with authenticated tests")
            return False
            
        # Run all endpoint tests
        self.test_kvkk_public_consent()
        self.test_tc_kimlik_validation() 
        self.test_multi_property_management()
        self.test_precheckin_qr_system()
        self.test_kiosk_mode()
        self.test_offline_sync()
        self.test_biometric_endpoints()
        self.test_emniyet_bildirimleri()
        self.test_health_and_guide()
        
        # Print summary
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        
        passed = sum(1 for r in self.test_results if r["success"])
        total = len(self.test_results)
        
        print(f"✅ Passed: {passed}/{total}")
        print(f"❌ Failed: {total - passed}/{total}")
        
        if total - passed > 0:
            print("\n🔍 FAILED TESTS:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  • {result['test']}: {result['details']}")
        
        print(f"\n🎯 Overall Success Rate: {(passed/total)*100:.1f}%")
        
        return passed == total

if __name__ == "__main__":
    tester = APITester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)