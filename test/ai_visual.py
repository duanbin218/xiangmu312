# -*- coding: utf-8 -*-
# 可视化逻辑从 ai算法 拆出，避免核心算法强依赖 OpenCV。

from typing import Tuple, Optional, List
import numpy as np
import cv2
import ai算法 as core  # 可视化依赖核心算法，但不反向依赖，避免循环引用。


def _make_grid_vis(grid: np.ndarray, cell_size: int, line_color=(200, 200, 200)):
    """
    生成放大后的网格底图，并统一绘制网格线。
    """
    if grid.dtype != np.uint8 or grid.ndim != 3 or grid.shape[2] != 3:
        raise ValueError("grid 必须是 HxWx3 的 uint8 BGR")

    h, w, _ = grid.shape

    # 用最近邻插值放大，避免颜色被模糊
    vis = cv2.resize(
        grid, (w * cell_size, h * cell_size),
        interpolation=cv2.INTER_NEAREST
    )

    _draw_grid_lines(vis, w, h, cell_size, line_color)
    return vis, h, w


def _draw_grid_lines(vis: np.ndarray, width: int, height: int, cell_size: int, line_color):
    """
    绘制网格线，便于多处可视化复用样式。
    """
    for x in range(width + 1):
        px = x * cell_size
        cv2.line(vis, (px, 0), (px, height * cell_size), line_color, 1)
    for y in range(height + 1):
        py = y * cell_size
        cv2.line(vis, (0, py), (width * cell_size, py), line_color, 1)


def _draw_text_with_outline(
    img: np.ndarray,
    text: str,
    org,
    font=cv2.FONT_HERSHEY_SIMPLEX,
    font_scale: float = 0.45,
    color=(255, 255, 255),
    outline_color=(0, 0, 0),
    thickness: int = 1,
    outline_thickness: int = 2,
):
    """
    文本描边绘制，统一样式避免多处重复调用。
    """
    cv2.putText(img, text, org, font, font_scale, outline_color, outline_thickness, cv2.LINE_AA)
    cv2.putText(img, text, org, font, font_scale, color, thickness, cv2.LINE_AA)


