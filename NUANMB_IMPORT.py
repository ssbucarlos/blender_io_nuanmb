#!BPY

bl_info = {
    "name": "Super Smash Bros. Ultimate Animation Importer + Camera",
    "description": "Imports animation data from NUANMB files (binary animation format used by some games developed by Bandai-Namco)",
    "author": "Carlos, Richard Qian (Worldblender), Ploaj",
    "version": (1, 0, 0),
    "blender": (2, 91, 0),
    "location": "File > Import",
    "category": "Import-Export"}
    
import bpy, enum, io, math, mathutils, os, struct, time

class AnimTrack:
    def __init__(self):
        self.name = ""
        self.type = ""
        self.flags = 0
        self.frameCount = 0
        self.dataOffset = 0
        self.dataSize = 0
        self.animations = []

    def __repr__(self):
        return "Node name: " + str(self.name) + "\t| Type: " + str(self.type) + "\t| Flags: " + str(self.flags) + "\t| # of frames: " + str(self.frameCount) + "\t| Data offset: " + str(self.dataOffset) + "\t| Data size: " + str(self.dataSize) + "\n"

class AnimCompressedHeader:
    def __init__(self):
        self.unk_4 = 0 # always 4?
        self.flags = 0
        self.defaultDataOffset = 0
        self.bitsPerEntry = 0
        self.compressedDataOffset = 0
        self.frameCount = 0

    def __repr__(self):
        return "Flags: " + str(self.flags) + "\t| Bits/entry: " + str(self.bitsPerEntry) + "\t| Data offset: " + str(self.compressedDataOffset) + "\t| Frame count: " + str(self.frameCount) + "\n"

class AnimCompressedItem:
    def __init__(self):
        self.start = 0
        self.end = 0
        self.count = 0

    def __init__(self, start, end, count):
        self.start = start
        self.end = end
        self.count = count

    def __repr__(self):
        return "Start: " + str(self.start) + "\t| End: " + str(self.end) + "\t| Count: " + str(self.count) + "\n"

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
    Vector4 = 9
    Direct = 256
    ConstTransform = 512
    Compressed = 1024
    Constant = 1280
    # Use 65280 or 0xff00 when performing a bitwise 'and' on a flag
    # Use 255 or 0x00ff when performing a bitwise 'and' on a flag, for uncompressed data

def readVarLenString(file):
    nameBuffer = []
    while('\x00' not in nameBuffer):
        nameBuffer.append(str(file.read(1).decode("utf-8", "ignore")))
    del nameBuffer[-1]
    return ''.join(nameBuffer)

# Utility function to read from a buffer by bits, as Python can only read by bytes
def readBits(buffer, bitCount, bitPosition):
    bee = struct.unpack('<B', buffer.read(1))[0] # Peek at next byte
    buffer.seek(-1, 1) # Go back one byte
    value = 0
    LE = 0
    bitIndex = 0
    for i in range(bitCount):
        bit = (bee & (0x1 << bitPosition)) >> bitPosition
        value = value | (bit << (LE + bitIndex))
        bitPosition += 1
        bitIndex += 1
        if (bitPosition >= 8):
            bitPosition = 0
            buffer.seek(1, 1) # Go forward one byte
            bee = struct.unpack('<B', buffer.read(1))[0] # Peek at next byte
            buffer.seek(-1, 1) # Go back one byte

        if (bitIndex >= 8):
            bitIndex = 0
            if ((LE + 8) > bitCount):
                LE = bitCount - 1
            else:
                LE += 8

    # Also return the bitPosition so that it can be reused by another call to this function
    return value, bitPosition

# A standard linear interpolation function for individual values
def lerp(av, bv, v0, v1, factor):
    if (v0 == v1):
        return av
    if (factor == v0):
        return av
    if (factor == v1):
        return bv

    mu = (factor - v0) / (v1 - v0)
    return (av * (1 - mu)) + (bv * mu)

def getExactObjectName(objName, compare):
    # A list of strings to split object names with so that they can exactly match a given track name
    extendNames = ["_VIS_O_OBJ", "_NSC_O_OBJ", "_O_OBJ", "_MeshShape"]

    for term in extendNames:
        result = objName.split(term)[0]
        if (result == compare):
            return result

    return objName

