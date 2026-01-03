import sys
import time
from public import *
import config

import cv2
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QEvent
from PyQt5.QtGui import QImage, QPixmap
import traceback
from 新大漠插件 import *
import ai算法
import ai_visual
from kmNet类封装2 import *
from changliang11 import changliang as cl
import dm_utils  # OCR 通用工具，避免重复解析逻辑。
from app.loot import LootFeature
import 寻路




init_runtime()

打怪控制 = 游戏控制器(delay_func=打怪延时)

血量控制 = 游戏控制器(delay_func=血量延时)

监控控制 = 游戏控制器(delay_func=监控延时)

界面控制 = 游戏控制器(delay_func=界面延时)

map_path = None

# with open(r"./pic/guaiwu/guaiwu.txt",'r',encoding='UTF-8') as f:
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

with open(config.ITEM_NAME_PATH,'r',encoding='ANSI') as f:
    物品名称路径 = f.read()
    物品名称路径 = 物品名称路径.replace('\n','|')+config.ITEM_NAME_EXTRA
    物品名称列表 = 物品名称路径.split('|')
    if config.DEBUG_LOG:
        print(物品名称路径)

def 设置字库(大漠对象):
    """集中设置字库，避免多个地方写错路径导致 OCR 不一致。"""
    大漠对象.SetDict(0, config.DICT_NUM_PATH)
    大漠对象.SetDict(1, config.DICT_SYS_PATH)
    大漠对象.SetDict(2, config.DICT_PLAYER_PATH)
    大漠对象.SetDict(3, config.被发现字库)


# 记录捡取物品的坏点坐标,防止物品是其他人的,不能拾取,人物来回往该物品地址寻路
wupin_list = set()

# 记录每次寻路找怪的坏点坐标,如果到达就清空集合,如果没有达到,就存储在集合中,防止下次寻路再以此点作为终点
bad_cells = set()

# 设置清空记录已捡取物品集合时间
CLEAR_INTERVAL = 120  # 间隔多少秒清空一次
last_clear_time = time.time()  # 上次清空时间

