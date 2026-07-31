#Borehole

gc.collect()

from ringBuffer import RingBuffer, push_all_cal, push_all_raw
from ringBuffer import rb_cal_count, rb_cal_wno, rb_cal_ms, rb_cal_sub
from ringBuffer import rb_raw_rf, rb_raw_ch, rb_raw_count, rb_raw_wno, rb_raw_ms, rb_raw_sub
from ringBuffer import CAPACITY_RAW, CAPACITY_CAL, raw_write_idx, cal_write_idx, cal_count, raw_count

gc.collect()

import wifi
import socket
import ustruct
import time
import network
import sys
import array
import select

#from PPS import init_time, pps_irq, ubx_checksum, ubx_send, ubx_recv, poll_gps_time, discipline_rtc,rtc_to_gps_wno_ms_subms
gc.collect()
#---------GPS Variables-----------
UBX_HDR = b'\xb5\x62' 
RXM_TM =(2,116)   #b'\x02\x74'
TIM_TM2= (13,3)   #b'\x0d\x03'
NAV_CLOCK= (1,34)       #b'\x01\x22'
REQUESTED_TIME_WINDOW = 1000000  #returned times (ns) will be within +/- requested_time_window of time of interested 
# UBX poll message for NAV-CLOCK (class 0x01, ID 0x22)
POLL_NAV_CLOCK = b'\xb5\x62\x01\x22\x00\x00\x23\x6a'

numMeas=1
global tcoll0
tcoll0=0

# ---------- Wi-Fi Setup ----------
ssid = 'Test_Omada_Wi-Fi'
#ssid = 'AirShower2.4G' 
password = 'Air$shower24'

wifi.con_to_wifi(ssid, password)
      
def clear_wifi_rx_buffer():
    global s
    if not s:
        print("No socket to clear.")
        return

    total = 0

    try:
        while True:
            data = s.recv(1024)
            if not data:
                break
            total += len(data)

    except OSError:
        pass  # buffer empty

    print("Wifi RX buffer cleared:", total, "bytes")

# ---------- Wifi and Socket Variables -----------
mac_id = wifi.wlan.config('mac')[-1]  # last byte of MAC
print('mac id:', mac_id)
ip, subnet, gateway, dns = wifi.wlan.ifconfig()
ip_last_byte = int(ip.split('.')[-1])
print("ESP IP:", ip_last_byte)

#HOST = '134.69.77.61' #Karbon Computer
HOST = '192.168.0.27' #Local network
PORT = 12345

# ---------- Socket Functions ----------

def connect_socket(host, port):
    while True:
        try:
            gc.collect()
            s = socket.socket()
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.connect((host, port))
            print("Socket connected.")
            gc.collect()

            return s
        except Exception as e:
            print("Failed to connect socket:", e)
            time.sleep(1)
            continue     

s = connect_socket(HOST,PORT)
#s.setblocking(False)
s.settimeout(.05) #50ms timeout

poller = select.poll()
poller.register(s, select.POLLIN)

def reconnect_socket(sock, poller):
    try:
        poller.unregister(sock)
    except:
        pass

    try:
        sock.close()
        gc.collect()
    except:
        pass

    time.sleep(0.1)

    s = connect_socket(HOST, PORT)

    poller.register(s, select.POLLIN)
    return s

# ---------- Send and Receive Functions -----------
def send_data(d):
    global s
    try:
        return s.send(d)

    except OSError as e:
        if e.args[0] in [11, 110]:  # EAGAIN, ETIMEDOUT, ECONNRESET
            print("No data to send")
            return None
        else:
            print("Send error:", e)
            #error_msg = (100, mac_id, 2, 0, 0, 0, 0, 0, 0, 0)
            s = reconnect_socket(s, poller)

            packet = data_packing(send_packet_format, 100, mac_id, 2, 0, 0, 0, 0, 0, 0, 0)
            s.send(packet)

            return None

