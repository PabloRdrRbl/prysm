"""Tools for working with Q (Forbes) polynomials."""
from functools import lru_cache

from .conf import config
from .pupil import Pupil
from .mathops import engine as e
from .coordinates import make_rho_phi_grid


def qbfs_recurrence_P(n, x, Pnm1=None, Pnm2=None, recursion_coef=None):
    """P(m+1) from oe-18-19-19700 eq. (2.6)."""
    if n == 0:
        return 2
    elif n == 1:
        return 6 - 8 * x
    else:
        if Pnm1 is None:
            Pnm1 = qbfs_recurrence_P(n - 1, x)
        if Pnm2 is None:
            Pnm2 = qbfs_recurrence_P(n - 2, x)
        if recursion_coef is None:
            recursion_coef = 2 - 4 * x

        return recursion_coef * Pnm1 - Pnm2


def qbfs_recurrence_Q(n, x, Pn=None, Pnm1=None, Pnm2=None, Qnm1=None, Qnm2=None, recursion_coef=None):
    """Q(m+1) from oe-18-19-19700 eq. (2.7)."""
    if n == 0:
        return e.ones_like(x)
    elif n == 1:
        return 1 / e.sqrt(19) * (13 - 16 * x)
    else:
        # allow passing of cached results
        if Pnm2 is None:
            Pnm2 = qbfs_recurrence_P(n - 2, x, recursion_coef=recursion_coef)
        if Pnm1 is None:
            Pnm1 = qbfs_recurrence_P(n - 1, x, Pnm2=Pnm2, recursion_coef=recursion_coef)
        if Pn is None:
            Pn = qbfs_recurrence_P(n, x, Pnm1=Pnm1, Pnm2=Pnm2, recursion_coef=recursion_coef)
        if Qnm2 is None:
            Qnm2 = qbfs_recurrence_Q(n - 2, x, Pn=Pn, Pnm1=Pnm1, Pnm2=Pnm2, recursion_coef=recursion_coef)
        if Qnm1 is None:
            Qnm1 = qbfs_recurrence_Q(n - 1, x, Pn=Pn, Pnm1=Pnm1, Pnm2=Pnm2, Qnm2=Qnm2, recursion_coef=recursion_coef)

        # now calculate the three-term recursion
        term1 = Pn
        term2 = g_qbfs(n - 1) * Qnm1
        term3 = h_qbfs(n - 2) * Qnm2
        numerator = term1 - term2 - term3
        denominator = f_qbfs(n)
        return numerator / denominator


@lru_cache()
def g_qbfs(n_minus_1):
    """g(m-1) from oe-18-19-19700 eq. (A.15)"""
    if n_minus_1 == 0:
        return - 1 / 2
    else:
        n_minus_2 = n_minus_1 - 1
        return - (1 + g_qbfs(n_minus_2) * h_qbfs(n_minus_2)) / f_qbfs(n_minus_1)


@lru_cache()
def h_qbfs(n_minus_2):
    """h(m-2) from oe-18-19-19700 eq. (A.14)"""
    n = n_minus_2 + 2
    return -n * (n - 1) / (2 * f_qbfs(n_minus_2))


@lru_cache()
def f_qbfs(n):
    """f(m) from oe-18-19-19700 eq. (A.16)"""
    if n == 0:
        return 2
    elif n == 1:
        return e.sqrt(19) / 2
    else:
        term1 = n * (n + 1) + 3
        term2 = g_qbfs(n - 1) ** 2
        term3 = h_qbfs(n - 2) ** 2
        return e.sqrt(term1 - term2 - term3)


