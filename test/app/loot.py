import time
import traceback

import cv2
import numpy as np

from changliang11 import changliang as cl
import dm_utils



class LootFeature:
    """
    捡物封装：复用 Worker 的识别与寻路辅助方法，只聚合捡物流程。
    """

    def _exclude_region_from_mask(self,hsv_image, x1, y1, x2, y2):
        """
        排除掉指定矩形区域 (x1, y1) 到 (x2, y2) 的部分
        :param hsv_image: 原始的 HSV 图像
        :param x1, y1: 矩形区域的左上角坐标
        :param x2, y2: 矩形区域的右下角坐标
        :return: 排除矩形区域后的掩膜
        """
        # 创建一个全为1的掩膜 (和输入图像大小相同)
        mask = np.ones(hsv_image.shape[:2], dtype=np.uint8)

        # 创建一个全为0的矩形区域掩膜
        mask[y1:y2, x1:x2] = 0

        return mask

    def run_loop(self, dm, x1, y1, x2, y2, 控制器):
        try:
            img_path = "../temp_img.bmp"
            dm.Capture(x1, y1, x2, y2, img_path)
            人物x, 人物y = dm_utils.ocr_player_pos(dm)
            img = cv2.imread(img_path)
            if img is None:
                raise RuntimeError(f"读图失败: {img_path}")

            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

            # 排除掉指定矩形区域
            exclusion_mask1 = self._exclude_region_from_mask(hsv, 0,352,1920,378)
            exclusion_mask2 = self._exclude_region_from_mask(hsv, 0, 352, 1920, 378)
            hsv = cv2.bitwise_and(hsv, hsv, mask=exclusion_mask1)

            mask_yellow = cv2.inRange(hsv, cl.mix_yellow, cl.max_yellow)
            mask_green = cv2.inRange(hsv, cl.mix_green, cl.max_green)
            mask_blue = cv2.inRange(hsv, cl.mix_blue, cl.max_blue)
            mask_red1 = cv2.inRange(hsv, cl.mix_red1, cl.max_red1)
            mask_red2 = cv2.inRange(hsv, cl.mix_red2, cl.max_red2)
            mask_red = cv2.bitwise_or(mask_red1, mask_red2)

            物品游戏坐标列表 = set()
            self._collect_items(mask_yellow, img, 物品游戏坐标列表, 人物x, 人物y, x1, y1, 控制器)
            self._collect_items(mask_green, img, 物品游戏坐标列表, 人物x, 人物y, x1, y1, 控制器)
            self._collect_items(mask_blue, img, 物品游戏坐标列表, 人物x, 人物y, x1, y1, 控制器)
            self._collect_items(mask_red, img, 物品游戏坐标列表, 人物x, 人物y, x1, y1, 控制器)

            # print("物品列表:", 物品游戏坐标列表)
            return 物品游戏坐标列表
        except Exception as exc:  # noqa: BLE001
            print(repr(exc))
            traceback.print_exc()
            return set()

    def _collect_items(self, mask, img, out_set, 人物x, 人物y, offset_x, offset_y, 控制器):

        kernel = np.ones((1, 4), np.uint8)  # 横向 4 像素的小核
        mask_merged = cv2.dilate(mask, kernel, iterations=1)

        contours, _ = cv2.findContours(mask_merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        i = 0
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w > 25 and h > 5:
                # # 绘制所有轮廓,contours列表存储了所有的8个轮廓数据
                # draw_img = cv2.drawContours(img, cnt, -1, (0, 0, 255), thickness=5)
                # # 显示绘制的所有轮廓,可以填返回值,也可以填参数1,在参数1的图片上绘制轮廓
                # cv2.imshow("draw_img", draw_img)
                # cv2.waitKey(1)
                i += 1
                x1 = x + offset_x
                y1 = y + offset_y
                x2 = x1 + w
                y2 = y1 + h
                # print("x1", x1)
                # print("y1", y1)
                # print("x2", x2)
                # print("y2", y2)
                人物x, 人物y = int(人物x), int(人物y)
                物品屏幕中心x = int(x1 + w / 2)
                物品屏幕中心y = int(y1 + 24)
                # print("中心", 物品屏幕中心x, 物品屏幕中心y)
                物品游戏x, 物品游戏y = 控制器.屏幕坐标转游戏坐标(
                    人物x, 人物y,
                    物品屏幕中心x,
                    物品屏幕中心y,
                )
                out_set.add((物品游戏x, 物品游戏y))
        # print("\n", i)


__all__ = ["LootFeature"]
