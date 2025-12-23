import threading

import cv2
import sys
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QMainWindow,QPushButton
from PyQt5.QtCore import QThread, pyqtSignal,Qt, QEvent,pyqtSlot
from PyQt5.QtGui import QImage, QPixmap
import heapq
import numpy as np
import time
import traceback
from 新大漠插件 import *
import ai算法
import ai_visual  # 可视化逻辑已拆分，核心算法不再依赖 OpenCV。
from kmNet类封装2 import *
from 常量 import changliang as cl
import config  # Centralize paths/constants to keep threads consistent.
import dm_utils  # OCR 通用工具，避免重复解析逻辑。

init_runtime()

打怪控制 = 游戏控制器(delay_func=打怪延时)

血量控制 = 游戏控制器(delay_func=血量延时)

监控控制 = 游戏控制器(delay_func=监控延时)


# with open(r"./pic/guaiwu/guaiwu.txt",'r',encoding='UTF-8') as f:
with open(config.MONSTER_LIST_PATH, 'r', encoding='UTF-8') as f:
    怪物图片路径 = f.read()
    怪物图片路径 = 怪物图片路径.replace('\n','|')
    target = "pic/guaiwu/宝宝.bmp|"
    # target = "|pic/guaiwu/单机_宝宝.bmp"
    怪物图片路径_不包括宝宝 = 怪物图片路径.replace(target, "")
    怪物路径列表 = 怪物图片路径.split('|')
    print(怪物图片路径)
    print(怪物路径列表)
    print(怪物图片路径_不包括宝宝)

with open(config.ITEM_NAME_PATH, 'r', encoding='ANSI') as f:
    物品名称路径 = f.read()
    物品名称路径 = 物品名称路径.replace('\n','|') + config.ITEM_NAME_EXTRA
    物品名称列表 = 物品名称路径.split('|')
    print(物品名称路径)


# 记录捡取物品的坐标,防止物品是其他人的,不能拾取,人物来回往该物品地址寻路
wupin_list = set()

# 记录每次寻路的终点,如果到达就清空集合,如果没有达到,就存储在集合中,防止下次寻路再以此点作为终点
bad_cells = set()

# 设置清空记录已捡取物品集合时间
CLEAR_INTERVAL = 60  # 间隔多少秒清空一次
last_clear_time = time.time()  # 上次清空时间


def 设置字库(大漠对象):
    """集中设置字库，避免多个地方写错路径导致 OCR 不一致。"""
    大漠对象.SetDict(0, config.DICT_NUM_PATH)
    大漠对象.SetDict(1, config.DICT_SYS_PATH)
    大漠对象.SetDict(2, config.DICT_PLAYER_PATH)


