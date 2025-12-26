import numpy as np

class changliang():
    max_yellow = np.array([35, 255, 255])
    mix_yellow = np.array([25, 179, 145])

    max_green = np.array([65, 255, 255])
    mix_green = np.array([55,205,150])

    max_blue = np.array([104, 210, 251])
    # 不包括中间透明公告栏的颜值范围 90, 109, 140
    mix_blue = np.array([78,96,111])            # 包括中间透明公告栏的颜色范围 78,96,111

    max_red1 = np.array([179, 255, 255])
    mix_red1 = np.array([170, 225, 150])

    max_red2 = np.array([10, 255, 255])
    mix_red2 = np.array([0, 225, 150])


