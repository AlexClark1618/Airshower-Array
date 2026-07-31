import socket, gc, time, os, sys, machine
from machine import WDT, Pin
import ota_update

ota_in_progress = False
prepare_mode = False
s = None
poller = None
uart1 = None
wdt = None
version_num = "0.01"
detector_num = "0"

def _cleanup_for_ota():
    """Segment 5.5: Close DAQ socket, deinit UART1, disable PPS before OTA transfer."""
    print("[LISTENER] === SEGMENT 5.5: CLOSING DAQ SOCKET AND REDUCING LOAD ===")
    try:
        poller.unregister(s)
        print("[LISTENER] Poller unregistered")
    except Exception as e:
        print("[LISTENER] Poller unregister error (non-fatal):", e)
    try:
        s.close()
        print("[LISTENER] DAQ socket closed")
    except Exception as e:
        print("[LISTENER] DAQ socket close error (non-fatal):", e)
    try:
        uart1.deinit()
        print("[LISTENER] UART1 deinitialized (GPS interrupts stopped)")
    except Exception as e:
        print("[LISTENER] UART1 deinit error (non-fatal):", e)
    try:
        Pin(27, Pin.IN).irq(handler=None)
        print("[LISTENER] PPS interrupt disabled")
    except Exception as e:
        print("[LISTENER] PPS IRQ disable error (non-fatal):", e)
    gc.collect()
    print("[LISTENER] Free memory after cleanup:", gc.mem_free())
    # Give lwIP time to complete FIN exchange with Karbon
    # and free TCP segments/pbufs before OTA transfer starts
    print("[LISTENER] Waiting 3s for lwIP TCP cleanup...")
    time.sleep(3)

