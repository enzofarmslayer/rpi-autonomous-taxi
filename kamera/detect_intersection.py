from typing import List
import numpy as np
from scipy import ndimage
from cluster import Cluster, ClusterType

"""
To be classified as (3-way) intersection, three criterias needs to be met:
1.  Binary mass-center is skewed upwards and towards the lane.
2.  Bounding box of opposite line does not exceed a prespecified 
    max value AND endpoints are in opposite corners.
3.  The above is true for two consecutive frames.
"""

MIN_COM_OFFSET_X = 0.10
MIN_COM_OFFSET_Y = -0.01
MAX_WIDTH_STRAIGHT = 140
MIN_SPACING_STRAIGHT = 0.6

DEBUG = True

def scan_for_intersection(binary_labeled: np.ndarray, 
                          clusters: List[Cluster]) -> Cluster:
    """ If intersection: return cluster who form the inside of the intersection """
    clusters_to_check = [cl for cl in clusters if cl.ctype != ClusterType.IGNORE]
    if len(clusters_to_check) != 2: return False

    # Get indices for clusters who pass criteria 2
    straight_candidates = [i for i, cl in enumerate(clusters_to_check) if 
                           _does_not_exceed_max_width(cl) and 
                           _endspoints_in_opposite_corners(binary_labeled, cl)]

    if DEBUG:
        msg = "Straight candidates:"
        for cand in straight_candidates:
            msg += " " + str(clusters_to_check[cand].ctype)
        print(msg)

    # Now check if opposite forms a curve according to critera 1
    for cl_index in straight_candidates:
        opp_cl = clusters_to_check[1-cl_index]
        opp_cl_binary = binary_labeled[opp_cl.slice]
        if DEBUG:
            print("Checking candidate: ", str(opp_cl.ctype))
        if passes_com_offeset_criteria(opp_cl_binary, opp_cl.ctype):
            return opp_cl
    
    return None

    
def _does_not_exceed_max_width(cl: Cluster) -> bool:
    width = cl.bbox[3] - cl.bbox[2]
    return width < MAX_WIDTH_STRAIGHT

def _endspoints_in_opposite_corners(binary_labeled: np.ndarray, 
                                    cl: Cluster) -> bool:
    cluster_labled = binary_labeled[cl.slice]
    h, w = cluster_labled.shape

    top_slice = cluster_labled[0:round(0.1*h), :]
    bottom_slice = cluster_labled[round(0.9*h):h, :]

    _, top_com_x = ndimage.center_of_mass(top_slice)
    _, bottom_com_x = ndimage.center_of_mass(bottom_slice)

    space = abs(top_com_x-bottom_com_x)/w
    return space > MIN_SPACING_STRAIGHT


def passes_com_offeset_criteria(cluster_binary: np.ndarray, cluster_type: ClusterType):
    """ True if center of mass as a relative offset from bouding box center is greater than required. """
    max_y, max_x = (d // 2 for d in cluster_binary.shape)
    y, x = ndimage.center_of_mass(cluster_binary)
    rel_offset_x = (max_x - x)/max_x
    rel_offset_y = (max_y - y)/max_y
    
    # Lane center opposite direction if left
    if cluster_type == ClusterType.LEFT:
         rel_offset_x *= -1

    if DEBUG:
        print(f"Offsets: {rel_offset_x:.2f} {rel_offset_y:.2f}")

    if (rel_offset_x > MIN_COM_OFFSET_X and rel_offset_y > MIN_COM_OFFSET_Y):
        return True

    return False
