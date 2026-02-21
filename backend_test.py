#!/usr/bin/env python3
"""
Quick ID Reader v4.0 Backend API Tests
Tests all new endpoints introduced in v4.0 including:
- Room Management
- Group Check-in 
- Guest Photo Capture
- Form-C Generation
- Monitoring Dashboard
- Backup/Restore
- OCR/Quality Check
- Compliance Reports
- Security Headers
"""

import requests
import base64
import json
import time
from datetime import datetime, timedelta

# Configuration
BASE_URL = "https://photo-capture-29.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@quickid.com"
ADMIN_PASSWORD = "admin123"

class QuickIDTester:
    def __init__(self):
        self.session = requests.Session()
        self.token = None
        self.test_guest_ids = []
        self.test_room_ids = []
        
    def authenticate(self):
        """Login and get Bearer token"""
        print("🔐 Authenticating...")
        response = self.session.post(f"{BASE_URL}/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if response.status_code == 200:
            data = response.json()
            self.token = data["token"]
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
            print(f"✅ Authenticated as {data['user']['name']} ({data['user']['role']})")
            return True
        else:
            print(f"❌ Authentication failed: {response.status_code} - {response.text}")
            return False
    
    def check_security_headers(self, response):
        """Check if security headers are present"""
        headers = response.headers
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
        }
        
        missing = []
        for header, expected in security_headers.items():
            if header not in headers:
                missing.append(header)
            elif headers[header] != expected:
                missing.append(f"{header} (expected: {expected}, got: {headers[header]})")
        
        if missing:
            print(f"⚠️  Missing security headers: {', '.join(missing)}")
            return False
        return True
    
    def generate_test_base64_image(self):
        """Generate small test base64 image"""
        # 1x1 red pixel PNG in base64
        return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAI9jU77zgAAAABJRU5ErkJggg=="
    
    def test_room_management(self):
        """Test Room Management endpoints"""
        print("\n🏨 Testing Room Management...")
        
        # 1. Get room types (public endpoint)
        print("Testing GET /api/rooms/types...")
        response = requests.get(f"{BASE_URL}/rooms/types")  # No auth needed
        if response.status_code == 200:
            types = response.json()
            print(f"✅ Room types: {types}")
        else:
            print(f"❌ Failed to get room types: {response.status_code}")
            
        # 2. Create room
        print("Testing POST /api/rooms...")
        room_data = {
            "room_number": "102",  # Use different room number to avoid conflict
            "room_type": "standard",
            "floor": 1,
            "capacity": 2
        }
        response = self.session.post(f"{BASE_URL}/rooms", json=room_data)
        if response.status_code == 200:
            room = response.json()["room"]
            self.test_room_ids.append(room["id"])
            print(f"✅ Created room {room['room_number']}")
            
            # 3. List rooms
            print("Testing GET /api/rooms...")
            response = self.session.get(f"{BASE_URL}/rooms")
            if response.status_code == 200:
                rooms = response.json()
                print(f"✅ Listed {rooms['total']} rooms")
            
            # 4. Get room stats
            print("Testing GET /api/rooms/stats...")
            response = self.session.get(f"{BASE_URL}/rooms/stats")
            if response.status_code == 200:
                stats = response.json()
                print(f"✅ Room stats: {stats}")
                
            # 5. Update room status
            print("Testing PATCH /api/rooms/{room_id}...")
            response = self.session.patch(f"{BASE_URL}/rooms/{room['id']}", json={"status": "occupied"})
            if response.status_code == 200:
                print("✅ Updated room status")
            else:
                print(f"❌ Failed to update room: {response.status_code}")
        else:
            print(f"❌ Failed to create room: {response.status_code} - {response.text}")
            
    def test_guest_photo(self):
        """Test Guest Photo endpoints"""
        print("\n📸 Testing Guest Photo...")
        
        # First create a guest to test with
        guest_data = {
            "first_name": "Hans",
            "last_name": "Mueller", 
            "id_number": "12345678901",
            "nationality": "Germany",
            "document_type": "passport",
            "kvkk_consent": True
        }
        
        response = self.session.post(f"{BASE_URL}/guests", json=guest_data)
        if response.status_code != 200:
            print(f"❌ Failed to create test guest: {response.status_code}")
            return
            
        guest = response.json()["guest"]
        guest_id = guest["id"]
        self.test_guest_ids.append(guest_id)
        
        # Test photo upload
        print(f"Testing POST /api/guests/{guest_id}/photo...")
        photo_data = {"image_base64": self.generate_test_base64_image()}
        response = self.session.post(f"{BASE_URL}/guests/{guest_id}/photo", json=photo_data)
        
        if response.status_code == 200:
            print("✅ Uploaded guest photo")
            
            # Test photo retrieval
            print(f"Testing GET /api/guests/{guest_id}/photo...")
            response = self.session.get(f"{BASE_URL}/guests/{guest_id}/photo")
            if response.status_code == 200:
                photo = response.json()
                print("✅ Retrieved guest photo")
            else:
                print(f"❌ Failed to get photo: {response.status_code}")
        else:
            print(f"❌ Failed to upload photo: {response.status_code} - {response.text}")
    
    def test_form_c(self):
        """Test Form-C generation for foreign guests"""
        print("\n📋 Testing Form-C Generation...")
        
        # Create a foreign guest
        guest_data = {
            "first_name": "Klaus",
            "last_name": "Weber",
            "id_number": "A12345678",
            "nationality": "Germany",
            "document_type": "passport",
            "birth_date": "1980-05-15",
            "gender": "M",
            "kvkk_consent": True
        }
        
        response = self.session.post(f"{BASE_URL}/guests", json=guest_data)
        if response.status_code != 200:
            print(f"❌ Failed to create foreign guest: {response.status_code}")
            return
            
        guest = response.json()["guest"]
        guest_id = guest["id"]
        self.test_guest_ids.append(guest_id)
        
        print(f"Testing GET /api/tc-kimlik/form-c/{guest_id}...")
        response = self.session.get(f"{BASE_URL}/tc-kimlik/form-c/{guest_id}")
        
        if response.status_code == 200:
            form_c = response.json()
            print("✅ Generated Form-C document")
            print(f"   Form type: {form_c.get('form_type')}")
        else:
            print(f"❌ Failed to generate Form-C: {response.status_code} - {response.text}")
    
    def test_group_checkin(self):
        """Test Group Check-in functionality"""
        print("\n👥 Testing Group Check-in...")
        
        # Create multiple guests first
        guest_ids = []
        for i in range(2):
            guest_data = {
                "first_name": f"Guest{i+1}",
                "last_name": "GroupTest",
                "id_number": f"GRP00{i+1}23456",
                "nationality": "Türkiye",
                "kvkk_consent": True
            }
            
            response = self.session.post(f"{BASE_URL}/guests", json=guest_data)
            if response.status_code == 200:
                guest_id = response.json()["guest"]["id"]
                guest_ids.append(guest_id)
                self.test_guest_ids.append(guest_id)
            else:
                print(f"❌ Failed to create guest {i+1}: {response.status_code}")
                return
        
        if len(guest_ids) < 2:
            print("❌ Need at least 2 guests for group check-in test")
            return
            
        print(f"Testing POST /api/guests/group-checkin with {len(guest_ids)} guests...")
        checkin_data = {"guest_ids": guest_ids}
        response = self.session.post(f"{BASE_URL}/guests/group-checkin", json=checkin_data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Group check-in successful: {result['successful_count']} guests")
        else:
            print(f"❌ Group check-in failed: {response.status_code} - {response.text}")
    
    def test_room_assignment(self):
        """Test room assignment functionality"""
        print("\n🔑 Testing Room Assignment...")
        
        if not self.test_room_ids or not self.test_guest_ids:
            print("❌ Need rooms and guests for assignment test")
            return
            
        room_id = self.test_room_ids[0]
        guest_id = self.test_guest_ids[0]
        
        # Test manual assignment
        print("Testing POST /api/rooms/assign...")
        assign_data = {"room_id": room_id, "guest_id": guest_id}
        response = self.session.post(f"{BASE_URL}/rooms/assign", json=assign_data)
        
        if response.status_code == 200:
            print("✅ Manual room assignment successful")
            
            # Test release room
            print(f"Testing POST /api/rooms/{room_id}/release...")
            response = self.session.post(f"{BASE_URL}/rooms/{room_id}/release")
            if response.status_code == 200:
                print("✅ Room released successfully")
        else:
            print(f"❌ Room assignment failed: {response.status_code} - {response.text}")
            
        # Test auto-assignment
        if len(self.test_guest_ids) > 1:
            guest_id = self.test_guest_ids[1]
            print("Testing POST /api/rooms/auto-assign...")
            auto_assign_data = {"guest_id": guest_id}
            response = self.session.post(f"{BASE_URL}/rooms/auto-assign", json=auto_assign_data)
            
            if response.status_code == 200:
                assignment = response.json()
                print(f"✅ Auto-assignment successful: Room {assignment.get('room', {}).get('room_number')}")
            else:
                print(f"❌ Auto-assignment failed: {response.status_code} - {response.text}")
    
    def test_monitoring_dashboard(self):
        """Test Monitoring Dashboard endpoints"""
        print("\n📊 Testing Monitoring Dashboard...")
        
        endpoints = [
            ("dashboard", "/api/monitoring/dashboard"),
            ("scan-stats", "/api/monitoring/scan-stats?days=30"),
            ("error-log", "/api/monitoring/error-log?days=7"),
            ("ai-costs", "/api/monitoring/ai-costs?days=30"),
        ]
        
        for name, endpoint in endpoints:
            print(f"Testing GET {endpoint}...")
            response = self.session.get(f"{BASE_URL.replace('/api', '')}{endpoint}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ {name} endpoint working")
            else:
                print(f"❌ {name} failed: {response.status_code} - {response.text}")
    
    def test_backup_restore(self):
        """Test Backup/Restore endpoints"""
        print("\n💾 Testing Backup/Restore...")
        
        # Test create backup
        print("Testing POST /api/admin/backup...")
        backup_data = {"description": "Test backup from API test"}
        response = self.session.post(f"{BASE_URL}/admin/backup", json=backup_data)
        
        if response.status_code == 200:
            backup = response.json()["backup"]
            print(f"✅ Backup created: {backup['description']}")
            
            # Test list backups
            print("Testing GET /api/admin/backups...")
            response = self.session.get(f"{BASE_URL}/admin/backups")
            if response.status_code == 200:
                backups = response.json()
                print(f"✅ Listed {backups['total']} backups")
                
        else:
            print(f"❌ Backup creation failed: {response.status_code} - {response.text}")
            
        # Test backup schedule
        print("Testing GET /api/admin/backup-schedule...")
        response = self.session.get(f"{BASE_URL}/admin/backup-schedule")
        if response.status_code == 200:
            schedule = response.json()
            print("✅ Retrieved backup schedule")
        else:
            print(f"❌ Backup schedule failed: {response.status_code}")
    
    def test_ocr_endpoints(self):
        """Test OCR and Quality Check endpoints"""
        print("\n🔍 Testing OCR Endpoints...")
        
        # Test OCR status
        print("Testing GET /api/scan/ocr-status...")
        response = requests.get(f"{BASE_URL}/scan/ocr-status")  # Public endpoint
        if response.status_code == 200:
            status = response.json()
            print(f"✅ OCR Status: {status}")
        else:
            print(f"❌ OCR status failed: {response.status_code}")
            
        # Test quality check
        print("Testing POST /api/scan/quality-check...")
        quality_data = {"image_base64": self.generate_test_base64_image()}
        response = self.session.post(f"{BASE_URL}/scan/quality-check", json=quality_data)
        
        if response.status_code == 200:
            quality = response.json()
            print(f"✅ Quality check completed: {quality.get('quality_checked', False)}")
        else:
            print(f"❌ Quality check failed: {response.status_code} - {response.text}")
    
    def test_compliance_reports(self):
        """Test Compliance Reports endpoint"""
        print("\n📑 Testing Compliance Reports...")
        
        print("Testing GET /api/compliance/reports...")
        response = self.session.get(f"{BASE_URL}/compliance/reports")
        
        if response.status_code == 200:
            reports = response.json()
            print("✅ Compliance reports generated")
            print(f"   Available reports: {len(reports.get('reports', []))}")
        else:
            print(f"❌ Compliance reports failed: {response.status_code} - {response.text}")
    
    def test_security_headers_sample(self):
        """Test that responses include security headers"""
        print("\n🔒 Testing Security Headers...")
        
        # Test on a sample authenticated endpoint
        response = self.session.get(f"{BASE_URL}/dashboard/stats")
        
        if response.status_code == 200:
            if self.check_security_headers(response):
                print("✅ Security headers present")
            else:
                print("❌ Security headers missing/incorrect")
        else:
            print(f"❌ Failed to test security headers: {response.status_code}")
    
    def cleanup_test_data(self):
        """Clean up test data created during tests"""
        print("\n🧹 Cleaning up test data...")
        
        # Delete test guests
        for guest_id in self.test_guest_ids:
            response = self.session.delete(f"{BASE_URL}/guests/{guest_id}")
            if response.status_code == 200:
                print(f"✅ Deleted guest {guest_id}")
                
        # Note: Rooms are typically not deleted in production systems
        # but we could add status updates to mark them as "maintenance" etc.
        
    def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting Quick ID Reader v4.0 API Tests")
        print(f"Backend URL: {BASE_URL}")
        print("=" * 60)
        
        if not self.authenticate():
            print("❌ Authentication failed - cannot proceed with tests")
            return False
            
        try:
            # Run all test suites
            self.test_room_management()
            self.test_guest_photo()
            self.test_form_c()
            self.test_group_checkin()
            self.test_room_assignment()
            self.test_monitoring_dashboard()
            self.test_backup_restore()
            self.test_ocr_endpoints()
            self.test_compliance_reports()
            self.test_security_headers_sample()
            
        except Exception as e:
            print(f"❌ Test execution failed: {str(e)}")
        
        finally:
            self.cleanup_test_data()
            
        print("\n" + "=" * 60)
        print("🏁 API Tests Completed")

def main():
    """Main test runner"""
    tester = QuickIDTester()
    tester.run_all_tests()

if __name__ == "__main__":
    main()