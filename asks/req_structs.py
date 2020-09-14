# pylint: disable=arguments-differ
"""
Some structures used throughout asks.
"""
from collections import OrderedDict, deque
from collections.abc import MutableMapping, Mapping


class SocketQ(deque):
    """
    A funky little subclass of deque built for the session classes.
    Allows for connection pooling of sockets to remote hosts.
    """

    def index(self, host_loc):
        try:
            return next(index for index, i in enumerate(self) if i.host == host_loc)
        except StopIteration:
            raise ValueError("{} not in SocketQ".format(host_loc)) from None

    def pull(self, index):
        x = self[index]
        del self[index]
        return x

    async def free_pool(self):
        while self:
            sock = self.pop()
            await sock.aclose()

    def __contains__(self, host_loc):
        for i in self:
            if i.host == host_loc:
                return True
        return False


"""
The rest of this file's contents are from request's source.

requests is licenced under the Apache 2.0 licence, which can be found here:

    http://www.apache.org/licenses/LICENSE-2.0

requests can be found here:
    https://github.com/kennethreitz/requests
"""


class CaseInsensitiveDict(MutableMapping):
    """A case-insensitive ``dict``-like object.
    Implements all methods and operations of
    ``collections.MutableMapping`` as well as dict's ``copy``. Also
    provides ``lower_items``.
    All keys are expected to be strings. The structure remembers the
    case of the last key to be set, and ``iter(instance)``,
    ``keys()``, ``items()``, ``iterkeys()``, and ``iteritems()``
    will contain case-sensitive keys. However, querying and contains
    testing is case insensitive::
        cid = CaseInsensitiveDict()
        cid['Accept'] = 'application/json'
        cid['aCCEPT'] == 'application/json'  # True
        list(cid) == ['Accept']  # True
    For example, ``headers['content-encoding']`` will return the
    value of a ``'Content-Encoding'`` response header, regardless
    of how the header name was originally stored.
    If the constructor, ``.update``, or equality comparison
    operations are given keys that have equal ``.lower()``s, the
    behavior is undefined.
    """

    def __init__(self, data=None, **kwargs):
        self._store = OrderedDict()
        if data is None:
            data = {}
        self.update(data, **kwargs)

    def __setitem__(self, key, value):
        # Use the lowercased key for lookups, but store the actual
        # key alongside the value.
        self._store[key.lower()] = (key, value)

    def __getitem__(self, key):
        return self._store[key.lower()][1]

    def __delitem__(self, key):
        del self._store[key.lower()]

    def __iter__(self):
        return (casedkey for casedkey, mappedvalue in self._store.values())

    def __len__(self):
        return len(self._store)

    def lower_items(self):
        """Like items(), but with all lowercase keys."""
        return ((lowerkey, keyval[1]) for (lowerkey, keyval) in self._store.items())

    def __eq__(self, other):
        if isinstance(other, Mapping):
            other = CaseInsensitiveDict(other)
        else:
            return NotImplemented
        # Compare insensitively
        return dict(self.lower_items()) == dict(other.lower_items())

    # Copy is required
    def copy(self):
        return CaseInsensitiveDict(self._store.values())

    def __repr__(self):
        return str(dict(self.items()))
