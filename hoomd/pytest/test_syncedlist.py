from pytest import fixture, raises
from hoomd.pytest.dummy import DummyOperation, DummySimulation
from hoomd.operation import Operation
from hoomd.data.syncedlist import SyncedList


@fixture
def op_list():
    return [DummyOperation(), DummyOperation(), DummyOperation()]


def test_init(op_list):
    def validate(x):
        return isinstance(x, DummyOperation)

    # Test automatic to_synced_list function generation
    slist = SyncedList(validation=validate)
    assert slist._validate == validate
    op = DummyOperation()
    assert slist._to_synced_list_conversion(op) is op

    # Test specified to_synced_list
    def cpp_identity(x):
        return x._cpp_obj

    slist = SyncedList(validation=validate, to_synced_list=cpp_identity)
    assert slist._to_synced_list_conversion == cpp_identity
    op._cpp_obj = 2
    assert slist._to_synced_list_conversion(op) == 2

    # Test full initialziation
    slist = SyncedList(validation=validate, to_synced_list=cpp_identity,
                       iterable=op_list)
    assert len(slist._list) == 3
    assert all(op._added for op in slist)


@fixture
def slist_empty():
    return SyncedList(lambda x: isinstance(x, Operation))


@fixture
def slist(slist_empty, op_list):
    slist_empty.extend(op_list)
    return slist_empty


class OpInt(int):
    def _attach(self):
        self._cpp_obj = None

    @property
    def _attached(self):
        return hasattr(self, '_cpp_obj')

    def _detach(self):
        del self._cpp_obj

    def _add(self, simulation):
        self._simulation = simulation

    def _remove(self):
        del self._simulation

    @property
    def _added(self):
        return hasattr(self, '_simulation')


@fixture
def islist(slist_empty):
    return SyncedList(lambda x: isinstance(x, int),
                      iterable=[OpInt(i) for i in [1, 2, 3]])


def test_contains(slist_empty, op_list):
    for op in op_list:
        slist_empty._list.append(op)
        assert op in slist_empty
        new_op = DummyOperation()
        print(id(new_op), [id(op) for op in slist_empty])
        assert new_op not in slist_empty


def test_len(slist_empty, op_list):
    slist_empty._list.extend(op_list)
    assert len(slist_empty) == 3
    del slist_empty._list[1]
    assert len(slist_empty) == 2


def test_iter(slist, op_list):
    for op, op2 in zip(slist, slist._list):
        assert op is op2


def test_getitem(slist):
    assert all([op is slist[i] for i, op in enumerate(slist)])
    assert slist[:] == slist._list
    assert slist[1:] == slist._list[1:]


def test_synced(slist):
    assert not slist._synced
    slist._synced_list = None
    assert slist._synced


def test_value_add_and_attach(slist):
    op = DummyOperation()
    assert not slist._value_add_and_attach(op)._attached
    assert op._added
    slist._synced_list = []
    slist._simulation = DummySimulation()
    op = DummyOperation()
    assert slist._value_add_and_attach(op)._attached
    assert op._added


def test_validate_or_error(slist):
    with raises(ValueError):
        slist._validate_or_error(3)
        slist._validate_or_error(None)
        slist._validate_or_error("hello")
    assert slist._validate_or_error(DummyOperation())


def test_syncing(slist, op_list):
    sync_list = []
    slist._sync(None, sync_list)
    assert len(sync_list) == 3
    assert all([op is op2 for op, op2 in zip(slist, sync_list)])
    assert all([op._attached for op in slist])


def test_unsync(slist, op_list):
    sync_list = []
    slist._sync(None, sync_list)
    slist._unsync()
    assert len(sync_list) == 0
    assert all([not op._attached for op in slist])
    assert not hasattr(slist, "_synced_list")


def test_delitem(slist):
    old_op = slist[2]
    del slist[2]
    assert len(slist) == 2
    assert old_op not in slist
    assert not old_op._added
    slist.append(old_op)
    old_ops = slist[1:]
    del slist[1:]
    assert len(slist) == 1
    assert all(old_op not in slist for old_op in old_ops)
    assert all(not old_op._added for old_op in old_ops)
    slist.extend(old_ops)

    # Tested attached
    sync_list = []
    slist._sync(None, sync_list)
    old_op = slist[1]
    del slist[1]
    assert len(slist) == 2
    assert len(sync_list) == 2
    assert old_op not in slist
    assert all(old_op is not op for op in sync_list)
    assert not old_op._attached
    assert not old_op._added
    old_ops = slist[1:]
    del slist[1:]
    assert len(slist) == 1
    assert all(old_op not in slist for old_op in old_ops)
    assert all(not (old_op._added or old_op._attached) for old_op in old_ops)


def test_setitem(slist, op_list):
    with raises(IndexError):
        slist[3]
    with raises(IndexError):
        slist[-4]
    new_op = DummyOperation()
    slist[1] = new_op
    assert new_op is slist[1]
    assert new_op._added

    # Check when attached
    sync_list = []
    slist._sync(None, sync_list)
    new_op = DummyOperation()
    old_op = slist[1]
    slist[1] = new_op
    assert not (old_op._attached or old_op._added)
    assert new_op._attached and new_op._added
    assert sync_list[1] is new_op


def test_synced_iter(slist):
    slist._simulation = None
    slist._synced_list = [1, 2, 3]
    assert all([i == j for i, j in zip(range(1, 4), slist.synced_iter())])


def test_sync(islist):
    islist.append(OpInt(4))
    assert len(islist) == 4
    assert islist[-1] == 4

    # Test attached
    sync_list = []
    islist._sync(None, sync_list)
    islist.append(OpInt(5))
    assert len(islist) == 5
    assert len(sync_list) == 5
    assert islist[-1] == 5


def test_insert(islist):
    index = 1
    islist.insert(1, OpInt(4))
    assert len(islist) == 4
    assert islist[index] == 4

    # Test attached
    sync_list = []
    islist._sync(None, sync_list)
    islist.insert(index, OpInt(5))
    assert len(islist) == 5
    assert len(sync_list) == 5
    assert islist[index] == 5


def test_extend(islist):
    oplist = [OpInt(i) for i in range(4, 7)]
    islist.extend(oplist)
    assert len(islist) == 6
    assert islist[3:] == oplist

    # Test attached
    oplist = [OpInt(i) for i in range(7, 10)]
    sync_list = []
    islist._sync(None, sync_list)
    islist.extend(oplist)
    assert len(islist) == 9
    assert len(sync_list) == 9
    assert sync_list[6:] == oplist
    assert islist[6:] == oplist


def test_clear(islist):
    islist.clear()
    assert len(islist) == 0
    oplist = [OpInt(i) for i in range(1, 4)]
    islist.extend(oplist)

    # Test attached
    sync_list = []
    islist._sync(None, sync_list)
    islist.clear()
    assert len(islist) == 0
    assert len(sync_list) == 0
    assert all([not op._attached for op in oplist])


def test_remove(islist):
    islist.clear()
    oplist = [OpInt(i) for i in range(1, 4)]
    islist.extend(oplist)
    islist.remove(oplist[1])
    assert len(islist) == 2
    assert oplist[1] not in islist

    # Test attached
    sync_list = []
    islist._sync(None, sync_list)
    islist.remove(oplist[0])
    assert len(islist) == 1
    assert len(sync_list) == 1
    assert not oplist[0]._attached
    assert oplist[0] not in islist
    assert oplist[0] not in sync_list
