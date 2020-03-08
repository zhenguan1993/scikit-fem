import itertools

import numpy as np

from .element import Element
from .discrete_field import DiscreteField


class ElementGlobal(Element):
    """Elements defined implicitly through global degrees-of-freedom."""

    V = None  # For caching inverse Vandermonde matrix
    derivatives = 2  # By default, include first and second derivatives

    def gbasis(self, mapping, X, i, tind=None):
        if tind is None:
            tind = np.arange(mapping.mesh.t.shape[1])

        if self.V is None:
            # initialize power basis
            self._pbasis_init(self.maxdeg, self.dim, self.derivatives)
            # construct Vandermonde matrix and invert it
            self.V = np.linalg.inv(self._eval_dofs(mapping.mesh))

        V = self.V[tind]

        x = mapping.F(X, tind=tind)
        U = [np.zeros((self.dim,) * k + x[0].shape)
             for k in range(self.derivatives + 1)]

        N = len(self._pbasis[()])
        # loop over new basis
        for k in range(self.derivatives + 1):
            for itr in range(N):
                diffs = list(itertools.product(*((list(range(self.dim)),) * k)))
                for diff in diffs:
                    U[k][diff] += (V[:, itr, i][:, None]
                                   * self._pbasis[diff][itr](*x))

        # put higher order derivatives into a single array
        hod = np.empty((self.derivatives - 2,), dtype=object)
        for k in range(self.derivatives - 2):
            hod[k] = U[k + 3]

        return (
            DiscreteField(
                value=U[0],
                grad=U[1],
                hess=U[2],
                hod=hod,
            ),
        )

    def _pbasis_create(self, i, j=None, k=None, dx=0, dy=0, dz=0):
        """Return a single power basis function."""
        if j is None and k is None:  # 1d
            cx = 1
            if dx > 0:
                for l in np.arange(dx, 0, -1):
                    cx *= i - dx + l
            return eval(("lambda x: {}*x**{}"
                         .format(cx, np.max([i - dx, 0]))))
        elif k is None:  # 2d
            cx = 1
            cy = 1
            if dx > 0:
                for l in np.arange(dx, 0, -1):
                    cx *= i - dx + l
            if dy > 0:
                for l in np.arange(dy, 0, -1):
                    cy *= j - dy + l
            return eval(("lambda x, y: {}*x**{}*y**{}"
                         .format(cx * cy,
                                 np.max([i - dx, 0]),
                                 np.max([j - dy, 0]))))
        else:  # 3d
            cx = 1
            cy = 1
            cz = 1
            if dx > 0:
                for l in np.arange(dx, 0, -1):
                    cx *= i - dx + l
            if dy > 0:
                for l in np.arange(dy, 0, -1):
                    cy *= j - dy + l
            if dz > 0:
                for l in np.arange(dz, 0, -1):
                    cz *= k - dz + l
            return eval(("lambda x, y, z: {}*x**{}*y**{}*z**{}"
                         .format(cx * cy * cz,
                                 np.max([i - dx, 0]),
                                 np.max([j - dy, 0]),
                                 np.max([k - dz, 0]),)))

    def _pbasis_init(self, maxdeg, dim, Ndiff):
        """Define power bases.

        Parameters
        ----------
        maxdeg
            Maximum degree of the basis
        dim
            Dimension of the domain.x
        Ndiff
            Number of derivatives to include.

        """
        self._pbasis = {}
        for k in range(Ndiff + 1):
            diffs = list(itertools.product(*((list(range(dim)),) * k)))
            for diff in diffs:
                desc = ''.join([str(d) for d in diff])
                dx = sum([1 for d in diff if d==0])
                dy = sum([1 for d in diff if d==1])
                self._pbasis[diff] = [
                    self._pbasis_create(i=i, j=j, dx=dx, dy=dy)
                    for i in range(maxdeg + 1)
                    for j in range(maxdeg + 1)
                    if i + j <= maxdeg
                ]

    def _eval_dofs(self, mesh, tind=None):
        if tind is None:
            tind = np.arange(mesh.t.shape[1])

        N = len(self._pbasis[()])
        V = np.zeros((len(tind), N, N))

        if mesh.t.shape[0] == 3:
            # vertices, edges, tangents, normals
            v = np.empty((3, 2, len(tind)))
            e = np.empty((3, 2, len(tind)))
            n = np.empty((3, 2, len(tind)))

            # vertices
            for itr in range(3):
                v[itr] = mesh.p[:, mesh.t[itr, tind]]

            # edge midpoints
            e[0] = .5 * (v[0] + v[1])
            e[1] = .5 * (v[1] + v[2])
            e[2] = .5 * (v[0] + v[2])

            # normal vectors
            n[0] = v[0] - v[1]
            n[1] = v[1] - v[2]
            n[2] = v[0] - v[2]

            for itr in range(3):
                n[itr] = np.array([n[itr, 1, :], -n[itr, 0, :]])
                n[itr] /= np.linalg.norm(n[itr], axis=0)
        else:
            raise NotImplementedError("The used mesh type not supported "
                                      "in ElementH2.")

        # evaluate dofs, gdof implemented in subclasses
        for itr in range(N):
            for jtr in range(N):
                U = {k: self._pbasis[k][itr] for k in self._pbasis}
                V[:, jtr, itr] = self.gdof(U, v, e, n, jtr)

        return V
