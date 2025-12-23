# -*- coding: utf-8 -*-
# Centralized resource/config values to avoid drift across threads.
from xiangmu312_codex.test.config import MONSTER_LIST_PATH

MONSTER_LIST_PATH = "./pic/guaiwu/longteng.txt"
ITEM_NAME_PATH = "./物品名字.txt"
ITEM_NAME_EXTRA = "士头|除魔|聚灵珠（小）|魔血石"
ITEM_TEXT_COLOR = "ffffff-000000"  # 物品找字颜色阈值，便于统一调整
PET_PIC_PATH = "./pic/guaiwu/宝宝.bmp"
TEMP_CAPTURE_BMP = "temp_img.bmp"
ITEM_MASK_BMP = "mask_rgb.bmp"
DISPLAY_INPUT_SCREEN = "screen"
ESCORT_BUREAU_PIC = "./pic/镖局.bmp"
ESCORT_START_PIC = "./pic/开始押镖.bmp"
ESCORT_ACCEPT_PIC = "./pic/接受护送.bmp"
ESCORT_CONFIRM_PIC = "./pic/镖车确定.bmp"
ESCORT_CHIEF_PIC = "./pic/镖局总管.bmp"
ESCORT_FINISH_PIC = "./pic/完成任务.bmp"
# 押镖流程找图区域配置，统一管理便于调参
ESCORT_REGION_MAIN = (5, 28, 1916, 823)
ESCORT_REGION_DIALOG = (8, 9, 390, 164)
ESCORT_REGION_CONFIRM = (700, 428, 1223, 657)
ESCORT_REGION_CHIEF = (11, 55, 1915, 718)
ESCORT_REGION_FINISH = (11, 20, 389, 161)
ESCORT_PIC_SIM = 0.8  # 押镖流程找图相似度阈值

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
MOUSE_MOVE_DURATION_MS = 2000  # 鼠标相对移动的默认时长，统一调整入口

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
识别人物坐标区域 = (48, 1057, 108, 1078)
识别人物血量区域 = (21, 1042, 81, 1055)
OCR_NUMBER_COLOR = "#255-50|#253-50"  # 统一数字类 OCR 颜色阈值

# 玩家识别区域与坐标偏移配置。
大范围识别玩家区域 = (3, 2, 1918, 924)
排除人物等级区域 = (928, 373, 1005, 396)
等级与中心点的X偏移 = 7
等级与中心点的Y偏移 = 83

# 物品名字长度 -> 屏幕坐标偏移（用于换算物品中心点）
ITEM_NAME_OFFSET_BY_LEN = {
    2: (10, 24),
    3: (16, 24),
    4: (22, 24),
    5: (28, 24),
    6: (36, 24),
}

# 玩家识别文本与颜色阈值，集中配置便于调整。
PLAYER_FIND_TEXT = "D4|D5|D6|Z4|Z5|Z6|F4|F5|F6"
PLAYER_FIND_COLOR = "ffffff-000000"

# 颜色协议（BGR），与 ai算法._parse_enemies 保持一致。
ENEMY_COLOR_S = (19, 19, 255)   # 高危怪：半径/权重更大
ENEMY_COLOR_A = (7, 2, 254)     # 中危怪
ENEMY_COLOR_B = (7, 2, 128)     # 低危怪（预留）
PLAYER_COLOR = (20, 30, 1)      # 玩家点颜色，用于避让/风险计算
PET_COLOR = (0, 0, 100)         # 宝宝/宠物标记