def getAnimationInfo(self, context, camera_selected, filepath, read_transform, read_material, read_visibility, read_camera):
    # Semi-global variables used by this function's hierarchy; cleared every time this function runs
    global AnimName; AnimName = ""
    GroupCount = 0
    global FrameCount; FrameCount = 0
    NodeCount = 0
    global AnimGroups; AnimGroups = {}
    # Structure of this dict is: {AnimType (numeric): an array of AnimTrack objects}

    print(self.files); print(filepath)
    for animFile in self.files:
        animPath = os.path.join(os.path.dirname(filepath), animFile.name)
        if os.path.isfile(animPath):
            with open(animPath, 'rb') as am:
                am.seek(0x10, 0)
                AnimCheck = struct.unpack('<L', am.read(4))[0]
                if (AnimCheck == 0x414E494D):
                    AnimVerA = struct.unpack('<H', am.read(2))[0]
                    AnimVerB = struct.unpack('<H', am.read(2))[0]
                    FinalFrameIndex = struct.unpack('<f', am.read(4))[0]
                    FrameCount = FinalFrameIndex + 1
                    print("Total # of frames: " + str(FrameCount))
                    print("FinalFrameIndex: " +str(FinalFrameIndex)) 
                    Unk1 = struct.unpack('<H', am.read(2))[0]
                    Unk2 = struct.unpack('<H', am.read(2))[0]
                    AnimNameOffset = am.tell() + struct.unpack('<L', am.read(4))[0]; am.seek(0x04, 1)
                    GroupOffset = am.tell() + struct.unpack('<L', am.read(4))[0]; am.seek(0x04, 1)
                    GroupCount = struct.unpack('<L', am.read(4))[0]; am.seek(0x04, 1)
                    BufferOffset = am.tell() + struct.unpack('<L', am.read(4))[0]; am.seek(0x04, 1)
                    BufferSize = struct.unpack('<L', am.read(4))[0]; am.seek(0x04, 1)
                    print("GroupOffset: " + str(GroupOffset) + " | " + "GroupCount: " + str(GroupCount) + " | " + "BufferOffset: " + str(BufferOffset) + " | " + "BufferSize: " + str(BufferSize))
                    am.seek(AnimNameOffset, 0)
                    AnimName = readVarLenString(am); am.seek(0x04, 1)
                    print("AnimName: " + AnimName)
                    am.seek(GroupOffset, 0)
                    # Collect information about the nodes
                    for g in range(GroupCount):
                        NodeAnimType = struct.unpack('<L', am.read(4))[0]; am.seek(0x04, 1)
                        NodeOffset = am.tell() + struct.unpack('<L', am.read(4))[0]; am.seek(0x04, 1)
                        NodeCount = struct.unpack('<L', am.read(4))[0]; am.seek(0x04, 1)
                        AnimGroups[NodeAnimType] = [] # Create empty array to append to later on
                        NextGroupPos = am.tell()
                        # print("AnimType: " + AnimType(NodeAnimType).name + " | " + "NodeOffset: " + str(NodeOffset) + " | " + "NodeCount: " + str(NodeCount) + " | NextGroupPos: " + str(NextGroupPos))
                        am.seek(NodeOffset, 0)
                        for n in range(NodeCount):
                            NodeNameOffset = am.tell() + struct.unpack('<L', am.read(4))[0]; am.seek(0x04, 1)
                            NodeDataOffset = am.tell() + struct.unpack('<L', am.read(4))[0]; am.seek(0x04, 1)
                            at = AnimTrack()
                            # Special workaround for material tracks
                            if (NodeAnimType == AnimType.Material.value or NodeAnimType == AnimType.Camera.value):
                                TrackCount = struct.unpack('<L', am.read(4))[0]; am.seek(0x04, 1)
                                NextNodePos = am.tell()
                                am.seek(NodeNameOffset, 0)
                                NodeName = readVarLenString(am)
                                am.seek(NodeDataOffset, 0)
                                for tr in range(TrackCount):
                                    at = AnimTrack()
                                    at.name = NodeName
                                    # An offset for the type name, which will be seeked to later
                                    TypeOffset = am.tell() + struct.unpack('<L', am.read(4))[0]; am.seek(0x04, 1)
                                    at.flags = struct.unpack('<L', am.read(4))[0]
                                    at.frameCount = struct.unpack('<L', am.read(4))[0]
                                    Unk3_0 = struct.unpack('<L', am.read(4))[0]
                                    at.dataOffset = struct.unpack('<L', am.read(4))[0]
                                    at.dataSize = struct.unpack('<L', am.read(4))[0]; am.seek(0x04, 1)
                                    NextTrackPos = am.tell()
                                    am.seek(TypeOffset, 0)
                                    at.type = readVarLenString(am)
                                    am.seek(NextTrackPos, 0)
                                    AnimGroups[NodeAnimType].append(at)
                            else:
                                NextNodePos = am.tell() + struct.unpack('<L', am.read(4))[0] + 0x07

                                am.seek(NodeNameOffset, 0)
                                at.name = readVarLenString(am)
                                am.seek(NodeDataOffset + 0x08, 0)
                                at.flags = struct.unpack('<L', am.read(4))[0]
                                at.frameCount = struct.unpack('<L', am.read(4))[0]
                                Unk3_0 = struct.unpack('<L', am.read(4))[0]
                                at.dataOffset = struct.unpack('<L', am.read(4))[0]
                                at.dataSize = struct.unpack('<L', am.read(4))[0]; am.seek(0x04, 1)
                                at.type = readVarLenString(am)
                                AnimGroups[NodeAnimType].append(at)

                            # print("NodeNameOffset: " + str(NodeNameOffset) + " | " + "NodeDataOffset: " + str(NodeDataOffset) + " | " + "NextNodePos: " + str(NextNodePos))
                            # print("NodeName: " + str(at.name) + " | " + "TrackFlags: " + str(at.flags) + " | " + "TrackFrameCount: " + str(at.frameCount) + " | " + "Unk3: " + str(Unk3_0) + " | " + "TrackDataOffset: " + str(at.dataOffset) +" | " + "TrackDataSize: " + str(at.dataSize))
                            am.seek(NextNodePos, 0)
                        # print("---------")
                        am.seek(NextGroupPos, 0)
                    print(AnimGroups)
                    am.seek(BufferOffset, 0) # This must happen or all data will be read incorrectly
                    readAnimations(io.BytesIO(am.read(BufferSize)))

                    # Now get the data into Blender
                    if (camera_selected):
                        importCamera(context)
                    else:
                        importAnimations(context, read_transform, read_material, read_visibility, read_camera)
                    

                else:
                    raise RuntimeError("%s is not a valid NUANMB file." % animPath)

