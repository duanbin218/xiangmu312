# -*- coding: utf-8 -*-
# 大漠 OCR/识别通用工具，避免重复代码与解析错误。
import re
import config

OCR_NUMBER_COLOR = "#255-50|#253-50"  # 统一数字类 OCR 颜色阈值，避免多处硬编码漂移

def _parse_int_pair(text, sep):
    """
    解析 OCR 字符串中的两个整数。
    - 优先按指定分隔符解析（例如 ":" 或 "/"）
    - 解析失败时兜底提取数字，降低噪声影响
    :param text: 传入的带解析的字符串,格式是"123:321"或者"123/321"
    :param sep: 分隔符号
    :return: 返回2个整数
    """
    # 统一清理 OCR 文本，兼容中文冒号/空格等噪声
    text = text.replace(" ", "").replace("：", ":").strip(":")
    if sep in text:
        parts = text.split(sep)
        if len(parts) == 2:
            try:
                return int(parts[0]), int(parts[1])
            except Exception:
                pass
    # 兜底：提取数字，避免格式异常导致坐标丢失
    nums = re.findall(r"-?\d+", text)
    if len(nums) >= 2:
        try:
            return int(nums[0]), int(nums[1])
        except Exception:
            # OCR 噪声或格式异常时不打断流程
            return -1, -1
    return -1, -1

# region OCR识别人物坐标
def ocr_player_pos(dm, rect=None):
    """
    通用人物坐标 OCR。
    - 统一字库与坐标入口，减少多处硬编码漂移
    - 解析失败时返回 (-1, -1)，避免抛异常影响主循环
    :param dm: 大漠对象
    :param rect: ocr识别区域
    """
    if rect is None:
        rect = config.识别人物坐标区域
    x1,y1,x2,y2 = rect
    dm.UseDict(0)
    text = dm.Ocr(x1,y1,x2,y2,OCR_NUMBER_COLOR, 1)
    if text == "":
        return(-1,-1)
    # 统一解析入口，降低 OCR 噪声造成的坐标丢失
    return _parse_int_pair(text, ":")
# endregion

# region OCR识别人物血量
def ocr_hp(dm, rect=None):
    """
    通用血量 OCR。
    - 统一颜色阈值与解析逻辑，避免不同线程判断不一致
    - 解析失败时返回 (-1, -1)，避免误判
    :param dm: 大漠对象
    :param rect: 识别区域
    :return: 两个整数
    """
    if rect is None:
        rect = config.识别人物血量区域
    dm.UseDict(0)
    text = dm.Ocr(*rect, OCR_NUMBER_COLOR, 1)
    if text == "":
        return -1,-1
    return _parse_int_pair(text, "/")
# endregion

# region 找图识别玩家,屏幕坐标转换成游戏地图坐标
def scan_player(dm, screen_to_game, player_pos=None, player_rect=None):
    """
    通用人物坐标 OCR。
    - 统一字库与坐标入口，减少多处硬编码漂移
    - 解析失败时返回 (-1, -1)，避免抛异常影响主循环
    :param dm: 大漠对象
    :param screen_to_game: 回调函数,屏幕坐标转换成游戏地图坐标
    :param player_pos: 人物当前坐标
    :param player_rect: ocr识别当前人物坐标区域
    :return:
    """
    if player_pos is None:
        player_pos = ocr_player_pos(dm, player_rect)
    px,py = player_pos
    if px < 0 or py < 0:
        return []

    dm.UseDict(2)
    ret = dm.FindStrEx(*config.大范围识别玩家区域,"D4|D5|D6|Z4|Z5|Z6|F4|F5|F6", "ffffff-000000", 1)
    if ret == "":
        return []

    ret1 = dm.ExcludePos(ret, 0, *config.排除人物等级区域)
    if ret1 == "":
        return []

    players = []
    for item in ret1.split("|"):
        parts = item.split(",")
        if len(parts)<3:
            continue
        try:
            screen_x = int(parts[1]) + config.等级与中心点的X偏移
            screen_y = int(parts[2]) + config.等级与中心点的Y偏移
            game_x, game_y = screen_to_game(px,py,screen_x,screen_y)
            players.append((game_x,game_y))
        except Exception:
            # 单个点异常时跳过，保证整体流程不中断
            continue
    return players
# endregion
















