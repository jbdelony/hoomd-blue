import pickle
import pytest
import hoomd
import atexit
import numpy
import itertools
from hoomd.snapshot import Snapshot
from hoomd import Simulation

devices = [hoomd.device.CPU]
if (hoomd.device.GPU.is_available()
        and len(hoomd.device.GPU.get_available_devices()) > 0):
    devices.append(hoomd.device.GPU)


@pytest.fixture(scope='session', params=devices)
def device(request):
    """Parameterized Device fixture.

    Tests that use `device` will run once on the CPU and once on the GPU. The
    device object is session scoped to avoid device creation overhead when
    running tests.
    """
    d = request.param()

    # enable GPU error checking
    if isinstance(d, hoomd.device.GPU):
        d.gpu_error_checking = True

    return d


@pytest.fixture(scope='session')
def simulation_factory(device):
    """Make a Simulation object from a snapshot.

    TODO: duck type this to allow it to create state from GSD files as well
    """

    def make_simulation(snapshot):
        sim = Simulation(device)

        # reduce sorter grid to avoid Hilbert curve overhead in unit tests
        for tuner in sim.operations.tuners:
            if isinstance(tuner, hoomd.tune.ParticleSorter):
                tuner.grid = 8

        sim.create_state_from_snapshot(snapshot)
        return sim

    return make_simulation


@pytest.fixture(scope='session')
def two_particle_snapshot_factory(device):
    """Make a snapshot with two particles.

    Args:
        particle_types: List of particle type names
        dimensions: Number of dimensions (2 or 3)
        d: Distance apart to place particles
        L: Box length

    The two particles are placed at (-d/2, 0, 0) and (d/2,0,0). When,
    dimensions==3, the box is L by L by L. When dimensions==2, the box is L by L
    by 1.
    """

    def make_snapshot(particle_types=['A'], dimensions=3, d=1, L=20):
        s = Snapshot(device.communicator)
        N = 2

        if s.exists:
            box = [L, L, L, 0, 0, 0]
            if dimensions == 2:
                box[2] = 0
            s.configuration.box = box
            s.particles.N = N
            # shift particle positions slightly in z so MPI tests pass
            s.particles.position[:] = [[-d / 2, 0, .1], [d / 2, 0, .1]]
            s.particles.types = particle_types
            if dimensions == 2:
                box[2] = 0
                s.particles.position[:] = [[-d / 2, 0.1, 0], [d / 2, 0.1, 0]]

        return s

    return make_snapshot


@pytest.fixture(scope='session')
def lattice_snapshot_factory(device):
    """Make a snapshot with particles on a cubic/square lattice.

    Args:
        particle_types: List of particle type names
        dimensions: Number of dimensions (2 or 3)
        a: Lattice constant
        n: Number of particles along each box edge
        r: Fraction of `a` to randomly perturb particles

    Place particles on a simple cubic (dimensions==3) or square (dimensions==2)
    lattice. The box is cubic (or square) with a side length of `n * a`.

    Set `r` to randomly perturb particles a small amount off their lattice
    positions. This is useful in MD simulation testing so that forces do not
    cancel out by symmetry.
    """

    def make_snapshot(particle_types=['A'], dimensions=3, a=1, n=7, r=0):
        s = Snapshot(device.communicator)

        if s.exists:
            box = [n * a, n * a, n * a, 0, 0, 0]
            if dimensions == 2:
                box[2] = 0
            s.configuration.box = box

            s.particles.N = n**dimensions
            s.particles.types = particle_types

            # create the lattice
            range_ = numpy.arange(-n / 2, n / 2)
            if dimensions == 2:
                pos = list(itertools.product(range_, range_, [0]))
            else:
                pos = list(itertools.product(range_, repeat=3))
            pos = numpy.array(pos) * a
            pos[:, 0] += a / 2
            pos[:, 1] += a / 2
            if dimensions == 3:
                pos[:, 2] += a / 2

            # perturb the positions
            if r > 0:
                shift = numpy.random.uniform(-r, r, size=(s.particles.N, 3))
                if dimensions == 2:
                    shift[:, 2] = 0
                pos += shift

            s.particles.position[:] = pos

        return s

    return make_snapshot


