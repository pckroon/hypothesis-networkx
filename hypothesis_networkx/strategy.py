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

import itertools

from hypothesis import strategies as st
from hypothesis import note
import networkx as nx


@st.composite
def graph_builder(draw,
                  node_data=st.fixed_dictionaries({}),
                  edge_data=st.fixed_dictionaries({}),
                  node_keys=st.integers(),
                  min_nodes=0, max_nodes=50,
                  min_edges=0, max_edges=None,
                  graph_type=nx.Graph,
                  self_loops=False, connected=True):
    if min_nodes < 0:
        raise ValueError('min_nodes can not be negative')
    if max_nodes is not None and min_nodes > max_nodes:
        raise ValueError('min_nodes must be less than or equal to max_nodes')
    if max_nodes is not None and connected and max_edges < max_nodes-1:
        raise ValueError("It's impossible to create a connected graph of {}"
                         "nodes with less than {} edges".format(max_nodes, max_nodes-1))

    graph = graph_type()
    # Draw node indices and their associated data
    nodes = draw(st.lists(st.tuples(node_keys, node_data), min_size=min_nodes,
                          max_size=max_nodes, unique_by=lambda t: t[0]))

    if not nodes:
        return graph
    graph.add_node(nodes[0][0], **nodes[0][1])
    for node, data in nodes[1:]:
        # Add all the other nodes, and if it has to become a connected graph,
        # add an edge to a node that's already there. Draw the node we're
        # connecting to before adding the current one, otherwise we need to
        # make sure we don't make a self-edge at the new node.
        if connected:
            edge_to = draw(st.sampled_from(list(graph.nodes)))
        graph.add_node(node, **data)
        if connected:
            graph.add_edge(node, edge_to, **draw(edge_data))

    # Now for the mess. The maximum number of edges possible depends on the
    # graph type. In addition, if it's a DiGraph, edge [a, b] != [b, a]; but if
    # it's a "normal" graph [a, b] == [b, a]. It becomes slightly worse, since
    # DiGraph is a subclass of Graph.
    if isinstance(graph, nx.DiGraph):
        max_possible_edges = len(nodes) * (len(nodes) - 1)
        edge_unique = lambda e: tuple(e[0])
    elif isinstance(graph, nx.Graph):
        edge_unique = lambda e: frozenset(e[0])
        max_possible_edges = len(nodes) * (len(nodes) - 1)//2

    # Lastly, there's Multi(Di)Graphs, which can make an infinite number of
    # edges. We'll keep it as a numeric value for now.
    if isinstance(graph, nx.MultiGraph):
        max_possible_edges = float('inf')

    if self_loops:
        max_possible_edges += len(nodes)

    # Correct for the edges we added earlier.
    if max_edges is None:
        max_edges = max_possible_edges - len(graph.edges)
    else:
        max_edges = min(max_possible_edges, max_edges - len(graph.edges))
    max_edges = max(0, max_edges)
    # And make sure min_edges <= max_edges.
    min_edges = min(max_edges, max(0, min_edges - len(graph.edges)))

    if max_edges == float('inf'):
        max_edges = None

    note(graph.edges)
    note((min_edges, max_edges))

    available_edges = list(nx.non_edges(graph))
    if self_loops:
        available_edges.extend((n, n) for n in graph.nodes)
    note('availabie: {}'.format(str(available_edges)))

    node_pair = st.sampled_from(available_edges)
    edge = st.tuples(node_pair, edge_data)
    edges = draw(st.lists(edge, min_size=min_edges, max_size=max_edges,
                          unique_by=edge_unique))

    note(edges)
    for (n1, n2), data in edges:
        graph.add_edge(n1, n2, **data)
    return graph
