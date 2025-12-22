# -*- coding: utf-8 -*-
# 大漠 OCR/识别通用工具，避免重复代码与解析错误。

import re
import config


def ocr_player_pos(dm, rect=None):
    """
    通用人物坐标 OCR。
    - 统一字库与坐标入口，减少多处硬编码漂移
    - 解析失败时返回 (-1, -1)，避免抛异常影响主循环
    """
    if rect is None:
        rect = config.OCR_PLAYER_POS_MAIN
    x1, y1, x2, y2 = rect
    dm.UseDict(0)
    text = dm.Ocr(x1, y1, x2, y2, "#255-50|#253-50", 1)
    if text == "":
        return -1, -1
    # 统一清理 OCR 文本，兼容中文冒号/空格等噪声
    text = text.strip().replace("：", ":").replace(" ", "")
    if ":" in text:
        parts = text.split(":")
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
