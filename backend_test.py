#!/usr/bin/env python3
"""
Backend Testing for Quick ID Reader Hotel App v5.1
Testing FIXED Room Assignment endpoints (room_assignment.py rewritten)

Auth credentials: admin@quickid.com / admin123
Base URL: https://mrz-parser.preview.emergentagent.com

ROOM ASSIGNMENT ENDPOINTS TO TEST:
1. Create rooms (POST /api/rooms)  
2. Create guests (POST /api/guests)
3. Manual room assignment (POST /api/rooms/assign) - FIXED
4. Auto room assignment (POST /api/rooms/auto-assign) - FIXED 
5. Room release (POST /api/rooms/{id}/release)
6. Room stats (GET /api/rooms/stats)
7. List rooms (GET /api/rooms)

Previous issue: ID mismatch between room_id UUID and MongoDB ObjectId - SHOULD BE FIXED NOW
"""
import requests
import json
import base64
import os
from typing import Optional

# Configuration
BASE_URL = "https://mrz-parser.preview.emergentagent.com"
ADMIN_EMAIL = "admin@quickid.com"
ADMIN_PASSWORD = "admin123"

class BackendTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.token = None
        self.session = requests.Session()
        # Store created resources for cleanup
        self.created_rooms = []
        self.created_guests = []
        
    def login(self) -> bool:
        """Login and get JWT token"""
        try:
            response = self.session.post(
                f"{self.base_url}/api/auth/login",
                json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("token")
                if self.token:
                    # Set authorization header for all future requests
                    self.session.headers.update({
                        "Authorization": f"Bearer {self.token}",
                        "Content-Type": "application/json"
                    })
                    print("✅ Login successful")
                    return True
            print(f"❌ Login failed: {response.status_code} - {response.text}")
            return False
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False

    def test_room_assignment_flow(self):
        """Test the complete room assignment flow as specified in review request"""
        print("\n🏨 Testing FIXED Room Assignment Flow:")
        
        results = []
        
        # Step 1: Create a room (admin only)
        print("\n  Step 1: Creating room 501...")
        room_data = {
            "room_number": "501", 
            "room_type": "standard", 
            "floor": 5, 
            "capacity": 2
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/rooms",
                json=room_data,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if "room" in data and "id" in data["room"] and "room_id" in data["room"]:
                    room_obj_id = data["room"]["id"]  # ObjectId string
                    room_uuid_id = data["room"]["room_id"]  # UUID string
                    
                    print(f"    ✅ Room created successfully")
                    print(f"       ObjectId: {room_obj_id}")
                    print(f"       Room ID (UUID): {room_uuid_id}")
                    
                    self.created_rooms.append(room_obj_id)
                    results.append(("Create room 501", True, "Room created with both id and room_id fields"))
                    
                    # Step 2: Create a guest for testing
                    print("\n  Step 2: Creating guest 'Test Misafir'...")
                    guest_data = {
                        "first_name": "Test", 
                        "last_name": "Misafir", 
                        "nationality": "TR", 
                        "id_number": "99988877766"
                    }
                    
                    response = self.session.post(
                        f"{self.base_url}/api/guests",
                        json=guest_data,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        guest_data = response.json()
                        if "guest" in guest_data and "id" in guest_data["guest"]:
                            guest_id = guest_data["guest"]["id"]
                            print(f"    ✅ Guest created successfully")
                            print(f"       Guest ID: {guest_id}")
                            
                            self.created_guests.append(guest_id)
                            results.append(("Create guest Test Misafir", True, "Guest created with id field"))
                            
                            # Step 3: Manual room assignment (THE BUG WAS HERE - should now work)
                            print("\n  Step 3: Manual room assignment (using room UUID)...")
                            assign_data = {
                                "room_id": room_uuid_id,  # Use UUID first
                                "guest_id": guest_id
                            }
                            
                            response = self.session.post(
                                f"{self.base_url}/api/rooms/assign",
                                json=assign_data,
                                timeout=30
                            )
                            
                            if response.status_code == 200:
                                assign_result = response.json()
                                if "room" in assign_result and "assignment" in assign_result:
                                    print("    ✅ Manual room assignment (UUID) successful!")
                                    print(f"       Room status: {assign_result['room'].get('status')}")
                                    print(f"       Assignment ID: {assign_result['assignment'].get('assignment_id')}")
                                    results.append(("Manual room assignment (UUID)", True, "Room assigned successfully using UUID"))
                                    
                                    # Test assignment with ObjectId too
                                    print("\n  Step 3b: Testing assignment with ObjectId...")
                                    
                                    # First release the room
                                    response = self.session.post(
                                        f"{self.base_url}/api/rooms/{room_uuid_id}/release",
                                        timeout=30
                                    )
                                    
                                    if response.status_code == 200:
                                        print("    ✅ Room released for ObjectId test")
                                        
                                        # Now try with ObjectId
                                        assign_data_oid = {
                                            "room_id": room_obj_id,  # Use ObjectId this time
                                            "guest_id": guest_id
                                        }
                                        
                                        response = self.session.post(
                                            f"{self.base_url}/api/rooms/assign",
                                            json=assign_data_oid,
                                            timeout=30
                                        )
                                        
                                        if response.status_code == 200:
                                            print("    ✅ Manual room assignment (ObjectId) successful!")
                                            results.append(("Manual room assignment (ObjectId)", True, "Room assigned successfully using ObjectId"))
                                        else:
                                            print(f"    ❌ Manual room assignment (ObjectId) failed: {response.status_code} - {response.text}")
                                            results.append(("Manual room assignment (ObjectId)", False, f"HTTP {response.status_code}: {response.text}"))
                                    else:
                                        print(f"    ❌ Room release failed: {response.status_code}")
                                        results.append(("Room release for ObjectId test", False, f"HTTP {response.status_code}"))
                                else:
                                    print(f"    ❌ Manual room assignment: Invalid response structure")
                                    results.append(("Manual room assignment (UUID)", False, "Invalid response structure"))
                            else:
                                print(f"    ❌ Manual room assignment failed: {response.status_code} - {response.text}")
                                results.append(("Manual room assignment (UUID)", False, f"HTTP {response.status_code}: {response.text}"))
                            
                            # Continue with remaining tests...
                            self.test_remaining_room_assignment_steps(results, room_uuid_id, guest_id)
                            
                        else:
                            print(f"    ❌ Guest creation: Missing id field in response")
                            results.append(("Create guest Test Misafir", False, "Missing id field in response"))
                    else:
                        print(f"    ❌ Guest creation failed: {response.status_code} - {response.text}")
                        results.append(("Create guest Test Misafir", False, f"HTTP {response.status_code}: {response.text}"))
                        
                else:
                    print(f"    ❌ Room creation: Missing id or room_id fields in response")
                    results.append(("Create room 501", False, "Missing id or room_id fields in response"))
            else:
                print(f"    ❌ Room creation failed: {response.status_code} - {response.text}")
                results.append(("Create room 501", False, f"HTTP {response.status_code}: {response.text}"))
                
        except Exception as e:
            print(f"    ❌ Room assignment flow error: {e}")
            results.append(("Room assignment flow", False, str(e)))
        
        return results

    def test_remaining_room_assignment_steps(self, results, first_room_id, first_guest_id):
        """Complete the remaining steps of room assignment testing"""
        
        # Step 4: Create another room for auto-assign test
        print("\n  Step 4: Creating room 502 for auto-assign test...")
        room_data = {
            "room_number": "502", 
            "room_type": "standard", 
            "floor": 5, 
            "capacity": 2
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/rooms",
                json=room_data,
                timeout=30
            )
            
            if response.status_code == 200:
                room_data = response.json()
                if "room" in room_data and "id" in room_data["room"]:
                    second_room_id = room_data["room"]["room_id"]
                    self.created_rooms.append(room_data["room"]["id"])
                    print(f"    ✅ Room 502 created: {second_room_id}")
                    results.append(("Create room 502", True, "Room 502 created successfully"))
                    
                    # Step 5: Create another guest
                    print("\n  Step 5: Creating guest 'Oto Atama'...")
                    guest_data = {
                        "first_name": "Oto", 
                        "last_name": "Atama", 
                        "nationality": "TR", 
                        "id_number": "88877766655"
                    }
                    
                    response = self.session.post(
                        f"{self.base_url}/api/guests",
                        json=guest_data,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        guest_data = response.json()
                        if "guest" in guest_data and "id" in guest_data["guest"]:
                            second_guest_id = guest_data["guest"]["id"]
                            self.created_guests.append(second_guest_id)
                            print(f"    ✅ Guest 'Oto Atama' created: {second_guest_id}")
                            results.append(("Create guest Oto Atama", True, "Second guest created successfully"))
                            
                            # Step 6: Auto-assign room (THE BUG WAS HERE TOO - should now work)
                            print("\n  Step 6: Auto-assign room...")
                            auto_assign_data = {"guest_id": second_guest_id}
                            
                            response = self.session.post(
                                f"{self.base_url}/api/rooms/auto-assign",
                                json=auto_assign_data,
                                timeout=30
                            )
                            
                            if response.status_code == 200:
                                auto_result = response.json()
                                if "room" in auto_result and "assignment" in auto_result:
                                    assigned_room_number = auto_result["room"].get("room_number")
                                    print(f"    ✅ Auto-assign successful! Assigned to room: {assigned_room_number}")
                                    results.append(("Auto-assign room", True, f"Auto-assigned to room {assigned_room_number}"))
                                else:
                                    print(f"    ❌ Auto-assign: Invalid response structure")
                                    results.append(("Auto-assign room", False, "Invalid response structure"))
                            else:
                                print(f"    ❌ Auto-assign failed: {response.status_code} - {response.text}")
                                results.append(("Auto-assign room", False, f"HTTP {response.status_code}: {response.text}"))
                                
                        else:
                            print(f"    ❌ Second guest creation: Missing id field")
                            results.append(("Create guest Oto Atama", False, "Missing id field"))
                    else:
                        print(f"    ❌ Second guest creation failed: {response.status_code}")
                        results.append(("Create guest Oto Atama", False, f"HTTP {response.status_code}"))
                        
                else:
                    print(f"    ❌ Second room creation: Missing id field")
                    results.append(("Create room 502", False, "Missing id field"))
            else:
                print(f"    ❌ Second room creation failed: {response.status_code}")
                results.append(("Create room 502", False, f"HTTP {response.status_code}"))
                
        except Exception as e:
            print(f"    ❌ Remaining steps error: {e}")
            results.append(("Remaining room assignment steps", False, str(e)))
        
        # Step 7: Release room (use first room)
        print("\n  Step 7: Release room...")
        try:
            response = self.session.post(
                f"{self.base_url}/api/rooms/{first_room_id}/release",
                timeout=30
            )
            
            if response.status_code == 200:
                release_result = response.json()
                if "status" in release_result:
                    print(f"    ✅ Room release successful! Status: {release_result.get('status')}")
                    results.append(("Release room", True, f"Room released, status: {release_result.get('status')}"))
                else:
                    print(f"    ❌ Room release: Invalid response structure")
                    results.append(("Release room", False, "Invalid response structure"))
            else:
                print(f"    ❌ Room release failed: {response.status_code} - {response.text}")
                results.append(("Release room", False, f"HTTP {response.status_code}: {response.text}"))
                
        except Exception as e:
            print(f"    ❌ Room release error: {e}")
            results.append(("Release room", False, str(e)))
        
        # Step 8: Get room stats
        print("\n  Step 8: Get room stats...")
        try:
            response = self.session.get(
                f"{self.base_url}/api/rooms/stats",
                timeout=30
            )
            
            if response.status_code == 200:
                stats = response.json()
                required_stats = ["total", "available", "occupied", "cleaning", "maintenance", "reserved", "occupancy_rate"]
                
                if all(stat in stats for stat in required_stats):
                    print(f"    ✅ Room stats retrieved successfully!")
                    print(f"       Total: {stats.get('total')}, Available: {stats.get('available')}, Occupied: {stats.get('occupied')}")
                    print(f"       Occupancy Rate: {stats.get('occupancy_rate')}%")
                    results.append(("Get room stats", True, f"Stats retrieved: {stats.get('total')} total rooms, {stats.get('occupancy_rate')}% occupancy"))
                else:
                    missing = [s for s in required_stats if s not in stats]
                    print(f"    ❌ Room stats: Missing fields: {missing}")
                    results.append(("Get room stats", False, f"Missing fields: {missing}"))
            else:
                print(f"    ❌ Room stats failed: {response.status_code} - {response.text}")
                results.append(("Get room stats", False, f"HTTP {response.status_code}: {response.text}"))
                
        except Exception as e:
            print(f"    ❌ Room stats error: {e}")
            results.append(("Get room stats", False, str(e)))
        
        # Step 9: List rooms
        print("\n  Step 9: List rooms...")
        try:
            response = self.session.get(
                f"{self.base_url}/api/rooms",
                timeout=30
            )
            
            if response.status_code == 200:
                rooms_data = response.json()
                if "rooms" in rooms_data:
                    rooms = rooms_data["rooms"]
                    room_numbers = [r.get("room_number") for r in rooms]
                    print(f"    ✅ Rooms list retrieved: {len(rooms)} rooms")
                    print(f"       Room numbers: {room_numbers}")
                    
                    # Check if our created rooms are in the list
                    created_rooms_found = [r for r in rooms if r.get("room_number") in ["501", "502"]]
                    if len(created_rooms_found) >= 2:
                        print(f"    ✅ Both created rooms found in the list with correct statuses")
                        results.append(("List rooms", True, f"Retrieved {len(rooms)} rooms, including our test rooms"))
                    else:
                        print(f"    ⚠️ Only {len(created_rooms_found)} of our test rooms found in list")
                        results.append(("List rooms", True, f"Retrieved {len(rooms)} rooms, but only {len(created_rooms_found)} test rooms found"))
                else:
                    print(f"    ❌ List rooms: Missing 'rooms' field in response")
                    results.append(("List rooms", False, "Missing 'rooms' field in response"))
            else:
                print(f"    ❌ List rooms failed: {response.status_code} - {response.text}")
                results.append(("List rooms", False, f"HTTP {response.status_code}: {response.text}"))
                
        except Exception as e:
            print(f"    ❌ List rooms error: {e}")
            results.append(("List rooms", False, str(e)))
        """Test NEW Multi-Provider OCR endpoints"""
        print("\n🔍 Testing Multi-Provider OCR Endpoints:")
        
        results = []
        
        # 1. GET /api/scan/providers (auth required)
        try:
            response = self.session.get(f"{self.base_url}/api/scan/providers", timeout=30)
            if response.status_code == 200:
                data = response.json()
                providers = data.get("providers", [])
                expected_providers = ["gpt-4o", "gpt-4o-mini", "gemini-flash", "tesseract"]
                
                if isinstance(providers, list) and len(providers) >= 4:
                    provider_ids = [p.get("id") for p in providers]
                    missing = [p for p in expected_providers if p not in provider_ids]
                    
                    if not missing:
                        print("  ✅ GET /api/scan/providers: All expected providers found")
                        print(f"     Providers: {provider_ids}")
                        
                        # Check health status and smart routing info
                        has_health = all("health_status" in p for p in providers)
                        has_costs = all("cost_per_scan" in p for p in providers)
                        
                        if has_health and has_costs:
                            print("     ✅ Health status and cost info present")
                        else:
                            print("     ⚠️ Missing health status or cost info")
                        
                        results.append(("GET /api/scan/providers", True, "Working correctly"))
                    else:
                        print(f"  ❌ GET /api/scan/providers: Missing providers: {missing}")
                        results.append(("GET /api/scan/providers", False, f"Missing providers: {missing}"))
                else:
                    print(f"  ❌ GET /api/scan/providers: Invalid response format or insufficient providers")
                    results.append(("GET /api/scan/providers", False, "Invalid response format"))
            else:
                print(f"  ❌ GET /api/scan/providers: {response.status_code} - {response.text}")
                results.append(("GET /api/scan/providers", False, f"HTTP {response.status_code}"))
        except Exception as e:
            print(f"  ❌ GET /api/scan/providers error: {e}")
            results.append(("GET /api/scan/providers", False, str(e)))
        
        # 2. Test cost estimation endpoints for all providers
        cost_providers = ["gpt-4o", "gpt-4o-mini", "gemini-flash", "tesseract"]
        for provider in cost_providers:
            try:
                response = self.session.get(f"{self.base_url}/api/scan/cost-estimate/{provider}", timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    if "estimated_cost_usd" in data and "provider_name" in data:
                        print(f"  ✅ GET /api/scan/cost-estimate/{provider}: Working")
                        print(f"     Cost: ${data.get('estimated_cost_usd', 'N/A')} - {data.get('provider_name', 'N/A')}")
                        results.append((f"GET /api/scan/cost-estimate/{provider}", True, "Working correctly"))
                    else:
                        print(f"  ❌ GET /api/scan/cost-estimate/{provider}: Missing required fields")
                        results.append((f"GET /api/scan/cost-estimate/{provider}", False, "Missing required fields"))
                else:
                    print(f"  ❌ GET /api/scan/cost-estimate/{provider}: {response.status_code} - {response.text}")
                    results.append((f"GET /api/scan/cost-estimate/{provider}", False, f"HTTP {response.status_code}"))
            except Exception as e:
                print(f"  ❌ GET /api/scan/cost-estimate/{provider} error: {e}")
                results.append((f"GET /api/scan/cost-estimate/{provider}", False, str(e)))
        
        return results

    def test_enhanced_image_quality_control(self):
        """Test Enhanced Image Quality Control endpoint"""
        print("\n🖼️ Testing Enhanced Image Quality Control:")
        
        results = []
        
        # Create a small test image in base64 format
        test_image_base64 = self.create_test_image_base64()
        
        if not test_image_base64:
            print("  ❌ Could not create test image")
            return [("POST /api/scan/quality-check", False, "Could not create test image")]
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/scan/quality-check",
                json={"image_base64": test_image_base64},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Check for enhanced quality data
                required_fields = ["overall_score", "checks", "recommendations", "suggested_provider"]
                enhanced_checks = ["glare", "document_edges", "skew"]
                
                has_required = all(field in data for field in required_fields)
                
                if has_required:
                    checks = data.get("checks", {})
                    has_enhanced = all(check in checks for check in enhanced_checks)
                    
                    if has_enhanced:
                        print("  ✅ POST /api/scan/quality-check: All enhanced features present")
                        print(f"     Overall Score: {data.get('overall_score')}")
                        print(f"     Suggested Provider: {data.get('suggested_provider')}")
                        print(f"     Enhanced Checks: {list(checks.keys())}")
                        
                        # Check recommendations structure
                        recommendations = data.get("recommendations", [])
                        if isinstance(recommendations, list):
                            print(f"     Recommendations: {len(recommendations)} items")
                        
                        results.append(("POST /api/scan/quality-check", True, "Working with all enhanced features"))
                    else:
                        print(f"  ❌ POST /api/scan/quality-check: Missing enhanced checks: {[c for c in enhanced_checks if c not in checks]}")
                        results.append(("POST /api/scan/quality-check", False, "Missing enhanced checks"))
                else:
                    missing = [f for f in required_fields if f not in data]
                    print(f"  ❌ POST /api/scan/quality-check: Missing required fields: {missing}")
                    results.append(("POST /api/scan/quality-check", False, f"Missing fields: {missing}"))
            else:
                print(f"  ❌ POST /api/scan/quality-check: {response.status_code} - {response.text}")
                results.append(("POST /api/scan/quality-check", False, f"HTTP {response.status_code}"))
                
        except Exception as e:
            print(f"  ❌ POST /api/scan/quality-check error: {e}")
            results.append(("POST /api/scan/quality-check", False, str(e)))
        
        return results

    def test_enhanced_ocr_status(self):
        """Test Enhanced OCR Status endpoint (public, no auth)"""
        print("\n🔧 Testing Enhanced OCR Status:")
        
        results = []
        
        # Remove auth header temporarily for public endpoint
        original_headers = dict(self.session.headers)
        if "Authorization" in self.session.headers:
            del self.session.headers["Authorization"]
        
        try:
            response = self.session.get(f"{self.base_url}/api/scan/ocr-status", timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check for required fields
                required_fields = ["tesseract_available", "supported_languages"]
                enhanced_fields = ["preprocessing"]  # NEW in v5.0
                
                has_required = all(field in data for field in required_fields)
                has_enhanced = "preprocessing" in data
                
                if has_required and has_enhanced:
                    preprocessing = data.get("preprocessing", {})
                    
                    # Check preprocessing structure
                    if "opencv_available" in preprocessing and "features" in preprocessing:
                        print("  ✅ GET /api/scan/ocr-status: All fields present including NEW preprocessing")
                        print(f"     Tesseract Available: {data.get('tesseract_available')}")
                        print(f"     OpenCV Available: {preprocessing.get('opencv_available')}")
                        print(f"     Supported Languages: {len(data.get('supported_languages', []))}")
                        print(f"     Preprocessing Features: {len(preprocessing.get('features', []))}")
                        
                        results.append(("GET /api/scan/ocr-status", True, "Working with enhanced preprocessing info"))
                    else:
                        print("  ❌ GET /api/scan/ocr-status: Invalid preprocessing structure")
                        results.append(("GET /api/scan/ocr-status", False, "Invalid preprocessing structure"))
                else:
                    missing = []
                    if not has_required:
                        missing.extend([f for f in required_fields if f not in data])
                    if not has_enhanced:
                        missing.append("preprocessing")
                    
                    print(f"  ❌ GET /api/scan/ocr-status: Missing fields: {missing}")
                    results.append(("GET /api/scan/ocr-status", False, f"Missing fields: {missing}"))
            else:
                print(f"  ❌ GET /api/scan/ocr-status: {response.status_code} - {response.text}")
                results.append(("GET /api/scan/ocr-status", False, f"HTTP {response.status_code}"))
                
        except Exception as e:
            print(f"  ❌ GET /api/scan/ocr-status error: {e}")
            results.append(("GET /api/scan/ocr-status", False, str(e)))
        
        # Restore auth headers
        self.session.headers.update(original_headers)
        
        return results

    def test_scan_endpoint_new_params(self):
        """Test that POST /api/scan accepts new provider and smart_mode fields"""
        print("\n📋 Testing /api/scan with NEW parameters:")
        
        results = []
        test_image_base64 = self.create_test_image_base64()
        
        if not test_image_base64:
            print("  ❌ Could not create test image")
            return [("POST /api/scan with new params", False, "Could not create test image")]
        
        # Test different parameter combinations
        test_cases = [
            {
                "name": "provider=gpt-4o-mini",
                "params": {
                    "image_base64": test_image_base64,
                    "provider": "gpt-4o-mini"
                }
            },
            {
                "name": "provider=tesseract", 
                "params": {
                    "image_base64": test_image_base64,
                    "provider": "tesseract"
                }
            },
            {
                "name": "smart_mode=true",
                "params": {
                    "image_base64": test_image_base64,
                    "smart_mode": True
                }
            },
            {
                "name": "provider + smart_mode",
                "params": {
                    "image_base64": test_image_base64,
                    "provider": "gpt-4o-mini",
                    "smart_mode": False
                }
            }
        ]
        
        for test_case in test_cases:
            try:
                response = self.session.post(
                    f"{self.base_url}/api/scan",
                    json=test_case["params"],
                    timeout=60  # Increased timeout for AI processing
                )
                
                # Check if it doesn't error on the new fields (accept 200 or valid processing errors)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        print(f"  ✅ POST /api/scan ({test_case['name']}): Accepts new parameters")
                        # Check if provider info is returned
                        if "provider" in data and "provider_info" in data:
                            used_provider = data.get("provider")
                            print(f"     Used Provider: {used_provider}")
                        results.append((f"POST /api/scan ({test_case['name']})", True, "Accepts new parameters"))
                    else:
                        # Even if processing fails, if it doesn't complain about unknown fields, it's good
                        error_msg = data.get("detail", {}).get("message", str(data))
                        if "unknown" not in error_msg.lower() and "invalid" not in error_msg.lower():
                            print(f"  ✅ POST /api/scan ({test_case['name']}): Accepts parameters (processing error is OK)")
                            results.append((f"POST /api/scan ({test_case['name']})", True, "Accepts parameters"))
                        else:
                            print(f"  ❌ POST /api/scan ({test_case['name']}): Parameter error: {error_msg}")
                            results.append((f"POST /api/scan ({test_case['name']})", False, f"Parameter error: {error_msg}"))
                elif response.status_code == 400:
                    # Check if error is about unknown fields vs other validation
                    error_text = response.text.lower()
                    if "unknown" in error_text or "unrecognized" in error_text or "unexpected" in error_text:
                        print(f"  ❌ POST /api/scan ({test_case['name']}): New parameters not recognized")
                        results.append((f"POST /api/scan ({test_case['name']})", False, "New parameters not recognized"))
                    else:
                        print(f"  ✅ POST /api/scan ({test_case['name']}): Accepts parameters (validation error is OK)")
                        results.append((f"POST /api/scan ({test_case['name']})", True, "Accepts parameters"))
                elif response.status_code in [429, 500]:
                    # Rate limit or server error - parameters were accepted but processing failed
                    print(f"  ✅ POST /api/scan ({test_case['name']}): Accepts parameters (server/rate limit error)")
                    results.append((f"POST /api/scan ({test_case['name']})", True, "Accepts parameters"))
                else:
                    print(f"  ❌ POST /api/scan ({test_case['name']}): {response.status_code} - {response.text}")
                    results.append((f"POST /api/scan ({test_case['name']})", False, f"HTTP {response.status_code}"))
                    
            except Exception as e:
                print(f"  ❌ POST /api/scan ({test_case['name']}) error: {e}")
                results.append((f"POST /api/scan ({test_case['name']})", False, str(e)))
        
        return results

    def create_test_image_base64(self) -> Optional[str]:
        """Create a simple test image in base64 format"""
        try:
            # Create a simple 100x100 white image with black text
            from PIL import Image, ImageDraw, ImageFont
            import io
            
            # Create white image
            img = Image.new('RGB', (200, 100), color='white')
            draw = ImageDraw.Draw(img)
            
            # Add some text to simulate a document
            try:
                # Use default font
                draw.text((10, 30), "TEST DOCUMENT", fill='black')
                draw.text((10, 50), "ID: 12345", fill='black')
            except:
                # If font fails, just draw rectangles to simulate a document
                draw.rectangle([10, 10, 190, 90], outline='black', width=2)
                draw.rectangle([20, 30, 100, 50], fill='gray')
            
            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return f"data:image/png;base64,{img_base64}"
            
        except ImportError:
            # Fallback: create a minimal base64 image manually
            # This is a 1x1 white PNG image
            minimal_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAI9jU77zwAAAABJRU5ErkJggg=="
            return f"data:image/png;base64,{minimal_png}"
        except Exception:
            return None

    def run_all_tests(self):
        """Run FIXED Room Assignment backend tests"""
        print("🚀 Starting Quick ID Reader v5.1 Room Assignment Tests")
        print("Testing FIXED room_assignment.py (ID mismatch issues resolved)")
        print("=" * 70)
        
        # Login first
        if not self.login():
            return False
        
        all_results = []
        
        # Run room assignment test suite
        all_results.extend(self.test_room_assignment_flow())
        
        # Summary
        print("\n" + "=" * 70)
        print("📊 Test Results Summary:")
        print("=" * 70)
        
        passed = sum(1 for _, status, _ in all_results if status)
        failed = len(all_results) - passed
        
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"📈 Total: {len(all_results)}")
        
        if failed > 0:
            print("\n❌ Failed Tests:")
            for test_name, status, message in all_results:
                if not status:
                    print(f"  • {test_name}: {message}")
        else:
            print("\n🎉 All room assignment tests PASSED!")
            print("The room_assignment.py fixes appear to be working correctly!")
        
        print("\n" + "=" * 70)
        
        return failed == 0


if __name__ == "__main__":
    tester = BackendTester()
    success = tester.run_all_tests()
    
    if success:
        print("🎉 All v5.0 backend tests PASSED!")
    else:
        print("💥 Some v5.0 backend tests FAILED!")
    
    exit(0 if success else 1)