import time
import traceback
from threading import Event
from typing import Callable, List, Optional, Tuple, Union, Any
from public import *
import ai算法
import config
import cv2
import dm_utils
import ai_visual
from kmNet类封装2 import RestartLoop  # 改: 抢占时强制回到主循环头

def 地图上绘制怪物点(img: Any, master_location: list):
    img = img.copy()
    # 地图上绘制危险级别 S 的怪
    S_list = [(a, b) for path, a, b in master_location if 'S' in path]
    if S_list:
        sb, sg, sr = config.ENEMY_COLOR_S
        for (mx, my) in S_list:
            img[my, mx][0] = sb
            img[my, mx][1] = sg
            img[my, mx][2] = sr
    # 地图上绘制危险级别 A 的怪
    A_list = [(a, b) for path, a, b in master_location if 'S' not in path]
    if A_list:
        ab, ag, ar = config.ENEMY_COLOR_A
        for (mx, my) in A_list:
            img[my, mx][0] = ab
            img[my, mx][1] = ag
            img[my, mx][2] = ar
    # 地图上绘制宝宝
    baobao_list = [(a, b) for path, a, b in master_location if '宝宝' in path]
    if baobao_list:
        pb, pg, pr = config.PET_COLOR
        for (mx, my) in baobao_list:
            img[my, mx][0] = pb
            img[my, mx][1] = pg
            img[my, mx][2] = pr
    return img

with open(config.MONSTER_LIST_PATH, 'r', encoding='UTF-8') as f:
    怪物图片路径 = f.read()
    怪物图片路径 = 怪物图片路径.replace('\n','|')
    # 与配置保持一致，且兼容列表中不带 "./" 的写法
    pet_path = config.PET_PIC_PATH[2:] if config.PET_PIC_PATH.startswith("./") else config.PET_PIC_PATH
    target = f"{pet_path}|"
    # target = "|pic/guaiwu/单机_宝宝.bmp"
    怪物图片路径_不包括宝宝 = 怪物图片路径.replace(target, "")
    怪物路径列表 = 怪物图片路径.split('|')
    # if config.DEBUG_LOG:
    #     print(怪物图片路径)
    #     print(怪物路径列表)
    #     print(怪物图片路径_不包括宝宝)

def 更新地图_怪物点(dm: object, controller: object,map_img):
    怪物列表_包括宝宝 = 识别怪物坐标(dm, controller, 543, 98, 1370, 714, 怪物图片路径, config.MONSTER_LIST_SIM)
    if 怪物列表_包括宝宝:
        map_img = 地图上绘制怪物点(map_img, 怪物列表_包括宝宝)
    return map_img, 怪物列表_包括宝宝


def 识别怪物坐标(dm: object, controller: object, x1,y1,x2,y2,path,sim):
    """
    找图找到范围内所有怪物的屏幕坐标,转换成游戏坐标,按(怪物名称,怪物游戏x,怪物游戏y)元组的形式存储到列表中
    """
    img_path = path
    人物坐标x, 人物坐标y = dm_utils.ocr_player_pos(dm)
    if 人物坐标x < 0 or 人物坐标y < 0:
        # OCR 坐标无效时跳过找图，避免无意义的坐标转换
        return []
    返回_找图AIEx = dm.AiFindPicEx(x1,y1,x2,y2, fr"./{img_path}", sim, 0)
    if 返回_找图AIEx != '':
        返回_找图AIEx_list = 返回_找图AIEx.split('|')
        怪物坐标列表 = []
        for i in 返回_找图AIEx_list:
            i_list = i.split(',')
            # 以血量为标准做怪物名字图,找到的坐标x+14,y+34偏移后,就是怪物的中心位置
            怪物图片序号 = int(i_list[0])
            怪物名字 = 怪物路径列表[怪物图片序号]
            怪物屏幕x = int(i_list[1]) + 14
            怪物屏幕y = int(i_list[2]) + 34
            游戏坐标x, 游戏坐标y = controller.屏幕坐标转游戏坐标(人物坐标x, 人物坐标y, 怪物屏幕x, 怪物屏幕y)
            # 把怪物名字也存储到列表,后期要根据怪物名字在地图上标记不同的颜色点
            怪物坐标 = (怪物名字,游戏坐标x, 游戏坐标y)
            if 怪物坐标 not in 怪物坐标列表:
                怪物坐标列表.append(怪物坐标)
        return 怪物坐标列表
    else:
        return []