def readAnimations(ao):
    for ag in AnimGroups.items():
        for track in ag[1]:
            ao.seek(track.dataOffset, 0)
            # Collect the actual data pertaining to every node
            if ((track.flags & 0xff00) == AnimTrackFlags.Constant.value or (track.flags & 0xff00) == AnimTrackFlags.ConstTransform.value):
                #print("readAnimations: Const or Const Transform")
                readDirectData(ao, track)
            if ((track.flags & 0xff00) == AnimTrackFlags.Direct.value):
                #print("readAnimations: Direct")
                for t in range(track.frameCount):
                    readDirectData(ao, track)
            if ((track.flags & 0xff00) == AnimTrackFlags.Compressed.value):
                #print("readAnimations: Compressed")
                readCompressedData(ao, track)
            #print(track.name + " | " + AnimType(ag[0]).name)
            #for id, frame in enumerate(track.animations):
            #    print(id + 1)
            #    print(frame)

    ao.close()

def readDirectData(aq, track):
    if ((track.flags & 0x00ff) == AnimTrackFlags.Transform.value):
        # Scale [X, Y, Z]
        sx = struct.unpack('<f', aq.read(4))[0]; sy = struct.unpack('<f', aq.read(4))[0]; sz = struct.unpack('<f', aq.read(4))[0]
        # Rotation [X, Y, Z, W]
        rx = struct.unpack('<f', aq.read(4))[0]; ry = struct.unpack('<f', aq.read(4))[0]; rz = struct.unpack('<f', aq.read(4))[0]; rw = struct.unpack('<f', aq.read(4))[0]
        # Position [X, Y, Z]
        px = struct.unpack('<f', aq.read(4))[0]; py = struct.unpack('<f', aq.read(4))[0]; pz = struct.unpack('<f', aq.read(4))[0]; pw = struct.unpack('<f', aq.read(4))[0]
        track.animations.append(mathutils.Matrix([[px, py, pz, 0], [rx, ry, rz, rw], [sx, sy, sz, 1]]))
        """
        Matrix composition:
                | X | Y | Z | W |
        Position|PX |PY |PZ |PW | 0
        Rotation|RX |RY |RZ |RW | 1
        Scale   |SX |SY |SZ |SW | 2
                  0   1   2   3
        PW and SW are not used here, instead being populated with '0' and '1', respectively
        """

    if ((track.flags & 0x00ff) == AnimTrackFlags.Texture.value):
        print("Direct texture data extraction not yet implemented")

    if ((track.flags & 0x00ff) == AnimTrackFlags.Float.value):
        track.animations.append(struct.unpack('<f', aq.read(4))[0])

    if ((track.flags & 0x00ff) == AnimTrackFlags.PatternIndex.value):
        print("Direct pattern index data extraction not yet implemented")

    if ((track.flags & 0x00ff) == AnimTrackFlags.Boolean.value):
        bitValue = struct.unpack('<B', aq.read(1))[0]
        track.animations.append(bitValue == 1)

    if ((track.flags & 0x00ff) == AnimTrackFlags.Vector4.value):
        # [X, Y, Z, W]
        x = struct.unpack('<f', aq.read(4))[0]; y = struct.unpack('<f', aq.read(4))[0]; z = struct.unpack('<f', aq.read(4))[0]; w = struct.unpack('<f', aq.read(4))[0]
        track.animations.append(mathutils.Vector([x, y, z, w]))

