import network
import gc
import time
import machine

gc.collect()

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.config(pm=network.WLAN.PM_NONE)
wlan.config(pm = 0)

max_retries = 10

def con_to_wifi(ssid, password):
    try:
        if not wlan.active():
            wlan.active(True)

        if wlan.isconnected():
            wlan.disconnect()
            time.sleep(0.1)

        print("Connecting to Wi-Fi...")
        wlan.connect(ssid, password)
        
        retry_count = 0
        while not wlan.isconnected():
            if retry_count > max_retries:
                print("Wi-Fi failed. Restarting device...")
                time.sleep(1)
                machine.reset()
            time.sleep(1)
            retry_count+=1
            
        print("Wi-Fi connected.")
        gc.collect()

        return wlan.ifconfig()
    
    except Exception as e:
        print("Error during wifi connect:", e)

version_num = "0.01"
# END_OF_FILE_WIFI