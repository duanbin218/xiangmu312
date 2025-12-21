# -*- coding: utf-8 -*-
# Centralized resource/config values to avoid drift across threads.

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
MAP_CENTER_X = 964
MAP_CENTER_Y = 464
TILE_WIDTH = 48
TILE_HEIGHT = 32
DEFAULT_CIRCLE_RADIUS = 170

# 大漠初始化与绑定相关配置，集中管理便于切换环境。
DM_REG_CODE = "duanbin2187ebec7e363f16ead014d9bb6365ebdf6"
DM_ADD_CODE = "389749"
GAME_PROCESS_NAME = "557ltss20251027.exe"
GAME_WINDOW_TITLE_KEYWORD = "开放"
GAME_WINDOW_CLASS = ""
WINDOW_ENUM_FLAGS = 1 + 16

# BindWindowEx 参数集中化，避免多处硬编码。
BIND_DISPLAY = "gdi"
BIND_MOUSE = "windows"
BIND_KEYPAD = "windows"
BIND_PUBLIC_DESC = ""
BIND_MODE = 0

# 窗口初始移动偏移，统一配置便于调整。
WINDOW_MOVE_X = -3
WINDOW_MOVE_Y = -26

# OCR/识别坐标集中管理，避免多处硬编码导致漂移。
OCR_PLAYER_POS_MAIN = (48, 1057, 108, 1078)
OCR_PLAYER_POS_ALT = (60, 1061, 109, 1075)
OCR_PLAYER_POS_PATH = (49, 1061, 105, 1075)
OCR_HP_RECT = (21, 1042, 81, 1055)

# 玩家识别区域与坐标偏移配置。
PLAYER_SCAN_RECT = (3, 2, 1918, 924)
PLAYER_EXCLUDE_RECT = (928, 373, 1005, 396)
PLAYER_SCREEN_OFFSET_X = 7
PLAYER_SCREEN_OFFSET_Y = 83

# 颜色协议（BGR），与 ai算法._parse_enemies 保持一致。
ENEMY_COLOR_S = (19, 19, 255)   # 高危怪：半径/权重更大
ENEMY_COLOR_A = (7, 2, 254)     # 中危怪
ENEMY_COLOR_B = (7, 2, 128)     # 低危怪（预留）
PLAYER_COLOR = (20, 30, 1)      # 玩家点颜色，用于避让/风险计算
PET_COLOR = (0, 0, 100)         # 宝宝/宠物标记