def readCompressedData(aq, track):
    ach = AnimCompressedHeader()
    ach.unk_4 = struct.unpack('<H', aq.read(2))[0]
    ach.flags = struct.unpack('<H', aq.read(2))[0]
    ach.defaultDataOffset = struct.unpack('<H', aq.read(2))[0]
    ach.bitsPerEntry = struct.unpack('<H', aq.read(2))[0]
    ach.compressedDataOffset = struct.unpack('<L', aq.read(4))[0]
    ach.frameCount = struct.unpack('<L', aq.read(4))[0]
    bp = 0 # Workaround to allow the bitreader function to continue at wherever it left off

    if ((track.flags & 0x00ff) == AnimTrackFlags.Transform.value):
        acj = [] # Contains an array of AnimCompressedItem objects
        for i in range(9):
            Start = struct.unpack('<f', aq.read(4))[0]
            End = struct.unpack('<f', aq.read(4))[0]
            Count = struct.unpack('<L', aq.read(4))[0]; aq.seek(0x04, 1)
            aci = AnimCompressedItem(Start, End, Count)
            acj.append(aci)
        #print(acj)

        aq.seek(track.dataOffset + ach.defaultDataOffset, 0)
        # Scale [X, Y, Z]
        sx = struct.unpack('<f', aq.read(4))[0]; sy = struct.unpack('<f', aq.read(4))[0]; sz = struct.unpack('<f', aq.read(4))[0]
        # Rotation [X, Y, Z, W]
        rx = struct.unpack('<f', aq.read(4))[0]; ry = struct.unpack('<f', aq.read(4))[0]; rz = struct.unpack('<f', aq.read(4))[0]; rw = struct.unpack('<f', aq.read(4))[0]
        # Position [X, Y, Z, W]
        px = struct.unpack('<f', aq.read(4))[0]; py = struct.unpack('<f', aq.read(4))[0]; pz = struct.unpack('<f', aq.read(4))[0]; pw = struct.unpack('<H', aq.read(2))[0]

        aq.seek(track.dataOffset + ach.compressedDataOffset, 0)
        for f in range(ach.frameCount):
            transform = mathutils.Matrix([[px, py, pz, pw], [rx, ry, rz, rw], [sx, sy, sz, 1]])
            """
            Matrix composition:
                    | X | Y | Z | W |
            Position|PX |PY |PZ |PW | 0
            Rotation|RX |RY |RZ |RW | 1
            Scale   |SX |SY |SZ |SW | 2
                      0   1   2   3
            SW is used to represent absolute scale, being populated with '1' by default
            """

            for itemIndex in range(len(acj)):
                # First check if this track should be parsed
                # TODO: Don't hard code these flags.
                if (not ((itemIndex == 0 and (ach.flags & 0x3) == 0x3) # isotropic scale
                    or (itemIndex >= 0 and itemIndex <= 2 and (ach.flags & 0x3) == 0x1) # normal scale
                    or (itemIndex > 2 and itemIndex <= 5 and (ach.flags & 0x4) > 0)
                    or (itemIndex > 5 and itemIndex <= 8 and (ach.flags & 0x8) > 0))):
                    continue

                item = acj[itemIndex]
                # Decompress
                valueBitCount = item.count
                if (valueBitCount == 0):
                    continue

                value, bp = readBits(aq, valueBitCount, bp)
                scale = 0
                for k in range(valueBitCount):
                    scale = scale | (0x1 << k)

                frameValue = lerp(item.start, item.end, 0, 1, value / float(scale))
                if frameValue == float('NaN'):
                    frameValue = 0

                # The 'Transform' type frequently depends on flags
                if ((ach.flags & 0x3) == 0x3):
                    # Scale isotropic
                    if (itemIndex == 0):
                        transform[2][3] = frameValue

                if ((ach.flags & 0x3) == 0x1):
                    # Scale normal
                    if (itemIndex == 0):
                        transform[2][0] = frameValue
                    elif (itemIndex == 1):
                        transform[2][1] = frameValue
                    elif (itemIndex == 2):
                        transform[2][2] = frameValue

                # Rotation and Position
                if (itemIndex == 3):
                    transform[1][0] = frameValue
                elif (itemIndex == 4):
                    transform[1][1] = frameValue
                elif (itemIndex == 5):
                    transform[1][2] = frameValue
                elif (itemIndex == 6):
                    transform[0][0] = frameValue
                elif (itemIndex == 7):
                    transform[0][1] = frameValue
                elif (itemIndex == 8):
                    transform[0][2] = frameValue

            # Rotations have an extra bit at the end
            if ((ach.flags & 0x4) > 0):
                wBit, bp = readBits(aq, 1, bp)
                wFlip = wBit == 1

                # W is calculated
                transform[1][3] = math.sqrt(abs(1 - (pow(transform[1][0], 2) + pow(transform[1][1], 2) + pow(transform[1][2], 2))))

                if wFlip:
                    transform[1][3] *= -1

            track.animations.append(transform)

    if ((track.flags & 0x00ff) == AnimTrackFlags.Texture.value):
        print("Compressed texture data extraction not yet implemented")

    if ((track.flags & 0x00ff) == AnimTrackFlags.Float.value):
        print("Compressed float data extraction not yet implemented")

    if ((track.flags & 0x00ff) == AnimTrackFlags.PatternIndex.value):
        print("Compressed pattern index data extraction not yet implemented")

    if ((track.flags & 0x00ff) == AnimTrackFlags.Boolean.value):
        aq.seek(track.dataOffset + ach.compressedDataOffset, 0)
        for t in range(ach.frameCount):
            bitValue, bp = readBits(aq, ach.bitsPerEntry, bp)
            track.animations.append(bitValue == 1)

    if ((track.flags & 0x00ff) == AnimTrackFlags.Vector4.value):
        acj = [] # Contains an array of AnimCompressedItem objects
        for i in range(4):
            Start = struct.unpack('<f', aq.read(4))[0]
            End = struct.unpack('<f', aq.read(4))[0]
            Count = struct.unpack('<L', aq.read(4))[0]; aq.seek(0x04, 1)
            aci = AnimCompressedItem(Start, End, Count)
            acj.append(aci)
        print(acj)

        aq.seek(track.dataOffset + ach.defaultDataOffset, 0)
        values = []
        # Copy default values
        for c in range(4):
            values.append(struct.unpack('<f', aq.read(4))[0])
        print("Values after default copy = " + str(values))
        aq.seek(track.dataOffset + ach.compressedDataOffset, 0)
        for f in range(ach.frameCount):
            for itemIndex in range(len(acj)):
                item = acj[itemIndex]
                # Decompress
                valueBitCount = item.count
                if (valueBitCount == 0):
                    continue

                value, bp = readBits(aq, valueBitCount, bp)
                scale = 0
                for k in range(valueBitCount):
                    scale = scale | (0x1 << k)
            
                frameValue = lerp(item.start, item.end, 0, 1, value / float(scale))
                if frameValue == float('NaN'):
                    frameValue = 0
                print("Frame{%s}, itemIndex{%s}, frameValue{%s}" % (str(f), str(itemIndex), str(frameValue)))
                values[itemIndex] = frameValue
                print("Frame{%s}, values[itemIndex] = %s" % (str(f), str(values[itemIndex])))
            track.animations.append(values[:]) #Gotta append a copy by using [:], or else a reference will get appended and all values of the list will be the last ones
        print(track.animations)

