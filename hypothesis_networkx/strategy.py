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

"""
Provides the :mod:`hypothesis` strategy :func:`graph_builder` that can be used
for building networkx graphs.
"""

from hypothesis import strategies as st
import networkx as nx


@st.composite
def graph_builder(draw,
                  node_data=st.fixed_dictionaries({}),
                  edge_data=st.fixed_dictionaries({}),
                  node_keys=None,
                  min_nodes=0, max_nodes=25,
                  min_edges=0, max_edges=None,
                  graph_type=nx.Graph,
                  self_loops=False, connected=True):
    """
    A :mod:`hypothesis` strategy for building networkx graphs.

    Parameters
    ----------
    draw
        For internal hypothesis use.
    node_data: `hypothesis.Strategy`
        The strategy to use to generate node attributes. Must generate a
        mapping.
    edge_data: `hypothesis.Strategy`
        The strategy to use to generate edge attributes. Must generate a
        mapping.
    node_keys: `hypothesis.Strategy` or None.
        The strategy to use to generate node keys. Must generate a Hashable. If
        `None`, node keys will be taken from range(0, number_of_nodes).
    min_nodes: int
        The minimum number of nodes that should be in the generated graph. Must
        be positive.
    max_nodes: int
        The maximum number of nodes that should be in the generated graph. Must
        be larger than `min_nodes`. `None` means no upper limit.
    min_edges: int
        The minimum number of edges that should be in the generated graph.
    max_edges: int
        The maximum number of edges that should be in the generated graph.
        `None` means no upper limit.
    graph_type: class
        The type of graph that should be created.
    self_loops: bool
        Whether self loops (edges between a node and itself) are allowed.
    connected: bool
        If `True`, the generated graph is guaranteed to be a single connected
        component.

    Raises
    ------
    ValueError
        - If `min_nodes` < 0.
        - If `max_nodes` < `min_nodes`
        - If the graph has to be connected, but `max_edges` is too small
          relative to `max_nodes`.

    Returns
    -------
    networkx.Graph
        The created graph. The actual type is determined by the argument
        `graph_type`.
    """
    if min_nodes < 0:
        raise ValueError('min_nodes can not be negative')
    if max_nodes is not None and min_nodes > max_nodes:
        raise ValueError('min_nodes must be less than or equal to max_nodes')
    if max_nodes is not None and max_edges is not None and connected and max_edges < max_nodes-1:
        raise ValueError("It's impossible to create a connected graph of {}"
                         "nodes with less than {} edges".format(max_nodes, max_nodes-1))

    graph = graph_type()
    # Draw node indices and their associated data
    node_datas = draw(st.lists(node_data, min_size=min_nodes, max_size=max_nodes))

    if not node_datas:
        return graph

    graph.add_nodes_from(enumerate(node_datas))

    # Draw a set of initial edges that guarantee that graph will be connected.
    # We use the invariant that all nodes < n_idx are connected. We create an
    # edge between n_idx and one of those before so that all nodes < n_idx + 1
    # are now connected.
    if connected:
        initial_edges = [draw(st.tuples(st.sampled_from(range(0, n_idx)),
                                        st.just(n_idx),
                                        edge_data))
                         for n_idx in range(1, len(graph))]
        graph.add_edges_from(initial_edges)

    # Now for the mess. The maximum number of edges possible depends on the
    # graph type.
    if isinstance(graph, nx.MultiGraph):
        # Multi(Di)Graphs can make an infinite number of edges. We'll keep it as
        # a numeric value for now.
        max_possible_edges = float('inf')
    else:
        # If it's a DiGraph, edge [a, b] != [b, a]; but if it's an undirected
        # graph [a, b] == [b, a]. It becomes slightly worse, since DiGraph is a
        # subclass of Graph.
        if isinstance(graph, nx.DiGraph):
            max_possible_edges = len(graph) * (len(graph) - 1)
        else:  # elif isinstance(graph, nx.Graph):
            max_possible_edges = (len(graph) * (len(graph) - 1))//2
        # And if we can make self-loops we get a few more. Note that the edge
        # (1, 1) is the same as the edge (1, 1), even in a DiGraph.
        if self_loops:
            max_possible_edges += len(graph)

    # Clamp to the range (0, max_possible_edges). Note that max_possible_edges
    # may be infinite in the case of MultiGraphs.
    if max_edges is None or max_edges > max_possible_edges:
        max_edges = max_possible_edges
    elif max_edges < 0:
        # We will need to correct for the number of edges already added.
        max_edges = len(graph.edges)
    max_edges -= len(graph.edges)

    if max_edges == float('inf'):
        max_edges = None

    # Likewise for min_edges...
    # We already added some edges, so subtract those.
    min_edges -= len(graph.edges)
    if min_edges < 0:
        min_edges = 0
    elif min_edges > max_edges:
        min_edges = max_edges

    def edge_filter(idx, jdx):
        """
        Helper function to decide whether the edge between idx and jdx can still
        be added to graph.
        """
        multi_edge = not graph.has_edge(idx, jdx) or isinstance(graph, nx.MultiGraph)
        # <= because self loops
        directed = idx <= jdx or isinstance(graph, nx.DiGraph)
        self_loop = idx != jdx or self_loops
        return multi_edge and directed and self_loop

    options = [(idx, jdx) for jdx in graph for idx in graph if edge_filter(idx, jdx)]
    if options:
        # We need to sample a number of items from options, these items are 
        # possibly not unique. In addition, we need to draw the same number of
        # items from edge_data and associate the two. To top it off, uniqueness
        # is defined by the content of the first element of the tuple.
        edges = st.lists(st.tuples(st.sampled_from(options), edge_data),
                         unique_by=None if isinstance(graph, nx.MultiGraph) else lambda e: e[:-1],
                         min_size=min_edges,
                         max_size=max_edges)
        graph.add_edges_from((e[0][0], e[0][1], e[1]) for e in draw(edges))

    if node_keys is not None:
        new_idxs = draw(st.lists(node_keys,
                                 unique=True,
                                 min_size=len(graph),
                                 max_size=len(graph)))
        graph = nx.relabel_nodes(graph, dict(zip(list(graph), new_idxs)))

    return graph
