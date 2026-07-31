import socket
import select
import struct
import os
import re
from datetime import datetime, timedelta
import gzip
import shutil
import time
import traceback
import errno
import datetime

#Changelog:
    #11/14/25- Added socket cleanup function to remove deadsockets
    #Better handled nonblocking send and receive functions with appropriate error catching. SHould hopefully reduce errors.
    #Borehole and veto are broadcasting to eachother filling up TCP socket. Added a recv in each esp code to clear the buffer. Too complicated (as I see) to try and deal with it server side.
    #12/2/25- Event numbers now generated on server


from datetime import datetime, timezone

GPS_UTC_OFFSET = 18  # leap seconds (valid as of 2026)

# Precompute GPS epoch in Unix seconds
GPS_EPOCH_UNIX = datetime(1980, 1, 6, tzinfo=timezone.utc).timestamp()

def gps_to_utc_seconds(gps_week: int, ms_of_week: int, ns_remainder: int) -> float:
    """
    Convert GPS time (week, milliseconds of week, nanoseconds remainder)
    to UTC seconds since Unix epoch.
    """

    # Total seconds into GPS time
    gps_seconds = (
        gps_week * 7 * 24 * 3600
        + ms_of_week / 1000.0
        + ns_remainder / 1e9
    )

    # Convert to Unix time
    unix_time_gps = GPS_EPOCH_UNIX + gps_seconds

    # Subtract leap seconds to get UTC
    unix_time_utc = unix_time_gps - GPS_UTC_OFFSET

    return unix_time_utc

HOST = '0.0.0.0'
PORT = 12345
UDP_PORT = 12346


# Data Format: 
PACKET_FORMAT = "!iiiiiiiiii"
PACKET_SIZE = struct.calcsize(PACKET_FORMAT)
            
