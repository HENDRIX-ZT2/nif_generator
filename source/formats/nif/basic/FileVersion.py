class FileVersion(pyffi.object_models.common.UInt):
    def set_value(self):
        raise NotImplementedError("file version is specified via data")

    def __str__(self):
        return '0x%08X' % self._value

    def read(self, stream, data):
        modification = data.modification
        ver, = struct.unpack('<I', stream.read(4))  # always little endian
        if (not modification) or modification == "jmihs1":
            if ver != data.version:
                raise ValueError(
                    "Invalid version number: "
                    "expected 0x%08X but got 0x%08X."
                    % (data.version, ver))
        elif modification == "neosteam":
            if ver != 0x08F35232:
                raise ValueError(
                    "Invalid NeoSteam version number: "
                    "expected 0x%08X but got 0x%08X."
                    % (0x08F35232, ver))
        elif modification == "ndoors":
            if ver != 0x73615F67:
                raise ValueError(
                    "Invalid Ndoors version number: "
                    "expected 0x%08X but got 0x%08X."
                    % (0x73615F67, ver))
        elif modification == "laxelore":
            if ver != 0x5A000004:
                raise ValueError(
                    "Invalid Laxe Lore version number: "
                    "expected 0x%08X but got 0x%08X."
                    % (0x5A000004, ver))
        else:
            raise ValueError(
                "unknown modification: '%s'" % modification)
        self._value = data.version

    def write(self, stream, data):
        # always little endian
        modification = data.modification
        if (not modification) or modification == "jmihs1":
            stream.write(struct.pack('<I', data.version))
        elif modification == "neosteam":
            stream.write(struct.pack('<I', 0x08F35232))
        elif modification == "ndoors":
            stream.write(struct.pack('<I', 0x73615F67))
        elif modification == "laxelore":
            stream.write(struct.pack('<I', 0x5A000004))
        else:
            raise ValueError(
                "unknown modification: '%s'" % modification)

    def get_detail_display(self):
        # todo: x.x.x.x display?
        return '0x%08X' % self._value