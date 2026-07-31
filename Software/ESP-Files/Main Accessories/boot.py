# This file is executed on every boot (including wake-boot from deepsleep)
#import esp
#esp.osdebug(None)
#import webrepl
#webrepl.start()
 
import machine
print("Executing boot file...")
# Check why we woke up
if machine.reset_cause() != machine.DEEPSLEEP_RESET:
    # This is a cold/warm boot — do one clean deepsleep reset
    machine.deepsleep(1)

# If we get here, we woke from deepsleep = clean RAM
# Continue with normal initialization...

import gc

gc.collect()

from machine import freq, WDT, UART, Pin, reset
freq(240000000)
wdt = WDT(timeout=20000)

uart1_tx_pin = 12  # Example: GPIO12
uart1_rx_pin = 14  # Example: GPIO14
rxbuf=8192 * 3
uart1 = UART(1, baudrate=115200*4, tx=Pin(uart1_tx_pin), rx=Pin(uart1_rx_pin), rxbuf=rxbuf)

version_num = "0.01"
# END_OF_FILE_BOOT