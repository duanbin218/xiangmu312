import time
import traceback

import cv2
import numpy as np

from changliang11 import changliang as cl
import dm_utils
import config

# 通过找色找地上物品
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
            exclusion_mask2 = self._exclude_region_from_mask(hsv, 4,253,1918,274)
            exclusion_mask = cv2.bitwise_or(exclusion_mask1, exclusion_mask2)
            hsv = cv2.bitwise_and(hsv, hsv, mask=exclusion_mask)

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




with open(config.ITEM_NAME_PATH,'r',encoding='ANSI') as f:
    物品名称路径 = f.read()
    物品名称路径 = 物品名称路径.replace('\n','|')+config.ITEM_NAME_EXTRA
    物品名称列表 = 物品名称路径.split('|')
    if config.DEBUG_LOG:
        print(物品名称路径)



# 通过找字找地上物品
class 找字找物:
    def _解析找字结果(self, ret, 物品名称列表, 人物x, 人物y, x1, y1, 控制器, out_set):
        if ret == "":
            return
        for item in ret.split("|"):
            parts = item.split(",")
            if len(parts) < 3:
                continue
            try:
                序号 = int(parts[0])
                if 序号 < 0 or 序号 >= len(物品名称列表):
                    continue
                物品屏幕x = int(parts[1]) + x1
                物品屏幕y = int(parts[2]) + y1
            except ValueError:
                continue
            物品名称 = 物品名称列表[序号]
            名字长度 = len(物品名称)
            offset = config.ITEM_NAME_OFFSET_BY_LEN.get(名字长度)
            if offset is None:
                # 未配置的名字长度先跳过，避免偏移错误
                continue
            off_x, off_y = offset
            物品游戏x, 物品游戏y = 控制器.屏幕坐标转游戏坐标(
                人物x, 人物y,
                物品屏幕x + off_x,
                物品屏幕y + off_y,
            )
            out_set.add((物品名称, (物品游戏x, 物品游戏y)))

    def _处理单色mask(
        self,
        dm,
        mask,
        mask_path,
        search_x2,
        search_y2,
        text,
        物品名称列表,
        人物x,
        人物y,
        x1,
        y1,
        控制器,
        out_set,
        color_name,
    ):
        if cv2.countNonZero(mask) == 0:
            return
        # 按颜色分别生成 mask，避免多色噪点叠加影响字库匹配
        mask_rgb = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        cv2.imwrite(mask_path, mask_rgb)
        # 释放缓存并切换到图片输入，避免旧图干扰识别
        dm.FreePic(mask_path)
        dm.SetDisplayInput(f"pic:{mask_path}")

        ret = dm.FindStrFastEx(0, 0, search_x2, search_y2, text, config.ITEM_TEXT_COLOR, 1)
        if config.DEBUG_LOG:
            print(f"颜色[{color_name}]识字结果: {ret}")
        self._解析找字结果(ret, 物品名称列表, 人物x, 人物y, x1, y1, 控制器, out_set)

    def 找物(self,dm,控制器,x1,y1,x2,y2):
        try:
            global 物品名称路径
            global 物品名称列表

            s = time.perf_counter()

            img_path = "../temp_img.bmp"
            dm.Capture(x1,y1,x2,y2, img_path)

            人物x,人物y = dm_utils.ocr_player_pos(dm)
            if config.DEBUG_LOG:
                print(人物x,人物y)
            if 人物x < 0 or 人物y < 0:
                # OCR 坐标无效时直接返回,避免坐标换算错误
                return set()
            人物x, 人物y = int(人物x), int(人物y)
            img = cv2.imread(img_path)
            if img is None:
                raise RuntimeError(f"读图失败: {img_path}")

            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

            # max_gray = np.array([136,70,211])
            # mix_gray = np.array([64,15,122])
            # mask_gray = cv2.inRange(hsv, mix_gray, max_gray)

            mask_yellow = cv2.inRange(hsv, cl.mix_yellow, cl.max_yellow)
            mask_green = cv2.inRange(hsv, cl.mix_green, cl.max_green)
            mask_blue = cv2.inRange(hsv, cl.mix_blue, cl.max_blue)
            mask_red1 = cv2.inRange(hsv, cl.mix_red1, cl.max_red1)
            mask_red2 = cv2.inRange(hsv, cl.mix_red2, cl.max_red2)
            mask_red = mask_red1 | mask_red2

            mask_path = "../mask_rgb.bmp"
            search_y2, search_x2 = img.shape[0] - 1, img.shape[1] - 1

            text = 物品名称路径
            物品游戏坐标列表 = set()

            dm.UseDict(1)
            try:
                # 分颜色依次找字，减少多色合并带来的噪点干扰
                self._处理单色mask(
                    dm, mask_yellow, mask_path, search_x2, search_y2, text,
                    物品名称列表, 人物x, 人物y, x1, y1, 控制器, 物品游戏坐标列表, "黄"
                )
                self._处理单色mask(
                    dm, mask_green, mask_path, search_x2, search_y2, text,
                    物品名称列表, 人物x, 人物y, x1, y1, 控制器, 物品游戏坐标列表, "绿"
                )
                self._处理单色mask(
                    dm, mask_blue, mask_path, search_x2, search_y2, text,
                    物品名称列表, 人物x, 人物y, x1, y1, 控制器, 物品游戏坐标列表, "蓝"
                )
                self._处理单色mask(
                    dm, mask_red, mask_path, search_x2, search_y2, text,
                    物品名称列表, 人物x, 人物y, x1, y1, 控制器, 物品游戏坐标列表, "红"
                )
            finally:
                # 异常也要恢复屏幕输入，避免影响后续识别
                dm.SetDisplayInput(config.DISPLAY_INPUT_SCREEN)

            ee = time.perf_counter()
            t = ee - s
            if config.DEBUG_LOG:
                print('找物品用时:', t)
                print(物品游戏坐标列表)
            return 物品游戏坐标列表
        except Exception as e:
            print(repr(e))
            traceback.print_exc()






__all__ = ["LootFeature"]
