# -*- coding: utf-8 -*-
# Centralized resource/config values to avoid drift across threads.
from xiangmu312_codex.test.config import MONSTER_LIST_PATH

MONSTER_LIST_PATH = "./pic/guaiwu/longteng.txt"
ITEM_NAME_PATH = "./物品名字.txt"
ITEM_NAME_EXTRA = "士头|除魔|聚灵珠（小）|魔血石"

DICT_NUM_PATH = "./字库/数字.txt"
DICT_SYS_PATH = "./字库/系统字库 - 副本.txt"
DICT_PLAYER_PATH = "./字库/玩家字库.txt"

MAP_IMAGE_PATH = "xinrenditu.bmp"

# kmNet connection settings (init_runtime defaults).
KMNET_IP = "192.168.2.188"
KMNET_PORT = "1538"
KMNET_TOKEN = "86C2E466"

# Map/coordinate settings used by kmNet controls.
# ================== 地图/坐标相关全局常量 ==================
# 统一中心点 & 只改这里即可全局生效
MAP_CENTER_X = 964           # 小地图/坐标系中心屏幕X
MAP_CENTER_Y = 464           # 小地图/坐标系中心屏幕Y
TILE_WIDTH = 48              # 游戏中 X 方向每格对应的屏幕像素
TILE_HEIGHT = 32             # 游戏中 Y 方向每格对应的屏幕像素
DEFAULT_CIRCLE_RADIUS = 170  # 八方位点击位置圆半径范围