class WorkerThread(QThread):

    caozuo = pyqtSignal(str)
    jiankong = pyqtSignal(str)
    xianshi = pyqtSignal(object)

    def __init__(self,大漠对象,句柄,线程名):
        super().__init__()
        self.大漠对象 = 大漠对象
        设置字库(大漠对象)
        self.句柄 = 句柄
        self.线程名 = 线程名
        # self.map_img = cv2.imread(config.MAP_IMAGE_PATH)
        self.宝宝在身边未攻击次数 = 0

    def run(self):
        窗口标题 = self.大漠对象.GetWindowTitle(self.句柄)

        if self.线程名 == '打怪线程':
            self.caozuo.emit(f"线程名:{self.线程名}|{窗口标题}|线程启动成功")
            self.打怪线程()
            # self.押镖()

        elif self.线程名 == '血量线程':
            self.jiankong.emit(f"线程名:{self.线程名}|{窗口标题}|线程启动成功")
            self.血量线程()

        # elif self.线程名 == '监控线程':
        #     self.caozuo.emit(f"线程名:{self.线程名}|{窗口标题}|线程启动成功")
        #     self.监控线程()

        elif self.线程名 == '界面线程':
            self.jiankong.emit(f"线程名:{self.线程名}|{窗口标题}|线程启动成功")
            self.界面线程()


    def 界面线程(self):
        global map_path
        接管中 = False  # 改: 界面线程接管状态
        盟重已处理 = False  # 改: 避免盟重反复执行回城操作
        while True:
            try:
                # print("1111")
                z, x, y = self.大漠对象.AiFindPic(*config.开始区域)
                if z != -1:
                    if not 接管中:
                        mark_walk_stopped(打怪_stop_event, 血量_stop_event, 监控_stop_event)  # 改: 先打标记再暂停
                        打怪_血量_监控_event.clear()
                        界面控制.acquire_input_owner()  # 改: 接管时独占输入
                        接管中 = True
                        盟重已处理 = False
                    界面控制.move_with_left_click(x,y,0,5,0,3)
                    界面控制.延时(2000)
                z, x, y = self.大漠对象.AiFindPic(*config.确定区域)
                if z != -1:
                    if not 接管中:
                        mark_walk_stopped(打怪_stop_event, 血量_stop_event, 监控_stop_event)  # 改: 先打标记再暂停
                        打怪_血量_监控_event.clear()
                        界面控制.acquire_input_owner()  # 改: 接管时独占输入
                        接管中 = True
                        盟重已处理 = False
                    界面控制.move_with_left_click(x,y,0,5,0,3)
                    界面控制.延时(2000)
                z, x, y = self.大漠对象.AiFindPic(*config.游戏中标志区域)
                if z != -1:
                    map_name = self.识别地图()
                    map_path_new = config.map_dict.get(map_name)  # 改: OCR 异常时避免 KeyError
                    if map_path_new:
                        map_path = map_path_new

                    if map_name == "盟重省":
                        if not 接管中:
                            mark_walk_stopped(打怪_stop_event, 血量_stop_event, 监控_stop_event)  # 改: 先打标记再暂停
                            打怪_血量_监控_event.clear()
                            界面控制.acquire_input_owner()  # 改: 接管时独占输入
                            接管中 = True
                            盟重已处理 = False
                        if not 盟重已处理:
                            if map_path_new:
                                img = cv2.imread(map_path_new)
                                self.回城操作(img,界面控制)
                                盟重已处理 = True  # 改: 盟重操作只做一次，等待地图变化
                    else:
                        盟重已处理 = False
                        if 接管中 and map_path_new:
                            打怪_血量_监控_event.set()  # 改: 满足“游戏中标志+非盟重”后恢复
                            接管中 = False
                            if 界面控制.is_input_owner():
                                界面控制.right_up()  # 改: 仅在拥有输入时收尾
                                界面控制.release_input_owner()
                # 游戏中标志未出现时，如果已接管则保持暂停（不做恢复）
                界面控制.延时(100)

            except Exception as e:
                print(repr(e))  # 输出异常的类型
                traceback.print_exc()
                if 界面控制.is_input_owner():
                    界面控制.right_up()  # 改: 异常时安全释放
                    界面控制.release_input_owner()
                    接管中 = False
                continue

    def 识别地图(self):
            self.大漠对象.UseDict(1)
            text = self.大漠对象.Ocr(*config.识别地图区域)
            for i, char in enumerate(text):
                if char in ':`.,' or not ('\u4e00' <= char <= '\u9fff'):
                    result = text[:i]
                    break
            else:
                result = text
            return result


    def 监控线程(self):

        cv2.namedWindow("demo_case")
        cv2.moveWindow("demo_case", 1920, 0)
        cv2.namedWindow("demo_case1")
        cv2.moveWindow("demo_case1", 1920, 700)
        global map_path
        set_thread_restart_events(监控_stop_event)  # 改: 注册监控线程的重启事件
        while True:
            try:
                监控控制.延时(0)  # 改: 统一等待运行事件，暂停时不往下跑

                s = time.perf_counter()
                # 全地图循环扫描玩家,如果有玩家,就执行后面的操作躲避玩家,否则就继续循环
                player_pos = dm_utils.ocr_player_pos(self.大漠对象)
                players = dm_utils.scan_player(
                    self.大漠对象,
                    监控控制.屏幕坐标转游戏坐标,
                    player_pos=player_pos,
                )
                if players:
                    # frame = self.map_img.copy()
                    map_img = cv2.imread(map_path)
                    frame = 寻路.地图上绘制玩家点(map_img, players)
                    人物x,人物y = player_pos
                    safe_point = ai算法.next_move_a(
                        (人物x,人物y),
                        frame,
                        (人物x,人物y),
                        40,
                        1,
                        escape_mode="free"
                    )
                    if safe_point is not None:
                        ai_visual.visualize_move(
                            frame, (人物x, 人物y), safe_point,
                            search_center=(人物x, 人物y), search_radius=40,
                            show_risk=True, scale=7, window="demo_case",
                            outfile="viz_demo.png",view_range=50
                        )
                        cv2.waitKey(1)
                        path = ai算法.a_star_eight(人物x, 人物y, safe_point[0], safe_point[1], frame, 2, 1, 1, 1, 1)
                        if path is not None:
                            ai_visual.visualize_grid_and_path(
                                frame,path,
                                win_name="demo_case1",
                                cell_size=7,
                                center_pos=(人物x, 人物y),
                                view_range=40,
                            )
                            cv2.waitKey(1)
                            with 监控控制.input_owner():  # 改: 抢占时独占输入
                                mark_walk_stopped(打怪_stop_event, 血量_stop_event)  # 改: 先打标记再暂停
                                pause_all()
                                监控控制.键盘点击(41)  # esc
                                print("监控线程抢占开始,首次安全点坐标:",safe_point)
                                print("监控线程抢占开始,安全点路径:",path)
                                寻路.walk_path(
                                    path,
                                    img=map_img,
                                    dm=self.大漠对象,
                                    get_pos=dm_utils.ocr_player_pos,
                                    controller=监控控制,
                                    bad_cells=bad_cells,
                                    end_threshold=1,
                                    reach_threshold=1,
                                    update_map_fn=寻路.update_map_fn,
                                    dynamic_repath=True,
                                    repath_radius=40,
                                    stop_event=(监控_stop_event,)
                                )
                                print("监控线程抢占结束")
                                resume_all()

                # e = time.perf_counter()
                # t = e - s
                # print("找字用时:", t)
                监控控制.延时(100)
            except RestartLoop:
                监控_stop_event.clear()  # 改: 清掉重启标记，回到循环头
                监控控制.right_up()  # 改: 防止右键卡住
                continue


    def 血量线程(self):
        cv2.namedWindow("test2")
        cv2.moveWindow("test2",1920,0)
        cv2.namedWindow("path1")
        cv2.moveWindow("path1", 1920, 350)
        cv2.namedWindow("path2")
        cv2.moveWindow("path2", 1920, 700)
        global map_path
        set_thread_restart_events(血量_stop_event)  # 改: 注册血量线程的重启事件
        try:
            while True:
                try:
                    血量控制.延时(0)  # 改: 统一等待运行事件，暂停时不往下跑
                    if 血量_stop_event.is_set():
                        raise RestartLoop()  # 改: 被抢占后强制回到循环头

                    当前血量, 最大血量 = dm_utils.ocr_hp(self.大漠对象)
                    self.jiankong.emit(f"当前血量:{当前血量}|最大血量:{最大血量}")

                    if 当前血量 == 0:
                        self.jiankong.emit("人物已死亡,需要重新登录游戏")
                        time.sleep(0.1)
                        continue
                    if 当前血量 < 0 or 最大血量 <= 0:
                        # OCR 失败或分母异常时跳过本轮，避免误判与除零
                        time.sleep(0.1)
                        continue

                    血量比例 = 当前血量/最大血量
                    if 0 < 血量比例 < 0.95:
                        mark_walk_stopped(血量_打怪_stop_event)  # 改: 先打标记再暂停
                        pause_combat()  # 暂停打怪线程
                        with 血量控制.input_owner():  # 改: 抢占时独占输入
                            血量控制.键盘点击(41)  # esc
                            print("血量线程抢占开始")
                            s = time.perf_counter()

                            # 找安全坐标点
                            人物x,人物y = dm_utils.ocr_player_pos(self.大漠对象)
                            if 人物x < 0 or 人物y < 0:
                                # 坐标识别失败时不进行寻路，避免走到异常位置
                                time.sleep(0.1)
                                continue
                            z, x, y = self.大漠对象.AiFindPic(150,119,1719,867, config.PET_PIC_PATH, config.PET_PIC_SIM, 0)
                            # z, x, y = self.大漠对象.AiFindPic(543, 98, 1370, 714, r"./pic/guaiwu/单机_宝宝.bmp", 0.60, 0)
                            # 找到宝宝坐标,以宝宝坐标为中心找安全坐标点
                            map_img = cv2.imread(map_path)
                            frame,_ = 寻路.更新地图_怪物点(self.大漠对象,血量控制,map_img)

                            if z != -1:
                                宝宝x,宝宝y = 血量控制.屏幕坐标转游戏坐标(人物x,人物y,x+14,y+34)
                                # 血量在75%以上时,安全点搜索半径为3,小范围选择安全坐标点
                                if 0.75 < 血量比例 < 0.95:
                                    bin_safe_point = ai算法.next_move_a((人物x,人物y),frame,(宝宝x,宝宝y),2,1)
                                    ai_visual.visualize_move(frame, (人物x, 人物y), bin_safe_point,
                                                             search_center=(宝宝x, 宝宝y),search_radius=2, scale=7, window="test2",
                                                             outfile="viz_demo.png", view_range=25)
                                # 血量在75%以下时,安全点搜索半径为全图,大范围选择安全坐标点
                                elif 0 < 血量比例 <= 0.75:
                                    bin_safe_point = ai算法.next_move_a((人物x, 人物y), frame, (宝宝x,宝宝y), None,1)
                                    ai_visual.visualize_move(frame,(人物x,人物y),bin_safe_point,search_center=(宝宝x,宝宝y),scale=7,window="test2",outfile="viz_demo.png",view_range=25)
                            else:
                                # 未找到宝宝坐标,以人物坐标为中心找安全坐标点
                                人物x,人物y = dm_utils.ocr_player_pos(self.大漠对象)
                                if 0.75 < 血量比例 < 0.95:
                                    bin_safe_point = ai算法.next_move_a((人物x,人物y),frame,(人物x, 人物y),5,1)
                                    ai_visual.visualize_move(frame, (人物x, 人物y), bin_safe_point,
                                                             search_center=(人物x, 人物y),search_radius=5, scale=7, window="test2",
                                                             outfile="viz_demo.png", view_range=25)
                                elif 0 < 血量比例 <= 0.75:
                                    bin_safe_point = ai算法.next_move_a((人物x, 人物y), frame, (人物x, 人物y), None,1)
                                    ai_visual.visualize_move(frame, (人物x, 人物y), bin_safe_point,
                                                             search_center=(人物x, 人物y), scale=7, window="test2",
                                                             outfile="viz_demo.png", view_range=25)
                            cv2.waitKey(1)

                            # 寻往安全坐标点
                            if bin_safe_point is not None:

                                frame,_  = 寻路.更新地图_怪物点(self.大漠对象,血量控制,map_img)
                                path = ai算法.a_star_eight(人物x, 人物y, bin_safe_point[0],bin_safe_point[1] ,frame,1,0,1,1,1)
                                print("血量线程安全坐标点:",bin_safe_point)
                                # 围绕着宝宝或者人物坐标点移动到安全位置
                                if path is not None :
                                    ai_visual.visualize_grid_and_path(frame,path,win_name="path1",cell_size=7,center_pos=(人物x,人物y),view_range=25)
                                    cv2.waitKey(1)

                                    ret_path_list = 寻路.walk_path(
                                    path,
                                    img=map_img,
                                    dm=self.大漠对象,
                                    get_pos=dm_utils.ocr_player_pos,
                                    controller=血量控制,
                                    bad_cells=bad_cells,
                                    stop_event=(血量_stop_event,),
                                    end_threshold=1,
                                    reach_threshold=1,
                                    )

                                    ai_visual.visualize_grid_and_path(frame, ret_path_list, win_name="path2", cell_size=7,
                                                                      center_pos=(人物x, 人物y), view_range=25)
                                    cv2.waitKey(1)
                                    e = time.perf_counter()
                                    t = e - s
                                    print('跑到安全点用时:', t)

                                    血量控制.随机延时(100, 300)
                                    # F3隐身,让怪物不要攻击自己
                                    血量控制.键盘点击(60)
                                    # 血量控制.随机延时(1400, 1600)

                    elif 0.95 <= 血量比例 <= 1 and 打怪_event.is_set() != True:
                        print("血量线程抢占结束")
                        resume_combat()  # 继续打怪线程
                    血量控制.延时(10)
                except RestartLoop:
                    血量_stop_event.clear()  # 改: 清掉重启标记，回到循环头
                    血量控制.right_up()  # 改: 防止右键卡住
                    continue

        except Exception as e:
            print(e)
            print(repr(e))
            traceback.print_exc()


    # ==============================
    # 实时主循环
    # ==============================
    def 打怪线程(self):
        try:
            cv2.namedWindow("test1")
            cv2.moveWindow("test1", 1920, 1080)

            global bad_cells               # 记录坏点(找怪时的怪物点)
            global last_clear_time
            global wupin_list              # 记录坏点(找物品时的物品点)
            global map_path
            set_thread_restart_events(打怪_stop_event, 血量_打怪_stop_event)  # 改: 注册打怪线程的重启事件
            while True:
                try:
                    打怪控制.延时(0)  # 改: 统一等待运行事件，暂停时不往下跑
                    if 打怪_stop_event.is_set() or 血量_打怪_stop_event.is_set():
                        raise RestartLoop()  # 改: 被抢占后强制回到循环头
                    # map_img = cv2.imread(config.map_dict["散人之家"])
                    map_img = cv2.imread(map_path)
                    # print(map_path)
                    # 每隔CLEAR_INTERVAL时间,清空wupin_list记录已捡物品的集合
                    now = time.time()
                    if now - last_clear_time >= CLEAR_INTERVAL:
                        if config.DEBUG_LOG:
                            print("清空wupin_list之前", wupin_list)
                        wupin_list.clear()
                        if config.DEBUG_LOG:
                            print("定时清空 wupin_list", wupin_list)
                        last_clear_time = now

                    if 打怪_stop_event.is_set():      # 从其他线程恢复,人物已经远离之前的位置了,不用检测宝宝是否在打怪以及地上是否有物品
                        打怪_stop_event.clear()

                    if 血量_打怪_stop_event.is_set():      # "血量_打怪_stop_event"为True,表示血量线程暂停过又恢复了打怪线程,那么检查宝宝是否打怪和检查周围是否有物品
                        血量_打怪_stop_event.clear()
                        print("从血量线程恢复,检测宝宝是否打怪")
                        self.fighting(150,119,1719,867)
                        打怪控制.延时(1000)                     # 给物品找图时间(物品掉落延迟)
                        self.拾取物品(map_img)
                    if 打怪_stop_event.is_set() or 血量_打怪_stop_event.is_set():
                        continue

                    人物x, 人物y = dm_utils.ocr_player_pos(self.大漠对象)

                    怪物列表_包括宝宝 = 寻路.识别怪物坐标(self.大漠对象,打怪控制,5, 28, 1916, 823,怪物图片路径,config.MONSTER_LIST_SIM)
                    怪物列表_不包括宝宝 = [item for item in 怪物列表_包括宝宝 if '宝宝' not in item[0]]

                    # 全局集合 bad_cells 记录了寻路过程中不能到达的怪物游戏坐标,找最近怪时先筛除掉这些不能到达的怪(不在这些怪中找最近怪)
                    # bad_cells 在 `沿路径控制人物行走()` 寻路函数中会被清空重置,重置条件是寻路函数能正常完成寻路到达终点,bad_cells就会被清空重置
                    if bad_cells:
                        怪物列表_不包括宝宝 = [item for item in 怪物列表_不包括宝宝 if item not in bad_cells]

                    if 怪物列表_不包括宝宝:
                        frame = 寻路.地图上绘制怪物点(map_img, 怪物列表_包括宝宝)

                        # 寻找最近怪物
                        怪物距离 = [np.hypot(mx - 人物x, my - 人物y) for (name,mx, my) in 怪物列表_不包括宝宝]
                        最近怪物 = 怪物列表_不包括宝宝[np.argmin(怪物距离)]
                        bad_cells.add(最近怪物)
                        # print('bad_cells',bad_cells)
                        name ,最近x, 最近y = 最近怪物

                        if config.DEBUG_LOG:
                            print('最近怪:', name, 最近x, 最近y)

                        # A星寻路算法算出路线path
                        path = ai算法.a_star_eight(人物x, 人物y, 最近x, 最近y,frame,1,1,11,0.001,11)
                        if config.DEBUG_LOG:
                            print('最近怪寻路路径', path)

                        # 沿着寻路路径开始寻路
                        ret_path_list = 寻路.walk_path(
                                        path,
                                        img=map_img,
                                        dm=self.大漠对象,
                                        get_pos=dm_utils.ocr_player_pos,
                                        controller=打怪控制,
                                        bad_cells=bad_cells,
                                        stop_event=(打怪_stop_event, 血量_打怪_stop_event),
                                        small_area_checker=寻路.small_area_checker,
                                        end_threshold=1,
                                        reach_threshold=1,
                                        right_only=True,
                                        pursuit_mode=True,
                                        update_map_fn=寻路.更新地图_怪物点,
                                    )

                        if 打怪_stop_event.is_set() or 血量_打怪_stop_event.is_set():
                            continue

                        打怪控制.随机延时(400, 600)
                        # F3隐身,让怪物不要攻击自己
                        打怪控制.键盘点击(60)
                        打怪控制.随机延时(1200, 1300)
                        # 宝宝在人物一边,怪物在人物另一边,宝宝和怪物被人物隔开了,比如人物要进门打怪,但是人物卡在了门口
                        if self.宝宝在身边未攻击次数 > 5:
                            if config.DEBUG_LOG:
                                print('人物卡在门口,把宝宝和怪物分开了,宝宝不能打怪')
                            人物x, 人物y = dm_utils.ocr_player_pos(self.大漠对象)
                            frame,_  = 寻路.更新地图_怪物点(self.大漠对象,打怪控制,map_img)
                            safe_point = ai算法.next_move_a((人物x, 人物y), frame, (人物x, 人物y), None, 1)
                            if config.DEBUG_LOG:
                                print('宝宝在身边未攻击次数大于5后安全点坐标', safe_point)
                            if 'safe_point' not in locals():
                                raise ValueError("宝宝在身边未攻击次数")
                            path = ai算法.a_star_eight(人物x, 人物y, safe_point[0], safe_point[1], frame, 1, 1, 1, 1, 1)
                            寻路.walk_path(
                                path,
                                img=map_img,
                                dm=self.大漠对象,
                                get_pos=dm_utils.ocr_player_pos,
                                controller=打怪控制,
                                bad_cells=bad_cells,
                                stop_event=(打怪_stop_event, 血量_打怪_stop_event),
                                end_threshold = 1,
                                repath_interval = 1,
                            )

                            if 打怪_stop_event.is_set() or 血量_打怪_stop_event.is_set():
                                continue

                        # 宝宝不在人物一格范围内就召唤
                        self.召唤宝宝()
                        self.拾取物品(map_img)
                        if 打怪_stop_event.is_set() or 血量_打怪_stop_event.is_set():
                                continue
                        self.fighting(627, 106, 1300, 712)
                        打怪控制.延时(1000)  # 给物品找图时间(物品掉落延迟)
                        self.拾取物品(map_img)
                        if 打怪_stop_event.is_set() or 血量_打怪_stop_event.is_set():
                                continue
                    # 找图发现周围没有怪后的操作
                    else:
                        人物x,人物y = dm_utils.ocr_player_pos(self.大漠对象)
                        # point = [(80,8),(58,8),(6,20),(9,65)]
                        point = [(18,141),(236,60),(72,357),(265,309)]
                        i = random.randint(0, 3)
                        frame,_  = 寻路.更新地图_怪物点(self.大漠对象,打怪控制,map_img)
                        path = ai算法.a_star_eight(人物x, 人物y, point[i][0], point[i][1], frame, 2, 1, 1, 2, 1)
                        print('周围没有怪了,前往下一个打怪点\n',path)
                        ai_visual.visualize_grid_and_path(frame, path, "test1", 1, center_pos=(人物x, 人物y), view_range=None)
                        cv2.waitKey(1)
                        寻路.walk_path(
                            path,
                            img=map_img,
                            dm=self.大漠对象,
                            get_pos=dm_utils.ocr_player_pos,
                            controller=打怪控制,
                            bad_cells=bad_cells,
                            stop_event=(打怪_stop_event, 血量_打怪_stop_event),
                            small_area_checker=寻路.small_area_checker,
                            big_area_checker=寻路.big_area_checker,
                            end_threshold=1,
                            reach_threshold=1,
                            right_only=True,
                            pursuit_mode=True,
                            update_map_fn=寻路.更新地图_怪物点,
                        )

                    打怪控制.延时(10)
                except RestartLoop:
                    打怪_stop_event.clear()  # 改: 清掉重启标记，回到循环头
                    血量_打怪_stop_event.clear()
                    打怪控制.right_up()  # 改: 防止右键卡住
                    continue
                except Exception as e:
                    continue

            print('退出打怪循环')
            cv2.destroyAllWindows()
        except Exception as e:
            print(e)
            print(repr(e))
            traceback.print_exc()

    # 判断宝宝是否在战斗中
    def fighting(self,x1,y1,x2,y2):
        print('fighiting')
        查找宝宝计次 = 0
        宝宝周围未找到怪物计次 = 0
        for i in range(5000):
            if 打怪_stop_event.is_set() or 血量_打怪_stop_event.is_set():
                print('恢复打怪线程,退出宝宝检测是否战斗中循环')
                raise RestartLoop()  # 改: 被抢占后强制回到主循环头
            宝宝列表 = list()
            宝宝 = list()
            宝宝攻击范围 = [None, None, None, None]  # 0,1是左上角坐标.2,3是右下角坐标

            返回_找图AIEx = self.大漠对象.AiFindPicEx(x1,y1,x2,y2, config.PET_PIC_PATH, config.PET_PIC_SIM, 0)
            # 返回_找图AIEx = self.大漠对象.AiFindPicEx(627, 106, 1300, 712, r"./pic/guaiwu/单机_宝宝.bmp", 0.6, 0)
            # print("宝宝数量:",返回_找图AIEx)
            if 返回_找图AIEx != "":
                查找宝宝计次 = 0
                返回_列表 = 返回_找图AIEx.split('|')
                if len(返回_列表) > 1:
                    for i in 返回_列表:
                        分隔结果 = i.split(',')
                        分隔结果 = [int(j) for j in 分隔结果]
                        宝宝列表.append(分隔结果)  # 有多个宝宝时,二维列表存储坐标位置
                else:
                    分隔结果 = 返回_列表[0].split(',')
                    宝宝 = [int(i) for i in 分隔结果]  # 只有一个宝宝时,存储坐标位置
            else:
                查找宝宝计次 += 1
                # print('宝宝未找到计次', 查找宝宝计次)
                if 查找宝宝计次 > 2:
                    break
            # 判断是否是空列表
            # print('宝宝列表',宝宝列表)
            # 找到多个宝宝时,判断每个宝宝周围是否有怪(是否在打怪)
            if 宝宝列表:
                # print("正在打怪中11111111111111")
                宝宝攻击范围1 = [宝宝列表[0][1] - 70, 宝宝列表[0][2] - 39, 宝宝列表[0][1] + 121, 宝宝列表[0][2] + 58]
                宝宝攻击范围2 = [宝宝列表[1][1] - 70, 宝宝列表[1][2] - 39, 宝宝列表[1][1] + 121, 宝宝列表[1][2] + 58]
                返回_找图AIEx1 = self.大漠对象.AiFindPicEx(宝宝攻击范围1[0], 宝宝攻击范围1[1], 宝宝攻击范围1[2],
                                                          宝宝攻击范围1[3], fr"./{怪物图片路径_不包括宝宝}", config.MONSTER_PIC_SIM, 0)
                返回_找图AIEx2 = self.大漠对象.AiFindPicEx(宝宝攻击范围2[0], 宝宝攻击范围2[1], 宝宝攻击范围2[2],
                                                          宝宝攻击范围2[3], fr"./{怪物图片路径_不包括宝宝}", config.MONSTER_PIC_SIM, 0)
                if 返回_找图AIEx1 != '' or 返回_找图AIEx2 != '' :
                    宝宝周围未找到怪物计次 = 0
                    self.宝宝在身边未攻击次数 = 0
                    # print("宝宝正在打怪中11111111111111")
                else:
                    宝宝周围未找到怪物计次 += 1
                    # print('宝宝周围未找到怪物计次', 宝宝周围未找到怪物计次)
                    if 宝宝周围未找到怪物计次 > 3:
                        print("怪物已死亡11111111111111")
                        break
            # 只找到一个宝宝时,判断宝宝周围是否有怪(是否在打怪)
            if 宝宝:
                # 0,1是左上角坐标.2,3是右下角坐标
                宝宝攻击范围 = [宝宝[1] - 70, 宝宝[2] - 39, 宝宝[1] + 121, 宝宝[2] + 58]

                返回_找图AIEx = self.大漠对象.AiFindPicEx(宝宝攻击范围[0], 宝宝攻击范围[1], 宝宝攻击范围[2],
                                                   宝宝攻击范围[3], fr"./{怪物图片路径_不包括宝宝}", config.MONSTER_PIC_SIM, 0)
                if 返回_找图AIEx != '':
                    宝宝周围未找到怪物计次 = 0
                    self.宝宝在身边未攻击次数 = 0
                    # print("宝宝正在打怪中")
                    # print(返回_找图AIEx)
                else:
                    宝宝周围未找到怪物计次 += 1
                    # print('宝宝周围未找到怪物计次', 宝宝周围未找到怪物计次)
                    if 宝宝周围未找到怪物计次 > 3:
                        print("怪物已死亡")
                        break

            返回_找图AIEx = self.大漠对象.AiFindPicEx(x1,y1,x2,y2, fr"./{怪物图片路径_不包括宝宝}", config.MONSTER_PIC_SIM, 0)
            if 返回_找图AIEx == "":
                print('小范围周围没怪,继续找最近怪')
                break

            打怪控制.随机延时(50, 100)


    def 召唤宝宝(self):
        print('召唤宝宝')
        global map_path
        for i in range(3):
            if 打怪_stop_event.is_set() or 血量_打怪_stop_event.is_set():
                break
            返回_找图AIEx = self.大漠对象.AiFindPicEx(842,358, 1082,519, config.PET_PIC_PATH, config.PET_PIC_SIM, 0)
            # 返回_找图AIEx = self.大漠对象.AiFindPicEx(842,358, 1082,519, r"./pic/guaiwu/单机_宝宝.bmp", 0.6, 0)
            if 返回_找图AIEx == '':
                打怪控制.键盘点击(65)
                打怪控制.随机延时(1200, 1300)
            else:
                self.宝宝在身边未攻击次数 += 1
                print('宝宝在身边,不用召唤')
                return
            # 这个在人物身边找图判断宝宝是否在的延时不能设置太大和太小,太小,宝宝还没召唤出来,找图找不到,太大,宝宝已经离开人物走向怪物了,找图也找不到
            打怪控制.延时(1000)
        else:
            print('3次找图没有找到宝宝,这里不能召唤宝宝,移动人物换个地方召唤')
            人物x,人物y = dm_utils.ocr_player_pos(self.大漠对象)
            map_img = cv2.imread(map_path)
            frame,_  = 寻路.更新地图_怪物点(self.大漠对象,打怪控制,map_img)
            safe_point = ai算法.next_move_a((人物x, 人物y), frame, (人物x, 人物y), None,1)
            path = ai算法.a_star_eight(人物x, 人物y, safe_point[0], safe_point[1], frame, 1, 1, 1, 1, 1)
            寻路.walk_path(
                path,
                img=map_img,
                dm=self.大漠对象,
                get_pos=dm_utils.ocr_player_pos,
                controller=打怪控制,
                bad_cells=bad_cells,
                stop_event=(打怪_stop_event, 血量_打怪_stop_event)
            )
            self.召唤宝宝()


    def 拾取物品(self,img):
        global wupin_list
        物品游戏坐标列表 = LootFeature().run_loop(self.大漠对象, 164, 117, 1896, 816, 控制器=打怪控制)
        print("物品游戏坐标列表:",物品游戏坐标列表)
        if 物品游戏坐标列表:
            for 物品 in 物品游戏坐标列表:
                print("正在拾取物品")
                if 物品 in wupin_list:
                    continue
                物品坐标x = 物品[0]
                物品坐标y = 物品[1]
                人物x, 人物y = dm_utils.ocr_player_pos(self.大漠对象)
                frame,_  = 寻路.更新地图_怪物点(self.大漠对象, 打怪控制,img)
                path = ai算法.a_star_eight(人物x, 人物y, 物品坐标x, 物品坐标y, frame, 1, 0, 0, 0.001, 0)
                寻路.walk_path(
                    path,
                    img=img,
                    dm=self.大漠对象,
                    get_pos=dm_utils.ocr_player_pos,
                    controller=打怪控制,
                    bad_cells=bad_cells,
                    stop_event=(打怪_stop_event, 血量_打怪_stop_event),
                    end_threshold=0,
                    repath_interval=1,
                )
                if 打怪_stop_event.is_set() or 血量_打怪_stop_event.is_set():
                    return
                人物x, 人物y = dm_utils.ocr_player_pos(self.大漠对象)
                if 人物x == 物品坐标x and 人物y == 物品坐标y:
                    self.物品捡取状态(物品坐标x,物品坐标y)


    def 物品捡取状态(self,物品坐标x,物品坐标y):
        global wupin_list
        self.大漠对象.UseDict(3)
        for i in range(100):
            z1, x1, y1 = self.大漠对象.FindStr(199, 935, 580, 1051, "无法捡起", "ffff00-000000", 1.0)
            if z1 != -1:
                print("无法捡取")
                wupin_list.add((物品坐标x,物品坐标y))
                return -1           # 不可捡取, 把当前坐标添加进物品坏点集合中, 坏点集合等待120秒后删除
            z2, x2, y2 = self.大漠对象.FindStr(23,36,179,55,"被发现","008000-000000",1.0)
            if z2 != -1:
                print("已捡取")
                return 1            # 已捡取
            打怪控制.延时(10)
        else:                       # 既不是不可捡取也不是已捡取, 进一步判断是否背包已满
            打怪控制.键盘点击(41)               # esc
            打怪控制.键盘点击(66)               # F9
            打怪控制.延时(1000)
            z, x, y = self.大漠对象.AiFindPic(*config.正常_背包整理区域)
            if z != -1:
                打怪控制._move_with_click("left",x,y,0,5,0,5)   # 点击整理背包
                打怪控制.延时(1000)
                z, x, y = self.大漠对象.AiFindPic(*config.背包状态区域)
                if z != -1:
                    打怪控制.键盘点击(41)
                    print("背包未满")
                else:
                    打怪控制.键盘点击(41)
                    打怪控制.延时(1000)
                    打怪控制.键盘点击(30)
                    print("背包已满, 点击回城卷")
        return 0


    def 前往NPC(self,npc:str,控制器,img,找图区域):
        人物x, 人物y = dm_utils.ocr_player_pos(self.大漠对象)
        目标x,目标y = Npc.MengZhong[npc]
        path = ai算法.a_star_eight(人物x,人物y,目标x,目标y,img,1,1)
        寻路.walk_path(path,img=img,dm=self.大漠对象,get_pos=dm_utils.ocr_player_pos,controller=控制器,right_only=True,end_threshold=5,reach_threshold=3)

        控制器.延时(1000)
        # 打开组合回收界面
        while True:
            人物x,人物y = dm_utils.ocr_player_pos(self.大漠对象)
            x,y = 游戏坐标转换屏幕坐标(人物x,人物y,*Npc.MengZhong[npc])
            for i in range(3):
                控制器._move_with_click("left",x,y,0,3,0,2)
                z1, x1, y1 = self.大漠对象.AiFindPic(*找图区域)
                if z1 != -1:
                    return x1,y1
                y = y - 28
                控制器.延时(1000)
            控制器.延时(1000)


    def 回城操作(self,img,控制器):
        try:
            # 前往并打开回收NPC
            self.前往NPC("sale",控制器,img,config.组合回收图片区域)
            # F9打开背包
            while True:
                控制器.键盘点击(66)
                z, x, y = self.大漠对象.AiFindPic(*config.回收_背包整理区域)
                if z != -1:
                    print("已打开背包")
                    break
                time.sleep(0.01)

            # 固定按顺序点击"一键回收"
            x = 337
            y = 35
            for i in range(3):
                time.sleep(1)
                offset_x = random.randint(0,37)
                offset_y = random.randint(0,4)
                控制器.simple_move_with_left_click(x+offset_x,y+offset_y)
                while True:
                    time.sleep(0.01)
                    ret = self.大漠对象.IsDisplayDead(1633,301,1718,317, 2)
                    if ret:
                        y = y + 16
                        break
            控制器.键盘点击(41)  # esc

            # 前往并打开仓库
            x,y = self.前往NPC("store", 控制器,img,config.仓库界面区域)
            控制器._move_with_click("left",x,y,0,5,0,2)

            time.sleep(1)
            # 整理背包
            z, x, y = self.大漠对象.AiFindPic(*config.仓库_背包整理区域)
            if z != -1:
                控制器._move_with_click("left",x,y,0,3,0,2)

            time.sleep(1)
            # # 右键逐个点击背包, 把背包所有东西放入仓库
            # x = 1603                # 仓库存放时打开背包的第一个格子的中心x
            # y = 148                 # 仓库存放时打开背包的第一个格子的中心y
            # for i in range(5):
            #     x = 1603
            #     if i != 0:
            #         y += 32         # 背包上下格子的间隔
            #     for j in range(8):
            #         offset_x = random.randint(-8,8)
            #         offset_y = random.randint(-8,8)
            #         控制器.simple_move_with_right_click(x+offset_x,y+offset_y)
            #         x += 36         # 背包左右格子的间隔

            # 前往并打开下图的NPC
            控制器.键盘点击(41)  # esc
            x, y = self.前往NPC("散人之家", 控制器, img, config.进入散人之家区域)
            # 点击下图
            控制器._move_with_click("left",x,y,0,5,0,2)
        except Exception as e:
            print(repr(e))  # 输出异常的类型
            traceback.print_exc()


    def 押镖(self):
        try:
            for i in range(30):
                # 走到可以接镖车的位置
                while True:
                    人物x,人物y = dm_utils.ocr_player_pos(self.大漠对象)
                    if 人物x != -1:
                        目标方位 = 打怪控制.判断方位(352, 348, 人物x, 人物y)
                        if abs(352 - 人物x) == 1 or abs(348 - 人物y) == 1:
                            打怪控制.左键点击方位_走路(目标方位, 100, 300)
                        else:
                            打怪控制.右键点击方位_跑步(目标方位, 100, 300)
                        if abs(352 - 人物x)<=2 and abs(348 - 人物y)<=2:
                            self.caozuo.emit("到达接镖位置")
                            break
                    else:
                        self.caozuo.emit("未识别到人物坐标")
                    打怪控制.随机延时(200, 400)
                # 点击NPC接镖
                for i in range(30):
                    z, x, y = self.大漠对象.AiFindPic(*config.ESCORT_REGION_MAIN, config.ESCORT_BUREAU_PIC, config.ESCORT_PIC_SIM, 0)
                    if z != -1:
                        打怪控制.move_with_left_click(x + 25, y - 34, -1, 1, 0, 10)
                        打怪控制.随机延时(200, 500)
                    z, x, y = self.大漠对象.AiFindPic(*config.ESCORT_REGION_DIALOG, config.ESCORT_START_PIC, config.ESCORT_PIC_SIM, 0)
                    if z != -1 :
                        打怪控制.move_with_left_click(x, y, 0, 20, 0, 8)
                        打怪控制.随机延时(200, 500)
                    z, x, y = self.大漠对象.AiFindPic(*config.ESCORT_REGION_DIALOG, config.ESCORT_ACCEPT_PIC, config.ESCORT_PIC_SIM, 0)
                    if z != -1 :
                        打怪控制.move_with_left_click(x, y,  0, 20, 0, 7)
                        打怪控制.随机延时(200, 500)
                    z, x, y = self.大漠对象.AiFindPic(*config.ESCORT_REGION_CONFIRM, config.ESCORT_CONFIRM_PIC, config.ESCORT_PIC_SIM,0)
                    if z != -1:
                        打怪控制.move_with_left_click(x, y, 0, 30, 0, 10)
                        打怪控制.随机延时(200, 500)
                        # 有时候找图找的坐标不准确,没有"镖车确定"的图片,就是接到镖车了
                        z, x, y = self.大漠对象.AiFindPic(*config.ESCORT_REGION_CONFIRM, config.ESCORT_CONFIRM_PIC, config.ESCORT_PIC_SIM, 0)
                        if z == -1:
                            self.caozuo.emit("接到镖车")
                            break
                        continue
                    打怪控制.随机延时(50, 100)
                # 接到镖车走到交镖车位置
                while True:
                    人物x, 人物y = dm_utils.ocr_player_pos(self.大漠对象)
                    if 人物x != -1:
                        目标方位 = 打怪控制.判断方位(382, 341, 人物x, 人物y)
                        if abs(382 - 人物x) == 1 or abs(341 - 人物y) == 1:
                            打怪控制.左键点击方位_走路(目标方位, 100,300)
                        else:
                            打怪控制.右键点击方位_跑步(目标方位, 100,300)
                        # 镖车走的慢,要等镖车
                        打怪控制.随机延时(2000, 2500)
                        self.caozuo.emit(f"{人物x},{人物y}")
                        if abs(382 - 人物x)<=2 and abs(341 - 人物y)<=2:
                            self.caozuo.emit("到达交镖车位置")
                            break
                    打怪控制.随机延时(200, 400)
                # 点击NPC交镖车
                for i in range(30):
                    z, x, y = self.大漠对象.AiFindPic(*config.ESCORT_REGION_CHIEF, config.ESCORT_CHIEF_PIC, config.ESCORT_PIC_SIM,0)
                    if z != -1:
                        打怪控制.move_with_left_click(x, y, 0, 23, 0, 10)
                        打怪控制.随机延时(200, 500)
                    z, x, y = self.大漠对象.AiFindPic(*config.ESCORT_REGION_FINISH, config.ESCORT_FINISH_PIC, config.ESCORT_PIC_SIM, 0)
                    if z != -1:
                        打怪控制.move_with_left_click(x, y,  0, 15, 0, 8)
                        打怪控制.随机延时(1000, 1500)
                        # 没找到完成任务,就是已经交任务了
                        z, x, y = self.大漠对象.AiFindPic(*config.ESCORT_REGION_FINISH, config.ESCORT_FINISH_PIC, config.ESCORT_PIC_SIM, 0)
                        if z == -1:
                            self.caozuo.emit("镖车交接完成")
                            # 按1键回城
                            # 打怪控制.键盘点击(30,100,300)
                            break
                        continue
                    打怪控制.随机延时(50, 100)
                打怪控制.随机延时(50, 100)
        except Exception as e:
            print(str(e))










