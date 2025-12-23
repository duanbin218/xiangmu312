import kmNet
import random
import win32api
import time
import keyboard
import threading
import os
import ctypes
import math
import config

# 方位移动的随机范围，区分走路/跑步，避免多处硬编码。
WALK_R90_MIN = (-4, 4)
WALK_R90_MAX = (-100, 100)
WALK_R45 = (-36, 36)
RUN_R90_MIN = (-1, 1)
RUN_R90_MAX = (-50, 50)
RUN_R45 = (-50, 50)

# ================== 全局标志 & 事件 ==================
exit_flag = False
runtime_started = False  # 避免重复初始化 kmNet / 键盘监听

# 抢占事件：主打怪线程用的延时会等待这个事件
打怪_event = threading.Event()
打怪_event.set()  # 默认允许运行

全局_event = threading.Event()
全局_event.set()

# 新增：每个线程自己的“走路中断”事件
打怪_stop_event = threading.Event()
血量_stop_event = threading.Event()
监控_stop_event = threading.Event()   # 监控要不要用看你需求

# ========== 线程协作：语义化封装，避免各处随意 set/clear ==========
def pause_all():
    """暂停所有受控延时（打怪/血量），监控线程不受影响。"""
    全局_event.clear()

def resume_all():
    """恢复所有受控延时（打怪/血量），监控线程不受影响。"""
    全局_event.set()

def pause_combat():
    """暂停打怪线程的延时(血量/监控不受影响)."""
    打怪_event.clear()

def resume_combat():
    """恢复打怪线程的延时（血量/监控不受影响）。"""
    打怪_event.set()

def mark_walk_stopped(*stop_events):
    """标记当前行走任务作废，通知相应 stop_event。"""
    for ev in stop_events:
        if ev is not None:
            ev.set()

# ================== Windows 低层键盘监听 ==================
user32 = ctypes.WinDLL('user32', use_last_error=True)


def keyboard_listener():
    """
    使用 GetAsyncKeyState 监听 PrintScreen（0x2C），
    在游戏窗口内也能生效。
    """
    global exit_flag
    while not exit_flag:
        if user32.GetAsyncKeyState(0x2C) & 0x8000:  # VK_SNAPSHOT = 0x2C
            exit_flag = True
            print("检测到 Print Screen 按键，程序将退出")
            return
        time.sleep(0.05)  # 降低 CPU 占用


def init_runtime(ip=config.KMNET_IP, port=config.KMNET_PORT, token=config.KMNET_TOKEN):
    """
    显式初始化 kmNet 并启动键盘监听，避免 import 副作用。
    重复调用将被忽略。
    """
    global runtime_started
    if runtime_started:
        return
    kmNet.init(ip, port, token)
    threading.Thread(target=keyboard_listener, daemon=True).start()
    runtime_started = True

# ================== 延时函数（毫秒） ==================
def _delay_with_events(毫秒: int, wait_events=None, min_sleep: float | None = None):
    """
    统一延时循环，减少多处重复逻辑。
    - wait_events: 需要等待的 Event 列表（可为空）
    - min_sleep: 当剩余时间不足时的最小 sleep（监控线程可用）
    """
    global exit_flag
    start = time.perf_counter()
    target_ms = 毫秒

    while True:
        # 检查退出标志
        if exit_flag:
            kmNet.enc_right(0)
            kmNet.enc_left(0)
            os._exit(0)

        if wait_events:
            for ev in wait_events:
                if ev is not None:
                    ev.wait()

        elapsed_ms = (time.perf_counter() - start) * 1000
        if elapsed_ms >= target_ms:
            break

        remaining_ms = target_ms - elapsed_ms
        if remaining_ms > 0:
            sleep_time = min(0.1, remaining_ms / 1000)
        else:
            sleep_time = min_sleep if min_sleep is not None else 0.01
        time.sleep(sleep_time)


def 打怪延时(毫秒: int):
    """
    主打怪线程用的高精度延时函数：
    - 每 100ms 检查一次 exit_flag
    - 会等待 打怪_event，可以被其他线程抢占暂停
    """
    _delay_with_events(毫秒, wait_events=[全局_event, 打怪_event])