class QBFSCache(object):
    """Cache of Qbfs terms evaluated over the unit circle.

    Note that the .grids attribute stores only radial coordinates, and they are stored in squared form."""
    def __init__(self):
        """Create a new QBFSCache instance."""
        self.Qs = {}
        self.Ps = {}
        self.grids = {}

    def get_QBFS(self, m, samples, rho_max=1):
        """Get an array of phase values for a given index, and number of samples."""
        key = self.make_key(m=m, samples=samples, rho_max=rho_max)
        try:
            Qm = self.Qs[key]
        except KeyError:
            rho = self.get_grid(samples, rho_max=rho_max)
            Pm = self.get_PBFS(m=m, samples=samples, rho_max=rho_max)
            if m > 2:
                Pnm2 = self.get_PBFS(m=m - 2, samples=samples, rho_max=rho_max)
                Pnm1 = self.get_PBFS(m=m - 1, samples=samples, rho_max=rho_max)
                Qnm2 = self.get_QBFS(m=m - 2, samples=samples, rho_max=rho_max)
                Qnm1 = self.get_QBFS(m=m - 1, samples=samples, rho_max=rho_max)
            else:
                Pnm1, Pnm2, Qnm1, Qnm2 = None, None, None, None

            Qm = qbfs_recurrence_Q(m, rho, Pn=Pm, Pnm1=Pnm1, Pnm2=Pnm2,
                                   Qnm1=Qnm1, Qnm2=Qnm2)
            self.Qs[key] = Qm

        return Qm

    def get_PBFS(self, m, samples, rho_max=1):
        """Get an array of P values for a given index."""
        key = self.make_key(m=m, samples=samples, rho_max=rho_max)
        try:
            Pm = self.Ps[key]

        except KeyError:
            rho = self.get_grid(samples, rho_max=rho_max)
            if m > 2:
                Pnm2 = self.get_PBFS(m - 2, samples=samples, rho_max=rho_max)
                Pnm1 = self.get_PBFS(m - 1, samples=samples, rho_max=rho_max)
            else:
                Pnm1, Pnm2 = None, None

            Pm = qbfs_recurrence_P(m, rho, Pnm1=Pnm1, Pnm2=Pnm2)
            self.Ps[key] = Pm

        return Pm

    def get_grid(self, samples, rho_max=1):
        """Get a grid of rho coordinates for a given number of samples."""
        key = self.make_key(None, samples=samples, rho_max=rho_max)[1:]
        try:
            rho = self.grids[key]
        except KeyError:
            rho, _ = make_rho_phi_grid(samples, aligned='y', radius=rho_max)
            rho = rho ** 2
            self.grids[key] = rho

        return rho

    def __call__(self, m, samples, rho_max=1):
        """Get an array of sag values for a given index, norm, and number of samples."""
        return self.get_QBFS(m=m, samples=samples, rho_max=rho_max)

    def make_key(self, m, samples, rho_max):
        """Generate a key into the cache dictionaries."""
        return (m, samples, rho_max)

    def clear(self, *args):
        """Empty the cache."""
        self.Qs = {}
        self.Ps = {}
        self.grids = {}

    @property
    def nbytes(self):
        n = 0
        for key in self.Qs:
            n += self.Qs[key].nbytes
            n += self.Ps[key].nbytes
            n += self.grids[key[1:]].nbytes

        return n


QBFScache = QBFSCache()
config.chbackend_observers.append(QBFScache.clear)


# Note that this class doesn't implement _name and other RichData requirements
class QPolySag1D(Pupil):
    """Base class with 1D Q polynomial logic."""

    def __init__(self, *args, **kwargs):
        """Initialize a new QBFS instance."""
        self.coefs = {}
        pass_args = {}
        if kwargs is not None:
            for key, value in kwargs.items():
                if key[0].lower() == 'a':
                    idx = int(key[1:])  # strip 'A' from index
                    self.coefs[idx] = value
                else:
                    pass_args[key] = value

        super().__init__(**pass_args)

    def build(self):
        """Use the aspheric coefficients stored in this class instance to build a sag model.

        Returns
        -------
        self : `QPolySag1D`
            this QPolySag1D instance`

        """
        self.phase = e.zeros([self.samples, self.samples], dtype=config.precision)
        ordered_terms = sorted(self.coefs)
        ordered_values = [self.coefs[v] for v in ordered_terms]
        for term, coef in zip(ordered_terms, ordered_values):
            if coef == 0:
                continue
            else:
                self.phase += coef * self._cache(term, self.samples)


class QBFSSag(QPolySag1D):
    _name = 'Qbfs'
    _cache = QBFScache
    """Qbfs aspheric surface sag, excluding base sphere."""

    def build(self):
        """Use the aspheric coefficients stored in this class instance to build a sag model.

        Returns
        -------
        self : `QBFSSag`
            this QBFSSag instance`

        """
        super().build()
        r2 = self._cache.get_grid(self.samples)
        coef = r2 * (1 - r2)
        self.phase *= coef


def a_qcon(n):
    """a(n) from oe-18-13-13851 eq. (5.2a)."""
    numerator = (2 * n + 5) * (n ** 2 + 5 * n + 10)
    denominator = (n + 1) * (n + 5) * (n + 5)
    return numerator / denominator


def b_qcon(n):
    """b(n) from oe-18-13-13851 eq. (5.2b)."""
    numerator = 2 * (n + 3) * (2 * n + 5)
    denominator = (n + 1) * (n + 5)
    return numerator / denominator


def c_qcon(n):
    """c(n) from oe-18-13-13851 eq. (5.2c)."""
    numerator = (n + 3) * (n + 4) * n
    denominator = (n + 1) * (n + 2) * (n + 5)
    return numerator / denominator


def a_zernike(m, n):
    """a(n) from oe-18-13-13861 eq. (4.1a)."""
    s = m + 2 * n
    numerator = (s + 1) * ((s - n) ** 2 + n ** 2 + s)
    denominator = (n + 1) * (s - n + 1) * s
    return numerator / denominator


def b_zernike(m, n):
    """b(n) from oe-18-13-13861 eq. (4.1b)."""
    s = m + 2 * n
    numerator = (s + 2) * (s + 1)
    denominator = (n + 1) * (s + n - 1)
    return numerator / denominator