class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # 直接加载.ui文件（无需提前转换成.py）
        uic.loadUi('./gui/longteng.ui', self)  # 参数1: .ui文件路径，参数2: 要附加到的窗口
        self.pushButton_kaishi.clicked.connect(self.kaishi)
        self.pushButton_yidong.clicked.connect(self.yidong)
        self.pushButton_ceshi.clicked.connect(self.ceshi)
        self.pushButton_bangding.clicked.connect(self.bangding)
        self.pushButton_jiebang.clicked.connect(self.jiebang)
        self.pushButton_ceshi2.clicked.connect(self.ceshi2)
        self.句柄_列表 = []
        self.A组线程对象列表 = []
        self.B组线程对象列表 = []
        self.C组线程对象列表 = []
        self.D组线程对象列表 = []

        # 大漠初始化, 创建了dms_a[]/dms_b[]/dms_c[]/dms[]4个列表的大漠对象
        大漠初始化(config.DM_REG_CODE, config.DM_ADD_CODE)
        设置字库(dms_a[0])
        返回_句柄 = dms_a[0].EnumWindowByProcess(
            config.GAME_PROCESS_NAME,
            config.GAME_WINDOW_TITLE_KEYWORD,
            config.GAME_WINDOW_CLASS,
            config.WINDOW_ENUM_FLAGS,
        )
        if 返回_句柄 != '':
            self.句柄_列表 = 返回_句柄.split(',')
            self.句柄_列表 = [int(i) for i in self.句柄_列表]
            for A大漠对象,B大漠对象,C大漠对象,D大漠对象,句柄 in zip(dms_a,dms_b,dms_c,dms,self.句柄_列表):
                窗口标题 = A大漠对象.GetWindowTitle(句柄)
                返回_绑定 = A大漠对象.BindWindowEx(
                    句柄,
                    config.BIND_DISPLAY,
                    config.BIND_MOUSE,
                    config.BIND_KEYPAD,
                    config.BIND_PUBLIC_DESC,
                    config.BIND_MODE,
                )
                if 返回_绑定 == 1:
                    self.plainTextEdit.appendPlainText(f"A大漠对象|{窗口标题}|绑定成功")
                    time.sleep(2)
                    A大漠对象.MoveWindow(句柄, config.WINDOW_MOVE_X, config.WINDOW_MOVE_Y)

                    self.A组线程对象列表.append(None)
                else:
                    self.plainTextEdit.appendPlainText(f"A大漠对象{窗口标题}|绑定失败")

                返回_绑定 = B大漠对象.BindWindowEx(
                    句柄,
                    config.BIND_DISPLAY,
                    config.BIND_MOUSE,
                    config.BIND_KEYPAD,
                    config.BIND_PUBLIC_DESC,
                    config.BIND_MODE,
                )
                if 返回_绑定 == 1:
                    self.plainTextEdit.appendPlainText(f"B大漠对象|{窗口标题}|绑定成功")
                    self.B组线程对象列表.append(None)
                else:
                    self.plainTextEdit.appendPlainText(f"B大漠对象{窗口标题}|绑定失败")

                返回_绑定 = C大漠对象.BindWindowEx(
                    句柄,
                    config.BIND_DISPLAY,
                    config.BIND_MOUSE,
                    config.BIND_KEYPAD,
                    config.BIND_PUBLIC_DESC,
                    config.BIND_MODE,
                )
                if 返回_绑定 == 1:
                    self.plainTextEdit.appendPlainText(f"C大漠对象|{窗口标题}|绑定成功")
                    self.C组线程对象列表.append(None)
                else:
                    self.plainTextEdit.appendPlainText(f"C大漠对象{窗口标题}|绑定失败")

                返回_绑定 = D大漠对象.BindWindowEx(
                    句柄,
                    config.BIND_DISPLAY,
                    config.BIND_MOUSE,
                    config.BIND_KEYPAD,
                    config.BIND_PUBLIC_DESC,
                    config.BIND_MODE,
                )
                if 返回_绑定 == 1:
                    self.plainTextEdit.appendPlainText(f"D大漠对象|{窗口标题}|绑定成功")
                    self.D组线程对象列表.append(None)
                else:
                    self.plainTextEdit.appendPlainText(f"D大漠对象{窗口标题}|绑定失败")


        else:
            self.plainTextEdit.appendPlainText('未找到窗口句柄')

        # 鼠标按下和释放事件
        btn = self.findChild(QPushButton,"pushButton_qujubing")     # 修复：objectName 需使用实际控件名
        if btn is not None:
            self.pushButton_qujubing = btn      # 统一引用,避免UI名称漂移

        if getattr(self, "pushButton_qujubing", None):  # 如果成功找到按钮对象
            # 给按钮安装事件过滤器（让窗口可以监听按钮的事件）
            self.pushButton_qujubing.installEventFilter(self)
        else:
            print("未找到按钮对象，请检查objectName")  # 调试提示

    def eventFilter(self, obj, event):
        """
        事件过滤器函数（监听所有安装过过滤器的对象）
        参数:
            obj: 触发事件的对象（这里是按钮）
            event: 事件对象（包含事件类型、坐标等信息）
        返回:
            bool: 是否继续传递事件（必须调用父类方法保持默认事件链）
        """
        # ---- 鼠标按下事件处理 ----
        if (obj == self.pushButton_qujubing and  # 确保是目标按钮
                event.type() == QEvent.MouseButtonPress):  # 鼠标按下事件

            if event.button() == Qt.LeftButton:  # 检查是否是左键
                # 将按钮局部坐标转换为窗口坐标（mapTo方法）
                window_pos = obj.mapTo(self, event.pos())
                # 打印调试信息（f-string格式化）
                self.lineEdit_jubing.setText('')

        # ---- 鼠标释放事件处理 ----
        elif (obj == self.pushButton_qujubing and  # 确保是目标按钮
              event.type() == QEvent.MouseButtonRelease):  # 鼠标释放事件

            if event.button() == Qt.LeftButton:  # 检查是否是左键
                句柄 = dms_a[0].GetMousePointWindow()
                self.lineEdit_jubing.setText(str(句柄))
                # 这里可以添加按钮释放后的业务逻辑

        # 必须调用父类方法，保证未处理的事件能继续传递
        return super().eventFilter(obj, event)

    def bangding(self):
        dms_a[0].UnBindWindow()
        句柄 = int(self.lineEdit_jubing.text())
        窗口标题 = dms_a[0].GetWindowTitle(句柄)
        返回_绑定 = dms_a[0].BindWindowEx(句柄, "gdi", "windows", "windows", "", 0)
        if 返回_绑定 == 1:
            self.plainTextEdit.appendPlainText(f"{窗口标题}|绑定成功")

    def jiebang(self):
        dms_a[0].UnBindWindow()
        self.plainTextEdit.appendPlainText("解除绑定")

    def ceshi(self):
        try:
            # 测试在新手验证地图躲避玩家
            # dms_a[0].UseDict(2)
            # s1 = time.perf_counter()
            # frame,players = 寻路.update_map_fn(dms_a[0],监控控制)
            # e1 = time.perf_counter()
            # print("更新地图耗时:",e1-s1)
            # 人物x, 人物y = dm_utils.ocr_player_pos(dms_a[0])
            #
            # s2 = time.perf_counter()
            # safe_point = ai算法.next_move_a((人物x, 人物y), frame, (人物x, 人物y), search_radius=25, selection_method=1,players=players,escape_mode='away')
            # e2 = time.perf_counter()
            # print("计算safe_point耗时:",e2-s2)
            # ai_visual.visualize_move(
            #     frame, (人物x, 人物y), safe_point,
            #     search_center=(人物x, 人物y), search_radius=25,
            #     show_risk=True, scale=15, window="demo_case",
            #     outfile="viz_demo.png"
            # )
            # cv2.waitKey(1)
            # if safe_point is not None:
            #     s3 = time.perf_counter()
            #     path = ai算法.a_star_eight(人物x, 人物y, safe_point[0], safe_point[1], frame, 1, 0, 0, 0.001, 0)
            #     e3 = time.perf_counter()
            #     print("计算path耗时:", e3 - s3)
            #
            #     print("a星寻路路径点",path)
            #     if path is not None:
            #         ai_visual.visualize_grid_and_path(frame, path=path, win_name="path", cell_size=15)
            #         ret_path_list = 寻路.walk_path(
            #             path,
            #             dm=dms_a[0],
            #             get_pos=dm_utils.ocr_player_pos,
            #             controller=监控控制,
            #             bad_cells=bad_cells
            #         )
            #         print("实际移动路径点",ret_path_list)
            #         ai_visual.visualize_grid_and_path(frame, path=ret_path_list, win_name="ret_path_list", cell_size=15)


            # 盟重回收等操作
            # 人物x, 人物y = dm_utils.ocr_player_pos(dms_a[0])
            # 目标x,目标y = Npc.MengZhong["sale"]
            # img = cv2.imread(config.MAP_IMAGE_PATH)
            # path = ai算法.a_star_eight(人物x,人物y,目标x,目标y,img,1,1)
            # 寻路.walk_path(path,dm=dms_a[0],get_pos=dm_utils.ocr_player_pos,controller=监控控制,right_only=True,end_threshold=5,reach_threshold=3)
            #
            # time.sleep(1)
            # 人物x,人物y = dm_utils.ocr_player_pos(dms_a[0])
            # # 打开组合回收界面
            # flag = False
            # while True:
            #     x,y = 游戏坐标转换屏幕坐标(人物x,人物y,*Npc.MengZhong["sale"])
            #     for i in range(3):
            #         监控控制._move_with_click("left",x,y,0,3,0,2)
            #         z, x1, y1 = dms_a[0].AiFindPic(*config.组合回收图片区域)
            #         if z != -1:
            #             print(x1,y1)
            #             flag = True
            #             break
            #         y = y - 28
            #         time.sleep(0.01)
            #     if flag == True:
            #         break
            #     time.sleep(0.01)
            # # F9打开背包
            # while True:
            #     打怪控制.键盘点击(66)
            #     z, x, y = dms_a[0].AiFindPic(*config.回收_背包整理区域)
            #     if z != -1:
            #         print("已打开背包")
            #         break
            #     time.sleep(0.01)
            #
            # # 固定按顺序点击"一键回收"
            # x = 337
            # y = 35
            # for i in range(3):
            #     time.sleep(1)
            #     offset_x = random.randint(0,37)
            #     offset_y = random.randint(0,4)
            #     监控控制.simple_move_with_left_click(x+offset_x,y+offset_y)
            #     while True:
            #         time.sleep(0.01)
            #         ret = dms_a[0].IsDisplayDead(1633,301,1718,317, 2)
            #         if ret:
            #             y = y + 16
            #             break
            # 打怪控制.键盘点击(41)  # esc


            # 前往仓库
            # 人物x, 人物y = dm_utils.ocr_player_pos(dms_a[0])
            # 目标x,目标y = Npc.MengZhong["store"]
            # img = cv2.imread(config.MAP_IMAGE_PATH)
            # path = ai算法.a_star_eight(人物x,人物y,目标x,目标y,img,1,1)
            # 寻路.walk_path(path,dm=dms_a[0],get_pos=dm_utils.ocr_player_pos,controller=监控控制,right_only=True,end_threshold=7,reach_threshold=3)
            # time.sleep(1)
            # 人物x,人物y = dm_utils.ocr_player_pos(dms_a[0])
            # # 打开仓库界面
            # flag = False
            # while True:
            #     x,y = 游戏坐标转换屏幕坐标(人物x,人物y,*Npc.MengZhong["store"])
            #     for i in range(3):
            #         监控控制._move_with_click("left",x,y,0,3,0,2)
            #         z, x1, y1 = dms_a[0].AiFindPic(*config.仓库界面区域)
            #         if z != -1:
            #             flag = True
            #             监控控制.simple_move_with_left_click(x1,y1)
            #             break
            #         y = y - 28
            #         time.sleep(0.01)
            #     if flag == True:
            #         break
            #     time.sleep(0.01)
            #
            # time.sleep(1)
            # # 整理背包
            # z, x, y = dms_a[0].AiFindPic(*config.仓库_背包整理区域)
            # if z != -1:
            #     监控控制._move_with_click("left",x,y,0,3,0,2)
            #
            # time.sleep(1)
            # # 右键逐个点击背包, 把背包所有东西放入仓库
            # x = 1603                # 仓库存放时打开背包的第一个格子的中心x
            # y = 148                 # 仓库存放时打开背包的第一个格子的中心y
            # for i in range(5):
            #     x = 1603
            #     if i != 0:
            #         y += 32         # 背包上下格子的间隔
            #     for j in range(8):
            #         offset_x = random.randint(-8,8)
            #         offset_y = random.randint(-8,8)
            #         监控控制.simple_move_with_right_click(x+offset_x,y+offset_y)
            #         x += 36         # 背包左右格子的间隔
            #
            # # 下图
            # 人物x, 人物y = dm_utils.ocr_player_pos(dms_a[0])
            # 目标x,目标y = Npc.MengZhong["散人之家"]
            # img = cv2.imread(config.MAP_IMAGE_PATH)
            # path = ai算法.a_star_eight(人物x,人物y,目标x,目标y,img,1,1)
            # 寻路.walk_path(path,dm=dms_a[0],get_pos=dm_utils.ocr_player_pos,controller=监控控制,right_only=True,end_threshold=7,reach_threshold=3)
            # flag = False
            # while True:
            #     x,y = 游戏坐标转换屏幕坐标(人物x,人物y,*Npc.MengZhong["散人之家"])
            #     for i in range(3):
            #         监控控制._move_with_click("left",x,y,0,3,0,2)
            #         z, x1, y1 = dms_a[0].AiFindPic(*config.进入散人之家区域)
            #         if z != -1:
            #             flag = True
            #             监控控制._move_with_click("left",x1,y1,0,5,0,2)
            #             break
            #         y = y - 28
            #         time.sleep(0.01)
            #     if flag == True:
            #         break
            #     time.sleep(0.01)

            img = cv2.imread(config.map_dict["盟重省"])
            self.回城操作(img,监控控制)


            pass
        except Exception as e:
            print(repr(e))  # 输出异常的类型
            traceback.print_exc()

    def 前往NPC(self, npc: str, 控制器, img, 找图区域):
        人物x, 人物y = dm_utils.ocr_player_pos(dms_a[0])
        print("起点",人物x,人物y)
        目标x, 目标y = Npc.MengZhong[npc]
        path = ai算法.a_star_eight(人物x, 人物y, 目标x, 目标y, img, 1, 1)
        寻路.walk_path(path, img=img,dm=dms_a[0], get_pos=dm_utils.ocr_player_pos, controller=控制器,
                       right_only=True, end_threshold=5, reach_threshold=3,pursuit_mode=True)

        控制器.延时(1000)
        人物x, 人物y = dm_utils.ocr_player_pos(dms_a[0])
        # 打开组合回收界面
        while True:
            x, y = 游戏坐标转换屏幕坐标(人物x, 人物y, *Npc.MengZhong[npc])
            for i in range(3):
                控制器._move_with_click("left", x, y, 0, 3, 0, 2)
                z1, x1, y1 = dms_a[0].AiFindPic(*找图区域)
                if z1 != -1:
                    return x1, y1
                y = y - 28
                控制器.延时(1000)
            控制器.延时(1000)

    def 回城操作(self, img, 控制器):
            # 前往并打开回收NPC
            self.前往NPC("sale", 控制器, img, config.组合回收图片区域)
            # F9打开背包
            while True:
                打怪控制.键盘点击(66)
                z, x, y = dms_a[0].AiFindPic(*config.回收_背包整理区域)
                if z != -1:
                    print("已打开背包")
                    break
                time.sleep(0.01)

            # 固定按顺序点击"一键回收"
            x = 337
            y = 35
            for i in range(3):
                time.sleep(1)
                offset_x = random.randint(0, 37)
                offset_y = random.randint(0, 4)
                监控控制.simple_move_with_left_click(x + offset_x, y + offset_y)
                while True:
                    time.sleep(0.01)
                    ret = dms_a[0].IsDisplayDead(1633, 301, 1718, 317, 2)
                    if ret:
                        y = y + 16
                        break
            打怪控制.键盘点击(41)  # esc

            # 前往并打开仓库
            x, y = self.前往NPC("store", 控制器, img, config.仓库界面区域)
            监控控制._move_with_click("left", x, y, 0, 5, 0, 2)

            time.sleep(1)
            # 整理背包
            z, x, y = dms_a[0].AiFindPic(*config.仓库_背包整理区域)
            if z != -1:
                监控控制._move_with_click("left", x, y, 0, 3, 0, 2)

            time.sleep(1)
            # 右键逐个点击背包, 把背包所有东西放入仓库
            x = 1603  # 仓库存放时打开背包的第一个格子的中心x
            y = 148  # 仓库存放时打开背包的第一个格子的中心y
            for i in range(5):
                x = 1603
                if i != 0:
                    y += 32  # 背包上下格子的间隔
                for j in range(8):
                    offset_x = random.randint(-8, 8)
                    offset_y = random.randint(-8, 8)
                    监控控制.simple_move_with_right_click(x + offset_x, y + offset_y)
                    x += 36  # 背包左右格子的间隔

            # 前往并打开下图的NPC
            x, y = self.前往NPC("散人之家", 控制器, img, config.进入散人之家区域)
            # 点击下图
            监控控制._move_with_click("left", x, y, 0, 5, 0, 2)






    def ceshi2(self):
        try:
            # 测试在盟重地图躲避玩家
            dms_a[0].UseDict(2)
            s1 = time.perf_counter()
            img = cv2.imread(config.map_dict["盟重省"])
            frame,players = 寻路.update_map_fn(dms_a[0],监控控制,img)
            e1 = time.perf_counter()
            print("更新地图耗时:",e1-s1)
            人物x, 人物y = dm_utils.ocr_player_pos(dms_a[0])

            s2 = time.perf_counter()
            safe_point = ai算法.next_move_a((人物x, 人物y), frame, (人物x, 人物y), search_radius=25, selection_method=1,players=players,escape_mode='away')
            e2 = time.perf_counter()
            print("计算safe_point耗时:",e2-s2)
            ai_visual.visualize_move(
                frame, (人物x, 人物y), safe_point,
                search_center=(人物x, 人物y), search_radius=25,
                show_risk=True, scale=15, window="demo_case",
                outfile="viz_demo.png",
                view_range=25
            )
            cv2.waitKey(1)
            if safe_point is not None:
                s3 = time.perf_counter()
                path = ai算法.a_star_eight(人物x, 人物y, safe_point[0], safe_point[1], frame, 1, 0, 0, 0.001, 0)
                e3 = time.perf_counter()
                print("计算path耗时:", e3 - s3)

                print("a星寻路路径点",path)
                if path is not None:
                    ai_visual.visualize_grid_and_path(frame, path=path, win_name="path", cell_size=15, center_pos=(人物x, 人物y),view_range=25)
                    ret_path_list = 寻路.walk_path(
                        path,
                        img = frame,
                        dm=dms_a[0],
                        get_pos=dm_utils.ocr_player_pos,
                        controller=监控控制,
                        bad_cells=bad_cells,
                    )
                    print("实际移动路径点",ret_path_list)
                    ai_visual.visualize_grid_and_path(frame, path=ret_path_list, win_name="ret_path_list", cell_size=15,center_pos=(人物x, 人物y),view_range=25)

        except Exception as e:
            print(repr(e))  # 输出异常的类型
            traceback.print_exc()


    # 在ui控件上显示图像
    def xianshi(self,mask_rgb):
        try:
            rgb = cv2.cvtColor(mask_rgb, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            self.label_mask.setPixmap(QPixmap.fromImage(qimg))
        except Exception as e:
            print(repr(e))
            traceback.print_exc()

    def kaishi(self):
        try:
            if self.A组线程对象列表 :
                for 序号,(A大漠对象,B大漠对象,C大漠对象,D大漠对象,句柄) in enumerate(zip(dms_a,dms_b,dms_c,dms,self.句柄_列表)):
                    if self.A组线程对象列表[序号] == None:
                        self.D组线程对象列表[序号] = WorkerThread(D大漠对象,句柄,'界面线程')
                        self.D组线程对象列表[序号].start()
                        time.sleep(3)
                        self.A组线程对象列表[序号] = WorkerThread(A大漠对象,句柄,'打怪线程')
                        self.A组线程对象列表[序号].caozuo.connect(self.caozuo)
                        self.A组线程对象列表[序号].xianshi.connect(self.xianshi)
                        self.A组线程对象列表[序号].start()
                        self.B组线程对象列表[序号] = WorkerThread(B大漠对象,句柄,'血量线程')
                        self.B组线程对象列表[序号].jiankong.connect(self.jiankong)
                        self.B组线程对象列表[序号].start()
                        self.C组线程对象列表[序号] = WorkerThread(C大漠对象, 句柄, '监控线程')
                        self.C组线程对象列表[序号].caozuo.connect(self.caozuo)
                        self.C组线程对象列表[序号].start()

            else:
                self.plainTextEdit.appendPlainText("请先绑定游戏后再开启线程")
        except Exception as e:
            print(e)

    def caozuo(self,str):
        self.plainTextEdit.appendPlainText(str)

    def jiankong(self,str):
        self.plainTextEdit_jiankong.appendPlainText(str)

    def yidong(self):
        文本 = self.lineEdit.text()
        if ',' in 文本 and 文本 != '':
            分割结果 = 文本.split(',')
            x = int(分割结果[0])
            y = int(分割结果[1])
            dms_a[0].MoveWindow(self.句柄_列表[0], x, y)
        else:
            self.plainTextEdit.appendPlainText("请输入正确的数值,如 : 0,-25")

    def closeEvent(self, event):
        # pyqt_ui窗口关闭时触发的事件
        if dms_a:
            dms_a[0].UnBindWindow()
            del dms_a[0]
        event.accept()  # 允许关闭
        print("关闭")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyWindow()
    window.show()
    cv2.waitKey()
    cv2.destroyAllWindows()
    sys.exit(app.exec_())
