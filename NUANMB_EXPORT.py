#!BPY
bl_info = {
    "name": "Super Smash Bros. Ultimate Animation Exporter",
    "description": "Exports animation data to NUANMB files (binary animation format used by some games developed by Bandai-Namco)",
    "author": "Carlos, Richard Qian (Worldblender), Ploaj",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "File > Export",
    "category": "Import-Export"}
    
import bpy, enum, io, math, mathutils, os, struct, time, numpy


class AnimType(enum.Enum):
    Transform = 1
    Visibility = 2
    Material = 4
    Camera = 5

class AnimTrackFlags(enum.Enum):
    Transform = 1
    Texture = 2
    Float = 3
    PatternIndex = 5
    Boolean = 8
    Vector = 9
    Direct = 256
    ConstTransform = 512
    Compressed = 1024
    Constant = 1280

def write_c_string(f, s):
    write_chars(f, s)
    write_byte(f, 0) #null terminator

# writes a variable number of empty bytes depending on necessary alignment
def pad(f, alignment):
    while(f.tell() % alignment):
        write_byte(f, 0)
        
def write_byte(f, val):
    f.write(struct.pack('<B', val))

def write_short(f, val):
    f.write(struct.pack('<h', val))
    
def write_ushort(f, val):
    f.write(struct.pack('<H', val))
    
def write_int(f, val):
    f.write(struct.pack('<i', val))
    
def write_uint(f, val):
    f.write(struct.pack('<I', val))
    
def write_float(f, val):
    f.write(struct.pack('<f', val))
    
def write_long64(f, val):
    f.write(struct.pack('<q', val))
    
def write_ulong64(f, val):
    f.write(struct.pack('<Q', val))
    
def write_chars(f, chars):
    f.write(struct.pack('<{}s'.format(len(chars)), chars.encode()))

def write_byte_array(f, ba):
    f.write(ba.getbuffer())
    
def write_bytes(f, bytes):
    for byte in bytes:
        write_byte(f, byte)

#Some longs contain an offset to data, but that offset isn't the absolute file offset its  
# relative to that long's position in the file/buffer.
def write_rel_offset(f, offsetPos):
    #Backup file write pos
    filePosBackup = f.tell()
    
    f.seek(offsetPos) #relative to file start
    write_long64(f, filePosBackup - offsetPos) #value written is the offset from the offsetPos to the data.
    
    f.seek(filePosBackup)


class Group:
    def __init__(self):
        self.nodesAnimType = 0
        self.nodesOffsetPos = 0
        self.nodesOffset = 0
        self.nodes = []
        
class Node:
    def __init__(self):
        self.name = ""
        self.nodeNameOffset = 0
        self.nodeNameOffsetPos = 0
        self.nodeDataOffset = 0
        self.nodeDataOffsetPos = 0
        self.nodeAnimTrack = NodeAnimTrack()
        self.materialSubNodes = [] #hack for materials + camera.
        
class NodeAnimTrack:
    def __init__(self):
        self.name = ""
        self.type = ""
        self.typeOffset = 0
        self.typeOffsetPos = 0
        self.flags = 0
        self.frameCount = 0
        self.dataOffset = 0 
        self.dataSize = 0
        self.unk3 = 0
        self.animationTrack = [] # could be an array of matrix4x4, or vector4, or bools, or floats, or...
                                
        
    def __repr__(self):
        return "Node name: " + str(self.name) + "\t| Type: " + str(self.type) + "\t| Flags: " + str(self.flags) + "\t| # of frames: " + str(self.frameCount) + "\t| Data offset: " + str(self.dataOffset) + "\t| Data size: " + str(self.dataSize) + "\n"
   
