# AutoSampler V2 Testing Guide

This guide explains how to test the new state-based AutoSampler V2 implementation against the hardware.

## 🏗️ Architecture Changes

### AutoSampler V1 (Current)
- Single class with large if-else chains
- Duplicate command handlers
- Inconsistent timing logic
- Hard to test individual states

### AutoSampler V2 (New)
- **State Pattern**: Each state is a separate class
- **Clean Transitions**: Explicit `enter()` and `exit()` methods
- **Consistent Interface**: All states implement same methods
- **Better Error Handling**: State-specific error recovery
- **Enhanced Delayed Run**: Proper timing and logging

## 📋 New Features in V2

### 1. Enhanced States
- `PowerOnState` - Initial startup
- `WaitingForCommandState` - Ready for commands
- `DelayedRunWaitingState` - **NEW** - Waiting for delay period
- `MovingToBottomResetState` - Moving to bottom for reset
- `MovingToBottomRunState` - Moving to bottom for sampling
- `HoldingPositionState` - Holding at bottom for sampling
- `MovingToHomeState` - Moving to home position
- `MovingToTopState` - Moving to top for extraction
- `ErrorState` - Error handling and recovery

### 2. Improved Command Handling
- Supports both `AutoSamplerCmds` objects and dictionaries
- Proper DELAYED_RUN implementation with timing
- State-specific command validation
- Better logging and status reporting

### 3. Better Status Reporting
- Structured status messages with timestamps
- State transition logging
- Progress reporting for delayed runs
- Error messages with context

## 🧪 Testing Strategy

### Phase 1: Unit Testing (Device Side)
Run the integration test on the device to compare V1 and V2 side by side.

### Phase 2: Hardware Testing (Proteus Side)
Use the comprehensive test suite to validate all functionality.

### Phase 3: Production Testing
Run both versions in parallel before switching over.

## 🚀 Running Tests

### 1. Device-Side Integration Test

```python
# On the MicroPython device
import uasyncio as asyncio
from controllers.auto_sampler_integration_test import main

# Run the comparison test
result = asyncio.run(main())
```

This will:
- Create both V1 and V2 samplers on different pins
- Test basic commands (STOP, RESET, RUN)
- Test delayed run functionality (V2 only)
- Monitor status messages
- Compare behavior and report results

### 2. Proteus-Side Hardware Test

```bash
# From Windows/Proteus side
cd proteus-plus/tests
python auto_sampler_v2_test.py --port COM3

# Run specific test
python auto_sampler_v2_test.py --port COM3 --test reset

# Available tests:
# - connectivity: Basic connectivity test
# - stop: STOP command test
# - reset: RESET command test  
# - run: RUN command test
# - delayed_run: DELAYED_RUN command test
# - stop_during: STOP during operation test
# - multiple: Multiple samplers test
# - error: Error recovery test
```

### 3. Test Configuration

#### Hardware Requirements
- 3 AutoSamplers connected to STM32 board
- Limit switches wired to configured pins
- Motor drivers connected to output pins
- Serial connection to Proteus/Windows

#### Test Parameters
```python
# Timing configuration
test_timeout = 30          # seconds
short_hold_time = 0.01     # hours (36 seconds)
test_delay = 10            # seconds for delayed run
```

## 📊 Expected Test Results

### Successful Test Output
```
🚀 Starting AutoSamplerV2 Hardware Tests
============================================================

🧪 Running test: Basic Connectivity
✅ PASSED: Basic Connectivity (2.1s)

🧪 Running test: STOP Command  
✅ PASSED: STOP Command (3.2s)

🧪 Running test: RESET Command
✅ PASSED: RESET Command (45.8s)

🧪 Running test: RUN Command
✅ PASSED: RUN Command (78.4s)

🧪 Running test: DELAYED_RUN Command
✅ PASSED: DELAYED_RUN Command (88.9s)

============================================================
📊 TEST SUMMARY
============================================================
✅ PASS Basic Connectivity.................... 2.1s
✅ PASS STOP Command......................... 3.2s  
✅ PASS RESET Command........................ 45.8s
✅ PASS RUN Command.......................... 78.4s
✅ PASS DELAYED_RUN Command.................. 88.9s
------------------------------------------------------------
Results: 8/8 tests passed (100.0%)
🎉 ALL TESTS PASSED!
```

## 🔧 Troubleshooting

### Common Issues

1. **Serial Communication**
   - Ensure correct COM port
   - Check baudrate (115200)
   - Verify cable connections

2. **Hardware Issues**
   - Check limit switch wiring
   - Verify motor driver connections
   - Test individual GPIO pins

3. **Timing Issues**
   - Adjust test timeouts for slower hardware
   - Check hold time conversions
   - Verify delay timing accuracy

4. **State Transition Issues**
   - Check sensor readings
   - Verify state transition logic
   - Review error logs

### Debug Commands

```python
# Check sensor states
sampler.get_sensor_state()

# Check current state
sampler.current_state.get_name()

# Manual motor control
sampler.go_up()
sampler.go_down()
sampler.stop()
```

## 📈 Migration Plan

### Step 1: Parallel Testing
- Run both V1 and V2 simultaneously
- Compare behavior and performance
- Validate all commands work correctly

### Step 2: Hardware Validation
- Test with real hardware setup
- Verify timing accuracy
- Check sensor integration

### Step 3: Production Switch
- Update main.py to use AutoSamplerV2
- Remove AutoSampler V1 code
- Update any dependent code

### Step 4: Cleanup
- Remove old files
- Update documentation
- Archive test results

## 🎯 Success Criteria

Before switching to V2, ensure:

- ✅ All hardware tests pass
- ✅ Timing accuracy matches V1
- ✅ No regression in functionality
- ✅ Better error handling works
- ✅ Delayed run feature works correctly
- ✅ Memory usage is acceptable
- ✅ Performance is equal or better

## 📞 Support

If tests fail or you encounter issues:

1. Check hardware connections
2. Review test logs for specific errors
3. Run individual tests to isolate problems
4. Compare V1 vs V2 behavior using integration test
5. Check sensor readings and state transitions

The new state-based design should be more reliable and easier to debug than the original implementation.
