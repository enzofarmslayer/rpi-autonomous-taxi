from dataclasses import dataclass
from typing import Tuple
import numpy as np
from scipy import ndimage
from enum import Enum, auto
from typing import Literal
import config

class ClusterType(Enum):
    CONTAINS_STOPLINE = auto()
    LEFT = auto()
    RIGHT = auto()
    IGNORE = auto()
    OK = auto()


@dataclass
class Cluster:
    id: int
    slice: Tuple[slice, slice]
    center_coords: Tuple[int, int]
    bbox: Tuple[int, int, int, int]
    pixel_count: int
    bbox_area: int
    ctype: ClusterType = ClusterType.OK


def find_clusters(binary):
    binary = np.asarray(binary)
    if binary.ndim != 2:
        raise ValueError("binary must be a 2D array")

    binary_mask = binary.astype(bool)
    structure = ndimage.generate_binary_structure(2, 1)

    # 1) Dilation (expand clusters to remove noise)
    grouped = ndimage.binary_dilation(binary_mask, structure=structure, iterations=config.DILATION_ITER_COUNT)

    # 2) CCL on the dilated image
    binary_labeled, num = ndimage.label(grouped, structure=structure)
    
    if num == 0:
        return np.zeros_like(binary_labeled, dtype=np.int32), []

    # 3) For each raw label, compute features using ORIGINAL mask
    slices = ndimage.find_objects(binary_labeled)
    final_labled_binary = np.zeros_like(binary_labeled, dtype=np.int32)
    final_clusters = []
    cluster_id_count = 1

    for slice_index, bbox in enumerate(slices, start=1):
        if bbox is None:
            continue

        # Get boolean mask for bounding box of current slice
        cluster_mask_bb = binary_labeled[bbox] == slice_index

        # Mask out 1s for cluster for counting
        orig_bb = binary_mask[bbox]
        cluster_mask_orig = cluster_mask_bb & orig_bb

        pixel_count = int(cluster_mask_orig.sum())
        if pixel_count < config.MIN_CLUSTER_ACTIVE_PX:
            continue
        
        h, w = cluster_mask_bb.shape
        bb_area = h * w

        # Reconstruct after passing criterias
        cluster = final_labled_binary[bbox]
        cluster[cluster_mask_bb] = cluster_id_count

        row_start, row_end = bbox[0].start, bbox[0].stop
        col_start, col_end = bbox[1].start, bbox[1].stop

        center_x = round(col_start + (col_end - col_start)/2)
        center_y = round(row_start + (row_end - row_start)/2)
        print((col_end, col_start))

        final_clusters.append(
            Cluster(
                id=cluster_id_count,
                slice=bbox,
                center_coords=(center_x, center_y),
                bbox=(row_start, row_end, col_start, col_end),
                pixel_count=pixel_count,
                bbox_area=bb_area
            )
        )
        cluster_id_count += 1

    return final_labled_binary.astype(np.int32), final_clusters


Method = Literal["left", "right", "center"]
def get_cluster_points(binary_labeled: np.ndarray, 
                       cluster: Cluster, 
                       method: Method) -> np.ndarray:
    
    if method not in ("left", "right", "center"):
        raise ValueError("method must be 'left', 'right', or 'center'")

    y_slice, x_slice = cluster.slice
    y_start = y_slice.start
    x_start = x_slice.start

    # Extract the binary mask for cluster
    mask_local = (binary_labeled[y_slice, x_slice] == cluster.id)

    points = []

    for local_row in range(mask_local.shape[0]):
        row_mask = mask_local[local_row, :]
        xs_in_row = np.where(row_mask)[0]

        if len(xs_in_row) == 0:
            continue  # skip empty rows

        global_y = y_start + local_row

        if method == "left":
            x_local = xs_in_row[0]
        elif method == "right":
            x_local = xs_in_row[-1]
        elif method == "center":
            x_local = int(np.mean(xs_in_row))

        global_x = x_start + x_local
        points.append([global_x, global_y])

    return np.array(points)
