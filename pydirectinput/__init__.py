'''
Partial implementation of DirectInput function calls to simulate
mouse and keyboard inputs.
'''

# native imports
import ctypes
import functools
import inspect
import time
from typing import (
    TYPE_CHECKING, Any, Callable, Final, Literal, Sequence, TypeAlias, TypeVar,
)


if TYPE_CHECKING:
    # https://github.com/python/mypy/issues/7540#issuecomment-845741357
    POINTER_TYPE = ctypes.pointer
else:
    # Monkeypatch typed pointer from typeshed into ctypes
    class pointer:
        @classmethod
        def __class_getitem__(cls, item):
            return ctypes.POINTER(item)
    POINTER_TYPE = pointer

# ==================================================================================================
# ===== External constants =========================================================================
# ==================================================================================================

# "Constants" for failsafe check and pause
# Intendend to be modified by callers
FAILSAFE: bool = True
FAILSAFE_POINTS: list[tuple[int, int]] = [(0, 0)]
PAUSE: float = 0.01  # 1/100 second pause by default.


# ==================================================================================================
# ===== Internal constants =========================================================================
# ==================================================================================================

# Constants for the mouse button names
_LEFT: Final[str] = "left"
_MIDDLE: Final[str] = "middle"
_RIGHT: Final[str] = "right"
_PRIMARY: Final[str] = "primary"
_SECONDARY: Final[str] = "secondary"

# INPUT type constants
_INPUT_MOUSE: Literal[0x0000] = 0x0000  # ctypes.c_ulong(0x0000)
_INPUT_KEYBOARD: Literal[0x0001] = 0x0001  # ctypes.c_ulong(0x0001)
_INPUT_HARDWARE: Literal[0x0002] = 0x0002  # ctypes.c_ulong(0x0002)

# Mouse Scan Code Mappings
_MOUSEEVENTF_MOVE: Literal[0x0001] = 0x0001  # ctypes.c_ulong(0x0001)
_MOUSEEVENTF_ABSOLUTE: Literal[0x8000] = 0x8000  # ctypes.c_ulong(0x8000)
_MOUSEEVENTF_WHEEL: Literal[0x0800] = 0x0800  # ctypes.c_ulong(0x0800)

_MOUSEEVENTF_LEFTDOWN: Literal[0x0002] = 0x0002  # ctypes.c_ulong(0x0002)
_MOUSEEVENTF_LEFTUP: Literal[0x0004] = 0x0004  # ctypes.c_ulong(0x0004)
_MOUSEEVENTF_LEFTCLICK: Final[int] = (
    _MOUSEEVENTF_LEFTDOWN + _MOUSEEVENTF_LEFTUP  # ctypes.c_ulong(0x0006)
)
_MOUSEEVENTF_RIGHTDOWN: Literal[0x0008] = 0x0008  # ctypes.c_ulong(0x0008)
_MOUSEEVENTF_RIGHTUP: Literal[0x0010] = 0x0010  # ctypes.c_ulong(0x0010)
_MOUSEEVENTF_RIGHTCLICK: Final[int] = (
    _MOUSEEVENTF_RIGHTDOWN + _MOUSEEVENTF_RIGHTUP  # ctypes.c_ulong(0x0018)
)
_MOUSEEVENTF_MIDDLEDOWN: Literal[0x0020] = 0x0020  # ctypes.c_ulong(0x0020)
_MOUSEEVENTF_MIDDLEUP: Literal[0x0040] = 0x0040  # ctypes.c_ulong(0x0040)
_MOUSEEVENTF_MIDDLECLICK: Final[int] = (
    _MOUSEEVENTF_MIDDLEDOWN + _MOUSEEVENTF_MIDDLEUP  # ctypes.c_ulong(0x0060)
)

# KeyBdInput Flags
_KEYEVENTF_EXTENDEDKEY: Literal[0x0001] = 0x0001  # ctypes.c_ulong(0x0001)
_KEYEVENTF_KEYUP: Literal[0x0002] = 0x0002  # ctypes.c_ulong(0x0002)
_KEYEVENTF_UNICODE: Literal[0x0004] = 0x0004  # ctypes.c_ulong(0x0004)
_KEYEVENTF_SCANCODE: Literal[0x0008] = 0x0008  # ctypes.c_ulong(0x0008)