class WorkerThread(QThread):

    caozuo = pyqtSignal(str)
    jiankong = pyqtSignal(str)
    xianshi = pyqtSignal(object)

    def __init__(self,大漠对象,句柄,线程名):
        super().__init__()
        self.大漠对象 = 大漠对象
        设置字库(self.大漠对象)  # 统一字库设置，避免线程间配置漂移
        self.句柄 = 句柄
        self.线程名 = 线程名
        # self.map_img = cv2.imread("D5073_mafagumu.bmp")
        # self.map_img = cv2.imread("sanrenzhijia.bmp")
        self.map_img = cv2.imread(config.MAP_IMAGE_PATH)
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

        elif self.线程名 == '监控线程':
            self.caozuo.emit(f"线程名:{self.线程名}|{窗口标题}|线程启动成功")
            self.监控线程()

    def 监控线程(self):
        while True:

            s = time.perf_counter()
            # 使用统一的玩家扫描逻辑，允许备用 OCR 矩形回退
            player_pos = dm_utils.ocr_player_pos(self.大漠对象)
            players = dm_utils.scan_players(
                self.大漠对象,
                监控控制.屏幕坐标转游戏坐标,
                player_pos=player_pos,  # 复用 OCR 结果，减少重复识别与字典切换
            )
            if players:
                # 直接用扫描结果绘制，避免再次 OCR/找字
                frame = self.map_img.copy()
                frame = self.地图上绘制玩家点(frame, players)
                人物x,人物y = player_pos
                safe_point = ai算法.next_move_a((人物x,人物y),frame,(人物x,人物y),40,1)
                if safe_point is not None:
                    # 修复：使用 ai_visual.visualize_move 并传入已计算的安全点
                    ai_visual.visualize_move(
                        frame, (人物x, 人物y), safe_point,
                        search_center=(人物x, 人物y), search_radius=30,
                        show_risk=True, scale=5, window="demo_case",
                        outfile="viz_demo.png"
                    )
                    path = ai算法.a_star_eight(人物x, 人物y, safe_point[0], safe_point[1], frame, 1, 1, 1, 2, 1)
                    if path is not None:
                        pause_all()
                        mark_walk_stopped(打怪_stop_event, 血量_stop_event)  # 标记当前行走任务作废
                        ret_path_list = self.沿路径控制人物行走_监控线程(path, False, False, 1, 1)
                        resume_all()


            e = time.perf_counter()
            t = e - s
            print("找字用时:", t)
            监控控制.延时(100)

    # 在地图上用特定颜色绘制怪物坐标点,这里设置的颜色值要和AI模块中的_parse_enemies()函数中设置的一致
    def 地图上绘制怪物点(self,img,怪物坐标列表:list):
        # 地图上绘制危险级别 S 的怪
        S_list = [(a, b) for path, a, b in 怪物坐标列表 if 'S' in path]
        if S_list :
            sb, sg, sr = config.ENEMY_COLOR_S  # 使用统一颜色协议，保证与 ai算法 一致
            for (mx, my) in S_list:
                img[my, mx][0] = sb
                img[my, mx][1] = sg
                img[my, mx][2] = sr
        # 地图上绘制危险级别 A 的怪
        A_list = [(a, b) for path, a, b in 怪物坐标列表 if 'S' not in path]
        if A_list :
            ab, ag, ar = config.ENEMY_COLOR_A  # 使用统一颜色协议，保证与 ai算法 一致
            for (mx, my) in A_list:
                img[my, mx][0] = ab
                img[my, mx][1] = ag
                img[my, mx][2] = ar
        # 地图上绘制宝宝
        baobao_list = [(a, b) for path, a, b in 怪物坐标列表 if '宝宝' in path]
        if baobao_list :
            pb, pg, pr = config.PET_COLOR  # 统一宝宝颜色，便于后续调整
            for (mx, my) in baobao_list:
                img[my, mx][0] = pb
                img[my, mx][1] = pg
                img[my, mx][2] = pr
        return img

    def 更新地图_怪物点(self):
        frame = self.map_img.copy()
        怪物列表_包括宝宝 = self.识别怪物坐标(543, 98, 1370, 714, 怪物图片路径, 0.82)
        if 怪物列表_包括宝宝:
            frame = self.地图上绘制怪物点(frame, 怪物列表_包括宝宝)
        return frame

    def 地图上绘制玩家点(self,img,玩家坐标列表:list):
        pb, pg, pr = config.PLAYER_COLOR  # 统一玩家颜色，保证与风险计算一致
        for (mx,my) in 玩家坐标列表:
            img[my, mx][0] = pb
            img[my, mx][1] = pg
            img[my, mx][2] = pr
        return img

    def 更新地图_玩家点(self):
        frame = self.map_img.copy()
        # 使用默认 OCR 坐标入口，包含备用矩形回退
        玩家坐标列表 = dm_utils.scan_players(
                self.大漠对象,
                监控控制.屏幕坐标转游戏坐标,
            )
        if 玩家坐标列表:
            print("玩家坐标列表", 玩家坐标列表)
            frame = self.地图上绘制玩家点(frame, 玩家坐标列表)
        return frame, 玩家坐标列表

    def 血量线程(self):
        try:
            while True:

                if 血量_stop_event.is_set():
                    血量_stop_event.clear()

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

                血量比例 = 当前血量 / 最大血量
                if 0 < 血量比例 < 0.95:
                    pause_combat()  # 暂停打怪线程
                    mark_walk_stopped(打怪_stop_event)  # 暂停打怪线程同时做个标记,恢复打怪线程时通过这个标识重置打怪线程循环
                    s = time.perf_counter()

                    # 找安全坐标点
                    人物x,人物y = dm_utils.ocr_player_pos(self.大漠对象)
                    if 人物x < 0 or 人物y < 0:
                        # 坐标识别失败时不进行寻路，避免走到异常位置
                        time.sleep(0.1)
                        continue
                    z, x, y = self.大漠对象.AiFindPic(150,119,1719,867, r"./pic/guaiwu/宝宝.bmp", 0.60, 0)
                    # z, x, y = self.大漠对象.AiFindPic(543, 98, 1370, 714, r"./pic/guaiwu/单机_宝宝.bmp", 0.60, 0)
                    # 找到宝宝坐标,以宝宝坐标为中心找安全坐标点

                    frame = self.更新地图_怪物点()

                    if z != -1:
                        宝宝x,宝宝y = 血量控制.屏幕坐标转游戏坐标(人物x,人物y,x+14,y+34)
                        # 血量在75%以上时,安全点搜索半径为3,小范围选择安全坐标点
                        if 0.75 < 血量比例 < 0.95:
                            bin_safe_point = ai算法.next_move_a((人物x,人物y),frame,(宝宝x,宝宝y),2,1)
                        # 血量在75%以下时,安全点搜索半径为全图,大范围选择安全坐标点
                        elif 0 < 血量比例 <= 0.75:
                            bin_safe_point = ai算法.next_move_a((人物x, 人物y), frame, (宝宝x,宝宝y), None,1)
                    else:
                    # 未找到宝宝坐标,以人物坐标为中心找安全坐标点
                        if 0.75 < 血量比例 < 0.95:
                            bin_safe_point = ai算法.next_move_a((人物x,人物y),frame,(人物x, 人物y),5,1)
                        elif 0 < 血量比例 <= 0.75:
                            bin_safe_point = ai算法.next_move_a((人物x, 人物y), frame, (人物x, 人物y), None,1)
                    cv2.waitKey(1)

                    # 寻往安全坐标点
                    if bin_safe_point is not None:

                        frame = self.更新地图_怪物点()
                        path = ai算法.a_star_eight(人物x, 人物y, bin_safe_point[0],bin_safe_point[1] ,frame,1,0,1,1,1)
                        print('安全路径',path)

                        # 围绕着宝宝或者人物坐标点移动到安全位置
                        if path is not None :
                            ret_path_list = self.沿路径控制人物行走_血量线程(path, False,False, 0, 0)

                            e = time.perf_counter()
                            t = e - s
                            print('跑到安全点用时:', t)

                            血量控制.随机延时(100, 300)
                            # F3隐身,让怪物不要攻击自己
                            血量控制.键盘点击(60)
                            # 血量控制.随机延时(1400, 1600)

                elif 0.95 <= 血量比例 <= 1:
                    resume_combat()  # 继续打怪线程
                time.sleep(0.1)

        except Exception as e:
            print(e)
            print(repr(e))
            traceback.print_exc()

    # 561, 113, 1429, 730
    def 捡物(self,x1,y1,x2,y2):
        try:
            s = time.perf_counter()

            # max_yellow = np.array([35, 255, 255])
            # mix_yellow = np.array([25, 179, 150])
            #
            # max_green = np.array([65, 255, 255])
            # mix_green = np.array([55, 220, 150])
            #
            # max_blue = np.array([104, 210, 251])
            # mix_blue = np.array([90, 109, 145])
            #
            # max_red1 = np.array([179, 255, 255])
            # mix_red1 = np.array([170, 225, 150])
            #
            # max_red2 = np.array([10, 255, 255])
            # mix_red2 = np.array([0, 225, 150])

            img_path = "temp_img.bmp"
            self.大漠对象.Capture(x1,y1,x2,y2, img_path)
            self.大漠对象.UseDict(0)

            # 正版龙腾范围 48, 1057, 108, 1078  # 单机版龙腾范围 84,1061,128,1077
            人物x,人物y = dm_utils.ocr_player_pos(self.大漠对象)
            if 人物x < 0 or 人物y < 0:
                # OCR 坐标无效时直接返回，避免坐标换算错误
                return set()
            img = cv2.imread(img_path)
            if img is None:
                raise RuntimeError(f"读图失败: {img_path}")

            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

            # max_gray = np.array([136,70,211])
            # mix_gray = np.array([64,15,122])
            # mask_gray = cv2.inRange(hsv, mix_gray, max_gray)

            mask_yellow = cv2.inRange(hsv, cl.mix_yellow, cl.max_yellow)

            mask_green = cv2.inRange(hsv, cl.mix_green, cl.max_green)

            mask_blue = cv2.inRange(hsv, cl.mix_blue, cl.max_blue)

            mask_red1 = cv2.inRange(hsv, cl.mix_red1, cl.max_red1)

            mask_red2 = cv2.inRange(hsv, cl.mix_red2, cl.max_red2)

            # 用这种掩码相加合并掩码的方式,会存在有'254'的掩码出现
            # mask = mask_yellow + mask_green + mask_blue
            # 用这个按位或的方式,掩码只会有'0'和'255'
            mask = mask_blue | mask_green | mask_yellow | mask_red1 | mask_red2
            # mask = mask_blue | mask_green | mask_yellow | mask_red1 | mask_red2 | mask_gray
            # count_254 = np.sum(mask == 254)
            # # 3. 输出结果
            # if count_254 > 0:
            #     print(f"✅ 警告：mask 图像中存在 {count_254} 个像素值为 254。")

            mask_path = "mask_rgb.bmp"

            mask_rgb = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
            self.xianshi.emit(mask_rgb)
            # cv2.imshow("mask_rgb", mask_rgb)
            # cv2.waitKey(1)
            cv2.imwrite("mask_rgb.bmp", mask_rgb)

            dm_ret = self.大漠对象.FreePic("mask_rgb.bmp")
            dm_ret = self.大漠对象.SetDisplayInput("pic:mask_rgb.bmp")

            self.大漠对象.UseDict(1)

            ss = self.大漠对象.Ocr(0, 0, x2, y2, "ffffff-000000", 1.0)
            print("识字结果:---------------------------------------------------\n",ss)

            text = 物品名称路径
            物品游戏坐标列表 = set()
            ret = self.大漠对象.FindStrFastEx(0, 0, x2, y2, text, "ffffff-000000",1)
            if ret != '':
                ret_list = ret.split('|')
                for i in ret_list:
                    i_list = i.split(',')
                    序号 = int(i_list[0])
                    物品屏幕x = int(i_list[1])+x1
                    物品屏幕y = int(i_list[2])+y1
                    物品名称 = 物品名称列表[序号]
                    名字长度 = len(物品名称)
                    # print('物品名字长度:',名字长度)
                    if 名字长度 == 2:
                        物品游戏x, 物品游戏y = 血量控制.屏幕坐标转游戏坐标(人物x, 人物y, 物品屏幕x + 10,物品屏幕y + 24)
                    elif 名字长度 == 3:
                        物品游戏x, 物品游戏y = 血量控制.屏幕坐标转游戏坐标(人物x, 人物y, 物品屏幕x + 16,物品屏幕y + 24)
                    elif 名字长度 == 4:
                        物品游戏x, 物品游戏y = 血量控制.屏幕坐标转游戏坐标(人物x, 人物y, 物品屏幕x + 22,物品屏幕y + 24)
                    elif 名字长度 == 5:
                        物品游戏x, 物品游戏y = 血量控制.屏幕坐标转游戏坐标(人物x, 人物y, 物品屏幕x + 28,物品屏幕y + 24)
                    elif 名字长度 == 6:
                        物品游戏x, 物品游戏y = 血量控制.屏幕坐标转游戏坐标(人物x, 人物y, 物品屏幕x + 36,物品屏幕y + 24)
                    物品游戏坐标列表.add((物品名称,(物品游戏x,物品游戏y)))
                # print('物品游戏坐标列表1111111111',物品游戏坐标列表)

            self.大漠对象.SetDisplayInput("screen")
            # print('识字完成-------------------------------------------------------------------')

            time.sleep(0.1)

            ee = time.perf_counter()
            t = ee - s
            print('找物品用时:',t)
            return 物品游戏坐标列表
        except Exception as e:
            print(repr(e))
            traceback.print_exc()

    def 识别怪物坐标(self,x1,y1,x2,y2,path,sim):
        """
        找图找到范围内所有怪物的屏幕坐标,转换成游戏坐标,按(怪物名称,怪物游戏x,怪物游戏y)元组的形式存储到列表中
        """
        img_path = path
        人物坐标x, 人物坐标y = dm_utils.ocr_player_pos(self.大漠对象)
        if 人物坐标x < 0 or 人物坐标y < 0:
            # OCR 坐标无效时跳过找图，避免无意义的坐标转换
            return []
        返回_找图AIEx = self.大漠对象.AiFindPicEx(x1,y1,x2,y2, fr"./{img_path}", sim, 0)
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
                游戏坐标x, 游戏坐标y = 血量控制.屏幕坐标转游戏坐标(人物坐标x, 人物坐标y, 怪物屏幕x, 怪物屏幕y)
                # 把怪物名字也存储到列表,后期要根据怪物名字在地图上标记不同的颜色点
                怪物坐标 = (怪物名字,游戏坐标x, 游戏坐标y)
                if 怪物坐标 not in 怪物坐标列表:
                    怪物坐标列表.append(怪物坐标)
            return 怪物坐标列表
        else:
            return []

    # ==============================
    # 实时主循环
    # ==============================
    def 打怪线程(self):
        try:
            # ai_visual.visualize_grid_and_path(self.map_img, path=None, win_name="map_img", cell_size=3)
            # cv2.waitKey(1)
            # cv2.moveWindow('map_img', 1926, 10)
            if self.map_img is None:
                print("未找到 longyuanzhilu.bmp")
                return
            global bad_cells
            global last_clear_time
            global wupin_list
            while True:

                # 每隔CLEAR_INTERVAL时间,清空wupin_list记录已捡物品的集合
                now = time.time()
                if now - last_clear_time >= CLEAR_INTERVAL:
                    print("清空wupin_list之前",wupin_list)
                    wupin_list.clear()
                    print("定时清空 wupin_list",wupin_list)
                    last_clear_time = now

                if 打怪_stop_event.is_set():      # "打怪_stop_event"为True,表示其他线程暂停过又恢复了打怪线程,那么检查宝宝是否打怪和检查周围是否有物品
                    打怪_stop_event.clear()
                    self.fighting(150,119,1719,867)
                    物品游戏坐标列表 = self.捡物(561, 113, 1429, 730)
                    print("血量监测后,宝宝打死怪后物品列表:", 物品游戏坐标列表)
                    if 物品游戏坐标列表:
                        for 物品 in 物品游戏坐标列表:
                            if 物品 not in wupin_list:
                                print("血量监测后,宝宝打死怪后捡取物品", 物品[0])
                                物品坐标x = 物品[1][0]
                                物品坐标y = 物品[1][1]
                                人物x, 人物y = dm_utils.ocr_player_pos(self.大漠对象)
                                frame = self.更新地图_怪物点()
                                path = ai算法.a_star_eight(人物x, 人物y, 物品坐标x, 物品坐标y, frame, 1, 0, 1, 1, 1)
                                print('血量监测后,宝宝打死怪后捡物品寻路路径:', path)
                                self.沿路径控制人物行走_打怪线程(path, False, False, 0, 1)
                                wupin_list.add(物品)

                frame = self.map_img.copy()
                人物x, 人物y = dm_utils.ocr_player_pos(self.大漠对象)

                怪物列表_包括宝宝 = self.识别怪物坐标(5, 28, 1916, 823,怪物图片路径,0.82)
                怪物列表_不包括宝宝 = [item for item in 怪物列表_包括宝宝 if '宝宝' not in item[0]]

                # 全局集合 bad_cells 记录了寻路过程中不能到达的怪物游戏坐标,找最近怪时先筛除掉这些不能到达的怪(不在这些怪中找最近怪)
                # bad_cells 在 `沿路径控制人物行走()` 寻路函数中会被清空重置,重置条件是寻路函数能正常完成寻路到达终点,bad_cells就会被清空重置
                if bad_cells:
                    怪物列表_不包括宝宝 = [item for item in 怪物列表_不包括宝宝 if item not in bad_cells]

                if 怪物列表_不包括宝宝:
                    self.地图上绘制怪物点(frame, 怪物列表_包括宝宝)

                    # 寻找最近怪物
                    怪物距离 = [np.hypot(mx - 人物x, my - 人物y) for (name,mx, my) in 怪物列表_不包括宝宝]
                    最近怪物 = 怪物列表_不包括宝宝[np.argmin(怪物距离)]
                    bad_cells.add(最近怪物)
                    # print('bad_cells',bad_cells)
                    name ,最近x, 最近y = 最近怪物

                    print('最近怪:',name,最近x,最近y)

                    # A星寻路算法算出路线path
                    path = ai算法.a_star_eight(人物x, 人物y, 最近x, 最近y,frame,1,1,1,1,1)
                    print('寻路路径',path)

                    # 沿着寻路路径开始寻路
                    ret_path_list = self.沿路径控制人物行走_打怪线程(path,True,False,1,0)

                    打怪控制.随机延时(400, 600)
                    # F3隐身,让怪物不要攻击自己
                    打怪控制.键盘点击(60)
                    打怪控制.随机延时(1200, 1300)
                    # 宝宝在人物一边,怪物在人物另一边,宝宝和怪物被人物隔开了,比如人物要进门打怪,但是人物卡在了门口
                    if self.宝宝在身边未攻击次数 > 5:
                        print('人物卡在门口,把宝宝和怪物分开了,宝宝不能打怪')
                        人物x, 人物y = dm_utils.ocr_player_pos(self.大漠对象)
                        frame = self.更新地图_怪物点()
                        safe_point = ai算法.next_move_a((人物x, 人物y), frame, (人物x, 人物y), None, 1)
                        print('宝宝在身边未攻击次数大于5后安全点坐标',safe_point)
                        if 'safe_point' not in locals():
                            raise ValueError("宝宝在身边未攻击次数")
                        path = ai算法.a_star_eight(人物x, 人物y, safe_point[0], safe_point[1], frame, 1, 1, 1, 1, 1)
                        self.沿路径控制人物行走_打怪线程(path, False, False, 1, 1)

                    # 宝宝不在人物一格范围内就召唤
                    self.召唤宝宝()

                    物品游戏坐标列表 = self.捡物(248,88,1607,864)
                    print("召唤宝宝后物品列表:",物品游戏坐标列表)
                    if 物品游戏坐标列表:
                        for 物品 in 物品游戏坐标列表:
                            print("召唤宝宝后捡取物品",物品[0])
                            if 物品 not in wupin_list:
                                物品坐标x = 物品[1][0]
                                物品坐标y = 物品[1][1]
                                人物x, 人物y = dm_utils.ocr_player_pos(self.大漠对象)
                                frame = self.更新地图_怪物点()
                                path = ai算法.a_star_eight(人物x, 人物y, 物品坐标x, 物品坐标y, frame, 1, 0, 1, 1, 1)
                                print('召唤宝宝后捡物品寻路路径:',path)
                                self.沿路径控制人物行走_打怪线程(path, False, False, 0, 1)
                                wupin_list.add(物品)

                    print('马上进入宝宝打怪中')
                    self.fighting(627, 106, 1300, 712)

                    # 打死怪后判断周围有没有装备
                    物品游戏坐标列表 = self.捡物(561, 113, 1429, 730)
                    print("宝宝打死怪后物品列表:", 物品游戏坐标列表)
                    if 物品游戏坐标列表:
                        for 物品 in 物品游戏坐标列表:
                            if 物品 not in wupin_list:
                                print("宝宝打死怪后捡取物品", 物品[0])
                                物品坐标x = 物品[1][0]
                                物品坐标y = 物品[1][1]
                                人物x, 人物y = dm_utils.ocr_player_pos(self.大漠对象)
                                frame = self.更新地图_怪物点()
                                path = ai算法.a_star_eight(人物x, 人物y, 物品坐标x, 物品坐标y, frame, 1, 0, 1, 1, 1)
                                print('宝宝打死怪后捡物品寻路路径:', path)
                                self.沿路径控制人物行走_打怪线程(path, False, False, 0, 1)
                                wupin_list.add(物品)

                # 找图发现周围没有怪后的操作
                else:
                    人物x,人物y = dm_utils.ocr_player_pos(self.大漠对象)
                    # point = [(80,8),(58,8),(6,20),(9,65)]
                    point = [(18,141),(236,60),(72,357),(265,309)]
                    i = random.randint(0, 3)
                    frame = self.更新地图_怪物点()
                    path = ai算法.a_star_eight(人物x, 人物y, point[i][0], point[i][1], frame, 1, 1, 1, 1, 1)
                    print('周围没有怪了,前往下一个打怪点\n',path)
                    self.沿路径控制人物行走_打怪线程(path,True,True,1,1)

                打怪控制.延时(100)
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
            宝宝列表 = list()
            宝宝 = list()
            宝宝攻击范围 = [None, None, None, None]  # 0,1是左上角坐标.2,3是右下角坐标

            返回_找图AIEx = self.大漠对象.AiFindPicEx(x1,y1,x2,y2, r"./pic/guaiwu/宝宝.bmp", 0.6, 0)
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
                if 查找宝宝计次 > 10:
                    break
            # 判断是否是空列表
            # print('宝宝列表',宝宝列表)
            # 找到多个宝宝时,判断每个宝宝周围是否有怪(是否在打怪)
            if 宝宝列表:
                # print("正在打怪中11111111111111")
                宝宝攻击范围1 = [宝宝列表[0][1] - 70, 宝宝列表[0][2] - 39, 宝宝列表[0][1] + 121, 宝宝列表[0][2] + 58]
                宝宝攻击范围2 = [宝宝列表[1][1] - 70, 宝宝列表[1][2] - 39, 宝宝列表[1][1] + 121, 宝宝列表[1][2] + 58]
                返回_找图AIEx1 = self.大漠对象.AiFindPicEx(宝宝攻击范围1[0], 宝宝攻击范围1[1], 宝宝攻击范围1[2],
                                                          宝宝攻击范围1[3], fr"./{怪物图片路径_不包括宝宝}", 0.85, 0)
                返回_找图AIEx2 = self.大漠对象.AiFindPicEx(宝宝攻击范围2[0], 宝宝攻击范围2[1], 宝宝攻击范围2[2],
                                                          宝宝攻击范围2[3], fr"./{怪物图片路径_不包括宝宝}", 0.85, 0)
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
                                                   宝宝攻击范围[3], fr"./{怪物图片路径_不包括宝宝}", 0.85, 0)
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

            返回_找图AIEx = self.大漠对象.AiFindPicEx(x1,y1,x2,y2, fr"./{怪物图片路径_不包括宝宝}", 0.85, 0)
            if 返回_找图AIEx == "":
                print('小范围周围没怪,继续找最近怪')
                break

            打怪控制.随机延时(50, 100)


    def 召唤宝宝(self):
        print('召唤宝宝')
        for i in range(3):
            返回_找图AIEx = self.大漠对象.AiFindPicEx(842,358, 1082,519, r"./pic/guaiwu/宝宝.bmp", 0.6, 0)
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
            frame = self.更新地图_怪物点()
            safe_point = ai算法.next_move_a((人物x, 人物y), frame, (人物x, 人物y), None,1)
            path = ai算法.a_star_eight(人物x, 人物y, safe_point[0], safe_point[1], frame, 1, 1, 1, 1, 1)
            self.沿路径控制人物行走_打怪线程(path, False, False, 1, 0)
            self.召唤宝宝()

    def 押镖(self):
        try:
            for i in range(30):
                # 走到可以接镖车的位置
                while True:
                    # 使用默认坐标 OCR，失败时可回退备用矩形
                    人物x, 人物y = dm_utils.ocr_player_pos(self.大漠对象)
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
                    z, x, y = self.大漠对象.AiFindPic(5, 28, 1916, 823, r"./pic/镖局.bmp", 0.8, 0)
                    if z != -1:
                        打怪控制.move_with_left_click(x + 25, y - 34, -1, 1, 0, 10)
                        打怪控制.随机延时(200, 500)
                    z, x, y = self.大漠对象.AiFindPic(8, 9, 390, 164, r"./pic/开始押镖.bmp", 0.8, 0)
                    if z != -1 :
                        打怪控制.move_with_left_click(x, y, 0, 20, 0, 8)
                        打怪控制.随机延时(200, 500)
                    z, x, y = self.大漠对象.AiFindPic(8, 9, 390, 164, r"./pic/接受护送.bmp", 0.8, 0)
                    if z != -1 :
                        打怪控制.move_with_left_click(x, y,  0, 20, 0, 7)
                        打怪控制.随机延时(200, 500)
                    z, x, y = self.大漠对象.AiFindPic(700, 428, 1223, 657, r"./pic/镖车确定.bmp", 0.8,0)
                    if z != -1:
                        打怪控制.move_with_left_click(x, y, 0, 30, 0, 10)
                        打怪控制.随机延时(200, 500)
                        # 有时候找图找的坐标不准确,没有"镖车确定"的图片,就是接到镖车了
                        z, x, y = self.大漠对象.AiFindPic(700, 428, 1223, 657, r"./pic/镖车确定.bmp", 0.8, 0)
                        if z == -1:
                            self.caozuo.emit("接到镖车")
                            break
                        continue
                    打怪控制.随机延时(50, 100)
                # 接到镖车走到交镖车位置
                while True:
                    # 使用默认坐标 OCR，失败时可回退备用矩形
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
                    z, x, y = self.大漠对象.AiFindPic(11, 55, 1915, 718, r"./pic/镖局总管.bmp", 0.8,0)
                    if z != -1:
                        打怪控制.move_with_left_click(x, y, 0, 23, 0, 10)
                        打怪控制.随机延时(200, 500)
                    z, x, y = self.大漠对象.AiFindPic(11, 20, 389, 161, r"./pic/完成任务.bmp", 0.8, 0)
                    if z != -1:
                        打怪控制.move_with_left_click(x, y,  0, 15, 0, 8)
                        打怪控制.随机延时(1000, 1500)
                        # 没找到完成任务,就是已经交任务了
                        z, x, y = self.大漠对象.AiFindPic(11, 20, 389, 161, r"./pic/完成任务.bmp", 0.8, 0)
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


    def _nearest_index_along_path(self,path, pos, start_index, max_lookahead=6):
        """
        在 path[start_index : start_index+max_lookahead] 范围内，
        找到离当前人物坐标最近的路径点索引，防止人物走快了、跨点。
        """
        px, py = pos
        best_i = start_index
        best_d = 10 ** 9

        end = min(len(path), start_index + max_lookahead + 1)
        for i in range(start_index, end):
            d = max(abs(px - path[i][0]), abs(py - path[i][1]))  # Chebyshev 距离
            if d < best_d:
                best_d = d
                best_i = i

        return best_i, best_d


    def 沿路径控制人物行走_打怪线程(self, path,
                           small_area=False,
                           big_area=False,
                           end_threshold=1,
                           reach_threshold=1,
                           max_lookahead=6,
                           sleep_interval=0.05,
                           # ==== 新增参数：动态重规划 ====
                           dynamic_repath: bool = False,  # 是否开启动态重规划
                           repath_interval: float = 0.5,  # 两次重规划最小间隔(秒)
                           repath_radius: int = 25,  # next_move_a 搜索半径
                           repath_selection_method: int = 1,  # next_move_a 的 selection_method
                           a_star_kwargs: dict | None = None,  # A* 的参数配置
                           stop_event = None,            # ==== 新增：中断事件 ====
                           ):
        """
        根据 path 控制鼠标移动方向和点击，让人物沿 path 走到终点。

        依赖外部接口：
            - 判断方位(目的地x, 目的地y, 人物当前点x, 人物当前点y)
            - 移动方位不点击(目标方位)
            - left_click()
            - 按下右键(), 释放右键()
            - 八方位点击坐标 需已通过 八方位点击坐标计算(...) 预先算好

        参数：
            path            路径点列表 [(x1,y1), (x2,y2), ...]
            small_area      小范围找图找怪标志位,True为找图,False为不找图
            big_area        大范围找图找怪标志位,True为找图,False为不找图
            reach_threshold 把人物视为“到达某个路径点”的容差（格子数，Chebyshev）
            max_lookahead   从当前索引往前看多少个点，用于纠正索引
            sleep_interval  每轮循环的暂停时间（秒），根据游戏刷新速度自己调
        """
        if not path:
            return

        # ===== 入场检查：人物是否在路径起点附近 =====
        cur = dm_utils.ocr_player_pos(self.大漠对象)
        if not cur or cur[0] < 0 or cur[1] < 0:
            print("警告: 入场时无法识别人 物坐标，放弃本次行走")
            return

        人物x0, 人物y0 = cur
        start_dist = max(abs(人物x0 - path[0][0]), abs(人物y0 - path[0][1]))
        print(f"入场检查: path[0]={path[0]}, 人物起始=({人物x0},{人物y0}), dist={start_dist}")

        if start_dist > 5:  # 阈值你自己调，比如 >3 或 >8
            print("警告: 人物与路径起点偏差太大，视为无效路径，退出，让上层重新算")
            return

        if a_star_kwargs is None:
            # 这里用你现在 main 里那一组 (1,1,1,2,1)
            a_star_kwargs = dict(
                foot_len=1,
                endpoint_deviation=1,
                safety_radius=1,
                safety_weight=2,
                close_penalty_distance=1,
            )

        road_list = []              # 记录走过了哪些坐标点
        end_x, end_y = path[-1]
        idx = 0                     # 迭代对象path的下标索引
        right_down = False
        last_dir = None

        # === 新增：卡死检测相关状态 ===
        last_idx = idx
        last_dist_to_next = None
        last_progress_time = time.time()
        stuck_timeout = 2.0  # 秒，按你游戏实际情况调，比如 3~8 秒

        # === 新增：重规划状态 ===
        current_goal = (end_x, end_y)  # 当前路径的最终目标点
        last_repath_time = 0.0  # 上次重规划时间戳

        # ==== 新增：是否“严格终点模式”（必须走到终点格子） ====
        strict_end = (end_threshold == 0)

        print('开始寻路')
        global bad_cells
        try:
            while True:

                # ==== 新增：被抢占后恢复时，立刻退出 ====
                if stop_event is not None and stop_event.is_set():
                    print("收到 stop_event 中断信号, 退出沿路径控制人物行走")
                    bad_cells.clear()
                    return road_list

                if small_area == True:
                    z, x, y = self.大漠对象.AiFindPic(843, 359, 1084, 513, 怪物图片路径_不包括宝宝, 0.85, 0)
                    if z != -1:
                        bad_cells.clear()
                        print('小范围检测到怪,停止寻路,清空bad_cells:', bad_cells)
                        return road_list
                if big_area == True :
                    z, x, y = self.大漠对象.AiFindPic(5, 28, 1916, 823, 怪物图片路径_不包括宝宝, 0.85, 0)
                    if z != -1:
                        bad_cells.clear()
                        print('大范围检测到怪,停止寻路,清空bad_cells:', bad_cells)
                        return road_list

                cur = dm_utils.ocr_player_pos(self.大漠对象)
                # OCR 失败直接下一轮
                if not cur or cur[0] < 0 or cur[1] < 0:
                    time.sleep(0.05)
                    continue

                人物x, 人物y = cur
                # print(f"当前人物坐标: ({人物x}, {人物y}), 终点: ({end_x}, {end_y}), ChebDist={max(abs(人物x - end_x), abs(人物y - end_y))}")

                if (人物x,人物y) not in road_list:
                    road_list.append((人物x,人物y))


                # ========== 新增：动态重规划 ==========

                if dynamic_repath:
                    now = time.time()
                    if now - last_repath_time >= repath_interval:
                        last_repath_time = now

                        # 1) 更新地图（地图上要把玩家画成敌人/高风险）
                        frame,players = self.更新地图_玩家点()

                        # 2) 以人物当前位置为中心，重新找“安全点”
                        new_safe = ai算法.next_move_a(
                            (人物x, 人物y),
                            frame,
                            (人物x, 人物y),  # 以自己为 search_center
                            repath_radius,  # 例如 40 或 50
                            repath_selection_method,  # 0/1
                            players=players,
                            escape_mode='away',
                        )

                        if new_safe is not None:
                            # 和当前终点差距不大就没必要重算，防抖
                            old_end = current_goal
                            diff = max(abs(new_safe[0] - old_end[0]),
                                       abs(new_safe[1] - old_end[1]))

                            if diff >= 3:  # 差距至少 3 格才重规划，你自己看着调
                                # 3) 基于最新地图 + 新安全点重算 A*
                                new_path = ai算法.a_star_eight(
                                    start_x=人物x,
                                    start_y=人物y,
                                    end_x=new_safe[0],
                                    end_y=new_safe[1],
                                    img_path=frame,
                                    **a_star_kwargs
                                )

                                if new_path:
                                    print("动态重规划成功, 新终点:", new_path[-1])

                                    # 用新路径替换旧路径
                                    path = new_path
                                    end_x, end_y = path[-1]
                                    current_goal = (end_x, end_y)

                                    # 重置索引 + 卡死检测状态
                                    idx = 0
                                    last_idx = 0
                                    last_dist_to_next = None
                                    last_progress_time = time.time()

                                    # 为了安全，重新从下一轮 while 开始，避免下面用到旧的 path
                                    continue
                                else:
                                    print("动态重规划失败, 保持当前路径")


                # 判断是否已经靠近终点
                if max(abs(人物x - end_x), abs(人物y - end_y)) <= end_threshold:
                    if right_down:
                        # 释放右键()
                        监控控制.right_up()
                    break

                # 按当前位置，把路径索引纠正到最近的点（防止跨点）
                idx, _ = self._nearest_index_along_path(path, (人物x, 人物y), idx, max_lookahead=max_lookahead)

                # 安全保护：只有当“索引到最后一个点”并且“人物确实靠近终点”才认为走完
                # 注意：strict_end 模式下（end_threshold == 0）不走这块逻辑，
                #       只依赖前面“终点判定”那一句，强制必须走到终点格子。
                if (not strict_end) and idx >= len(path) - 1:
                    end_dist = max(abs(人物x - end_x), abs(人物y - end_y))

                    if end_dist <= end_threshold:
                        # 真正走到终点附近了，正常收尾
                        if right_down:
                            监控控制.right_up()
                        break
                    else:
                        # 索引到了最后一个点，但人离终点还很远 => 当前这条路径已经不可信了
                        print(
                            f"警告: idx 已到末尾但人物距终点仍然很远 (dist={end_dist})，"
                            "视为路径失效，退出寻路函数，交给上层重新算路径"
                        )
                        if right_down:
                            监控控制.right_up()
                        return road_list

                # ==== 修改：避免 idx 在最后一个点时越界 ====
                if idx >= len(path) - 1:
                    # 严格终点模式下会走到这里；我们强制用“倒数第二 -> 最后一个点”这条边来控制方向
                    if len(path) >= 2:
                        当前路径点 = path[-2]
                        下一点 = path[-1]
                    else:
                        # 理论上 path 长度为 1 的情况很少出现，这里兜个底
                        当前路径点 = path[-1]
                        下一点 = path[-1]
                else:
                    当前路径点 = path[idx]
                    下一点 = path[idx + 1]

                # === 新增：计算距离，用于判断是否卡死 ===
                dist_to_next = max(abs(人物x - 下一点[0]), abs(人物y - 下一点[1]))

                now = time.time()
                progressed = False

                # 条件1：路径索引变大了，说明向前推进了
                if idx != last_idx:
                    progressed = True
                # 条件2：索引没变，但距离变小了，也算有进展
                elif last_dist_to_next is None or dist_to_next < last_dist_to_next:
                    progressed = True

                if progressed:
                    last_progress_time = now
                    last_dist_to_next = dist_to_next
                    last_idx = idx
                elif now - last_progress_time > stuck_timeout:
                    # 既没拉近距离也没推进索引，持续超过 stuck_timeout 秒 => 判定卡死
                    print("检测到路径点卡死, idx=", idx, "下一点=", 下一点, "距离=", dist_to_next)
                    if right_down:
                        监控控制.right_up()
                    return road_list

                # === 是否是“直线段”？（人物点 + 下两个路径点） ===
                直线段 = False
                if idx + 2 < len(path):
                    直线段 = ai算法.check_the_connection(
                        当前路径点,
                        下一点,
                        path[idx + 2],
                    )

                # 依据直线/拐弯决定鼠标目标方位
                if 直线段:
                    目标方位 = 监控控制.判断方位(下一点[0], 下一点[1], 当前路径点[0], 当前路径点[1])
                    # ---------- 直线：右键长按 ----------
                    # 1. 如果方向变了 或者 之前没按过右键 -> 移动鼠标到新方向 & 按右键
                    if (not right_down) or (目标方位 != last_dir):
                        监控控制.移动方位不点击(目标方位)
                        if not right_down:
                            监控控制.right_down()
                            right_down = True

                    # 2. 已经按住且方向没变，就保持不动，让人物自己沿直线跑
                else:
                    目标方位 = 监控控制.判断方位(下一点[0], 下一点[1], 人物x, 人物y)
                    # ---------- 非直线：左键点走 ----------
                    # 1. 如果之前在右键长按，需要先松开右键
                    if right_down:
                        # 释放右键()
                        监控控制.right_up()
                        right_down = False

                    # 2. 移动到对应方向，点一下左键
                    监控控制.左键点击方位_走路(目标方位)

                last_dir = 目标方位

                # 如果人物已经贴近“下一路径点”，把索引推进
                if max(abs(人物x - 下一点[0]), abs(人物y - 下一点[1])) <= reach_threshold and idx < len(path) - 1:
                    idx += 1

                监控控制.延时(sleep_interval)
            bad_cells.clear()
            print('到达怪物,清空bad_cells:',bad_cells)
            return road_list
        except Exception as e:
            print(repr(e))  # 输出异常的类型
            traceback.print_exc()
        finally:
            监控控制.right_up()












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

        self.map_img = cv2.imread(config.MAP_IMAGE_PATH)

        # 大漠初始化参数集中到 config，便于环境切换与维护
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
            for A大漠对象,B大漠对象,C大漠对象,句柄 in zip(dms_a,dms_b,dms_c,self.句柄_列表):
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
                    # A大漠对象.MoveWindow(句柄, -8, -31)
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


        else:
            self.plainTextEdit.appendPlainText('未找到窗口句柄')

        # 鼠标按下和释放事件
        btn = self.findChild(QPushButton, "pushButton_qujubing")  # 修复：objectName 需使用实际控件名
        if btn is not None:
            self.pushButton_qujubing = btn  # 统一引用，避免 UI 名称漂移

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
        pass

    def ceshi2(self):
        try:

            dms_a[0].UseDict(2)
            s1 = time.perf_counter()
            frame,players = self.更新地图_玩家点()
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
                outfile="viz_demo.png"
            )
            cv2.waitKey(1)
            if safe_point is not None:
                s3 = time.perf_counter()
                # path = ai算法.a_star_eight(人物x, 人物y, safe_point[0], safe_point[1], frame, 1, 1, 1, 2, 1)
                path = ai算法.a_star_eight(人物x, 人物y, safe_point[0], safe_point[1], frame, 1, 0, 0, 0.001, 0)
                e3 = time.perf_counter()
                print("计算path耗时:", e3 - s3)

                print("a星寻路路径点",path)
                if path is not None:
                    ai_visual.visualize_grid_and_path(frame, path=path, win_name="path", cell_size=15)
                    ret_path_list = self.沿路径控制人物行走(path, False, False, 0, 0)
                    print("实际移动路径点",ret_path_list)
                    ai_visual.visualize_grid_and_path(frame, path=ret_path_list, win_name="ret_path_list", cell_size=15)

        except Exception as e:
            print(repr(e))  # 输出异常的类型
            traceback.print_exc()

    def 地图上绘制玩家点(self,img,玩家坐标列表:list):
        pb, pg, pr = config.PLAYER_COLOR  # 统一玩家颜色，避免与算法协议不一致
        for (mx,my) in 玩家坐标列表:
            img[my, mx][0] = pb
            img[my, mx][1] = pg
            img[my, mx][2] = pr
        return img

    def 更新地图_玩家点(self):
        frame = self.map_img.copy()
        # 使用默认 OCR 坐标入口，包含备用矩形回退
        玩家坐标列表 = dm_utils.scan_players(
                dms_a[0],
                监控控制.屏幕坐标转游戏坐标,
            )
        if 玩家坐标列表:
            print("玩家坐标列表",玩家坐标列表)
            frame = self.地图上绘制玩家点(frame,玩家坐标列表)
        return frame,玩家坐标列表

    def _nearest_index_along_path(self,path, pos, start_index, max_lookahead=6):
        """
        在 path[start_index : start_index+max_lookahead] 范围内，
        找到离当前人物坐标最近的路径点索引，防止人物走快了、跨点。
        """
        px, py = pos
        best_i = start_index
        best_d = 10 ** 9

        end = min(len(path), start_index + max_lookahead + 1)
        for i in range(start_index, end):
            d = max(abs(px - path[i][0]), abs(py - path[i][1]))  # Chebyshev 距离
            if d < best_d:
                best_d = d
                best_i = i

        return best_i, best_d


    def 沿路径控制人物行走(self, path,
                           small_area=False,
                           big_area=False,
                           end_threshold=1,
                           reach_threshold=1,
                           max_lookahead=6,
                           sleep_interval=0.05,
                           # ==== 新增参数：动态重规划 ====
                           dynamic_repath: bool = False,  # 是否开启动态重规划
                           repath_interval: float = 0.5,  # 两次重规划最小间隔(秒)
                           repath_radius: int = 25,  # next_move_a 搜索半径
                           repath_selection_method: int = 1,  # next_move_a 的 selection_method
                           a_star_kwargs: dict | None = None,  # A* 的参数配置
                           stop_event = None,  # ==== 新增：中断事件 ====
                           ):
        """
        根据 path 控制鼠标移动方向和点击，让人物沿 path 走到终点。

        依赖外部接口：
            - 判断方位(目的地x, 目的地y, 人物当前点x, 人物当前点y)
            - 移动方位不点击(目标方位)
            - left_click()
            - 按下右键(), 释放右键()
            - 八方位点击坐标 需已通过 八方位点击坐标计算(...) 预先算好

        参数：
            path            路径点列表 [(x1,y1), (x2,y2), ...]
            small_area      小范围找图找怪标志位,True为找图,False为不找图
            big_area        大范围找图找怪标志位,True为找图,False为不找图
            reach_threshold 把人物视为“到达某个路径点”的容差（格子数，Chebyshev）
            max_lookahead   从当前索引往前看多少个点，用于纠正索引
            sleep_interval  每轮循环的暂停时间（秒），根据游戏刷新速度自己调
        """
        if not path:
            return

        # ===== 入场检查：人物是否在路径起点附近 =====
        cur = dm_utils.ocr_player_pos(dms_a[0])
        if not cur or cur[0] < 0 or cur[1] < 0:
            print("警告: 入场时无法识别人 物坐标，放弃本次行走")
            return

        人物x0, 人物y0 = cur
        start_dist = max(abs(人物x0 - path[0][0]), abs(人物y0 - path[0][1]))
        print(f"入场检查: path[0]={path[0]}, 人物起始=({人物x0},{人物y0}), dist={start_dist}")

        if start_dist > 5:  # 阈值你自己调，比如 >3 或 >8
            print("警告: 人物与路径起点偏差太大，视为无效路径，退出，让上层重新算")
            return

        if a_star_kwargs is None:
            # 这里用你现在 main 里那一组 (1,1,1,2,1)
            a_star_kwargs = dict(
                foot_len=1,
                endpoint_deviation=1,
                safety_radius=1,
                safety_weight=2,
                close_penalty_distance=1,
            )

        road_list = []              # 记录走过了哪些坐标点
        end_x, end_y = path[-1]
        idx = 0                     # 迭代对象path的下标索引
        right_down = False
        last_dir = None

        # === 新增：卡死检测相关状态 ===
        last_idx = idx
        last_dist_to_next = None
        last_progress_time = time.time()
        stuck_timeout = 4.0  # 秒，按你游戏实际情况调，比如 3~8 秒

        # === 新增：重规划状态 ===
        current_goal = (end_x, end_y)  # 当前路径的最终目标点
        last_repath_time = 0.0  # 上次重规划时间戳

        # ==== 新增：是否“严格终点模式”（必须走到终点格子） ====
        strict_end = (end_threshold == 0)

        print('开始寻路')
        global bad_cells
        try:
            while True:

                # ==== 新增：被抢占后恢复时，立刻退出 ====
                if stop_event is not None and stop_event.is_set():
                    print("收到 stop_event 中断信号, 退出沿路径控制人物行走")
                    bad_cells.clear()
                    return road_list

                if small_area == True:
                    z, x, y = dms_a[0].AiFindPic(843, 359, 1084, 513, 怪物图片路径_不包括宝宝, 0.85, 0)
                    if z != -1:
                        bad_cells.clear()
                        print('小范围检测到怪,停止寻路,清空bad_cells:', bad_cells)
                        return road_list
                if big_area == True :
                    z, x, y = dms_a[0].AiFindPic(5, 28, 1916, 823, 怪物图片路径_不包括宝宝, 0.85, 0)
                    if z != -1:
                        bad_cells.clear()
                        print('大范围检测到怪,停止寻路,清空bad_cells:', bad_cells)
                        return road_list

                cur = dm_utils.ocr_player_pos(dms_a[0])
                # OCR 失败直接下一轮
                if not cur or cur[0] < 0 or cur[1] < 0:
                    time.sleep(0.05)
                    continue

                人物x, 人物y = cur
                # print(f"当前人物坐标: ({人物x}, {人物y}), 终点: ({end_x}, {end_y}), ChebDist={max(abs(人物x - end_x), abs(人物y - end_y))}")

                if (人物x,人物y) not in road_list:
                    road_list.append((人物x,人物y))


                # ========== 新增：动态重规划 ==========

                if dynamic_repath:
                    now = time.time()
                    if now - last_repath_time >= repath_interval:
                        last_repath_time = now

                        # 1) 更新地图（地图上要把玩家画成敌人/高风险）
                        frame,players = self.更新地图_玩家点()

                        # 2) 以人物当前位置为中心，重新找“安全点”
                        new_safe = ai算法.next_move_a(
                            (人物x, 人物y),
                            frame,
                            (人物x, 人物y),  # 以自己为 search_center
                            repath_radius,  # 例如 40 或 50
                            repath_selection_method,  # 0/1
                            players=players,
                            escape_mode='away',
                        )

                        if new_safe is not None:
                            # 和当前终点差距不大就没必要重算，防抖
                            old_end = current_goal
                            diff = max(abs(new_safe[0] - old_end[0]),
                                       abs(new_safe[1] - old_end[1]))

                            if diff >= 3:  # 差距至少 3 格才重规划，你自己看着调
                                # 3) 基于最新地图 + 新安全点重算 A*
                                new_path = ai算法.a_star_eight(
                                    start_x=人物x,
                                    start_y=人物y,
                                    end_x=new_safe[0],
                                    end_y=new_safe[1],
                                    img_path=frame,
                                    **a_star_kwargs
                                )

                                if new_path:
                                    print("动态重规划成功, 新终点:", new_path[-1])

                                    # 用新路径替换旧路径
                                    path = new_path
                                    end_x, end_y = path[-1]
                                    current_goal = (end_x, end_y)

                                    # 重置索引 + 卡死检测状态
                                    idx = 0
                                    last_idx = 0
                                    last_dist_to_next = None
                                    last_progress_time = time.time()

                                    # 为了安全，重新从下一轮 while 开始，避免下面用到旧的 path
                                    continue
                                else:
                                    print("动态重规划失败, 保持当前路径")


                # 判断是否已经靠近终点
                if max(abs(人物x - end_x), abs(人物y - end_y)) <= end_threshold:
                    if right_down:
                        # 释放右键()
                        监控控制.right_up()
                    break

                # 按当前位置，把路径索引纠正到最近的点（防止跨点）
                idx, _ = self._nearest_index_along_path(path, (人物x, 人物y), idx, max_lookahead=max_lookahead)

                # 安全保护：只有当“索引到最后一个点”并且“人物确实靠近终点”才认为走完
                # 注意：strict_end 模式下（end_threshold == 0）不走这块逻辑，
                #       只依赖前面“终点判定”那一句，强制必须走到终点格子。
                if (not strict_end) and idx >= len(path) - 1:
                    end_dist = max(abs(人物x - end_x), abs(人物y - end_y))

                    if end_dist <= end_threshold:
                        # 真正走到终点附近了，正常收尾
                        if right_down:
                            监控控制.right_up()
                        break
                    else:
                        # 索引到了最后一个点，但人离终点还很远 => 当前这条路径已经不可信了
                        print(
                            f"警告: idx 已到末尾但人物距终点仍然很远 (dist={end_dist})，"
                            "视为路径失效，退出寻路函数，交给上层重新算路径"
                        )
                        if right_down:
                            监控控制.right_up()
                        return road_list

                # ==== 修改：避免 idx 在最后一个点时越界 ====
                if idx >= len(path) - 1:
                    # 严格终点模式下会走到这里；我们强制用“倒数第二 -> 最后一个点”这条边来控制方向
                    if len(path) >= 2:
                        当前路径点 = path[-2]
                        下一点 = path[-1]
                    else:
                        # 理论上 path 长度为 1 的情况很少出现，这里兜个底
                        当前路径点 = path[-1]
                        下一点 = path[-1]
                else:
                    当前路径点 = path[idx]
                    下一点 = path[idx + 1]

                # === 新增：计算距离，用于判断是否卡死 ===
                dist_to_next = max(abs(人物x - 下一点[0]), abs(人物y - 下一点[1]))

                now = time.time()
                progressed = False

                # 条件1：路径索引变大了，说明向前推进了
                if idx != last_idx:
                    progressed = True
                # 条件2：索引没变，但距离变小了，也算有进展
                elif last_dist_to_next is None or dist_to_next < last_dist_to_next:
                    progressed = True

                if progressed:
                    last_progress_time = now
                    last_dist_to_next = dist_to_next
                    last_idx = idx
                elif now - last_progress_time > stuck_timeout:
                    # 既没拉近距离也没推进索引，持续超过 stuck_timeout 秒 => 判定卡死
                    print("检测到路径点卡死, idx=", idx, "下一点=", 下一点, "距离=", dist_to_next)
                    if right_down:
                        监控控制.right_up()
                    return road_list

                # === 是否是“直线段”？（人物点 + 下两个路径点） ===
                直线段 = False
                if idx + 2 < len(path):
                    直线段 = ai算法.check_the_connection(
                        当前路径点,
                        下一点,
                        path[idx + 2],
                    )

                # 依据直线/拐弯决定鼠标目标方位
                if 直线段:
                    目标方位 = 监控控制.判断方位(下一点[0], 下一点[1], 当前路径点[0], 当前路径点[1])
                    # ---------- 直线：右键长按 ----------
                    # 1. 如果方向变了 或者 之前没按过右键 -> 移动鼠标到新方向 & 按右键
                    if (not right_down) or (目标方位 != last_dir):
                        监控控制.移动方位不点击(目标方位)
                        if not right_down:
                            监控控制.right_down()
                            right_down = True

                    # 2. 已经按住且方向没变，就保持不动，让人物自己沿直线跑
                else:
                    目标方位 = 监控控制.判断方位(下一点[0], 下一点[1], 人物x, 人物y)
                    # ---------- 非直线：左键点走 ----------
                    # 1. 如果之前在右键长按，需要先松开右键
                    if right_down:
                        # 释放右键()
                        监控控制.right_up()
                        right_down = False

                    # 2. 移动到对应方向，点一下左键
                    监控控制.左键点击方位_走路(目标方位)

                last_dir = 目标方位

                # 如果人物已经贴近“下一路径点”，把索引推进
                if max(abs(人物x - 下一点[0]), abs(人物y - 下一点[1])) <= reach_threshold and idx < len(path) - 1:
                    idx += 1

                监控控制.延时(sleep_interval)
            bad_cells.clear()
            print('到达怪物,清空bad_cells:',bad_cells)
            return road_list
        except Exception as e:
            print(repr(e))  # 输出异常的类型
            traceback.print_exc()
        finally:
            监控控制.right_up()

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
                for 序号,(A大漠对象,B大漠对象,C大漠对象,句柄) in enumerate(zip(dms_a,dms_b,dms_c,self.句柄_列表)):
                    if self.A组线程对象列表[序号] == None:
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
        dms_a[0].UnBindWindow()
        if dms_a:
            del dms_a[0]  # 修复：原代码使用不存在的 dms，避免 NameError
        event.accept()  # 允许关闭
        print("关闭")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyWindow()
    window.show()
    cv2.waitKey()
    cv2.destroyAllWindows()
    sys.exit(app.exec_())


