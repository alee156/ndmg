#!/usr/bin/env python

# Copyright 2016 NeuroData (http://neurodata.io)
#
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
#

# graph.py
# Created by Greg Kiar on 2016-01-27.
# Email: gkiar@jhu.edu

from __future__ import print_function

from itertools import combinations
from collections import defaultdict
import numpy as np
import networkx as nx
import nibabel as nb
import ndmg
import time


class graph(object):
    def __init__(self, N, rois, attr=None):
        """
        Initializes the graph with nodes corresponding to the number of ROIs

        **Positional Arguments:**

                N:
                    - Number of rois
                rois:
                    - Set of ROIs as either an array or niftii file)
                attr:
                    - Node or graph attributes. Can be a list. If 1 dimensional
                      will be interpretted as a graph attribute. If N
                      dimensional will be interpretted as node attributes. If
                      it is any other dimensional, it will be ignored.
        """
        self.N = N
        self.edge_dict = defaultdict(int)

        self.rois = nb.load(rois).get_data()
        n_ids = np.unique(self.rois)
        n_ids = n_ids[n_ids != 0]

        self.g = nx.Graph(name="Generated by NeuroData's MRI Graphs (ndmg)",
                          version=ndmg.version,
                          date=time.asctime(time.localtime()),
                          source="http://m2g.io",
                          region="brain",
                          sensor="Diffusion MRI",
                          ecount=0,
                          vcount=len(n_ids)
                          )
        print(self.g.graph)

        [self.g.add_node(ids) for ids in n_ids]
        pass

    def make_graph(self, streamlines, attr=None):
        """
        Takes streamlines and produces a graph

        **Positional Arguments:**

                streamlines:
                    - Fiber streamlines either file or array in a dipy EuDX
                      or compatible format.
        """
        nlines = np.shape(streamlines)[0]
        print("# of Streamlines: " + str(nlines))

        for idx, streamline in enumerate(streamlines):
            if (idx % int(nlines*0.05)) == 0:
                print(idx)

            points = np.round(streamline).astype(int)
            p = set()
            for point in points:
                try:
                    loc = self.rois[point[0], point[1], point[2]]
                except IndexError:
                    pass
                else:
                    pass

                if loc:
                    p.add(loc)

            edges = combinations(p, 2)
            for edge in edges:
                lst = tuple([int(node) for node in edge])
                self.edge_dict[tuple(sorted(lst))] += 1

        edge_list = [(k[0], k[1], v) for k, v in self.edge_dict.items()]
        self.g.add_weighted_edges_from(edge_list)
        pass

    def get_graph(self):
        """
        Returns the graph object created
        """
        try:
            return self.g
        except AttributeError:
            print("Error: the graph has not yet been defined.")
            pass

    def save_graph(self, graphname, fmt='gpickle'):
        """
        Saves the graph to disk

        **Positional Arguments:**

                graphname:
                    - Filename for the graph

        **Optional Arguments:**

                fmt:
                    - Output graph format
        """
        self.g.graph['ecount'] = nx.number_of_edges(self.g)
        if fmt == 'gpickle':
            nx.write_gpickle(self.g, graphname)
        elif fmt == 'graphml':
            nx.write_graphml(self.g, graphname)
        else:
            raise ValueError('graphml is the only format currently supported')
        pass

    def summary(self):
        """
        User friendly wrapping and display of graph properties
        """
        print("\n Graph Summary:")
        print(nx.info(self.g))
        pass
