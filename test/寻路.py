import time
import traceback
from threading import Event
from typing import Callable, List, Optional, Tuple, Union, Any
from public import *
import ai算法
import config
import cv2
import dm_utils


def 地图上绘制怪物点(img: Any, master_location: list):
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
    if config.DEBUG_LOG:
        print(怪物图片路径)
        print(怪物路径列表)
        print(怪物图片路径_不包括宝宝)

def 更新地图_怪物点(dm: object, controller: object):
    map_img = cv2.imread(config.MAP_IMAGE_PATH)
    怪物列表_包括宝宝 = 识别怪物坐标(dm, controller, 543, 98, 1370, 714, 怪物图片路径, config.MONSTER_LIST_SIM)
    if 怪物列表_包括宝宝:
        map_img = 地图上绘制怪物点(map_img, 怪物列表_包括宝宝)
    return map_img


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
    pb, pg, pr = config.PLAYER_COLOR
    for (mx,my) in 玩家坐标列表:
        img[my, mx][0] = pb
        img[my, mx][1] = pg
        img[my, mx][2] = pr
    return img


def update_map_fn(dm: object,controller: object):
    map_img = cv2.imread(config.MAP_IMAGE_PATH)
    玩家坐标列表 = dm_utils.scan_player(
        dm,
        controller.屏幕坐标转游戏坐标,
    )
    if 玩家坐标列表:
        print("玩家坐标列表", 玩家坐标列表)
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


