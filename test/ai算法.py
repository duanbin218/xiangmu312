from typing import Tuple, Optional, List
from collections import deque
import numpy as np
import cv2
import math
import heapq
import config  # 颜色协议集中在 config，避免算法与绘制不一致。

# <计算出风险值最小的安全点>↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓

# 8 邻域偏移量，用于可达性 BFS
_EIGHT_DIRECTIONS = (
    (-1, -1), (0, -1), (1, -1),
    (-1, 0),           (1, 0),
    (-1, 1),  (0, 1),  (1, 1),
)

def _cheb(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

def _clamp_center(center: Tuple[int, int], w: int, h: int) -> Tuple[int, int]:
    x = min(max(center[0], 0), w - 1)
    y = min(max(center[1], 0), h - 1)
    return x, y

def _parse_enemies(grid: np.ndarray):
    H, W, _ = grid.shape
    # 颜色协议从 config 读取，保证绘制/算法一致，避免风险计算失真。
    sb, sg, sr = config.ENEMY_COLOR_S
    ab, ag, ar = config.ENEMY_COLOR_A
    bb, bg, br = config.ENEMY_COLOR_B
    pb, pg, pr = config.PLAYER_COLOR
    S_mask = (grid[:, :, 2] == sr) & (grid[:, :, 1] == sg) & (grid[:, :, 0] == sb)
    A_mask = (grid[:, :, 2] == ar) & (grid[:, :, 1] == ag) & (grid[:, :, 0] == ab)
    B_mask = (grid[:, :, 2] == br) & (grid[:, :, 1] == bg) & (grid[:, :, 0] == bb)
    P_mask = (grid[:, :, 2] == pr) & (grid[:, :, 1] == pg) & (grid[:, :, 0] == pb)

    enemies: List[Tuple[Tuple[int, int], int, int]] = []

    ys, xs = np.where(S_mask)
    for y, x in zip(ys, xs):
        r = int(grid[y, x, 0])  # B 通道：半径
        w = int(grid[y, x, 1])  # G 通道：权重
        enemies.append(((x, y), r, w))

    ys, xs = np.where(A_mask)
    for y, x in zip(ys, xs):
        r = int(grid[y, x, 0])
        w = int(grid[y, x, 1])
        enemies.append(((x, y), r, w))

    ys, xs = np.where(B_mask)
    for y, x in zip(ys, xs):
        r = int(grid[y, x, 0])
        w = int(grid[y, x, 1])
        enemies.append(((x, y), r, w))

    ys, xs = np.where(P_mask)
    for y, x in zip(ys, xs):
        r = int(grid[y, x, 0])
        w = int(grid[y, x, 1])
        enemies.append(((x, y), r, w))

    return enemies

def _compute_risk(grid: np.ndarray, enemies) -> np.ndarray:
    H, W, _ = grid.shape
    risk = np.zeros((H, W), dtype=np.int32)
    for (xe, ye), r, w in enemies:
        x0, x1 = max(0, xe - r), min(W - 1, xe + r)
        y0, y1 = max(0, ye - r), min(H - 1, ye + r)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                d = max(abs(x - xe), abs(y - ye))
                if d <= r:
                    # 按 (r - d + 1) 阶梯增加风险权重
                    risk[y, x] += w * (r - d + 1)
                    # 如果你只想在半径内加一个固定权重，改成：
                    # risk[y, x] += w
    return risk

def _bfs_reachable(
    start: Tuple[int, int],
    walkable: np.ndarray,
    domain: np.ndarray,
) -> np.ndarray:
    """
    使用 8 邻域 BFS 在 walkable 与 domain 的交集内扩张, 生成从 start 可达的布尔掩码。
    """
    H, W = walkable.shape
    reachable = np.zeros((H, W), dtype=bool)
    sx, sy = start
    if not (0 <= sx < W and 0 <= sy < H):
        return reachable
    if not (walkable[sy, sx] and domain[sy, sx]):
        return reachable

    queue = deque([(sx, sy)])
    reachable[sy, sx] = True
    while queue:
        x, y = queue.popleft()
        for dx, dy in _EIGHT_DIRECTIONS:
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H and not reachable[ny, nx]:
                if walkable[ny, nx] and domain[ny, nx]:
                    reachable[ny, nx] = True
                    queue.append((nx, ny))
    return reachable


# =====================  核心计算：在“局部小地图”上跑  =====================

def _next_move_core(
    a_pos: Tuple[int, int],
    grid: np.ndarray,
    search_center: Optional[Tuple[int, int]] = None,
    search_radius: Optional[int] = None,
    selection_method: int = 0,
    players: Optional[List[Tuple[int, int]]] = None,  # 多玩家坐标列表（与 a_pos 同一坐标系）
    escape_mode: str = "free",                        # "free/away/left/right/toward"
) -> Optional[Tuple[int, int]]:
    """
    在当前 grid（可以是整图，也可以是裁剪后的 sub_grid）上，
    计算风险最小的安全点。

    players: 多个玩家的坐标列表（地图坐标），用于计算“合成逃跑方向”.
    escape_mode:
        - "free"   : 不限制方向
        - "away"   : 朝玩家们的合成相反方向逃（默认想要的）
        - "toward" : 朝玩家们方向靠近（一般用不到）
        - "left"   : 绕在玩家们的“左侧”
        - "right"  : 绕在玩家们的“右侧”
    """
    # ===== 参数检查 =====
    if selection_method not in (0, 1):
        raise ValueError('请输入安全点的选择方式,"0或者1"')

    if not isinstance(grid, np.ndarray) or grid.ndim != 3 or grid.shape[2] != 3 or grid.dtype != np.uint8:
        raise ValueError("grid 必须是 uint8 的 (H,W,3) BGR 数组")

    H, W, _ = grid.shape

    ax, ay = a_pos
    if not (0 <= ax < W and 0 <= ay < H):
        raise ValueError("a_pos 越界。")

    # ===== 搜索中心 =====
    if search_center is None:
        cx, cy = ax, ay
    else:
        cx, cy = _clamp_center(search_center, W, H)

    # ===== 敌人 & 风险图 =====
    enemies = _parse_enemies(grid)
    if enemies:
        risk = _compute_risk(grid, enemies)
    else:
        risk = np.zeros((H, W), dtype=np.int32)

    # 如果人物当前格子没风险，就没必要动
    if risk[ay, ax] == 0:
        return (ax, ay)

    # ===== 可通行区域 =====
    walkable = (grid[:, :, 0] == 255) & (grid[:, :, 1] == 255) & (grid[:, :, 2] == 255)

    # ===== 搜索域 domain：只在 search_radius 附近找候选点 =====
    if search_radius is None:
        domain = np.ones((H, W), dtype=bool)
    else:
        domain = np.zeros((H, W), dtype=bool)
        x0, x1 = max(0, cx - search_radius), min(W - 1, cx + search_radius)
        y0, y1 = max(0, cy - search_radius), min(H - 1, cy + search_radius)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if _cheb((x, y), (cx, cy)) <= search_radius:
                    domain[y, x] = True

    # 确保起点在 domain 内（方便 BFS 起跳）
    if not domain[ay, ax]:
        domain[ay, ax] = True

    # ===== 候选点：可通行 + 在搜索域内 =====
    candidates = np.argwhere(walkable & domain)
    if candidates.size == 0:
        return None

    # ===== 可达性（在当前 grid 内）=====
    reachable = _bfs_reachable((ax, ay), walkable, walkable)

    # ===== 敌人距离（按需计算）=====
    def _nearest_enemy_dist(x: int, y: int) -> int:
        if not enemies:
            return 10**9
        return min(
            _cheb((x, y), (xe, ye))
            for (xe, ye), _, _ in enemies
        )

    # ===== 多玩家合成方向向量 =====
    def _group_direction() -> Optional[Tuple[float, float]]:
        """
        返回 v = group->me 的合成向量 (vx, vy)，用于决定逃跑方向。
        """
        if not players:
            return None

        vx_total = 0.0
        vy_total = 0.0
        count = 0

        for (px, py) in players:
            dx = ax - px
            dy = ay - py
            # 玩家和人物重合 / 极近 -> 忽略方向
            if dx == 0 and dy == 0:
                continue
            # 用 Chebyshev 距离近的玩家权重更大
            d = max(abs(dx), abs(dy))
            if d == 0:
                continue
            weight = 1.0 / d    # 越近权重越大
            vx_total += dx * weight
            vy_total += dy * weight
            count += 1

        if count == 0:
            return None

        # 如果合成向量很小，说明玩家分布比较对称，方向不明显
        if abs(vx_total) < 1e-3 and abs(vy_total) < 1e-3:
            return None

        return vx_total, vy_total

    group_dir = _group_direction()

    # ===== 方向过滤器 =====
    def _direction_ok(x: int, y: int) -> bool:
        """
        根据 players 的合成方向和 escape_mode 判断 (x,y) 是否是“允许的躲避方向”
        """
        if escape_mode == "free" or group_dir is None:
            return True

        vx, vy = group_dir  # threat_group -> me 的合成向量
        wx = x - ax         # me -> candidate
        wy = y - ay

        if wx == 0 and wy == 0:
            return True

        dot = vx * wx + vy * wy
        cross = vx * wy - vy * wx

        if escape_mode == "away":
            # 要求候选点在“远离玩家群”的半平面
            return dot > 0
        elif escape_mode == "toward":
            # 反过来，朝玩家群靠近（一般不用）
            return dot < 0
        elif escape_mode == "left":
            # 在 group->me 向量的左侧
            return cross > 0
        elif escape_mode == "right":
            # 在 group->me 向量的右侧
            return cross < 0
        else:
            # 未知模式，当 free 处理
            return True

    # ===== 拆分候选：方向合适 vs 仅可达（排除当前格） =====
    dir_ok_list: List[Tuple[int, int]] = []
    all_ok_list: List[Tuple[int, int]] = []

    for y, x in candidates:
        if not reachable[y, x]:
            continue

        # ★ 当前格风险>0时，不把当前格纳入候选 ★
        # 能走到这里说明 risk[ay, ax] > 0（前面 risk==0 已经 return）
        if x == ax and y == ay:
            continue

        all_ok_list.append((y, x))

        if _direction_ok(x, y):
            dir_ok_list.append((y, x))

    # ===== 兜底 1：除当前格外没有任何可达格子 =====
    if not all_ok_list:
        print("next_move_a: 除当前格外无任何可达格子，返回当前点作为兜底")
        return (ax, ay)

    # 优先用“方向合适”的点；没有就退回“所有可达点”
    eval_list = dir_ok_list if dir_ok_list else all_ok_list
    if not eval_list:
        # 正常逻辑不会到这里（上面对 all_ok_list 已经做了非空判断）
        return (ax, ay)

    # ===== 按原来的规则，从 eval_list 中选最优点 =====
    best = None
    best_key = None

    if selection_method == 0:
        # 0：优先离敌人远
        for y, x in eval_list:
            d_enemy = _nearest_enemy_dist(x, y)
            key = (
                int(risk[y, x]),              # 1) 风险越小越好
                -int(d_enemy),                # 2) 离最近敌人越远越好
                _cheb((x, y), (ax, ay)),      # 3) 离人物越近越好
                y,
                x,
            )
            if best_key is None or key < best_key:
                best_key = key
                best = (x, y)
    else:
        # 1：优先离人物近
        for y, x in eval_list:
            d_enemy = _nearest_enemy_dist(x, y)
            key = (
                int(risk[y, x]),
                _cheb((x, y), (ax, ay)),      # 离人物越近
                -int(d_enemy),                # 再考虑离敌人远
                y,
                x,
            )
            if best_key is None or key < best_key:
                best_key = key
                best = (x, y)

    print('局部安全点坐标(局部/当前坐标系):', best)
    return best


# =====================  包装器：在大地图上裁剪局部再调用 core  =====================

def next_move_a(
    a_pos: Tuple[int, int],
    grid: np.ndarray,
    search_center: Optional[Tuple[int, int]] = None,
    search_radius: Optional[int] = None,
    selection_method: int = 0,
    *,
    use_local: bool = True,
    local_margin: int = 15,     # BFS 额外留出的绕路余量
    max_patch_size: int = 300,  # 局部 patch 最大宽/高，超过就退回“全图模式”
    players: Optional[List[Tuple[int, int]]] = None,  # 多个玩家坐标（全图坐标）
    escape_mode: str = "free",                         # "free/away/left/right/toward"
) -> Optional[Tuple[int, int]]:
    """
    大地图版 next_move_a：
    - 默认启用局部模式 use_local=True：
        只在以 search_center 为中心的一块小 patch 上跑计算，大幅降低耗时；
        然后把结果映射回原始 grid 坐标。
    - 如果 search_radius 为空，或者 patch 太大，就自动退回“全图模式”。
    :param a_pos: 当前人物坐标（全图坐标）
    :param grid: 整张地图的 (H,W,3) BGR
    :param search_center: 搜索中心（全图坐标），默认用人物坐标
    :param search_radius: 搜索半径（你说的 40 或 50）
    :param selection_method: 0/1 选择策略
    :param use_local: 是否启用局部裁剪优化
    :param local_margin: BFS 绕路余量
    :param max_patch_size: 局部 patch 的最大边长
    :param players: [(px,py), ...] 地图上所有需要考虑的玩家坐标（人类玩家），用于计算逃跑方向。
    :param escape_mode: 见 _next_move_core 注释。
    """
    if selection_method not in (0, 1):
        raise ValueError('请输入安全点的选择方式,"0或者1"')

    if not isinstance(grid, np.ndarray) or grid.ndim != 3 or grid.shape[2] != 3 or grid.dtype != np.uint8:
        raise ValueError("grid 必须是 uint8 的 (H,W,3) BGR 数组")

    H, W, _ = grid.shape
    ax, ay = a_pos
    if not (0 <= ax < W and 0 <= ay < H):
        raise ValueError("a_pos 越界。")

    # 搜索中心（全图坐标）
    if search_center is None:
        cx, cy = ax, ay
    else:
        cx, cy = _clamp_center(search_center, W, H)

    # ===== 不用局部模式 / 没有 search_radius：直接全图算 =====
    if (not use_local) or (search_radius is None):
        best = _next_move_core(
            (ax, ay),
            grid,
            (cx, cy),
            search_radius,
            selection_method,
            players=players,
            escape_mode=escape_mode,
        )
        print('安全点坐标(全图):', best)
        return best

    # ===== 先在全图上解析敌人，估一个最大半径 =====
    enemies_full = _parse_enemies(grid)
    max_enemy_radius = max((r for _, r, _ in enemies_full), default=0)

    # 搜索圆理论包围盒
    dom_x0 = cx - search_radius
    dom_x1 = cx + search_radius
    dom_y0 = cy - search_radius
    dom_y1 = cy + search_radius

    # full_margin = 敌人半径影响 + BFS 绕路余量
    full_margin = max_enemy_radius + local_margin

    # 目标 patch：同时覆盖
    # - 人物位置 a_pos
    # - 搜索圆的包围盒
    # 再向外扩 full_margin
    target_x_min = min(dom_x0, ax) - full_margin
    target_x_max = max(dom_x1, ax) + full_margin
    target_y_min = min(dom_y0, ay) - full_margin
    target_y_max = max(dom_y1, ay) + full_margin

    # 和整图范围做一次截断
    px0 = max(0, int(target_x_min))
    py0 = max(0, int(target_y_min))
    px1 = min(W - 1, int(target_x_max))
    py1 = min(H - 1, int(target_y_max))

    subW = px1 - px0 + 1
    subH = py1 - py0 + 1

    # patch 太大 -> 回退全图
    if subW > max_patch_size or subH > max_patch_size:
        print(f"next_move_a: 局部 patch 太大({subW}x{subH}), 回退到全图计算")
        best = _next_move_core(
            (ax, ay),
            grid,
            (cx, cy),
            search_radius,
            selection_method,
            players=players,
            escape_mode=escape_mode,
        )
        print('安全点坐标(全图):', best)
        return best

    # ===== 裁剪出局部 sub_grid =====
    sub_grid = grid[py0:py1 + 1, px0:px1 + 1]

    # 把人物位置和搜索中心映射到局部坐标系
    a_pos_sub = (ax - px0, ay - py0)
    search_center_sub = (cx - px0, cy - py0)

    # 把玩家坐标也映射到局部坐标系（只保留在 patch 内的）
    players_sub: Optional[List[Tuple[int, int]]] = None
    if players:
        tmp = []
        for (px, py) in players:
            if px0 <= px <= px1 and py0 <= py <= py1:
                tmp.append((px - px0, py - py0))
        players_sub = tmp if tmp else None

    # ===== 在局部小地图上跑“原来的算法 + 方向控制” =====
    best_local = _next_move_core(
        a_pos_sub,
        sub_grid,
        search_center_sub,
        search_radius,
        selection_method,
        players=players_sub,
        escape_mode=escape_mode,
    )

    if best_local is None:
        print("next_move_a: 局部搜索未找到可用安全点, 回退全图")
        best = _next_move_core(
            (ax, ay),
            grid,
            (cx, cy),
            search_radius,
            selection_method,
            players=players,
            escape_mode=escape_mode,
        )
        print('安全点坐标(全图):', best)
        return best

    bx, by = best_local

    # 映射回全图坐标
    global_best = (bx + px0, by + py0)
    print('安全点坐标(全图坐标系):', global_best)
    return global_best

# </计算出风险值最小的安全点>↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑




# <a星寻路优化算法,裁切部分地图进行a星,不会全图,提高计算效率>↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓

# =====================================
#  八方向移动（切比雪夫）
# =====================================
_EIGHT_DIRS: List[Tuple[int, int]] = [
    (1, 0), (-1, 0), (0, 1), (0, -1),
    (1, 1), (1, -1), (-1, 1), (-1, -1),
]


# =====================================
#  基础掩码：可走 / 障碍 / 敌人
# =====================================
def _build_masks(grid: np.ndarray):
    """
    grid: HxWx3, uint8, BGR

    颜色约定：
    - 可走：纯白 (255,255,255)
    - 障碍：纯黑 (0,0,0)
    - 敌人：其它非白非黑的颜色（比如 (3,1,255)、(1,1,128)）
      敌人格子本身视为不可走。
    """
    if grid.dtype != np.uint8 or grid.ndim != 3 or grid.shape[2] != 3:
        raise ValueError("grid 必须是 HxWx3 的 uint8 BGR 图")

    B = grid[:, :, 0]
    G = grid[:, :, 1]
    R = grid[:, :, 2]

    white = (B == 255) & (G == 255) & (R == 255)
    black = (B == 0) & (G == 0) & (R == 0)

    # 敌人：非白非黑 & 至少一个通道 > 0
    enemy = ~(white | black) & ((B > 0) | (G > 0) | (R > 0))

    walkable = white & (~enemy)      # 只能走白色格子
    obstacle = ~walkable             # 其它全部视为障碍（黑 + 敌人 + 杂色）

    return walkable, obstacle, enemy


# =====================================
#  多源 BFS：到最近障碍的切比雪夫距离
# =====================================
def _chebyshev_distance_transform(
    obstacle: np.ndarray,
    max_distance: int,
) -> np.ndarray:
    """
    多源 BFS，计算每个格子到最近“障碍/敌人”的切比雪夫距离（单位步）。
    obstacle: True 表示障碍/敌人/不可走
    """
    h, w = obstacle.shape
    max_distance = int(max(1, max_distance))
    INF = max_distance + 1

    dist = np.full((h, w), INF, dtype=np.int32)
    q = deque()

    ys, xs = np.where(obstacle)
    for y, x in zip(ys, xs):
        dist[y, x] = 0
        q.append((x, y))

    while q:
        x, y = q.popleft()
        d0 = dist[y, x]
        if d0 >= max_distance:
            continue
        nd = d0 + 1
        for dx, dy in _EIGHT_DIRS:
            nx, ny = x + dx, y + dy
            if nx < 0 or nx >= w or ny < 0 or ny >= h:
                continue
            if dist[ny, nx] > nd:
                dist[ny, nx] = nd
                q.append((nx, ny))

    return dist


# =====================================
#  障碍风险图（越近越危险，不做归一化）
# =====================================
def _build_obstacle_risk_map(
    walkable: np.ndarray,
    obstacle: np.ndarray,
    safety_radius: int,
    close_penalty_distance: int,
) -> np.ndarray:
    """
    Build the obstacle risk map (Chebyshev distance based).
    - safety_radius: mild penalty radius, smoothly falls to 0 at the border.
    - close_penalty_distance: strong penalty zone radius, rapidly increases near walls.
    """
    h, w = walkable.shape

    safety_radius = int(max(0, safety_radius))
    close_penalty_distance = int(max(0, close_penalty_distance))

    if safety_radius <= 0 and close_penalty_distance <= 0:
        return np.zeros((h, w), dtype=np.float32)

    max_d = max(1, safety_radius, close_penalty_distance)
    dist = _chebyshev_distance_transform(obstacle, max_d).astype(np.float32)

    risk = np.zeros((h, w), dtype=np.float32)

    if safety_radius > 0:
        mild_mask = (dist > 0) & (dist <= safety_radius)
        if np.any(mild_mask):
            mild_scale = (safety_radius - dist[mild_mask]) / safety_radius
            mild_scale = np.clip(mild_scale, 0.0, 1.0)
            # Gentle penalty (0~1) to bias towards open areas.
            risk[mild_mask] += np.square(mild_scale)

    if close_penalty_distance > 0:
        close_mask = (dist > 0) & (dist <= close_penalty_distance)
        if np.any(close_mask):
            norm_d = dist[close_mask]
            inv = (close_penalty_distance / norm_d) ** 2
            # Inverse-distance penalty: d=1 hurts close_penalty_distance^3, d grows -> quickly decays.
            penalty = inv * (close_penalty_distance)
            risk[close_mask] += penalty

    risk[~walkable] = 0.0

    return risk

# =====================================
#  敌人风险图（越近越危险，不做归一化）
# =====================================
def _build_enemy_risk_map(
    grid: np.ndarray,
    walkable: np.ndarray,
    enemy_mask: np.ndarray,
) -> np.ndarray:
    """
    Enemy risk map (B=radius, G=weight).
    Danger drops to 0 outside the monster radius and scales with the supplied weight.
    """
    h, w, _ = grid.shape

    risk = np.zeros((h, w), dtype=np.float32)
    if not enemy_mask.any():
        return risk

    B = grid[:, :, 0].astype(np.int32)      # radius from B channel
    G = grid[:, :, 1].astype(np.float32)    # weight from G channel

    ys, xs = np.where(enemy_mask)
    for y0, x0 in zip(ys, xs):
        radius = int(B[y0, x0])
        if radius <= 0:
            radius = 1
        weight = float(G[y0, x0])
        if weight <= 0:
            weight = 1.0

        for dy in range(-radius, radius + 1):
            ny = y0 + dy
            if ny < 0 or ny >= h:
                continue
            for dx in range(-radius, radius + 1):
                nx = x0 + dx
                if nx < 0 or nx >= w:
                    continue
                if dx == 0 and dy == 0:
                    continue

                d = max(abs(dx), abs(dy))
                if d > radius:
                    continue
                if not walkable[ny, nx]:
                    continue

                falloff = (radius - d) / radius
                if falloff <= 0:
                    continue

                # Larger monsters + close distance => significantly higher risk.
                danger = weight * (falloff ** 2) * radius
                risk[ny, nx] += danger

    return risk


# =====================================
#  A* 八方向安全寻路
# =====================================
def _a_star_eight_core(
    start_x,                                     # 起点 x 坐标（局部坐标）
    start_y,                                     # 起点 y 坐标（局部坐标）
    end_x,                                       # 终点 x 坐标（局部坐标）
    end_y,                                       # 终点 y 坐标（局部坐标）
    grid: np.ndarray,                            # 局部/全局 np.ndarray, HxWx3, uint8, BGR
    foot_len,                                    # 步长（格子数，>=1）
    endpoint_deviation,                          # 终点允许误差（切比雪夫）
    safety_radius,                               # 安全半径：障碍影响范围
    safety_weight,                               # 安全权重：越大越远离障碍/敌人（>=0）
    close_penalty_distance,                      # 强惩罚区半径：近距离额外加罚
) -> Optional[List[Tuple[int, int]]]:
    """
    只在给定 grid 上跑 A*（grid 可以是整图，也可以是裁剪后的 sub_grid）。
    start_x/start_y/end_x/end_y 必须是这个 grid 的坐标系。
    """
    if grid.dtype != np.uint8 or grid.ndim != 3 or grid.shape[2] != 3:
        raise ValueError("grid 必须是 HxWx3 的 uint8 BGR 图像")

    h, w, _ = grid.shape

    start_x = int(start_x)
    start_y = int(start_y)
    end_x = int(end_x)
    end_y = int(end_y)

    foot_len = max(1, int(foot_len))
    endpoint_deviation = max(0, int(endpoint_deviation))
    safety_radius = int(max(0, safety_radius))
    safety_weight = float(safety_weight)
    if safety_weight < 0:
        safety_weight = 0.0
    close_penalty_distance = int(max(0, close_penalty_distance))

    if not (0 <= start_x < w and 0 <= start_y < h):
        raise ValueError("起点不在当前 grid 范围内")
    if not (0 <= end_x < w and 0 <= end_y < h):
        raise ValueError("终点不在当前 grid 范围内")

    # 1. 掩码
    walkable, obstacle, enemy_mask = _build_masks(grid)
    if not walkable[start_y, start_x]:
        # 起点本身是障碍/敌人，强行当可走，避免直接挂死
        walkable[start_y, start_x] = True
        print("起点格子在当前 grid 内不可走（障碍或敌人），已强制标记为可走")

    # 2. 风险图：障碍 + 敌人（不做归一化）
    if safety_weight <= 0:
        risk_cost = np.zeros((h, w), dtype=np.float64)
    else:
        obstacle_risk = _build_obstacle_risk_map(
            walkable, obstacle, safety_radius, close_penalty_distance
        )
        enemy_risk = _build_enemy_risk_map(
            grid, walkable, enemy_mask
        )
        combined_risk = (obstacle_risk + enemy_risk).astype(np.float64, copy=False)
        # 预缩放，后面循环里就只加一次
        risk_cost = combined_risk * safety_weight

    # 3. 目标区域（终点误差）
    goal_mask = np.zeros((h, w), dtype=bool)
    for y in range(h):
        for x in range(w):
            if not walkable[y, x]:
                continue
            if max(abs(x - end_x), abs(y - end_y)) <= endpoint_deviation:
                goal_mask[y, x] = True

    if not goal_mask.any() and walkable[end_y, end_x]:
        goal_mask[end_y, end_x] = True

    if not goal_mask.any():
        return None

    # 4. A* 主体
    INF = float("inf")
    g_cost = np.full((h, w), INF, dtype=np.float64)
    came_from: dict[Tuple[int, int], Tuple[int, int]] = {}

    def heuristic(x: int, y: int) -> float:
        """八方向启发：Octile distance"""
        dx = abs(x - end_x)
        dy = abs(y - end_y)
        diag = min(dx, dy)
        straight = max(dx, dy) - diag
        return (math.sqrt(2) * diag + straight) * foot_len

    sx, sy = start_x, start_y
    g_cost[sy, sx] = 0.0
    start_h = heuristic(sx, sy)

    open_heap: List[Tuple[float, float, int, int]] = [(start_h, 0.0, sx, sy)]

    while open_heap:
        f, current_g, x, y = heapq.heappop(open_heap)

        if current_g > g_cost[y, x] + 1e-6:
            continue

        if goal_mask[y, x]:
            path: List[Tuple[int, int]] = [(x, y)]
            while (x, y) != (sx, sy):
                x, y = came_from[(x, y)]
                path.append((x, y))
            path.reverse()
            return path

        for dx, dy in _EIGHT_DIRS:
            nx = x + dx * foot_len
            ny = y + dy * foot_len
            if nx < 0 or nx >= w or ny < 0 or ny >= h:
                continue

            # 步长 > 1 时，中间的格子也必须全是可走的
            ok = True
            for step in range(1, foot_len + 1):
                ix = x + dx * step
                iy = y + dy * step
                if (
                    ix < 0 or ix >= w or
                    iy < 0 or iy >= h or
                    not walkable[iy, ix]
                ):
                    ok = False
                    break
            if not ok:
                continue

            # 几何移动代价：直走 1，斜走 sqrt(2)，再乘步长
            base_move_cost = math.sqrt(dx * dx + dy * dy) * foot_len

            # 安全代价：预缩放后的格子风险
            step_risk = float(risk_cost[ny, nx])

            tentative_g = current_g + base_move_cost + step_risk

            if tentative_g + 1e-6 < g_cost[ny, nx]:
                g_cost[ny, nx] = tentative_g
                came_from[(nx, ny)] = (x, y)
                f_new = tentative_g + heuristic(nx, ny)
                heapq.heappush(open_heap, (f_new, tentative_g, nx, ny))

    return None


def a_star_eight(
    start_x,                                     # 起点 x 坐标（全图坐标）
    start_y,                                     # 起点 y 坐标（全图坐标）
    end_x,                                       # 终点 x 坐标（全图坐标）
    end_y,                                       # 终点 y 坐标（全图坐标）
    img_path,                                    # np.ndarray, HxWx3, uint8, BGR（整图）
    foot_len,                                    # 步长（格子数，>=1）
    endpoint_deviation,                          # 终点允许误差（切比雪夫）
    safety_radius,                               # 安全半径：障碍影响范围
    safety_weight,                               # 安全权重：越大越远离障碍/敌人（>=0）
    close_penalty_distance,                      # 强惩罚区半径：近距离额外加罚
    *,
    use_local: bool = True,                      # 是否启用局部裁剪
    local_margin: int = 10,                      # 起终点两边各扩多少格（基础余量）
    max_patch_size: int = 260,                   # 局部 patch 最大宽/高，超过则回退全图
) -> Optional[List[Tuple[int, int]]]:
    """
    对外的 A* 寻路接口：

    - 默认用局部模式：
        只截取“起点 + 终点 + 安全半径/惩罚半径 + 额外 margin”组成的一块小图来跑 A*，
        然后把结果路径坐标映射回全图坐标。
    - 如果 patch 太大，或者局部范围内无路，则自动回退到“整图 A*”。

    这样大地图 1000x1000 的时候，一般只在几十~两百的 patch 里跑，大幅减少耗时。
    """
    grid = img_path

    if not isinstance(grid, np.ndarray) or grid.ndim != 3 or grid.shape[2] != 3 or grid.dtype != np.uint8:
        raise ValueError("img_path 必须是 HxWx3 的 uint8 BGR 图像")

    H, W, _ = grid.shape

    # 先把全局坐标转 int 并做边界检查
    start_x = int(start_x)
    start_y = int(start_y)
    end_x = int(end_x)
    end_y = int(end_y)

    if not (0 <= start_x < W and 0 <= start_y < H):
        raise ValueError("起点不在地图范围内")
    if not (0 <= end_x < W and 0 <= end_y < H):
        raise ValueError("终点不在地图范围内")

    # 如果不开局部模式，直接全图跑
    if not use_local:
        print("a_star_eight: use_local=False, 使用整图 A*")
        return _a_star_eight_core(
            start_x, start_y, end_x, end_y,
            grid,
            foot_len,
            endpoint_deviation,
            safety_radius,
            safety_weight,
            close_penalty_distance,
        )

    # ======= 计算局部 patch 区域（全图坐标） =======

    # 总 margin = 安全半径 + 强惩罚半径 + 自定义余量
    total_margin = int(local_margin + safety_radius + close_penalty_distance)

    x_min = min(start_x, end_x) - total_margin
    x_max = max(start_x, end_x) + total_margin
    y_min = min(start_y, end_y) - total_margin
    y_max = max(start_y, end_y) + total_margin

    # 和整图范围做一次截断
    px0 = max(0, x_min)
    py0 = max(0, y_min)
    px1 = min(W - 1, x_max)
    py1 = min(H - 1, y_max)

    subW = px1 - px0 + 1
    subH = py1 - py0 + 1

    # 如果 patch 还太大，就直接回退全图
    if subW > max_patch_size or subH > max_patch_size:
        print(f"a_star_eight: 局部 patch 太大({subW}x{subH}), 回退整图 A*")
        return _a_star_eight_core(
            start_x, start_y, end_x, end_y,
            grid,
            foot_len,
            endpoint_deviation,
            safety_radius,
            safety_weight,
            close_penalty_distance,
        )

    # ======= 截取局部 sub_grid，映射坐标到局部坐标系 =======
    sub_grid = grid[py0:py1 + 1, px0:px1 + 1]

    sx_local = start_x - px0
    sy_local = start_y - py0
    ex_local = end_x - px0
    ey_local = end_y - py0

    # 安全检查：防止由于整数截断导致坐标跑出 sub_grid
    if not (0 <= sx_local < subW and 0 <= sy_local < subH):
        print("警告: sx_local/sy_local 越界, 回退整图 A*")
        return _a_star_eight_core(
            start_x, start_y, end_x, end_y,
            grid,
            foot_len,
            endpoint_deviation,
            safety_radius,
            safety_weight,
            close_penalty_distance,
        )

    if not (0 <= ex_local < subW and 0 <= ey_local < subH):
        print("警告: ex_local/ey_local 越界, 回退整图 A*")
        return _a_star_eight_core(
            start_x, start_y, end_x, end_y,
            grid,
            foot_len,
            endpoint_deviation,
            safety_radius,
            safety_weight,
            close_penalty_distance,
        )

    # ======= 在局部 patch 上跑 A* =======
    path_local = _a_star_eight_core(
        sx_local, sy_local, ex_local, ey_local,
        sub_grid,
        foot_len,
        endpoint_deviation,
        safety_radius,
        safety_weight,
        close_penalty_distance,
    )

    if path_local is None:
        # 局部范围里找不到路，就回退整图
        print(f"a_star_eight: 局部 {subW}x{subH} 无路可走, 回退整图 A*")
        return _a_star_eight_core(
            start_x, start_y, end_x, end_y,
            grid,
            foot_len,
            endpoint_deviation,
            safety_radius,
            safety_weight,
            close_penalty_distance,
        )

    # ======= 把局部路径映射回全图坐标 =======
    path_global = [(x + px0, y + py0) for (x, y) in path_local]

    # 调试输出一下 patch 信息和路径长度，方便你对比性能
    print(f"a_star_eight: 使用局部 patch {subW}x{subH}, 路径长度={len(path_global)}")

    return path_global


# </a星寻路优化算法>↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑




# <检测3点是否成一线>↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
# 控制鼠标沿路径移动寻路时,通过这个函数来决策鼠标的按键策略
# ---- 工具：把两点之间的位移归一化到 8 个方向之一 ----
def _unit_dir(a, b):
    """
    把 a->b 的位移转换成 8 向单位向量（dx, dy ∈ {-1, 0, 1}）
    a, b: (x, y)
    """
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    if dx == 0 and dy == 0:
        return (0, 0)
    ux = 0 if dx == 0 else dx // abs(dx)
    uy = 0 if dy == 0 else dy // abs(dy)
    return (ux, uy)


def check_the_connection(start, next_point, next_next_point):
    """
    当前点 / 下一路径点 / 下下路径点 是否成三点一线（同一个 8 方向）
    True  -> 直线段（可以右键长按）
    False -> 转弯段（要用左键点走）
    """
    d1 = _unit_dir(start, next_point)
    d2 = _unit_dir(next_point, next_next_point)
    return d1 != (0, 0) and d1 == d2

# </检测3点是否成一线>↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑




# <可视化显示>↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓

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
    path: [(x,y), ...]，jy_a_star_eight 的返回结果
    cell_size: 每个格子放大成多少像素
    """
    if grid.dtype != np.uint8 or grid.ndim != 3 or grid.shape[2] != 3:
        raise ValueError("grid 必须是 HxWx3 的 uint8 BGR")

    h, w, _ = grid.shape

    # 用最近邻插值放大，避免颜色被模糊
    vis = cv2.resize(
        grid, (w * cell_size, h * cell_size),
        interpolation=cv2.INTER_NEAREST
    )

    # 画淡灰色网格线
    line_color = (200, 200, 200)
    for x in range(w + 1):
        px = x * cell_size
        cv2.line(vis, (px, 0), (px, h * cell_size), line_color, 1)
    for y in range(h + 1):
        py = y * cell_size
        cv2.line(vis, (0, py), (w * cell_size, py), line_color, 1)

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
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()

# =====================  先放大图像,在放大后的图像上绘制点  =====================
def visualize_grid_and_point(
    grid: np.ndarray,
    point: Tuple,
    win_name: str = "A* path",
    cell_size: int = 30,
):
    if grid.dtype != np.uint8 or grid.ndim != 3 or grid.shape[2] != 3:
        raise ValueError("grid 必须是 HxWx3 的 uint8 BGR")

    h, w, _ = grid.shape

    # 用最近邻插值放大，避免颜色被模糊
    vis = cv2.resize(
        grid, (w * cell_size, h * cell_size),
        interpolation=cv2.INTER_NEAREST
    )

    # 画淡灰色网格线
    line_color = (200, 200, 200)
    for x in range(w + 1):
        px = x * cell_size
        cv2.line(vis, (px, 0), (px, h * cell_size), line_color, 1)
    for y in range(h + 1):
        py = y * cell_size
        cv2.line(vis, (0, py), (w * cell_size, py), line_color, 1)

    if point is not None:
        point_color = (0, 0, 255)  # 红
        gx, gy = point  # 这里假设 point=(x, y) = (列, 行)
        # 把格子坐标转成放大后图像的像素坐标（格子中心）
        cx = gx * cell_size + cell_size // 2
        cy = gy * cell_size + cell_size // 2
        cv2.circle(vis, (cx,cy), radius=cell_size // 3, color=point_color, thickness=-1)
    else:
        print('传入的坐标点为None')

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
    enemies = _parse_enemies(grid)
    risk = _compute_risk(grid, enemies)
    # print(risk)
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

    # 画网格线
    for i in range(W + 1):
        x = i * scale
        cv2.line(vis, (x, 0), (x, H * scale), (180, 180, 180), 1)
    for j in range(H + 1):
        y = j * scale
        cv2.line(vis, (0, y), (W * scale, y), (180, 180, 180), 1)

    # 绘制敌人 + “切比雪夫半径方框”
    for (xe, ye), r, w in enemies:
        color = (0, 0, 255) if w == 3 else (0, 255, 0)  # 红 or 绿              # 根据w权重设置绘制矩形框的颜色
        center_px = (xe * scale + scale // 2, ye * scale + scale // 2)         # 图像被放大处理了,计算放大后绘制中心点的位置
        cv2.circle(vis, center_px, max(2, scale // 3), color, -1)              # 设置的颜色绘制中心点
        # 切比雪夫半径 → 方形包围（像素对齐）
        tl = (max(0, xe - r) * scale, max(0, ye - r) * scale)                  # 敌人攻击范围矩形框左上角坐标
        br = (min(W - 1, xe + r) * scale + (scale - 1), min(H - 1, ye + r) * scale + (scale - 1))   # 敌人攻击范围矩形框右下角坐标
        cv2.rectangle(vis, tl, br, color, 2)                                   # 设置的颜色绘制敌人矩形框
        # 绘制标识文字的外轮廓为黑色
        cv2.putText(vis, f"E{(int(xe), int(ye))}", (xe * scale + 3, ye * scale + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2, cv2.LINE_AA)
        # 绘制标识文字的内部为白色
        cv2.putText(vis, f"E{(int(xe), int(ye))}", (xe * scale + 3, ye * scale + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

    # 绘制搜索中心点 + 搜索半径（方框）
    if search_center is None:
        search_center = a_pos
    cx, cy = search_center
    if search_radius is not None and search_radius >= 0:
        tl = (max(0, cx - search_radius) * scale, max(0, cy - search_radius) * scale)   # 矩形框左上角坐标
        br = (min(W - 1, cx + search_radius) * scale + (scale - 1),                     # 矩形框右下角坐标
              min(H - 1, cy + search_radius) * scale + (scale - 1))
        cv2.rectangle(vis, tl, br, (255, 0, 255), 2)                                    # 绘制洋红色矩形搜索框
    search_center_b = (cx * scale + scale // 2, cy * scale + scale // 2)      # 图像被放大处理了,计算放大后绘制中心点的位置
    cv2.circle(vis, search_center_b, max(3, scale // 3), (255, 255, 0), -1)  # 青色绘制中心点 (BGR: 255,255,0)
    # 绘制标识文字的外轮廓为黑色
    cv2.putText(vis, f"C{search_center}", (cx * scale + 3, cy * scale + 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2, cv2.LINE_AA)
    # 绘制标识文字的内部为白色
    cv2.putText(vis, f"C{search_center}", (cx * scale + 3, cy * scale + 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

    # 绘制 人物a 点（青色）与 T目的地坐标（黄色）
    ax, ay = a_pos
    a_center = (ax * scale + scale // 2, ay * scale + scale // 2)               # 图像被放大处理了,计算放大后绘制人物点的位置

    if target is not None:
        tx, ty = target                                                         # 目的点坐标,通过next_move_a()计算获取
        t_center = (tx * scale + scale // 2, ty * scale + scale // 2)           # 图像被放大处理了,计算放大后绘制目标点的位置
        cv2.circle(vis, t_center, max(3, scale // 3), (0, 255, 255), -1)  # 黄色绘制目标点 (BGR: 0,255,255)
        cv2.line(vis, a_center, t_center, (0, 0, 0), 3)          # 人物坐标与目的点坐标的连线(外轮廓线黑色)
        cv2.line(vis, a_center, t_center, (0, 255, 255), 2)      # 人物坐标与目的点坐标的连线(内部线黄色)
        # 绘制标识文字的外轮廓为黑色
        cv2.putText(vis, f"T{(int(tx),int(ty))}", (tx * scale + 3, ty * scale + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2, cv2.LINE_AA)
        # 绘制标识文字的内部为黄色
        cv2.putText(vis, f"T{(int(tx),int(ty))}", (tx * scale + 3, ty * scale + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)
    cv2.circle(vis, a_center, max(2, scale // 4), (255, 255, 255), -1)  # 白色绘制人物点 (BGR: 255,255,0)
    # 绘制标识文字的外轮廓为黑色
    cv2.putText(vis, f"P{a_pos}", (ax * scale + 3, ay * scale + scale - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2, cv2.LINE_AA)
    # 绘制标识文字的内部为白色
    cv2.putText(vis, f"P{a_pos}", (ax * scale + 3, ay * scale + scale - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

    # 绘制每个网格的risk风险值
    # for (h, w), value in np.ndenumerate(risk):
    #     if risk[h,w] > 0 :
    #         # 绘制标识文字的外轮廓为黑色
    #         cv2.putText(vis, f"r{risk[h,w]}", (w * scale + 20, h * scale + 35),
    #                     cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2, cv2.LINE_AA)
    #         # 绘制标识文字的内部为白色
    #         cv2.putText(vis, f"r{risk[h,w]}", (w * scale + 20, h * scale + 35),
    #                     cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

    # 显示/保存
    try:
        cv2.imshow(window, vis)
        # cv2.waitKey(0)
        # cv2.destroyAllWindows()
    except Exception:
        cv2.imwrite(outfile, vis)
        print(f"[info] GUI 不可用，已保存到: {outfile}")

# =====================  Demo：可视化样例  =====================
def _demo_visual(grid: np.ndarray):
    a = (3, 0)
    target = next_move_a(a, grid, search_center=(5,7), search_radius=3)
    print(f"A={a}, target={target}")                # 如果target输出为None , 可能是出发点(人物点)被填充成了障碍点(非纯白色)
    visualize_move(
        grid, a, target,
        search_center=(5,7), search_radius=3,
        show_risk=True, scale=55, window="demo_case",
        outfile="viz_demo.png"
    )

# </可视化显示>↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑




