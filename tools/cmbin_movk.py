#!/usr/bin/env python3
# Thread 3: find the CryptoManager SMC fnid dispatch by locating movk Wd/Xd,#0xc200,lsl#16
# encodings across cm.bin, then disasm a window at each. Args: <cm.bin>
import sys, struct, ctypes, ctypes.util
data = open(sys.argv[1], 'rb').read()
N = len(data)
# module file-base -> load VA (from cmbin_parse)
MODS = [(0x0,0x82001000,'CryptoManagerV40'),(0x211000,0x82001800,'fmp_fw_V20'),
        (0x228000,0x82002000,'drm_fw'),(0x379000,0x82003800,'srpmb_fw'),
        (0x3ca000,0x82004000,'hdcp_fw'),(0x3eb000,0x82001800,'tail_fw')]
def mod_of(off):
    cur=MODS[0]
    for m in MODS:
        if off>=m[0]: cur=m
    return cur
def va_of(off):
    b,lv,nm=mod_of(off); return lv+(off-b),nm

# movk Wd,#imm16,lsl#16  = 0x72A00000 | (hw=1<<21) | (imm16<<5) | Rd ; imm16=0xc200 -> 0x72B84000|Rd
# movk Xd,#0xc200,lsl#16 = 0xF2B84000|Rd ;  movz variants 0x52.../0xD2...
TARGETS = {0x72B84000:'movk Wd,#0xc200,lsl#16', 0xF2B84000:'movk Xd,#0xc200,lsl#16',
           0x52B84000:'movz Wd,#0xc200,lsl#16', 0xD2B84000:'movz Xd,#0xc200,lsl#16'}
sites=[]
for off in range(0, N-4, 4):
    w=struct.unpack_from('<I',data,off)[0]
    base=w & 0xFFFFFFE0
    if base in TARGETS:
        sites.append((off,w,TARGETS[base]))
print(f"movk/movz #0xc200,lsl#16 sites: {len(sites)}")
for off,w,desc in sites:
    va,nm=va_of(off)
    print(f"  file 0x{off:x}  VA 0x{va:x}  [{nm}]  Rd=w{w&0x1f}  {desc}")

# disasm a window at each site
cs=ctypes.CDLL(ctypes.util.find_library('capstone') or '/usr/lib64/libcapstone.so.5')
class I(ctypes.Structure):
    _fields_=[("id",ctypes.c_uint),("address",ctypes.c_uint64),("size",ctypes.c_uint16),
              ("bytes",ctypes.c_uint8*24),("mnemonic",ctypes.c_char*32),
              ("op_str",ctypes.c_char*160),("detail",ctypes.c_void_p)]
cs.cs_open.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.POINTER(ctypes.c_size_t)]
cs.cs_disasm.argtypes=[ctypes.c_size_t,ctypes.c_char_p,ctypes.c_size_t,ctypes.c_uint64,
                       ctypes.c_size_t,ctypes.POINTER(ctypes.POINTER(I))]
cs.cs_disasm.restype=ctypes.c_size_t
h=ctypes.c_size_t(); cs.cs_open(1,0,ctypes.byref(h))
for off,w,desc in sites[:12]:
    va,nm=va_of(off); start=off-6*4; vastart=va-6*4
    code=data[start:start+16*4]
    arr=ctypes.POINTER(I)(); n=cs.cs_disasm(h.value,code,len(code),vastart,0,ctypes.byref(arr))
    print(f"\n--- {nm} file 0x{off:x} VA 0x{va:x} ---")
    for i in range(n):
        ins=arr[i]; mk=' <==' if ins.address==va else ''
        print(f"  0x{ins.address:x}: {ins.mnemonic.decode():7} {ins.op_str.decode()}{mk}")
