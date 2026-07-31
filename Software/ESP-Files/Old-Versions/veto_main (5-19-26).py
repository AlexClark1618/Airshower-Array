#Veto

#Updated- 11/13/25 (Alex)

#Changelog:
    #General cleanup
    #More info packets
    #Improved send function to handle errors
    #Added timeout for send

import socket
import ustruct
import time
import network
from machine import UART, Pin, WDT
import time
import gc
from PPS import init_time, pps_irq, ubx_checksum, ubx_send, ubx_recv, poll_gps_time, discipline_rtc,rtc_to_gps_wno_ms_subms


#---------GPS Functions-----------
UBX_HDR = b'\xb5b'
RXM_TM=b'\x02\x74'
TIM_TM2=b'\x0d\x03'
uart1_tx_pin = 12  # Example: GPIO12
uart1_rx_pin = 14  # Example: GPIO14
uart1 = UART(1, baudrate=115200*4, tx=Pin(uart1_tx_pin), rx=Pin(uart1_rx_pin), rxbuf=8192*2)

time.sleep(0.1)
numMeas=1
# ---------- Wifi and Socket Stuff ----------
def con_to_wifi(ssid, password):
    if wlan.isconnected():
        wlan.disconnect()
        time.sleep(0.1)
    
    while not wlan.isconnected():
        try:
            print("Connecting to Wi-Fi...")
            wlan.connect(ssid, password)
            while not wlan.isconnected():
                time.sleep(1)
            print("Wi-Fi connected.")
            return wlan.ifconfig()
        except OSError as e:
            print(f"Connection attempt failed: {e}")
            
send_packet_format = "!iiiiiiiiii"

def data_packing(packet_format: str, msg: tuple):
    try:
        packet = ustruct.pack(packet_format, 
            msg[0],#inst,            # char (1 byte)
            msg[1],#ID,
            msg[2],#RF,              # char (1 byte)
            msg[3],#cal,              # uint8 (1 byte)
            msg[4],#ch,          # uint8 (1 byte)
            msg[5],#w_num,      	 # uint32 (4 bytes) #Q for 8 byte uint64
            msg[6],#ms,         # uint32 (4 bytes)
            msg[7],#sub_ms,
            msg[8],#event_num                  # uint32 (4 bytes)
            msg[9] #count
        )
        
        return packet
    
    except Exception:
        print("Error in data packing")

def connect_socket(host, port):
    while True:
        try:
            s = socket.socket()
            s.connect((host, port))
            print("Socket connected.")
            return s
        except Exception as e:
            print("Failed to connect socket:", e)
            time.sleep(1)

# ---------- GPS Functions ----------
def clearRxBuf():
    while uart1.any():
        print('buffer cleared of ',uart1.any(), 'bytes\n')
        (uart1.read())

def findUBX_HDR():
    while  (uart1.read(1) != b'\xb5'):
        pass
    while  (uart1.read(1) != b'\x62'):
        pass
    #        C   ID  RF Cal  ch wno  Ms Sub cnt
    #request=(0,  0,  0,  0,  0,  0,  0,  0,  0)

def readData(det):
#det: 0 == BH and 1 == AS
#     towMsR=0
#     while towMsR < Request:
        
        #print('readData')
        findUBX_HDR()    
        #print('\tFound UBX header: ', bytehdr)
        #bytehdr = UBX_HDR
        while uart1.any() < 4:
            pass
        data0 = uart1.read(4)
        #print('Header: ',data0)
        bytehdr2 = data0[0:2]
        lenb = data0[2:4]
        if bytehdr2 == RXM_TM:
            hdr2='RXM_TM'
            ##print('\tFound Raw time stamp header: ', bytehdr2)
        elif bytehdr2 == TIM_TM2:
            hdr2='TIM_TM2'
            ##print('\tFound Calibrated time stamp header: ', bytehdr2)

        leni = int.from_bytes(lenb, "little")
        ##print('\tdata length: ',leni)
        ##print ('buffer ', uart1.any())
        while uart1.any() < (leni+2):
            pass

        if (bytehdr2 == RXM_TM):
                plb = uart1.read(leni)
                #print(plb)
                cksum = uart1.read(2)
                #print('checksum:',cksum)
                version=plb[0]

                end="   "
                ##print('\nraw data:\n', bytehdr+bytehdr2+plb+cksum, '\n')

                ##print ('parsed data:')
                ##print(hdr+'|'+hdr2)
                #print('ver',version, end=end)
                numMeas=plb[1]
                #print('numMeas',numMeas, end ="\t")
                for ii in range(0, numMeas*24, 24):
                    #print('ii',ii,end=end)
                    edgeInfob=plb[8+ii:12+ii]
                    #print('edgeInfob',edgeInfob)
                    edgeInfo=int.from_bytes(edgeInfob, "little")
                    #print('edgeInfo',edgeInfo, end =end)
                    RF= (edgeInfo >> 4) & 1
                    #if RF ==1:
                        #print('EdgeF', end =end)
                    #else:
                        #print('EdgeR', end =end)
                    ch = edgeInfo & 1
                    ##print('channel ', ch, end =end)
                    countb = plb[12+ii:14+ii]
                    count=int.from_bytes(countb, "little")
                    ##print('count ', count, end =end)
                    wnob=plb[14+ii:16+ii]
                    wno=int.from_bytes(wnob,"little")
                    ##print('wno ', wno, end =end)
                    towMsb=plb[16+ii:20+ii]
                    towMs=int.from_bytes(towMsb,"little")
                    ##print('towMs ', towMs, end =end)
                    towSubMsb=plb[20+ii:24+ii]
                    towSubMs=int.from_bytes(towSubMsb,"little")
                    ##print('towSubMs ', towSubMs)
                ##print('\n')