@pytest.fixture(autouse=True)
def skip_mpi(request):
    if request.node.get_closest_marker('serial'):
        if 'device' in request.fixturenames:
            if request.getfixturevalue('device').communicator.num_ranks > 1:
                pytest.skip('Test does not support MPI execution')
        else:
            raise ValueError('skip_mpi requires the *device* fixture')


@pytest.fixture(autouse=True)
def only_gpu(request):
    if request.node.get_closest_marker('gpu'):
        if 'device' in request.fixturenames:
            if not isinstance(request.getfixturevalue('device'),
                              hoomd.device.GPU):
                pytest.skip('Test is run only on GPU(s).')
        else:
            raise ValueError('only_gpu requires the *device* fixture')


@pytest.fixture(autouse=True)
def only_cpu(request):
    if request.node.get_closest_marker('cpu'):
        if 'device' in request.fixturenames:
            if not isinstance(request.getfixturevalue('device'),
                              hoomd.device.CPU):
                pytest.skip('Test is run only on CPU(s).')
        else:
            raise ValueError('only_cpu requires the *device* fixture')


@pytest.fixture(scope='function', autouse=True)
def numpy_random_seed():
    """Seed the numpy random number generator.

    Automatically reset the numpy random seed at the start of each function
    for reproducible tests.
    """
    numpy.random.seed(42)


def pytest_addoption(parser):
    """Add HOOMD specific options to the pytest command line.

    * validate - run validation tests
    """
    parser.addoption(
        "--validate",
        action="store_true",
        default=False,
        help="Enable long running validation tests.",
    )


@pytest.fixture(autouse=True)
def skip_validate(request):
    """Skip validation tests by default.

    Pass the command line option --validate to enable these tests.
    """
    if request.node.get_closest_marker('validate'):
        if not request.config.getoption("validate"):
            pytest.skip('Validation tests not requested.')


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "serial: Tests that will not execute with more than 1 MPI process")
    config.addinivalue_line("markers",
                            "gpu: Tests that should only run on the gpu.")
    config.addinivalue_line(
        "markers",
        "cupy_optional: tests that should pass with and without CuPy.")
    config.addinivalue_line(
        "markers",
        "validate: Tests that perform long-running validations.")
    config.addinivalue_line("markers", "cpu: Tests that only run on the CPU.")
    config.addinivalue_line("markers", "gpu: Tests that only run on the GPU.")


def abort(exitstatus):
    # get a default mpi communicator
    communicator = hoomd.communicator.Communicator()
    # abort the deadlocked ranks
    hoomd._hoomd.abort_mpi(communicator.cpp_mpi_conf, exitstatus)


def pytest_sessionfinish(session, exitstatus):
    """ Finalize pytest session

    MPI tests may fail on one rank but not others. To prevent deadlocks in these
    situations, this code calls ``MPI_Abort`` when pytest is exiting with a
    non-zero exit code. **pytest** should be run with the ``-x`` option so that
    it exits on the first error.
    """

    if exitstatus != 0 and hoomd.version.mpi_enabled:
        atexit.register(abort, exitstatus)


def logging_check(cls, expected_namespace, expected_loggables):
    """Function for testing object logging specification.

    Args:
        cls (object): The loggable class to test for the correct logging
            specfication.
        expected_namespace (tuple[str]): A tuple of strings that indicate the
            expected namespace minus the class name.
        expected_loggables (dict[str, dict[str, Any]]): A dict with string keys
            representing the expected loggable quantities. If the value for a
            key is ``None`` then, only check for the existence of the loggable
            quantity. Otherwise, the inner `dict` should consist of some
            combination of the keys ``default`` and ``category`` indicating the
            expected value of each for the loggable.
    """
    # Check namespace
    assert all(log_quantity.namespace == expected_namespace + (cls.__name__,)
               for log_quantity in cls._export_dict.values())

    # Check specific loggables
    def check_loggable(cls, name, properties):
        assert name in cls._export_dict
        if properties is None:
            return None
        log_quantity = cls._export_dict[name]
        for name, prop in properties.items():
            assert getattr(log_quantity, name) == prop

    for name, properties in expected_loggables.items():
        check_loggable(cls, name, properties)


def pickling_check(instance):
    pkled_instance = pickle.loads(pickle.dumps(instance))
    assert instance == pkled_instance


def operation_pickling_check(instance, sim):
    pickling_check(instance)
    sim.operations += instance
    sim.run(0)
    pickling_check(instance)
