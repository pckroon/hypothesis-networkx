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
import networkx as nx


@st.composite
def graph_builder(draw,
                  node_data=st.fixed_dictionaries({}),
                  edge_data=st.fixed_dictionaries({}),
                  node_keys=st.integers(),
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
    node_keys: `hypothesis.Strategy`
        The strategy to use to generate node keys. Must generate a Hashable.
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
        If `True`, the generated graph is garuanteed to be a single connected
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
    node_keys = draw(st.sets(node_keys, min_size=min_nodes, max_size=max_nodes))

    if not node_keys:
        return graph

    node = node_keys.pop()
    data = draw(node_data)
    # We can't do **data, since the keys might be e.g. int instead of str.
    graph.add_node(node)
    for key, value in data.items():
        graph.nodes[node][key] = value

    for node in node_keys:
        # Add all the other nodes, and if it has to become a connected graph,
        # add an edge to a node that's already there. Draw the node we're
        # connecting to before adding the current one, otherwise we need to
        # make sure we don't make a self-edge at the new node.
        if connected:
            edge_to = draw(st.sampled_from(list(graph.nodes)))
        # We can't do **data, since the keys might be e.g. int instead of str.
        data = draw(node_data)
        graph.add_node(node)
        for key, value in data.items():
            graph.nodes[node][key] = value

        if connected:
            data = draw(edge_data)
            graph.add_edge(node, edge_to)
            for key, value in data.items():
                graph.edges[node, edge_to][key] = value

    # Now for the mess. The maximum number of edges possible depends on the
    # graph type. In addition, if it's a DiGraph, edge [a, b] != [b, a]; but if
    # it's a "normal" graph [a, b] == [b, a]. It becomes slightly worse, since
    # DiGraph is a subclass of Graph.
    if isinstance(graph, nx.DiGraph):
        max_possible_edges = len(graph) * (len(graph) - 1)
    else:  # elif isinstance(graph, nx.Graph):
        max_possible_edges = (len(graph) * (len(graph) - 1))//2

    # Lastly, there's Multi(Di)Graphs, which can make an infinite number of
    # edges. We'll keep it as a numeric value for now.
    if isinstance(graph, nx.MultiGraph):
        max_possible_edges = float('inf')

    # And if we can make self-loops we get a few more. Note that the edge
    # (1, 1) is the same as the edge (1, 1), even in a DiGraph.
    if self_loops:
        max_possible_edges += len(graph)
    # Correct for the edges we added earlier and clamp to the range
    # (0, max_possible_edges)
    if max_edges is None:
        max_edges = max_possible_edges - len(graph.edges)
    else:
        max_edges = max_edges - len(graph.edges)

    if max_edges > max_possible_edges:
        max_edges = max_possible_edges
    elif max_edges < 0:
        max_edges = 0

    min_edges = min_edges - len(graph.edges)
    if min_edges < 0:
        min_edges = 0
    elif min_edges > max_edges:
        min_edges = max_edges

    if max_edges == float('inf'):
        max_edges = None

    available_edges = list(nx.non_edges(graph))
    if self_loops:
        available_edges.extend((n, n) for n in graph.nodes if not graph.has_edge(n, n))

    edges_to_add = draw(st.integers(min_value=min_edges, max_value=max_edges))

    for _ in range(edges_to_add):
        node_pair = draw(st.sampled_from(available_edges))
        available_edges.remove(node_pair)
        data = draw(edge_data)
        graph.add_edge(*node_pair)
        for key, value in data.items():
                graph.edges[node_pair][key] = value

    return graph
