#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2018 University of Groningen

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from hypothesis import strategies as st
from hypothesis import given, settings, HealthCheck, note

import networkx as nx
import pytest

from hypothesis_networkx import graph_builder

# Pylint doesn't like hypothesis
# pylint: disable=no-value-for-parameter


@settings(max_examples=250, suppress_health_check=[HealthCheck.too_slow])
@given(st.data())
def test_graph_builder(data):
    """
    Make sure the number of nodes and edges of the generated graphs is correct,
    and make sure that graphs that are supposed to be connected are.
    """
    graph_types = st.sampled_from([nx.Graph, nx.DiGraph, nx.MultiGraph,
                                   nx.MultiDiGraph, nx.OrderedGraph,
                                   nx.OrderedDiGraph, nx.OrderedMultiGraph,
                                   nx.OrderedMultiDiGraph])

    graph_type = data.draw(graph_types, label='graph type')
    node_keys = st.integers()

    multigraph = graph_type in [nx.MultiGraph, nx.MultiDiGraph,
                                nx.OrderedMultiGraph, nx.OrderedMultiDiGraph]

    min_nodes = data.draw(st.integers(min_value=0, max_value=25),
                          label='min nodes')
    max_nodes = data.draw(st.integers(min_value=min_nodes, max_value=25),
                          label='max nodes')

    max_min_edges = None if not multigraph else 50
    min_edges = data.draw(st.integers(min_value=0, max_value=max_min_edges),
                          label='min edges')
    max_edges = data.draw(st.one_of(st.none(), st.integers(min_value=max(min_edges, max_nodes-1))),
                          label='max edges')

    if multigraph:
        max_edges = min(50, max_edges) if max_edges else 50

    self_loops = data.draw(st.booleans(), label='self loops')
    connected = data.draw(st.booleans(), label='connected')

    strategy = graph_builder(node_keys=node_keys,
                             min_nodes=min_nodes, max_nodes=max_nodes,
                             min_edges=min_edges, max_edges=max_edges,
                             self_loops=self_loops, connected=connected,
                             graph_type=graph_type)
    graph = data.draw(strategy)

    note("Number of nodes: {}".format(len(graph)))
    note("Number of edges: {}".format(len(graph.edges)))

    if isinstance(graph, nx.DiGraph):
        max_possible_edges = len(graph.nodes) * (len(graph.nodes) - 1)
    elif isinstance(graph, nx.Graph):
        max_possible_edges = len(graph.nodes) * (len(graph.nodes) - 1)//2
    if isinstance(graph, nx.MultiGraph):
        max_possible_edges = float('inf')
    if self_loops:
        max_possible_edges += len(graph.nodes)

    if max_edges is None:
        max_edges = float('inf')
    if max_nodes is None:
        max_nodes = float('inf')

    if min_edges > max_possible_edges:
        min_edges = max_possible_edges
    if len(graph) < 2:
        min_edges = 0
    note('min_edges: {}'.format(min_edges))
    note('max_edges: {}'.format(max_edges))

    assert isinstance(graph, graph_type)
    assert min_nodes <= len(graph.nodes) <= max_nodes
    assert min_edges <= len(graph.edges) <= max_edges
    assert self_loops or nx.number_of_selfloops(graph) == 0
    if graph:
        if isinstance(graph, nx.DiGraph):
            assert not connected or nx.is_weakly_connected(graph)
        else:
            assert not connected or nx.is_connected(graph)


def test_multigraph_max_edges_none():
    try:
        graph_builder(graph_type=nx.MultiGraph, max_edges=None).example()
    except Exception:
        pytest.fail()


@settings(deadline=None)
@given(st.data())
def test_node_edge_data(data):
    """
    Make sure node and edge data end up in the right place.
    """
    node_data = st.dictionaries(keys=st.one_of(st.text(), st.integers()),
                                values=st.one_of(st.text(), st.integers()),
                                max_size=2)
    node_data = data.draw(node_data)
    node_data_st = st.just(node_data)
    edge_data = st.dictionaries(keys=st.one_of(st.text(), st.integers()),
                                values=st.one_of(st.text(), st.integers()),
                                max_size=2)
    edge_data = data.draw(edge_data)
    edge_data_st = st.just(edge_data)

    builder = graph_builder(max_nodes=3, max_edges=3,
                            node_data=node_data_st, edge_data=edge_data_st)

    graph = data.draw(builder)
    for node in graph:
        assert graph.nodes[node] == node_data
    for edge in graph.edges:
        assert graph.edges[edge] == edge_data


@given(st.data())
def test_node_keys(data):
    """
    Make sure node keys are drawn from the correct strategy.
    """
    size = 5
    base_keys = st.one_of(st.integers(), st.text())
    node_keys = st.sets(st.recursive(base_keys, lambda s: st.tuples(s, s)),
                        min_size=size, max_size=size)
    keys = data.draw(node_keys)
    graph = data.draw(graph_builder(min_nodes=size, max_nodes=size,
                                    node_keys=st.sampled_from(list(keys))))
    assert set(graph.nodes) == set(keys)


@given(st.data())
def test_negative_max_edges(data):
    """
    Make sure that when max_edges < 0, max_edges becomes 0.
    """
    builder = graph_builder(max_nodes=5, connected=False, max_edges=-1)
    graph = data.draw(builder)
    note("Number of nodes: {}".format(len(graph.nodes)))
    note("Number of edges: {}".format(len(graph.edges)))

    assert len(graph.edges) == 0
    assert len(graph.nodes) <= 5