# This function deals with all of the Blender-camera-specific operations
def importCamera(context):
    #should only enter this function if the selected object was the camera.
    cam = bpy.context.object

    #Create the animation_data if it doesnt already exist
    try:
        cam.animation_data.action
    except:
        cam.animation_data_create()
    
    #idk lol
    action = bpy.data.actions.new(AnimName)
    cam.animation_data.action = action
    
    #matrix setup
    cam.matrix_basis.identity()
    cam.rotation_mode = "QUATERNION"
    
    #Start the animation on Frame 1, which is the blender default
    
    # Animation frames start at 1, the same as what Blender uses by default
    context.scene.frame_start = 1
    sm = action.pose_markers.new(AnimName + "-start")
    sm.frame = context.scene.frame_start
    context.scene.frame_end = FrameCount + 1
    em = action.pose_markers.new(AnimName + "-end")
    em.frame = context.scene.frame_end

    for ag in AnimGroups.items():
        if (ag[0] == AnimType.Transform.value):  
            cam.name = ag[1][0].name
            # Iterate by frame, and loop through tracks by name to set the transformation matrices
            for frame in range(int(FrameCount)):
                for track in ag[1]:
                    print("Track frame # " + str(frame) + ", type " + AnimType.Transform.name)
                    qr = mathutils.Quaternion(track.animations[frame][1].wxyz)
                    pm = mathutils.Matrix.Translation(track.animations[frame][0][:3]) # Position matrix
                    rm = mathutils.Matrix.Rotation(qr.angle, 4, qr.axis) # Rotation matrix
                    sx = mathutils.Matrix.Scale(track.animations[frame][2][0], 4, (1, 0, 0)) # Scale matrix
                    sy = mathutils.Matrix.Scale(track.animations[frame][2][1], 4, (0, 1, 0))
                    sz = mathutils.Matrix.Scale(track.animations[frame][2][2], 4, (0, 0, 1))
                    
                    cam.matrix_local = mathutils.Matrix(pm @ rm @ sx @ sy @ sz)
                    
                    cam.keyframe_insert(data_path ='location',
                                            frame = frame + 1,
                                            group = AnimName)
                    cam.keyframe_insert(data_path ='rotation_quaternion',
                                            frame = frame + 1,
                                            group = AnimName)
                    cam.keyframe_insert(data_path ='scale',
                                            frame = frame + 1,
                                            group = AnimName)
                                                                
        elif (ag[0] == AnimType.Camera.value):
            print("Storing Camera Flags and Data as custom data")  
            for track in ag[1]:
                print ("Camera Track Type: " + str(track.type))
                if(track.type == "FieldOfView"):
                    blender_frame = 1
                    #TODO: Blender doesn't allow keyframing FOV directly,
                    # need to figure out conversion between smash FOV
                    # and convert that to Sensor Width and Focal Length
                    for anim_frame in track.animations:
                        cam["FOV"] = anim_frame
                        cam.keyframe_insert(data_path = '["FOV"]',
                                            frame = blender_frame,
                                            group = AnimName)
                        blender_frame += 1
                    
            
    
    #Create an empty object and then parent this camera to it.
    #That way, we can rotate the empty 90 to match the orientation from the .numdlb script
    empty = bpy.data.objects.new("empty", None)
    empty.name = "Cam-Rotation-Fixer"
    bpy.context.collection.objects.link(empty)
    
    empty.rotation_euler[0] = math.radians(90)
    cam.parent = empty
    
    #Now change the camera object's camera data, such as FOV, Lens Type, etc...
    cam.data.type       = "PERSP"
    cam.data.angle      = math.radians(56.7)
    cam.data.shift_y    = 0.060
    cam.data.sensor_fit = "HORIZONTAL"
       
    #Now change some scene data just incase they werent already set
    render = bpy.context.scene.render
    render.resolution_x   = 1920
    render.resolution_y   = 1080
    render.pixel_aspect_x = 1
    render.pixel_aspect_y = 1
    render.fps            = 60
    
          