class Quantanizer:
    def __init__(self, valueArray, epsilon):
        de_nan_array(valueArray)
        #self.values = valueArray
        self.min = min(valueArray)
        self.max = max(valueArray)
        if math.isclose(self.min, 1, rel_tol=1e-04):
            self.min = 1
        if math.isclose(self.max, 1, rel_tol=1e-04):
            self.max = 1
        if math.isclose(self.min, 0, abs_tol=1e-04):
            self.min = 0
        if math.isclose(self.max, 0, abs_tol=1e-04):
            self.max = 0
        if math.isclose(self.min, self.max, rel_tol=1e-04):
            self.min = self.max
        self.constant = self.min == self.max
        self.bitCount = self.calc_bit_count(epsilon, valueArray)
        
    def __repr__(self):
        return "min: " + str(self.min) + " max: " + str(self.max) + " constant: " + str(self.constant)  + " bitCount: " + str(self.bitCount) + "\t"
        
    def calc_bit_count(self, epsilon, valueArray):
        if self.constant:
            return 0
        while epsilon < 1:
            for bits in range(1, 31):
                if self.compute_error(bits, valueArray) < epsilon:
                    return bits
            epsilon *= 2
        return -1 #Failed to find an optimal bit count. idk if this ever happens
        
    def compute_error(self, bits, valueArray):
        e = 0
        if self.constant:
            return 0
        for v in valueArray:
            ce = abs(v - self.decompressed_value(v,bits))
            e = max(e, ce)
        return e 

    def decompressed_value(self, v, bits): 
        qv = quantanization_value(bits)    
        if qv == 0:
            return 0
               
        dv = lerp(self.min, self.max, 0, 1, self.quantanize(v, bits) / quantanization_value(bits))
        return dv if not math.isnan(dv) else 0 #I dont think python generates NaNs like in C#
        
    def quantanize(self, v, bits):
        if v <= self.min:
            return 0
        
        if v >= self.max:
            return quantanization_value(bits)
        
        #Quantanized value, which is supposed to be an integer    
        quantanized = (v - self.min) / (self.max - self.min) * quantanization_value(bits)
        quantanized = math.trunc(quantanized)
        return quantanized
   
    
def quantanization_value(bitCount):
    v = 0
    for i in range(0, bitCount):
        v |= 1 << i
    return v
        
def lerp(av, bv, v0, v1, t): #idk whats going on in here tbh tbh
    if v0 == v1:
        return av
    if t == v0:
        return av
    if t == v1:
        return bv    
    mu = (t - v0) / (v1 - v0)
    val = ( (av * (1 - mu)) + (bv * mu))
    return val if not math.isnan(val) else 0
        
def de_nan_array(va):
    for v in va:
        if math.isnan(v):
            print("NaN")
            v = 0.0    


def material_group_hacks(f, g):
    pad(f, 0x8) #8-byte alignment for arrays
    write_rel_offset(f, g.nodesOffsetPos)
    for node in g.nodes:
        node.nodeNameOffsetPos = f.tell()
        write_long64(f, 0) #Placeholder offset, node name e.g. "EyeL"
        node.nodeDataOffsetPos = f.tell()
        write_long64(f, 0) #Placeholder offset, probably node data offset
        write_long64(f, len(node.materialSubNodes)) #Material nodes have subnodes, e.g. CustomBoolean1. Length is 9 for "EyeL"
        pad(f, 0x8)
        
    for node in g.nodes:
        pad(f, 0x4) #4-byte alignent for strings, about to write "EyeL"
        write_rel_offset(f, node.nodeNameOffsetPos)
        write_c_string(f, node.name)
        pad(f, 0x8) #8-byte alignment for arrays
        write_rel_offset(f, node.nodeDataOffsetPos)
        
        for msn in node.materialSubNodes:
            nat = msn.nodeAnimTrack
            nat.typeOffsetPos = f.tell()
            write_long64(f, 0) #A temp offset to the type name
            write_uint(f, nat.flags)
            write_uint(f, nat.frameCount)
            write_uint(f, nat.unk3)
            write_uint(f, nat.dataOffset)
            write_long64(f, nat.dataSize)
            pad(f, 0x8)
            
        for msn in node.materialSubNodes:
            nat = msn.nodeAnimTrack
            pad(f, 0x4) #4-byte alignement for strings, about to write "CustomVector0"
            write_rel_offset(f, nat.typeOffsetPos)
            write_c_string(f, nat.type)
            #...Repeat for all custom vectors, looks like the type names are contiguous
    
    #Umm after this the massive unified animation data buffer gets written
    #what happened to the custom bools and floats????
    #Turns out studiosb doesnt write them out
        