# =====================  可视化放大图像显示路径点  =====================
def visualize_grid_and_path(
    grid: np.ndarray,
    path: Optional[List[Tuple[int, int]]],
    win_name: str = "A* path",
    cell_size: int = 30,
):
    """
    用 OpenCV 把小网格放大显示，并把路径画出来。

    grid: HxWx3, uint8, BGR
    path: [(x,y), ...]，a_star_eight 的返回结果
    cell_size: 每个格子放大成多少像素
    """
    vis, h, w = _make_grid_vis(grid, cell_size)

    if path:
        # 画路径：红色线 + 点，起点绿，终点蓝
        path_color = (0, 0, 255)      # 红
        start_color = (0, 255, 0)     # 绿
        end_color = (255, 0, 0)       # 蓝

        pts = []
        for (x, y) in path:
            cx = int(x * cell_size + cell_size / 2)
            cy = int(y * cell_size + cell_size / 2)
            pts.append((cx, cy))

        for i in range(1, len(pts)):
            cv2.line(vis, pts[i - 1], pts[i], path_color, 1)

        cv2.circle(vis, pts[0], radius=cell_size // 3, color=start_color, thickness=-1)
        cv2.circle(vis, pts[-1], radius=cell_size // 3, color=end_color, thickness=-1)
    else:
        cv2.putText(
            vis, "NO PATH", (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2, cv2.LINE_AA
        )

    cv2.imshow(win_name, vis)


# =====================  先放大图像,在放大后的图像上绘制点  =====================
def visualize_grid_and_point(
    grid: np.ndarray,
    point: Tuple,
    win_name: str = "A* path",
    cell_size: int = 30,
):
    vis, h, w = _make_grid_vis(grid, cell_size)

    if point is not None:
        point_color = (0, 0, 255)  # 红
        gx, gy = point  # 这里假设 point=(x, y) = (列, 行)
        # 把格子坐标转成放大后图像的像素坐标（格子中心）
        cx = gx * cell_size + cell_size // 2
        cy = gy * cell_size + cell_size // 2
        cv2.circle(vis, (cx, cy), radius=cell_size // 3, color=point_color, thickness=-1)
    else:
        print("传入的坐标点为None")

    cv2.imshow(win_name, vis)
    return vis


# =====================  可视化放大显示地图上的出发点/中心点/怪物点/网格风险值/每个点的范围  =====================
def visualize_move(
    grid: np.ndarray,
    a_pos: Tuple[int, int],
    target: Optional[Tuple[int, int]],
    search_center: Optional[Tuple[int, int]] = None,
    search_radius: Optional[int] = None,
    show_risk: bool = True,
    scale: int = 28,
    window: str = "move_viz",
    outfile: str = "viz_demo.png",
):
    """
    将grid网格放大显示,绘制风险热力图,人物点、安全可达目标点、敌人位置、敌人攻击范围、搜索中心、搜索半径、标识每个网格风险权重值
    :param grid: np图像
    :param a_pos: 人物坐标
    :param target: 目标点坐标
    :param search_center: 搜索中心
    :param search_radius: 搜索半径
    :param show_risk：网格是否叠加风险权重
    :param scale: 网格放大倍数
    :param window：图像显示窗口的名称
    :param outfile：图像不能显示时，图像保存的名称
    """
    H, W, _ = grid.shape
    enemies = core._parse_enemies(grid)
    risk = core._compute_risk(grid, enemies)
    # 基底图：放大（保持像素块）
    base = cv2.resize(grid, (W * scale, H * scale), interpolation=cv2.INTER_NEAREST)

    # 叠加风险热力图
    if show_risk and risk.max() > 0:
        rn = (risk.astype(np.float32) / risk.max() * 255.0).astype(np.uint8)
        rn_big = cv2.resize(rn, (W * scale, H * scale), interpolation=cv2.INTER_NEAREST)
        heat = cv2.applyColorMap(rn_big, cv2.COLORMAP_JET)
        vis = cv2.addWeighted(base, 0.55, heat, 0.45, 0.0)
    else:
        vis = base.copy()

    # 画网格线（可视化样式统一）
    _draw_grid_lines(vis, W, H, scale, (180, 180, 180))

    # 绘制敌人 + “切比雪夫半径方框”
    for (xe, ye), r, w in enemies:
        color = (0, 0, 255) if w == 3 else (0, 255, 0)  # 红 or 绿
        center_px = (xe * scale + scale // 2, ye * scale + scale // 2)
        cv2.circle(vis, center_px, max(2, scale // 3), color, -1)
        # 切比雪夫半径 → 方形包围（像素对齐）
        tl = (max(0, xe - r) * scale, max(0, ye - r) * scale)
        br = (min(W - 1, xe + r) * scale + (scale - 1), min(H - 1, ye + r) * scale + (scale - 1))
        cv2.rectangle(vis, tl, br, color, 2)
        _draw_text_with_outline(
            vis,
            f"E{(int(xe), int(ye))}",
            (xe * scale + 3, ye * scale + 14),
        )

    # 绘制搜索中心点 + 搜索半径（方框）
    if search_center is None:
        search_center = a_pos
    cx, cy = search_center
    if search_radius is not None and search_radius >= 0:
        tl = (max(0, cx - search_radius) * scale, max(0, cy - search_radius) * scale)
        br = (min(W - 1, cx + search_radius) * scale + (scale - 1),
              min(H - 1, cy + search_radius) * scale + (scale - 1))
        cv2.rectangle(vis, tl, br, (255, 0, 255), 2)
    search_center_b = (cx * scale + scale // 2, cy * scale + scale // 2)
    cv2.circle(vis, search_center_b, max(3, scale // 3), (255, 255, 0), -1)
    _draw_text_with_outline(
        vis,
        f"C{search_center}",
        (cx * scale + 3, cy * scale + 14),
    )

    # 绘制 人物a 点（青色）与 T目的地坐标（黄色）
    ax, ay = a_pos
    a_center = (ax * scale + scale // 2, ay * scale + scale // 2)

    if target is not None:
        tx, ty = target
        t_center = (tx * scale + scale // 2, ty * scale + scale // 2)
        cv2.circle(vis, t_center, max(3, scale // 3), (0, 255, 255), -1)
        cv2.line(vis, a_center, t_center, (0, 0, 0), 3)
        cv2.line(vis, a_center, t_center, (0, 255, 255), 2)
        _draw_text_with_outline(
            vis,
            f"T{(int(tx), int(ty))}",
            (tx * scale + 3, ty * scale + 14),
            color=(0, 255, 255),
        )
    cv2.circle(vis, a_center, max(2, scale // 4), (255, 255, 255), -1)
    _draw_text_with_outline(
        vis,
        f"P{a_pos}",
        (ax * scale + 3, ay * scale + scale - 6),
    )

    try:
        cv2.imshow(window, vis)
    except Exception:
        cv2.imwrite(outfile, vis)
        print(f"[info] GUI 不可用，已保存到: {outfile}")


# =====================  Demo：可视化样例  =====================
def _demo_visual(grid: np.ndarray):
    a = (3, 0)
    target = core.next_move_a(a, grid, search_center=(5, 7), search_radius=3)
    print(f"A={a}, target={target}")  # 如果 target 为 None，可能出发点被填充为障碍点
    visualize_move(
        grid, a, target,
        search_center=(5, 7), search_radius=3,
        show_risk=True, scale=55, window="demo_case",
        outfile="viz_demo.png"
    )
