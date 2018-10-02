from skfem import *

import numpy as np

import meshio
from pygmsh import generate_mesh
from pygmsh.built_in import Geometry

geom = Geometry()
circle = geom.add_circle([0.] * 3, 1., .5**3)
geom.add_physical_line(circle.line_loop.lines, 'perimeter')
geom.add_physical_surface(circle.plane_surface, 'disk')
mesh = MeshTri.from_meshio(meshio.Mesh(*generate_mesh(geom)))

element = ElementTriMorley()
mapping = MappingAffine(mesh)
ib = InteriorBasis(mesh, element, mapping, 2)


@bilinear_form
def biharmonic(u, du, ddu, v, dv, ddv, w):

    def shear(ddw):
        return np.array([[ddw[0][0], ddw[0][1]],
                         [ddw[1][0], ddw[1][1]]])

    def ddot(T1, T2):
        return T1[0, 0]*T2[0, 0] +\
               T1[0, 1]*T2[0, 1] +\
               T1[1, 0]*T2[1, 0] +\
               T1[1, 1]*T2[1, 1]

    return ddot(shear(ddu), shear(ddv))


@linear_form
def unit_rotation(v, dv, ddv, w):
    return v


stokes = asm(biharmonic, ib)
rotf = asm(unit_rotation, ib)

dofs = ib.get_dofs(mesh.boundaries['perimeter'])

D = np.concatenate((dofs.nodal['u'], dofs.facet['u_n']))

psi = np.zeros_like(rotf)
psi[ib.complement_dofs(D)] = solve(*condense(stokes, rotf, D=D))

if __name__ == "__main__":

    from os.path import splitext
    from sys import argv

    from matplotlib.tri import Triangulation
    
    M, Psi = ib.refinterp(psi, 3)
    Psi0 = max(Psi)
    print('phi0 = {} (cf. exact = 1/64 = {})'.format(Psi0, 1/64))

    ax = mesh.draw()
    fig = ax.get_figure()
    ax.tricontour(Triangulation(M.p[0, :], M.p[1, :], M.t.T), Psi)
    ax.axis('off')
    ax.get_figure().savefig(splitext(argv[0])[0] + '_stream-lines.png')

    refbasis = InteriorBasis(M, ElementTriP1())
    velocity = np.vstack([derivative(Psi, refbasis, refbasis, 1),
                          -derivative(Psi, refbasis, refbasis, 0)])
    ax = mesh.draw()
    sparsity_factor = 2**3      # subsample the arrows
    vector_factor = 2**3        # lengthen the arrows
    x = M.p[:, ::sparsity_factor]
    u = vector_factor * velocity[:, ::sparsity_factor]
    ax.quiver(x[0], x[1], u[0], u[1], x[0])
    ax.axis('off')
    ax.get_figure().savefig(splitext(argv[0])[0] + '_velocity-vectors.png')