def write_group_array(f, groups):
    
    #write out some preliminary node stuff for all groups
    for g in groups: 
        write_long64(f, g.nodesAnimType) #Write the AnimType of the group, check out the enums
        g.nodesOffsetPos = f.tell()
        write_long64(f, 0) #Temp 'NodeOffset'
        write_long64(f, len(g.nodes)) #NodeCount, a 'Node' could be something like a bone in an AnimTrack
        pad(f, 0x8) #probably not necessary since just wrote 3 long64s...
    
    #now actually write out the nodes  
    for g in groups:
        if (g.nodesAnimType == AnimType.Material.value or g.nodesAnimType == AnimType.Camera.value):
            material_group_hacks(f, g)
            continue
        
        pad(f, 0x8) #8-byte alignment for arrays
        write_rel_offset(f, g.nodesOffsetPos) 
        
        for node in g.nodes: #Node Prep 
            node.nodeNameOffsetPos = f.tell()
            write_long64(f, 0) #Temp node name offset
            node.nodeDataOffsetPos = f.tell()
            write_long64(f, 0) #Temp node data offset
            write_long64(f, 1) #'Array.length', but it seems like only materials have multiple sub nodes in the array
            pad(f, 0x8) #Probably not necessary, since only longs got written
            
        for node in g.nodes: #Node Finalizer Loop
            pad(f, 0x4) #4-byte alignement for strings
            write_rel_offset(f, node.nodeNameOffsetPos) #about to write name so go fill-in offset
            write_c_string(f, node.name) #e.g "ArmL"
            pad(f, 0x8) #8-byte alignment for arrays
            write_rel_offset(f, node.nodeDataOffsetPos)#node data? like, the flags,framecount, AnimType, etc
            #Time to write out the node data, order is important
            nat = node.nodeAnimTrack
            nat.typeOffsetPos = f.tell()
            write_long64(f, 0) # A temp offset to the TypeName. Idk why its done this way rather than just write out the enum
            write_uint(f, nat.flags)
            write_uint(f, nat.frameCount)
            write_uint(f, nat.unk3)
            write_uint(f, nat.dataOffset) #Shouldnt this be unknown at this point? Already known in studiosb, which means the data buffer was already calculated at this point
            write_long64(f, nat.dataSize) # guess ill just premake the animation data buffer.
                                          # dataOffset refers to its offset in the unified data buffer that contains all data for all nodes in all tracks.
                                          # so, data offset will be 0 for the first entry
            pad(f, 0x8)
            pad(f, 0x4)#4-byte alignement for strings
            write_rel_offset(f, nat.typeOffsetPos)
            write_c_string(f, nat.type)
            
            

def write_nuanmb(f, animBuffer, groups, finalFrameIndex, animName):
    write_chars(f, "HBSS")
    write_int(f, 0x40)# 4 bytes
    pad(f, 0x10)#16-Byte Aligned Header
    write_uint(f, 0x414E494D) #Magic, 4 bytes
    write_ushort(f, 0x0002) #VersionMajor, 2 bytes
    write_ushort(f, 0x0000) #VersionMinor, 2 bytes
    write_float(f, finalFrameIndex) # FFI, 4 bytes
    write_ushort(f, 0x0001) #Unk1, 2 bytes
    write_ushort(f, 0x0003) #Unk2, 2 bytes
    
    animNameOffset = f.tell()
    write_long64(f, 0) # Placeholder relative offset for anim name, 8 bytes
    
    groupOffset = f.tell()
    write_long64(f, 0) # Placeholder relative offset for animation arrays, aka the 'GroupOffset', 8 bytes
    
    write_long64(f, len(groups))#e.g '3' for anim w/ 'Transform', 'Visibility', 'Material' tracks, 8 bytes
   
    bufferOffset = f.tell()
    write_long64(f, 0) #Placeholder relative offset for GroupData "BufferOffset"
    
    write_long64(f, animBuffer.getbuffer().nbytes) # "BufferSize"
    
    pad(f, 0x8) #8 Bytes
    
    pad(f, 0x4) #4 Byes, necessary padding because file name string will be written
    write_rel_offset(f, animNameOffset) #Nows a good time to fix the temp offset
    write_c_string(f, animName) #variable bytes
    pad(f, 0x4) #4 byes, apparently  strings are padded before and after?
    
    pad(f, 0x8) # 8-byte alignement for arrays and matl data objects
    write_rel_offset(f, groupOffset)
    write_group_array(f, groups)
    
    #ready to write beeg buffer
    pad(f, 0x8)
    write_rel_offset(f, bufferOffset)
    write_byte_array(f, animBuffer)
    
def make_anim_buffer(context, groups, compression):
    b = io.BytesIO()
    for g in groups:
        for node in g.nodes:
            if node.materialSubNodes: #Material or Camera
                for sn in node.materialSubNodes:
                    write_track_from_nat(b, sn.nodeAnimTrack, compression)
            else: #Normal
                write_track_from_nat(b, node.nodeAnimTrack, compression)
    return b

def write_uncompressed_tranform(b, nat):
    for af in nat.animationTrack: #af means "AnimationFrame"
        '''
        Smash matrix
          0   1   2   3
        0 SX  SY  SZ  N/A
        1 RX  RY  RZ  RW
        2 PX  PY  PZ  0
        '''
        sx = af[0][0]; sy = af[0][1]; sz = af[0][2]
        rx = af[1][0]; ry = af[1][1]; rz = af[1][2]; rw = af[1][3]
        px = af[2][0]; py = af[2][1]; pz = af[2][2]
        
        write_float(b, sx); write_float(b, sy); write_float(b, sz)
        write_float(b, rx); write_float(b, ry); write_float(b, rz); write_float(b, rw)
        write_float(b, px); write_float(b, py); write_float(b, pz); 
        write_float(b, 0); #Always 0?
        
        #Wrote Direct, so set Direct Flags
        nat.flags |= AnimTrackFlags.Direct.value
   