# ---------- Data Packing -----------
send_packet_format = "!iiiiiiiiii"

def data_packing(packet_format,v0,v1,v2,v3,v4,v5,v6,v7,v8,v9):
    try:
        return ustruct.pack(packet_format,v0,v1,v2,v3,v4,v5,v6,v7,v8,v9)
    except Exception as e:
        print("Error in data packing", e)
        return None

# ---------- GPS Functions ----------
junk=bytearray(1024)

def clearRxBuf():
    print('clearRxBuf')
    gc.collect()
    try:
        #print('clearRxBuf:', uart1.any(),'bytes')
        print('buffer cleared of ',uart1.any(), 'bytes\n')
        while uart1.any()>1024:
            junk=(uart1.read(1024))
        while uart1.any():
            uart1.read()
    except Exception as e:
        print("Error in clear buffer:", e)
        #error_msg = (100, mac_id, 4, 0, 0, 0, 0, 0, 0, 0)
        packet = data_packing(send_packet_format, 100, mac_id, 4, 0, 0, 0, 0, 0, 0, 0)
        send_data(packet)

def maxRxBuf(n,n2):
    try:
        nbuf = uart1.any()
        if nbuf > n:
            nClear=0
            while (uart1.any() > n):
                #nskim = uart1.any()-n + 1000
                nClear += 1
                readData(1)
                readData(1)
                #uart1.readinto(junk, 1024)
                #junk=uart1.read(1024)
            print('buffer cleared of ',nClear, "50ms segments")
        elif nbuf > n2:
            readData(1)  #read and parse 1kb segment of raw data
            readData(1)  #read and parse 60byte segment of cal data
            print('buffer cleared of a 50ms segment')
    except Exception as e:
        print('maxRxbuf exception',e)
        #error_msg = (100, mac_id, 5, 0, 0, 0, 0, 0, 0, 0)
        packet = data_packing(send_packet_format,100, mac_id, 5, 0, 0, 0, 0, 0, 0, 0)
        send_data(packet)

