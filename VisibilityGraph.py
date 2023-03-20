import json
import math

import matplotlib.pyplot as plt
import networkx as nx
from shapely.geometry import LineString, Polygon

from BST import BalancedBinarySearchTree, Node
from task_allocation import Utility


def on_segment(segment, w_i):
    x, y = w_i
    (x1, y1), (x2, y2) = segment
    # check if the point is on the line defined by the segment
    if (x - x1) * (y2 - y1) == (y - y1) * (x2 - x1):
        # check if the point is between the endpoints of the segment
        if (x1 < x < x2 or x2 < x < x1) and (y1 < y < y2 or y2 < y < y1):
            return True
    return False


def intersection(line1, line2, include_endpoints):
    x1, y1 = line1[0]
    x2, y2 = line1[1]
    x3, y3 = line2[0]
    x4, y4 = line2[1]
    denom = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
    if denom == 0:
        return None  # lines are parallel
    ua = ((x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)) / denom
    ub = ((x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)) / denom

    if include_endpoints:
        if not (0 <= ua <= 1 and 0 <= ub <= 1):  # Not including the endpoints
            return None  # intersection point is outside of line segments
    else:
        if not (0 < ua < 1 and 0 < ub < 1):  # Not including the endpoints
            return None  # intersection point is outside of line segments

    x = x1 + ua * (x2 - x1)
    y = y1 + ua * (y2 - y1)
    return (x, y)


def does_intersect(seg1, seg2, include_endpoints):
    x1, y1 = seg1[0]
    x2, y2 = seg1[1]
    x3, y3 = seg2[0]
    x4, y4 = seg2[1]

    dx1 = x2 - x1
    dy1 = y2 - y1
    dx2 = x4 - x3
    dy2 = y4 - y3

    det = dx1 * dy2 - dx2 * dy1

    if det == 0:
        return False

    t1 = (dx2 * (y1 - y3) - dy2 * (x1 - x3)) / det
    t2 = (dx1 * (y1 - y3) - dy1 * (x1 - x3)) / det
    if include_endpoints:
        if 0 <= t1 <= 1 and 0 <= t2 <= 1:
            return True
    else:
        if 0 < t1 < 1 and 0 < t2 < 1:
            return True
    return False


def inorder_traversal(current_node):
    if current_node:
        inorder_traversal(current_node.left_child)
        print(current_node)
        inorder_traversal(current_node.right_child)


def search_for_edge(root: Node, key):
    result = False
    if root is None or does_intersect(root.edge, key, True):
        return True
    else:
        result = search_for_edge(root.left_child, key) and search_for_edge(root.right_child, key)
    return result


def find_intersection_in_tree(edge, tree: BalancedBinarySearchTree):
    # TODO traverse the tree in order and find if any edges are intersecting!
    search_for_edge(tree.root, edge)
    return False


def visible_vertices(p, S):
    """returns a set of visible vertices from point
    Parameters
    ----------
    holes : Set of obstacles
    point : a point
    Returns
    ----------
    [(point, visible_vertex, weight), ...]

    """
    # initialize the BST and result list
    W = []
    T = BalancedBinarySearchTree()
    # sort the obstacle vertices by the angle from initial rho to the vertex
    # in the case of a draw use the distance to the vertex as a tie breaker

    # Define a custom key function to calculate the angle of each point
    def angle_to_point(point):
        x, y = point
        angle = math.atan2(y - p[1], x - p[0]) * 180 / math.pi
        distance = math.dist(point, p)
        return ((360 - angle) % 360, distance)

    # Find the initial intersections and store then in a balanced search tree in the order that they were intersected by the line rho
    # Initialize the half-line rho to be pointing in the positive x direction
    p_wi = (p, (p[0] + 10000000, 0))  # TODO make sure that this is enough
    for edge in S.edges():
        intersection_point = intersection(p_wi, edge, True)
        if intersection_point is not None:
            T.insert(0.0, math.dist(p, intersection_point), edge)

    # Sort the list of points based on their angle to the origin
    w_previous = None
    w_previous_visible = None
    for w_i in sorted(S.nodes, key=angle_to_point):
        T.pretty_print()
        if w_i == p:  # Do not check collision between the same nodes
            continue

        p_wi = (p, w_i)
        visible = is_visible(S, T, p_wi, w_previous, w_previous_visible, w_i)
        if visible:
            W.append((p, w_i))
            for edge in S.edges(w_i):  # the point have two edges
                for node in edge:
                    # only compare with the node which is not the common point
                    if node is not w_i:
                        angle, distance = angle_to_point(node)
                        if angle_to_point(w_i) <= angle_to_point(node):
                            # Edge is on the Clockwise side of w_i
                            T.insert(angle, distance, edge)
                        else:
                            # Edge is on the Counter-clockwise side of w_i
                            T.delete(angle, distance)

        w_previous = w_i
        w_previous_visible = visible
    T.pretty_print()

    return W