def small_area_checker(dm: object):
    z, _, _ = dm.AiFindPic(843, 359, 1084, 513, 怪物图片路径_不包括宝宝, config.MONSTER_PIC_SIM, 0)  # 在小区域内找怪图
    return z != -1  # 大漠：z != -1 表示找到了图

def big_area_checker(dm: object):
    z, _, _ = dm.AiFindPic(5, 28, 1916, 823, 怪物图片路径_不包括宝宝, config.MONSTER_PIC_SIM, 0)
    return z != -1  # 大漠：z != -1 表示找到了图


def 地图上绘制玩家点(img,玩家坐标列表:list):
    img = img.copy()
    pb, pg, pr = config.PLAYER_COLOR
    for (mx,my) in 玩家坐标列表:
        img[my, mx][0] = pb
        img[my, mx][1] = pg
        img[my, mx][2] = pr
    return img


def update_map_fn(dm: object,controller: object,map_img):             # 获取坐标后, 更新地图
    玩家坐标列表 = dm_utils.scan_player(
        dm,
        controller.屏幕坐标转游戏坐标,
    )
    if 玩家坐标列表:
        # print("玩家坐标列表123", 玩家坐标列表)
        map_img = 地图上绘制玩家点(map_img, 玩家坐标列表)
    return map_img, 玩家坐标列表


def _nearest_index_along_path(
    path: List[tuple], pos: tuple, start_index: int, max_lookahead: int = 6
) -> Tuple[int, int]:
    """
    在 path[start_index : start_index+max_lookahead] 范围内，
    找到离当前位置最近的路径点索引，防止跨点。
    """
    px, py = pos
    best_i = start_index
    best_d = 10**9
    end = min(len(path), start_index + max_lookahead + 1)
    for i in range(start_index, end):
        d = max(abs(px - path[i][0]), abs(py - path[i][1]))
        if d < best_d:
            best_d = d
            best_i = i
    return best_i, best_d


def _select_pursuit_point(
    path: List[tuple],
    pos: tuple,
    start_index: int,
    lookahead_dist: int,
    window: int,
    *,
    prefer_turn: bool = True,
) -> Tuple[tuple, int]:
    """
    在前方窗口里选择“前瞻点/转折点”，避免贴着最近点来回抖动。
    """
    if not path:
        return (-1, -1), 0
    lookahead_dist = max(0, int(lookahead_dist))
    window = max(1, int(window))
    end = min(len(path) - 1, start_index + window)
    if start_index >= end:
        return path[end], end

    px, py = pos
    target_idx = end
    for i in range(start_index + 1, end + 1):
        d = max(abs(px - path[i][0]), abs(py - path[i][1]))
        if d >= lookahead_dist:
            target_idx = i
            break

    if prefer_turn and end - start_index >= 2:
        for i in range(start_index + 2, end + 1):
            if not ai算法.check_the_connection(path[i - 2], path[i - 1], path[i]):
                turn_idx = i - 1
                if turn_idx > target_idx:
                    target_idx = turn_idx
                break

    return path[target_idx], target_idx


def _unit_dir(a: tuple, b: tuple) -> Tuple[int, int]:
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    if dx == 0 and dy == 0:
        return (0, 0)
    ux = 0 if dx == 0 else dx // abs(dx)
    uy = 0 if dy == 0 else dy // abs(dy)
    return (ux, uy)


def _straight_segment_end(path: List[tuple], start_index: int) -> Tuple[int, Tuple[int, int]]:
    if not path or start_index >= len(path) - 1:
        return start_index, (0, 0)
    start_index = max(0, start_index)
    direction = _unit_dir(path[start_index], path[start_index + 1])
    if direction == (0, 0):
        return start_index, (0, 0)
    end_index = start_index + 1
    for i in range(start_index + 1, len(path) - 1):
        if _unit_dir(path[i], path[i + 1]) != direction:
            break
        end_index = i + 1
    return end_index, direction


def _line_offset(pos: tuple, line_point: tuple, direction: tuple) -> int:
    dx, dy = direction
    if dx == 0 and dy == 0:
        return 10**9
    if dx == 0:
        return abs(pos[0] - line_point[0])
    if dy == 0:
        return abs(pos[1] - line_point[1])
    if dx == dy:
        diff = abs((pos[0] - pos[1]) - (line_point[0] - line_point[1]))
    else:
        diff = abs((pos[0] + pos[1]) - (line_point[0] + line_point[1]))
    return (diff + 1) // 2