hdr = bytearray(1)
def findUBX_HDR():
    try:
        state = 0  # 0 = looking for 0xB5, 1 = looking for 0x62
        n=0
        i=0
        while True:
            if uart1.any() == 0:
                i=i+1
                time.sleep_ms(1)
                if (i-i//1000*1000) == 0:
                    print('ubx',end='.')
                continue

            uart1.readinto(hdr)  # integer, no bytes object
            b = hdr[0]
            n=n+1
            #print(b,end=' ')
            if state == 0:
                if b == 0xB5:
                    state = 1
            else:
                if b == 0x62:
                    return n # header found
                else:
                    state = 0  
    except Exception as e:
        print("findUBX_HDR error:",e)
        #error_msg = (100, mac_id, 6, 0, 0, 0, 0, 0, 0, 0)
        packet = data_packing(send_packet_format, 100, mac_id, 6, 0, 0, 0, 0, 0, 0, 0)
        send_data(packet)

hdr2 = bytearray(4)
def findHDR2():
    try:
        while uart1.any() < 4:
            time.sleep_ms(0)
        uart1.readinto(hdr2)
        cls  = hdr2[0]
        msg  = hdr2[1]
        leni = hdr2[2] | (hdr2[3] << 8)
        #print('HDR2', cls, msg, leni)
        # optional sanity check
    #     if leni > 2048:
    #         raise ValueError("Invalid UBX length")
        return cls, msg, leni
    except Exception as e:
        print("findUBX_HDR2 error:",e)
        #error_msg = (100, mac_id, 7, 0, 0, 0, 0, 0, 0, 0)
        packet = data_packing(send_packet_format, 100, mac_id, 7, 0, 0, 0, 0, 0, 0, 0)
        send_data(packet)

MAX_TOI=64

toi_RF     = array.array("B", bytearray(MAX_TOI))
toi_valid     = array.array("B", bytearray(MAX_TOI))
toi_ch     = array.array("B", bytearray(MAX_TOI))
toi_wno     = array.array("H", bytearray(MAX_TOI))
toi_Ms     = array.array("I", bytearray(MAX_TOI))
toi_SubMs     = array.array("I", bytearray(MAX_TOI))

plb = bytearray(2048)
ck  = bytearray(2)

def readData():
    #print('readData')
    global slope

    try:
        # Find UBX sync
        findUBX_HDR()

        cls, msg, leni = findHDR2()
        if leni > 2048:
            return (0, 0, 0, 0, 0)

        # Wait cooperatively for payload + checksum
        needed = leni + 2
        while uart1.any() < needed:
            time.sleep_ms(1)

        # Read payload + checksum without allocating
        uart1.readinto(plb, leni)
        uart1.readinto(ck, 2)

        # ---------- RXM-TM ----------
        if (cls, msg) == RXM_TM:
            version = plb[0]
            numMeas = plb[1]

            base = 8
            for _ in range(numMeas):
                edgeInfo = (
                    plb[base+0] |
                    (plb[base+1] << 8) |
                    (plb[base+2] << 16) |
                    (plb[base+3] << 24)
                )

                RF = (edgeInfo >> 4) & 1
                ch = edgeInfo & 1

                count = plb[base+4] | (plb[base+5] << 8)
                wno   = plb[base+6] | (plb[base+7] << 8)

                towMs = (
                    plb[base+8] |
                    (plb[base+9] << 8) |
                    (plb[base+10] << 16) |
                    (plb[base+11] << 24)
                )

                towSubMs = (
                    plb[base+12] |
                    (plb[base+13] << 8) |
                    (plb[base+14] << 16) |
                    (plb[base+15] << 24)
                )

                push_all_raw(RF, ch, wno, towMs, towSubMs, count)

                base += 24

        # ---------- TIM-TM2 ----------
        elif (cls, msg) == TIM_TM2:
            ch = plb[0]
            edgeInfo = plb[1]

            edgeF     = (edgeInfo >> 2) & 1
            edgeR     = (edgeInfo >> 7) & 1
            timeValid = (edgeInfo >> 6) & 1

            count = plb[2] | (plb[3] << 8)
            wnoR  = plb[4] | (plb[5] << 8)
            wnoF  = plb[6] | (plb[7] << 8)

            towMsR = (
                plb[8] |
                (plb[9] << 8) |
                (plb[10] << 16) |
                (plb[11] << 24)
            )

            towSubMsR = (
                plb[12] |
                (plb[13] << 8) |
                (plb[14] << 16) |
                (plb[15] << 24)
            )

            towMsF = (
                plb[16] |
                (plb[17] << 8) |
                (plb[18] << 16) |
                (plb[19] << 24)
            )

            towSubMsF = (
                plb[20] |
                (plb[21] << 8) |
                (plb[22] << 16) |
                (plb[23] << 24)
            )

            accEst = (
                plb[24] |
                (plb[25] << 8) |
                (plb[26] << 16) |
                (plb[27] << 24)
            )

            push_all_cal(wnoR, towMsR, towSubMsR, count)
            return (wnoR, towMsR, towSubMsR, timeValid, ch)

        # ---------- NAV-CLOCK ----------
        elif (cls, msg) == NAV_CLOCK:
            iTOW = (
                plb[0] |
                (plb[1] << 8) |
                (plb[2] << 16) |
                (plb[3] << 24)
            )

            iclkBias  = ustruct.unpack_from('<i', plb, 4)[0]
            iclkDrift = ustruct.unpack_from('<i', plb, 8)[0]

            tAcc = (
                plb[12] |
                (plb[13] << 8) |
                (plb[14] << 16) |
                (plb[15] << 24)
            )

            fAcc = (
                plb[16] |
                (plb[17] << 8) |
                (plb[18] << 16) |
                (plb[19] << 24)
            )

            slope = iclkDrift

        # Yield once after heavy UART work
        time.sleep_ms(0)
        return (0, 0, 0, 0, 0)

    except MemoryError as e:
        sys.print_exception(e)
        print("Memory Error in ReadData")
        machine.reset()

    except Exception as e:
        sys.print_exception(e)
        print("Error in readData", e)
        packet = data_packing(send_packet_format, 100, mac_id, 9, 0, 0, 0, 0, 0, 0, 0)
        send_data(packet)      
        return (0, 0, 0, 0, 0)
            
# ---------- Info Packets ----------
packet = data_packing(send_packet_format, 100, mac_id, ip_last_byte, 15, time.ticks_ms(), 0, 0, 0, 0, 0)
send_data(packet)

time.sleep(0.1)

packet = data_packing(send_packet_format, 1, mac_id, ip_last_byte, 0, 0, 0, 0, 0, 0, 0)
send_data(packet)

# ---------- Main Loop ----------

NEvents0 = 0
NEvents1 = 0
deltaT = 0

#initialise Valid, slope  and offset 
uart1.write(POLL_NAV_CLOCK) #Poll Nav Clock
slope=0
tRaw1=None
tCal1 = None
Valid = 0
res=None
oldtowMsR = 0            
oldtowMs = 0            
countdtMs = 0    

while ((slope == 0) or (tRaw1 == None) or (Valid == 0)):
    try:
        print('\ninit while loop', slope, tRaw1, Valid, res)
        uart1.write(POLL_NAV_CLOCK) #Poll Nav Clock
        for i in range(4):
            res=readData()
            if (res[1] > 0):
                if (res[3] > 0):
                    Valid = 1
                else:
                    Valid = 0
                    print("GPS not locked")
                    time.sleep(1)# wait 1 second before trying again
                    break

            lastCount=rb_cal_count.get(0)  #latest cal count
                
            for i in range(raw_count[0]):
                if rb_raw_count.get(i)==lastCount:
                    tCal1=rb_cal_ms.get(0)*1000000+(rb_cal_sub.get(0))
                    tRaw1=rb_raw_ms.get(i)*1000000+(rb_raw_sub.get(i)//1000)
                    break
    except Exception as e: #I believe this is just due to readData memory allocation
        sys.print_exception(e)
        print("Error in gps initialization")
        #error_msg = (100, mac_id, 10, 0, 0, 0, 0, 0, 0, 0)
        packet = data_packing(send_packet_format, 100, mac_id, 10, 0, 0, 0, 0, 0, 0, 0)
        send_data(packet)
        continue

CC=0
reqCount=0
global toi_len

clearRxBuf()

T0=time.ticks_us()
event_num = 0 #Keeps track of borehole events (could be moved to server)

tx_packet_size = ustruct.calcsize(send_packet_format)
send_buffer = bytearray(640)
send_buffer_index = 0

#init the PPS interrupt
#init_time(uart1)
RFRaw       = rb_raw_rf.buffer
chRaw       = rb_raw_ch.buffer
countRaw    = rb_raw_count.buffer
towMsRaw    = rb_raw_ms.buffer
towSubMsRaw = rb_raw_sub.buffer
countCal    = rb_cal_count.buffer
towMsCal    = rb_cal_ms.buffer
towSubMsCal = rb_cal_sub.buffer

while True:
    #print(gc.mem_free())
    #print(gc.mem_alloc())
    gc.collect()
    #micropython.mem_info()

    try:
        if not wifi.wlan.isconnected():
            wifi.con_to_wifi(ssid, password, max_retries = 10)        
        res = (0,0,0)
        maxRxBuf(15000, 20000)        

        # Reset ring buffers, then alias to the names the rest of the loop uses.
        # Replaces: RFRaw=[]; chRaw=[]; countRaw=[]; ... ; toi = []
        raw_write_idx[0] = 0; raw_count[0] = 0
        cal_write_idx[0] = 0; cal_count[0] = 0

        T1=time.ticks_us()
        diff = time.ticks_diff(T1, T0)
        if diff > 5_000_000:
            ##print(gc.mem_free())
            #print(gc.mem_alloc())
            micropython.mem_info()

            uart1.write(POLL_NAV_CLOCK)
            data_msg = (97, mac_id, gc.mem_free(), gc.mem_alloc(), 0,
                        0, 0, 0, 0, 0)
            print(data_msg)
            ustruct.pack_into(send_packet_format, send_buffer,
                              send_buffer_index, *data_msg)
            send_buffer_index += tx_packet_size
            T0=T1
    
        while (res[0] == 0) or (res[4] == 1):
            res = readData()
            #print(res)
            time.sleep(0)

        timeValid = res[3]
        wnoToi=res[0]
        lastC=cal_count[0]-1   # was len(countCal)-1
        lastR=raw_count[0]-1   # was len(countRaw)-1

        for i in range(lastR,-1,-1):
            if countRaw[i]==countCal[lastC]:
                tCal1=towMsCal[lastC]*1000000+(towSubMsCal[lastC])
                tRaw1=towMsRaw[i]*1000000+ towSubMsRaw[i]//1000
                break

        lenRaw=raw_count[0]   # was len(towMsRaw)

        # Was: toi.append((RFRaw[i],timeValid,chRaw[i],wnoToi,Ms,SubMs, countRaw[i], i))
        # Now: pack straight into send_buffer
        for i in range(lenRaw):
            if chRaw[i] == 0:
                tRaw=towMsRaw[i]*1000000+ towSubMsRaw[i]//1000
                res=(tRaw-tRaw1)-((tRaw-tRaw1)*slope//1000000000)+tCal1
                Ms=res//1000000
                SubMs = res - Ms * 1000000
                data_msg = (99, mac_id, RFRaw[i], timeValid, chRaw[i],
                            wnoToi, Ms, SubMs, event_num, countRaw[i])
                #print("datamsg1:",data_msg)
                ustruct.pack_into(send_packet_format, send_buffer,
                                  send_buffer_index, *data_msg)
                send_buffer_index += tx_packet_size

        # Was: scan toi for ch==0 rises, append ch==1 matches to toi
        # Now: scan raw for ch==0 rises, pack ch==1 matches into send_buffer
        for i in range(lenRaw):
            if chRaw[i] == 0 and RFRaw[i] == 0:        # rise on ch0
                tRaw = towMsRaw[i]*1_000_000 + towSubMsRaw[i]//1000
                for j in range(lenRaw):
                    if chRaw[j] == 1:
                        tRaw2 = towMsRaw[j]*1_000_000 + towSubMsRaw[j]//1000
                        diff = tRaw2-tRaw
                        if (diff < 750) and (diff >= 0):
                            res=(tRaw2-tRaw1)-((tRaw2-tRaw1)*slope//1000000000)+tCal1
                            Ms=res//1000000
                            SubMs = res - Ms * 1000000
                            data_msg = (99, mac_id, RFRaw[j], timeValid, 1,
                                        wnoToi, Ms, SubMs, event_num, countRaw[i])
                            #print("datamsg2:", data_msg)

                            ustruct.pack_into(send_packet_format, send_buffer,
                                              send_buffer_index, *data_msg)
                            send_buffer_index += tx_packet_size

        data = send_data(send_buffer[:send_buffer_index])
        #if data:
            #print("!!!!!!!!!!!!!!!!!!!!!data sent", len(send_buffer[:send_buffer_index]))
        send_buffer_index = 0
                
        wdt.feed()
        event_num +=1

    except Exception as e:
        sys.print_exception(e)

        print("Error in main loop", e)
        packet = data_packing(send_packet_format, 100, mac_id, ip_last_byte, 14, 0, 0, 0, 0, 0, 0)
        send_data(packet)
        continue
        
    
    

    


