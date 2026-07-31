# gps_pps_rtc_pll_improved_v2.py
# ESP32 + u-blox F9T
# PPS-disciplined RTC using phase+frequency PLL
#
# UART: TX=12, RX=14
# PPS: GPIO 27
#
# FIXES:
# - Configure F9T for proper 1Hz PPS output
# - Add PPS debouncing to reject noise
# - Validate PPS period before disciplining

from machine import UART, Pin, RTC
import time
import struct
import micropython

micropython.alloc_emergency_exception_buf(256)

# -----------------------------
# Configuration
# -----------------------------

UART_ID = 1
UART_BAUD = 115200 * 4
UART_TX = 12
UART_RX = 14

PPS_PIN = 27

MAX_PHASE_SLEW_US = 9999         # max phase correction per PPS
ALPHA = 0.008                    # PLL frequency gain - reduced for stability
KP = 0.8                         # Proportional gain - increased to dominate over stale integral
INTEGRAL_DECAY = 0.9999          # Integral decay factor to prevent long-term windup (0.9999 = ~1hr time constant)

LOCK_THRESHOLD_US = 50          # Phase error threshold for lock detection
LOCK_FREQ_THRESHOLD = 100       # Frequency offset threshold for lock detection
FEED_FORWARD = -400
# Debug/logging options
VERBOSE_PPS = False             # Print every PPS discipline event
PRINT_INTERVAL_SEC = 60         # How often to print summary stats
RUN_MONITORING = False          # Run main loop monitoring (can cause phase jumps)
VERIFY_ALIGNMENT = True         # Check GPS/RTC alignment via TIM_TM2 (adds overhead)

# PPS validation
PPS_MIN_PERIOD_US = 950_000     # Minimum valid PPS period (0.95s)
PPS_MAX_PERIOD_US = 1_050_000   # Maximum valid PPS period (1.05s)

# -----------------------------
# Constants
# -----------------------------

GPS_UNIX_OFFSET = -630720000 #315964800        # seconds
LEAP_SECONDS = 18                  # update if leap seconds change
SECONDS_PER_WEEK = 604800
NS_PER_MS = 1_000_000
NS_PER_SEC = 1_000_000_000


# -----------------------------
# Globals (IRQ-safe)
# -----------------------------

rtc = RTC()
pps_last_us = 0
pps_valid = False
pps_missed = False
first_pps_done = False
pps_count = 0
pps_invalid_count = 0

# PLL state
freq_offset_us_per_sec = 0
pll_locked = False
read_tim_tm2 = False            # Flag to trigger TIM_TM2 read after PPS

# -----------------------------
# PPS interrupt with debouncing
# -----------------------------

def pps_irq(pin):
    global pps_last_us, pps_valid, pps_missed, pps_count, pps_invalid_count, read_tim_tm2
    now = time.ticks_us()
    
    # Debounce: check if this is a valid 1Hz PPS
    if pps_valid:
        period = time.ticks_diff(now, pps_last_us)
        
        # Reject pulses that are too close together (noise or wrong frequency)
        if period < PPS_MIN_PERIOD_US:
            pps_invalid_count += 1
            if pps_invalid_count % 10 == 0:
                print(f"WARNING: Rejecting fast PPS pulse (period={period}us)")
            return
        
        # Detect missed pulses
        if period > PPS_MAX_PERIOD_US:
            pps_missed = True
            print(f"WARNING: PPS period too long ({period}us)")
    
    pps_last_us = now
    pps_valid = True
    pps_count += 1
    read_tim_tm2 = True  # Signal to read TIM_TM2
    discipline_rtc()

# -----------------------------
# UBX helpers
# -----------------------------

def ubx_checksum(data):
    a = b = 0
    for x in data:
        a = (a + x) & 0xFF
        b = (b + a) & 0xFF
    return a, b

def ubx_send(uart, cls, msg, payload=b''):
    hdr = struct.pack('<BBBBH', 0xB5, 0x62, cls, msg, len(payload))
    full = hdr[2:] + payload
    ck = ubx_checksum(full)
    uart.write(hdr + payload + bytes(ck))