def 血量延时(毫秒: int):
    """
    血量监测线程用的高精度延时：
    - 同样每 100ms 检查 exit_flag
    - 不受 打怪_event 影响（不被抢占暂停）
    """
    _delay_with_events(毫秒, wait_events=[全局_event])


def 监控延时(毫秒: int):
    """
    监控线程用的高精度延时：
    - 同样每 100ms 检查 exit_flag
    - 最高优先级,不受任何 Event 影响
    """
    _delay_with_events(毫秒, wait_events=None, min_sleep=0.01)


# ================== 统一控制类：鼠标/键盘 + 游戏坐标 ==================
class 游戏控制器:
    def __init__(self, km=kmNet, delay_func=None,
                 圆心x=config.MAP_CENTER_X, 圆心y=config.MAP_CENTER_Y, 半径r=config.DEFAULT_CIRCLE_RADIUS):
        if delay_func is None:
            raise ValueError("必须传入延时函数 delay_func，例如 打怪延时/血量延时/监控延时")

        self.kmNet = km
        self._delay = delay_func
        self.八方位点击坐标 = self._计算八方位点击坐标(圆心x, 圆心y, 半径r)

    # ========= 基础延时 =========
    def 延时(self, 毫秒: int):
        """对外暴露的延时接口，内部统一用 _delay，避免递归。"""
        self._delay(毫秒)

    # ========= 鼠标基础操作 =========
    def _move_relative(self, dx, dy):
        """
        统一相对移动入口，便于后续调整移动策略。
        """
        self.kmNet.enc_move_auto(int(dx), int(dy), 2000)

    def move_without_click(
        self,
        目标x, 目标y,
        最小x偏移=0, 最大x偏移=0,
        最小y偏移=0, 最大y偏移=0,
        延时a=100, 延时b=200,
    ):
        """
        从当前位置相对移动到目标坐标，带随机偏移和延时。
        """
        当前x, 当前y = win32api.GetCursorPos()
        # print(f"\n起始位置: x={当前x}, y={当前y}")

        x移动 = 目标x - 当前x
        y移动 = 目标y - 当前y

        x随机偏移 = random.randint(最小x偏移, 最大x偏移)
        y随机偏移 = random.randint(最小y偏移, 最大y偏移)
        总x移动 = x移动 + x随机偏移
        总y移动 = y移动 + y随机偏移

        self._move_relative(总x移动, 总y移动)

        for _ in range(5):
            当前x, 当前y = win32api.GetCursorPos()
            x移动 = 目标x - 当前x
            y移动 = 目标y - 当前y
            if abs(x移动) < 2 and abs(y移动) < 2:
                # print("位置正确")
                break

            x随机偏移 = random.randint(最小x偏移, 最大x偏移)
            y随机偏移 = random.randint(最小y偏移, 最大y偏移)
            总x移动 = x移动 + x随机偏移
            总y移动 = y移动 + y随机偏移

            self._move_relative(总x移动, 总y移动)

            self.随机延时(10,50)

        self.随机延时(延时a,延时b)

    def move_with_left_click(
        self,
        目标x, 目标y,
        最小x偏移=0, 最大x偏移=0,
        最小y偏移=0, 最大y偏移=0,
        延时a=100, 延时b=200,
    ):
        self._move_with_click(
            "left",
            目标x, 目标y,
            最小x偏移, 最大x偏移,
            最小y偏移, 最大y偏移,
            延时a, 延时b,
            use_offset=True,
        )

    def move_with_right_click(
            self,
            目标x, 目标y,
            最小x偏移=0, 最大x偏移=0,
            最小y偏移=0, 最大y偏移=0,
            延时a=100, 延时b=200,
    ):
        """
        右键版带偏移移动点击，保持与左键一致的行为入口。
        """
        self._move_with_click(
            "right",
            目标x, 目标y,
            最小x偏移, 最大x偏移,
            最小y偏移, 最大y偏移,
            延时a, 延时b,
            use_offset=True,
        )

    def simple_move_without_click(self, 目标x, 目标y, 延时a=100, 延时b=200):
        当前x, 当前y = win32api.GetCursorPos()
        x移动 = 目标x - 当前x
        y移动 = 目标y - 当前y

        self._move_relative(x移动, y移动)

        self.随机延时(延时a, 延时b)

    def _move_with_click(
        self,
        button: str,
        目标x, 目标y,
        最小x偏移=0, 最大x偏移=0,
        最小y偏移=0, 最大y偏移=0,
        延时a=100, 延时b=200,
        use_offset: bool = True,
    ):
        """
        统一移动+点击入口，避免左右键和偏移/非偏移重复实现。
        """
        if button not in ("left", "right"):
            raise ValueError("button must be 'left' or 'right'")
        if use_offset:
            self.move_without_click(
                目标x, 目标y,
                最小x偏移, 最大x偏移,
                最小y偏移, 最大y偏移,
                延时a, 延时b,
            )
        else:
            self.simple_move_without_click(目标x, 目标y, 延时a, 延时b)
        self._mouse_click(button, 延时a, 延时b)

    def _mouse_click(self, button: str, 延时a=70, 延时b=200):
        """
        统一鼠标点击逻辑，避免左右键重复实现。
        """
        if button == "left":
            click = self.kmNet.enc_left
        elif button == "right":
            click = self.kmNet.enc_right
        else:
            raise ValueError("button must be 'left' or 'right'")

        click(1)
        self.随机延时(延时a, 延时b)
        click(0)
        self.随机延时(延时a, 延时b)

    def left_click(self):
        self._mouse_click("left")

    def right_click(self):
        self._mouse_click("right")

    def simple_move_with_left_click(self, 目标x, 目标y, 延时a=100, 延时b=200):
        self._move_with_click(
            "left",
            目标x, 目标y,
            延时a=延时a, 延时b=延时b,
            use_offset=False,
        )

    def simple_move_with_right_click(self, 目标x, 目标y, 延时a=100, 延时b=200):
        self._move_with_click(
            "right",
            目标x, 目标y,
            延时a=延时a, 延时b=延时b,
            use_offset=False,
        )

    def 键盘点击(self, HID值, 延时a=70, 延时b=200):
        self.kmNet.enc_keydown(HID值)
        self.随机延时(延时a, 延时b)
        self.kmNet.enc_keyup(HID值)
        self.随机延时(延时a, 延时b)

    def right_down(self):
        self.kmNet.enc_right(1)

    def right_up(self):
        self.kmNet.enc_right(0)

    def 随机延时(self, 最小延时, 最大延时):
        随机时间 = random.randint(最小延时, 最大延时)
        self._delay(随机时间)

    # ================== 游戏坐标/方位相关 ==================
    @staticmethod
    def _计算八方位点击坐标(圆心x, 圆心y, 半径r):
        八方位点击坐标 = []
        for i in range(8):
            角度 = i * 45  # 0:正东, 1:东北, 逆时针
            弧度 = math.radians(角度)
            x = 圆心x + 半径r * math.cos(弧度)
            y = 圆心y - 半径r * math.sin(弧度)
            八方位点击坐标.append((int(x), int(y)))
        return 八方位点击坐标

    @staticmethod
    def 判断方位(目的地x, 目的地y, 中心点x, 中心点y):
        if 目的地x > 中心点x and 目的地y == 中心点y:
            return '正东'
        elif 目的地x > 中心点x and 目的地y < 中心点y:
            return '东北'
        elif 目的地x == 中心点x and 目的地y < 中心点y:
            return '正北'
        elif 目的地x < 中心点x and 目的地y < 中心点y:
            return '西北'
        elif 目的地x < 中心点x and 目的地y == 中心点y:
            return '正西'
        elif 目的地x < 中心点x and 目的地y > 中心点y:
            return '西南'
        elif 目的地x == 中心点x and 目的地y > 中心点y:
            return '正南'
        elif 目的地x > 中心点x and 目的地y > 中心点y:
            return '东南'
        else:
            # 目的地 == 中心点 等情况
            return None

    def 方位取反(self, 目的地x, 目的地y, 中心点x, 中心点y):
        目标方位 = self.判断方位(目的地x, 目的地y, 中心点x, 中心点y)
        对应 = {
            '正东': '正西',
            '东北': '西南',
            '正北': '正南',
            '西北': '东南',
            '正西': '正东',
            '西南': '东北',
            '正南': '正北',
            '东南': '西北',
        }
        return 对应.get(目标方位)

    @classmethod
    def 屏幕坐标转游戏坐标(cls, 人物游戏x, 人物游戏y, 目标屏幕x, 目标屏幕y, 偏移量y=0):
        # 使用全局常量做中心点和格子尺寸
        屏幕坐标x偏移量 = config.MAP_CENTER_X - 目标屏幕x
        屏幕坐标y偏移量 = config.MAP_CENTER_Y + 偏移量y - 目标屏幕y
        游戏坐标x偏移量 = 屏幕坐标x偏移量 / config.TILE_WIDTH
        游戏坐标y偏移量 = 屏幕坐标y偏移量 / config.TILE_HEIGHT
        整数x偏移量 = cls.custom_int(游戏坐标x偏移量)
        整数y偏移量 = cls.custom_int(游戏坐标y偏移量)
        游戏坐标x = int(人物游戏x) - int(整数x偏移量)
        游戏坐标y = int(人物游戏y) - int(整数y偏移量)
        return 游戏坐标x, 游戏坐标y

    @staticmethod
    def custom_int(a: float, eps: float = 1e-12) -> int:
        """
        # a是正数,
        - 如果它的小数部分小于等于0.5,舍弃小数部分,变量a变成正整数,
        - 如果他的小数部分大于0.5,小数部分变成1,变量a变成正整数,
        # a是负数,
        - 如果它的小数部分小于-0.5,小数部分变成-1,变量a变成负整数,
        - 如果它的小数部分大于等于-0.5,舍弃小数部分,变量a变成负整数,
        """
        frac, _ = math.modf(a)
        base = int(a)  # 向 0 截断
        if a >= 0:
            return base + 1 if frac > 0.5 + eps else base
        else:
            return base - 1 if frac < -0.5 - eps else base

    _方位索引 = {
        "正东": 0, "东北": 1, "正北": 2, "西北": 3,
        "正西": 4, "西南": 5, "正南": 6, "东南": 7,
    }
    def _随机方向坐标(self, 目标方位, r90_min, r90_max, r45):
        idx = self._方位索引.get(目标方位)
        if idx is None:
            raise ValueError(f"未知方位: {目标方位}")

        base_x, base_y = self.八方位点击坐标[idx]

        if 目标方位 in ("正东", "正西"):
            dx = random.randint(*r90_max)
            dy = random.randint(*r90_min)
        elif 目标方位 in ("正北", "正南"):
            dx = random.randint(*r90_min)
            dy = random.randint(*r90_max)
        else:
            off = random.randint(*r45)
            dx = dy = off

        return base_x + dx, base_y + dy

    def 移动方位不点击(self, 目标方位):
        # 目标点 = 当前点 等情况，直接不动，避免抛异常
        if 目标方位 is None:
            return
        x, y = self._随机方向坐标(
            目标方位,
            r90_min=WALK_R90_MIN,
            r90_max=WALK_R90_MAX,
            r45=WALK_R45,
        )
        self.simple_move_without_click(x, y)

    def 左键点击方位_走路(self, 目标方位, 延时a=100, 延时b=200):
        if 目标方位 is None:
            return
        x, y = self._随机方向坐标(
            目标方位,
            r90_min=WALK_R90_MIN,
            r90_max=WALK_R90_MAX,
            r45=WALK_R45,
        )
        self.simple_move_with_left_click(x, y, 延时a, 延时b)

    def 右键点击方位_跑步(self, 目标方位, 延时a=100, 延时b=200):
        if 目标方位 is None:
            return
        x, y = self._随机方向坐标(
            目标方位,
            r90_min=RUN_R90_MIN,
            r90_max=RUN_R90_MAX,
            r45=RUN_R45,
        )
        self.simple_move_with_right_click(x, y, 延时a, 延时b)



# ================== 测试函数 ==================
# 测试鼠标每次移动的坐标是不是我们指定的坐标
def test():
    my_mouse = 游戏控制器(delay_func=监控延时)
    my_mouse.move_without_click(500, 500)

# 测试鼠标每次移动的相对坐标是不是100,100
def test1():
    kmNet.enc_move_auto(100, 100, 300)
    当前x, 当前y = win32api.GetCursorPos()
    print(f"结束位置: x={当前x}, y={当前y}")

# 按F3执行哪个程序
def on_f3_press(event):
    test1()


if __name__ == "__main__":
    init_runtime()
    keyboard.on_press_key('F3', on_f3_press)
    print("\n按下 F3 测试（按 ESC 退出）...")
    keyboard.wait('esc')
