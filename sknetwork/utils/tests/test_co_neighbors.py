#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on October 2019
@author: Nathan de Lara <ndelara@enst.fr>
"""
import unittest

import numpy as np

from sknetwork.utils import co_neighbors_graph
from sknetwork.data import movie_actor
from sknetwork.linalg import CoNeighborsOperator


class TestCoNeighbors(unittest.TestCase):

    def setUp(self):
        """Simple biadjacency for tests."""
        self.biadjacency = movie_actor()

    def test_exact(self):
        n = self.biadjacency.shape[0]
        adjacency = co_neighbors_graph(self.biadjacency, method='exact', normalized=False)
        self.assertEqual(adjacency.shape, (n, n))
        adjacency = co_neighbors_graph(self.biadjacency, method='exact')
        self.assertEqual(adjacency.shape, (n, n))

        operator = CoNeighborsOperator(self.biadjacency)
        x = np.random.randn(n)
        y1 = adjacency.dot(x)
        y2 = operator.dot(x)
        self.assertAlmostEqual(np.linalg.norm(y1 - y2), 0)

    def test_knn(self):
        n = self.biadjacency.shape[0]
        adjacency = co_neighbors_graph(self.biadjacency, method='knn')
        self.assertEqual(adjacency.shape, (n, n))
        adjacency = co_neighbors_graph(self.biadjacency, method='knn', normalized=False)
        self.assertEqual(adjacency.shape, (n, n))
