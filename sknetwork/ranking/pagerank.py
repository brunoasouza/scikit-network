#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on May 31 2019
@author: Nathan de Lara <ndelara@enst.fr>
@author: Thomas Bonald <bonald@enst.fr>
"""

from typing import Union, Optional

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import eigs, LinearOperator, lsqr, bicgstab

from sknetwork.basics.rand_walk import transition_matrix
from sknetwork.ranking.base import BaseRanking
from sknetwork.utils.format import bipartite2undirected
from sknetwork.utils.check import check_format, is_square
from sknetwork.utils.seeds import seeds2probs, stack_seeds
from sknetwork.utils.verbose import VerboseMixin


class RandomSurferOperator(LinearOperator, VerboseMixin):
    """
    Random surfer as a LinearOperator

    Parameters
    ----------
    adjacency :
        Adjacency matrix of the graph.
    damping_factor : float
        Probability to continue the random walk.
    seeds :
        If ``None``, the uniform distribution is used.
        Otherwise, a non-negative, non-zero vector or a dictionary must be provided.
    fb_mode :
        Forward-Backward mode. If ``True``, the random surfer performs two consecutive jumps, the first one follows the
        direction of the edges, while the second one goes in the opposite direction.

    Attributes
    ----------
    a : sparse.csr_matrix
        Scaled transposed transition matrix.
    b : np.ndarray
        Scaled restart probability vector.

    """
    def __init__(self, adjacency: sparse.csr_matrix, damping_factor: float = 0.85, seeds=None,
                 fb_mode: bool = False, verbose: bool = False):
        VerboseMixin.__init__(self, verbose)

        n1, n2 = adjacency.shape
        restart_prob: np.ndarray = seeds2probs(n1, seeds)

        if fb_mode:
            restart_prob = np.hstack((restart_prob, np.zeros(n2)))
            adjacency = bipartite2undirected(adjacency)

        LinearOperator.__init__(self, shape=adjacency.shape, dtype=float)
        n = adjacency.shape[0]
        out_degrees = adjacency.dot(np.ones(n))

        damping_matrix = damping_factor * sparse.eye(n, format='csr')
        if fb_mode:
            damping_matrix.data[n1:] = 1

        self.a = (damping_matrix.dot(transition_matrix(adjacency))).T.tocsr()
        self.b = (np.ones(n) - damping_factor * out_degrees.astype(bool)) * restart_prob

    def _matvec(self, x):
        return self.a.dot(x) + self.b * x.sum()

    # noinspection PyTypeChecker
    def solve(self, solver: str = 'lanczos', n_iter: int = 10):
        """Pagerank vector for a given adjacency and seeds.

        Parameters
        ----------
        solver: str
            Which method to use to solve the Pagerank problem. Can be 'lanczos', 'lsqr' or 'bicgstab'.
        n_iter : int
            If ``solver`` is not one of the standard values, the pagerank is approximated by emulating the random walk
            for ``n_iter`` iterations.

        Returns
        -------
        score: np.ndarray
            Pagerank of the rows.

        """

        n: int = self.a.shape[0]

        if solver == 'bicgstab':
            x, info = bicgstab(sparse.eye(n, format='csr') - self.a, self.b, atol=0.)
            self._scipy_solver_info(info)
        elif solver == 'lanczos':
            _, x = sparse.linalg.eigs(self, k=1)
        elif solver == 'lsqr':
            x = lsqr(sparse.eye(n, format='csr') - self.a, self.b)[0]
        else:
            x = self.b
            for i in range(n_iter):
                x = self.dot(x)
                x /= x.sum()

        x = abs(x.flatten().real)
        return x / x.sum()


class PageRank(BaseRanking, VerboseMixin):
    """
    Compute the PageRank of each node, corresponding to its frequency of visit by a random walk.

    The random walk restarts with some fixed probability. The restart distribution can be personalized by the user.
    This variant is known as Personalized PageRank.

    Parameters
    ----------
    damping_factor : float
        Probability to continue the random walk.
    solver : str
        Which solver to use: 'bicgstab', 'lanczos' (default), 'lsqr'.
        Otherwise, the random walk is emulated for a certain number of iterations.
    n_iter : int
        If ``solver`` is not one of the standard values, the pagerank is approximated by emulating the random walk for
        ``n_iter`` iterations.

    Attributes
    ----------
    scores_ : np.ndarray
        PageRank score of each node.

    Example
    -------
    >>> from sknetwork.data import house
    >>> pagerank = PageRank()
    >>> adjacency = house()
    >>> seeds = {0: 1}
    >>> np.round(pagerank.fit_transform(adjacency, seeds), 2)
    array([0.29, 0.24, 0.12, 0.12, 0.24])

    References
    ----------
    Page, L., Brin, S., Motwani, R., & Winograd, T. (1999). The PageRank citation ranking: Bringing order to the web.
    Stanford InfoLab.
    """
    def __init__(self, damping_factor: float = 0.85, solver: Union[str, None] = 'lanczos', n_iter: int = 10):
        super(PageRank, self).__init__()

        if damping_factor < 0 or damping_factor >= 1:
            raise ValueError('Damping factor must be between 0 and 1.')
        else:
            self.damping_factor = damping_factor
        self.solver = solver
        self.n_iter = n_iter

    # noinspection PyTypeChecker
    def fit(self, adjacency: Union[sparse.csr_matrix, np.ndarray],
            seeds: Optional[Union[dict, np.ndarray]] = None) -> 'PageRank':
        """Fit algorithm to data.

        Parameters
        ----------
        adjacency :
            Adjacency matrix.
        seeds :
            If ``None``, the uniform distribution is used.
            Otherwise, a non-negative, non-zero vector or a dictionary must be provided.

        Returns
        -------
        self: :class:`PageRank`
        """

        adjacency = check_format(adjacency)
        if not is_square(adjacency):
            raise ValueError("The adjacency is not square. See BiPageRank.")

        rso = RandomSurferOperator(adjacency, self.damping_factor, seeds, False)
        self.scores_ = rso.solve(self.solver, self.n_iter)

        return self


class BiPageRank(PageRank):
    """Compute the PageRank of each node through a random walk in the bipartite graph.

    Parameters
    ----------
    damping_factor : float
        Probability to continue the random walk.
    solver : str
        Which solver to use: 'bicgstab', 'lanczos', 'lsqr'.

    Attributes
    ----------
    scores_ : np.ndarray
        PageRank score of each row.
    scores_row_ : np.ndarray
        PageRank score of each row (copy of **scores_**).
    scores_col_ : np.ndarray
        PageRank score of each column.


    Example
    -------
    >>> from sknetwork.data import star_wars
    >>> bipagerank = BiPageRank()
    >>> biadjacency = star_wars()
    >>> seeds = {0: 1}
    >>> np.round(bipagerank.fit_transform(biadjacency, seeds), 2)
    array([0.45, 0.11, 0.28, 0.17])
    """
    def __init__(self, damping_factor: float = 0.85, solver: str = None, n_iter: int = 10):
        PageRank.__init__(self, damping_factor, solver, n_iter)

        self.scores_row_ = None
        self.scores_col_ = None

    def fit(self, biadjacency: Union[sparse.csr_matrix, np.ndarray],
            seeds_row: Optional[Union[dict, np.ndarray]] = None, seeds_col: Optional[Union[dict, np.ndarray]] = None) \
            -> 'BiPageRank':
        """Fit algorithm to data.

        Parameters
        ----------
        biadjacency :
            Biadjacency matrix.
        seeds_row :
            Seed rows, as a dict or a vector.
        seeds_col :
            Seed columns, as a dict or a vector.
            If both seeds_row and seeds_col are ``None``, the uniform distribution is used.

        Returns
        -------
        self: :class:`BiPageRank`
        """

        biadjacency = check_format(biadjacency)
        n_row, n_col = biadjacency.shape
        adjacency = bipartite2undirected(biadjacency)
        seeds = stack_seeds(n_row, n_col, seeds_row, seeds_col)
        pagerank = PageRank(self.damping_factor, self.solver, self.n_iter)
        pagerank.fit(adjacency, seeds)

        scores_row = pagerank.scores_[:n_row]
        scores_col = pagerank.scores_[n_row:]

        self.scores_row_ = scores_row / np.sum(scores_row)
        self.scores_col_ = scores_col / np.sum(scores_col)
        self.scores_ = self.scores_row_

        return self
