class LineString:
    """Basic type for strings ending in a newline character (0x0a).
    >>> from tempfile import TemporaryFile
    >>> f = TemporaryFile()
    >>> l = NifFormat.LineString()
    >>> f.write('abcdefg\\x0a'.encode())
    8
    >>> f.seek(0)
    0
    >>> l.read(f)
    >>> str(l)
    'abcdefg'
    >>> f.seek(0)
    0
    >>> l.set_value('Hi There')
    >>> l.write(f)
    >>> f.seek(0)
    0
    >>> m = NifFormat.LineString()
    >>> m.read(f)
    >>> str(m)
    'Hi There'
    """

    def __init__(self, **kwargs):
        # BasicBase.__init__(self, **kwargs)
        self.set_value('')

    def get_value(self):
        return self._value

    def set_value(self, value):
        self._value = pyffi.object_models.common._as_bytes(value).rstrip('\x0a'.encode("ascii"))

    def __str__(self):
        return pyffi.object_models.common._as_str(self._value)

    def get_size(self, data=None):
        return len(self._value) + 1  # +1 for trailing endline

    def get_hash(self, data=None):
        return self.get_value()

    def read(self, stream, data=None):
        self._value = stream.readline().rstrip('\x0a'.encode("ascii"))

    def write(self, stream, data=None):
        stream.write(self._value)
        stream.write("\x0a".encode("ascii"))

