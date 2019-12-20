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
    node_data: `hypothesis.SearchStrategy[dict]`
        The strategy to use to generate node attributes. Must generate a
        mapping.
    edge_data: `hypothesis.SearchStrategy[dict]`
        The strategy to use to generate edge attributes. Must generate a
        mapping.
    node_keys: `hypothesis.SearchStrategy[collections.abc.Hashable]` or None
        The strategy to use to generate node keys. Must generate a Hashable. If
        `None`, node keys will be taken from range(0, number_of_nodes).
    min_nodes: int
        The minimum number of nodes that should be in the generated graph. Must
        be positive.
    max_nodes: int or None
        The maximum number of nodes that should be in the generated graph. Must
        be larger than `min_nodes`. `None` means no upper limit.
    min_edges: int
        The minimum number of edges that should be in the generated graph. Less
        edges may be added if the produced graph contains too few nodes.
    max_edges: int or None
        The maximum number of edges that should be in the generated graph.
        `None` means no upper limit. Note that if `connected` is True more edges
        may be added.
    graph_type: class
        The type of graph that should be created.
    self_loops: bool
        Whether self loops (edges between a node and itself) are allowed.
    connected: bool
        If `True`, the generated graph is guaranteed to be a single (weakly)
        connected component.

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
    is_multigraph = graph.is_multigraph()
    is_directed = graph.is_directed()

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
        # Shrink towards high index, so shrink to the path graph. Otherwise
        # it'll shrink to the star graph.
        initial_edges = [draw(st.tuples(st.integers(-(n_idx-1), 0).map(lambda x: -x),
                                        st.just(n_idx)))
                         for n_idx in range(1, len(graph))]
        graph.add_edges_from(initial_edges)

    # Now for the mess. The maximum number of edges possible depends on the
    # graph type.
    if not is_multigraph:
        # Multi(Di)Graphs can make an infinite number of edges. For everything
        # else we clamp the range to (0, max_possible_edges)
        max_possible_edges = len(graph) * (len(graph) - 1)
        if is_directed:
            max_possible_edges *= 2
        if self_loops:
            max_possible_edges += len(graph)
        if max_edges is None or max_edges > max_possible_edges:
            max_edges = max_possible_edges
    if max_edges is not None:
        # Correct for number of edges already made if graph is connected.
        # This may mean we added more edges than originally allowed.
        max_edges -= len(graph.edges)
    if max_edges < 0:
        max_edges = 0

    # Likewise for min_edges
    # We already added some edges, so subtract those.
    min_edges -= len(graph.edges)
    if min_edges < 0:
        min_edges = 0
    elif min_edges > max_edges:
        min_edges = max_edges

    def edge_filter(edge):
        """
        Helper function to decide whether the edge between idx and jdx can still
        be added to graph.
        """
        # <= because self loops
        idx, jdx = edge
        return ((not graph.has_edge(idx, jdx) or is_multigraph) and
                (idx <= jdx or is_directed) and
                (idx != jdx or self_loops))

    # We need to sample a number of items from options, these items are
    # possibly not unique. In addition, we need to draw the same number of
    # items from edge_data and associate the two. To top it off, uniqueness
    # is defined by the content of the first element of the tuple.
    edges = st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=len(graph) - 1),
            st.integers(min_value=0, max_value=len(graph) - 1),
        ).filter(edge_filter),
        unique=not is_multigraph,
        min_size=min_edges,
        max_size=max_edges
    )
    graph.add_edges_from(draw(edges))

    edge_datas = draw(st.lists(
        edge_data,
        min_size=len(graph.edges),
        max_size=len(graph.edges)
    ))
    for edge, data in zip(graph.edges, edge_datas):
        graph.edges[edge].update(data)

    if node_keys is not None:
        new_idxs = draw(st.sets(node_keys,
                                min_size=len(graph),
                                max_size=len(graph)))
        graph = nx.relabel_nodes(graph, dict(zip(list(graph), list(new_idxs))))

    return graph