def ubx_recv(uart, cls, msg, timeout_ms=500):
    buf = b''
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
        if uart.any():
            buf += uart.read(uart.any())
            while b'\xB5\x62' in buf:
                i = buf.index(b'\xB5\x62')
                if len(buf) < i + 6:
                    break
                _, _, rcls, rmsg, ln = struct.unpack_from('<BBBBH', buf, i)
                total = 6 + ln + 2
                if len(buf) < i + total:
                    break
                payload = buf[i+6:i+6+ln]
                ck = ubx_checksum(buf[i+2:i+6+ln])
                if buf[i+6+ln:i+8+ln] == bytes(ck):
                    if rcls == cls and rmsg == msg:
                        return payload
                buf = buf[i+total:]
    return None

def configure_f9t_pps(uart):
    """Configure F9T to output 1Hz PPS on TIMEPULSE pin"""
    print("Configuring F9T for 1Hz PPS output...")
    
    # CFG-TP5 (TimePulse 5) configuration for TIMEPULSE (TP1)
    # This sets up a 1Hz output with 100ms pulse width
    payload = struct.pack('<BBHHHIIIIIHH',
        0,           # tpIdx = 0 (TIMEPULSE)
        1,           # version = 1
        0,           # reserved1
        0,           # antCableDelay
        0,           # rfGroupDelay
        1,           # freqPeriod = 1 Hz
        1,           # freqPeriodLock = 1 Hz (locked to GNSS)
        100000,      # pulseLenRatio = 100ms (10% duty cycle)
        100000,      # pulseLenRatioLock = 100ms
        0,           # userConfigDelay
        0b11110111,  # flags: active=1, lockGnssFreq=1, lockedOtherSet=1, 
                     #        isFreq=0, isLength=1, alignToTow=1, polarity=1, gridUtcGnss=1
        0            # reserved2
    )
    
    ubx_send(uart, 0x06, 0x31, payload)
    time.sleep_ms(100)
    
    # Also send CFG-CFG to save configuration
    # Save to BBR, Flash, EEPROM
    payload = struct.pack('<III', 0, 0x1F1F, 0)  # Clear none, Save all, Load none
    ubx_send(uart, 0x06, 0x09, payload)
    time.sleep_ms(100)
    
    print("F9T PPS configuration sent")

def poll_gps_time(uart):
    """Poll GPS time via UBX-NAV-TIMEUTC"""
    if uart.any():
        uart.read(uart.any())

    ubx_send(uart, 0x01, 0x21)  # NAV-TIMEUTC
    p = ubx_recv(uart, 0x01, 0x21)
    print("p",p,len(p))
    if not p or len(p) < 20:
        print("return None")
        return None
    year, month, day, hour, minute, second, valid = struct.unpack_from('<HBBBBBB', p, 12)
    if not (valid & 0x04):
        
        return None
    return (year, month, day, hour, minute, second)

def poll_tim_tm2(uart):
    """Poll TIM-TM2 message to get GPS time at INT2/PPS edge
    
    Returns: (second, nanosecond) tuple or None if unavailable
    TIM-TM2 provides the GPS time-of-week and sub-second info when INT2 triggered
    """
    ubx_send(uart, 0x0D, 0x03)  # TIM-TM2
    p = ubx_recv(uart, 0x0D, 0x03, timeout_ms=200)
    
    if not p or len(p) < 28:
        return None
    
    # Parse TIM-TM2 payload
    # ch, flags, count, wnR, wnF, towMsR, towSubMsR, towMsF, towSubMsF, accEst
    ch, flags = struct.unpack_from('<BB', p, 0)
    
    # Check if valid measurement
    if not (flags & 0x01):  # Check timeBase bit
        return None
    
    # Get time-of-week at rising edge (when PPS fired)
    towMsR = struct.unpack_from('<I', p, 8)[0]  # milliseconds
    towSubMsR = struct.unpack_from('<I', p, 12)[0]  # sub-milliseconds (scaled nanoseconds)
    
    # Convert to seconds and nanoseconds
    # towSubMsR is in units of 2^-32 seconds
    total_ns = (towMsR * 1_000_000) + int((towSubMsR / 4294967296.0) * 1_000_000_000)
    
    # Extract just the second within the minute
    total_seconds = total_ns // 1_000_000_000
    second_in_minute = total_seconds % 60
    nanosecond = total_ns % 1_000_000_000
    
    return (second_in_minute, nanosecond)

