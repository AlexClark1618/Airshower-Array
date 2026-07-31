#Airshower Calibration Code
#9-15-25

###To Change:
    #How to add gps count

import socket
import ustruct
import time
import network
import select
from machine import UART, Pin, WDT
import time
import gc

#---------GPS Functions-----------
UBX_HDR = b'\xb5b'
RXM_TM=b'\x02\x74'
TIM_TM2=b'\x0d\x03'
uart1_tx_pin = 12  # Example: GPIO12
uart1_rx_pin = 14  # Example: GPIO14
uart1 = UART(1, baudrate=115200*4, tx=Pin(uart1_tx_pin), rx=Pin(uart1_rx_pin), rxbuf= 8192*3)

rxbuf = 8192 * 3

time.sleep(1)
NNC=10
numMeas=1

def clearRxBuf():
    while uart1.any():
        print('buffer cleared of ',uart1.any(), 'bytes\n')
        (uart1.read())

def findUBX_HDR():
    print('findUBX_HDR')
    Byte2=0
    while Byte2 != b'\x62':
        while uart1.read(1) != b'\xb5':
            pass
        Byte2=uart1.read(1)

def request(wno,Ms,subMs):
    #print('Request Started')
    #print(gc.mem_free())
    gc.collect()
    res=(0,0,0)
    #while res[1] < Ms+1: #Exceed the time of interest by at least 1 ms
    while (res[1]) < Ms+1:
        #print('readData started')
        res=readData(1)
        #print('readData finished')
        #print('readData output:', res)
        #print(Ms)
        #print(res)
        if res[0] != 0:
            #print(res[0] == 0)
            #print ('read Cal Data',res)
            if (abs(Ms - res[1]) > 1) | (res[0] != wno) :
                pass
                #print('Unreasonable request')
                 #Assuming we get a res > Ms and fails this check it should reset it

                #clearRxBuf()
                #return [(0,0,0,0,0,0)]
            
    lastC=len(countCal)-1
    lastR=len(countRaw)-1
    #Find upper index in raw data

    for i in range(lastR,-1,-1):
        if countRaw[i]==countCal[lastC]:
            break
    rawIndex2=i
    #Find lower index in raw data
    for j in range(lastR-1,-1,-1):
        if countRaw[j]==countCal[lastC-1]:
            break
    rawIndex1=j
    #print('towMsCal:',towMsCal)
    #print('towSubMsCal:',towSubMsCal)

    tCal2=towMsCal[lastC]*1000000+(towSubMsCal[lastC])
    tCal1=towMsCal[lastC-1]*1000000+(towSubMsCal[lastC-1])
    tRaw2=towMsRaw[rawIndex2]*1000000+int(towSubMsRaw[rawIndex2]/1000)
    tRaw1=towMsRaw[rawIndex1]*1000000+int(towSubMsRaw[rawIndex1]/1000)
    
    
    slope = (tCal2-tCal1)/(tRaw2-tRaw1)
    
    #print('slope', slope)
    #intercept = tCal2-tRaw2
    timesOfInterest=[]
    for i in range(rawIndex1,rawIndex2+1):
        tRaw=towMsRaw[i]*1000000+int(towSubMsRaw[i]/1000)
        #print(towMsRaw,towSubMsRaw,intercept,tRaw)
        res=int((tRaw-tRaw1)*slope)+tCal1
        sec=int(res/1000000000)
        ns=res-sec*1000000000
        ms=int(ns/1000000)
        Ms=sec*1000+ms
        SubMs=res-Ms*1000000
        timesOfInterest.append((RFRaw[i],1,chRaw[i],wno,Ms,SubMs))
    return(timesOfInterest)

def readData(det):
#det: 0 == BH and 1 == AS
#     towMsR=0
#     while towMsR < Request:
        
        #print('readData started')
        findUBX_HDR()
        #print('found header')
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
            #print('1')
            #print('\tFound Raw time stamp header: ', bytehdr2)
        elif bytehdr2 == TIM_TM2:
            hdr2='TIM_TM2'
            #print('2')
            #print('\tFound Calibrated time stamp header: ', bytehdr2)

        leni = int.from_bytes(lenb, "little")
        #print('\tdata length: ',leni)
        ##print ('buffer ', uart1.any())

        while uart1.any() < (leni+2):
            if leni > rxbuf:
                clearRxBuf()
                return((0,0,0))
 
            #print('3')
            else:
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
                    ##if RF ==1:
                        ##print('1', end =end)
                    ##else:
                        ##print('0', end =end)
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
                    #print('towSubMs ', towSubMs)
                ##print('\n')
                    RFRaw.append(RF)
                    chRaw.append(ch)
                    countRaw.append(count)
                    towMsRaw.append(towMs)
                    #print("towMs:", towMs)
                    towSubMsRaw.append(towSubMs)

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
                ##print('timeValid', timeValid, end=end)
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
                #print('accEst ', accEst, end=end)
                #print('5')
                ##print('\n')
                
                #cksum = uart1.read(2)
                #print('checksum',cksum,'\n')
                if det == 1:
                    #RFCal.append(0) #!!!Error here
                    #chCal.append(ch)
                    countCal.append(count)
                    towMsCal.append(towMsR)
                    towSubMsCal.append(towSubMsR)
                    #print('6')
        else:
                #print('It is junk')
                
                while uart1.any():
                    #print('buffer cleared of ',uart1.any(), 'bytes\n')
                    (uart1.read())
                    
        if (bytehdr2 == TIM_TM2) & (det == 1):
            #print('data bytehdr2',bytehdr2)
            #print("towMsR:", towMsR)

            return((wnoR,towMsR,towSubMsR)) #calibrated data
        elif (bytehdr2 == TIM_TM2) & (det == 0):
            #print(ch, wnoR, wnoF, towMsR, towMsF, towSubMsR, towSubMsF)

            return[
                (0, 1, ch, wnoR, towMsR, towSubMsR),
                (1, 1, ch, wnoF, towMsF, towSubMsF)
            ]
        else:
            #print('0 bytehdr2',bytehdr2)
            #if bytehdr2 == RXM_TM:
                #print('Header passed')
            return((0,0,0))