def all_same(nat):
    allSame = True
    first = nat.animationTrack[0]
    for af in nat.animationTrack:
        if first != af:
            allSame = False
            break
        
    return allSame

def write_const_transform(b, nat):
    af = nat.animationTrack[0]
    
    sx = af[0][0]; sy = af[0][1]; sz = af[0][2]
    rx = af[1][0]; ry = af[1][1]; rz = af[1][2]; rw = af[1][3]
    px = af[2][0]; py = af[2][1]; pz = af[2][2]

    write_float(b, sx); write_float(b, sy); write_float(b, sz)
    write_float(b, rx); write_float(b, ry); write_float(b, rz); write_float(b, rw)
    write_float(b, px); write_float(b, py); write_float(b, pz); 
    write_float(b, 0); #Always 0?

    nat.flags |= AnimTrackFlags.ConstTransform.value
    
def write_compressed_transform(b, nat):
    
    nat.flags |= AnimTrackFlags.Compressed.value
    
    epsilon = 0.000002 # Maybe allow this to be set by user, but might just be confusing.
    
    #Make the 'Animation Track' into a numpy array for vertical slicing
    at = numpy.array(nat.animationTrack) 
      
    sx = Quantanizer(at[:, 0, 0], epsilon)
    sy = Quantanizer(at[:, 0, 1], epsilon)
    sz = Quantanizer(at[:, 0, 2], epsilon)
    rx = Quantanizer(at[:, 1, 0], epsilon)
    ry = Quantanizer(at[:, 1, 1], epsilon)
    rz = Quantanizer(at[:, 1, 2], epsilon)
    px = Quantanizer(at[:, 2, 0], epsilon)
    py = Quantanizer(at[:, 2, 1], epsilon)
    pz = Quantanizer(at[:, 2, 2], epsilon)
    
    hasScale = not (sx.constant and sy.constant and sz.constant)
    hasRotation = not (rx.constant and ry.constant and rz.constant)
    hasPosition = not (px.constant and py.constant and pz.constant)
    
    """
    print("nat.name = " + str(nat.name))
    print("sx:" + str(sx) + "\t sy:" + str(sy) + "\t sz:" + str(sz) + 
        "\t rx:" + str(rx) + "\t ry:" + str(ry) + "\t rz:" + str(rz) +
        "\t px:" + str(px) + "\t py:" + str(py) + "\t pz:" + str(pz) )
    
    print("sx = {" + str(at[:,0,0]) + "}\n")
    """
    
    #print("rx = {" + str(at[:,1,0]) + "}\n")
    
    
    cFlags = 0 #Compression Flags
    bitsPerEntry = 0
    
    if sx.bitCount == -1 or sy.bitCount == -1 or sz.bitCount == -1 \
    or rx.bitCount == -1 or ry.bitCount == -1 or rz.bitCount == -1 \
    or px.bitCount == -1 or py.bitCount == -1 or pz.bitCount == -1:
        print("Compression Level too small to compress")
        return
    
    if hasScale:
        cFlags |= 0x01
        bitsPerEntry += sx.bitCount if not sx.constant else 0
        bitsPerEntry += sy.bitCount if not sy.constant else 0
        bitsPerEntry += sz.bitCount if not sz.constant else 0
    else:
        cFlags |= 0x02
    
    if hasRotation:
        cFlags |= 0x04
        bitsPerEntry += rx.bitCount if not rx.constant else 0
        bitsPerEntry += ry.bitCount if not ry.constant else 0
        bitsPerEntry += rz.bitCount if not rz.constant else 0
        bitsPerEntry += 1 #The 1 is for extra W rotation bit 
    
    if hasPosition:
        cFlags |= 0x08
        bitsPerEntry += px.bitCount if not px.constant else 0
        bitsPerEntry += py.bitCount if not py.constant else 0
        bitsPerEntry += pz.bitCount if not pz.constant else 0
    
    
    #Compressed Header
    write_short(b, 0x04)
    write_short(b, cFlags)
    write_short(b, 160) #Not Hex in StudioSB
    write_ushort(b, bitsPerEntry)
    write_int(b, 204) #Not Hex in StudioSB
    write_int(b, len(nat.animationTrack))
    write_float(b, sx.min)
    write_float(b, sx.max)
    write_long64(b, sx.bitCount if hasScale else 16)
    write_float(b, sy.min)
    write_float(b, sy.max)
    write_long64(b, sy.bitCount if hasScale else 16)
    write_float(b, sz.min)
    write_float(b, sz.max)
    write_long64(b, sz.bitCount if hasScale else 16)
    write_float(b, rx.min)
    write_float(b, rx.max)
    write_long64(b, rx.bitCount if hasRotation else 16)
    write_float(b, ry.min)
    write_float(b, ry.max)
    write_long64(b, ry.bitCount if hasRotation else 16)
    write_float(b, rz.min)
    write_float(b, rz.max)
    write_long64(b, rz.bitCount if hasRotation else 16)
    write_float(b, px.min)
    write_float(b, px.max)
    write_long64(b, px.bitCount if hasPosition else 16)
    write_float(b, py.min)
    write_float(b, py.max)
    write_long64(b, py.bitCount if hasPosition else 16)
    write_float(b, pz.min)
    write_float(b, pz.max)
    write_long64(b, pz.bitCount if hasPosition else 16)
    dv = nat.animationTrack[0] #Default Values
    write_float(b, dv[0][0])
    write_float(b, dv[0][1])
    write_float(b, dv[0][2])
    write_float(b, dv[1][0])
    write_float(b, dv[1][1])
    write_float(b, dv[1][2])
    write_float(b, dv[1][3])
    write_float(b, dv[2][0])
    write_float(b, dv[2][1])
    write_float(b, dv[2][2])
    write_int(b, 0)
    
    #Now we can finally write the bits
    bitString = ""
    frame = 0
    for af in nat.animationTrack:
        if hasScale:
            #print("Frame: " + str(frame) + " af[0][0] = " + str(af[0][0]))
           # print("sx.quantanize = " + str(sx.quantanize(af[0][0], sx.bitCount)) + " ")
            bitString += get_bits(sx.quantanize(af[0][0], sx.bitCount), sx.bitCount)
            bitString += get_bits(sy.quantanize(af[0][1], sy.bitCount), sy.bitCount)
            bitString += get_bits(sz.quantanize(af[0][2], sz.bitCount), sz.bitCount)

        if hasRotation:
            #print("Frame: " + str(frame) + " af[1][0] = " + str(af[1][0]))
            #print("rx.quantanize = " + str(rx.quantanize(af[1][0], rx.bitCount)) + " ")
            bitString += get_bits(rx.quantanize(af[1][0], rx.bitCount), rx.bitCount)
            bitString += get_bits(ry.quantanize(af[1][1], ry.bitCount), ry.bitCount)
            bitString += get_bits(rz.quantanize(af[1][2], rz.bitCount), rz.bitCount)
            
        if hasPosition:
            bitString += get_bits(px.quantanize(af[2][0], px.bitCount), px.bitCount)
            bitString += get_bits(py.quantanize(af[2][1], py.bitCount), py.bitCount)
            bitString += get_bits(pz.quantanize(af[2][2], pz.bitCount), pz.bitCount)
            if not pz.constant:
                print("Frame: " + str(frame) + ", af[2][2] = " + str(af[2][2]) + ", pz.quantize = " + str(pz.quantanize(af[2][2], pz.bitCount)) 
                    + ",pz.bitCount =" + str(pz.bitCount) + ", bits = " + str(get_bits(pz.quantanize(af[2][2], pz.bitCount), pz.bitCount)))
        if hasRotation:
            #'flip-W' bit
            w = math.sqrt(math.fabs( 1 - (
                rx.decompressed_value(af[1][0], rx.bitCount)**2 +
                ry.decompressed_value(af[1][1], ry.bitCount)**2 +
                rz.decompressed_value(af[1][2], rz.bitCount)**2)))
            fBit = 1 if (af[1][3] < 0) != (w < 0) else 0
            bitString += get_bits(fBit, 1)
        frame += 1
        
    #print("bitString Length = " + str(len(bitString)))
    #print("bitString = " + str(bitString))
    if bitString != "":       
        ba = get_bytes(bitString)
        write_bytes(b, ba)