# -----------------------------
# Initial alignment
# -----------------------------

def init_time(uart):
    global first_pps_done, pps_valid
    
    #uart = UART(UART_ID, baudrate=UART_BAUD, tx=Pin(UART_TX), rx=Pin(UART_RX), rxbuf=8192, timeout=100)
    
    # Note: F9T PPS should be configured manually to 1Hz using u-center
    # The configure_f9t_pps() function doesn't work reliably
    
    # Set up PPS interrupt
    pps = Pin(PPS_PIN, Pin.IN)
    pps.irq(trigger=Pin.IRQ_RISING, handler=pps_irq)

    print("Waiting for GPS fix and 1Hz PPS alignment...")
    
    while True:
        pps_valid = False
        
        t = poll_gps_time(uart)
        print("t",t)
        if t is None:
            print("Waiting for GPS fix...")
            time.sleep_ms(500)
            continue
            
        print(f"GPS time: {t[0]}-{t[1]:02d}-{t[2]:02d} {t[3]:02d}:{t[4]:02d}:{t[5]:02d}")
        
        # Wait for next PPS with timeout
        timeout = time.ticks_add(time.ticks_ms(), 1500)
        while not pps_valid:
            if time.ticks_diff(time.ticks_ms(), timeout) > 0:
                print("PPS timeout, retrying...")
                break
            time.sleep_ms(1)
        
        if pps_valid:
            # Increment second for PPS edge
            ss = t[5] + 1
            mm = t[4]
            hh = t[3]
            dd = t[2]
            mon = t[1]
            yy = t[0]
            
            if ss >= 60:
                ss = 0
                mm += 1
                if mm >= 60:
                    mm = 0
                    hh += 1
                    if hh >= 24:
                        hh = 0
                        print("WARNING: Init crossed day boundary")
            
            rtc.datetime((yy, mon, dd, 0, hh, mm, ss, 0))
            print(f"RTC initialized: {yy}-{mon:02d}-{dd:02d} {hh:02d}:{mm:02d}:{ss:02d}.000000")
            print("RTC seconds aligned to GPS at PPS edge")
            first_pps_done = True
            break
    
    return uart

