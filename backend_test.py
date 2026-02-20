#!/usr/bin/env python3

import requests
import sys
import json
import base64
import os
from datetime import datetime
from io import BytesIO
from PIL import Image

class QuickIDAPITester:
    def __init__(self, base_url="https://quick-id-scan.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.guest_id = None
        
    def log(self, message):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        
    def run_test(self, name, method, endpoint, expected_status, data=None, timeout=30):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        self.tests_run += 1
        self.log(f"🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=headers, timeout=timeout)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=timeout)
            else:
                raise ValueError(f"Unsupported method: {method}")

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ {name} - Status: {response.status_code}")
                try:
                    return True, response.json()
                except:
                    return True, response.text
            else:
                self.log(f"❌ {name} - Expected {expected_status}, got {response.status_code}")
                try:
                    error_detail = response.json().get('detail', 'Unknown error')
                    self.log(f"   Error: {error_detail}")
                except:
                    self.log(f"   Response: {response.text[:200]}")
                return False, {}

        except requests.exceptions.Timeout:
            self.log(f"❌ {name} - Request timeout ({timeout}s)")
            return False, {}
        except Exception as e:
            self.log(f"❌ {name} - Error: {str(e)}")
            return False, {}

    def create_test_image(self):
        """Create a test image with realistic content for ID scanning"""
        # Create a simple test image with text-like elements (simulating an ID card)
        img = Image.new('RGB', (400, 250), color='white')
        
        # Add some colored rectangles to simulate ID card elements
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(img)
        
        # Background blue stripe (like many ID cards have)
        draw.rectangle([0, 0, 400, 50], fill='#003f7f')
        
        # Simulate text areas with colored blocks
        draw.rectangle([20, 70, 180, 90], fill='#333333')  # Name field
        draw.rectangle([20, 100, 120, 120], fill='#666666')  # ID field  
        draw.rectangle([20, 130, 100, 150], fill='#999999')  # Date field
        draw.rectangle([250, 70, 370, 180], fill='#cccccc')  # Photo area
        
        # Add some text-like noise
        for i in range(5):
            for j in range(10):
                x = 25 + j * 15
                y = 75 + i * 20
                draw.rectangle([x, y, x+10, y+2], fill='#000000')
        
        # Convert to base64
        buffer = BytesIO()
        img.save(buffer, format='JPEG')
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return f"data:image/jpeg;base64,{img_base64}"

    def test_health(self):
        """Test health endpoint"""
        success, response = self.run_test("Health Check", "GET", "api/health", 200)
        if success and response.get('status') == 'healthy':
            return True
        self.log("❌ Health endpoint did not return healthy status")
        return False

    def test_dashboard_stats(self):
        """Test dashboard stats endpoint"""
        success, response = self.run_test("Dashboard Stats", "GET", "api/dashboard/stats", 200)
        if success and isinstance(response, dict):
            required_fields = ['total_guests', 'today_checkins', 'today_checkouts', 'pending_reviews']
            missing_fields = [f for f in required_fields if f not in response]
            if missing_fields:
                self.log(f"❌ Dashboard stats missing fields: {missing_fields}")
                return False
            self.log(f"   📊 Stats: {response['total_guests']} guests, {response['today_checkins']} checkins")
            return True
        return False

    def test_scan_endpoint(self):
        """Test scan endpoint with real image"""
        self.log("🖼️  Creating test image for scanning...")
        test_image = self.create_test_image()
        
        # The scan endpoint takes time, use longer timeout
        success, response = self.run_test(
            "Scan ID Document", "POST", "api/scan", 200, 
            {"image_base64": test_image}, timeout=15
        )
        
        if success and response.get('success'):
            self.log(f"   📋 Scan ID: {response.get('scan', {}).get('id', 'N/A')}")
            extracted = response.get('extracted_data', {})
            self.log(f"   🔍 Valid: {extracted.get('is_valid', False)}")
            self.log(f"   📄 Doc Type: {extracted.get('document_type', 'N/A')}")
            return True, response
        return False, {}

    def test_guest_crud(self):
        """Test complete guest CRUD operations"""
        # Create guest
        guest_data = {
            "first_name": "Test",
            "last_name": "User", 
            "id_number": "12345678901",
            "birth_date": "1990-01-01",
            "gender": "M",
            "nationality": "TR",
            "document_type": "tc_kimlik",
            "notes": "Test guest created by automation"
        }
        
        success, response = self.run_test("Create Guest", "POST", "api/guests", 200, guest_data)
        if not success:
            return False
            
        guest = response.get('guest', {})
        self.guest_id = guest.get('id')
        if not self.guest_id:
            self.log("❌ No guest ID returned from create")
            return False
            
        self.log(f"   👤 Created guest ID: {self.guest_id}")
        
        # Get single guest
        success, response = self.run_test("Get Single Guest", "GET", f"api/guests/{self.guest_id}", 200)
        if not success:
            return False
            
        # Update guest
        update_data = {"notes": "Updated by automation test"}
        success, response = self.run_test("Update Guest", "PATCH", f"api/guests/{self.guest_id}", 200, update_data)
        if not success:
            return False
            
        # Get guest list
        success, response = self.run_test("Get Guest List", "GET", "api/guests?page=1&limit=10", 200)
        if success and 'guests' in response:
            self.log(f"   📋 Found {len(response['guests'])} guests, total: {response.get('total', 0)}")
        else:
            return False
            
        # Test search
        success, response = self.run_test("Search Guests", "GET", "api/guests?search=Test&status=pending", 200)
        if not success:
            return False
            
        return True

    def test_checkin_checkout(self):
        """Test check-in and check-out operations"""
        if not self.guest_id:
            self.log("❌ No guest ID available for check-in/out tests")
            return False
            
        # Check-in
        success, response = self.run_test("Guest Check-in", "POST", f"api/guests/{self.guest_id}/checkin", 200)
        if success:
            status = response.get('guest', {}).get('status')
            self.log(f"   ✅ Guest status after check-in: {status}")
            if status != 'checked_in':
                self.log("❌ Guest status not updated to checked_in")
                return False
        else:
            return False
            
        # Check-out  
        success, response = self.run_test("Guest Check-out", "POST", f"api/guests/{self.guest_id}/checkout", 200)
        if success:
            status = response.get('guest', {}).get('status')
            self.log(f"   ✅ Guest status after check-out: {status}")
            if status != 'checked_out':
                self.log("❌ Guest status not updated to checked_out")
                return False
        else:
            return False
            
        return True

    def test_exports(self):
        """Test export functionality"""
        # Test JSON export
        success, response = self.run_test("Export Guests JSON", "GET", "api/exports/guests.json", 200)
        if success and 'guests' in response:
            self.log(f"   📄 JSON Export: {len(response['guests'])} guests")
        else:
            return False
            
        # Test CSV export (returns different response type)
        try:
            url = f"{self.base_url}/api/exports/guests.csv"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                self.tests_passed += 1
                self.log("✅ Export Guests CSV - Status: 200")
                content = response.text[:100].replace('\n', '\\n')
                self.log(f"   📄 CSV Content preview: {content}...")
                return True
            else:
                self.log(f"❌ Export Guests CSV - Expected 200, got {response.status_code}")
                return False
        except Exception as e:
            self.log(f"❌ Export Guests CSV - Error: {str(e)}")
            return False
        finally:
            self.tests_run += 1

    def test_cleanup(self):
        """Clean up test data"""
        if self.guest_id:
            success, response = self.run_test("Delete Test Guest", "DELETE", f"api/guests/{self.guest_id}", 200)
            if success:
                self.log(f"   🗑️  Cleaned up guest {self.guest_id}")
            return success
        return True

    def run_all_tests(self):
        """Run all backend API tests"""
        self.log("🚀 Starting Quick ID Reader API Tests")
        self.log(f"📍 Testing endpoint: {self.base_url}")
        
        test_results = {
            'health': self.test_health(),
            'dashboard_stats': self.test_dashboard_stats(), 
            'scan_endpoint': self.test_scan_endpoint()[0],  # Only get success bool
            'guest_crud': self.test_guest_crud(),
            'checkin_checkout': self.test_checkin_checkout(),
            'exports': self.test_exports(),
            'cleanup': self.test_cleanup()
        }
        
        # Print results summary
        self.log("\n" + "="*50)
        self.log("📊 TEST RESULTS SUMMARY")
        self.log("="*50)
        
        for test_name, passed in test_results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            self.log(f"{test_name.upper()}: {status}")
            
        self.log(f"\n📈 Overall: {self.tests_passed}/{self.tests_run} tests passed ({self.tests_passed/self.tests_run*100:.1f}%)")
        
        if self.tests_passed == self.tests_run:
            self.log("🎉 All tests passed!")
            return 0
        else:
            self.log(f"⚠️  {self.tests_run - self.tests_passed} tests failed")
            return 1

def main():
    """Main test runner"""
    backend_url = os.environ.get('REACT_APP_BACKEND_URL', 'https://quick-id-scan.preview.emergentagent.com')
    tester = QuickIDAPITester(backend_url)
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())