def get_bits(value, bitCount):
    bits = ""
    for i in range(bitCount):
        bit = (value >> i) & 0x1
        bits += format(bit, 'b')  
    return bits

def get_bytes(bitString):
    ba = []
    byte = 0
    bitCounter = 0
    for bit in bitString:
        byte |= int(bit, 2) << bitCounter
        bitCounter += 1
        if bitCounter == 8:
            ba.append(byte)
            byte = 0
            bitCounter = 0 
    if bitCounter != 0:
        ba.append(byte) 
    return ba    


"""
def write_transform(b, nat):
    if all_same(nat):
        write_const_transform(b, nat)
    else:
        write_compressed_transform(b, nat)
"""
    
def write_track_from_nat(b, nat, compression):
    nat.dataOffset = b.tell()
    nat.frameCount = len(nat.animationTrack)
    
    if ((nat.flags & 0x00ff) == AnimTrackFlags.Transform.value):
        if all_same(nat):
            write_const_transform(b, nat)
            nat.frameCount = 1
        elif compression:
            write_compressed_transform(b, nat)
        else:
            write_uncompressed_tranform(b, nat)
            
    elif ((nat.flags & 0x00ff) == AnimTrackFlags.Float.value):
        for af in nat.animationTrack:
            write_float(b,af)
        if (nat.frameCount == 1):
            nat.flags |= AnimTrackFlags.Constant.value
        else:
            nat.flags |= AnimTrackFlags.Direct.value
    
    elif ((nat.flags & 0x00ff) == AnimTrackFlags.Boolean.value):
        for af in nat.animationTrack:
            write_byte(b,af)
        if (nat.frameCount == 1):
            nat.flags |= AnimTrackFlags.Constant.value
        else:
            nat.flags |= AnimTrackFlags.Direct.value
        
    elif (nat.flags & 0x00ff) == AnimTrackFlags.Vector.value:
        for af in nat.animationTrack:
            for i in af: #[0, 1 , 2 , 3] Should be a vector of 4 values
                write_float(b, i)
        if (nat.frameCount == 1):
            nat.flags |= AnimTrackFlags.Constant.value
        else:
            nat.flags |= AnimTrackFlags.Direct.value
            
    
    nat.dataSize = b.tell() - nat.dataOffset
    pad(b, 0x64)
            
            