# -----------------------------
# RTC discipline
# -----------------------------
'''
def discipline_rtc():
    global first_pps_done, freq_offset_us_per_sec, pll_locked

    if not pps_valid:
        return

    y, m, d, wd, hh, mm, ss, rtc_us = rtc.datetime()

    # Phase error
    error = rtc_us
    if error > 500_000:
        error -= 1_000_000

    if not first_pps_done:
        rtc.datetime((y, m, d, wd, hh, mm, ss, 0))
        print("Emergency PPS alignment")
        first_pps_done = True
        return

    # PI controller with integral decay
    phase_correction = int(KP * error)
    
    # Apply integral decay to prevent long-term windup from stale history
    # This gives more weight to recent errors than old ones
    freq_offset_us_per_sec *= INTEGRAL_DECAY
    
    # Integral term with anti-windup protection
    # Only accumulate if phase correction isn't saturating
    if abs(phase_correction + int(freq_offset_us_per_sec)) < MAX_PHASE_SLEW_US * 0.9:
        freq_offset_us_per_sec += -370+ ALPHA * error
        freq_offset_us_per_sec = (freq_offset_us_per_sec +370) +ALPHA*error
    # Clamp integral term to prevent runaway
    freq_offset_us_per_sec = max(-999, min(999, freq_offset_us_per_sec))
    
    total_correction = phase_correction + int(freq_offset_us_per_sec) + FEED_FORWARD
    total_correction = max(-MAX_PHASE_SLEW_US, min(MAX_PHASE_SLEW_US, total_correction))

    # Apply correction to RTC microseconds
    new_us = rtc_us - total_correction
    new_ss = ss
    new_mm = mm
    new_hh = hh
    
    # Handle microsecond wraparound with proper second adjustment
    if new_us < 0:
        new_us += 1_000_000
        new_ss -= 1
        if new_ss < 0:
            new_ss = 59
            new_mm -= 1
            if new_mm < 0:
                new_mm = 59
                new_hh -= 1
                if new_hh < 0:
                    new_hh = 23
                    # Not handling day decrement for simplicity
    elif new_us >= 1_000_000:
        new_us -= 1_000_000
        new_ss += 1
        if new_ss >= 60:
            new_ss = 0
            new_mm += 1
            if new_mm >= 60:
                new_mm = 0
                new_hh += 1
                if new_hh >= 24:
                    new_hh = 0
                    # Not handling day increment for simplicity
    
    rtc.datetime((y, m, d, wd, new_hh, new_mm, new_ss, new_us))

    # Lock detection
    was_locked = pll_locked
    if abs(error) < LOCK_THRESHOLD_US and abs(freq_offset_us_per_sec) < LOCK_FREQ_THRESHOLD:
        if not pll_locked:
            pll_locked = True
            print("*** PLL LOCKED ***")
    else:
        if pll_locked:
            pll_locked = False
            print("*** PLL UNLOCKED ***")

    # Print status based on verbosity settings
    if VERBOSE_PPS:
        # Print every PPS (causes jitter due to serial overhead!)
        lock_indicator = "LOCK" if pll_locked else "    "
        print(f"[{lock_indicator}] Phase: {error:+6d}us | P: {phase_correction:+6d} | I: {int(freq_offset_us_per_sec):+6d} | Total: {total_correction:+6d} | sec: {new_ss:02d} | PPS#{pps_count}")
    elif pps_count % 10 == 0 or was_locked != pll_locked:
        # Print every 10 seconds or on lock status change
        lock_indicator = "LOCK" if pll_locked else "    "
        print(f"[{lock_indicator}] Phase: {error:+6d}us | P: {phase_correction:+6d} | I: {int(freq_offset_us_per_sec):+6d} | Total: {total_correction:+6d} | sec: {new_ss:02d} | PPS#{pps_count}")
'''