def c_zernike(m, n):
    """c(n) from oe-18-13-13861 eq. (4.1c)."""
    s = m + 2 * n
    numerator = (s + 2) * (s - n) * n
    denominator = (n + 1) * (s - n + 1) * s
    return numerator / denominator


def qcon_recurrence(n, x, qnm1=None, qnm2=None):
    from scipy.special import jacobi
    jacpoly = jacobi(n, 0, 4)
    return jacpoly(x)


class QCONCache(object):
    """Cache of Qcon terms evaluated over the unit circle.

    Note that the .grids attribute stores only radial coordinates, and they are stored as:
    x => x^2
      => 2x - 1.

    This means that all of the appropriate coordinate transformations are applied only once, instead
    of once in the generation of each term."""
    def __init__(self):
        """Create a new QCONCache instance."""
        self.Qs = {}
        self.Ps = {}
        self.grids = {}

    def get_QCON(self, m, samples, rho_max=1):
        """Get an array of phase values for a given index, and number of samples."""
        # TODO: update
        key = self.make_key(m=m, samples=samples, rho_max=rho_max)
        try:
            Qm = self.Qs[key]
        except KeyError:
            rho = self.get_grid(samples, rho_max=rho_max)
            Pm = self.get_PBFS(m=m, samples=samples, rho_max=rho_max)
            if m > 2:
                Pnm2 = self.get_PBFS(m=m - 2, samples=samples, rho_max=rho_max)
                Pnm1 = self.get_PBFS(m=m - 1, samples=samples, rho_max=rho_max)
                Qnm2 = self.get_QBFS(m=m - 2, samples=samples, rho_max=rho_max)
                Qnm1 = self.get_QBFS(m=m - 1, samples=samples, rho_max=rho_max)
            else:
                Pnm1, Pnm2, Qnm1, Qnm2 = None, None, None, None

            Qm = qbfs_recurrence_Q(m, rho, Pn=Pm, Pnm1=Pnm1, Pnm2=Pnm2,
                                   Qnm1=Qnm1, Qnm2=Qnm2)
            self.Qs[key] = Qm

        return Qm

    def get_PBFS(self, m, samples, rho_max=1):
        """Get an array of P values for a given index."""
        # TODO: update
        key = self.make_key(m=m, samples=samples, rho_max=rho_max)
        try:
            Pm = self.Ps[key]

        except KeyError:
            rho = self.get_grid(samples, rho_max=rho_max)
            if m > 2:
                Pnm2 = self.get_PBFS(m - 2, samples=samples, rho_max=rho_max)
                Pnm1 = self.get_PBFS(m - 1, samples=samples, rho_max=rho_max)
            else:
                Pnm1, Pnm2 = None, None

            Pm = qbfs_recurrence_P(m, rho, Pnm1=Pnm1, Pnm2=Pnm2)
            self.Ps[key] = Pm

        return Pm

    def get_grid(self, samples, rho_max=1):
        """Get a grid of rho coordinates for a given number of samples."""
        key = self.make_key(None, samples=samples, rho_max=rho_max)[1:]
        try:
            rho = self.grids[key]
        except KeyError:
            rho, _ = make_rho_phi_grid(samples, aligned='y', radius=rho_max)
            rho = rho ** 2
            rho = 2 * rho - 1
            self.grids[key] = rho

        return rho

    def __call__(self, m, samples, rho_max=1):
        """Get an array of sag values for a given index, norm, and number of samples."""
        return self.get_QCON(m=m, samples=samples, rho_max=rho_max)

    def make_key(self, m, samples, rho_max):
        """Generate a key into the cache dictionaries."""
        return (m, samples, rho_max)

    def clear(self, *args):
        """Empty the cache."""
        self.Qs = {}
        self.Ps = {}
        self.grids = {}

    @property
    def nbytes(self):
        n = 0
        for key in self.Qs:
            n += self.Qs[key].nbytes
            n += self.Ps[key].nbytes
            n += self.grids[key[1:]].nbytes

        return n


QCONcache = QCONCache()
config.chbackend_observers.append(QCONcache.clear)


class QCONSag(QPolySag1D):
    _name = 'Qcon'
    _cache = QCONcache
    """Qcon aspheric surface sag, excluding base sphere."""

    def build(self):
        """Use the aspheric coefficients stored in this class instance to build a sag model.

        Returns
        -------
        self : `QCONSag`
            this QCONSag instance`

        """
        super().build()
        # todo, update this.  Want r^4, but cache grid is stored as a more complicated
        # transformation.  Maybe store grid twice, once as r or r^2, and another as the
        # full transformation?

        # the code below is r^2, regardless.
        r2 = self._cache.get_grid(self.samples)
        coef = r2 * (1 - r2)
        self.phase *= coef