def walk_path(
    path: List[tuple],  # 规划好的路径点列表（游戏坐标/格子坐标），例如 [(x1,y1),(x2,y2)...]
    *,  # 强制后续参数使用“关键字传参”，避免不同线程/调用方位置传参造成混淆
    dm: object,
    get_pos: Callable[[object,Union[None, tuple]], tuple],  # 获取人物当前坐标的回调函数；需返回 (x, y)，识别失败返回 (-1, -1)
    controller,  # 行走控制器：封装“判断方位/鼠标按下抬起/左键点方向/延时”等具体操作实现
    bad_cells: set,  # 共享的“坏格子/禁走点”集合；本函数会在退出时清空，便于上层下一次寻路复用
    stop_event: Union[Event, tuple[Event, ...], None] = None,  # 接收 Event 或者元组，或者 None
    small_area_checker: Optional[Callable[[object], bool]] = None,  # 可选：小范围找怪/风险检测；返回 True 时提前退出
    big_area_checker: Optional[Callable[[object], bool]] = None,  # 可选：大范围找怪/风险检测；返回 True 时提前退出
    update_map_fn: Optional[Callable[[object,object], Tuple[Any, List[tuple]]]] = None,  # 可选：刷新地图与玩家点（用于动态重寻路）
    end_threshold: int = 0,  # 到达终点的距离阈值（切比雪夫距离）；0 表示必须精确踩到终点
    reach_threshold: int = 0,  # 到达“下一个路径点”的距离阈值；满足后 idx 才会推进到下一个点
    max_lookahead: int = 6,  # 纠偏窗口：从当前 idx 起向前最多看 N 个点，选一个离当前位置最近的点作为新 idx
    sleep_interval: float = 0.05,  # 每次发出移动指令后的间隔（秒）；越小越灵敏但可能抖动/更吃 CPU
    dynamic_repath: bool = False,  # 是否动态重寻路：边走边用 update_map_fn 刷新地图，并重新算更安全的目标/路径
    repath_interval: float = 0.5,  # 动态重寻路最小间隔（秒）；避免过于频繁地刷新/重算
    repath_radius: Optional[int] = None,  # 动态重寻路 safe_point 的搜索半径（格子）；None 则使用配置默认值
    repath_selection_method: Optional[int] = None,  # 动态重寻路 safe_point 的选择策略；None 则使用配置默认值
    a_star_kwargs: Optional[dict] = None,  # 动态重寻路时传给 ai算法.a_star_eight 的参数（foot_len/safety_weight 等）
):
    """
    统一的沿路径行走逻辑。允许注入坐标获取、控制器、地图更新与终止事件，便于多线程复用。
    """
    if controller is None:  # 外部没传控制器时，默认用“监控控制”（避免 None 导致调用失败）
        controller = 监控控制  # 监控控制里封装了方位判断、鼠标按下/抬起、左键点方向等动作

    if not path:  # 没有路径点就无需行走
        return  # 直接返回 None（上层可据此判断无需移动）

    cur = get_pos(dm)
    if cur[0] < 0 or cur[1] < 0:  # 坐标识别失败（约定：负数表示失败）
        print("警告: 入场时无法识别人物坐标，放弃本次行走")  # 打印提示便于定位识别问题
        return  # 放弃本次走路，让上层决定是否重试/重算

    start_dist = max(abs(cur[0] - path[0][0]), abs(cur[1] - path[0][1]))  # 人物与路径起点的切比雪夫距离
    if start_dist > 5:  # 起点偏差过大通常意味着路径已经过期/人物不在预期位置
        print("警告: 人物与路径起点偏差太大，视为无效路径，退出，让上层重新算")  # 交给上层重新 A* 规划
        return  # 直接退出，不做“强行追起点”的移动

    next_move_cfg = Parameter.Ai.next_move  # next_move（安全点/逃离点）相关配置

    if repath_radius is None:  # 调用方没显式指定动态重寻路的搜索半径
        repath_radius = next_move_cfg["search_radius_default"] or 25  # 用配置默认值，缺省再回退到 25
    if repath_selection_method is None:  # 调用方没显式指定 safe_point 选择策略
        repath_selection_method = next_move_cfg["selection_method_default"] or 1  # 用配置默认值，缺省再回退到 1

    if a_star_kwargs is None:  # 调用方没传动态重寻路使用的 A* 参数
        a_star_kwargs = Parameter.Ai.astar  # A* 寻路相关配置

    road_list: List[Coord] = []  # 记录“实际走过”的人物坐标点（用于调试/可视化/回放）
    end_x, end_y = path[-1]  # 当前路径的终点（会在动态重寻路时更新）
    idx = 0  # 当前跟随的路径点索引（指向 path[idx]）
    right_down = False  # 标记：当前是否处于“按住右键持续走”的状态（直线段更平滑）
    last_dir = None  # 上一次移动的目标方位（用于减少重复发指令）
    last_idx = idx  # 上一次循环时的 idx（用于判断是否有前进）
    last_dist_to_next = None  # 上一次循环时“到下一点”的距离（用于判断是否在接近目标）
    last_progress_time = time.time()  # 上一次确认“有进展”的时间戳（用于卡住检测）
    stuck_timeout = 4.0  # 卡住超时阈值：超过该时间仍无进展则认为卡点，提前返回
    current_goal = (end_x, end_y)  # 记录当前目标终点（动态重寻路时用于判断目标是否变化）
    last_repath_time = 0.0  # 上一次执行动态重寻路的时间戳
    strict_end = end_threshold == 0  # end_threshold==0 表示“严格到点”：必须走到最后一个格子

    print(f"{controller}开始寻路")  # 日志：开始执行 walk_path
    try:  # 主循环包一层 try，保证异常时也会释放按键/鼠标
        while True:  # 一直走到终点/提前退出条件满足/卡住为止
            # if stop_event is not None and stop_event.is_set():  # 外部请求中断（多线程安全退出）
            #     print("收到 stop_event 中断信号, 退出沿路径控制人物行走")  # 日志：收到停止信号
            #     bad_cells.clear()  # 清空坏格子集合，避免污染下一次寻路
            #     return road_list  # 返回已走过的实际路径点，便于上层做可视化/纠错

            # print("鼠标寻路中")

            if stop_event is not None:
                for ev in stop_event:
                    if ev is not None and ev.is_set():
                        print(f"收到 {controller} 中断信号, 退出沿路径控制人物行走")  # 日志：收到停止信号
                        bad_cells.clear()  # 清空坏格子集合，避免污染下一次寻路
                        return road_list  # 返回已走过的实际路径点，便于上层做可视化/纠错

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
                    frame, players = update_map_fn(dm,controller)  # 刷新地图，并识别玩家点（用于避让/逃离）`````````````````````````
                    new_safe = ai算法.next_move_a(  # 基于当前局势计算一个“更安全”的临时目标点
                        (人物x, 人物y),  # 当前人物位置
                        frame,  # 当前地图/风险栅格（含玩家/怪物等信息）
                        (人物x, 人物y),  # 搜索中心（通常就是当前位置）
                        repath_radius,  # 搜索半径
                        repath_selection_method,  # safe_point 选择策略
                        players=players,  # 传入玩家点列表，AI 可据此躲人
                        escape_mode="away",  # 逃离模式：倾向于“远离”威胁源
                    )  # 结束 next_move_a 调用
                    print("重算后的坐标",new_safe)
                    if new_safe is not None:  # 找到了新的安全点
                        diff = max(abs(new_safe[0] - current_goal[0]), abs(new_safe[1] - current_goal[1]))  # 新旧目标差距
                        if diff >= 3:  # 变化太小就不重算，避免抖动（目标频繁变动）
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
            if max(abs(人物x - end_x), abs(人物y - end_y)) <= end_threshold:  # 已经到达（或足够接近）终点
                if right_down:  # 如果正在按住右键持续走
                    controller.right_up()  # 先松开右键，避免人物继续走偏
                break  # 跳出主循环，准备正常结束

            idx, _ = _nearest_index_along_path(  # 纠偏：在 idx 附近找一个离当前位置最近的路径点作为新的 idx
                path,  # 当前路径
                (人物x, 人物y),  # 当前位置
                idx,  # 从当前 idx 开始向前搜索
                max_lookahead=max_lookahead,  # 向前搜索窗口大小
            )  # 结束纠偏计算

            if (not strict_end) and idx >= len(path) - 1:  # 非严格到点时，走到路径末尾就做一次“兜底判断”
                end_dist = max(abs(人物x - end_x), abs(人物y - end_y))  # 再算一次与终点的距离
                if end_dist <= end_threshold:  # 如果其实已经接近终点
                    if right_down:  # 若右键仍按着
                        controller.right_up()  # 松开右键
                    break  # 认为到达，正常结束
                else:  # 否则说明“路径走完了但人还没到”，属于异常/卡点/地图变化
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
                print(f"{controller}结束寻路2")
                return road_list  # 提前返回，让上层决定重算/换策略

            直线段 = False  # 标记：当前位置附近是否属于“直线行走段”
            if idx + 2 < len(path):  # 至少还剩 3 个点，才能判断三点是否共线/可直连
                直线段 = ai算法.check_the_connection(当前路径点, 下一点, path[idx + 2])  # 判断 (当前,下一,下下) 是否构成直线段

            if 直线段:  # 直线段：更适合“按住右键持续走”，减少频繁点击导致的抖动
                目标方位 = controller.判断方位(下一点[0], 下一点[1], 当前路径点[0], 当前路径点[1])  # 用路径点推算方向更稳定
                if (not right_down) or (目标方位 != last_dir):  # 没按右键或方向变了才需要更新指令
                    controller.移动方位不点击(目标方位)  # 移动到该方向（不左键点击）
                    if not right_down:  # 如果还没进入“右键按住走路”模式
                        controller.right_down()  # 按下右键开始持续走
                        right_down = True  # 记录状态：右键已按下
            else:  # 非直线段：用“左键点击方位”逐步转向更可靠
                目标方位 = controller.判断方位(下一点[0], 下一点[1], 人物x, 人物y)  # 用当前位置到下一点计算方向，保证转向准确
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