def discipline_rtc():
    """
    Disciplines the ESP32 RTC using PPS with phase+frequency PLL.
    Safely handles wraparound across microseconds, seconds, minutes, hours, days, months, and years.
    """
    global first_pps_done, freq_offset_us_per_sec, pll_locked

    if not pps_valid:
        return

    # Read current RTC datetime
    y, m, d, wd, hh, mm, ss, rtc_us = rtc.datetime()

    # Phase error in microseconds
    error = rtc_us
    if error > 500_000:
        error -= 1_000_000

    # Emergency alignment on first PPS
    if not first_pps_done:
        rtc.datetime((y, m, d, wd, hh, mm, ss, 0))
        first_pps_done = True
        return

    # PI controller with decay
    phase_correction = int(KP * error)
    freq_offset_us_per_sec *= INTEGRAL_DECAY

    # Integral term with anti-windup
    if abs(phase_correction + int(freq_offset_us_per_sec)) < MAX_PHASE_SLEW_US * 0.9:
        freq_offset_us_per_sec += -370 + ALPHA * error
        freq_offset_us_per_sec = (freq_offset_us_per_sec + 370) + ALPHA * error

    freq_offset_us_per_sec = max(-999, min(999, freq_offset_us_per_sec))

    total_correction = max(-MAX_PHASE_SLEW_US, min(MAX_PHASE_SLEW_US,
                         phase_correction + int(freq_offset_us_per_sec) + FEED_FORWARD))

    # Apply correction
    new_us = rtc_us - total_correction
    new_ss, new_mm, new_hh, new_d, new_m, new_y = ss, mm, hh, d, m, y

    # Microsecond → second wrap
    if new_us < 0:
        new_us += 1_000_000
        new_ss -= 1
    elif new_us >= 1_000_000:
        new_us -= 1_000_000
        new_ss += 1

    # Second → minute wrap
    if new_ss < 0:
        new_ss += 60
        new_mm -= 1
    elif new_ss >= 60:
        new_ss -= 60
        new_mm += 1

    # Minute → hour wrap
    if new_mm < 0:
        new_mm += 60
        new_hh -= 1
    elif new_mm >= 60:
        new_mm -= 60
        new_hh += 1

    # Hour → day wrap
    if new_hh < 0:
        new_hh += 24
        new_d -= 1
    elif new_hh >= 24:
        new_hh -= 24
        new_d += 1

    # Day → month/year wrap with leap year handling
    def days_in_month(year, month):
        if month == 2:
            return 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28
        return [31,28,31,30,31,30,31,31,30,31,30,31][month-1]

    if new_d < 1:
        new_m -= 1
        if new_m < 1:
            new_m = 12
            new_y -= 1
        new_d = days_in_month(new_y, new_m)
    elif new_d > days_in_month(new_y, new_m):
        new_d = 1
        new_m += 1
        if new_m > 12:
            new_m = 1
            new_y += 1

    # Optional: recompute weekday if needed
    import utime
    new_wd = utime.localtime(utime.mktime((new_y, new_m, new_d, new_hh, new_mm, new_ss, 0, 0)))[6]

    # Update RTC
    rtc.datetime((new_y, new_m, new_d, new_wd, new_hh, new_mm, new_ss, new_us))

    # Lock detection
    was_locked = pll_locked
    if abs(error) < LOCK_THRESHOLD_US and abs(freq_offset_us_per_sec) < LOCK_FREQ_THRESHOLD:
        if not pll_locked:
            pll_locked = True
            print("*** PLL LOCKED ***")
    else:
        if pll_locked:
            pll_locked = False
            print("*** PLL UNLOCKED ***")

    # Optional debug print
    if VERBOSE_PPS:
        lock_indicator = "LOCK" if pll_locked else "    "
        print(f"[{lock_indicator}] Phase: {error:+6d}us | P: {phase_correction:+6d} | "
              f"I: {int(freq_offset_us_per_sec):+6d} | Total: {total_correction:+6d} | "
              f"sec: {new_ss:02d} | PPS#{pps_count}")
# -----------------------------
# Main loop
# -----------------------------

def main():
    global pps_missed, pps_invalid_count
    
    uart = init_time()
    
    print("\n=== PLL Running ===")
    print("Expecting 1Hz PPS pulses...")
    
    last_pps_count = pps_count
    last_check = time.ticks_ms()
    next_print = time.ticks_add(time.ticks_ms(), PRINT_INTERVAL_SEC * 1000)
    
    while True:
        # Non-blocking wait - just yield CPU, don't block
        time.sleep_ms(100)  # Short sleep to yield CPU without blocking interrupts
        
        now = time.ticks_ms()
        
        # Check if it's time for periodic status print
        if time.ticks_diff(now, next_print) >= 0:
            next_print = time.ticks_add(now, PRINT_INTERVAL_SEC * 1000)
            
            # Check for missed PPS
            if pps_missed:
                print("\n!!! PPS SIGNAL LOST OR IRREGULAR !!!")
                pps_missed = False
            
            # Check PPS rate
            elapsed = time.ticks_diff(now, last_check) / 1000.0
            pps_delta = pps_count - last_pps_count
            pps_rate = pps_delta / elapsed
            
            if pps_delta == 0:
                print("\n!!! WARNING: No valid PPS pulses received !!!")
            elif abs(pps_rate - 1.0) > 0.1:
                print(f"\nWARNING: PPS rate = {pps_rate:.2f} Hz (expected 1.0 Hz)")
                print(f"Received {pps_delta} pulses in {elapsed:.1f} seconds")
            
            if pps_invalid_count > 0:
                print(f"INFO: Rejected {pps_invalid_count} invalid PPS pulses")
            
            last_pps_count = pps_count
            last_check = now
            
            # Display RTC time
            y, m, d, wd, hh, mm, ss, us = rtc.datetime()
            lock_status = "LOCKED" if pll_locked else "unlocked"
            print(f"[{lock_status}] RTC: {y}-{m:02d}-{d:02d} {hh:02d}:{mm:02d}:{ss:02d}.{us:06d} | Freq: {freq_offset_us_per_sec:+.2f} us/s | PPS: {pps_count}")
    
    return uart  # Return uart for potential use

