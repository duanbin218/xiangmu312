# -*- coding: utf-8 -*-
# 大漠 OCR/识别通用工具，避免重复代码与解析错误。

import config


def ocr_player_pos(dm, rect=None):
    """
    通用人物坐标 OCR。
    - 统一字库与坐标入口，减少多处硬编码漂移
    - 解析失败时返回 (-1, -1)，避免抛异常影响主循环
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



