# MapVirtualKey Map Types
_MAPVK_VK_TO_VSC: Literal[0] = 0  # ctypes.c_unit(0)
_MAPVK_VSC_TO_VK: Literal[1] = 1  # ctypes.c_unit(1)
_MAPVK_VK_TO_CHAR: Literal[2] = 2  # ctypes.c_unit(2)
_MAPVK_VSC_TO_VK_EX: Literal[3] = 3  # ctypes.c_unit(3)
_MAPVK_VK_TO_VSC_EX: Literal[4] = 4  # ctypes.c_unit(4)

# GetSystemMetrics nIndex arguments
_SM_CXSCREEN: Literal[0] = 0
_SM_CYSCREEN: Literal[1] = 1

# ==================================================================================================
# ===== C struct redefinitions =====================================================================
# ==================================================================================================
_PUL_PyType: TypeAlias = type[POINTER_TYPE[ctypes.c_ulong]]
_PUL: _PUL_PyType = ctypes.POINTER(ctypes.c_ulong)


class _KEYBDINPUT(ctypes.Structure):
    wVk: int  # ctypes.c_ushort
    wScan: int  # ctypes.c_ushort
    dwFlags: int  # ctypes.c_ulong
    time: int  # ctypes.c_ulong
    dwExtraInfo: POINTER_TYPE[ctypes.c_ulong]
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", _PUL)]


class _HARDWAREINPUT(ctypes.Structure):
    uMsg: int  # ctypes.c_ulong
    wParamL: int  # ctypes.c_short
    wParamH: int  # ctypes.c_ushort
    _fields_ = [("uMsg", ctypes.c_ulong),
                ("wParamL", ctypes.c_short),
                ("wParamH", ctypes.c_ushort)]


class _MOUSEINPUT(ctypes.Structure):
    dx: int  # ctypes.c_long
    dy: int  # ctypes.c_long
    mouseData: int  # ctypes.c_ulong
    dwFlags: int  # ctypes.c_ulong
    time: int  # ctypes.c_ulong
    dwExtraInfo: POINTER_TYPE[ctypes.c_ulong]
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", _PUL)]


class _POINT(ctypes.Structure):
    x: int  # ctypes.c_long
    y: int  # ctypes.c_long
    _fields_ = [("x", ctypes.c_long),
                ("y", ctypes.c_long)]