def run_minimal_with_verification(uart):
    """Run in minimal mode with optional TIM_TM2 verification"""
    global read_tim_tm2
    
    print("\n=== PLL Running in minimal mode ===")
    print("No monitoring loop - zero interference with PPS timing")
    if VERIFY_ALIGNMENT:
        print("TIM_TM2 verification enabled - checking GPS/RTC second alignment")
        print("Note: TIM_TM2 reports GPS time, adjusting for leap seconds")
    else:
        print("TIM_TM2 verification disabled - maximum performance")
    print("Press Ctrl+C to exit\n")
    
    # Current GPS-UTC offset (leap seconds)
    # As of 2026, this is 18 seconds (GPS is ahead of UTC)
    GPS_UTC_OFFSET = 18
    
    # Verification loop - check TIM_TM2 after PPS to verify second alignment
    while True:
        if VERIFY_ALIGNMENT and read_tim_tm2:
            read_tim_tm2 = False
            
            # Read TIM_TM2 to get GPS time at PPS edge
            tim_data = poll_tim_tm2(uart)
            
            if tim_data:
                gps_sec, gps_ns = tim_data
                
                # Convert GPS second to UTC second
                utc_sec = (gps_sec - GPS_UTC_OFFSET) % 60
                
                # Read RTC time
                y, m, d, wd, hh, mm, rtc_sec, rtc_us = rtc.datetime()
                
                # Compare seconds (RTC should be in UTC)
                sec_diff = (rtc_sec - utc_sec) % 60
                if sec_diff > 30:
                    sec_diff -= 60
                
                # Only print every 60 PPS (every minute) to avoid interference
                if pps_count % 60 == 0:
                    if sec_diff == 0:
                        print(f"✓ PPS#{pps_count}: RTC sec={rtc_sec:02d} GPS sec={gps_sec:02d} (UTC {utc_sec:02d}) ALIGNED | GPS ns={gps_ns} RTC us={rtc_us}")
                    else:
                        print(f"✗ PPS#{pps_count}: RTC sec={rtc_sec:02d} GPS sec={gps_sec:02d} (UTC {utc_sec:02d}) MISALIGNED by {sec_diff}s!")
        
        time.sleep_ms(100 if VERIFY_ALIGNMENT else 1000)  # Longer sleep when not verifying
        
        time.sleep_ms(50)  # Short sleep to avoid busy-waiting




# -----------------------------
# Convert RTC → GPS week/ms/subms
# 
def rtc_to_gps_wno_ms_subms():
    # Current UTC in nanoseconds
    unix_ns = time.time_ns()

    # Convert to seconds
    unix_sec = unix_ns // NS_PER_SEC
    sub_ns = unix_ns % NS_PER_SEC

    # Convert UTC → GPS seconds
    gps_sec = unix_sec - GPS_UNIX_OFFSET + LEAP_SECONDS

    # GPS week number
    gps_week = gps_sec // SECONDS_PER_WEEK

    # Time of week (seconds)
    tow_sec = gps_sec % SECONDS_PER_WEEK

    # Convert to milliseconds
    ms = tow_sec * 1000 + (sub_ns // NS_PER_MS)

    # Sub-millisecond remainder
    sub_ms = sub_ns % NS_PER_MS  # nanoseconds under 1 ms

    return gps_week, ms, sub_ms



if __name__ == "__main__":
    if RUN_MONITORING:
        main()
    else:
        # Minimal mode with TIM_TM2 verification
        uart = init_time()
        run_minimal_with_verification(uart)

version_num = "0.01"
# END_OF_FILE_PPS