"""
Door-based alignment between two 3DGS modules.

Given four corner points of a door from two separate spaces (Module and Base Map),
compute the rigid transformation (R, t) that maps Module space into Base Map space.

Corner labeling convention (clockwise from top-left when facing the door):
    1---2
    |   |
    4---3

Because the two spaces face the door from opposite sides, left/right is mirrored:
    Module  -> Base Map
    1       -> 2
    2       -> 1
    3       -> 4
    4       -> 3

The returned 4x4 matrix T satisfies:
    p_basemap = T @ p_module   (homogeneous coordinates)
"""

import numpy as np


def _make_frame(corners: np.ndarray) -> np.ndarray:
    """
    Build a 4x4 rigid frame from coplanar door corners.

    The frame origin is placed at c1 (top-left corner), with axes:
        u = normalize(c2 - c1)   horizontal (→)
        v = normalize(c4 - c1)   vertical   (↓)
        n = cross(u, v)           normal out of the door surface

    Args:
        corners: (4, 3) corners ordered [c1, c2, c3, c4]
        c1, c2, c3, c4: (3,) corner points in world coord

    Returns:
        F: (4, 4) homogeneous frame matrix  [u | v | n | origin]
    """
    c1, c2, _, c4 = corners
    u = c2 - c1;  u = u / np.linalg.norm(u)
    v = c4 - c1;  v = v / np.linalg.norm(v)
    n = np.cross(u, v)

    F = np.eye(4)
    F[:3, 0] = u
    F[:3, 1] = v
    F[:3, 2] = n
    F[:3, 3] = c1
    # F: [c1을 원점으로 하는 로컬 좌표계] -> [월드 좌표계]

    return F


def matrix_module2basemap(corners_module: np.ndarray, corners_basemap: np.ndarray) -> np.ndarray:
    """
    Compute the 4x4 transformation that aligns a Module into Base Map space.

    T = F_basemap @ S @ inv(F_module)

    S = diag(sw, sh, sn, 1)  — 로컬 프레임의 u/v/n 축별 스케일
        sw = w_basemap / w_module   (가로)
        sh = h_basemap / h_module   (세로)
        sn = (sw + sh) / 2          (법선, 산술평균)

    Args:
        corners_module:  (4, 3) [c1, c2, c3, c4], clockwise from top-left
        corners_basemap: (4, 3) [c1, c2, c3, c4], clockwise from top-left

    Returns:
        T: (4, 4) homogeneous transformation matrix
    """
    corners_module  = np.asarray(corners_module,  dtype=np.float64)
    corners_basemap = np.asarray(corners_basemap, dtype=np.float64)

    assert corners_module.shape  == (4, 3), "corners_module must be (4, 3)"
    assert corners_basemap.shape == (4, 3), "corners_basemap must be (4, 3)"

    corners_basemap_matched = corners_basemap[[1, 0, 3, 2]]

    sw = np.linalg.norm(corners_basemap_matched[1] - corners_basemap_matched[0]) \
       / np.linalg.norm(corners_module[1] - corners_module[0])
    sh = np.linalg.norm(corners_basemap_matched[3] - corners_basemap_matched[0]) \
       / np.linalg.norm(corners_module[3] - corners_module[0])
    sn = np.sqrt(sw * sh)

    F_module  = _make_frame(corners_module)
    F_basemap = _make_frame(corners_basemap_matched)

    R_m = F_module[:3, :3]
    t_m = F_module[:3, 3]
    F_module_inv = np.eye(4)
    F_module_inv[:3, :3] = R_m.T
    F_module_inv[:3,  3] = -R_m.T @ t_m

    S = np.diag([sw, sh, sn, 1.0]) # 모듈과 베이스맵의 스케일 차이 보정

    return F_basemap @ S @ F_module_inv


def apply_transform(T: np.ndarray, points: np.ndarray) -> np.ndarray:
    """
    Apply a 4x4 homogeneous transformation to an (N, 3) point array.

    Args:
        points: (N, 3) array of 3D points
        T:      (4, 4) transformation matrix

    Returns:
        (N, 3) transformed points
    """
    points = np.asarray(points, dtype=np.float64)
    # 예: 점이 2개라면
    # [[x1, y1, z1],
    #  [x2, y2, z2]]
    ones = np.ones((len(points), 1))            
    # len(points)는 전달받은 points의 개수 (몇개의 점을 행렬변환할지)
    # [[ 1. ],
    #  [ 1. ]]                                       
    points_h = np.hstack([points, ones])
    # [[x1, y1, z1, 1],
    #  [x2, y2, z2, 1]]
    transformed_h = (T @ points_h.T).T
    # [T @ [x1, y1, z1, 1].T,
    #  T @ [x2, y2, z2, 1].T].T

    return transformed_h[:, :3]


if __name__ == "__main__":

    module_corners = np.array([
        [0.0, 2.0, 0.0],   # c1 top-left
        [1.0, 2.0, 0.0],   # c2 top-right
        [1.0, 0.0, 0.0],   # c3 bottom-right
        [0.0, 0.0, 0.0],   # c4 bottom-left
    ])

    # 이거 읽어보기!!!!!!!!!!!
    R_gt = np.array([
        [-1,  0,  0],
        [ 0,  1,  0],
        [ 0,  0, -1],
    ], dtype=float)
    t_gt = np.array([5.0, 0.0, 0.0])

    basemap_corners_raw = (R_gt @ module_corners.T).T + t_gt 
    basemap_corners = basemap_corners_raw[[1, 0, 3, 2]]

    T = matrix_module2basemap(module_corners, basemap_corners)
    print("module2basemap transform:\n", np.round(T, 6))

    transformed = apply_transform(T, module_corners)
    print("Module corners:")
    print(np.round(module_corners, 6))
    print("Transformed module corners:")
    print(np.round(transformed, 6))
    print("Error:")
    print(np.linalg.norm(transformed - basemap_corners_raw))


    # papapa