def keyframe_insert_locrotscale(obj, boneName, frame, groupName):
    obj.keyframe_insert(data_path = 'pose.bones["%s"].%s' % (boneName, 'location'),
                        frame = frame,
                        group = groupName)
    obj.keyframe_insert(data_path = 'pose.bones["%s"].%s' % (boneName, 'rotation_quaternion'),
                        frame = frame,
                        group = groupName)
    obj.keyframe_insert(data_path = 'pose.bones["%s"].%s' % (boneName, 'scale'),
                        frame = frame,
                        group = groupName)                        

# This function deals with all of the Blender-specific operations
def importAnimations(context, read_transform, read_material, read_visibility, read_camera):
    obj = bpy.context.object
    bpy.ops.object.mode_set(mode='POSE', toggle=False)
    
    #Re-Enable inheriting scale for bones. Will get turned off per-animation
    for bone in obj.data.bones:
        bone.inherit_scale = 'FULL'
    
    # Force all bones to use quaternion rotation
    # Also set each bone to the identity matrix
    for bone in obj.pose.bones:
        bone.matrix_basis.identity()
        bone.rotation_mode = 'QUATERNION'

    try:
        obj.animation_data.action
    except:
        obj.animation_data_create()

    action = bpy.data.actions.new(AnimName)
    obj.animation_data.action = action

    # Animation frames start at 1, the same as what Blender uses by default
    context.scene.frame_start = 1
    sm = action.pose_markers.new(AnimName + "-start")
    sm.frame = context.scene.frame_start
    context.scene.frame_end = FrameCount + 1
    em = action.pose_markers.new(AnimName + "-end")
    em.frame = context.scene.frame_end

    for ag in AnimGroups.items():
        if (read_transform and ag[0] == AnimType.Transform.value):
            # Iterate by frame, and loop through tracks by name to set the transformation matrices
            for frame in range(int(FrameCount) + 1):
                # Structure of this dict is: {bone name, transformation matrix}; is cleared on every frame
                tfmArray = {}
                #print("Track frame # " + str(frame) + ", type " + AnimType.Transform.name)
                for track in ag[1]:
                    if (frame < track.frameCount):
                        # Set up a matrix that can set position, rotation, and scale all at once
                        #print("Track Name = " + str(track.name) + " ")
                        qr = mathutils.Quaternion(track.animations[frame][1].wxyz)
                        pm = mathutils.Matrix.Translation(track.animations[frame][0][:3]) # Position matrix
                        rm = mathutils.Matrix.Rotation(qr.angle, 4, qr.axis) # Rotation matrix
                        sx = mathutils.Matrix.Scale(track.animations[frame][2][0], 4, (1, 0, 0)) # Scale matrix
                        sy = mathutils.Matrix.Scale(track.animations[frame][2][1], 4, (0, 1, 0))
                        sz = mathutils.Matrix.Scale(track.animations[frame][2][2], 4, (0, 0, 1))
                        
                        scalex = track.animations[frame][2][0]
                        scaley = track.animations[frame][2][1]
                        scalez = track.animations[frame][2][2]
                        
                        if ((scalex != 1) or (scaley != 1) or (scalez != 1)):
                            for bone in obj.data.bones:
                                if (bone.name == track.name):
                                    bone.inherit_scale = 'NONE'
                        
                        transform = mathutils.Matrix(pm @ rm @ sx @ sy @ sz)
                        tfmArray[track.name] = transform

                # Iterate through the bone order in selected armature, and transform each of them
                for tbone in obj.pose.bones:
                    if (tbone.name in tfmArray):
                        # print(tbone.name + " | Animation matrix: " + str(tfmArray[tbone.name].transposed()))
                        if (tbone.parent):
                            tbone.matrix = tbone.parent.matrix @ tfmArray[tbone.name]
                            #Naive Helper Bone Fixes, will be replaced once they are better understood
                            if tbone.name == 'ShoulderL':
                                match = next((x for x in ['H_SholderL', 'H_ShoulderL'] if x in obj.pose.bones.keys()), False)
                                if match: #FoundHelperBone
                                    hb = obj.pose.bones[match]
                                    hb.matrix = tbone.parent.matrix @ tfmArray[tbone.name]
                                    keyframe_insert_locrotscale(obj, hb.name, frame + 1, AnimName)
                            if tbone.name == 'ArmL':
                                match = next((x for x in ['H_ElbowL'] if x in obj.pose.bones.keys()), False)
                                if match: #FoundHelperBone
                                    hb = obj.pose.bones[match]
                                    hb.matrix = tbone.parent.matrix @ tfmArray[tbone.name]
                                    keyframe_insert_locrotscale(obj, hb.name, frame + 1, AnimName)
                            if tbone.name == 'ShoulderR':
                                match = next((x for x in ['H_SholderR', 'H_ShoulderR'] if x in obj.pose.bones.keys()), False)
                                if match: #FoundHelperBone
                                    hb = obj.pose.bones[match]
                                    hb.matrix = tbone.parent.matrix @ tfmArray[tbone.name]
                                    keyframe_insert_locrotscale(obj, hb.name, frame + 1, AnimName)
                            if tbone.name == 'ArmR':
                                match = next((x for x in ['H_ElbowR'] if x in obj.pose.bones.keys()), False)
                                if match: #FoundHelperBone
                                    hb = obj.pose.bones[match]
                                    hb.matrix = tbone.parent.matrix @ tfmArray[tbone.name]
                                    keyframe_insert_locrotscale(obj, hb.name, frame + 1, AnimName)                                    
                                    
                                    
                        else:
                            tbone.matrix = tfmArray[tbone.name]
                            
   
                        # First, add the position keyframes
                        try:
                            obj.keyframe_insert(data_path='pose.bones["%s"].%s' %
                                       (tbone.name, "location"),
                                       frame=frame + 1,
                                       group=AnimName)
                        except:
                            continue

                        # Next, add the rotation keyframes
                        try:
                            obj.keyframe_insert(data_path='pose.bones["%s"].%s' %
                                       (tbone.name, "rotation_quaternion"),
                                       frame=frame + 1,
                                       group=AnimName)
                        except:
                            continue

                        # Last, add the scale keyframes
                        try:
                            obj.keyframe_insert(data_path='pose.bones["%s"].%s' %
                                       (tbone.name, "scale"),
                                       frame=frame + 1,
                                       group=AnimName)
                        except:
                            continue
                    

        elif (read_visibility and ag[0] == AnimType.Visibility.value):
            for track in ag[1]:
                for vframe, trackData in enumerate(track.animations):
                    #print("Track frame # " + str(vframe + 1) + ", type " + AnimType.Visibility.name + " for " + track.name)
                    #print("Value: " + str(trackData))

                    # All meshes are visible by default, so search the object list and hide objects whose visibility is False
                    for target in bpy.data.objects:
                        if (target.type == 'MESH' and track.name == getExactObjectName(target.name, track.name)):
                            target.hide_render = not trackData
                            target.hide_viewport = not trackData
                            target.keyframe_insert(data_path="hide_viewport", frame=vframe + 1, group=AnimName)
                            target.keyframe_insert(data_path="hide_render", frame=vframe + 1, group=AnimName)


        elif (read_material and ag[0] == AnimType.Material.value):
            for track in ag[1]:
                blender_frame = 1
                for afv in track.animations: #'Animation Frame Value'
                    obj["%s:%s" % (track.name, track.type)] = afv
                    obj.keyframe_insert(data_path = '["%s:%s"]' % (track.name, track.type),
                                        frame = blender_frame,
                                        group = track.name)
                    blender_frame += 1
                    

        elif (read_camera and ag[0] == AnimType.Camera.value):
            print("Importing camera animations not yet supported")

    # Clear any unkeyed poses
    for bone in obj.pose.bones:
        bone.matrix_basis.identity()

