#!/usr/bin/env python3
"""
Comprehensive test for AutoSamplerV2 implementation.
Tests all states, transitions, and command handling against hardware.
"""

import serial
import json
import time
import threading
from queue import Queue, Empty
from dataclasses import dataclass
from typing import Optional, Dict, List
import argparse


@dataclass
class TestResult:
    name: str
    passed: bool
    message: str
    duration: float


class AutoSamplerV2Tester:
    def __init__(self, port: str, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.message_queue = Queue()
        self.running = False
        self.reader_thread = None
        self.test_results: List[TestResult] = []
        
        # Test configuration
        self.test_timeout = 30  # seconds
        self.short_hold_time = 0.01  # hours (36 seconds)
        self.test_delay = 10  # seconds for delayed run test
        
    def connect(self):
        """Connect to the device"""
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Allow connection to stabilize
            
            # Start message reader thread
            self.running = True
            self.reader_thread = threading.Thread(target=self._message_reader, daemon=True)
            self.reader_thread.start()
            
            print(f"✅ Connected to {self.port}")
            return True
        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from device"""
        self.running = False
        if self.reader_thread:
            self.reader_thread.join(timeout=2)
        if self.serial:
            self.serial.close()
        print("📴 Disconnected")
    
    def _message_reader(self):
        """Background thread to read messages from device"""
        while self.running:
            try:
                if self.serial and self.serial.in_waiting:
                    line = self.serial.readline().decode('utf-8').strip()
                    if line:
                        try:
                            msg = json.loads(line)
                            # Flatten nested system messages so filters can match top-level keys
                            if isinstance(msg, dict) and isinstance(msg.get("message"), dict):
                                flat = dict(msg)
                                flat.update(msg["message"])  # promote inner message fields
                                self.message_queue.put(flat)
                            else:
                                self.message_queue.put(msg)
                        except json.JSONDecodeError:
                            # Suppress noisy non-JSON logs
                            pass
                time.sleep(0.01)
            except Exception as e:
                if self.running:
                    print(f"⚠️  Reader error: {e}")
    
    def send_command(self, sampler_id: int, cmd: int, hold_time: float = 0, delay_seconds: int = 0):
        """Send command to specific sampler"""
        command = {
            "message_source": "proteus_test",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "message": {
                "command": "auto_sampler_cmd",
                "sampler_id": sampler_id,
                "cmd": cmd,
                "hold_time": hold_time,
                "delay_seconds": delay_seconds
            }
        }
        # Minimal send print
        print(f"📤 Sending auto_sampler_cmd to sampler {sampler_id}: cmd={cmd}, hold={hold_time}, delay={delay_seconds}")
        self.serial.write((json.dumps(command) + "\n").encode('utf-8'))
    
    def wait_for_message(self, timeout: float = 10, **filters) -> Optional[Dict]:
        """Wait for a message matching the given filters"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                message = self.message_queue.get(timeout=0.1)
                
                # Check if message matches all filters
                matches = True
                for key, value in filters.items():
                    if key not in message or message[key] != value:
                        matches = False
                        break
                
                if matches:
                    return message
                else:
                    # Put message back for other tests
                    self.message_queue.put(message)
                    
            except Empty:
                continue
        
        return None
    
    def wait_for_state(self, sampler_id: int, expected_state: str, timeout: float = 30) -> bool:
        """Wait for sampler to reach expected state"""
        print(f"⏳ Waiting for Sampler {sampler_id} to reach state: {expected_state}")
        message = self.wait_for_message(timeout=timeout, message_source="auto_sampler", sampler_id=sampler_id, status=expected_state)
        
        if message:
            print(f"✅ Sampler {sampler_id} reached state: {expected_state}")
            return True
        else:
            print(f"❌ Timeout waiting for state: {expected_state}")
            return False
    
    def run_test(self, test_func, test_name: str):
        """Run a single test and record results"""
        print(f"\n🧪 Running test: {test_name}")
        print("=" * 60)
        
        start_time = time.time()
        try:
            result = test_func()
            duration = time.time() - start_time
            
            if result:
                print(f"✅ PASSED: {test_name} ({duration:.1f}s)")
                self.test_results.append(TestResult(test_name, True, "Test passed", duration))
            else:
                print(f"❌ FAILED: {test_name} ({duration:.1f}s)")
                self.test_results.append(TestResult(test_name, False, "Test failed", duration))
                
        except Exception as e:
            duration = time.time() - start_time
            print(f"💥 ERROR: {test_name} - {e} ({duration:.1f}s)")
            self.test_results.append(TestResult(test_name, False, f"Exception: {e}", duration))
    
    def test_basic_connectivity(self) -> bool:
        """Test basic connectivity and initial state"""
        print("Testing basic connectivity...")
        
        # Wait for any auto sampler status
        message = self.wait_for_message(timeout=10, message_source="auto_sampler")
        if not message:
            print("❌ No status messages received")
            return False
        
        print(f"📨 Received auto_sampler system message")
        return True

    def test_all_idle(self) -> bool:
        """Ensure all samplers report waiting_for_command before running other tests"""
        for sid in [1, 2, 3]:
            if not self.wait_for_state(sid, "waiting_for_command", 20):
                return False
        return True
    
    def test_stop_command(self) -> bool:
        """Test STOP command"""
        print("Testing STOP command...")
        
        # Send STOP command to sampler 1
        self.send_command(1, 0)  # STOP = 0
        
        # Wait for waiting_for_command state
        return self.wait_for_state(1, "waiting_for_command", 10)
    
    def test_reset_command(self) -> bool:
        """Test RESET command (full cycle)"""
        print("Testing RESET command...")
        
        # Send RESET command
        self.send_command(1, 1)  # RESET = 1
        
        # Should go through: moving_to_bottom -> moving_to_home -> waiting_for_command
        states = ["moving_to_bottom", "moving_to_home", "waiting_for_command"]
        
        for state in states:
            if not self.wait_for_state(1, state, 30):
                return False
        
        return True
    
    def test_run_command(self) -> bool:
        """Test RUN command (full sampling cycle)"""
        print("Testing RUN command...")
        
        # Send RUN command with short hold time
        self.send_command(1, 2, hold_time=self.short_hold_time)  # RUN = 2
        
        # Should go through the full cycle
        states = [
            "moving_to_bottom",
            "holding_position", 
            "moving_to_top",
            "waiting_for_command"
        ]
        
        for state in states:
            timeout = 60 if state == "holding_position" else 30
            if not self.wait_for_state(1, state, timeout):
                return False
        
        return True
    
    def test_delayed_run_command(self) -> bool:
        """Test DELAYED_RUN command"""
        print("Testing DELAYED_RUN command...")
        
        # Send DELAYED_RUN command
        self.send_command(1, 3, hold_time=self.short_hold_time, delay_seconds=self.test_delay)  # DELAYED_RUN = 3
        
        # Should first go to delayed_run_waiting
        if not self.wait_for_state(1, "delayed_run_waiting", 10):
            return False
        
        print(f"⏳ Waiting {self.test_delay} seconds for delay to complete...")
        
        # Then should proceed with normal run cycle
        states = [
            "moving_to_bottom",
            "holding_position",
            "moving_to_top", 
            "waiting_for_command"
        ]
        
        for state in states:
            timeout = 60 if state == "holding_position" else (self.test_delay + 30)
            if not self.wait_for_state(1, state, timeout):
                return False
        
        return True
    
    def test_stop_during_operation(self) -> bool:
        """Test STOP command during operation"""
        print("Testing STOP during operation...")
        
        # Start a run
        self.send_command(1, 2, hold_time=1.0)  # Long hold time
        
        # Wait for it to start moving
        if not self.wait_for_state(1, "moving_to_bottom", 30):
            return False
        
        # Send STOP command
        time.sleep(2)  # Let it move for a bit
        self.send_command(1, 0)  # STOP
        
        # Should return to waiting
        return self.wait_for_state(1, "waiting_for_command", 10)
    
    def test_multiple_samplers(self) -> bool:
        """Test commanding multiple samplers simultaneously"""
        print("Testing multiple samplers...")
        
        # Send commands to all 3 samplers
        for sampler_id in [1, 2, 3]:
            self.send_command(sampler_id, 1)  # RESET all
        
        # Wait for all to complete reset
        for sampler_id in [1, 2, 3]:
            if not self.wait_for_state(sampler_id, "waiting_for_command", 60):
                print(f"❌ Sampler {sampler_id} failed to complete reset")
                return False
        
        print("✅ All samplers completed reset")
        return True
    
    def test_error_recovery(self) -> bool:
        """Test error state and recovery"""
        print("Testing error recovery...")
        
        # This test would need to simulate a timeout condition
        # For now, we'll test that RESET works from any state
        
        # Send RESET command (should work from any state)
        self.send_command(1, 1)  # RESET
        
        return self.wait_for_state(1, "waiting_for_command", 60)
    
    def run_all_tests(self):
        """Run all tests"""
        print("🚀 Starting AutoSamplerV2 Hardware Tests")
        print("=" * 60)
        
        # Test suite
        tests = [
            (self.test_basic_connectivity, "Basic Connectivity"),
            (self.test_all_idle, "All Samplers Idle"),
            (self.test_stop_command, "STOP Command (Sampler 1)"),
            (self.test_reset_command, "RESET Command (Sampler 1)"),
            (self.test_run_command, "RUN Command (Sampler 1)"),
            (self.test_delayed_run_command, "DELAYED_RUN Command (Sampler 1)"),
            (self.test_stop_during_operation, "STOP During Operation (Sampler 1)"),
            (self.test_multiple_samplers, "Multiple Samplers RESET"),
            (self.test_error_recovery, "Error Recovery (Sampler 1)"),
        ]
        
        # Run tests
        for test_func, test_name in tests:
            self.run_test(test_func, test_name)
            time.sleep(2)  # Brief pause between tests
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in self.test_results if r.passed)
        total = len(self.test_results)
        
        for result in self.test_results:
            status = "✅ PASS" if result.passed else "❌ FAIL"
            print(f"{status} {result.name:.<40} {result.duration:>6.1f}s")
            if not result.passed:
                print(f"     └─ {result.message}")
        
        print("-" * 60)
        print(f"Results: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        
        if passed == total:
            print("🎉 ALL TESTS PASSED!")
        else:
            print(f"⚠️  {total-passed} tests failed")


def main():
    parser = argparse.ArgumentParser(description="AutoSamplerV2 Hardware Test")
    parser.add_argument("--port", "-p", default="COM3", help="Serial port (default: COM3)")
    parser.add_argument("--baudrate", "-b", type=int, default=115200, help="Baudrate (default: 115200)")
    parser.add_argument("--test", "-t", help="Run specific test only")
    
    args = parser.parse_args()
    
    tester = AutoSamplerV2Tester(args.port, args.baudrate)
    
    if not tester.connect():
        return 1
    
    try:
        if args.test:
            # Run specific test
            test_methods = {
                "connectivity": tester.test_basic_connectivity,
                "stop": tester.test_stop_command,
                "reset": tester.test_reset_command,
                "run": tester.test_run_command,
                "delayed_run": tester.test_delayed_run_command,
                "stop_during": tester.test_stop_during_operation,
                "multiple": tester.test_multiple_samplers,
                "error": tester.test_error_recovery,
            }
            
            if args.test in test_methods:
                tester.run_test(test_methods[args.test], args.test)
            else:
                print(f"❌ Unknown test: {args.test}")
                print(f"Available tests: {', '.join(test_methods.keys())}")
                return 1
        else:
            # Run all tests
            tester.run_all_tests()
        
        tester.print_summary()
        
    finally:
        tester.disconnect()
    
    # Return exit code based on test results
    failed_tests = sum(1 for r in tester.test_results if not r.passed)
    return 0 if failed_tests == 0 else 1


if __name__ == "__main__":
    exit(main())
