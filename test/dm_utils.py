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
    """
    text = text.strip().replace("：", ":").replace(" ", "")
    if sep in text:
        parts = text.split(sep)
        if len(parts) == 2:
            try:
                return int(parts[0]), int(parts[1])
            except Exception:
                pass
    nums = re.findall(r"-?\d+", text)
    if len(nums) >= 2:
        try:
            return int(nums[0]), int(nums[1])
        except Exception:
            return -1, -1
    return -1, -1


def _ocr_int_pair(dm, rect, sep):
    """
    统一 OCR + 解析入口，避免多处重复处理。
    """
    text = dm.Ocr(*rect, OCR_NUMBER_COLOR, 1)
    if text == "":
        return -1, -1
    return _parse_int_pair(text, sep)


def ocr_player_pos(dm, rect=None):
    """
    通用人物坐标 OCR。
    - 统一字库与坐标入口，减少多处硬编码漂移
    - 解析失败时返回 (-1, -1)，避免抛异常影响主循环
    """

    if rect is None:
        rect = config.OCR_PLAYER_POS_MAIN
    dm.UseDict(0)
    return _ocr_int_pair(dm, rect, ":")


def ocr_hp(dm, rect=None):
    """
    通用血量 OCR。
    - 统一颜色阈值与解析逻辑，避免不同线程判断不一致
    - 解析失败时返回 (-1, -1)，避免误判
    """
    if rect is None:
        rect = config.OCR_HP_RECT
    dm.UseDict(0)
    return _ocr_int_pair(dm, rect, "/")


def scan_players(dm, screen_to_game, player_pos=None, player_rect=None):
    """
    扫描玩家坐标列表。
    - 统一 FindStrEx/ExcludePos/屏幕偏移逻辑
    - 解析失败返回空列表，避免中断主流程
    """
    # 优先使用传入的 player_pos，避免重复 OCR
    if player_pos is None:
        player_pos = ocr_player_pos(dm, player_rect)
    px, py = player_pos
    if px < 0 or py < 0:
        return []

    dm.UseDict(2)
    sx1, sy1, sx2, sy2 = config.PLAYER_SCAN_RECT
    ret = dm.FindStrEx(sx1, sy1, sx2, sy2, "D4|D5|D6|Z4|Z5|Z6|F4|F5|F6", "ffffff-000000", 1)
    if ret == "":
        return []

    ex1, ey1, ex2, ey2 = config.PLAYER_EXCLUDE_RECT
    ret1 = dm.ExcludePos(ret, 0,ex1, ey1, ex2, ey2)
    if ret1 == "":
        return []

    players = []
    for item in ret1.split("|"):
        parts = item.split(",")
        if len(parts) < 3:
            continue
        try:
            screen_x = int(parts[1]) + config.PLAYER_SCREEN_OFFSET_X
            screen_y = int(parts[2]) + config.PLAYER_SCREEN_OFFSET_Y
            game_x, game_y = screen_to_game(px, py, screen_x, screen_y)
            players.append((game_x, game_y))
        except Exception:
            # 单个点异常时跳过，保证整体流程不中断
            continue
    return players
