
class HeaderString:
    def __str__(self):
        return 'NetImmerse/Gamebryo File Format, Version x.x.x.x'

    def get_detail_display(self):
        return self.__str__()

    def get_hash(self, data=None):
        return None

    def read(self, stream, data):
        version_string = self.version_string(data.version, data.modification)
        s = stream.read(len(version_string))
        if s != version_string.encode("ascii"):
            raise ValueError(
                "invalid NIF header: expected '%s' but got '%s'"
                % (version_string, s))
        # for almost all nifs we have version_string + \x0a
        # but Bully SE has some nifs with version_string + \x0d\x0a
        # see for example World/BBonusB.nft
        eol = stream.read(1)
        if eol == '\x0d'.encode("ascii"):
            eol = stream.read(1)
        if eol != '\x0a'.encode("ascii"):
            raise ValueError(
                "invalid NIF header: bad version string eol")

    def write(self, stream, data):
        stream.write(self.version_string(data.version, data.modification).encode("ascii"))
        stream.write('\x0a'.encode("ascii"))

    def get_size(self, data=None):
        ver = data.version if data else -1
        return len(self.version_string(ver).encode("ascii")) + 1

    @staticmethod
    def version_string(version, modification=None):
        """Transforms version number into a version string.
        >>> NifFormat.HeaderString.version_string(0x03000300)
        'NetImmerse File Format, Version 3.03'
        >>> NifFormat.HeaderString.version_string(0x03010000)
        'NetImmerse File Format, Version 3.1'
        >>> NifFormat.HeaderString.version_string(0x0A000100)
        'NetImmerse File Format, Version 10.0.1.0'
        >>> NifFormat.HeaderString.version_string(0x0A010000)
        'Gamebryo File Format, Version 10.1.0.0'
        >>> NifFormat.HeaderString.version_string(0x0A010000,
        ...                                       modification="neosteam")
        'NS'
        >>> NifFormat.HeaderString.version_string(0x14020008,
        ...                                       modification="ndoors")
        'NDSNIF....@....@...., Version 20.2.0.8'
        >>> NifFormat.HeaderString.version_string(0x14030009,
        ...                                       modification="jmihs1")
        'Joymaster HS1 Object Format - (JMI), Version 20.3.0.9'
        """
        if version == -1 or version is None:
            raise ValueError('No string for version %s.' % version)
        if modification == "neosteam":
            if version != 0x0A010000:
                raise ValueError("NeoSteam must have version 0x0A010000.")
            return "NS"
        elif version <= 0x0A000102:
            s = "NetImmerse"
        else:
            s = "Gamebryo"
        if version == 0x03000300:
            v = "3.03"
        elif version <= 0x03010000:
            v = "%i.%i" % ((version >> 24) & 0xff, (version >> 16) & 0xff)
        else:
            v = "%i.%i.%i.%i" % ((version >> 24) & 0xff, (version >> 16) & 0xff, (version >> 8) & 0xff, version & 0xff)
        if modification == "ndoors":
            return "NDSNIF....@....@...., Version %s" % v
        elif modification == "jmihs1":
            return "Joymaster HS1 Object Format - (JMI), Version %s" % v
        else:
            return "%s File Format, Version %s" % (s, v)