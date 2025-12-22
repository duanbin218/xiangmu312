# -*- coding: utf-8 -*-
# 大漠 OCR/识别通用工具，避免重复代码与解析错误。

import config

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
    text = dm.Ocr(x1,y1,x2,y2,"#255-50|#253-50", 1)
    if text == "":
        return(-1,-1)
    try:
        text = text.strip(":")
        parts = text.split(":")
        if len(parts) != 2:
            return(-1,-1)
        return int(parts[0]), int(parts[1])
    except Exception:
        # OCR 噪声或格式异常时不打断流程
        return -1,-1
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
