def gather_camera_groups(context):    
    #Blender stuff
    sce = bpy.context.scene #blender scene
    c = bpy.context.object #blender Camera
    
    #Cameras have 2 groups, a "Transform" and a "Camera" group
    groups = []
    
    #Make Transform Group
    tg = Group()
    tg.nodesAnimType = AnimType.Transform.value
    
    #Make Transform Node
    tn = Node()
    tn.name = c.name
    
    #make NodeAnimTrack
    tnat = tn.nodeAnimTrack
    for f in range(sce.frame_start, sce.frame_end):
        sce.frame_set(f)
        sx = c.scale[0]; sy = c.scale[1]; sz = c.scale[2]
        rw = c.rotation_quaternion[0] #Blender has RW in first index, Smash has it in last
        rx = c.rotation_quaternion[1]
        ry = c.rotation_quaternion[2]
        rz = c.rotation_quaternion[3]
        px = c.location[0]; py = c.location[1]; pz = c.location[2]
        tnat.animationTrack.append([[sx, sy, sz, 1], [rx, ry, rz, rw], [px, py, pz, 1]])
        tnat.flags |= AnimTrackFlags.Transform.value
        tnat.type = "Transform"
    
    tn.nodeAnimTrack = tnat
    tg.nodes.append(tn)
    
    #Make Camera Group
    cg = Group()
    cg.nodesAnimType = AnimType.Camera.value
    
    #Make Camera Node
    cn = Node()
    cn.name = c.name + "Shape" 
    
    #Make Camera Subnodes as if it were material
    csnFarClip = Node()
    csnFieldOfView = Node()
    csnNearClip = Node()
    
    #FarClip seems to be the same value in all investigated tracks
    cnat = csnFarClip.nodeAnimTrack
    cnat.animationTrack.append(100000.0)
    cnat.flags |= AnimTrackFlags.Float.value
    cnat.flags |= AnimTrackFlags.Constant.value
    cnat.type = "FarClip"
    csnFarClip.nodeAnimTrack = cnat
    
    #Field of view changes throughout an animation, proper keyframing is planned
    cnat = csnFieldOfView.nodeAnimTrack
    cnat.flags |= AnimTrackFlags.Float.value
    cnat.type = "FieldOfView"
    for f in range(sce.frame_start, sce.frame_end):
        sce.frame_set(f)
        cnat.animationTrack.append(c["FOV"]) #Todo: Figure out FOV conversion, dont hardcode this value
    csnFieldOfView.nodeAnimTrack = cnat
    
    #NearClip seems to be the same value in all investigated tracks
    cnat = csnNearClip.nodeAnimTrack
    cnat.animationTrack.append(1.0)
    cnat.flags |= AnimTrackFlags.Float.value
    cnat.flags |= AnimTrackFlags.Constant.value
    cnat.type = "NearClip"
    csnNearClip.nodeAnimTrack = cnat
        
    
    
    
    cn.materialSubNodes.append(csnFarClip)
    cn.materialSubNodes.append(csnFieldOfView)
    cn.materialSubNodes.append(csnNearClip)
 
    cg.nodes.append(cn)
    
    
    groups.append(tg) 
    groups.append(cg)
    return groups
    