#                     RFRaw.append(RF)
#                     chRaw.append(ch)
#                     countRaw.append(count)
#                     towMsRaw.append(towMs)
#                     towSubMsRaw.append(towSubMs)
        elif (bytehdr2 == TIM_TM2):
                plb = uart1.read(leni)
                #print(plb)
                cksum = uart1.read(2)
                #print('checksum:',cksum)

                end="   "
                ##print('\nraw data:\n', bytehdr+bytehdr2+plb+cksum, '\n')

                ##print ('parsed data:')
                ##print(hdr+'|'+hdr2)
                #print('ver',version, end=end)
                ch=plb[0]
                ##print('channel ',channel, end=end)
                edgeInfo=plb[1]
                #print('edgeInfo',edgeInfo, end = end)
                #edgeInfo=int.from_bytes(edgeInfob, "little")
                edgeF = (edgeInfo >> 2) & 1
                edgeR = (edgeInfo >> 7) & 1
                timeValid = (edgeInfo >> 6) & 1
                #timeValid = int.from_bytes(timeValidb, "little")
                #print('timeValid', timeValid, end=end)
                countb = plb[2:4]
                count=int.from_bytes(countb, "little")
                ##print('count ', count, end =end)
                wnoRb = plb[4:6]
                wnoR=int.from_bytes(wnoRb, "little")
                ##print('wnoR ', wnoR, end =end)
                wnoFb = plb[6:8]
                wnoF=int.from_bytes(wnoFb, "little")
                ##print('wnoF ', wnoF, end =end)
                towMsRb=plb[8:12]
                towMsR=int.from_bytes(towMsRb,"little")
                ##print('towMsR ', towMsR, end=end)
                towSubMsRb=plb[12:16]
                towSubMsR=int.from_bytes(towSubMsRb,"little")
                ##print('towSubMsR ', towSubMsR, end=end)
                towMsFb=plb[16:20]
                towMsF=int.from_bytes(towMsFb,"little")
                ##print('towMsF ', towMsF, end=end)
                towSubMsFb=plb[20:24]
                towSubMsF=int.from_bytes(towSubMsFb,"little")
                ##print('towSubMsF ', towSubMsF, end=end)
                accEstb=plb[24:28]
                accEst=int.from_bytes(accEstb,"little")
                ##print('accEst ', accEst, end=end)
                
                ##print('\n')
                
                #cksum = uart1.read(2)
                #print('checksum',cksum,'\n')
                if det == 1:
                    #RFRaw.append(0)
                    #chRaw.append(ch)
                    countCal.append(count)
                    towMsCal.append(towMsR)
                    towSubMsCal.append(towSubMsR)

        else:
                ##print('It is junk')
                
                while uart1.any():
                    print('buffer cleared of ',uart1.any(), 'bytes\n')
                    (uart1.read())
        
        if (bytehdr2 == TIM_TM2) & (det == 1):
            return((wnoR,towMsR,towSubMsR)) #calibrated data
        elif (bytehdr2 == TIM_TM2) & (det == 0):
            #print(ch, wnoR, wnoF, towMsR, towMsF, towSubMsR, towSubMsF)

            return [
                (0, timeValid, ch, wnoR, towMsR, towSubMsR, count),
                (1, timeValid, ch, wnoF, towMsF, towSubMsF, count)
            ]
        else:
            return((0,0,0))


