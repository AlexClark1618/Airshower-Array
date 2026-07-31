import array
import gc
CAPACITY_RAW =  1024
CAPACITY_CAL = 128
raw_write_idx = [0]
raw_count     = [0]
cal_write_idx = [0]
cal_count     = [0]
gc.collect()
# ---------- ringbuffer ----------
# ─── Individual buffers (each knows only its own data + shared state) ───────
class RingBuffer:
    #global raw_write_idx, raw_count, cal_write_idx, cal_count

    def __init__(self, typecode, capacity, write_idx_ref, count_ref):
        if typecode not in ('B', 'I', 'H'):
            raise ValueError("typecode must be 'B' or 'I' or 'H'")
        if typecode == 'I':
            self.mask = 0xFFFFFFFF
            self.buffer = array.array(typecode, bytearray(capacity*4))
           #self.capacity = capacity
        elif typecode == 'H':
            self.mask = 0xFFFF
            self.buffer = array.array(typecode, bytearray(capacity*2))

            #self.capacity = capacity*2
        elif typecode == 'B':
            self.mask = 0xFF
            self.buffer     = array.array(typecode, bytearray(capacity))
            #self.capacity = capacity

        self.typecode   = typecode
        self.capacity   = capacity
        #self.buffer     = array.array(typecode, bytearray(self.capacity))
        self.write_idx  = write_idx_ref       # shared mutable reference
        self.count      = count_ref           # shared mutable reference
        #self.mask       = 0xFF if typecode == 'B' else 0xFFFFFFFF
        #self.mask = 0xFF if typecode == 'B' else 0xFFFF if typecode == 'H' else 0xFFFFFFFF
    def push(self, value: int):
        pos = self.write_idx[0]
        self.buffer[pos] = value & self.mask

    def get(self, n: int) -> int | None:
        
        """n=0 → newest, n=1 → one older, etc."""
        if n < 0 or n >= self.count[0]:
            return None
        # -n because write_idx already points to next free slot
        idx = (self.write_idx[0] - n -1) % self.capacity
        return self.buffer[idx]

    def get_latest(self) -> int | None:
        return self.get(0)

    def get_oldest(self) -> int | None:
        if self.count[0] == 0:
            return None
        #print("oldest", self.write_idx, self.count[0], self.capacity)
        idx = (self.write_idx[0] - self.count[0]) % self.capacity
        return self.buffer[idx]

    def __len__(self):
        return self.count[0]

    @property
    def is_full(self) -> bool:
        return self.count[0] == self.capacity


# ─── Create the raw buffers ─────────────────────────────────────────────────
gc.collect()
#print("free mem1", gc.mem_free())
rb_raw_count = RingBuffer('I', CAPACITY_RAW, raw_write_idx,  raw_count)
gc.collect()
#print("free mem2", gc.mem_free())
rb_raw_ms    = RingBuffer('I', CAPACITY_RAW, raw_write_idx,  raw_count)
gc.collect()
#print("free mem3", gc.mem_free())
rb_raw_sub   = RingBuffer('I', CAPACITY_RAW, raw_write_idx,  raw_count)
gc.collect()
#print("free mem4", gc.mem_free())
rb_raw_wno   = RingBuffer('H', CAPACITY_RAW, raw_write_idx,  raw_count)
gc.collect()
#print("free mem5", gc.mem_free())
rb_raw_rf    = RingBuffer('B', CAPACITY_RAW, raw_write_idx,  raw_count)
gc.collect()
#print("free mem6", gc.mem_free())
rb_raw_ch    = RingBuffer('B', CAPACITY_RAW, raw_write_idx,  raw_count)
gc.collect()
#print("free mem7", gc.mem_free())

# (you can still create cal buffers the old way if they are independent)
#rb_cal_rf    = RingBuffer('B', CAPACITY_CAL, cal_write_idx,  cal_count)
#rb_cal_ch    = RingBuffer('B', CAPACITY_CAL, cal_write_idx,  cal_count)
rb_cal_count = RingBuffer('I', CAPACITY_CAL, cal_write_idx,  cal_count)
rb_cal_ms    = RingBuffer('I', CAPACITY_CAL, cal_write_idx,  cal_count)
rb_cal_sub   = RingBuffer('I', CAPACITY_CAL, cal_write_idx,  cal_count)
rb_cal_wno   = RingBuffer('H', CAPACITY_CAL, cal_write_idx,  cal_count)
gc.collect()
#print("free mem8", gc.mem_free())



@micropython.native
def push_all_raw(rf: int, ch: int, wno: int, ms: int, sub: int, count: int):
    global idx_raw, count_raw

    pos = raw_write_idx[0]
    buf_rf    = rb_raw_rf.buffer
    buf_ch    = rb_raw_ch.buffer
    buf_count = rb_raw_count.buffer
    buf_wno    = rb_raw_wno.buffer
    buf_ms    = rb_raw_ms.buffer
    buf_sub   = rb_raw_sub.buffer
    buf_rf[pos]    = rf
    buf_ch[pos]    = ch
    buf_count[pos] = count
    buf_wno[pos]   = wno
    buf_ms[pos]    = ms
    buf_sub[pos]   = sub
    raw_write_idx[0] = (pos + 1) % CAPACITY_RAW
    if raw_count[0] < CAPACITY_RAW:
        raw_count[0] += 1


@micropython.native
#def push_all_cal(rf: int, ch: int, wno: int, ms: int, sub: int, count: int):
def push_all_cal(wno: int, ms: int, sub: int, count: int):
    global idx_cal, count_cal
    pos = cal_write_idx[0]
#     buf_rf    = rb_cal_rf.buffer
#     buf_ch    = rb_cal_ch.buffer
    buf_count = rb_cal_count.buffer
    buf_wno    = rb_cal_wno.buffer
    buf_ms    = rb_cal_ms.buffer
    buf_sub   = rb_cal_sub.buffer
#     buf_rf[pos]    = rf
#     buf_ch[pos]    = ch
    buf_count[pos] = count
    buf_wno[pos]   = wno
    buf_ms[pos]    = ms
    buf_sub[pos]   = sub
    cal_write_idx[0] = (pos + 1) % CAPACITY_CAL
#     if cal_write_idx[0] >255:
#         print("push_all_cal: idx >255!!!", cal_write_idx[0], pos)
    if cal_count[0] < CAPACITY_CAL:
        cal_count[0] += 1

version_num = "0.01"
# END_OF_FILE_RINGBUFFER