def gather_groups(context, exportSplit): 
    #Blender Setup
    obj = bpy.context.object
    sce = bpy.context.scene
    
    #Groups Setup
    groups = []
    
    #Make Transform group
    tg = Group()
    tg.nodesAnimType = AnimType.Transform.value
    
    bones = []
    if exportSplit:
        fcurves = obj.animation_data.action.fcurves
        for curve in fcurves:
            if not curve.group.select:
                continue
            bn = curve.data_path.split('"')[1]
            pb = obj.pose.bones.get(bn)
            if pb:
                if pb not in bones:
                    bones.append(pb)
            
    else:
        for bone in obj.pose.bones:
            bones.append(bone)

    # Re-Write, current theory is that updating frames is expensive, so here will only go through all frames once.
    ignore_markers = ['_eff', 'H_', '_offset', '_null']

    # Transform Group Prep
    for bone in bones: 
        if any(ss in bone.name for ss in ignore_markers):
            bones.remove(bone)

    bone_node_dict = {} # Key is the bone name, Value is the transform node
    for bone in bones:
        tn = Node()
        tn.name = bone.name
        nat = tn.nodeAnimTrack
        nat.flags |= AnimTrackFlags.Transform.value
        nat.type = "Transform"
        bone_node_dict[bone.name] = tn

    # Visibility Group Prep
    vis_group = Group()
    vis_group.nodesAnimType = AnimType.Visibility.value

    vis_markers = ['_VIS_O']
    vis_meshes = []
    for child in obj.children:
        if not any(ss in child.name for ss in vis_markers):
            continue
        if exportSplit:
            curve_selected = False
            for curve in child.animation_data.action.fcurves:
                if curve.group.select:
                    curve_selected = True
            if curve_selected == False:
                continue
        if child in vis_meshes:
            continue
        vis_meshes.append(child)
    
    vis_mesh_node_dict = {} #Key is vis_mesh name, Value is the vis node
    for vis_mesh in vis_meshes:
        vis_name = None
        for vis_marker in vis_markers:
            if vis_marker in vis_mesh.name:
                vis_name = vis_mesh.name.split(vis_marker)[0]
        vis_node = Node()
        vis_node.name = vis_name
        nat = vis_node.nodeAnimTrack
        nat.flags |= AnimTrackFlags.Boolean.value
        nat.type = 'Visibility'
        vis_mesh_node_dict[vis_mesh] = vis_node

    
    # Material Group Prep
    mat_group = Group()
    mat_group.nodesAnimType = AnimType.Material.value

    mat_name_main_node_dict = {} # Key is mat name, Value is the main node (Material nodes are wierd and have 'subnodes')
    mat_prop_sub_node_dict = {} # Key is mat prop, Value is the sub node
    main_node_sub_nodes_dict = {} # Key is main node, Value is the list of sub nodes
    sub_node_blender_property_dict = {}
    for key, value in obj.items(): #Key Format for materials should be nat.name:nat.type
        if ':' not in key:
            continue
        mat_name = key.split(':')[0] # e.g. 'EyeL'
        mat_property = key.split(':')[1] # e.g. 'CustomVector6'

        if mat_name not in mat_name_main_node_dict.keys():
            mat_main_node = Node()
            mat_main_node.name = mat_name
            mat_name_main_node_dict[mat_name] = mat_main_node
        
        prop_sub_node = Node()
        nat = prop_sub_node.nodeAnimTrack
        if 'Boolean' in mat_property:
            nat.flags |= AnimTrackFlags.Boolean.value
        elif 'Float' in mat_property:
            nat.flags |= AnimTrackFlags.Float.value
        elif 'Vector' in mat_property:
            nat.flags |= AnimTrackFlags.Vector.value
        else:
            print('Unknown Material Property Type %s' % (mat_property))
            continue
        nat.type = mat_property
        mat_prop_sub_node_dict[mat_property] = prop_sub_node

        main_node = mat_name_main_node_dict[mat_name]
        if main_node not in main_node_sub_nodes_dict:
            main_node_sub_nodes_dict[main_node] = []
        sub_node_list = main_node_sub_nodes_dict[main_node]
        sub_node_list.append(prop_sub_node)
        sub_node_blender_property_dict[prop_sub_node] = key


        
    # Go through each frame, and fill out the nodes for each group
    for frame in range(sce.frame_start, sce.frame_end):
        sce.frame_set(frame)
        for bone in bones:
            tn = bone_node_dict[bone.name]
            trans = None
            rot = None
            scale = None
            nat = tn.nodeAnimTrack
            if not bone.parent:
                trans = bone.matrix.to_translation()
                rot = bone.matrix.to_quaternion()
                scale = bone.matrix.to_scale()
            else:
                pmi = bone.parent.matrix.inverted()
                rm = pmi @ bone.matrix
                trans = rm.to_translation()
                rot = rm.to_quaternion()
                scale = rm.to_scale()
            if frame != sce.frame_start:
                previous_frame_smash_quaternion = nat.animationTrack[frame - sce.frame_start - 1][1][:]
                p = previous_frame_smash_quaternion
                previous_frame_blender_quaternion = mathutils.Quaternion([p[3],p[0],p[1],p[2]])
                if previous_frame_blender_quaternion.dot(rot) < 0:
                    rot.negate()
            nat.animationTrack.append([ [scale[0], scale[1], scale[2], 1],
                                        [rot[1], rot[2], rot[3], rot[0]],
                                        [trans[0], trans[1], trans[2], 1] ])
        
        for vis_mesh in vis_meshes:
            vis_node = vis_mesh_node_dict[vis_mesh]
            nat = vis_node.nodeAnimTrack
            is_visible = not vis_mesh.hide_render
            nat.animationTrack.append(is_visible)

        for main_node, sub_node_list in main_node_sub_nodes_dict.items():
            for sub_node in sub_node_list:
                nat = sub_node.nodeAnimTrack
                blender_property = obj[sub_node_blender_property_dict[sub_node]]
                bp = blender_property
                if 'Vector' in nat.type:
                    nat.animationTrack.append([bp[0], bp[1], bp[2], bp[3]])
                else:
                    nat.animationTrack.append(bp)

    # Add the Nodes to their Group and then add the groups to the list.
    for bone_node in bone_node_dict:
        tg.nodes.append(bone_node_dict[bone_node])
    tg.nodes.sort(key = lambda node: node.name)

    for vis_mesh in vis_mesh_node_dict:
        vis_group.nodes.append(vis_mesh_node_dict[vis_mesh])
    vis_group.nodes.sort(key = lambda node: node.name)

    for main_node, sub_node_list in main_node_sub_nodes_dict.items():
        for sub_node in sub_node_list:
            main_node.materialSubNodes.append(sub_node)

    for main_node in main_node_sub_nodes_dict.keys():
        mat_group.nodes.append(main_node)
    
    groups.append(tg)
    groups.append(vis_group)
    groups.append(mat_group)

    return groups
    
