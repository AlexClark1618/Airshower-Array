#Must register Mac ID at this address: https://onet.oxy.edu/status/login

import network

# Get the MAC address of the station interface (STA)
sta_if = network.WLAN(network.STA_IF)
sta_if.active(True)  # Make sure it's active
mac = sta_if.config('mac')  # Returns a bytes object

# Format as human-readable MAC address
mac_str = ':'.join('{:02x}'.format(b) for b in mac)

print("ESP32 MAC Address:", mac_str)
print(mac[-1])