# ---------- Functions ----------
delay=1
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
 
send_packet_format = "!IIIIIIIII"
request_packet_format = '!IIIII'

def data_packing(packet_format: str):
    packet = ustruct.pack(packet_format, 
        inst,            # char (1 byte)
        ID,
        RF,              # char (1 byte)
        cal,              # uint8 (1 byte)
        ch,          # uint8 (1 byte)
        w_num,      	 # uint32 (4 bytes) #Q for 8 byte uint64
        ms,         # uint32 (4 bytes)
        sub_ms,
        event_num                  # uint32 (4 bytes)
    )
    
    return packet

def connect_socket(host, port):
    s = socket.socket()
    try:
        s.connect((host, port))
        print("Socket connected.")
        return s
    except OSError as e:
        print("Failed to connect socket:", e)
        return None

def reconnect_socket():
    global s, poller

    # Try to safely unregister and close old socket
    try:
        if s:
            poller.unregister(s)
            s.close()
    except Exception as e:
        print("Error closing old socket:", e)

    print("Reconnecting socket...")
    time.sleep(1)

    # Attempt reconnect
    s = connect_socket(HOST, PORT)
    if s:
        try:
            poller.register(s, select.POLLIN)
            clear_rx_buffer(s, poller)  # Only call this if s is valid
            print("Reconnected successfully.")
        except Exception as e:
            print("Error registering poller or clearing buffer:", e)
            s = None  # Mark socket as dead
    else:
        print("Socket reconnection failed.")

def clear_rx_buffer(sock, poller):      
    if not sock:
        print("No socket to clear.")
        return

    try:
        while True:
            events = poller.poll(0)  # Non-blocking poll
            if not events:
                break
            try:
                sock.recv(1024)
            except OSError:
                break
        print("rx buffer cleared")
    except Exception as e:
        print("Error during buffer clear:", e)
    
# ---------- Wi-Fi Setup ----------
#ssid = 'TP-Link_FB80'
#password = 'Beau&River'

ssid = 'ONet'
password = ''

#These can be moved to the main wifi function, but I thinks its more versitile to define them as globals
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

con_to_wifi(ssid, password)
mac_ID = wlan.config('mac')[-1]  # last byte of MAC
print('mac id:', mac_ID)
# ---------- Connecting to Server ----------
#HOST = '192.168.0.93' #Home
HOST = '134.69.233.83'
#HOST = '134.69.218.243' #Karbon Computer
PORT = 12345

s = connect_socket(HOST,PORT)
poller = select.poll()

if s:
    try:
        poller.register(s, select.POLLIN)
        clear_rx_buffer(s, poller)
    except Exception as e:
        print("Initial poller registration failed:", e)
        s = None  # Mark as failed
else:
    print("Initial socket connect failed.")

# ---------- Main Loop ----------
i = 0
while i < 20:
    clearRxBuf()
    time.sleep(0.1)
    i += 1

wdt = WDT(timeout=5000)  # 5 seconds
print("Running")
event_num = 0
while True:
    #Checks for wifi disconnections. (May want to move this to an exception handle)
    try:
        if not wlan.isconnected():
            con_to_wifi(ssid, password)
            
        RFRaw=[]
        chRaw=[]
        countRaw=[]
        countCal=[]
        towMsRaw=[]
        towMsCal=[]
        towSubMsRaw=[]
        towSubMsCal=[]
        
        res = (0,0,0)
        while res[1] == 0:
            try:
                res = readData(1)
            except Exception: #Restart on any error
                continue
            
        w_num = res[0]
        ms = res[1] + 100
        sub_ms = res[2]
        
        try:
            timesOfInterest=request(w_num,ms,sub_ms)
        except Exception: #Restart on any error
            continue

        for i in range(len(timesOfInterest)):
            inst = 99           
            ID = mac_ID
            RF = timesOfInterest[i][0]              
            cal = timesOfInterest[i][1]               
            ch = timesOfInterest[i][2]           
            w_num = timesOfInterest[i][3]   
            ms = timesOfInterest[i][4]      
            sub_ms = timesOfInterest[i][5]
            event_num = event_num #Unnecessary

            try:
                packet = data_packing(send_packet_format)
                data = s.send(packet)
                wdt.feed()

                #print(f'Bytes sent: {data}')#Prints byte size
            
            except OSError as e: 
                print("Socket error:", e)
                reconnect_socket()
                break  # Exit inner loop
    except Exception as e:
        print("Main loop exception:", e)
        reconnect_socket()

    event_num += 1
    print(".")