# ---------- Wi-Fi Setup ---------
ssid = 'AirShower2.4G'
password = 'Air$shower24'

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

con_to_wifi(ssid, password)
full_mac = wlan.config('mac')
mac_id = wlan.config('mac')[-1]  # last byte of MAC
print("Mac ID:",mac_id)
ip, subnet, gateway, dns = wlan.ifconfig()
ip_last_byte = int(ip.split('.')[-1])          
print("ESP IP:", ip_last_byte)

# ---------- Connecting to Server ----------
#HOST = '192.168.0.93' #Home
#HOST = '134.69.200.155'
HOST = '134.69.77.61' #Karbon Computer
PORT = 12345

s = connect_socket(HOST,PORT)
#s.settimeout(.1)
s.setblocking(False)

# ---------- Send and Recieve Functions ----------
def send_data(d):
    global s
    
    try:
        data = s.send(d)
        return data 

    except OSError as e:
        if e.args[0] in [11, 110, 104]:  # EAGAIN, ETIMEDOUT, ECONNRESET
            # No data or connection lost
            print("No data")
            
        else:
            print("Socket error:", e)
            try:
                s.close()
            except:
                pass
            s = connect_socket(HOST, PORT)  # your reconnect function
            
def recieve(num_bytes):
    global s
    try:

        data = s.recv(num_bytes) 

        if data:
            print("Wifi RX buffer cleared of:", len(data), "bytes")

    except OSError as e:
        if e.args[0] in [11, 110, 104]:  # EAGAIN, ETIMEDOUT, ECONNRESET
            # No data or connection lost
            print("No data to clear")
            
        else:
            print("Socket error:", e)
            try:
                s.close()
            except:
                pass
            s = connect_socket(HOST, PORT)  # your reconnect function

# ---------- Info Packets ----------
error_msg = (100, mac_id, 15, time.ticks_ms(), ip_last_byte, 0, 0, 0, 0, 0) # This tells me when the board restarted how long it took to reach the main loop since booting
packet = data_packing(send_packet_format, error_msg)
send_data(packet)

time.sleep(0.1)

info_msg = (1, mac_id, ip_last_byte, 0, 0, 0, 0, 0, 0, 0) # This tells me when the board restarted how long it took to reach the main loop since booting
packet = data_packing(send_packet_format, info_msg)
send_data(packet)

# ---------- Main Loop ----------
clearRxBuf()

event_num = -1 #Keeps track of borehole events (could be moved to server)

wdt = WDT(timeout=50000)  # 5 seconds

send_buffer = bytearray()

#init_time(uart1)
while True:
    try:
        #Checks for wifi disconnections. (May want to move this to an exception handle)
        if not wlan.isconnected():
            con_to_wifi(ssid, password)
        
        res = (0,0,0)
        while res[0] == 0:
            res = readData(0)
            #wdt.feed()
            print(res)
        #print('res:', res)
        #timeStamp=rtc_to_gps_wno_ms_subms()
        timesOfInterest = res
        ID=mac_id
        
        for i in range(len(timesOfInterest)):
            inst = 99           
            ID = mac_id
            RF = timesOfInterest[i][0]              
            cal = timesOfInterest[i][1]               
            ch = timesOfInterest[i][2]           
            w_num = timesOfInterest[i][3]   
            ms = timesOfInterest[i][4]      
            sub_ms = timesOfInterest[i][5]
            event_num = event_num 
            count = timesOfInterest[i][6] 

            msg = (inst, ID, RF, cal, ch, w_num, ms, sub_ms, event_num, count)
            
            packet = data_packing(send_packet_format, msg)
            
            #if (RF==0 & ch==0):
                #add a stamp stamp if it is a rise on channel 0.
                #msg2 = (97, ID, 0, cal, 0, timeStamp[0],timeStamp[1],timeStamp[2],event_num, count)
                #packet2 = data_packing(send_packet_format, msg2)
                #send_buffer+= packet2

                
            send_buffer+= packet
            wdt.feed()

        recieve(1024) #Keeps socket empty
        data = send_data(send_buffer) #Should I start checking wifi and socket are active before sending? It seems kind of pointless,
        if data: 
            print("!!!!!!!!!!!!!!!!!!!!!data sent", len(send_buffer) )
        send_buffer = bytearray()
        wdt.feed()

        event_num -=1
        
    except Exception as e:
        print("Error in main loop", e)
        error_msg = (100, mac_id, ip_last_byte, 14, 0, 0, 0, 0, 0, 0)
        packet = data_packing(send_packet_format, error_msg)
        send_data(packet)
        continue
        
    
    

    

