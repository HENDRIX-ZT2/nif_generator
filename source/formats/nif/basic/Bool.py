import struct


class bool:
    """Basic implementation of a 32-bit (8-bit for versions > 4.0.0.2)
    boolean type.
    >>> i = NifFormat.bool()
    >>> i.set_value('false')
    >>> i.get_value()
    False
    >>> i.set_value('true')
    >>> i.get_value()
    True
    """

    def __init__(self, **kwargs):
        # BasicBase.__init__(self, **kwargs)
        self.set_value(False)

    def get_value(self):
        return self._value

    def set_value(self, value):
        if isinstance(value, str):
            if value.lower() == 'false':
                self._value = False
                return
            elif value == '0':
                self._value = False
                return
        if value:
            self._value = True
        else:
            self._value = False

    def get_size(self, data=None):
        ver = data.version if data else -1
        if ver > 0x04000002:
            return 1
        else:
            return 4

    def get_hash(self, data=None):
        return self._value

    def read(self, stream, data):
        if data.version > 0x04000002:
            value, = struct.unpack(data._byte_order + 'B',
                                   stream.read(1))
        else:
            value, = struct.unpack(data._byte_order + 'I',
                                   stream.read(4))
        self._value = bool(value)

    def write(self, stream, data):
        if data.version > 0x04000002:
            stream.write(struct.pack(data._byte_order + 'B',
                                     int(self._value)))
        else:
            stream.write(struct.pack(data._byte_order + 'I',
                                     int(self._value)))