def is_visible(S, T, p_wi, w_previous, w_previous_visible, w_i):
    visible = True

    # If p_wi intersects any edges of the polygon which w_i is a part of do not check anything else
    polygon_nodes = list(nx.dfs_preorder_nodes(S, w_i))
    poly = Polygon(polygon_nodes)
    line = LineString(p_wi)
    visible = not line.crosses(poly)

    if visible:
        # If it is the first iteration or w_i-1 is not on the segment p_wi
        if w_previous is None or not on_segment(p_wi, w_previous):
            # search in T for the edge e in the leaftmost leaf
            e = T.find_min()
            if e is not None:
                visible = not does_intersect(p_wi, e.edge, include_endpoints=True)
        elif w_previous_visible:
            # TODO search T for an edge that intersects the segment (w_i-1, w_i)
            e = find_intersection_in_tree((w_previous, w_i), T)
            if e:
                visible = False
        else:
            visible = False
    return visible


def construct_graph(polygon: Polygon, holes: list):
    G = nx.Graph()
    for i in range(len(polygon.boundary.coords) - 1):
        node_from = polygon.boundary.coords[i]
        node_to = polygon.boundary.coords[i + 1]
        G.add_node(node_from, pos=node_from, type="border")
        G.add_node(node_to, pos=node_to, type="border")
        G.add_edge(polygon.boundary.coords[i], polygon.boundary.coords[i + 1], type="border")

    node_from = polygon.boundary.coords[-1]
    node_to = polygon.boundary.coords[len(polygon.boundary.coords) - 2]
    G.add_node(node_from, pos=node_from, type="border")
    G.add_node(node_to, pos=node_to, type="border")
    G.add_edge(polygon.boundary.coords[-1], polygon.boundary.coords[len(polygon.boundary.coords) - 2], type="border")

    for hole in holes:
        for i in range(len(hole.boundary.coords) - 1):
            node_from = hole.boundary.coords[i]
            node_to = hole.boundary.coords[i + 1]
            G.add_node(node_from, pos=node_from, type="obstacle")
            G.add_node(node_to, pos=node_to, type="obstacle")
            G.add_edge(hole.boundary.coords[i], hole.boundary.coords[i + 1], type="obstacle")

        node_from = hole.boundary.coords[-1]
        node_to = hole.boundary.coords[len(hole.boundary.coords) - 2]
        G.add_node(node_from, pos=node_from, type="obstacle")
        G.add_node(node_to, pos=node_to, type="obstacle")
        G.add_edge(hole.boundary.coords[-1], hole.boundary.coords[len(hole.boundary.coords) - 2], type="obstacle")
    return G


def visibility_graph(polygon: Polygon, holes: list):
    # Construct the graph
    G = construct_graph(polygon, holes)
    # Add all vertices and edges of the polygons to the graph
    print(polygon)
    print(holes)
    print("Polygon as a graph: ", G)
    # check for visibility in each of the vertices
    edges = []
    for v in G.nodes:
        edges.extend(visible_vertices(v, G))

    G.add_edges_from(edges)
    nx.draw(G, nx.get_node_attributes(G, "pos"), with_labels=True)
    plt.show()


def naive_visibility_graph(polygon: Polygon, holes: list):
    # Create a NetworkX graph to represent the visibility graph
    visibility_graph = nx.Graph()
    visibility_graph = construct_graph(polygon, holes)

    for u in visibility_graph.nodes:
        for v in visibility_graph.nodes:
            if u == v:
                continue
            line = LineString([u, v])
            intersects_obstacle = False
            for obstacle in holes:
                if line.crosses(obstacle) or line.within(obstacle):
                    intersects_obstacle = True
                    break
            if not intersects_obstacle:
                visibility_graph.add_edge(u, v)
    print(visibility_graph)

    nx.draw(visibility_graph, nx.get_node_attributes(visibility_graph, "pos"), with_labels=True)
    plt.show()


if __name__ == "__main__":
    naive_visibility_graph(
        Polygon([(0, 0), (0, 10), (10, 12), (10, 0)]),
        [
            Polygon([(2, 2), (4, 2), (4, 4), (2, 4)]),
            Polygon([(6, 2), (7, 2), (7, 7), (6, 7)]),
        ],
    )
    # main()

    # dataset_name = "AC300"

    # files = Utility.getAllCoverageFiles(dataset_name)

    # for file_name in files:
    #     with open(file_name) as json_file:
    #         data = json.load(json_file)
    #     visibility_graph(data["polygon"], data["holes"])
    #     break
    #     break
    #     break