class _INPUT_UNION(ctypes.Union):
    ki: _KEYBDINPUT
    mi: _MOUSEINPUT
    hi: _HARDWAREINPUT
    _fields_ = [("ki", _KEYBDINPUT),
                ("mi", _MOUSEINPUT),
                ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    type: Literal[0, 1, 2]  # ctypes.c_ulong
    ii: _INPUT_UNION
    _anonymous_ = ('ii', )
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", _INPUT_UNION)]


# ==================================================================================================
# ==== User32 functions ============================================================================
# ==================================================================================================

# ----- SendInput --------------------------------------------------------------
_SendInput: Callable[
    [
        ctypes.c_uint,  # cInputs: ctypes.c_uint
        POINTER_TYPE[_INPUT],  # pInputs: POINTER_TYPE[INPUT]
        ctypes.c_int  # cbSize: ctypes.c_int
    ],
    int  # -> ctypes.c_uint
] = ctypes.windll.user32.SendInput


def send_input(
    inputs: _INPUT | Sequence[_INPUT],
) -> int:
    '''
    Abstraction layer over SendInput (winuser.h)

    See https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput
    '''
    # prepare arguments
    cInputs: ctypes.c_uint
    __Inputs: ctypes.Array[_INPUT]
    pInputs: POINTER_TYPE[_INPUT]
    cbSize: ctypes.c_int
    if isinstance(inputs, _INPUT):
        # -> single element array
        cInputs = ctypes.c_uint(1)
        __Inputs = (_INPUT * 1)(inputs)
    else:
        cInputs = ctypes.c_uint(len(inputs))
        __Inputs = (_INPUT * len(inputs))(*inputs)
    pInputs = ctypes.pointer(__Inputs[0])
    cbSize = ctypes.c_int(ctypes.sizeof(__Inputs))
    # execute function
    return _SendInput(cInputs, pInputs, cbSize)


# ----- MapVirtualKeyW ---------------------------------------------------------
_MapVirtualKeyW: Callable[
    [
        ctypes.c_uint,  # uCode: ctypes.c_uint
        ctypes.c_uint  # uMapType: ctypes.c_uint
    ],
    int  # -> ctypes.c_uint
] = ctypes.windll.user32.MapVirtualKeyW


def map_virtual_key(
    uCode: int,
    uMapType: Literal[0, 1, 2, 3]
) -> int:
    '''
    Abstraction layer over MapVirtualKeyW (winuser.h)

    See https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-mapvirtualkeyw
    '''
    return _MapVirtualKeyW(ctypes.c_uint(uCode), ctypes.c_uint(uMapType))


# ----- GetSystemMetrics -------------------------------------------------------
_GetSystemMetrics: Callable[
    [
        int  # nIndex: ctypes.c_int
    ],
    int  # -> ctypes.c_int
] = ctypes.windll.user32.GetSystemMetrics


def get_system_metrics(nIndex: int) -> int:
    '''
    Abstraction layer over GetSystemMetrics (winuser.h)

    See https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getsystemmetrics
    '''
    return _GetSystemMetrics(nIndex)


# ----- GetCursorPos -----------------------------------------------------------
_GetCursorPos: Callable[
    [
        POINTER_TYPE[_POINT]  # lpPoint: ctypes.c_int
    ],
    bool  # -> ctypes.c_bool
] = ctypes.windll.user32.GetCursorPos


def get_cursor_pos() -> _POINT:
    '''
    Abstraction layer over GetCursorPos (winuser.h)

    See https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getcursorpos
    '''
    cursor = _POINT()
    _GetCursorPos(ctypes.pointer(cursor))
    return cursor


# ==================================================================================================
# ===== Keyboard Scan Code Mappings ================================================================
# ==================================================================================================

KEYBOARD_MAPPING = {
    'escape': 0x01,
    'esc': 0x01,
    'f1': 0x3B,
    'f2': 0x3C,
    'f3': 0x3D,
    'f4': 0x3E,
    'f5': 0x3F,
    'f6': 0x40,
    'f7': 0x41,
    'f8': 0x42,
    'f9': 0x43,
    'f10': 0x44,
    'f11': 0x57,
    'f12': 0x58,
    'printscreen': 0xB7,
    'prntscrn': 0xB7,
    'prtsc': 0xB7,
    'prtscr': 0xB7,
    'scrolllock': 0x46,
    'pause': 0xC5,
    '`': 0x29,
    '1': 0x02,
    '2': 0x03,
    '3': 0x04,
    '4': 0x05,
    '5': 0x06,
    '6': 0x07,
    '7': 0x08,
    '8': 0x09,
    '9': 0x0A,
    '0': 0x0B,
    '-': 0x0C,
    '=': 0x0D,
    'backspace': 0x0E,
    'insert': 0xD2 + 1024,
    'home': 0xC7 + 1024,
    'pageup': 0xC9 + 1024,
    'pagedown': 0xD1 + 1024,
    # numpad
    'numlock': 0x45,
    'divide': 0xB5 + 1024,
    'multiply': 0x37,
    'subtract': 0x4A,
    'add': 0x4E,
    'decimal': 0x53,
    'numpadenter': 0x9C + 1024,
    'numpad1': 0x4F,
    'numpad2': 0x50,
    'numpad3': 0x51,
    'numpad4': 0x4B,
    'numpad5': 0x4C,
    'numpad6': 0x4D,
    'numpad7': 0x47,
    'numpad8': 0x48,
    'numpad9': 0x49,
    'numpad0': 0x52,
    # end numpad
    'tab': 0x0F,
    'q': 0x10,
    'w': 0x11,
    'e': 0x12,
    'r': 0x13,
    't': 0x14,
    'y': 0x15,
    'u': 0x16,
    'i': 0x17,
    'o': 0x18,
    'p': 0x19,
    '[': 0x1A,
    ']': 0x1B,
    '\\': 0x2B,
    'del': 0xD3 + 1024,
    'delete': 0xD3 + 1024,
    'end': 0xCF + 1024,
    'capslock': 0x3A,
    'a': 0x1E,
    's': 0x1F,
    'd': 0x20,
    'f': 0x21,
    'g': 0x22,
    'h': 0x23,
    'j': 0x24,
    'k': 0x25,
    'l': 0x26,
    ';': 0x27,
    "'": 0x28,
    'enter': 0x1C,
    'return': 0x1C,
    'shift': 0x2A,
    'shiftleft': 0x2A,
    'z': 0x2C,
    'x': 0x2D,
    'c': 0x2E,
    'v': 0x2F,
    'b': 0x30,
    'n': 0x31,
    'm': 0x32,
    ',': 0x33,
    '.': 0x34,
    '/': 0x35,
    'shiftright': 0x36,
    'ctrl': 0x1D,
    'ctrlleft': 0x1D,
    'win': 0xDB + 1024,
    'winleft': 0xDB + 1024,
    'alt': 0x38,
    'altleft': 0x38,
    ' ': 0x39,
    'space': 0x39,
    'altright': 0xB8 + 1024,
    'winright': 0xDC + 1024,
    'apps': 0xDD + 1024,
    'ctrlright': 0x9D + 1024,
    # arrow key scancodes can be different depending on the hardware,
    # so I think the best solution is to look it up based on the virtual key
    # https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-mapvirtualkeya?redirectedfrom=MSDN
    'up': map_virtual_key(0x26, _MAPVK_VK_TO_VSC),
    'left': map_virtual_key(0x25, _MAPVK_VK_TO_VSC),
    'down': map_virtual_key(0x28, _MAPVK_VK_TO_VSC),
    'right': map_virtual_key(0x27, _MAPVK_VK_TO_VSC),
}


# ==================================================================================================
# ===== Fail Safe and Pause implementation =========================================================
# ==================================================================================================

class FailSafeException(Exception):
    pass


def failSafeCheck() -> None:
    if FAILSAFE and tuple(position()) in FAILSAFE_POINTS:
        raise FailSafeException(
            "PyDirectInput fail-safe triggered from mouse moving to a corner of the screen. "
            "To disable this fail-safe, set pydirectinput.FAILSAFE to False. "
            "DISABLING FAIL-SAFE IS NOT RECOMMENDED."
        )


def _handlePause(_pause: Any) -> None:
    '''Pause the default amount of time if `_pause=True` in function arguments'''
    if _pause:
        assert isinstance(PAUSE, int) or isinstance(PAUSE, float)
        time.sleep(PAUSE)


RT = TypeVar('RT')  # return type


# direct copy of _genericPyAutoGUIChecks()
def _genericPyDirectInputChecks(wrappedFunction: Callable[..., RT]) -> Callable[..., RT]:
    '''Decorator for wrapping input functions'''
    @functools.wraps(wrappedFunction)
    def wrapper(*args: Any, **kwargs: Any):
        funcArgs = inspect.getcallargs(wrappedFunction, *args, **kwargs)
        failSafeCheck()
        returnVal = wrappedFunction(*args, **kwargs)
        _handlePause(funcArgs.get("_pause"))
        return returnVal
    return wrapper


# ==================================================================================================
# ===== Helper Functions ===========================================================================
# ==================================================================================================

def _to_windows_coordinates(x: int = 0, y: int = 0) -> tuple[int, int]:
    '''
    Convert x,y coordinates to windows form and return as tuple (x, y).
    '''
    display_width, display_height = size()

    # the +1 here prevents exactly mouse movements from sometimes ending up off by 1 pixel
    windows_x = (x * 65536) // display_width + 1
    windows_y = (y * 65536) // display_height + 1

    return windows_x, windows_y


# position() works exactly the same as PyAutoGUI.
# I've duplicated it here so that moveRel() can use it to calculate
# relative mouse positions.
def position(x: int | None = None, y: int | None = None) -> tuple[int, int]:
    '''
    Return the current mouse position as tuple (x, y).
    '''
    cursor = get_cursor_pos()
    return (x if x else cursor.x, y if y else cursor.y)


# size() works exactly the same as PyAutoGUI.
# I've duplicated it here so that _to_windows_coordinates() can use it
# to calculate the window size.
def size() -> tuple[int, int]:
    '''
    Return the display size as tuple (x, y).
    '''
    return (get_system_metrics(_SM_CXSCREEN), get_system_metrics(_SM_CYSCREEN))


# ==================================================================================================
# ===== Main Mouse Functions =======================================================================
# ==================================================================================================

# Ignored parameters: duration, tween, logScreenshot
@_genericPyDirectInputChecks
def mouseDown(
    x: int | None = None,
    y: int | None = None,
    button: str = _PRIMARY,
    duration: float | None = None,
    tween: None = None,
    logScreenshot: bool = False,
    _pause: bool = True,
) -> None:
    '''
    Press down mouse button `button`.
    '''
    if x is not None or y is not None:
        moveTo(x, y)

    ev: int | None = None
    if button == _PRIMARY or button == _LEFT:
        ev = _MOUSEEVENTF_LEFTDOWN
    elif button == _MIDDLE:
        ev = _MOUSEEVENTF_MIDDLEDOWN
    elif button == _SECONDARY or button == _RIGHT:
        ev = _MOUSEEVENTF_RIGHTDOWN

    if not ev:
        raise ValueError(
            f'button arg to _click() must be one of "left", "middle", or "right", not {button}'
        )

    extra = ctypes.c_ulong(0)
    ii_ = _INPUT_UNION()
    ii_.mi = _MOUSEINPUT(0, 0, 0, ev, 0, ctypes.pointer(extra))
    xi = _INPUT(_INPUT_MOUSE, ii_)
    send_input(xi)


# Ignored parameters: duration, tween, logScreenshot
@_genericPyDirectInputChecks
def mouseUp(
    x: int | None = None,
    y: int | None = None,
    button: str = _PRIMARY,
    duration: float | None = None,
    tween: None = None,
    logScreenshot: bool = False,
    _pause: bool = True,
) -> None:
    '''
    Lift up mouse button `button`.
    '''
    if x is not None or y is not None:
        moveTo(x, y)

    ev: int | None = None
    if button == _PRIMARY or button == _LEFT:
        ev = _MOUSEEVENTF_LEFTUP
    elif button == _MIDDLE:
        ev = _MOUSEEVENTF_MIDDLEUP
    elif button == _SECONDARY or button == _RIGHT:
        ev = _MOUSEEVENTF_RIGHTUP

    if not ev:
        raise ValueError(
            'button arg to _click() must be one of "left", "middle", or "right", not {button}'
        )

    extra = ctypes.c_ulong(0)
    ii_ = _INPUT_UNION()
    ii_.mi = _MOUSEINPUT(0, 0, 0, ev, 0, ctypes.pointer(extra))
    xi = _INPUT(_INPUT_MOUSE, ii_)
    send_input(xi)


# Ignored parameters: duration, tween, logScreenshot
@_genericPyDirectInputChecks
def click(
    x: int | None = None,
    y: int | None = None,
    clicks: int = 1,
    interval: float = 0.0,
    button: str = _PRIMARY,
    duration: float | None = None,
    tween: None = None,
    logScreenshot: bool = False,
    _pause: bool = True,
) -> None:
    '''
    Click mouse button `button` (String left|right|middle).
    '''
    if x is not None or y is not None:
        moveTo(x, y)

    ev: int | None = None
    if button == _PRIMARY or button == _LEFT:
        ev = _MOUSEEVENTF_LEFTCLICK
    elif button == _MIDDLE:
        ev = _MOUSEEVENTF_MIDDLECLICK
    elif button == _SECONDARY or button == _RIGHT:
        ev = _MOUSEEVENTF_RIGHTCLICK

    if not ev:
        raise ValueError(
            f'button arg to _click() must be one of "left", "middle", or "right", not {button}'
        )

    for _ in range(clicks):
        failSafeCheck()

        extra = ctypes.c_ulong(0)
        ii_ = _INPUT_UNION()
        ii_.mi = _MOUSEINPUT(0, 0, 0, ev, 0, ctypes.pointer(extra))
        xi: _INPUT = _INPUT(_INPUT_MOUSE, ii_)
        send_input(xi)
        time.sleep(interval)


def leftClick(
    x: int | None = None,
    y: int | None = None,
    interval: float = 0.0,
    duration: float = 0.0,
    tween: None = None,
    logScreenshot: bool = False,
    _pause: bool = True,
) -> None:
    '''
    Click Left Mouse button.
    '''
    click(x, y, 1, interval, _LEFT, duration, tween, logScreenshot, _pause)


def rightClick(
    x: int | None = None,
    y: int | None = None,
    interval: float = 0.0,
    duration: float = 0.0,
    tween: None = None,
    logScreenshot: bool = False,
    _pause: bool = True,
) -> None:
    '''
    Click Right Mouse button.
    '''
    click(x, y, 1, interval, _RIGHT, duration, tween, logScreenshot, _pause)


def middleClick(
    x: int | None = None,
    y: int | None = None,
    interval: float = 0.0,
    duration: float = 0.0,
    tween: None = None,
    logScreenshot: bool = False,
    _pause: bool = True,
) -> None:
    '''
    Click Middle Mouse button.
    '''
    click(x, y, 1, interval, _MIDDLE, duration, tween, logScreenshot, _pause)


def doubleClick(
    x: int | None = None,
    y: int | None = None,
    interval: float = 0.0,
    button: str = _LEFT,
    duration: float = 0.0,
    tween: None = None,
    logScreenshot: bool = False,
    _pause: bool = True,
) -> None:
    '''
    Double click `button`.
    '''
    click(x, y, 2, interval, button, duration, tween, logScreenshot, _pause)


def tripleClick(
    x: int | None = None,
    y: int | None = None,
    interval: float = 0.0,
    button: str = _LEFT,
    duration: float = 0.0,
    tween: None = None,
    logScreenshot: bool = False,
    _pause: bool = True,
) -> None:
    '''
    Triple click `button`.
    '''
    click(x, y, 3, interval, button, duration, tween, logScreenshot, _pause)


# Originally implemented by https://github.com/learncodebygaming/pydirectinput/pull/22
# A negative number of clicks will scroll down and a positive number will scroll up
@_genericPyDirectInputChecks
def scroll(clicks: int = 0, interval: float = 0) -> None:
    '''
    Mouse scroll `clicks` number of times, waiting `interval` seconds between
    every scroll.
    '''
    if clicks >= 0:
        direction = 1
    else:
        direction = -1
        clicks = abs(clicks)

    for _ in range(clicks):
        extra = ctypes.c_ulong(0)
        ii_ = _INPUT_UNION()
        ii_.mi = _MOUSEINPUT(
            0,
            0,
            ctypes.c_ulong(direction * 120),
            _MOUSEEVENTF_WHEEL,
            0,
            ctypes.pointer(extra)
        )
        x = _INPUT(ctypes.c_ulong(0), ii_)
        send_input(x)
        time.sleep(interval)


# Ignored parameters: duration, tween, logScreenshot
# PyAutoGUI uses ctypes.windll.user32.SetCursorPos(x, y) for this,
# which might still work fine in DirectInput environments.
# Use the relative flag to do a raw win32 api relative movement call
# (no MOUSEEVENTF_ABSOLUTE flag), which may be more appropriate for some
# applications. Note that this may produce inexact results depending on
# mouse movement speed.
@_genericPyDirectInputChecks
def moveTo(
    x: int | None = None,
    y: int | None = None,
    duration: None = None,
    tween: None = None,
    logScreenshot: bool = False,
    _pause: bool = True,
    relative: bool = False
) -> None:
    '''
    Move the mouse to an absolute(*) postion.

    (*) If `relative is True`: use `moveRel(..., relative=True) to move.`
    '''
    if not relative:
        # if only x or y is provided, will keep the current position for the other axis
        x, y = position(x, y)
        x, y = _to_windows_coordinates(x, y)
        extra = ctypes.c_ulong(0)
        ii_ = _INPUT_UNION()
        ii_.mi = _MOUSEINPUT(
            x,
            y,
            0,
            (_MOUSEEVENTF_MOVE | _MOUSEEVENTF_ABSOLUTE),
            0,
            ctypes.pointer(extra)
        )
        command = _INPUT(_INPUT_MOUSE, ii_)
        send_input(command)
    else:
        currentX, currentY = position()
        if x is None or y is None:
            raise ValueError("x and y have to be integers if relative is set!")
        moveRel(x - currentX, y - currentY, relative=True)


# Ignored parameters: duration, tween, logScreenshot
# move() and moveRel() are equivalent.
# Use the relative flag to do a raw win32 api relative movement call
# (no MOUSEEVENTF_ABSOLUTE flag), which may be more appropriate for some
# applications.
@_genericPyDirectInputChecks
def moveRel(
    xOffset: int | None = None,
    yOffset: int | None = None,
    duration: None = None,
    tween: None = None,
    logScreenshot: bool = False,
    _pause: bool = True,
    relative: bool = False
) -> None:
    '''
    Move the mouse a relative amount.

    `relative` parameter decides how the movement is executed.
    -> `False`: New postion is calculated and absolute movement is used.
    -> `True`: Uses API relative movement (can be inconsistent)
    '''
    if not relative:
        x, y = position()
        if xOffset is None:
            xOffset = 0
        if yOffset is None:
            yOffset = 0
        moveTo(x + xOffset, y + yOffset)
    else:
        # When using MOUSEEVENTF_MOVE for relative movement the results may be inconsistent.
        # "Relative mouse motion is subject to the effects of the mouse speed and the two-mouse
        # threshold values. A user sets these three values with the Pointer Speed slider of the
        # Control Panel's Mouse Properties sheet. You can obtain and set these values using the
        # SystemParametersInfo function."
        # https://docs.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-mouseinput
        # https://stackoverflow.com/questions/50601200/pyhon-directinput-mouse-relative-moving-act-not-as-expected
        extra = ctypes.c_ulong(0)
        ii_ = _INPUT_UNION()
        ii_.mi = _MOUSEINPUT(xOffset, yOffset, 0, _MOUSEEVENTF_MOVE, 0, ctypes.pointer(extra))
        command = _INPUT(_INPUT_MOUSE, ii_)
        send_input(command)


move = moveRel


# Missing feature: drag functions


# ==================================================================================================
# ===== Keyboard Functions =========================================================================
# ==================================================================================================

# Ignored parameters: logScreenshot
# Missing feature: auto shift for special characters (ie. '!', '@', '#'...)
@_genericPyDirectInputChecks
def keyDown(
    key: str,
    logScreenshot: None = None,
    _pause: bool = True
) -> bool:
    '''
    Press down `key`.
    '''
    if key not in KEYBOARD_MAPPING or KEYBOARD_MAPPING[key] is None:
        return False

    keybdFlags: int = _KEYEVENTF_SCANCODE
    hexKeyCode = KEYBOARD_MAPPING[key]

    if hexKeyCode >= 1024 or key in ['up', 'left', 'down', 'right']:
        keybdFlags |= _KEYEVENTF_EXTENDEDKEY

    # Init event tracking
    insertedEvents = 0
    expectedEvents = 1

    extra = ctypes.c_ulong(0)
    ii_ = _INPUT_UNION()
    ii_.ki = _KEYBDINPUT(0, hexKeyCode, keybdFlags, 0, ctypes.pointer(extra))
    x = _INPUT(_INPUT_KEYBOARD, ii_)
    insertedEvents += send_input(x)

    return insertedEvents == expectedEvents


# Ignored parameters: logScreenshot
# Missing feature: auto shift for special characters (ie. '!', '@', '#'...)
@_genericPyDirectInputChecks
def keyUp(
    key: str,
    logScreenshot: None = None,
    _pause: bool = True
) -> bool:
    '''
    Release key `key`.
    '''
    if key not in KEYBOARD_MAPPING or KEYBOARD_MAPPING[key] is None:
        return False

    keybdFlags: int = _KEYEVENTF_SCANCODE | _KEYEVENTF_KEYUP
    hexKeyCode = KEYBOARD_MAPPING[key]

    if hexKeyCode >= 1024 or key in ['up', 'left', 'down', 'right']:
        keybdFlags |= _KEYEVENTF_EXTENDEDKEY

    # Init event tracking
    insertedEvents = 0
    expectedEvents = 1

    extra = ctypes.c_ulong(0)
    ii_ = _INPUT_UNION()
    ii_.ki = _KEYBDINPUT(0, hexKeyCode, keybdFlags, 0, ctypes.pointer(extra))
    x = _INPUT(_INPUT_KEYBOARD, ii_)

    # SendInput returns the number of event successfully inserted into input stream
    # https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput#return-value
    insertedEvents += send_input(x)

    return insertedEvents == expectedEvents


# Ignored parameters: logScreenshot
# nearly identical to PyAutoGUI's implementation
@_genericPyDirectInputChecks
def press(
    keys: str | list[str],
    presses: int = 1,
    interval: float = 0.0,
    logScreenshot: None = None,
    _pause: bool = True
) -> bool:
    '''
    Press the collection of `keys` for `presses` amount of times.
    '''
    if isinstance(keys, str):
        if len(keys) > 1:
            keys = keys.lower()
        keys = [keys]  # If keys is 'enter', convert it to ['enter'].
    else:
        lowerKeys: list[str] = []
        for s in keys:
            if len(s) > 1:
                lowerKeys.append(s.lower())
            else:
                lowerKeys.append(s)
        keys = lowerKeys
    interval = float(interval)

    # We need to press x keys y times, which comes out to x*y presses in total
    expectedPresses = presses * len(keys)
    completedPresses = 0

    for _ in range(presses):
        for k in keys:
            failSafeCheck()
            downed = keyDown(k)
            upped = keyUp(k)
            # Count key press as complete if key was "downed" and "upped" successfully
            if downed and upped:
                completedPresses += 1

        time.sleep(interval)

    return completedPresses == expectedPresses


# Ignored parameters: logScreenshot
# nearly identical to PyAutoGUI's implementation
@_genericPyDirectInputChecks
def typewrite(
    message: str,
    interval: float = 0.0,
    logScreenshot: None = None,
    _pause: bool = True
) -> None:
    '''
    Break down `message` into characters and press them one by one.
    '''
    interval = float(interval)
    for c in message:
        if len(c) > 1:
            c = c.lower()
        press(c, _pause=False)
        time.sleep(interval)
        failSafeCheck()


write = typewrite


# Originally implemented by https://github.com/learncodebygaming/pydirectinput/pull/30
# nearly identical to PyAutoGUI's implementation
@_genericPyDirectInputChecks
def hotKey(*args: str, interval: float = 0.0, wait: float = 0.0) -> None:
    '''
    Press down buttons in order they are specified as arguments,
    releasing them in reverse order, e.g. 'ctrl', 'c' will first press
    Control, then C and release C before releasing Control.

    Use keyword-only argument `interval` to specify a delay between single
    keys when pressing and releasing and `wait` for delay between last press
    and first release.
    '''
    delay_key: bool = False
    for c in args:
        if delay_key:
            time.sleep(interval)
        delay_key = True
        if len(c) > 1:
            c = c.lower()
        keyDown(c)
    time.sleep(wait)
    delay_key = False
    for c in reversed(args):
        if delay_key:
            time.sleep(interval)
        delay_key = True
        if len(c) > 1:
            c = c.lower()
        keyUp(c)