def start_listener():
    global ota_in_progress, prepare_mode
    addr = socket.getaddrinfo('0.0.0.0', 8080)[0][-1]
    t = socket.socket()
    t.bind(addr)
    t.listen(1)
    print("Listening for OTA trigger on port 8080...")

    while True:
        cl, addr = t.accept()
        print('Client connected from', addr)
        raw_request = cl.recv(1024)
        if not raw_request:
            cl.close()
            continue

        request = raw_request.decode()

        if "/prepare" in request:
            # Two-phase OTA: deinit UART1 and PPS BEFORE the OTA connection arrives.
            # This frees core 0 from UART ISR load (~400-500/sec), allowing lwIP to
            # process TCP at full speed. Required for Windows OTA compatibility —
            # without this, the UART ISR delays TCP ACKs on the ESP32's tiny ~5.7KB
            # receive window, causing zero-window events that Windows' 200ms delayed
            # ACK timer cannot recover from. See ARCHITECTURE.md.
            print("[LISTENER] === PREPARE: DEINITING UART1 AND PPS FOR OTA ===")
            prepare_mode = True
            try:
                uart1.deinit()
                print("[LISTENER] UART1 deinitialized (GPS interrupts stopped)")
            except Exception as e:
                print("[LISTENER] UART1 deinit error (non-fatal):", e)
            try:
                Pin(27, Pin.IN).irq(handler=None)
                print("[LISTENER] PPS interrupt disabled")
            except Exception as e:
                print("[LISTENER] PPS IRQ disable error (non-fatal):", e)
            gc.collect()
            print("[LISTENER] Free memory after prepare:", gc.mem_free())
            cl.send(b"HTTP/1.1 200 OK\r\n\r\nready\n")
            cl.close()
            print("[LISTENER] Prepare complete — ready for OTA connection")
            continue

        elif "/version/" in request:
            # Generalized version probe: /version/<filename> reads version_num from that file
            # NOTE: Must be checked BEFORE /ota routes because filenames like
            # ota_listener.py contain "/ota" substring which would match /ota handler
            try:
                ver_path = request.split(" ")[1]  # e.g. "/version/PPS.py"
                ver_file = ver_path.split("/version/")[1].split("?")[0].split(" ")[0]
                # Read the file and extract version_num
                file_ver = "unknown"
                try:
                    with open(ver_file, "r") as vf:
                        for vline in vf:
                            if vline.strip().startswith("version_num"):
                                file_ver = vline.split("=")[1].strip().strip('"').strip("'")
                                break
                except OSError:
                    file_ver = "FILE NOT FOUND"
                cl.send("HTTP/1.1 200 OK\r\n\r\nDetector " + detector_num + " " + ver_file + " Version: " + file_ver + "\n")
            except Exception as e:
                cl.send(b"HTTP/1.1 400 Bad Request\r\n\r\nBad version request\n")
        elif "/version" in request:
            cl.send("HTTP/1.1 200 OK\r\n\r\nDetector "+ detector_num + " Firmware Version Number: " + version_num + "\n")

        elif "/ota/" in request:
            # GENERALIZED OTA — push any .py or .txt file (except main.py)
            # URL format: POST /ota/<filename> HTTP/1.1
            print("[LISTENER] === GENERALIZED OTA REQUEST ===")
            try:
                # Parse filename from URL path
                ota_path = request.split(" ")[1]  # e.g. "/ota/PPS.py"
                target_file = ota_path.split("/ota/")[1].split("?")[0].split(" ")[0]
                print("[LISTENER] Target file:", target_file)

                # Validate filename
                if "/" in target_file or "\\" in target_file or target_file == "":
                    cl.send(b"HTTP/1.1 400 Bad Request\r\n\r\nInvalid filename\n")
                    cl.close()
                    continue
                if target_file == "main.py":
                    cl.send(b"HTTP/1.1 400 Bad Request\r\n\r\nmain.py must use /ota endpoint\n")
                    cl.close()
                    continue
                if not (target_file.endswith(".py") or target_file.endswith(".txt")):
                    cl.send(b"HTTP/1.1 400 Bad Request\r\n\r\nOnly .py and .txt files allowed\n")
                    cl.close()
                    continue

                # Parse Content-Length
                content_length = 0
                for line in request.split("\r\n"):
                    if line.lower().startswith("content-length:"):
                        content_length = int(line.split(":")[1].strip())
                        break
                print("[LISTENER] Content-Length:", content_length)

                if content_length == 0:
                    cl.send(b"HTTP/1.1 400 Bad Request\r\n\r\nNo Content-Length\n")
                    cl.close()
                    continue

                # Split headers from body
                initial_data = b""
                if b"\r\n\r\n" in raw_request:
                    header_end = raw_request.index(b"\r\n\r\n") + 4
                    initial_data = raw_request[header_end:]

                # Disable WDT (will fail on ESP32 but non-fatal)
                try:
                    WDT(1000000)
                except Exception as e:
                    print("[LISTENER] WDT disable error (non-fatal):", e)

                ota_in_progress = True
                _cleanup_for_ota()

                ota_update.receive_and_install(cl, content_length, initial_data, target_file)

            except Exception as e:
                print("[GEN-OTA] UNEXPECTED ERROR:", e)
                sys.print_exception(e)
                try:
                    cl.send(b"HTTP/1.1 500 Internal Server Error\r\n\r\nOTA failed: " + str(e).encode() + b"\n")
                    time.sleep(1)
                    cl.close()
                except:
                    pass
                continue

        elif "/ota" in request:
            print("[LISTENER] === SEGMENT 1: OTA REQUEST RECEIVED ===")
            print("[LISTENER] Raw request size:", len(raw_request), "bytes")

            # Parse Content-Length from POST headers
            print("[LISTENER] === SEGMENT 2: PARSING HEADERS ===")
            content_length = 0
            for line in request.split("\r\n"):
                if line.lower().startswith("content-length:"):
                    content_length = int(line.split(":")[1].strip())
                    break
            print("[LISTENER] Content-Length:", content_length)

            if content_length == 0:
                print("[LISTENER] ERROR: No Content-Length header found. Is curl sending --data-binary?")
                cl.send(b"HTTP/1.1 400 Bad Request\r\n\r\nNo file data received\n")
                cl.close()
                continue

            # Split headers from body (body starts after \r\n\r\n)
            print("[LISTENER] === SEGMENT 3: SPLITTING HEADERS FROM BODY ===")
            initial_data = b""
            if b"\r\n\r\n" in raw_request:
                header_end = raw_request.index(b"\r\n\r\n") + 4
                initial_data = raw_request[header_end:]
                print("[LISTENER] Header size:", header_end, "bytes")
                print("[LISTENER] Initial body data:", len(initial_data), "bytes")
            else:
                print("[LISTENER] WARNING: No header/body separator found in request")

            print("[LISTENER] === SEGMENT 4: DISABLING WDT ===")
            try:
                WDT(1000000)
                print("[LISTENER] Watchdog disabled for OTA.")
            except Exception as e:
                print("[LISTENER] WDT disable error (non-fatal):", e)

            print("[LISTENER] === SEGMENT 5: SETTING OTA FLAG ===")
            ota_in_progress = True
            print("[LISTENER] ota_in_progress = True")

            _cleanup_for_ota()

            # Response is sent AFTER body is fully read (inside receive_and_install)
            # to keep curl in "sending" mode during the transfer
            print("[LISTENER] === SEGMENT 6: HANDING OFF TO OTA_UPDATE ===")
            ota_update.receive_and_install(cl, content_length, initial_data)

        else:
            cl.send(b"HTTP/1.1 200 OK\r\n\r\nHello from ESP32\n")
        cl.close()
# END_OF_FILE_OTA_LISTENER