# ==== Import OPERATOR ====
from bpy_extras.io_utils import (ImportHelper)

class NUANMB_Import_Operator(bpy.types.Operator, ImportHelper):
    """Imports animation data from NUANMB files"""
    bl_idname = ("import_scene.nuanmb")
    bl_label = ("Import NUANMB")
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".nuanmb"
    filter_glob: bpy.props.StringProperty(default="*.nuanmb", options={'HIDDEN'})
    files: bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement)
    
    read_transform: bpy.props.BoolProperty(
            name="Transformation",
            description="Read transformation data",
            default=True,
            )

    read_material: bpy.props.BoolProperty(
            name="Material",
            description="Read material data",
            default=True,
            )

    read_visibility: bpy.props.BoolProperty(
            name="Visibility",
            description="Read visibility data",
            default=True,
            )

    read_camera: bpy.props.BoolProperty(
            name="Camera",
            description="Read camera data",
            default=True,
            )
    
    def execute(self, context):
        keywords = self.as_keywords(ignore=("filter_glob", "files",))
        time_start = time.time()
        if (context.active_object.type == 'CAMERA'):
            camera_selected = True
        else:
            camera_selected = False
        getAnimationInfo(self, context, camera_selected, **keywords)
        context.view_layer.update()

        print("Done! All animations imported in " + str(round(time.time() - time_start, 4)) + " seconds.")
        return {"FINISHED"}

    def draw(self, context):
        pass

    @classmethod
    def poll(self, context):
        if context.active_object is not None:
            if ((context.active_object.type == 'CAMERA') or (context.active_object.type == 'ARMATURE')):
                return True
        return False

class NUANMB_PT_import_tracks(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Tracks"
    bl_parent_id = "FILE_PT_operator"

    @classmethod
    def poll(cls, context):
        sfile = context.space_data
        operator = sfile.active_operator

        return operator.bl_idname == "IMPORT_SCENE_OT_nuanmb"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        sfile = context.space_data
        operator = sfile.active_operator

        layout.prop(operator, "read_transform")
        layout.prop(operator, "read_material")
        layout.prop(operator, "read_visibility")
        layout.prop(operator, "read_camera")

classes = (
    NUANMB_Import_Operator,
    NUANMB_PT_import_tracks,
)

# Add to a menu
def menu_func_import(self, context):
    self.layout.operator(NUANMB_Import_Operator.bl_idname, text="NUANMB (.nuanmb)")

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

    for cls in classes:
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register