def _is_white_cell(grid: Any, x: int, y: int) -> bool:
    if grid is None:
        return False
    h, w = grid.shape[:2]
    if x < 0 or x >= w or y < 0 or y >= h:
        return False
    b, g, r = grid[y, x]
    return b == 255 and g == 255 and r == 255


def _forward_clear(grid: Any, start: tuple, end: tuple, direction: tuple) -> bool:
    dx, dy = direction
    if dx == 0 and dy == 0:
        return False
    steps = max(abs(end[0] - start[0]), abs(end[1] - start[1]))
    for step in range(1, steps + 1):
        x = start[0] + dx * step
        y = start[1] + dy * step
        if not _is_white_cell(grid, x, y):
            return False
    return True


def _has_new_players(
    prev_players: List[tuple], curr_players: List[tuple], near_threshold: int = 3
) -> bool:
    if not prev_players or not curr_players:
        return False
    for (cx, cy) in curr_players:
        if all(
            max(abs(cx - px), abs(cy - py)) > near_threshold
            for (px, py) in prev_players
        ):
            return True
    return False


def walk_path(
    path: List[tuple],  # 规划好的路径点列表（游戏坐标/格子坐标），例如 [(x1,y1),(x2,y2)...]
    *,  # 强制后续参数使用“关键字传参”，避免不同线程/调用方位置传参造成混淆
    img: Any,
    dm: object,
    get_pos: Callable[[object,Union[None, tuple]], tuple],  # 获取人物当前坐标的回调函数；需返回 (x, y)，识别失败返回 (-1, -1)
    controller,  # 行走控制器：封装“判断方位/鼠标按下抬起/左键点方向/延时”等具体操作实现
    bad_cells: Optional[set] = None,  # 共享的“坏格子/禁走点”集合；本函数会在退出时清空，便于上层下一次寻路复用
    stop_event: Union[Event, tuple[Event, ...], None] = None,  # 接收 Event 或者元组，或者 None
    small_area_checker: Optional[Callable[[object], bool]] = None,  # 可选：小范围找怪/风险检测；返回 True 时提前退出
    big_area_checker: Optional[Callable[[object], bool]] = None,  # 可选：大范围找怪/风险检测；返回 True 时提前退出
    update_map_fn: Optional[Callable[[object,object,Any], Tuple[Any, List[tuple]]]] = None,  # 可选：刷新地图与玩家点（用于动态重寻路）
    end_threshold: int = 0,  # 到达终点的距离阈值（切比雪夫距离）；0 表示必须精确踩到终点
    reach_threshold: int = 0,  # 到达“下一个路径点”的距离阈值；满足后 idx 才会推进到下一个点
    max_lookahead: int = 6,  # 纠偏窗口：从当前 idx 起向前最多看 N 个点，选一个离当前位置最近的点作为新 idx
    sleep_interval: float = 50,  # 每次发出移动指令后的间隔（秒）；越小越灵敏但可能抖动/更吃 CPU
    dynamic_repath: bool = False,  # 是否动态重寻路：边走边用 update_map_fn 刷新地图，并重新算更安全的目标/路径
    repath_interval: float = 0.5,  # 动态重寻路最小间隔（秒）；避免过于频繁地刷新/重算
    repath_radius: Optional[int] = None,  # 动态重寻路 safe_point 的搜索半径（格子）；None 则使用配置默认值
    repath_selection_method: Optional[int] = None,  # 动态重寻路 safe_point 的选择策略；None 则使用配置默认值
    a_star_kwargs: Optional[dict] = None,  # 动态重寻路时传给 ai算法.a_star_eight 的参数（foot_len/safety_weight 等）
    right_only: bool = False,  # 为 True 时全程仅用右键移动；为 False 时允许左键+右键组合
    right_refresh_interval: float = 22,  # 右键持续按住时刷新鼠标方向的间隔（秒），避免转向慢导致跑偏
    right_only_straight_lock: bool = True,  # right_only=True 时启用直行锁定,还要搭配传入 update_map_fn 刷新地图函数才能使用
    straight_lock_deviation: int = 1,  # 允许的直行偏离格数
    straight_lock_release_dist: int = 2,  # 接近直线段末端时解除直行锁定
    straight_lock_check_interval: float = 0.2,  # 直行锁定前方检测间隔（秒）
    repath_to_end: bool = False,  # 为 True 时 dynamic_repath 重算目标固定为最初终点（path[-1]），用于跑步跨点/偏航纠正
    pursuit_mode: bool = False,  # 为 True 时使用“前瞻点/转折点”作为移动目标，减少贴点来回抖动
    pursuit_lookahead: int = 4,  # 前瞻距离（格子，切比雪夫距离）
    pursuit_window: int = 8,  # 前方窗口大小（点数），越大越“看得远”
    pursuit_turn: bool = True,  # 优先选择前方转折点
):
    """
    统一的沿路径行走逻辑。允许注入坐标获取、控制器、地图更新与终止事件，便于多线程复用。
    """

    owner_acquired = False

    if bad_cells is None:
        bad_cells = set()

    if not path:  # 没有路径点就无需行走
        return  # 直接返回 None（上层可据此判断无需移动）

    fixed_end = path[-1]  # 固定终点（用于 repath_to_end 模式）

    cur = get_pos(dm)
    if cur[0] < 0 or cur[1] < 0:  # 坐标识别失败（约定：负数表示失败）
        print("警告: 入场时无法识别人物坐标，放弃本次行走")  # 打印提示便于定位识别问题
        return  # 放弃本次走路，让上层决定是否重试/重算

    start_dist = max(abs(cur[0] - path[0][0]), abs(cur[1] - path[0][1]))  # 人物与路径起点的切比雪夫距离
    if start_dist > 5:  # 起点偏差过大通常意味着路径已经过期/人物不在预期位置
        if repath_to_end and dynamic_repath and update_map_fn is not None:
            print("警告: 人物与路径起点偏差太大，尝试动态重算到固定终点")  # 尝试自愈：从当前位置重算到目标
            try:
                frame, _ = update_map_fn(dm, controller, img)
                astar_cfg = a_star_kwargs or Parameter.Ai.astar
                new_path = ai算法.a_star_eight(
                    start_x=cur[0],
                    start_y=cur[1],
                    end_x=fixed_end[0],
                    end_y=fixed_end[1],
                    img_path=frame,
                    **astar_cfg,
                )
                if new_path:
                    path = new_path
                else:
                    print("警告: 动态重算失败，退出")
                    return
            except Exception as e:
                print("警告: 动态重算异常，退出", repr(e))
                return
        else:
            print("警告: 人物与路径起点偏差太大，视为无效路径，退出，让上层重新算")  # 交给上层重新 A* 规划
            return  # 直接退出，不做“强行追起点”的移动

    owner_acquired = controller.acquire_input_owner()  # 改: 寻路期间独占输入，避免多线程抢占

    next_move_cfg = Parameter.Ai.next_move  # next_move（安全点/逃离点）相关配置

    if repath_radius is None:  # 调用方没显式指定动态重寻路的搜索半径
        repath_radius = next_move_cfg["search_radius_default"] or 25  # 用配置默认值，缺省再回退到 25
    if repath_selection_method is None:  # 调用方没显式指定 safe_point 选择策略
        repath_selection_method = next_move_cfg["selection_method_default"] or 1  # 用配置默认值，缺省再回退到 1

    if a_star_kwargs is None:  # 调用方没传动态重寻路使用的 A* 参数
        a_star_kwargs = Parameter.Ai.astar  # A* 寻路相关配置

    straight_lock_deviation = max(0, int(straight_lock_deviation))
    straight_lock_release_dist = max(0, int(straight_lock_release_dist))
    straight_lock_check_interval = max(0.0, float(straight_lock_check_interval))

    road_list: List[Coord] = []  # 记录“实际走过”的人物坐标点（用于调试/可视化/回放）
    end_x, end_y = fixed_end  # 当前路径的终点（会在动态重寻路时更新）
    idx = 0  # 当前跟随的路径点索引（指向 path[idx]）
    right_down = False  # 标记：当前是否处于“按住右键持续走”的状态（直线段更平滑）
    last_dir = None  # 上一次移动的目标方位（用于减少重复发指令）
    last_idx = idx  # 上一次循环时的 idx（用于判断是否有前进）
    last_dist_to_next = None  # 上一次循环时“到下一点”的距离（用于判断是否在接近目标）
    last_progress_time = time.time()  # 上一次确认“有进展”的时间戳（用于卡住检测）
    stuck_timeout = 4.0  # 卡住超时阈值：超过该时间仍无进展则认为卡点，提前返回
    current_goal = (end_x, end_y)  # 记录当前目标终点（动态重寻路时用于判断目标是否变化）
    last_safe_with_players = None  # 记录上一次检测到玩家后的安全点
    last_players = None  # 记录上一次检测到的玩家坐标列表
    last_repath_time = 0.0  # 上一次执行动态重寻路的时间戳
    off_path_cnt = 0  # 连续偏离路径计数（用于 repath_to_end 模式快速纠偏）
    last_mouse_move_time = 0.0  # 最近一次下发“移动方位”指令的时间（用于右键长按刷新）
    last_straight_map_time = 0.0  # 直行锁定使用的地图缓存时间戳
    last_straight_map = None  # 直行锁定使用的地图缓存
    strict_end = end_threshold == 0  # end_threshold==0 表示“严格到点”：必须走到最后一个格子

    print(f"{controller}开始寻路")  # 日志：开始执行 walk_path
    try:  # 主循环包一层 try，保证异常时也会释放按键/鼠标
        while True:  # 一直走到终点/提前退出条件满足/卡住为止

            if stop_event is not None:
                for ev in stop_event:
                    if ev is not None and ev.is_set():
                        print(f"收到 {controller} 中断信号, 退出沿路径控制人物行走")  # 日志：收到停止信号
                        bad_cells.clear()  # 清空坏格子集合，避免污染下一次寻路
                        raise RestartLoop()  # 改: 抢占后直接回到线程主循环头

            if small_area_checker and small_area_checker(dm):  # 小范围发现怪物/威胁（由调用方定义检测逻辑）
                bad_cells.clear()  # 退出前清理共享状态
                return road_list  # 立即返回
            if big_area_checker and big_area_checker(dm):  # 大范围发现怪物/威胁
                bad_cells.clear()  # 同样清理共享状态
                return road_list  # 立即返回

            cur = get_pos(dm)  # 本轮循环重新获取人物坐标（行走过程中坐标会变化）
            if cur[0] < 0 or cur[1] < 0:  # 坐标识别失败则短暂等待再试，避免误操作
                time.sleep(0.05)  # 轻微 sleep，给 OCR/识别留时间
                continue  # 跳过本轮，不发走路指令
            人物x, 人物y = cur  # 拆包得到人物坐标
            if (人物x, 人物y) not in road_list:  # 避免重复记录相同点导致列表膨胀
                road_list.append((人物x, 人物y))  # 追加“实际经过点”用于调试/展示

            if dynamic_repath and update_map_fn is not None:  # 开启动态重寻路且提供了地图刷新函数
                now = time.time()  # 当前时间戳（用于节流）
                if now - last_repath_time >= repath_interval:  # 到达重算间隔才执行一次重算
                    last_repath_time = now  # 更新“上次重算时间”
                    frame, players = update_map_fn(dm,controller, img)  # 刷新地图，并识别玩家点（用于避让/逃离）`````````````````````````
                    last_straight_map = frame
                    last_straight_map_time = now
                    skip_safe_repath = False
                    if repath_to_end:
                        new_path = ai算法.a_star_eight(
                            start_x=人物x,
                            start_y=人物y,
                            end_x=fixed_end[0],
                            end_y=fixed_end[1],
                            img_path=frame,
                            **a_star_kwargs,
                        )
                        if new_path:
                            path = new_path
                            end_x, end_y = fixed_end
                            current_goal = fixed_end
                            idx = 0
                            last_idx = 0
                            last_dist_to_next = None
                            last_progress_time = time.time()
                            off_path_cnt = 0
                            continue
                        else:
                            print("动态重算到固定终点失败，继续沿旧路径尝试")
                        skip_safe_repath = True

                    if not skip_safe_repath:
                        has_players = bool(players)
                        prev_players = last_players or []
                        new_players_appeared = (
                            has_players
                            and prev_players
                            and _has_new_players(prev_players, players)
                        )
                        # print("寻路中时时更新玩家坐标列表")
                        direction_players = players
                        escape_mode = "free"
                        if new_players_appeared:
                            direction_players = prev_players
                            escape_mode = "away"
                        new_safe = ai算法.next_move_a(  # 基于当前局势计算一个“更安全”的临时目标点
                            (人物x, 人物y),  # 当前人物位置
                            frame,  # 当前地图/风险栅格（含玩家/怪物等信息）
                            (人物x, 人物y),  # 搜索中心（通常就是当前位置）
                            repath_radius,  # 搜索半径
                            repath_selection_method,  # safe_point 选择策略
                            players=direction_players,  # 传入玩家点列表，AI 可据此躲人
                            escape_mode=escape_mode,  # 选择安全点模式
                        )  # 结束 next_move_a 调用
                        print("寻路中找到玩家坐标",players,"寻路中找到新的安全点",new_safe)
                        if has_players:
                            if new_safe is not None:
                                last_safe_with_players = new_safe
                            last_players = list(players)
                        elif last_safe_with_players is not None and new_safe == (人物x, 人物y):
                            new_safe = last_safe_with_players
                        # print("重算后的坐标",new_safe)
                        if new_safe is not None:  # 找到了新的安全点
                            diff = max(abs(new_safe[0] - current_goal[0]), abs(new_safe[1] - current_goal[1]))  # 新旧目标差距
                            should_repath = diff >= 3 or (has_players and new_safe != current_goal)
                            if should_repath:  # 变化太小就不重算，避免抖动（目标频繁变动）
                                new_path = ai算法.a_star_eight(  # 从当前位置到新安全点重新跑一遍 A*，得到新路径
                                    start_x=人物x,  # A* 起点 x
                                    start_y=人物y,  # A* 起点 y
                                    end_x=new_safe[0],  # A* 终点 x（安全点）
                                    end_y=new_safe[1],  # A* 终点 y（安全点）
                                    img_path=frame,  # A* 使用的地图栅格（带风险/障碍信息）
                                    **a_star_kwargs,  # A* 额外参数（安全权重、步长等）
                                )  # 结束 A* 计算

                                if new_path:  # A* 成功返回新路径
                                    path = new_path  # 替换当前跟随的路径
                                    end_x, end_y = path[-1]  # 更新终点
                                    current_goal = (end_x, end_y)  # 记录新的目标终点
                                    idx = 0  # 重置路径索引（从新路径的起点开始跟随）
                                    last_idx = 0  # 同步重置 last_idx，避免误判“无进展”
                                    last_dist_to_next = None  # 清空距离历史，重新开始进展判断
                                    last_progress_time = time.time()  # 重置进展时间，避免立刻触发卡点
                                    print("终点更新为:",end_x,end_y)

                                    continue  # 进入下一轮循环，用新路径驱动行走
                                if has_players:
                                    print("检测到玩家但重算路径失败，停止沿旧路径移动")
                                    return road_list
            if max(abs(人物x - end_x), abs(人物y - end_y)) <= end_threshold:  # 已经到达（或足够接近）终点
                if right_down:  # 如果正在按住右键持续走
                    controller.right_up()  # 先松开右键，避免人物继续走偏
                break  # 跳出主循环，准备正常结束

            idx, dist_to_path = _nearest_index_along_path(  # 纠偏：在 idx 附近找一个离当前位置最近的路径点作为新的 idx
                path,  # 当前路径
                (人物x, 人物y),  # 当前位置
                idx,  # 从当前 idx 开始向前搜索
                max_lookahead=max_lookahead,  # 向前搜索窗口大小
            )  # 结束纠偏计算

            if repath_to_end and dynamic_repath and update_map_fn is not None:
                # 右键长按跑步时可能出现“跨点/转向慢导致跑偏”，用偏离路径阈值触发快速纠偏
                if dist_to_path >= 2:
                    off_path_cnt += 1
                else:
                    off_path_cnt = 0
                if off_path_cnt >= 3 and (time.time() - last_repath_time) >= 0.2:
                    if right_down:
                        controller.right_up()
                        right_down = False
                    last_repath_time = time.time()
                    try:
                        frame, _ = update_map_fn(dm, controller,img)
                        new_path = ai算法.a_star_eight(
                            start_x=人物x,
                            start_y=人物y,
                            end_x=fixed_end[0],
                            end_y=fixed_end[1],
                            img_path=frame,
                            **a_star_kwargs,
                        )
                        if new_path:
                            path = new_path
                            end_x, end_y = fixed_end
                            current_goal = fixed_end
                            idx = 0
                            last_idx = 0
                            last_dist_to_next = None
                            last_progress_time = time.time()
                            off_path_cnt = 0
                            continue
                    except Exception:
                        pass

            if (not strict_end) and idx >= len(path) - 1:  # 非严格到点时，走到路径末尾就做一次“兜底判断”
                end_dist = max(abs(人物x - end_x), abs(人物y - end_y))  # 再算一次与终点的距离
                if end_dist <= end_threshold:  # 如果其实已经接近终点
                    if right_down:  # 若右键仍按着
                        controller.right_up()  # 松开右键
                    break  # 认为到达，正常结束
                else:  # 否则说明“路径走完了但人还没到”，属于异常/卡点/地图变化
                    if repath_to_end and dynamic_repath and update_map_fn is not None:
                        if right_down:
                            controller.right_up()
                            right_down = False
                        last_repath_time = time.time()
                        frame, _ = update_map_fn(dm, controller,img)
                        new_path = ai算法.a_star_eight(
                            start_x=人物x,
                            start_y=人物y,
                            end_x=fixed_end[0],
                            end_y=fixed_end[1],
                            img_path=frame,
                            **a_star_kwargs,
                        )
                        if new_path:
                            path = new_path
                            end_x, end_y = fixed_end
                            current_goal = fixed_end
                            idx = 0
                            last_idx = 0
                            last_dist_to_next = None
                            last_progress_time = time.time()
                            off_path_cnt = 0
                            continue
                    if right_down:  # 为安全起见先松开右键
                        controller.right_up()  # 松开右键
                    print(f"{controller}结束寻路1")
                    return road_list  # 提前返回，让上层重新规划路径

            if idx >= len(path) - 1:  # idx 已经在末尾（或超出）时，保证还能取到“当前/下一点”
                if len(path) >= 2:  # 正常情况：路径至少两个点
                    当前路径点 = path[-2]  # 把倒数第二个点当作当前点
                    下一点 = path[-1]  # 最后一个点当作下一点（终点）
                else:  # 极端情况：路径只有一个点（起点==终点）
                    当前路径点 = path[-1]  # 当前点就是唯一的点
                    下一点 = path[-1]  # 下一点也只能是它自己
            else:  # idx 仍在路径中间，正常取相邻两个点
                当前路径点 = path[idx]  # 当前跟随的路径点
                下一点 = path[idx + 1]  # 下一个要前往的路径点

            追踪点 = 下一点
            if pursuit_mode:
                追踪点, _ = _select_pursuit_point(
                    path,
                    (人物x, 人物y),
                    idx,
                    pursuit_lookahead,
                    pursuit_window,
                    prefer_turn=pursuit_turn,
                )

            dist_to_next = max(abs(人物x - 下一点[0]), abs(人物y - 下一点[1]))  # 当前位置到“下一点”的距离
            now = time.time()  # 当前时间（用于卡住判断）
            progressed = False  # 标记：本轮是否有“前进/接近目标”的进展
            if idx != last_idx:  # 路径索引推进了，说明确实在沿着路径前进
                progressed = True  # 视为有进展
            elif last_dist_to_next is None or dist_to_next < last_dist_to_next:  # 即使 idx 没变，但距离变小也算接近
                progressed = True  # 视为有进展

            if progressed:  # 本轮有进展：更新进展状态
                last_progress_time = now  # 记录“最近一次有进展”的时间
                last_dist_to_next = dist_to_next  # 记录当前距离，供下次比较
                last_idx = idx  # 记录当前 idx，供下次判断是否推进
            elif now - last_progress_time > stuck_timeout:  # 长时间没进展：认为卡住/被挡
                if right_down:  # 若右键按住中
                    controller.right_up()  # 先松开右键，避免持续走造成更大偏差
                    right_down = False
                if repath_to_end and dynamic_repath and update_map_fn is not None:
                    last_repath_time = now
                    try:
                        frame, _ = update_map_fn(dm, controller,img)
                        new_path = ai算法.a_star_eight(
                            start_x=人物x,
                            start_y=人物y,
                            end_x=fixed_end[0],
                            end_y=fixed_end[1],
                            img_path=frame,
                            **a_star_kwargs,
                        )
                        if new_path:
                            path = new_path
                            end_x, end_y = fixed_end
                            current_goal = fixed_end
                            idx = 0
                            last_idx = 0
                            last_dist_to_next = None
                            last_progress_time = time.time()
                            off_path_cnt = 0
                            continue
                    except Exception:
                        pass
                print(f"{controller}结束寻路2")
                return road_list  # 提前返回，让上层决定重算/换策略

            直线段 = False  # 标记：当前位置附近是否属于“直线行走段”
            if idx + 2 < len(path):  # 至少还剩 3 个点，才能判断三点是否共线/可直连
                直线段 = ai算法.check_the_connection(当前路径点, 下一点, path[idx + 2])  # 判断 (当前,下一,下下) 是否构成直线段

            straight_lock_dir = None
            if right_only and right_only_straight_lock and update_map_fn is not None:
                end_idx, straight_dir = _straight_segment_end(path, idx)
                if straight_dir != (0, 0) and end_idx > idx:
                    line_offset = _line_offset((人物x, 人物y), path[idx], straight_dir)
                    if line_offset <= straight_lock_deviation:
                        straight_end = path[end_idx]
                        dist_to_end = max(abs(人物x - straight_end[0]), abs(人物y - straight_end[1]))
                        if dist_to_end > straight_lock_release_dist:
                            if (
                                last_straight_map is None
                                or (now - last_straight_map_time) >= straight_lock_check_interval
                            ):
                                try:
                                    last_straight_map, _ = update_map_fn(dm, controller,img)
                                    last_straight_map_time = now
                                except Exception:
                                    last_straight_map = None
                            if last_straight_map is not None and _forward_clear(
                                last_straight_map,
                                (人物x, 人物y),
                                straight_end,
                                straight_dir,
                            ):
                                straight_lock_dir = straight_dir

            if right_only:
                if straight_lock_dir is not None:
                    target_x = 人物x + straight_lock_dir[0]
                    target_y = 人物y + straight_lock_dir[1]
                else:
                    target_x, target_y = 追踪点
                目标方位 = controller.判断方位(target_x, target_y, 人物x, 人物y)
                if (not right_down) or (目标方位 != last_dir) or (now - last_mouse_move_time >= right_refresh_interval):
                    controller.移动方位不点击(目标方位)
                    last_mouse_move_time = now
                    if not right_down:
                        controller.right_down()
                        right_down = True
                last_dir = 目标方位
            else:
                if 直线段:  # 直线段：更适合“按住右键持续走”，减少频繁点击导致的抖动
                    if pursuit_mode and dist_to_path > 1:
                        目标方位 = controller.判断方位(追踪点[0], 追踪点[1], 人物x, 人物y)
                    else:
                        目标方位 = controller.判断方位(追踪点[0], 追踪点[1], 当前路径点[0], 当前路径点[1])  # 用路径点推算方向更稳定
                    if (not right_down) or (目标方位 != last_dir) or (now - last_mouse_move_time >= right_refresh_interval):  # 没按右键或方向变了才需要更新指令
                        controller.移动方位不点击(目标方位)  # 移动到该方向（不左键点击）
                        last_mouse_move_time = now
                        if not right_down:  # 如果还没进入“右键按住走路”模式
                            controller.right_down()  # 按下右键开始持续走
                            right_down = True  # 记录状态：右键已按下
                else:  # 非直线段：用“左键点击方位”逐步转向更可靠
                    目标方位 = controller.判断方位(追踪点[0], 追踪点[1], 人物x, 人物y)  # 用当前位置到追踪点计算方向，保证转向准确
                    if right_down:  # 若之前处于右键按住状态
                        controller.right_up()  # 松开右键，避免持续走错方向
                        right_down = False  # 更新状态
                    controller.左键点击方位_走路(目标方位)  # 左键点一下对应方向，让人物迈向下一点

                last_dir = 目标方位  # 记录本次目标方位，供下一轮去重判断

            if (  # 如果已经“够近”下一点，则推进 idx，开始追下一个点
                max(abs(人物x - 下一点[0]), abs(人物y - 下一点[1])) <= reach_threshold  # 到下一点的距离达到阈值
                and idx < len(path) - 1  # 且 idx 还没到路径末尾
            ):
                idx += 1  # 推进到下一个路径点索引

            controller.延时(sleep_interval)  # 每步延时：让操作节奏更像人，也降低 CPU/识别压力

        bad_cells.clear()  # 正常结束时同样清理坏格子集合
        print(f"{controller}结束寻路")
        return road_list  # 返回“实际走过的点”，可用于可视化对比 path 与实际偏差
    except Exception as e:  # 捕获异常避免线程直接崩溃
        # 记录异常，方便排查
        print(repr(e))  # 打印异常类型/信息
        traceback.print_exc()  # 打印堆栈，便于定位是哪一步出错
    finally:  # 无论正常/异常/提前返回，都确保松开右键
        controller.right_up()  # 防止右键卡住导致人物一直走/影响后续操作
        if owner_acquired:
            controller.release_input_owner()  # 改: 释放输入占用权