class RotatingFileWriter:
    def __init__(self, base_folder_name = "folder", base_file_name="file", ext=".txt", time_length = 10, gzip_files=False, header = ""):
        self.base_data_storage_folder = 'GPS Data'
        self.base_folder_name = base_folder_name
        self.base_file_name = base_file_name
        self.ext = ext
        self.time_length = time_length
        self.gzip_files = gzip_files
        self.date = datetime.now().strftime("%Y%m%d")
        self.folder_run_number = self._get_next_run_number()
        #self.run_number = self._get_next_run_number()
        self.cycle_number = 1
        
        self.header = header
        self.folder_dir = self.open_new_folder()
        self.connection_log = os.path.join(self.folder_dir, "connection_log.txt")
        self.error_log = os.path.join(self.folder_dir, "error_log.txt")
        self.unique_esp_log = os.path.join(self.folder_dir, "unique_esp_log.txt")
        self.stats_log = os.path.join(self.folder_dir, "stats_log.txt")
        self.stats_file = open(self.stats_log, "a", buffering=1)

        self.open_new_file()

    def _get_next_run_number(self):
        """Find the next available run number across all files."""
        run_pattern = re.compile(
            rf"{self.base_folder_name}_(\d+)_(\d+)"
        )
        max_run = 0
        for folder_name in os.listdir(self.base_data_storage_folder):
            match = run_pattern.match(folder_name)
            folder_path = os.path.join(self.base_data_storage_folder, folder_name)

            if os.path.isdir(folder_path):
                if match:
                    run_num = int(match.group(1))
                    max_run = max(max_run, run_num)
        return max_run + 1
    
    def open_new_folder(self):
        folder_name = (
            f"{self.base_folder_name}_{self.folder_run_number:04d}_{self.date}")

        folder_path = os.path.join(self.base_data_storage_folder, folder_name)
        os.mkdir(folder_path)

        return folder_path

    def open_new_file(self):

        if hasattr(self, "file") and self.file:
            self._close_and_gzip()
        self.filename = (
            f"{self.base_file_name}_{self.date}_run{self.folder_run_number:04d}_cycle{self.cycle_number:04d}{self.ext}"
        )
        
        self.file_path = os.path.join(self.folder_dir, self.filename)
        self.file = open(self.file_path, "w", buffering = 1)#buffering=1024*1024)
        self.start_time = datetime.now()

        if self.header:
            self.file.write(self.header + "\n") 

        print(f"[INFO] Opened {self.filename}")
        with open(self.connection_log, 'a') as cl:
            cl.write(f"\nStart Cycle {self.cycle_number}:{datetime.now()}\n")
        with open(self.error_log, 'a') as el:
            el.write(f"\nStart Cycle {self.cycle_number}:{datetime.now()}\n")
        self.stats_file.write(f"\nStart Cycle {self.cycle_number}:{datetime.now()}\n")

        self.cycle_number += 1
        time.sleep(1)



    def _close_and_gzip(self):
        self.file.close()

        if self.gzip_files:
            gz_path = self.file_path + ".gz"
            with open(self.file_path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
            os.remove(self.file_path)
            print(f"[INFO] Compressed {self.file_path} -> {gz_path}")

    def write(self, data: str):
        
        if datetime.now() - self.start_time >= timedelta(hours = self.time_length):
            self.open_new_file()

        self.file.write(data)
        #print(self.current_size)


    def close(self):
        if self.file:
            self._close_and_gzip()
        for fh in (getattr(self, "stats_file", None), getattr(self, "cpu_file", None)):
            try:
                if fh:
                    fh.close()
            except Exception:
                pass


"""def cleanup_client_socket(sock, addr, sockets, clients):
    if sock in sockets:
        sockets.remove(sock)
    if sock in clients:
        del clients[sock]
    sock.close()

    with open(writer.connection_log, 'a') as log:
        log.write(f"{time.time()}: Disconnected from {addr}\n")
    print(f"[SERVER] Dead client socket removed: {addr}")
"""
def cleanup_client_socket(sock, addr, sockets, clients, clients_by_id):
    import traceback
    print(f"[CLEANUP] Removing {addr}")
    traceback.print_stack()
    
    if sock in sockets:
        sockets.remove(sock)

    client_info = clients.get(sock)
    if client_info:
        client_id = client_info.get("id")

        if client_id and clients_by_id.get(client_id) == sock:
            del clients_by_id[client_id]

        del clients[sock]

    sock.close()

    with open(writer.connection_log, 'a') as log:
        log.write(f"{datetime.now()}: Disconnected from {addr}\n")

    print(f"[SERVER] Dead client socket removed: {addr}")
    
def ns_timestamp(ms, sub_ms):

    return (ms*1000000 + sub_ms)

def run_server():

    # Create the server socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    server.setblocking(False)

    print(f"[SERVER] Server listening on {HOST}:{PORT}")

    sockets = [server]  # includes all connected sockets
    clients = {}        # map client socket -> {'buffer': bytearray, 'id': int}
    clients_by_id = {}

    udp_clients = set()

    last_time = 0
    esp_unique_ID_list = []

    event_num_BH = 1
    event_num_veto = -1

    while True:
        if int(time.time())%60==0 and int(time.time())!=last_time: #To let you know server is running
            print(".")
            last_time = int(time.time())

        readable, _, _ = select.select(sockets, [], [], 0.1)

        for s in readable:
            
            if s is server: #Deals with server connects to client sockets
                try:
                    client_socket, addr = server.accept()
                    client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    client_socket.setblocking(False)
                    sockets.append(client_socket)
                    clients[client_socket] = { #Dictionary of client raw data and addresses
                        "buffer": bytearray(),
                        "addr": addr
                    }

                    print(f"[SERVER] New ESP32 connected from {addr}")
                    with open(writer.connection_log, 'a') as log:
                        log.write(f"{datetime.now()}: Reconnected from {addr}\n")

                except OSError as e:
                    if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                        # No client to accept right now, ignore
                        continue
                    else:
                        print(f"[SERVER] Error accepting connection: {addr}; {e}")
                        with open(writer.error_log, 'a') as f:
                            f.write(f"[SERVER] Error accepting connection: {addr}; {e}\n")
                        continue

            else: #Reads client data
                client_info = clients.get(s)
                client_addr = client_info["addr"] if client_info else None
                try:
                    data = s.recv(2048)
                    if not data:  # empty = client closed connection
                        #cleanup_client_socket(s, client_addr, sockets, clients)
                        cleanup_client_socket(s, client_addr, sockets, clients, clients_by_id)
                        continue

                except OSError as e:
                    if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                        # Non-blocking socket has no data, this is fine
                        continue
                    else: #ETimedout isnt being used, ECONNRESET means client coneection was disconnected
                        print(f"[SERVER] Error Receiving from {client_addr}: {e}")
                        print("Debug",  s.fileno())
                        with open(writer.error_log, 'a') as f:
                            f.write(f"[SERVER] Error Receiving from {client_addr}: {e}\n")


                        #cleanup_client_socket(s, client_addr, sockets, clients)
                        cleanup_client_socket(s, client_addr, sockets, clients, clients_by_id)

                        continue

                clients[s]["buffer"].extend(data)
                # Packet buffer to handle multiple packets at the same time
                while len(clients[s]["buffer"]) >= PACKET_SIZE:
                    packet = clients[s]["buffer"][:PACKET_SIZE]
                    clients[s]["buffer"] = clients[s]["buffer"][PACKET_SIZE:]

                    #Unpacks data
                    inst, ID, RF, Cal, ch, w_num, ms, sub_ms, event_num, count = struct.unpack(PACKET_FORMAT, packet)
                    
                    if clients[s].get("id") != ID:
                        existing_sock = clients_by_id.get(ID)

                        if existing_sock is not None and existing_sock != s:
                            old_info = clients.get(existing_sock)
                            old_addr = old_info["addr"] if old_info else None

                            print(f"[SERVER] ID {ID} reconnected. Closing old socket {old_addr}")

                            #cleanup_client_socket(existing_sock, old_addr, sockets, clients)
                            cleanup_client_socket(existing_sock, old_addr, sockets, clients, clients_by_id)
                        clients_by_id[ID] = s
                        clients[s]["id"] = ID

                    if inst == 1: #Info Code
                        with open(writer.connection_log, 'a') as log:
                            log.write(f"{inst}; {ID}; {RF}; {Cal}; {ch}; {w_num}; {ms}; {sub_ms}; {event_num}; {count}\n")

                    elif inst == 100: #Error code
                        #writer.write(f"{inst}; {ID}; {RF}; {Cal}; {ch}; {w_num}; {ms}; {sub_ms}; {event_num}; {count}\n")
                        with open(writer.error_log, 'a') as f:
                            f.write(f"[ESP]:{inst}; {ID}; {RF}; {Cal}; {ch}; {w_num}; {ms}; {sub_ms}; {event_num}; {count}\n") # Ignore labels; RF = Error Code

                    elif inst in (93, 94, 95, 96, 97, 98):
                        # High-rate telemetry -> persistent stats_file handle (NOT a
                        # per-message open(); that throttled the select loop and delayed
                        # the BH timestamp broadcast, producing stale TOIs / "unreasonable"
                        # storms on the arrays). Whole block guarded so a transient I/O
                        # error or an unbound prev_event_num_BH can't break the loop.
                        try:
                            if inst == 97:
                                if ID == 48:
                                    event_num = prev_event_num_BH
                                elif ID == 16:
                                    event_num = event_num_veto  # quirk of the esp-side code
                            writer.stats_file.write(f"{datetime.now()}; {inst}; {ID}; {RF}; {Cal}; {ch}; {w_num}; {ms}; {sub_ms}; {event_num}; {count}\n")
                        except Exception:
                            pass
                        
                    elif inst == 99: #Data Code
                        if ID not in esp_unique_ID_list:
                            esp_unique_ID_list.append(ID)
                            with open(writer.unique_esp_log, 'a') as f:
                                f.write(f"{str(ID)}\n")

                        if ID == 128:
                            
                            if ch == 0 and RF == 0: #Measuring time from rise  
                                event_num = event_num_BH
                                prev_event_num_BH = event_num_BH
                                writer.write(f"{inst}; {ID}; {RF}; {Cal}; {ch}; {w_num}; {ms}; {sub_ms}; {event_num}; {count}\n")

                                event_num_BH+=1

                                rise_BH_timestamp = ns_timestamp(ms, sub_ms)
                                
                                
                                for client_ID in list(clients_by_id.keys()):

                                    if client_ID not in (128,16):
                                        client_sock = clients_by_id.get(client_ID)
                                        
                                        if client_sock is None:
                                            continue
                                        
                                        client_info = clients.get(client_sock)
                                        client_addr = client_info["addr"] if client_info else "Unknown"
                                  
                                        try:
                                            broadcast_format = '!iiiii'
                                            broadcast_packet = struct.pack(broadcast_format, inst, w_num, ms, sub_ms, event_num)
                                            broadcast = client_sock.sendall(broadcast_packet)
                
                                        except OSError as e:
                                            if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                                                # Error can be skipped
                                                continue

                                            else:  # ECONNRESET or other fatal error
                                                print(f"[SERVER] Send Error to {client_addr}: {e}")
                                                with open(writer.error_log, 'a') as f:
                                                    f.write(f"[SERVER] Send Error to {client_addr}: {e}\n")
                                                
                                                #cleanup_client_socket(client_sock, client_addr, sockets, clients)
                                                cleanup_client_socket(client_sock, client_addr, sockets, clients, clients_by_id)

                                                continue
                        

                            if ch == 0 and RF == 1: 

                                fall_BH_timestamp = ns_timestamp(ms,sub_ms)
                                
                                try:
                                    if abs(rise_BH_timestamp-fall_BH_timestamp)<5000:

                                        event_num = prev_event_num_BH
                                        writer.write(f"{inst}; {ID}; {RF}; {Cal}; {ch}; {w_num}; {ms}; {sub_ms}; {event_num}; {count}\n")
                                except Exception:
                                    pass

                            if ch == 1:
                                try:
                                    event_num = prev_event_num_BH
                                    writer.write(f"{inst}; {ID}; {RF}; {Cal}; {ch}; {w_num}; {ms}; {sub_ms}; {event_num}; {count}\n")
                                except Exception:
                                    pass

                        elif ID == 16:

                            if ch == 0 and RF == 0: #Measuring time from rise     
                                event_num = event_num_veto
                                prev_event_num_veto = event_num_veto
                                writer.write(f"{inst}; {ID}; {RF}; {Cal}; {ch}; {w_num}; {ms}; {sub_ms}; {event_num}; {count}\n")

                                event_num_veto-=1

                                rise_veto_timestamp = ns_timestamp(ms, sub_ms)    
                                
                                bh16_t0 = time.perf_counter(); bh16_sent = 0; bh16_drops = 0

                                for client_ID in list(clients_by_id.keys()):
                                    
                                    if client_ID not in (128,16):
                                        client_sock = clients_by_id.get(client_ID)
                                        
                                        if client_sock is None:
                                            continue

                                        client_info = clients.get(client_sock)
                                        client_addr = client_info["addr"] if client_info else "Unknown"
                                        try:
                                            broadcast_format = '!iiiii'
                                            broadcast_packet = struct.pack(broadcast_format, inst, w_num, ms, sub_ms, event_num)

                                            broadcast = client_sock.sendall(broadcast_packet)
                                            bh16_sent += 1                                                   
                                        except OSError as e:
                                            if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                                                # Error can be skipped
                                                bh16_drops += 1
                                                continue

                                            else:  # ECONNRESET or other fatal error
                                                print(f"[SERVER] Send Error to {client_addr}: {e}")
                                                with open(writer.error_log, 'a') as f:
                                                    f.write(f"[SERVER] Send Error to {client_addr}: {e}\n")
                                                
                                                #cleanup_client_socket(client_sock, client_addr, sockets, clients)
                                                cleanup_client_socket(client_sock, client_addr, sockets, clients, clients_by_id)

                                                continue
                                print(f"[BH16] {datetime.now()} toi_ms={ms} toi_sub={sub_ms} "
                                f"fanout_ms={(time.perf_counter()-bh16_t0)*1000:.3f} "
                                f"sent={bh16_sent} eagain_drops={bh16_drops}")
                            if ch == 0 and RF == 1: 

                                fall_veto_timestamp = ns_timestamp(ms,sub_ms)

                                if abs(rise_veto_timestamp-fall_veto_timestamp)<5000:

                                    event_num = prev_event_num_veto
                                    writer.write(f"{inst}; {ID}; {RF}; {Cal}; {ch}; {w_num}; {ms}; {sub_ms}; {event_num}; {count}\n")
                              
                            if ch == 1:
                                try:
                                    event_num = prev_event_num_veto
                                    writer.write(f"{inst}; {ID}; {RF}; {Cal}; {ch}; {w_num}; {ms}; {sub_ms}; {event_num}; {count}\n")
                                except Exception:
                                    pass

                        else: #For other clients
                            writer.write(f"{inst}; {ID}; {RF}; {Cal}; {ch}; {w_num}; {ms}; {sub_ms}; {event_num}; {count}\n")

                    else:
                        #writer.write("Unknown Code\n")
                        #    
                        with open(writer.error_log, 'a') as f:
                            f.write(f"Unknown Code from client {client_addr}\n")

                        clients[s]["buffer"].clear()
                        print(f"Buffer cleared from client {client_addr}")

                        break
        T1 = time.time()
        print(f'Full loop time: {(T1-T0)*1000}ms')

if __name__ == "__main__":

    try:
        while True:
            try:
                
                HEADER = "Req Code; ID; RF; Cal; Ch; W#; t_ow mil; t_ow submil; Event; GPS Count"
                writer = RotatingFileWriter(base_folder_name= "Run", base_file_name="gps_daq", ext=".txt", time_length = 1, header = HEADER) #1 hr long files
                rise_BH_timestamp = 0
                fall_BH_timestamp = 0
                run_server()

            except Exception as e: #Auto-restart server on any errors
                print(f"[FATAL ERROR] {e}")
                traceback.print_exc()
                with open(writer.error_log, 'a') as f:
                    f.write(f"[SERVER] Fatal error: {e}\n{traceback.format_exc()}\n")
                
                writer.close()

                print("Restarting server in 3 seconds...")
                time.sleep(3)

    except KeyboardInterrupt:
        print("DAQ Stopped")
    #Note: Im noticing the esp keeps writting to the TCP buffer even after server shutdown, becasue Im not handling closing the sockets on shutdown.
    #May be something to worry about in the future, but right now its not a concern. I can probably just have a for loop through the clients list

    finally:
        writer.close()