def export_nuanmb_main(context, filepath, compression, exportSplit):
 
    print(str(filepath))
    fileName = os.path.basename(filepath)
    print(str(fileName))
    groups = []
    
    if (context.active_object.type == 'CAMERA'):
        compression = False # Smash Camera Anims are not compressed
        groups = gather_camera_groups(context)
    else:
        groups = gather_groups(context, exportSplit)
    
    animBuffer = make_anim_buffer(context, groups, compression)
    
    s = bpy.context.scene
    finalFrameIndex = s.frame_end - s.frame_start - 1
 
    with open(filepath, 'wb') as f:
        write_nuanmb(f, animBuffer, groups, finalFrameIndex, fileName)

    return {'FINISHED'}


# ExportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator


class ExportSomeData(Operator, ExportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "export_test.some_data"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Export .nuanmb"

    # ExportHelper mixin class uses this
    filename_ext = ".nuanmb"

    filter_glob: StringProperty(
        default="*.nuanmb",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
    compression: BoolProperty(
        name="Enable Compression",
        description="Currently only compresses Transform tracks",
        default=True,
    )

    splitExport: BoolProperty(
        name="Split Export",
        description="Only Exports the selected animation groups (groups are green)",
        default=False,
    )
    
    
    def execute(self, context):
        return export_nuanmb_main(context, self.filepath, self.compression, self.splitExport)
    
    @classmethod
    def poll(self, context):
        if context.active_object is not None:
            if ((context.active_object.type == 'CAMERA') or (context.active_object.type == 'ARMATURE')):
                return True
        return False

# Only needed if you want to add into a dynamic menu
def menu_func_export(self, context):
    self.layout.operator(ExportSomeData.bl_idname, text="NUANMB (.nuanmb)")


def register():
    bpy.utils.register_class(ExportSomeData)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(ExportSomeData)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()

    # test call
    bpy.ops.export_test.some_data('INVOKE_DEFAULT')
