'''
Partial implementation of DirectInput function calls to simulate
mouse and keyboard inputs.
'''

from __future__ import annotations

# native imports
import functools
import inspect
import sys
import time
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from ctypes import (
    POINTER, Array, Structure, Union, WinDLL, c_bool, c_int, c_long,
    c_short, c_uint, c_ulong, c_ushort, c_void_p, pointer, sizeof, windll,
)
from math import ceil, floor, log10
from struct import unpack
from threading import Lock

# Windows-only
if sys.platform != 'win32':
    raise ImportError(
        "This module makes Windows API calls and is thereby only available "
        "on that plattform!"
    )

# Python 3.7 or higher
if sys.version_info >= (3, 7):
    from typing import Any, Callable, TypeVar, TYPE_CHECKING
    from typing import cast as hint_cast  # prevent confusion with ctypes.cast
else:
    raise ImportError(
        "This module is strictly typed and can't be used in Python <3.7!"
    )

# Python 3.8 or higher
if sys.version_info >= (3, 8):
    # native imports
    from typing import ClassVar, Final, Literal, Protocol
else:
    # pip imports
    from typing_extensions import ClassVar, Final, Literal, Protocol

# Python 3.9 or higher
if sys.version_info >= (3, 9):
    _list = list
else:
    from typing import List
    _list = List

# Python 3.10 or higher
if sys.version_info >= (3, 10):
    # native imports
    from typing import ParamSpec, TypeAlias
else:
    # pip imports
    from typing_extensions import ParamSpec, TypeAlias


# ------------------------------------------------------------------------------
if TYPE_CHECKING:
    # https://github.com/python/mypy/issues/7540#issuecomment-845741357
    _POINTER_TYPE = pointer
else:
    class __pointer:
        '''Monkeypatch typed pointer from typeshed into ctypes'''
        @classmethod
        def __class_getitem__(cls, item):
            return POINTER(item)
    _POINTER_TYPE = __pointer
# ------------------------------------------------------------------------------

# ==============================================================================
# ===== Internal time source ===================================================
# ==============================================================================
_time: Callable[[], float] = time.perf_counter
_time_ns: Callable[[], int] = time.perf_counter_ns
_sleep: Callable[[float], None] = time.sleep


# ==============================================================================
# ===== External "constants" ===================================================
# ==============================================================================

# ----- "Constants" for failsafe check and pause -------------------------------
# Intendend to be modified by callers
FAILSAFE: bool = True
'''
Stop execution if mouse is moved into one of `FAILSAFE_POINTS`.
Change to disable failsafe behaviour.
'''
FAILSAFE_POINTS: list[tuple[int, int]] = [(0, 0)]
'''
List of coordinates that trigger failafe exception. (default: top left corner)
'''
PAUSE: float = 0.01  # 1/100 second pause by default
'''
Default pause interval in seconds if _pause argument isn't set to False.
1/100 second pause by default.
'''
MINIMUM_SLEEP_IDEAL: float = 1e-6
'''
Extremely small timer interval greater than 0 that still generates
'''
MINIMUM_SLEEP_ACTUAL: float = 0.002
'''
Actual time spent on sleeping with MINIMUM_SLEEP_IDEAL, rounded up for safety.
'''
# ------------------------------------------------------------------------------


# ----- Constants for the mouse button names -----------------------------------
MOUSE_LEFT: str = "left"
'''Name of left mouse button'''
MOUSE_MIDDLE: str = "middle"
'''Name of middle mouse button'''
MOUSE_RIGHT: str = "right"
'''Name of right mouse button'''
MOUSE_PRIMARY: str = "primary"
'''Name of primary mouse button (left mouse button unless swapped)'''
MOUSE_SECONDARY: str = "secondary"
'''Name of secondary mouse button (right mouse button unless swapped)'''
MOUSE_BUTTON4: str = "mouse4"
'''Name of first additional mouse button (usually a side button)'''
MOUSE_X1: str = "x1"
'''Name of first additional mouse button (usually a side button)'''
MOUSE_BUTTON5: str = "mouse5"
'''Name of second additional mouse button (usually a side button)'''
MOUSE_X2: str = "x2"
'''Name of second additional mouse button (usually a side button)'''
# ------------------------------------------------------------------------------


# ==============================================================================
# ===== External setup functions ===============================================
# ==============================================================================

# ----- automatically measure minimum sleep time -------------------------------
def calibrate_real_sleep_minimum(
    runs: int = 10,
    *,
    verbose: bool = False
) -> None:
    '''
    Measure your system's minimum sleep duration and calibrate
    `MINIMUM_SLEEP_ACTUAL` accordingly.

    Will try to sleep for `MINIMUM_SLEEP_IDEAL` seconds and measure actual time
    difference. Repeat for `runs` amount of times, take the highest measurement
    and round it up to the next higher value in the same order of magnitude.

    Example: [0.001874, 0.001721, 0.001806] would round up to 0.002
    '''

    def round_up_same_magnitude(x: float) -> float:
        mag: float = 10**floor(log10(x))
        return ceil(x / mag) * mag

    def stopwatch(duration: float) -> float:
        t1: int = _time_ns()
        _sleep(duration)
        t2: int = _time_ns()
        return (t2 - t1) * 1e-9

    if verbose:
        print("Calibrating real sleep minimum...")

    measurements = [
        stopwatch(MINIMUM_SLEEP_IDEAL) for _ in range(runs)
    ]
    if verbose:
        print(f"Real measurements: {measurements}")

    new_sleep_minimum = round_up_same_magnitude(max(measurements))
    if verbose:
        print(
            "Rounding max measurement to next higher value in same order of "
            f"magnitude: {new_sleep_minimum}"
        )

    global MINIMUM_SLEEP_ACTUAL
    if verbose:
        print(
            f"Changing MINIMUM_SLEEP_ACTUAL from {MINIMUM_SLEEP_ACTUAL} to "
            f"{new_sleep_minimum}"
        )
    MINIMUM_SLEEP_ACTUAL = (  # pyright: ignore[reportConstantRedefinition]
        new_sleep_minimum
    )
# ------------------------------------------------------------------------------


# ==============================================================================
# ===== Internal constants =====================================================
# ==============================================================================


# ----- INPUT.type constants ---------------------------------------------------
_INPUT_MOUSE: Final = 0x0000  # c_ulong(0x0000)
'''The event is a mouse event. Use the mi structure of the union.'''
_INPUT_KEYBOARD: Final = 0x0001  # c_ulong(0x0001)
'''The event is a keyboard event. Use the ki structure of the union.'''
_INPUT_HARDWARE: Final = 0x0002  # c_ulong(0x0002)
'''The event is a hardware event. Use the hi structure of the union.'''
# ------------------------------------------------------------------------------


# ----- MOUSEINPUT.mouseData constants -----------------------------------------
_XBUTTON1: Final = 0x0001  # c_ulong(0x0001)
'''Set if the first X button is pressed or released.'''
_XBUTTON2: Final = 0x0002  # c_ulong(0x0002)
'''Set if the second X button is pressed or released.'''
# ------------------------------------------------------------------------------


# ----- MOUSEINPUT.dwFlags constants -------------------------------------------
_MOUSEEVENTF_MOVE: Final = 0x0001  # c_ulong(0x0001)
'''Movement occurred.'''

_MOUSEEVENTF_LEFTDOWN: Final = 0x0002  # c_ulong(0x0002)
'''The left button was pressed.'''
_MOUSEEVENTF_LEFTUP: Final = 0x0004  # c_ulong(0x0004)
'''The left button was released.'''
_MOUSEEVENTF_LEFTCLICK: Final = (
    _MOUSEEVENTF_LEFTDOWN + _MOUSEEVENTF_LEFTUP  # c_ulong(0x0006)
)
'''Combined event: Left button was clicked.'''

_MOUSEEVENTF_RIGHTDOWN: Final = 0x0008  # c_ulong(0x0008)
'''The right button was pressed.'''
_MOUSEEVENTF_RIGHTUP: Final = 0x0010  # c_ulong(0x0010)
'''The right button was released.'''
_MOUSEEVENTF_RIGHTCLICK: Final = (
    _MOUSEEVENTF_RIGHTDOWN + _MOUSEEVENTF_RIGHTUP  # c_ulong(0x0018)
)
'''Combined event: Right button was clicked.'''

_MOUSEEVENTF_MIDDLEDOWN: Final = 0x0020  # c_ulong(0x0020)
'''The middle button was pressed.'''
_MOUSEEVENTF_MIDDLEUP: Final = 0x0040  # c_ulong(0x0040)
'''The middle button was released.'''
_MOUSEEVENTF_MIDDLECLICK: Final = (
    _MOUSEEVENTF_MIDDLEDOWN + _MOUSEEVENTF_MIDDLEUP  # c_ulong(0x0060)
)
'''Combined event: Middle button was clicked.'''

_MOUSEEVENTF_XDOWN: Final = 0x0080  # c_ulong(0x0080)
'''An X button was pressed.'''
_MOUSEEVENTF_XUP: Final = 0x0100  # c_ulong(0x0100)
'''An X button was released.'''
_MOUSEEVENTF_XCLICK: Final = (
    _MOUSEEVENTF_XDOWN + _MOUSEEVENTF_XUP  # c_ulong(0x0180)
)
'''Combined event: Side button was clicked.'''

_MOUSEEVENTF_WHEEL: Final = 0x0800  # c_ulong(0x0800)
'''
The wheel was moved, if the mouse has a wheel.
The amount of movement is specified in mouseData.
'''
_MOUSEEVENTF_HWHEEL: Final = 0x1000  # c_ulong(0x1000)
'''
The wheel was moved horizontally, if the mouse has a wheel. The amount of
movement is specified in mouseData.
Windows XP/2000: This value is not supported.
'''

_MOUSEEVENTF_MOVE_NOCOALESCE: Final = 0x2000  # c_ulong(0x2000)
'''
The WM_MOUSEMOVE messages will not be coalesced. The default behavior is to
coalesce WM_MOUSEMOVE messages.
Windows XP/2000: This value is not supported.
'''
_MOUSEEVENTF_VIRTUALDESK: Final = 0x4000  # c_ulong(0x4000)
'''
Maps coordinates to the entire desktop. Must be used with MOUSEEVENTF_ABSOLUTE.
'''
_MOUSEEVENTF_ABSOLUTE: Final = 0x8000  # c_ulong(0x8000)
'''
The dx and dy members contain normalized absolute coordinates. If the flag is
not set, dxand dy contain relative data (the change in position since the last
reported position). This flag can be set, or not set, regardless of what kind of
mouse or other pointing device, if any, is connected to the system. For further
information about relative mouse motion, see the following Remarks section.
'''
# ------------------------------------------------------------------------------


# ----- Scrolling distance -----------------------------------------------------
_WHEEL_DELTA: Final = 120
'''
The delta was set to 120 to allow Microsoft or other vendors to build
finer-resolution wheels (a freely-rotating wheel with no notches) to send more
messages per rotation, but with a smaller value in each message.

https://docs.microsoft.com/en-us/windows/win32/inputdev/wm-mousewheel
'''
# ------------------------------------------------------------------------------


# ----- KEYBDINPUT.dwFlags Flags ------------------------------------------------
_KEYEVENTF_EXTENDEDKEY: Final = 0x0001  # c_ulong(0x0001)
'''
If specified, the scan code was preceded by a prefix byte that has the value
0xE0 (224).
'''
_KEYEVENTF_KEYUP: Final = 0x0002  # c_ulong(0x0002)
'''
If specified, the key is being released. If not specified, the key is being
pressed.
'''
_KEYEVENTF_UNICODE: Final = 0x0004  # c_ulong(0x0004)
'''
If specified, the system synthesizes a VK_PACKET keystroke. The wVk parameter
must be zero. This flag can only be combined with the KEYEVENTF_KEYUP flag.
For more information, see the Remarks section.
'''
_KEYEVENTF_SCANCODE: Final = 0x0008  # c_ulong(0x0008)
'''If specified, wScan identifies the key and wVk is ignored.'''
# ------------------------------------------------------------------------------


# ----- MOUSEINPUT Remarks -----------------------------------------------------
'''
https://docs.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-mouseinput#remarks

----- Remarks -----

If the mouse has moved, indicated by MOUSEEVENTF_MOVE, dx and dy specify
information about that movement. The information is specified as absolute or
relative integer values.

If MOUSEEVENTF_ABSOLUTE value is specified, dx and dy contain normalized
absolute coordinates between 0 and 65,535. The event procedure maps these
coordinates onto the display surface. Coordinate (0,0) maps onto the upper-left
corner of the display surface; coordinate (65535,65535) maps onto the
lower-right corner. In a multimonitor system, the coordinates map to the
primary monitor.

If MOUSEEVENTF_VIRTUALDESK is specified, the coordinates map to the entire
virtual desktop.

If the MOUSEEVENTF_ABSOLUTE value is not specified, dx and dy specify movement
relative to the previous mouse event (the last reported position). Positive
values mean the mouse moved right (or down); negative values mean the mouse
moved left (or up).

Relative mouse motion is subject to the effects of the mouse speed and the
two-mouse threshold values. A user sets these three values with the
Pointer Speed slider of the Control Panel's Mouse Properties sheet. You can
obtain and set these values using the SystemParametersInfo[1] function.

The system applies two tests to the specified relative mouse movement. If the
specified distance along either the x or y axis is greater than the first mouse
threshold value, and the mouse speed is not zero, the system doubles the
distance. If the specified distance along either the x or y axis is greater than
the second mouse threshold value, and the mouse speed is equal to two, the
system doubles the distance that resulted from applying the first threshold
test. It is thus possible for the system to multiply specified relative mouse
movement along the x or y axis by up to four times.

[1] https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-systemparametersinfoa
'''
# ------------------------------------------------------------------------------


# ----- MapVirtualKey Map Types ------------------------------------------------
_MAPVK_VK_TO_VSC: Final = 0  # c_unit(0)
'''
The uCode parameter is a virtual-key code and is translated into a scan code.
If it is a virtual-key code that does not distinguish between left- and
right-hand keys, the left-hand scan code is returned.
If there is no translation, the function returns 0.
'''
_MAPVK_VSC_TO_VK: Final = 1  # c_unit(1)
'''
The uCode parameter is a scan code and is translated into a virtual-key code
that does not distinguish between left- and right-hand keys.
If there is no translation, the function returns 0.
'''
_MAPVK_VK_TO_CHAR: Final = 2  # c_unit(2)
'''
The uCode parameter is a virtual-key code and is translated into an unshifted
character value in the low order word of the return value. Dead keys
(diacritics) are indicated by setting the top bit of the return value.
If there is no translation, the function returns 0.
'''
_MAPVK_VSC_TO_VK_EX: Final = 3  # c_unit(3)
'''
The uCode parameter is a scan code and is translated into a virtual-key code
that distinguishes between left- and right-hand keys.
If there is no translation, the function returns 0.
'''
_MAPVK_VK_TO_VSC_EX: Final = 4  # c_unit(4)
'''
Windows Vista and later: The uCode parameter is a virtual-key code and is
translated into a scan code. If it is a virtual-key code that does not
distinguish between left- and right-hand keys, the left-hand scan code is
returned. If the scan code is an extended scan code, the high byte of the uCode
value can contain either 0xe0 or 0xe1 to specify the extended scan code.
If there is no translation, the function returns 0.
'''
# ------------------------------------------------------------------------------


# ----- GetSystemMetrics nIndex arguments --------------------------------------
_SM_CXSCREEN: Final = 0
'''
The width of the screen of the primary display monitor, in pixels. This is the
same value obtained by calling GetDeviceCaps[1] as follows:
`GetDeviceCaps(hdcPrimaryMonitor, HORZRES)`.

[1] https://docs.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-getdevicecaps
'''
_SM_CYSCREEN: Final = 1
'''
The height of the screen of the primary display monitor, in pixels. This is the
same value obtained by calling GetDeviceCaps[1] as follows:
`GetDeviceCaps(hdcPrimaryMonitor, VERTRES)`.

[1] https://docs.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-getdevicecaps
'''
_SM_SWAPBUTTON: Final = 23
'''
Nonzero if the meanings of the left and right mouse buttons are swapped;
otherwise, 0.
'''
_SM_XVIRTUALSCREEN: Final = 76
'''
The coordinates for the left side of the virtual screen. The virtual screen is
the bounding rectangle of all display monitors. The SM_CXVIRTUALSCREEN metric
is the width of the virtual screen.
'''
_SM_YVIRTUALSCREEN: Final = 77
'''
The coordinates for the top of the virtual screen. The virtual screen is the
bounding rectangle of all display monitors. The SM_CYVIRTUALSCREEN metric is
the height of the virtual screen.
'''
_SM_CXVIRTUALSCREEN: Final = 78
'''
The width of the virtual screen, in pixels. The virtual screen is the bounding
rectangle of all display monitors. The SM_XVIRTUALSCREEN metric is the
coordinates for the left side of the virtual screen.
'''
_SM_CYVIRTUALSCREEN: Final = 79
'''
The height of the virtual screen, in pixels. The virtual screen is the bounding
rectangle of all display monitors. The SM_YVIRTUALSCREEN metric is the
coordinates for the top of the virtual screen.
'''
# ------------------------------------------------------------------------------


# ----- SystemParametersInfoW uiAction arguments -------------------------------
_SPI_GETMOUSE: Final = 0x0003  # c_uint
'''
Retrieves the two mouse threshold values and the mouse acceleration. The
pvParam parameter must point to an array of three integers that receives these
values. See mouse_event[1] for further information.

https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-mouse_event
'''
_SPI_SETMOUSE: Final = 0x0004  # c_uint
'''
Sets the two mouse threshold values and the mouse acceleration. The pvParam
parameter must point to an array of three integers that specifies these values.
See mouse_event[1] for further information.

https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-mouse_event
'''
_SPI_GETMOUSESPEED: Final = 0x0070  # c_uint
'''
Retrieves the current mouse speed. The mouse speed determines how far the
pointer will move based on the distance the mouse moves. The pvParam parameter
must point to an integer that receives a value which ranges between 1 (slowest)
and 20 (fastest). A value of 10 is the default. The value can be set by an
end-user using the mouse control panel application or by an application using
SPI_SETMOUSESPEED.
'''
_SPI_SETMOUSESPEED: Final = 0x0071  # c_uint
'''
Sets the current mouse speed. The pvParam parameter is an integer between
1 (slowest) and 20 (fastest). A value of 10 is the default. This value is
typically set using the mouse control panel application.
'''
# ------------------------------------------------------------------------------


# ----- MOUSEEVENTF Index constants --------------------------------------------
_MOUSE_PRESS: Final = 0
_MOUSE_RELEASE: Final = 1
_MOUSE_CLICK: Final = 2
# ------------------------------------------------------------------------------


# ----- MOUSEEVENTF Lookup dicts -----------------------------------------------
_MOUSEEVENTF_LEFT: tuple[int, int, int] = (
    _MOUSEEVENTF_LEFTDOWN,
    _MOUSEEVENTF_LEFTUP,
    _MOUSEEVENTF_LEFTCLICK
)
_MOUSEEVENTF_MIDDLE: tuple[int, int, int] = (
    _MOUSEEVENTF_MIDDLEDOWN,
    _MOUSEEVENTF_MIDDLEUP,
    _MOUSEEVENTF_MIDDLECLICK
)
_MOUSEEVENTF_RIGHT: tuple[int, int, int] = (
    _MOUSEEVENTF_RIGHTDOWN,
    _MOUSEEVENTF_RIGHTUP,
    _MOUSEEVENTF_RIGHTCLICK
)
_MOUSEEVENTF_X: tuple[int, int, int] = (
    _MOUSEEVENTF_XDOWN,
    _MOUSEEVENTF_XUP,
    _MOUSEEVENTF_XCLICK
)
_MOUSE_MAPPING_EVENTF: dict[str, tuple[int, int, int]] = {}
_MOUSE_MAPPING_DATA: dict[str, int] = {}


def update_MOUSEEVENT_mappings() -> None:
    '''
    Update the MOUSEEVENT mappings if you change the name of the button name
    constants.

    This function MUST be called every time one of the `MOUSE_*` constants
    is been changed!
    '''
    _MOUSE_MAPPING_EVENTF.update({
        MOUSE_LEFT: _MOUSEEVENTF_LEFT,
        MOUSE_MIDDLE: _MOUSEEVENTF_MIDDLE,
        MOUSE_RIGHT: _MOUSEEVENTF_RIGHT,
        MOUSE_BUTTON4: _MOUSEEVENTF_X,
        MOUSE_X1: _MOUSEEVENTF_X,
        MOUSE_BUTTON5: _MOUSEEVENTF_X,
        MOUSE_X2: _MOUSEEVENTF_X,
    })
    _MOUSE_MAPPING_DATA.update({
        MOUSE_LEFT: 0,
        MOUSE_MIDDLE: 0,
        MOUSE_RIGHT: 0,
        MOUSE_BUTTON4: _XBUTTON1,
        MOUSE_X1: _XBUTTON1,
        MOUSE_BUTTON5: _XBUTTON2,
        MOUSE_X2: _XBUTTON2,
    })


update_MOUSEEVENT_mappings()  # call the function on import to set mappings.
# ------------------------------------------------------------------------------


# ==============================================================================
# ===== C struct redefinitions =================================================
# ==============================================================================

# ----- Pointer type to unsigned long ------------------------------------------
_PUL_PyType: TypeAlias = "type[_POINTER_TYPE[c_ulong]]"
_PUL: _PUL_PyType = POINTER(c_ulong)
# ------------------------------------------------------------------------------


# ----- MOUSEINPUT -------------------------------------------------------------
class _MOUSEINPUT(Structure):
    '''
    MOUSEINPUT structure (winuser.h)

    Contains information about a simulated mouse event.

    https://docs.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-mouseinput
    '''
    # Python side type hinting
    dx: int  # c_long
    '''
    The absolute position of the mouse, or the amount of motion since the last
    mouse event was generated, depending on the value of the dwFlags member.
    Absolute data is specified as the x coordinate of the mouse; relative data
    is specified as the number of pixels moved.
    '''
    dy: int  # c_long
    '''
    The absolute position of the mouse, or the amount of motion since the last
    mouse event was generated, depending on the value of the dwFlags member.
    Absolute data is specified as the y coordinate of the mouse; relative data
    is specified as the number of pixels moved.
    '''
    mouseData: int  # c_ulong
    '''
    If dwFlags contains MOUSEEVENTF_WHEEL, then mouseData specifies the amount
    of wheel movement. A positive value indicates that the wheel was rotated
    forward, away from the user; a negative value indicates that the wheel was
    rotated backward, toward the user. One wheel click is defined as
    WHEEL_DELTA, which is 120.

    Windows Vista: If dwFlags contains MOUSEEVENTF_HWHEEL, then dwData specifies
    the amount of wheel movement. A positive value indicates that the wheel was
    rotated to the right; a negative value indicates that the wheel was rotated
    to the left. One wheel click is defined as WHEEL_DELTA, which is 120.

    If dwFlags does not contain MOUSEEVENTF_WHEEL, MOUSEEVENTF_XDOWN, or
    MOUSEEVENTF_XUP, then mouseData should be zero.

    If dwFlags contains MOUSEEVENTF_XDOWN or MOUSEEVENTF_XUP, then mouseData
    specifies which X buttons were pressed or released. This value may be any
    combination of the following flags. (See _XBUTTON* constants)
    '''
    dwFlags: int  # c_ulong
    '''
    A set of bit flags that specify various aspects of mouse motion and button
    clicks. The bits in this member can be any reasonable combination of the
    following values.

    The bit flags that specify mouse button status are set to indicate changes
    in status, not ongoing conditions. For example, if the left mouse button is
    pressed and held down, MOUSEEVENTF_LEFTDOWN is set when the left button is
    first pressed, but not for subsequent motions. Similarly MOUSEEVENTF_LEFTUP
    is set only when the button is first released.

    You cannot specify both the MOUSEEVENTF_WHEEL flag and either
    MOUSEEVENTF_XDOWN or MOUSEEVENTF_XUP flags simultaneously in the dwFlags
    parameter, because they both require use of the mouseData field.
    (See _MOUSEEVENTF_* constants)
    '''
    time: int  # c_ulong
    '''
    The time stamp for the event, in milliseconds. If this parameter is 0, the
    system will provide its own time stamp.
    '''
    dwExtraInfo: _PUL_PyType
    '''
    An additional value associated with the keystroke. Use the
    GetMessageExtraInfo[1] function to obtain this information.

    [1] https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getmessageextrainfo
    '''
    # ctypes side struct definition
    _fields_ = [
        ("dx", c_long),
        ("dy", c_long),
        ("mouseData", c_ulong),
        ("dwFlags", c_ulong),
        ("time", c_ulong),
        ("dwExtraInfo", _PUL)
    ]
# ------------------------------------------------------------------------------


# ----- KEYBDINPUT -------------------------------------------------------------
class _KEYBDINPUT(Structure):
    '''
    KEYBDINPUT structure (winuser.h)

    Contains information about a simulated keyboard event.

    https://docs.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-keybdinput
    '''
    # Python side type hinting
    wVk: int  # c_ushort
    '''
    A virtual-key code. The code must be a value in the range 1 to 254. If the
    dwFlags member specifies KEYEVENTF_UNICODE, wVk must be 0.
    '''
    wScan: int  # c_ushort
    '''
    A hardware scan code for the key. If dwFlags specifies KEYEVENTF_UNICODE,
    wScan specifies a Unicode character which is to be sent to the foreground
    application.
    '''
    dwFlags: int  # c_ulong
    '''
    Specifies various aspects of a keystroke. This member can be certain
    combinations of the following values. (See _KEYEVENTF_* constants)
    '''
    time: int  # c_ulong
    '''
    The time stamp for the event, in milliseconds. If this parameter is zero,
    the system will provide its own time stamp.
    '''
    dwExtraInfo: _PUL_PyType
    '''
    An additional value associated with the keystroke. Use the
    GetMessageExtraInfo[1] function to obtain this information.

    [1] https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getmessageextrainfo
    '''
    # ctypes side struct definition
    _fields_ = [
        ("wVk", c_ushort),
        ("wScan", c_ushort),
        ("dwFlags", c_ulong),
        ("time", c_ulong),
        ("dwExtraInfo", _PUL)
    ]
# ------------------------------------------------------------------------------


# ----- HARDWAREINPUT ----------------------------------------------------------
class _HARDWAREINPUT(Structure):
    '''
    HARDWAREINPUT structure (winuser.h)

    Contains information about a simulated message generated by an input device
    other than a keyboard or mouse.

    https://docs.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-hardwareinput
    '''
    # Python side type hinting
    uMsg: int  # c_ulong
    '''The message generated by the input hardware.'''
    wParamL: int  # c_short
    '''The low-order word of the lParam parameter for uMsg.'''
    wParamH: int  # c_ushort
    '''The high-order word of the lParam parameter for uMsg.'''
    # ctypes side struct definition
    _fields_ = [
        ("uMsg", c_ulong),
        ("wParamL", c_short),
        ("wParamH", c_ushort)
    ]
# ------------------------------------------------------------------------------


# ----- POINT ------------------------------------------------------------------
class _POINT(Structure):
    '''
    POINT structure

    The POINT structure defines the x- and y- coordinates of a point.

    https://docs.microsoft.com/en-us/previous-versions/dd162805(v=vs.85)
    '''
    # Python side type hinting
    x: int  # c_long
    '''The x-coordinate of the point.'''
    y: int  # c_long
    '''The y-coordinate of the point.'''
    # ctypes side struct definition
    _fields_ = [
        ("x", c_long),
        ("y", c_long)
    ]
# ------------------------------------------------------------------------------


# ----- INPUT ------------------------------------------------------------------
class _INPUT_UNION(Union):
    '''
    https://docs.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-input
    '''
    # Python side type hinting
    mi: _MOUSEINPUT
    ki: _KEYBDINPUT
    hi: _HARDWAREINPUT
    # ctypes side struct definition
    _fields_ = [
        ("mi", _MOUSEINPUT),
        ("ki", _KEYBDINPUT),
        ("hi", _HARDWAREINPUT)
    ]


class _INPUT(Structure):
    '''
    INPUT structure (winuser.h)

    Used by SendInput to store information for synthesizing input events such
    as keystrokes, mouse movement, and mouse clicks.

    https://docs.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-input
    '''
    # Python side type hinting
    type: Literal[0, 1, 2]  # c_ulong
    '''
    The type of the input event. This member can be one of the following values.
    (See _INPUT_* constants)
    '''
    ii: _INPUT_UNION
    mi: _MOUSEINPUT  # part of _INPUT_UNION ii
    '''The information about a simulated mouse event.'''
    ki: _KEYBDINPUT  # part of _INPUT_UNION ii
    '''The information about a simulated keyboard event.'''
    hi: _HARDWAREINPUT  # part of _INPUT_UNION ii
    '''The information about a simulated hardware event.'''
    # ctypes side struct definition
    _anonymous_ = ('ii', )
    _fields_ = [("type", c_ulong),
                ("ii", _INPUT_UNION)]
# ------------------------------------------------------------------------------


# ==============================================================================
# ===== C struct factory functions =============================================
# ==============================================================================

# ----- _create_mouse_input ----------------------------------------------------
def _create_mouse_input(
    dx: int = 0,         # c_long
    dy: int = 0,         # c_long
    mouseData: int = 0,  # c_ulong
    dwFlags: int = 0,    # c_ulong
    time: int = 0,       # c_ulong
) -> _INPUT:
    '''Create INPUT structure for mouse input'''
    dwExtraInfo: c_ulong = c_ulong(0)
    input_struct: _INPUT = _INPUT(_INPUT_MOUSE)
    input_struct.mi = _MOUSEINPUT(
        dx,
        dy,
        mouseData,
        dwFlags,
        time,
        pointer(dwExtraInfo)
    )
    return input_struct
# ------------------------------------------------------------------------------


# ----- _create_keyboard_input -------------------------------------------------
def _create_keyboard_input(
    wVk: int = 0,      # c_ushort
    wScan: int = 0,    # c_ushort
    dwFlags: int = 0,  # c_ulong
    time: int = 0      # c_ulong
) -> _INPUT:
    '''Create INPUT structure for keyboard input'''
    dwExtraInfo: c_ulong = c_ulong(0)
    input_struct: _INPUT = _INPUT(_INPUT_KEYBOARD)
    input_struct.ki = _KEYBDINPUT(
        wVk,
        wScan,
        dwFlags,
        time,
        pointer(dwExtraInfo)
    )
    return input_struct
# ------------------------------------------------------------------------------


# ----- _create_hardware_input -------------------------------------------------
def _create_hardware_input(  # pyright: ignore[reportUnusedFunction]
    uMsg: int = 0,     # c_ulong
    wParamL: int = 0,  # c_short
    wParamH: int = 0   # c_ushort
) -> _INPUT:
    '''Create INPUT structure for hardware input'''
    input_struct: _INPUT = _INPUT(_INPUT_HARDWARE)
    input_struct.hi = _HARDWAREINPUT(
        uMsg,
        wParamL,
        wParamH
    )
    return input_struct
# ------------------------------------------------------------------------------


# ==============================================================================
# ==== User32 functions ========================================================
# ==============================================================================

# ----- user32.dll -------------------------------------------------------------
_user32: WinDLL = windll.user32
# ------------------------------------------------------------------------------


# ----- SendInput Declaration --------------------------------------------------
class _SendInputType(Protocol):
    argtypes: tuple[type[c_uint], type[_POINTER_TYPE[_INPUT]], type[c_int]]
    restype: type[c_uint]

    def __call__(
        self,
        cInputs: c_uint | int,
        pInputs: _POINTER_TYPE[_INPUT] | _INPUT | Array[_INPUT],
        cbSize: c_int | int
    ) -> int:  # c_uint
        ...


_SendInput: _SendInputType = hint_cast(_SendInputType, _user32.SendInput)
'''
----- SendInput function (winuser.h) -----

Synthesizes keystrokes, mouse motions, and button clicks.

https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput

----- Parameters -----

[in] cInputs

Type: UINT

The number of structures in the pInputs array.

[in] pInputs

Type: LPINPUT

An array of INPUT structures. Each structure represents an event to be inserted
into the keyboard or mouse input stream.

[in] cbSize

Type: int

The size, in bytes, of an INPUT structure. If cbSize is not the size of an INPUT
structure, the function fails.

----- Return value -----

Type: UINT

The function returns the number of events that it successfully inserted into the
keyboard or mouse input stream. If the function returns zero, the input was
already blocked by another thread. To get extended error information, call
GetLastError.

This function fails when it is blocked by UIPI. Note that neither GetLastError
nor the return value will indicate the failure was caused by UIPI blocking.

----- Remarks -----

This function is subject to UIPI. Applications are permitted to inject input
only into applications that are at an equal or lesser integrity level.

The SendInput function inserts the events in the INPUT structures serially into
the keyboard or mouse input stream. These events are not interspersed with other
keyboard or mouse input events inserted either by the user (with the keyboard or
mouse) or by calls to keybd_event, mouse_event, or other calls to SendInput.

This function does not reset the keyboard's current state. Any keys that are
already pressed when the function is called might interfere with the events that
this function generates. To avoid this problem, check the keyboard's state with
the GetAsyncKeyState function and correct as necessary.

Because the touch keyboard uses the surrogate macros defined in winnls.h to send
input to the system, a listener on the keyboard event hook must decode input
originating from the touch keyboard. For more information, see Surrogates and
Supplementary Characters.

An accessibility application can use SendInput to inject keystrokes
corresponding to application launch shortcut keys that are handled by the shell.
This functionality is not guaranteed to work for other types of applications.
'''
_SendInput.argtypes = c_uint, POINTER(_INPUT), c_int
_SendInput.restype = c_uint


def _send_input(
    inputs: _INPUT | Sequence[_INPUT],
) -> int:
    '''
    Abstraction layer over SendInput (winuser.h)

    See https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput
    '''
    # prepare arguments
    cInputs: c_uint
    inputs_array: Array[_INPUT]
    if isinstance(inputs, _INPUT):
        # -> single element array
        cInputs = c_uint(1)
        inputs_array = (_INPUT * 1)(inputs)
    else:
        cInputs = c_uint(len(inputs))
        inputs_array = (_INPUT * len(inputs))(*inputs)
    cbSize: c_int = c_int(sizeof(_INPUT))
    # execute function
    # inputs_array will be automatically be referenced by pointer
    return _SendInput(cInputs, inputs_array, cbSize)
# ------------------------------------------------------------------------------


# ----- MapVirtualKeyW Declaration ---------------------------------------------
class _MapVirtualKeyWType(Protocol):
    argtypes: tuple[type[c_uint], type[c_uint]]
    restype: type[c_uint]

    def __call__(
        self,
        uCode: c_uint | int,
        uMapType: c_uint | int
    ) -> int:  # c_uint
        ...


_MapVirtualKeyW = hint_cast(_MapVirtualKeyWType, _user32.MapVirtualKeyW)
'''
----- MapVirtualKeyW function (winuser.h) -----

Translates (maps) a virtual-key code into a scan code or character value, or
translates a scan code into a virtual-key code.

To specify a handle to the keyboard layout to use for translating the specified
code, use the MapVirtualKeyEx function.

https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-mapvirtualkeyw

----- Parameters -----

[in] uCode

Type: UINT

The virtual key code[1] or scan code for a key. How this value is interpreted
depends on the value of the uMapType parameter.

Starting with Windows Vista, the high byte of the uCode value can contain
either 0xe0 or 0xe1 to specify the extended scan code.

[in] uMapType

Type: UINT

The translation to be performed. The value of this parameter depends on the
value of the uCode parameter. (See _MAPVK_VK_TO_* constants)

----- Return value -----

Type: UINT

The return value is either a scan code, a virtual-key code, or a character
value, depending on the value of uCode and uMapType. If there is no translation,
the return value is zero.

----- Remarks -----

An application can use MapVirtualKey to translate scan codes to the virtual-key
code constants VK_SHIFT, VK_CONTROL, and VK_MENU, and vice versa. These
translations do not distinguish between the left and right instances of the
SHIFT, CTRL, or ALT keys.

An application can get the scan code corresponding to the left or right instance
of one of these keys by calling MapVirtualKey with uCode set to one of the
following virtual-key code constants:

    VK_LSHIFT
    VK_RSHIFT
    VK_LCONTROL
    VK_RCONTROL
    VK_LMENU
    VK_RMENU

These left- and right-distinguishing constants are available to an application
only through the GetKeyboardState[2], SetKeyboardState[3], GetAsyncKeyState[4],
GetKeyState, MapVirtualKey, and MapVirtualKeyEx functions. For list complete
table of virtual key codes, see Virtual Key Codes[1].

[1] https://docs.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes

[2] https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getkeyboardstate

[3] https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setkeyboardstate

[4] https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getasynckeystate

[5] https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getkeystate
'''
_MapVirtualKeyW.argtypes = c_uint, c_uint
_MapVirtualKeyW.restype = c_uint


def _map_virtual_key(
    uCode: int,
    uMapType: Literal[0, 1, 2, 3, 4]  # See _MAPVK_* constants
) -> int:
    '''
    Abstraction layer over MapVirtualKeyW (winuser.h)

    Accepted values for uMapType are:
    - _MAPVK_VK_TO_VSC = 0
    - _MAPVK_VSC_TO_VK = 1
    - _MAPVK_VK_TO_CHAR = 2
    - _MAPVK_VSC_TO_VK_EX = 3
    - _MAPVK_VK_TO_VSC_EX = 4

    See https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-mapvirtualkeyw
    '''
    return _MapVirtualKeyW(c_uint(uCode), c_uint(uMapType))
# ------------------------------------------------------------------------------


# ----- GetSystemMetrics Declaration -------------------------------------------
class _GetSystemMetricsType(Protocol):
    argtypes: tuple[type[c_int]]
    restype: type[c_int]

    def __call__(
        self,
        nIndex: c_int | int,
    ) -> int:  # c_int
        ...


_GetSystemMetrics = hint_cast(_GetSystemMetricsType, _user32.GetSystemMetrics)
'''
----- GetSystemMetrics function (winuser.h) -----

Retrieves the specified system metric or system configuration setting.

Note that all dimensions retrieved by GetSystemMetrics are in pixels.

https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getsystemmetrics

----- Parameters -----

[in] nIndex

Type: int

The system metric or configuration setting to be retrieved. This parameter can
be one of the following values. Note that all SM_CX* values are widths and all
SM_CY* values are heights. Also note that all settings designed to return
Boolean data represent TRUE as any nonzero value, and FALSE as a zero value.
(See _SM_* constants)

----- Return value -----

Type: int

If the function succeeds, the return value is the requested system metric or
configuration setting.

If the function fails, the return value is 0. GetLastError does not provide
extended error information.

----- Remarks -----

System metrics can vary from display to display.

GetSystemMetrics(SM_CMONITORS) counts only visible display monitors. This is
different from EnumDisplayMonitors[1], which enumerates both visible display
monitors and invisible pseudo-monitors that are associated with mirroring
drivers. An invisible pseudo-monitor is associated with a pseudo-device used to
mirror application drawing for remoting or other purposes.

This API is not DPI aware, and should not be used if the calling thread is
per-monitor DPI aware. For the DPI-aware version of this API, see
GetSystemMetricsForDPI[2]. For more information on DPI awareness, see the
Windows High DPI documentation[3].

[1] https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-enumdisplaymonitors

[2] https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getsystemmetricsfordpi

[3] https://docs.microsoft.com/en-us/windows/win32/hidpi/high-dpi-desktop-application-development-on-windows
'''  # noqa (URL too long)
_GetSystemMetrics.argtypes = c_int,
_GetSystemMetrics.restype = c_int


def _get_system_metrics(nIndex: int) -> int:
    '''
    Abstraction layer over GetSystemMetrics (winuser.h)

    See the _SM_* constants for accepted values for the nIndex argument.

    See https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getsystemmetrics
    '''
    return _GetSystemMetrics(nIndex)
# ------------------------------------------------------------------------------


# ----- GetCursorPos Declaration -----------------------------------------------
class _GetCursorPosType(Protocol):
    argtypes: tuple[type[_POINTER_TYPE[_POINT]]]
    restype: type[c_bool]

    def __call__(
        self,
        lpPoint: _POINTER_TYPE[_POINT] | _POINT
    ) -> bool:  # c_bool
        ...


_GetCursorPos = hint_cast(_GetCursorPosType, _user32.GetCursorPos)
'''
----- GetCursorPos function (winuser.h) -----

Retrieves the position of the mouse cursor, in screen coordinates.

https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getcursorpos

----- Parameters -----

[out] lpPoint

Type: LPPOINT

A pointer to a POINT structure that receives the screen coordinates of the
cursor.

----- Return value -----

Type: BOOL

Returns nonzero if successful or zero otherwise. To get extended error
information, call GetLastError.

----- Remarks -----

The cursor position is always specified in screen coordinates and is not
affected by the mapping mode of the window that contains the cursor.

The calling process must have WINSTA_READATTRIBUTES access to the window
station.

The input desktop must be the current desktop when you call GetCursorPos. Call
OpenInputDesktop[1] to determine whether the current desktop is the input
desktop. If it is not, call SetThreadDesktop[2] with the HDESK returned by
OpenInputDesktop to switch to that desktop.

[1] https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-openinputdesktop

[2] https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setthreaddesktop
'''
_GetCursorPos.argtypes = POINTER(_POINT),
_GetCursorPos.restype = c_bool


def _get_cursor_pos() -> _POINT:
    '''
    Abstraction layer over GetCursorPos (winuser.h)

    See https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getcursorpos
    '''
    cursor = _POINT()
    # cursor will be automatically be referenced by pointer
    _GetCursorPos(cursor)
    return cursor
# ------------------------------------------------------------------------------


# ----- SystemParametersInfoW Declaration -----------------------------------------------
class _SystemParametersInfoW_Type(Protocol):
    argtypes: tuple[type[c_uint], type[c_uint], type[c_void_p], type[c_uint]]
    restype: type[c_bool]

    def __call__(
        self,
        uiAction: c_uint | int,
        uiParam: c_uint | int,
        pvParam: c_void_p | Any,
        fWinIni: c_uint | int,
    ) -> bool:  # c_bool
        ...


_SystemParametersInfoW = hint_cast(
    _SystemParametersInfoW_Type,
    _user32.SystemParametersInfoW
)
'''
----- SystemParametersInfoW function (winuser.h) -----

Retrieves or sets the value of one of the system-wide parameters. This function
can also update the user profile while setting a parameter.

https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-systemparametersinfow

'''
_SystemParametersInfoW.argtypes = c_uint, c_uint, c_void_p, c_uint
_SystemParametersInfoW.restype = c_bool


# ----- Get system settings for mouse movement ---------------------------------
def _get_mouse_parameters() -> tuple[int, int, int]:
    '''
    Query system parameters for user's mouse settings.

    Abstraction layer over SystemParametersInfoW (winuser.h)

    https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-systemparametersinfow

    Information on _SPI_GETMOUSE

    Retrieves the two mouse threshold values and the mouse acceleration. The
    pvParam parameter must point to an array of three integers that receives these
    values. See mouse_event[1] for further information.

    https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-mouse_event
    '''
    pvParam: Array[c_uint] = (c_uint * 3)()
    _SystemParametersInfoW(_SPI_GETMOUSE, 0, pointer(pvParam), 0)
    return (pvParam[0], pvParam[1], pvParam[2])
# ------------------------------------------------------------------------------


# ----- Set system settings for mouse movement ---------------------------------
def _set_mouse_parameters(
    threshold1: int,
    threshold2: int,
    enhanced_pointer_precision: int
) -> bool:
    '''
    Set system parameters for user's mouse settings.

    Abstraction layer over SystemParametersInfoW (winuser.h)

    https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-systemparametersinfow

    Information on _SPI_SETMOUSE

    Sets the two mouse threshold values and the mouse acceleration. The pvParam
    parameter must point to an array of three integers that specifies these values.
    See mouse_event[1] for further information.

    https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-mouse_event
    '''
    pvParam: Final[Array[c_uint]] = (c_uint * 3)(
        threshold1,
        threshold2,
        enhanced_pointer_precision
    )
    # leave last parameter as 0 to make changes non-permanent and restore
    # themselves upon reboot if something goes wrong and the wrong setting
    # was overwritten.
    return _SystemParametersInfoW(_SPI_SETMOUSE, 0, pointer(pvParam), 0)
# ------------------------------------------------------------------------------


# ----- Get system settings for mouse speed ------------------------------------
def _get_mouse_speed() -> int:
    '''
    Query system parameters for user's mouse settings.

    Abstraction layer over SystemParametersInfoW (winuser.h)

    https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-systemparametersinfow

    Information on SPI_GETMOUSESPEED

    Retrieves the current mouse speed. The mouse speed determines how far the
    pointer will move based on the distance the mouse moves. The pvParam
    parameter must point to an integer that receives a value which ranges
    between 1 (slowest) and 20 (fastest). A value of 10 is the default. The
    value can be set by an end-user using the mouse control panel application
    or by an application using SPI_SETMOUSESPEED.
    '''
    pvParam: Array[c_uint] = (c_uint * 1)()
    _SystemParametersInfoW(_SPI_GETMOUSESPEED, 0, pointer(pvParam), 0)
    return pvParam[0]
# ------------------------------------------------------------------------------


# ----- Set system settings for mouse movement ---------------------------------
def _set_mouse_speed(mouse_speed: int) -> bool:
    '''
    Set system parameters for user's mouse settings.

    Abstraction layer over SystemParametersInfoW (winuser.h)

    https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-systemparametersinfow

    Information on SPI_SETMOUSESPEED

    Sets the current mouse speed. The pvParam parameter is an integer between
    1 (slowest) and 20 (fastest). A value of 10 is the default. This value is
    typically set using the mouse control panel application.
    '''
    pvParam: Final[Array[c_uint]] = (c_uint * 1)(mouse_speed)
    # leave last parameter as 0 to make changes non-permanent and restore
    # themselves upon reboot if something goes wrong and the wrong setting
    # was overwritten.
    return _SystemParametersInfoW(_SPI_SETMOUSESPEED, 0, pointer(pvParam), 0)
# ------------------------------------------------------------------------------


# ==============================================================================
# ===== Keyboard Scan Code Mappings ============================================
# ==============================================================================

# ----- Special class for key extended scancode sequences ----------------------
class ScancodeSequence(_list[int]):
    '''
    A special class with the sole purpose of representing extended scancode
    sequences that should be grouped together in a single INPUT array.

    Inserting non-scancode elements is illegal, but no runtime checks exist
    to verify correct input! Violations could lead to unpredictable runtime
    behaviour. You've been warned.
    '''
    pass
# ------------------------------------------------------------------------------


# ----- TypeAlias for KEYBOARD_MAPPING values ----------------------------------
ScancodeTypes: TypeAlias = "int | ScancodeSequence"
'''
Acceptable value types in KEYBOARD_MAPPING.

Accepts single standalone scancode integer or multiple scancode integers
contained in a special class ScancodeSequence instance.
'''
# ------------------------------------------------------------------------------


# ----- Offsets for values in KEYBOARD_MAPPING ---------------------------------
_OFFSET_EXTENDEDKEY: Final = 0xE000
_OFFSET_SHIFTKEY: Final = 0x10000
# ------------------------------------------------------------------------------


# ----- KEYBOARD_MAPPING -------------------------------------------------------
_SHIFT_SCANCODE: Final = 0x2A  # Used in auto-shifting
# should be keyboard MAKE scancodes ( <0x80 )
# some keys require the use of EXTENDEDKEY flags, they
US_QWERTY_MAPPING: Final[dict[str, ScancodeTypes]] = {
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
    'printscreen': 0x54,  # same result as ScancodeSequence([0xE02A, 0xE037])
    'prntscrn': 0x54,  # same result as ScancodeSequence([0xE02A, 0xE037])
    'prtsc': 0x54,  # same result as ScancodeSequence([0xE02A, 0xE037])
    'prtscr': 0x54,  # same result as ScancodeSequence([0xE02A, 0xE037])
    'scrolllock': 0x46,
    'ctrlbreak': 0x46 + _OFFSET_EXTENDEDKEY,
    'pause': ScancodeSequence([0xE11D, 0x45, 0xE19D, 0xC5]),
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
    '~': 0x29 + _OFFSET_SHIFTKEY,
    '!': 0x02 + _OFFSET_SHIFTKEY,
    '@': 0x03 + _OFFSET_SHIFTKEY,
    '#': 0x04 + _OFFSET_SHIFTKEY,
    '$': 0x05 + _OFFSET_SHIFTKEY,
    '%': 0x06 + _OFFSET_SHIFTKEY,
    '^': 0x07 + _OFFSET_SHIFTKEY,
    '&': 0x08 + _OFFSET_SHIFTKEY,
    '*': 0x09 + _OFFSET_SHIFTKEY,
    '(': 0x0A + _OFFSET_SHIFTKEY,
    ')': 0x0B + _OFFSET_SHIFTKEY,
    '_': 0x0C + _OFFSET_SHIFTKEY,
    '+': 0x0D + _OFFSET_SHIFTKEY,
    'backspace': 0x0E,
    '\b': 0x0E,
    'insert': 0x52 + _OFFSET_EXTENDEDKEY,
    'home': 0x47 + _OFFSET_EXTENDEDKEY,
    'pageup': 0x49 + _OFFSET_EXTENDEDKEY,
    'pgup': 0x49 + _OFFSET_EXTENDEDKEY,
    'pagedown': 0x51 + _OFFSET_EXTENDEDKEY,
    'pgdn': 0x51 + _OFFSET_EXTENDEDKEY,
    # numpad
    'numlock': 0x45,
    'divide': 0x35 + _OFFSET_EXTENDEDKEY,
    'multiply': 0x37,
    'subtract': 0x4A,
    'add': 0x4E,
    'decimal': 0x53,
    'numperiod': 0x53,
    'numpadenter': 0x1C + _OFFSET_EXTENDEDKEY,
    'numpad1': 0x4F,
    'numpad2': 0x50,
    'numpad3': 0x51,
    'numpad4': 0x4B,
    'numpad5': 0x4C,
    'numpad6': 0x4D,
    'numpad7': 0x47,
    'numpad8': 0x48,
    'numpad9': 0x49,
    'num0': 0x52,
    'num1': 0x4F,
    'num2': 0x50,
    'num3': 0x51,
    'num4': 0x4B,
    'num5': 0x4C,
    'num6': 0x4D,
    'num7': 0x47,
    'num8': 0x48,
    'num9': 0x49,
    'num0': 0x52,
    'clear': 0x4C,  # name from pyautogui
    # end numpad
    'tab': 0x0F,
    '\t': 0x0F,
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
    'Q': 0x10 + _OFFSET_SHIFTKEY,
    'W': 0x11 + _OFFSET_SHIFTKEY,
    'E': 0x12 + _OFFSET_SHIFTKEY,
    'R': 0x13 + _OFFSET_SHIFTKEY,
    'T': 0x14 + _OFFSET_SHIFTKEY,
    'Y': 0x15 + _OFFSET_SHIFTKEY,
    'U': 0x16 + _OFFSET_SHIFTKEY,
    'I': 0x17 + _OFFSET_SHIFTKEY,
    'O': 0x18 + _OFFSET_SHIFTKEY,
    'P': 0x19 + _OFFSET_SHIFTKEY,
    '{': 0x1A + _OFFSET_SHIFTKEY,
    '}': 0x1B + _OFFSET_SHIFTKEY,
    '|': 0x2B + _OFFSET_SHIFTKEY,
    'del': 0x53 + _OFFSET_EXTENDEDKEY,
    'delete': 0x53 + _OFFSET_EXTENDEDKEY,
    'end': 0x4F + _OFFSET_EXTENDEDKEY,
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
    'A': 0x1E + _OFFSET_SHIFTKEY,
    'S': 0x1F + _OFFSET_SHIFTKEY,
    'D': 0x20 + _OFFSET_SHIFTKEY,
    'F': 0x21 + _OFFSET_SHIFTKEY,
    'G': 0x22 + _OFFSET_SHIFTKEY,
    'H': 0x23 + _OFFSET_SHIFTKEY,
    'J': 0x24 + _OFFSET_SHIFTKEY,
    'K': 0x25 + _OFFSET_SHIFTKEY,
    'L': 0x26 + _OFFSET_SHIFTKEY,
    ':': 0x27 + _OFFSET_SHIFTKEY,
    '"': 0x28 + _OFFSET_SHIFTKEY,
    'enter': 0x1C,
    'return': 0x1C,
    '\n': 0x1C,
    'shift': _SHIFT_SCANCODE,
    'shiftleft': _SHIFT_SCANCODE,
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
    'Z': 0x2C + _OFFSET_SHIFTKEY,
    'X': 0x2D + _OFFSET_SHIFTKEY,
    'C': 0x2E + _OFFSET_SHIFTKEY,
    'V': 0x2F + _OFFSET_SHIFTKEY,
    'B': 0x30 + _OFFSET_SHIFTKEY,
    'N': 0x31 + _OFFSET_SHIFTKEY,
    'M': 0x32 + _OFFSET_SHIFTKEY,
    '<': 0x33 + _OFFSET_SHIFTKEY,
    '>': 0x34 + _OFFSET_SHIFTKEY,
    '?': 0x35 + _OFFSET_SHIFTKEY,
    'shiftright': 0x36,
    'ctrl': 0x1D,
    'ctrlleft': 0x1D,
    'win': 0x5B + _OFFSET_EXTENDEDKEY,
    'super': 0x5B + _OFFSET_EXTENDEDKEY,  # name from pyautogui
    'winleft': 0x5B + _OFFSET_EXTENDEDKEY,
    'alt': 0x38,
    'altleft': 0x38,
    ' ': 0x39,
    'space': 0x39,
    'altright': 0x38 + _OFFSET_EXTENDEDKEY,
    'winright': 0x5C + _OFFSET_EXTENDEDKEY,
    'apps': 0x5D + _OFFSET_EXTENDEDKEY,
    'context': 0x5D + _OFFSET_EXTENDEDKEY,
    'contextmenu': 0x5D + _OFFSET_EXTENDEDKEY,
    'ctrlright': 0x1D + _OFFSET_EXTENDEDKEY,
    # Originally from learncodebygaming/pydirectinput:
    # arrow key scancodes can be different depending on the hardware,
    # so I think the best solution is to look it up based on the virtual key
    # https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-mapvirtualkeya
    'up': _map_virtual_key(0x26, _MAPVK_VK_TO_VSC) + _OFFSET_EXTENDEDKEY,
    'left': _map_virtual_key(0x25, _MAPVK_VK_TO_VSC) + _OFFSET_EXTENDEDKEY,
    'down': _map_virtual_key(0x28, _MAPVK_VK_TO_VSC) + _OFFSET_EXTENDEDKEY,
    'right': _map_virtual_key(0x27, _MAPVK_VK_TO_VSC) + _OFFSET_EXTENDEDKEY,
    # While forking the original repository and working on the code,
    # I'm starting to doubt this still holds true.
    # As far as I can see, arrow keys are just the Numpad scancodes for Num
    # 2, 4, 6, and 8 with EXTENDEDKEY flag.
    # In fact, looking up the virtual key codes will just return the very same
    # scancodes the Numpad keys occupy.
    'help': 0x63,
    'sleep': 0x5f + _OFFSET_EXTENDEDKEY,
    'medianext': 0x19 + _OFFSET_EXTENDEDKEY,
    'nexttrack': 0x19 + _OFFSET_EXTENDEDKEY,
    'mediaprevious': 0x10 + _OFFSET_EXTENDEDKEY,
    'prevtrack': 0x10 + _OFFSET_EXTENDEDKEY,
    'mediastop': 0x24 + _OFFSET_EXTENDEDKEY,
    'stop': 0x24 + _OFFSET_EXTENDEDKEY,
    'mediaplay': 0x22 + _OFFSET_EXTENDEDKEY,
    'mediapause': 0x22 + _OFFSET_EXTENDEDKEY,
    'playpause': 0x22 + _OFFSET_EXTENDEDKEY,
    'mute': 0x20 + _OFFSET_EXTENDEDKEY,
    'volumemute': 0x20 + _OFFSET_EXTENDEDKEY,
    'volumeup': 0x30 + _OFFSET_EXTENDEDKEY,
    'volup': 0x30 + _OFFSET_EXTENDEDKEY,
    'volumedown': 0x2E + _OFFSET_EXTENDEDKEY,
    'voldown': 0x2E + _OFFSET_EXTENDEDKEY,
    'media': 0x6D + _OFFSET_EXTENDEDKEY,
    'launchmediaselect': 0x6D + _OFFSET_EXTENDEDKEY,
    'email': 0x6C + _OFFSET_EXTENDEDKEY,
    'launchmail': 0x6C + _OFFSET_EXTENDEDKEY,
    'calculator': 0x21 + _OFFSET_EXTENDEDKEY,
    'calc': 0x21 + _OFFSET_EXTENDEDKEY,
    'launch1': 0x6B + _OFFSET_EXTENDEDKEY,
    'launchapp1': 0x6B + _OFFSET_EXTENDEDKEY,
    'launch2': 0x21 + _OFFSET_EXTENDEDKEY,
    'launchapp2': 0x21 + _OFFSET_EXTENDEDKEY,
    'browsersearch': 0x65 + _OFFSET_EXTENDEDKEY,
    'browserhome': 0x32 + _OFFSET_EXTENDEDKEY,
    'browserforward': 0x69 + _OFFSET_EXTENDEDKEY,
    'browserback': 0x6A + _OFFSET_EXTENDEDKEY,
    'browserstop': 0x68 + _OFFSET_EXTENDEDKEY,
    'browserrefresh': 0x67 + _OFFSET_EXTENDEDKEY,
    'browserfavorites': 0x66 + _OFFSET_EXTENDEDKEY,
    'f13': 0x64,
    'f14': 0x65,
    'f15': 0x66,
    'f16': 0x67,
    'f17': 0x68,
    'f18': 0x69,
    'f19': 0x6A,
    'f20': 0x6B,
    'f21': 0x6C,
    'f22': 0x6D,
    'f23': 0x6E,
    'f24': 0x76,
}
'''
Maps a string representation of keyboard keys to their corresponding hardware
scan code. Based on standard US QWERTY-Layout.

Not intended to be changed at runtime!

If you want to change the keyboard mapping to better reflect your own keyboard
layout, use `KEYBOARD_MAPPING.update(your_dict)` where `your_dict` is a dict
that maps keynames to scancodes.
'''

KEYBOARD_MAPPING: dict[str, ScancodeTypes] = {}
'''
Maps a string representation of keyboard keys to their corresponding hardware
scan code. Based on standard US QWERTY-Layout by default.

If you want to change the keyboard mapping to better reflect your own keyboard
layout, use `KEYBOARD_MAPPING.update(your_dict)`, where `your_dict` is a dict
that maps keynames to scancodes.
'''
KEYBOARD_MAPPING.update(US_QWERTY_MAPPING)  # use US QWERTY by default
# ------------------------------------------------------------------------------


# ==============================================================================
# ===== Fail Safe and Pause implementation =====================================
# ==============================================================================

# ----- Exceptions -------------------------------------------------------------
class FailSafeException(Exception):
    '''Raised when _failSafeCheck detects failsafe mouse position.'''
    pass


class PriorInputFailedException(Exception):
    '''Raised in hold() context managers when raise_on_failure is set.'''
    pass
# ------------------------------------------------------------------------------


# ----- Failsafe Check ---------------------------------------------------------
def _failSafeCheck() -> None:
    '''
    Check if mouse has been moved into one of the defined failsafe points,
    indicated by global var `FAILSAFE_POINTS`, and raise `FailSafeException`
    if that's the case.

    Set global var `FAILSAFE` to False to stop raising exceptions.
    '''
    if FAILSAFE and tuple(position()) in FAILSAFE_POINTS:
        raise FailSafeException(
            "PyDirectInput fail-safe triggered from mouse moving to a corner "
            "of the screen. "
            "To disable this fail-safe, set pydirectinput.FAILSAFE to False. "
            "DISABLING FAIL-SAFE IS NOT RECOMMENDED."
        )
# ------------------------------------------------------------------------------


# ----- handle pause for generic input checks ----------------------------------
def _handlePause(_pause: Any) -> None:
    '''
    Pause the default amount of time if `_pause=True` in function arguments.
    '''
    if _pause:
        _sleep(PAUSE)
# ------------------------------------------------------------------------------


# ----- generic input check decorator ------------------------------------------
_PS = ParamSpec('_PS')  # param spec
_RT = TypeVar('_RT')  # return type


# direct copy of _genericPyAutoGUIChecks()
def _genericPyDirectInputChecks(
    wrappedFunction: Callable[_PS, _RT]
) -> Callable[_PS, _RT]:
    '''
    Decorator for wrapping input functions.

    Performs failsafe checking and inserts artifical delay after input
    functions have been executed unless disabled.

    The delay amount is set by global var `PAUSE`.
    '''
    @functools.wraps(wrappedFunction)
    def wrapper(*args: _PS.args, **kwargs: _PS.kwargs) -> _RT:
        funcArgs: dict[str, Any] = (
            inspect.getcallargs(wrappedFunction, *args, **kwargs)
        )
        _failSafeCheck()
        returnVal: _RT = wrappedFunction(*args, **kwargs)
        _handlePause(funcArgs.get("_pause"))
        return returnVal
    return wrapper
# ------------------------------------------------------------------------------


# ==============================================================================
# ===== Helper Functions =======================================================
# ==============================================================================

# ------------------------------------------------------------------------------
def _calc_normalized_screen_coord(
    pixel_coord: int,
    display_total: int
) -> int:
    '''
    Convert a pixel coordinate to normalized Windows screen coordinate value
    (range 0 - 65535) by taking the average of two neighboring pixels.
    '''
    # formula from this strange (probably machine translated) article
    # https://sourceexample.com/make-a-statement-in-the-source-code-of-the-coordinate-conversion-of-sendinput-(windows-api)-that-is-overflowing-in-the-streets-23df9/
    # win_coord = (x * 65536 + width - 1) // width
    # This alone is not enough, but we can do better by taking the average of
    # this pixel plus the next pixel.
    # In my testing this perfectly reflected the real pixel that SendInput moves
    # to, down to the pixels that Windows themselves can't resolve.
    this_pixel: Final[int] = (
        (pixel_coord * 65536 + display_total - 1) // display_total
    )
    next_pixel: Final[int] = (
        ((pixel_coord + 1) * 65536 + display_total - 1) // display_total
    )
    return (this_pixel + next_pixel) // 2
# ------------------------------------------------------------------------------


# ----- translate pixels to normalized Windows coordinates ---------------------
def _to_windows_coordinates(
    x: int = 0,
    y: int = 0,
    *,
    virtual: bool = False
) -> tuple[int, int]:
    '''
    Convert x,y coordinates to normalized windows coordinates and return as
    tuple (x, y).
    '''
    display_width: int
    display_height: int
    offset_left: int
    offset_top: int

    if virtual:
        display_width, display_height, offset_left, offset_top = virtual_size()
    else:
        display_width, display_height = size()
        offset_left, offset_top = 0, 0

    windows_x: int = _calc_normalized_screen_coord(
        x - offset_left,
        display_width
    )
    windows_y: int = _calc_normalized_screen_coord(
        y - offset_top,
        display_height
    )

    return windows_x, windows_y
# ------------------------------------------------------------------------------


# ----- get mouse position -----------------------------------------------------
def position(
    x: int | float | None = None,
    y: int | float | None = None
) -> tuple[int, int]:
    '''
    Return a postion tuple (x, y).

    If x and/or y argument(s) ar not given, use current mouse cursor coordinate
    instead.
    '''
    cursor: _POINT = _get_cursor_pos()
    return (
        cursor.x if x is None else int(x),
        cursor.y if y is None else int(y)
    )
# ------------------------------------------------------------------------------


# ----- get primary screen resolution ------------------------------------------
def size() -> tuple[int, int]:
    '''
    Return the size of the primary display as tuple (`width`, `height`).
    '''
    return (
        _get_system_metrics(_SM_CXSCREEN),
        _get_system_metrics(_SM_CYSCREEN)
    )
# ------------------------------------------------------------------------------


# ----- get resolution of multi monitor bounding box ---------------------------
def virtual_size() -> tuple[int, int, int, int]:
    '''
    Return the the display size of the complete virtual monitor bounding box
    rectangle as tuple (`width`, `height`, `left_offset`, `top_offset`).

    On a single monitor system, this function is equal to (*_size(), 0, 0).

    `left_offset` and `top_offset` are measured from the top left pixel of the
    primary monitor.
    '''
    return (
        _get_system_metrics(_SM_CXVIRTUALSCREEN),
        _get_system_metrics(_SM_CYVIRTUALSCREEN),
        _get_system_metrics(_SM_XVIRTUALSCREEN),
        _get_system_metrics(_SM_YVIRTUALSCREEN),
    )
# ------------------------------------------------------------------------------


# ----- are coordinates on primary monitor -------------------------------------
def onScreen(
    x: int | tuple[int, int] | None = None,
    y: int | None = None
) -> bool:
    '''
    Returns whether the given xy coordinates are on the primary screen or not.
    '''
    if isinstance(x, Sequence):
        assert not isinstance(x, int)  # remove int annotation, mypy needs this
        if y is not None:
            raise ValueError(
                "onScreen() does not accept Sequence-types as first argument "
                "if a second argument is also provided!"
            )
        try:
            x, y = x[0], x[1]
        except IndexError as e:
            raise ValueError(
                "onScreen() does not accept single element sequences "
                "as first argument!"
            ) from e

    x, y = position(x, y)
    display_width: int
    display_height: int
    display_width, display_height = size()

    return (0 <= x < display_width and 0 <= y < display_height)
# ------------------------------------------------------------------------------


# ----- lookup function for MOUSEINPUT data ------------------------------------
def _get_mouse_struct_data(
    button: str,
    method: Literal[0, 1, 2]
) -> tuple[int | None, int]:
    '''
    Translate a button string to INPUT struct data.

    Automatically detect the correct button if MOUSE_PRIMARY or MOUSE_SECONDARY
    are given as the button argument.
    '''
    if not (0 <= method <= 2):
        raise ValueError(f"method index {method} is not a valid argument!")

    buttons_swapped: bool
    if button == MOUSE_PRIMARY:
        buttons_swapped = (_get_system_metrics(_SM_SWAPBUTTON) != 0)
        button = MOUSE_RIGHT if buttons_swapped else MOUSE_LEFT
    elif button == MOUSE_SECONDARY:
        buttons_swapped = (_get_system_metrics(_SM_SWAPBUTTON) != 0)
        button = MOUSE_LEFT if buttons_swapped else MOUSE_RIGHT

    event_value: int | None
    event_value = _MOUSE_MAPPING_EVENTF.get(button, (None, None, None))[method]
    mouseData: int = _MOUSE_MAPPING_DATA.get(button, 0)

    return event_value, mouseData
# ------------------------------------------------------------------------------


# ----- normalize key name to lower case if not shifiting ----------------------
def _normalize_key(
    key: str,
    *,
    auto_shift: bool = False
) -> str:
    '''
    return a lowercase representation of `key` if key is longer than one
    character or automatic shifting is disabled (default).
    '''
    return key.lower() if (len(key) > 1 or not auto_shift) else key
# ------------------------------------------------------------------------------


# ----- calculate step target for a single steps -------------------------------
def _add_one_step(
    current: int,
    target: int,
    remaining_steps: int
) -> int:
    '''
    Calculate a target distance in a lazy way, providing self-healing to
    disturbed movement.
    '''
    if remaining_steps <= 1:
        return target
    step_factor: float = (remaining_steps - 1) / remaining_steps
    return round(target - ((target - current) * step_factor))
# ------------------------------------------------------------------------------


# ------------------------------------------------------------------------------
# ----- Mouse acceleration and Ehanced Pointer Precision storage singleton -----
class __MouseSpeedSettings:
    '''
    Allows controlled storage of Windows Enhanced Pointer Precision and mouse
    speed settings.
    '''
    __context_manager_epp: ClassVar[int | None] = None
    __context_manager_speed: ClassVar[int | None] = None
    __context_manager_count: ClassVar[int] = 0
    __context_manager_lock: ClassVar[Lock] = Lock()
    __manual_store_epp: ClassVar[int | None] = None
    __manual_store_speed: ClassVar[int | None] = None
    __manual_lock: ClassVar[Lock] = Lock()
    # --------------------------------------------------------------------------

    @classmethod
    def get_manual_mouse_settings(cls) -> tuple[int | None, int | None]:
        with cls.__manual_lock:
            return (
                cls.__manual_store_epp,
                cls.__manual_store_speed
            )
    # --------------------------------------------------------------------------

    @classmethod
    def set_manual_mouse_settings(
        cls,
        enhanced_pointer_precision_enabled: int,
        mouse_speed: int
    ) -> None:
        with cls.__manual_lock:
            cls.__manual_store_epp = enhanced_pointer_precision_enabled
            cls.__manual_store_speed = mouse_speed
    # --------------------------------------------------------------------------

    @classmethod
    def get_ctxtmgr_mouse_settings(cls) -> tuple[int | None, int | None]:
        with cls.__context_manager_lock:
            cls.__context_manager_count -= 1
            if cls.__context_manager_count > 0:
                # Don't retrieve stored value until last
                return (None, None)
            epp_enabled: int | None = cls.__context_manager_epp
            mouse_speed: int | None = cls.__context_manager_speed
            cls.__context_manager_epp = None
            cls.__context_manager_speed = None
            return (epp_enabled, mouse_speed)
    # --------------------------------------------------------------------------

    @classmethod
    def set_ctxtmgr_mouse_settings(
        cls,
        enhanced_pointer_precision_enabled: int,
        mouse_speed: int
    ) -> None:
        with cls.__context_manager_lock:
            cls.__context_manager_count += 1
            if cls.__context_manager_count > 1:
                # Don't allow changing the stored value if another value is
                # already stored
                return
            cls.__context_manager_epp = enhanced_pointer_precision_enabled
            cls.__context_manager_speed = mouse_speed
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------


# ----- Temporarily disable Enhanced Pointer Precision -------------------------
@contextmanager
def _without_mouse_acceleration() -> Generator[None, None, None]:
    '''
    Context manager that allows temporarily disabling Windows Enhanced Pointer
    Precision on enter and restoring the previous setting on exit.
    '''
    th1: int
    th2: int
    precision: int | None
    # store mouse parameters (thresholds, enhanced pointer precision)
    th1, th2, precision = _get_mouse_parameters()
    speed: int | None = _get_mouse_speed()
    assert(isinstance(precision, int))
    assert(isinstance(speed, int))
    __MouseSpeedSettings.set_ctxtmgr_mouse_settings(precision, speed)
    try:
        # modify mouse parameters
        if precision != 0:
            _set_mouse_parameters(th1, th2, 0)
        yield
    finally:
        # restore mouse parameters
        precision, speed = __MouseSpeedSettings.get_ctxtmgr_mouse_settings()
        if precision is not None:
            _set_mouse_parameters(th1, th2, precision)
        if speed is not None:
            _set_mouse_speed(speed)
# ------------------------------------------------------------------------------


# ----- manually store current enhanced pointer precision setting --------------
def store_mouse_acceleration_settings() -> None:
    '''
    Manually save the current Windows Enhanced Pointer Precision setting so that
    it can be restored later with
    `restore_mouse_acceleration_settings()`.
    '''
    precision: int
    _, _, precision = _get_mouse_parameters()
    speed: int = _get_mouse_speed()
    __MouseSpeedSettings.set_manual_mouse_settings(precision, speed)
# ------------------------------------------------------------------------------


# ----- manually restore current enhanced pointer precision setting ------------
def restore_mouse_acceleration_settings() -> None:
    '''
    Manually restore the current Windows Enhanced Pointer Precision setting to
    what it was beforehand when it was saved with
    `store_mouse_acceleration_settings()`.
    '''
    precision: int | None
    speed: int | None
    precision, speed = __MouseSpeedSettings.get_manual_mouse_settings()
    if precision is None or speed is None:
        raise ValueError(
            "Can't restore Enhanced Pointer Precision setting! "
            "Setting was not saved beforehand!"
        )
    th1: int
    th2: int
    th1, th2, _ = _get_mouse_parameters()
    if precision is not None:
        _set_mouse_parameters(th1, th2, precision)
    if speed is not None:
        _set_mouse_speed(speed)
# ------------------------------------------------------------------------------


# ==============================================================================
# ===== Main Mouse Functions ===================================================
# ==============================================================================

# ----- mouseDown --------------------------------------------------------------
@_genericPyDirectInputChecks
def mouseDown(
    x: int | None = None,
    y: int | None = None,
    button: str = MOUSE_PRIMARY,
    duration: float = 0.0,
    tween: None = None,
    logScreenshot: bool = False,
    _pause: bool = True,
    *,
    relative: bool = False,
    virtual: bool = False,
    attempt_pixel_perfect: bool = False,
    disable_mouse_acceleration: bool = False,
) -> None:
    '''
    Press down mouse button `button`.

    If `x` or `y` are given and not None, then the mouse will move the indicated
    postion before pressing the button.

    `button` is the name of the button to press. Use the public `MOUSE_*`
    constants to get valid argument values. (If you change the constants, then
    you will have to call `update_MOUSEEVENT_mappings()` to resync the lookup
    functions)

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.

    `duration`, `tween`, `relative`, `virtual`, `attempt_pixel_perfect`,
    `disable_mouse_acceleration` are only relevant if x or y are given.
    See `moveTo()` for further information.

    Raises `ValueError` if `button` is not a valid mouse button name.

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot` is currently unsupported.
    '''
    # TODO: bounding box check for valid position
    if x is not None or y is not None:
        moveTo(
            x,
            y,
            duration=duration,
            tween=tween,
            logScreenshot=logScreenshot,
            _pause=False,  # don't add an additional pause
            relative=relative,
            virtual=virtual,
            attempt_pixel_perfect=attempt_pixel_perfect,
            disable_mouse_acceleration=disable_mouse_acceleration,
        )

    event_value: int | None = None
    mouseData: int
    event_value, mouseData = _get_mouse_struct_data(button, _MOUSE_PRESS)

    if not event_value:
        raise ValueError(
            f'Invalid button argument! '
            f'Expected "{MOUSE_LEFT}", "{MOUSE_RIGHT}", "{MOUSE_MIDDLE}", '
            f'"{MOUSE_BUTTON4}", "{MOUSE_BUTTON5}", "{MOUSE_PRIMARY}" or '
            f'"{MOUSE_SECONDARY}"; got "{button}" instead!'
        )

    _send_input(_create_mouse_input(
        mouseData=mouseData,
        dwFlags=event_value
    ))
# ------------------------------------------------------------------------------


# ----- mouseUp ----------------------------------------------------------------
@_genericPyDirectInputChecks
def mouseUp(
    x: int | None = None,
    y: int | None = None,
    button: str = MOUSE_PRIMARY,
    duration: float = 0.0,
    tween: None = None,
    logScreenshot: bool = False,
    _pause: bool = True,
    *,
    relative: bool = False,
    virtual: bool = False,
    attempt_pixel_perfect: bool = False,
    disable_mouse_acceleration: bool = False,
) -> None:
    '''
    Lift up mouse button `button`.

    If `x` or `y` are given and not None, then the mouse will move the indicated
    postion before lifting the button.

    `button` is the name of the button to press. Use the public `MOUSE_*`
    constants to get valid argument values. (If you change the constants, then
    you will have to call `update_MOUSEEVENT_mappings()` to resync the lookup
    functions)

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.

    `duration`, `tween`, `relative`, `virtual`, `attempt_pixel_perfect`,
    `disable_mouse_acceleration` are only relevant if x or y are given.
    See `moveTo()` for further information.

    Raises `ValueError` if `button` is not a valid mouse button name.

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot` is currently unsupported.
    '''
    # TODO: bounding box check for valid position
    if x is not None or y is not None:
        moveTo(
            x,
            y,
            duration=duration,
            tween=tween,
            logScreenshot=logScreenshot,
            _pause=False,  # don't add an additional pause
            relative=relative,
            virtual=virtual,
            attempt_pixel_perfect=attempt_pixel_perfect,
            disable_mouse_acceleration=disable_mouse_acceleration,
        )

    event_value: int | None = None
    mouseData: int
    event_value, mouseData = _get_mouse_struct_data(button, _MOUSE_RELEASE)

    if not event_value:
        raise ValueError(
            f'Invalid button argument! '
            f'Expected "{MOUSE_LEFT}", "{MOUSE_RIGHT}", "{MOUSE_MIDDLE}", '
            f'"{MOUSE_BUTTON4}", "{MOUSE_BUTTON5}", "{MOUSE_PRIMARY}" or '
            f'"{MOUSE_SECONDARY}"; got "{button}" instead!'
        )

    _send_input(_create_mouse_input(
        mouseData=mouseData,
        dwFlags=event_value
    ))
# ------------------------------------------------------------------------------


# ----- click ------------------------------------------------------------------
@_genericPyDirectInputChecks
def click(
    x: int | None = None,
    y: int | None = None,
    clicks: int = 1,
    interval: float = 0.0,
    button: str = MOUSE_PRIMARY,
    duration: float = 0.0,
    tween: None = None,
    logScreenshot: bool = False,
    _pause: bool = True,
    *,
    relative: bool = False,
    virtual: bool = False,
    attempt_pixel_perfect: bool = False,
    disable_mouse_acceleration: bool = False,
) -> None:
    '''
    Click mouse button `button` (combining press down and lift up).

    If `x` or `y` are given and not None, then the mouse will move the indicated
    postion before clicking the button.

    `button` is the name of the button to press. Use the public `MOUSE_*`
    constants to get valid argument values. (If you change the constants, then
    you will have to call `update_MOUSEEVENT_mappings()` to resync the lookup
    functions)

    `clicks` is an integer that determines the amount of times the button will
    be clicked.

    `interval` is the wait time in seconds between clicks.

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.

    `duration`, `tween`, `relative`, `virtual`, `attempt_pixel_perfect`,
    `disable_mouse_acceleration` are only relevant if x or y are given.
    See `moveTo()` for further information.

    Raises `ValueError` if `button` is not a valid mouse button name.

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot` is currently unsupported.
    '''
    # TODO: bounding box check for valid position
    if x is not None or y is not None:
        moveTo(
            x,
            y,
            duration=duration,
            tween=tween,
            logScreenshot=logScreenshot,
            _pause=False,  # don't add an additional pause
            relative=relative,
            virtual=virtual,
            attempt_pixel_perfect=attempt_pixel_perfect,
            disable_mouse_acceleration=disable_mouse_acceleration,
        )

    event_value: int | None = None
    mouseData: int
    event_value, mouseData = _get_mouse_struct_data(button, _MOUSE_CLICK)

    if not event_value:
        raise ValueError(
            f'Invalid button argument! '
            f'Expected "{MOUSE_LEFT}", "{MOUSE_RIGHT}", "{MOUSE_MIDDLE}", '
            f'"{MOUSE_BUTTON4}", "{MOUSE_BUTTON5}", "{MOUSE_PRIMARY}" or '
            f'"{MOUSE_SECONDARY}"; got "{button}" instead!'
        )

    apply_interval: bool = False
    for _ in range(clicks):
        if apply_interval:  # Don't delay first press
            _sleep(interval)
        apply_interval = True

        _send_input(_create_mouse_input(
            mouseData=mouseData,
            dwFlags=event_value
        ))
# ------------------------------------------------------------------------------


# ----- leftClick --------------------------------------------------------------
def leftClick(
    x: int | None = None,
    y: int | None = None,
    interval: float = 0.0,
    duration: float = 0.0,
    tween: None = None,
    logScreenshot: bool = False,
    _pause: bool = True,
    *,
    relative: bool = False,
    virtual: bool = False,
    attempt_pixel_perfect: bool = False,
    disable_mouse_acceleration: bool = False,
) -> None:
    '''
    Click Left Mouse button.

    See `click()` for more information
    '''
    click(
        x,
        y,
        clicks=1,
        interval=interval,
        button=MOUSE_LEFT,
        duration=duration,
        tween=tween,
        logScreenshot=logScreenshot,
        _pause=_pause,  # Keep _pause since this function has no input checks
        relative=relative,
        virtual=virtual,
        attempt_pixel_perfect=attempt_pixel_perfect,
        disable_mouse_acceleration=disable_mouse_acceleration,
    )
# ------------------------------------------------------------------------------


# ----- rightClick -------------------------------------------------------------
def rightClick(
    x: int | None = None,
    y: int | None = None,
    interval: float = 0.0,
    duration: float = 0.0,
    tween: None = None,
    logScreenshot: bool = False,
    _pause: bool = True,
    *,
    relative: bool = False,
    virtual: bool = False,
    attempt_pixel_perfect: bool = False,
    disable_mouse_acceleration: bool = False,
) -> None:
    '''
    Click Right Mouse button.

    See `click()` for more information
    '''
    click(
        x,
        y,
        clicks=1,
        interval=interval,
        button=MOUSE_RIGHT,
        duration=duration,
        tween=tween,
        logScreenshot=logScreenshot,
        _pause=_pause,  # Keep _pause since this function has no input checks
        relative=relative,
        virtual=virtual,
        attempt_pixel_perfect=attempt_pixel_perfect,
        disable_mouse_acceleration=disable_mouse_acceleration,
    )
# ------------------------------------------------------------------------------


# ----- middleClick ------------------------------------------------------------
def middleClick(
    x: int | None = None,
    y: int | None = None,
    interval: float = 0.0,
    duration: float = 0.0,
    tween: None = None,
    logScreenshot: bool = False,
    _pause: bool = True,
    *,
    relative: bool = False,
    virtual: bool = False,
    attempt_pixel_perfect: bool = False,
    disable_mouse_acceleration: bool = False,
) -> None:
    '''
    Click Middle Mouse button.

    See `click()` for more information
    '''
    click(
        x,
        y,
        clicks=1,
        interval=interval,
        button=MOUSE_MIDDLE,
        duration=duration,
        tween=tween,
        logScreenshot=logScreenshot,
        _pause=_pause,  # Keep _pause since this function has no input checks
        relative=relative,
        virtual=virtual,
        attempt_pixel_perfect=attempt_pixel_perfect,
        disable_mouse_acceleration=disable_mouse_acceleration,
    )
# ------------------------------------------------------------------------------


# ----- doubleClick ------------------------------------------------------------
def doubleClick(
    x: int | None = None,
    y: int | None = None,
    interval: float = 0.0,
    button: str = MOUSE_LEFT,
    duration: float = 0.0,
    tween: None = None,
    logScreenshot: bool = False,
    _pause: bool = True,
    *,
    relative: bool = False,
    virtual: bool = False,
    attempt_pixel_perfect: bool = False,
    disable_mouse_acceleration: bool = False,
) -> None:
    '''
    Double click `button`.

    See `click()` for more information
    '''
    click(
        x,
        y,
        clicks=2,
        interval=interval,
        button=button,
        duration=duration,
        tween=tween,
        logScreenshot=logScreenshot,
        _pause=_pause,  # Keep _pause since this function has no input checks
        relative=relative,
        virtual=virtual,
        attempt_pixel_perfect=attempt_pixel_perfect,
        disable_mouse_acceleration=disable_mouse_acceleration,
    )
# ------------------------------------------------------------------------------


# ----- tripleClick ------------------------------------------------------------
def tripleClick(
    x: int | None = None,
    y: int | None = None,
    interval: float = 0.0,
    button: str = MOUSE_LEFT,
    duration: float = 0.0,
    tween: None = None,
    logScreenshot: bool = False,
    _pause: bool = True,
    *,
    relative: bool = False,
    virtual: bool = False,
    attempt_pixel_perfect: bool = False,
    disable_mouse_acceleration: bool = False,
) -> None:
    '''
    Triple click `button`.

    See `click()` for more information
    '''
    click(
        x,
        y,
        clicks=3,
        interval=interval,
        button=button,
        duration=duration,
        tween=tween,
        logScreenshot=logScreenshot,
        _pause=_pause,  # Keep _pause since this function has no input checks
        relative=relative,
        virtual=virtual,
        attempt_pixel_perfect=attempt_pixel_perfect,
        disable_mouse_acceleration=disable_mouse_acceleration,
    )
# ------------------------------------------------------------------------------


# ----- scroll -----------------------------------------------------------------
# Originally implemented by
# https://github.com/learncodebygaming/pydirectinput/pull/22
@_genericPyDirectInputChecks
def scroll(
    clicks: int = 0,
    x: Any = None,  # x and y do absolutely nothing, still keeping the arguments
    y: Any = None,  # to stay consistent with PyAutoGUI.
    logScreenshot: bool = False,
    _pause: bool = True,
    *,
    interval: float = 0.0
) -> None:
    '''
    Vertically scroll mouse `clicks` number of times, waiting `interval`
    seconds between every scroll.

    Negative values of `clicks` will scroll down, postive values will scroll
    up.

    `x` and `y` are intentionally ignored and only exists to keep the call
    signature backwards-compatible with PyAutoGui.
    If you need to change the mouse position before scrolling use one of the
    `move()` functions.

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot` is currently unsupported.
    '''
    direction: Literal[-1, 1]
    if clicks >= 0:
        direction = 1
    else:
        direction = -1
        clicks = abs(clicks)

    apply_interval: bool = False
    for _ in range(clicks):
        if apply_interval:
            _sleep(interval)
        apply_interval = True

        _send_input(_create_mouse_input(
            mouseData=(direction * _WHEEL_DELTA),
            dwFlags=_MOUSEEVENTF_WHEEL
        ))
# ------------------------------------------------------------------------------


# ----- hscroll ----------------------------------------------------------------
@_genericPyDirectInputChecks
def hscroll(
    clicks: int = 0,
    x: Any = None,  # x and y do absolutely nothing, still keeping the arguments
    y: Any = None,  # to stay consistent with PyAutoGUI.
    logScreenshot: bool = False,
    _pause: bool = True,
    *,
    interval: float = 0.0
) -> None:
    '''
    Horizontally scroll mouse `clicks` number of times, waiting `interval`
    seconds between every scroll.

    Negative values of `clicks` will scroll left, postive values will scroll
    right.

    `x` and `y` are intentionally ignored and only exists to keep the call
    signature backwards-compatible with PyAutoGui.
    If you need to change the mouse position before scrolling use one of the
    `move()` functions.

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot` is currently unsupported.
    '''
    direction: Literal[-1, 1]
    if clicks >= 0:
        direction = 1
    else:
        direction = -1
        clicks = abs(clicks)

    apply_interval: bool = False
    for _ in range(clicks):
        if apply_interval:
            _sleep(interval)
        apply_interval = True

        _send_input(_create_mouse_input(
            mouseData=(direction * _WHEEL_DELTA),
            dwFlags=_MOUSEEVENTF_HWHEEL
        ))
# ------------------------------------------------------------------------------


# ----- scroll alias -----------------------------------------------------------
vscroll = scroll
# ------------------------------------------------------------------------------


# ----- moveTo -----------------------------------------------------------------
@_genericPyDirectInputChecks
def moveTo(
    x: int | None = None,
    y: int | None = None,
    duration: float = 0.0,
    tween: None = None,
    logScreenshot: bool = False,
    _pause: bool = True,
    relative: bool = False,
    *,
    virtual: bool = False,
    attempt_pixel_perfect: bool = False,
    disable_mouse_acceleration: bool = False,
) -> None:
    '''
    Move the mouse to an absolute(*) postion indicated by the arguments of
    `x` and `y`. The coordinates 0,0 represent the top left pixel of the
    primary monitor.

    If `duration` is floating point number greater than 0, then this function
    will automatically split the movement into microsteps instead of moving
    straight to the target position.

    (*) If `relative` is set: Use absolute mouse movement to move the mouse
    cursor to the current mouse position offset by arguments `x` and `y`.

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.

    Setting `virtual` to True (default: False) changes the way internal APIs
    handle coordinates and is intended for multi monitor systems. It should be
    pretty much unncessary even for multi monitor systems, since all the
    necessary internal calculations beyond the border of the primay monitor
    work without it.

    The way that Windows calculates the target pixel coordinates internally
    unfortunately leads to inaccuracies and unreachable pixels, especially
    if the `virtual` option is used.

    If you need the target position to be pixel perfect, you can try setting
    `attempt_pixel_perfect` to True, which will use tiny relative movements
    to correct the unreachable position.

    Relative movement is influenced by mouse speed and Windows Enhanced Pointer
    Precision, which can be temporarily disabled by setting
    `disable_mouse_acceleration`.

    ----------------------------------------------------------------------------
    Careful! Disabling mouse acceleration settings is MAYBE thread-safe,
    NOT multiprocessing-safe, and DEFINITELY NOT independent processses safe!

    If you you start a relative movement while another is already in progress
    than the second movement could overwrite the first setting and disable
    Enhanced Pointer Precision and change mouse speed.
    There are some measures in place to try to mitigate that risk, such as an
    internal counter that only allows storing and restoring the acceleration
    settings as long as no other movement is currently in progress.
    Additionally, the acceleration settings can be manually saved and
    restored with `store_mouse_acceleration_settings()` and
    `restore_mouse_acceleration_settings()`. For your convinnience, the
    store function is automatically called during import to save your current
    setting. You can then call the restore function at any time.

    If all fails, the setting is not written permanently to your Windows
    settings, so it should restore itself upon reboot.

    Bottom line: Don't use the `disable_mouse_acceleration` argument if you use
    this library in multiple threads / processes / programs at the same time!

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot`, `tween` are currently unsupported.
    '''
    # TODO: bounding box check for valid position
    final_x: int
    final_y: int
    current_x: int = 0
    current_y: int = 0
    if relative:
        current_x, current_y = position()
        final_x = current_x + (0 if x is None else x)
        final_y = current_y + (0 if y is None else y)
    else:
        # if only x or y is provided, will keep the current position for the
        # other axis
        final_x, final_y = position(x, y)

    dwFlags: int = (_MOUSEEVENTF_MOVE | _MOUSEEVENTF_ABSOLUTE)
    if virtual:
        dwFlags |= _MOUSEEVENTF_VIRTUALDESK

    final_time: Final[float] = _time() + duration
    keep_looping: bool = True

    apply_duration: bool = False
    while keep_looping:
        if apply_duration:
            _sleep(MINIMUM_SLEEP_IDEAL)  # sleep between iterations
        apply_duration = True

        time_segments: int = min(
            int((final_time - _time()) / MINIMUM_SLEEP_ACTUAL),
            max(abs(final_x - current_x), abs(final_y - current_y))
        )
        if time_segments <= 1:
            keep_looping = False

        current_x, current_y = position()
        x = _add_one_step(current_x, final_x, time_segments)
        y = _add_one_step(current_y, final_y, time_segments)

        if x == current_x and y == current_y:
            # no change in movement for current segment ->try again
            continue

        x, y = _to_windows_coordinates(x, y, virtual=virtual)
        _send_input(_create_mouse_input(
            dx=x, dy=y,
            dwFlags=dwFlags
        ))

    # After-care: Did Windows move the cursor correctly?
    # If not, attempt to fix off-by-one errors.
    if attempt_pixel_perfect:
        current_x, current_y = position()
        if current_x == final_x and current_y == final_y:
            return  # We are already pixel perfect, great!
        moveRel(
            xOffset=final_x - current_x,
            yOffset=final_y - current_y,
            duration=0.0,
            _pause=False,  # don't add an additional pause
            relative=True,
            virtual=virtual,
            disable_mouse_acceleration=disable_mouse_acceleration
        )
# ------------------------------------------------------------------------------


# ----- moveRel ----------------------------------------------------------------
@_genericPyDirectInputChecks
def moveRel(
    xOffset: int | None = None,
    yOffset: int | None = None,
    duration: float = 0.0,
    tween: None = None,
    logScreenshot: bool = False,
    _pause: bool = True,
    relative: bool = False,
    *,
    virtual: bool = False,
    disable_mouse_acceleration: bool = False
) -> None:
    '''
    Move the mouse a relative amount determined by `xOffset` and `yOffset`.

    If `duration` is floating point number greater than 0, then this function
    will automatically split the movement into microsteps instead of moving the
    complete distance instantly.

    `relative` parameter decides how the movement is executed.
    -> `False`: New postion is calculated and absolute movement is used.
    -> `True`: Uses API relative movement (can be inconsistent)

    The inconsistency issue can be solved by disabling Enhanced Pointer
    Precision and set Mouse speed to 10 in Windows mouse settings. Since users
    may not want to permanently change their input settings just for this
    library, the `disable_mouse_acceleration` argument can be used to
    temporarily disable Enhanced Pointer Precision and fix mouse speed at 10
    and restore it after the mouse movement.

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.

    Setting `virtual` to True (default: False) changes the way internal APIs
    handle coordinates and is intended for multi monitor systems. It should be
    pretty much unncessary even for multi monitor systems, since all the
    necessary internal calculations beyond the border of the primay monitor
    work without it.

    ----------------------------------------------------------------------------
    Careful! Disabling mouse acceleration settings is MAYBE thread-safe,
    NOT multiprocessing-safe, and DEFINITELY NOT independent processses safe!

    If you you start a relative movement while another is already in progress
    than the second movement could overwrite the first setting and disable
    Enhanced Pointer Precision and change mouse speed.
    There are some measures in place to try to mitigate that risk, such as an
    internal counter that only allows storing and restoring the acceleration
    settings as long as no other movement is currently in progress.
    Additionally, the acceleration settings can be manually saved and
    restored with `store_mouse_acceleration_settings()` and
    `restore_mouse_acceleration_settings()`. For your convinnience, the
    store function is automatically called during import to save your current
    setting. You can then call the restore function at any time.

    If all fails, the setting is not written permanently to your Windows
    settings, so it should restore itself upon reboot.

    Bottom line: Don't use the `disable_mouse_acceleration` argument if you use
    this library in multiple threads / processes / programs at the same time!

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot`, `tween` are currently unsupported.
    '''
    # TODO: bounding box check for valid position
    if xOffset is None:
        xOffset = 0
    if yOffset is None:
        yOffset = 0
    if not relative:
        moveTo(
            xOffset,
            yOffset,
            duration=duration,
            tween=tween,
            logScreenshot=logScreenshot,
            _pause=False,  # don't add an additional pause
            relative=True,
            virtual=virtual
        )
    else:
        current_x: int = 0
        current_y: int = 0
        final_time: Final[float] = _time() + duration
        keep_looping: bool = True

        apply_duration: bool = False
        while keep_looping:
            if apply_duration:
                _sleep(MINIMUM_SLEEP_IDEAL)  # sleep between iterations
            apply_duration = True

            time_segments: int = min(
                int((final_time - _time()) / MINIMUM_SLEEP_ACTUAL),
                max(xOffset - current_x, yOffset - current_y)
            )
            if time_segments <= 1:
                keep_looping = False

            x = _add_one_step(current_x, xOffset, time_segments) - current_x
            y = _add_one_step(current_y, yOffset, time_segments) - current_y

            if x == 0 and y == 0:
                # no change in movement for current segment ->try again
                continue

            input_struct: _INPUT = _create_mouse_input(
                dx=x, dy=y,
                dwFlags=_MOUSEEVENTF_MOVE
            )
            current_x += x
            current_y += y

            # When using MOUSEEVENTF_MOVE for relative movement the results may
            # be inconsistent. "Relative mouse motion is subject to the effects
            # of the mouse speed and the two-mouse threshold values. A user sets
            # these three values with the Pointer Speed slider of the Control
            # Panel's Mouse Properties sheet. You can obtain and set these
            # values using the SystemParametersInfo function."
            # https://docs.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-mouseinput
            # https://stackoverflow.com/questions/50601200/pyhon-directinput-mouse-relative-moving-act-not-as-expected
            # We can solve this issue by just disabling Enhanced Pointer
            # Precision and forcing Mouse speed to neutral 10.
            # Since that is a user setting that users may want to have enabled,
            # use a optional keyword-only argument and a state-restoring context
            # manager to give users the choice if they want this library messing
            # around in their Windows settings.
            if disable_mouse_acceleration:
                # Use a context manager to temporarily disable enhanced pointer
                # precision
                with _without_mouse_acceleration():
                    _send_input(input_struct)
            else:
                _send_input(input_struct)
# ------------------------------------------------------------------------------


# ----- move alias -------------------------------------------------------------
# move() and moveRel() are equivalent.
move = moveRel
# ------------------------------------------------------------------------------


# ----- dragTo -----------------------------------------------------------------
@_genericPyDirectInputChecks
def dragTo(
    x: int | None = None,
    y: int | None = None,
    duration: float = 0.0,
    tween: None = None,
    button: str | None = None,
    logScreenshot: bool = False,
    _pause: bool = True,
    mouseDownUp: bool = True,
    *,
    relative: bool = False,
    virtual: bool = False,
    attempt_pixel_perfect: bool = False,
    disable_mouse_acceleration: bool = False
) -> None:
    '''
    Press and hold a mouse button while moving to the target coordinates.

    See `moveTo` for more information on most arguments.

    `button` is a string that is one of the following constants:
    MOUSE_LEFT, MOUSE_RIGHT, MOUSE_MIDDLE, MOUSE_BUTTON4, MOUSE_BUTTON5,
    MOUSE_PRIMARY (default), MOUSE_SECONDARY.

    If `mouseDownUp` (default: True) is manually set to False, then this
    function is basically the same as `moveTo`. Only exists to match PyAutoGUI.

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot`, `tween` are currently unsupported.
    '''
    # TODO: bounding box check for valid position
    if button is None:
        button = MOUSE_PRIMARY
    if mouseDownUp:
        mouseDown(button=button, _pause=False, virtual=virtual)
    moveTo(
        x,
        y,
        duration=duration,
        tween=tween,
        logScreenshot=logScreenshot,
        _pause=False,  # don't add an additional pause
        relative=relative,
        virtual=virtual,
        attempt_pixel_perfect=attempt_pixel_perfect,
        disable_mouse_acceleration=disable_mouse_acceleration
    )
    if mouseDownUp:
        mouseUp(button=button, _pause=False, virtual=virtual)
# ------------------------------------------------------------------------------


# ----- dragRel ----------------------------------------------------------------
@_genericPyDirectInputChecks
def dragRel(
    xOffset: int | None = None,
    yOffset: int | None = None,
    duration: float = 0.0,
    tween: None = None,
    button: str | None = None,
    logScreenshot: bool = False,
    _pause: bool = True,
    mouseDownUp: bool = True,
    *,
    relative: bool = False,
    virtual: bool = False,
    disable_mouse_acceleration: bool = False
) -> None:
    '''
    Press and hold a mouse button while moving a relative distance

    See `moveRel` for more information on most arguments.

    `button` is a string that is one of the following constants:
    MOUSE_LEFT, MOUSE_RIGHT, MOUSE_MIDDLE, MOUSE_BUTTON4, MOUSE_BUTTON5,
    MOUSE_PRIMARY (default), MOUSE_SECONDARY.

    If `mouseDownUp` (default: True) is manually set to False, then this
    function is basically the same as `moveTo`. Only exists to match PyAutoGUI.

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot`, `tween` are currently unsupported.
    '''
    # TODO: bounding box check for valid position
    if button is None:
        button = MOUSE_PRIMARY
    if mouseDownUp:
        mouseDown(button=button, _pause=False, virtual=virtual)
    moveRel(
        xOffset,
        yOffset,
        duration=duration,
        tween=tween,
        _pause=False,  # don't add an additional pause
        relative=False,
        virtual=virtual,
        disable_mouse_acceleration=disable_mouse_acceleration,
    )
    if mouseDownUp:
        mouseUp(button=button, _pause=False, virtual=virtual)
# ------------------------------------------------------------------------------


# ----- drag alias -------------------------------------------------------------
drag = dragRel
# ------------------------------------------------------------------------------


# ==============================================================================
# ===== Keyboard Functions =====================================================
# ==============================================================================

# ----- isValidKey -------------------------------------------------------------
def isValidKey(key: str) -> bool:
    '''
    Returns true if key name `key` can be translated into a valid scan code.
    '''
    return key in KEYBOARD_MAPPING
# ------------------------------------------------------------------------------


# ===== scancode functions =====================================================

# ----- scancode_keyDown -------------------------------------------------------
@_genericPyDirectInputChecks
def scancode_keyDown(
    scancodes: ScancodeTypes,
    logScreenshot: None = None,
    _pause: bool = True,
    *,
    auto_shift: bool = False
) -> bool:
    '''
    Press down key corresponding to `scancodes`.

    The actually pressed key will depend on your system keyboard layout.
    Limits the available character set but should provide the best
    compatibility.

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.

    `auto_shift` is used internally by higher level functions to automatically
    press the shift key before supported scancodes (indicitated by a special
    bit outside the regular scancode range, while it technically can be used,
    it's not intended for public access).

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot` is currently unsupported.
    '''
    scancodes_sequence: ScancodeSequence
    if isinstance(scancodes, int):
        scancodes_sequence = ScancodeSequence([scancodes])
    else:
        scancodes_sequence = scancodes

    keybdFlags: int = _KEYEVENTF_SCANCODE
    input_structs: list[_INPUT] = []
    extendedFlag: int

    # Init event tracking
    insertedEvents: int = 0
    expectedEvents: int = 0

    for scancode in scancodes_sequence:

        if auto_shift and scancode & _OFFSET_SHIFTKEY:
            input_structs += [_create_keyboard_input(
                wScan=_SHIFT_SCANCODE,
                dwFlags=keybdFlags
            )]
            expectedEvents += 1

        scancode = scancode & 0xFFFF

        extendedFlag = _KEYEVENTF_EXTENDEDKEY if scancode >= 0xE000 else 0
        input_structs += [_create_keyboard_input(
            wScan=scancode,
            dwFlags=keybdFlags | extendedFlag
        )]
        expectedEvents += 1

    insertedEvents += _send_input(input_structs)

    # SendInput returns the number of event successfully inserted into
    # input stream
    # https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput#return-value
    return insertedEvents == expectedEvents
# ------------------------------------------------------------------------------


# ----- scancode_keyUp ---------------------------------------------------------
@_genericPyDirectInputChecks
def scancode_keyUp(
    scancodes: ScancodeTypes,
    logScreenshot: None = None,
    _pause: bool = True,
    *,
    auto_shift: bool = False
) -> bool:
    '''
    Release key corresponding to `scancodes`.

    The actually pressed key will depend on your system keyboard layout.
    Limits the available character set but should provide the best
    compatibility.

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.

    `auto_shift` is used internally by higher level functions to automatically
    press the shift key before supported scancodes (indicitated by a special
    bit outside the regular scancode range, while it technically can be used,
    it's not intended for public access).

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot` is currently unsupported.
    '''
    scancodes_sequence: ScancodeSequence
    if isinstance(scancodes, int):
        scancodes_sequence = ScancodeSequence([scancodes])
    else:
        scancodes_sequence = scancodes

    keybdFlags: int = _KEYEVENTF_SCANCODE | _KEYEVENTF_KEYUP
    input_structs: list[_INPUT] = []
    extendedFlag: int

    # Init event tracking
    insertedEvents: int = 0
    expectedEvents: int = 0

    for scancode in scancodes_sequence:

        if auto_shift and scancode & _OFFSET_SHIFTKEY:
            input_structs += [_create_keyboard_input(
                wScan=_SHIFT_SCANCODE,
                dwFlags=keybdFlags
            )]
            expectedEvents += 1

        scancode = scancode & 0xFFFF

        extendedFlag = _KEYEVENTF_EXTENDEDKEY if scancode >= 0xE000 else 0
        input_structs += [_create_keyboard_input(
            wScan=scancode & 0xFFFF,
            dwFlags=keybdFlags | extendedFlag
        )]
        expectedEvents += 1

    insertedEvents += _send_input(input_structs)
    return insertedEvents == expectedEvents
# ------------------------------------------------------------------------------


# ----- _helper_scancode_press -------------------------------------------------
def _helper_scancode_press(
    scancodes: ScancodeTypes,
    duration: float = 0.0,
    _pause: bool = True,
    auto_shift: bool = False
) -> bool:
    '''
    Press `scancode`, wait for `duration` seconds, release `scancode`.

    Return `True` if complete press was successful.
    '''
    downed: bool = scancode_keyDown(
        scancodes,
        _pause=_pause,
        auto_shift=auto_shift
    )
    _sleep(duration)
    upped: bool = scancode_keyUp(
        scancodes,
        _pause=_pause,
        auto_shift=auto_shift
    )
    # Count key press as complete if key was "downed" and "upped"
    # successfully
    return bool(downed and upped)
# ------------------------------------------------------------------------------


# ----- scancode_press ---------------------------------------------------------
# Ignored parameters: logScreenshot
@_genericPyDirectInputChecks
def scancode_press(
    scancodes: ScancodeTypes | Sequence[ScancodeTypes],
    presses: int = 1,
    interval: float = 0.0,
    logScreenshot: None = None,
    _pause: bool = True,
    *,
    auto_shift: bool = False,
    delay: float = 0.0,
    duration: float = 0.0
) -> bool:
    '''
    Press the sequence of `keys` for `presses` amount of times.

    The actually pressed key will depend on your system keyboard layout.
    Limits the available character set but should provide the best
    compatibility.

    Explanation of time parameters (seconds as floating point numbers):

    - `interval` is the time spent waiting between sequences. If `keys` is a
    str instance or single element list, then `interval` will be ignored.
    - `delay` is the time from one complete key (press+release) to the next one
    in the same sequence. If there is only a single key in a sequence, then
    `delay` will be ignored.
    - `duration` is the time spent on holding every key before releasing it
    again.

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.
    Be aware, that the global pause defined by the PAUSE `constant` only applies
    after every call to this function, not inbetween (no extra pause between
    pressing and releasing key, use the `duration` argument instead)!

    `auto_shift` is used internally by higher level functions to automatically
    press the shift key before supported scancodes (indicitated by a special
    bit outside the regular scancode range, while it technically can be used,
    it's not intended for public access).

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot` is currently unsupported.
    '''
    scancodes_sequence: Sequence[ScancodeTypes]
    if isinstance(scancodes, int):
        scancodes_sequence = [ScancodeSequence([scancodes])]
    elif isinstance(scancodes, ScancodeSequence):
        scancodes_sequence = [scancodes]
    else:
        scancodes_sequence = scancodes

    # We need to press x keys y times, which comes out to x*y presses in total
    expectedPresses: int = presses * len(scancodes_sequence)
    completedPresses: int = 0

    apply_interval: bool = False
    for _ in range(presses):
        if apply_interval:  # Don't delay first press
            _sleep(interval)
        apply_interval = True

        apply_delay: bool = False
        for c in scancodes_sequence:
            if apply_delay:  # Don't delay first press
                _sleep(delay)
            apply_delay = True

            completedPresses += _helper_scancode_press(
                c,
                duration,
                _pause=False,
                auto_shift=auto_shift
            )

    return completedPresses == expectedPresses
# ------------------------------------------------------------------------------


# ----- scancode_hold ----------------------------------------------------------
@contextmanager
@_genericPyDirectInputChecks
def scancode_hold(
    scancodes: ScancodeTypes | Sequence[ScancodeTypes],
    logScreenshot: None = None,
    _pause: bool = True,
    *,
    auto_shift: bool = False,
    raise_on_failure: bool = False,
) -> Generator[None, None, None]:
    '''
    Hold the sequence of keys corresponding to `scancodes` as long as the
    context manager is in scope (press upon entry, release upon exit).

    Keys will be released in reverse order (LIFO), but still practically
    instantenous.

    The actually pressed key will depend on your system keyboard layout.
    Limits the available character set but should provide the best
    compatibility.

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.
    Be aware, that the global pause defined by the PAUSE `constant` only applies
    after every call to this function, not inbetween (no pause between press
    and releasing key)!

    `auto_shift` is used internally by higher level functions to automatically
    press the shift key before supported scancodes (indicitated by a special
    bit outside the regular scancode range, while it technically can be used,
    it's not intended for public access).

    If `raise_on_failure` is True, then `PriorInputFailedException` will be
    raised if not all keyboard inputs could be executed successfully.

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot` is currently unsupported.
    '''
    scancodes_sequence: Sequence[ScancodeTypes]
    if isinstance(scancodes, int):
        scancodes_sequence = [ScancodeSequence([scancodes])]
    elif isinstance(scancodes, ScancodeSequence):
        scancodes_sequence = [scancodes]
    else:
        scancodes_sequence = scancodes

    expectedPresses: int = len(scancodes_sequence)
    downed: int = 0
    upped: int = 0

    try:
        for c in scancodes_sequence:
            downed += scancode_keyDown(c, _pause=False, auto_shift=auto_shift)
        yield
    finally:
        for c in reversed(scancodes_sequence):
            upped += scancode_keyUp(c, _pause=False, auto_shift=auto_shift)
        if raise_on_failure and not (expectedPresses == downed == upped):
            raise PriorInputFailedException
# ------------------------------------------------------------------------------


# ----- scancode_hotkey --------------------------------------------------------
@_genericPyDirectInputChecks
def scancode_hotkey(
    *args: ScancodeTypes,
    interval: float = 0.0,
    wait: float = 0.0,
    logScreenshot: None = None,
    _pause: bool = True,
    auto_shift: bool = True,
) -> bool:
    '''
    Press down buttons in order they are specified as arguments,
    releasing them in reverse order, e.g. 0x1D, 0x2E will first press
    Control, then C and release C before releasing Control.

    Use keyword-only argument `interval` to specify a delay between single
    keys when pressing and releasing and `wait` for delay between last press
    and first release.

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.
    Be aware, that the global pause defined by the PAUSE `constant` only applies
    after every call to this function, not inbetween (no pause between press
    and releasing key)!

    `auto_shift` is used internally by higher level functions to automatically
    press the shift key before supported scancodes (indicitated by a special
    bit outside the regular scancode range, while it technically can be used,
    it's not intended for public access).

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot` is currently unsupported.
    '''
    expectedPresses: int = len(args)
    downed: int = 0
    upped: int = 0

    apply_interval: bool = False
    for code in args:
        if apply_interval:
            _sleep(interval)  # sleep between iterations
        apply_interval = True

        downed += scancode_keyDown(code, _pause=False, auto_shift=auto_shift)

    _sleep(wait)

    apply_interval = False
    for code in reversed(args):
        if apply_interval:
            _sleep(interval)  # sleep between iterations
        apply_interval = True

        upped += scancode_keyUp(code, _pause=False, auto_shift=auto_shift)

    return (expectedPresses == downed == upped)
# ------------------------------------------------------------------------------


# ===== keyname functions ======================================================

# ----- keyDown ----------------------------------------------------------------
# Ignored parameters: logScreenshot
@_genericPyDirectInputChecks
def keyDown(
    key: str,
    logScreenshot: None = None,
    _pause: bool = True,
    *,
    auto_shift: bool = False
) -> bool:
    '''
    Press down key corresponding to key name `key`.

    `key` will be interpreted as a keyboard key (US QWERTY).
    The actually pressed key will depend on your system keyboard layout.
    Limits the available character set but should provide the best
    compatibility.

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.

    If `auto_shift` is True, then "shifted" characters like upper case letters
    and the symbols on the number row automatically insert a Shift scancode
    into the input sequence.

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot` is currently unsupported.
    '''
    scancode: ScancodeTypes | None = KEYBOARD_MAPPING.get(key)
    if scancode is None:
        return False
    return scancode_keyDown(
        scancode,
        logScreenshot,
        _pause,
        auto_shift=auto_shift
    )
# ------------------------------------------------------------------------------


# ----- keyUp ------------------------------------------------------------------
# Ignored parameters: logScreenshot
def keyUp(
    key: str,
    logScreenshot: None = None,
    _pause: bool = True,
    *,
    auto_shift: bool = False
) -> bool:
    '''
    Lift up key corresponding to key name `key`.

    `key` will be interpreted as a keyboard key (US QWERTY).
    The actually lifted key will depend on your system keyboard layout.
    Limits the available character set but should provide the best
    compatibility.

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.

    If `auto_shift` is True, then "shifted" characters like upper case letters
    and the symbols on the number row automatically insert a Shift scancode
    into the input sequence.

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot` is currently unsupported.
    '''
    scancode: ScancodeTypes | None = KEYBOARD_MAPPING.get(key)
    if scancode is None:
        return False
    return scancode_keyUp(
        scancode,
        logScreenshot,
        _pause,
        auto_shift=auto_shift
    )
# ------------------------------------------------------------------------------


# ----- _helper_press ----------------------------------------------------------
def _helper_press(
    key: str,
    duration: float = 0.0,
    _pause: bool = True,
    auto_shift: bool = False
) -> bool:
    '''
    Press `key`, wait for `duration` seconds, release `key`.

    Return `True` if complete press was successful.
    '''
    downed: bool = keyDown(key, _pause=_pause, auto_shift=auto_shift)
    _sleep(duration)
    upped: bool = keyUp(key, _pause=_pause, auto_shift=auto_shift)
    # Count key press as complete if key was "downed" and "upped"
    # successfully
    return bool(downed and upped)
# ------------------------------------------------------------------------------


# ----- press ------------------------------------------------------------------
# Ignored parameters: logScreenshot
@_genericPyDirectInputChecks
def press(
    keys: str | Sequence[str],
    presses: int = 1,
    interval: float = 0.0,
    logScreenshot: None = None,
    _pause: bool = True,
    *,
    auto_shift: bool = False,
    delay: float = 0.0,
    duration: float = 0.0
) -> bool:
    '''
    Press the sequence of `keys` for `presses` amount of times.

    `keys` will be interpreted as sequence of keyboard keys (US QWERTY).
    The actually pressed key will depend on your system keyboard layout.
    Limits the available character set but should provide the best
    compatibility.

    Explanation of time parameters (seconds as floating point numbers):

    - `interval` is the time spent waiting between sequences. If `keys` is a
    str instance or single element list, then `interval` will be ignored.
    - `delay` is the time from one complete key (press+release) to the next one
    in the same sequence. If there is only a single key in a sequence, then
    `delay` will be ignored.
    - `duration` is the time spent on holding every key before releasing it
    again.

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.
    Be aware, that the global pause defined by the `PAUSE` var only applies
    after every call to this function, not inbetween (no extra pause between
    pressing and releasing key, use the `duration` argument instead)!

    If `auto_shift` is True, then "shifted" characters like upper case letters
    and the symbols on the number row automatically insert a Shift scancode
    into the input sequence.

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot` is currently unsupported.
    '''
    if isinstance(keys, str):
        keys = [keys]  # If keys is 'enter', convert it to ['enter'].
    keys = [_normalize_key(key, auto_shift=auto_shift) for key in keys]

    # We need to press x keys y times, which comes out to x*y presses in total
    expectedPresses: int = presses * len(keys)
    completedPresses: int = 0

    apply_interval: bool = False
    for _ in range(presses):
        if apply_interval:  # Don't delay first press
            _sleep(interval)
        apply_interval = True

        apply_delay: bool = False
        for k in keys:
            if apply_delay:  # Don't delay first press
                _sleep(delay)
            apply_delay = True

            completedPresses += _helper_press(
                k,
                duration,
                _pause=False,
                auto_shift=auto_shift
            )

    return completedPresses == expectedPresses
# ------------------------------------------------------------------------------


# ----- hold -------------------------------------------------------------------
@contextmanager
@_genericPyDirectInputChecks
def hold(
    keys: str | Sequence[str],
    logScreenshot: None = None,
    _pause: bool = True,
    *,
    auto_shift: bool = False,
    raise_on_failure: bool = False,
) -> Generator[None, None, None]:
    '''
    Hold the sequence of keys corresponding to key names in `keys` as long as
    the context manager is in scope (press upon entry, release upon exit).

    Keys will be released in reverse order (LIFO), but still practically
    instantenous.

    `key` will be interpreted as a keyboard key (US QWERTY).
    The actually pressed key will depend on your system keyboard layout.
    Limits the available character set but should provide the best
    compatibility.

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.
    Be aware, that the global pause defined by the PAUSE `constant` only applies
    after every call to this function, not inbetween (no pause between press
    and releasing key)!

    `auto_shift` is used internally by higher level functions to automatically
    press the shift key before supported scancodes (indicitated by a special
    bit outside the regular scancode range, while it technically can be used,
    it's not intended for public access).

    If `raise_on_failure` is True, then `PriorInputFailedException` will be
    raised if not all keyboard inputs could be executed successfully.

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot` is currently unsupported.
    '''
    if isinstance(keys, str):
        keys = [keys]  # make single element into iterable
    keys = [_normalize_key(key, auto_shift=auto_shift) for key in keys]

    expectedPresses: int = len(keys)
    downed: int = 0
    upped: int = 0

    try:
        for k in keys:
            downed += keyDown(k, auto_shift=auto_shift)
        yield
    finally:
        for k in reversed(keys):
            upped += keyUp(k, auto_shift=auto_shift)
        if raise_on_failure and not (expectedPresses == downed == upped):
            raise PriorInputFailedException
# ------------------------------------------------------------------------------


# ----- typewrite --------------------------------------------------------------
@_genericPyDirectInputChecks
def typewrite(
    message: str,
    interval: float = 0.0,
    logScreenshot: None = None,
    _pause: bool = True,
    *,
    auto_shift: bool = False,
    delay: float = 0.0,
    duration: float = 0.0
) -> None:
    '''
    Break down `message` into a single character key sequence and press each
    key one by one.

    `message` will be interpreted as sequence of keyboard keys (US QWERTY).
    The actually pressed keys will depend on your system keyboard layout.
    Limits the available character set but should provide the best
    compatibility.

    Explanation of time parameters (seconds as floating point numbers):

    - `interval` is the time spent waiting between sequences. If `message` is a
    single character string, then `interval` will be ignored.
    - `delay` is the time from one complete key (press+release) to the next one
    in the same sequence. If there is only a single key in a sequence, then
    `delay` will be ignored.
    - `duration` is the time spent on holding every key before releasing it
    again.

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.
    Be aware, that the global pause defined by the PAUSE `constant` only applies
    after every call to this function, not inbetween (no pause between press
    and releasing key)!

    `auto_shift` is used internally by higher level functions to automatically
    press the shift key before supported scancodes (indicitated by a special
    bit outside the regular scancode range, while it technically can be used,
    it's not intended for public access).

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot` is currently unsupported.
    '''

    apply_interval: bool = False
    for key in message:
        if apply_interval:  # Don't delay first press
            _sleep(interval)
        apply_interval = True

        press(
            key,
            _pause=False,
            auto_shift=auto_shift,
            delay=delay,
            duration=duration
        )
# ------------------------------------------------------------------------------


# ----- typewrite alias --------------------------------------------------------
write = typewrite
# ------------------------------------------------------------------------------


# ----- hotkey -----------------------------------------------------------------
# Originally implemented by
# https://github.com/learncodebygaming/pydirectinput/pull/30
@_genericPyDirectInputChecks
def hotkey(
    *args: str,
    interval: float = 0.0,
    wait: float = 0.0,
    logScreenshot: None = None,
    _pause: bool = True,
    auto_shift: bool = True,
) -> None:
    '''
    Press down buttons in order they are specified as arguments,
    releasing them in reverse order, e.g. 'ctrl', 'c' will first press
    Control, then C and release C before releasing Control.

    Use keyword-only argument `interval` to specify a delay between single
    keys when pressing and releasing and `wait` for delay between last press
    and first release.

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.
    Be aware, that the global pause defined by the PAUSE `constant` only applies
    after every call to this function, not inbetween (no pause between press
    and releasing key)!

    `auto_shift` is used internally by higher level functions to automatically
    press the shift key before supported scancodes (indicitated by a special
    bit outside the regular scancode range, while it technically can be used,
    it's not intended for public access).

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot` is currently unsupported.
    '''
    apply_interval: bool = False
    for key in args:
        if apply_interval:
            _sleep(interval)  # sleep between iterations
        apply_interval = True

        keyDown(key, _pause=False, auto_shift=auto_shift)

    _sleep(wait)

    apply_interval = False
    for key in reversed(args):
        if apply_interval:
            _sleep(interval)  # sleep between iterations
        apply_interval = True

        keyUp(key, _pause=False, auto_shift=auto_shift)
# ------------------------------------------------------------------------------


# ===== unicode functions ======================================================

# ----- unicode_charDown -------------------------------------------------------
@_genericPyDirectInputChecks
def unicode_charDown(
    char: str,
    logScreenshot: None = None,
    _pause: bool = True
) -> bool:
    '''
    Send Unicode character(s) `char` to currently focused application as
    WM_KEYDOWN message.

    `char` will be interpreted as a string of Unicode characters
    (independet from keyboard layout). Supports complete Unicode character set
    but may not be compatible with every application.

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot` is currently unsupported.
    '''
    utf16surrogates: bytes = char.encode('utf-16be')
    codes: Sequence[int] = unpack(
        f'>{len(utf16surrogates)//2}H',
        utf16surrogates
    )

    keybdFlags: int = _KEYEVENTF_UNICODE

    input_structs: list[_INPUT] = [
        _create_keyboard_input(
            wVk=0,
            wScan=charcode,
            dwFlags=keybdFlags
        )
        for charcode in codes
    ]
    # Init event tracking
    expectedEvents: int = len(input_structs)
    insertedEvents: int = _send_input(input_structs)

    return insertedEvents == expectedEvents
# ------------------------------------------------------------------------------


# ----- unicode_charUp ---------------------------------------------------------
@_genericPyDirectInputChecks
def unicode_charUp(
    char: str,
    logScreenshot: None = None,
    _pause: bool = True
) -> bool:
    '''
    Send Unicode character(s) `char` to currently focused application as
    WM_KEYUP message.

    `char` will be interpreted as a string of Unicode characters
    (independet from keyboard layout). Supports complete Unicode character set
    but may not be compatible with every application.

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot` is currently unsupported.
    '''
    utf16surrogates: bytes = char.encode('utf-16be')
    codes: Sequence[int] = unpack(
        f'>{len(utf16surrogates)//2}H',
        utf16surrogates
    )

    keybdFlags: int = _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP

    input_structs: list[_INPUT] = [
        _create_keyboard_input(
            wVk=0,
            wScan=charcode,
            dwFlags=keybdFlags
        )
        for charcode in codes
    ]
    # Init event tracking
    expectedEvents: int = len(input_structs)
    insertedEvents: int = _send_input(input_structs)

    return insertedEvents == expectedEvents
# ------------------------------------------------------------------------------


# ----- _helper_unicode_press_char ---------------------------------------------
def _helper_unicode_press_char(
    char: str,
    duration: float = 0.0,
    _pause: bool = True,
) -> bool:
    '''
    Press `key`, wait for `duration` seconds, release `key`.

    Return `True` if complete press was successful.
    '''
    downed: bool = unicode_charDown(char, _pause=_pause)
    _sleep(duration)
    upped: bool = unicode_charUp(char, _pause=_pause)
    # Count key press as complete if key was "downed" and "upped"
    # successfully
    return bool(downed and upped)


# ----- unicode_press ----------------------------------------------------------
@_genericPyDirectInputChecks
def unicode_press(
    chars: str | Sequence[str],
    presses: int = 1,
    interval: float = 0.0,
    logScreenshot: None = None,
    _pause: bool = True,
    *,
    delay: float = 0.0,
    duration: float = 0.0
) -> bool:
    '''
    Press the sequence of `chars` for `presses` amount of times.

    `chars` will be interpreted as a sequence of Unicode characters
    (independet from keyboard layout). Supports complete Unicode character set
    but may not be compatible with every application.

    Explanation of time parameters (seconds as floating point numbers):

    - `interval` is the time spent waiting between sequences. If `chars` is a
    str instance or single element list, then `interval` will be ignored.
    - `delay` is the time from one complete char (press+release) to the next one
    in the same sequence. If there is only a single char in a sequence, then
    `delay` will be ignored.
    - `duration` is the time spent on holding every char before releasing it
    again.

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.
    Be aware, that the global pause defined by the PAUSE `constant` only applies
    after every call to this function, not inbetween (no extra pause between
    pressing and releasing key, use the `duration` argument instead)!

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot` is currently unsupported.
    '''
    if isinstance(chars, str):
        chars = [chars]

    # We need to press x keys y times, which comes out to x*y presses in total
    expectedPresses: int = presses * len(chars)
    completedPresses: int = 0

    apply_interval: bool = False
    for _ in range(presses):
        if apply_interval:  # Don't delay first press
            _sleep(interval)
        apply_interval = True

        apply_delay: bool = False
        for c in chars:
            if apply_delay:  # Don't delay first press
                _sleep(delay)
            apply_delay = True

            completedPresses += _helper_unicode_press_char(
                c,
                duration,
                _pause=False,
            )

    return completedPresses == expectedPresses
# ------------------------------------------------------------------------------


# ----- unicode_hold -----------------------------------------------------------
@contextmanager
@_genericPyDirectInputChecks
def unicode_hold(
    chars: str | Sequence[str],
    logScreenshot: None = None,
    _pause: bool = True,
    *,
    raise_on_failure: bool = False,
) -> Generator[None, None, None]:
    '''
    Hold the sequence of "keys" corresponding to unicode characters in `chars`
    as long as the context manager is in scope (press upon entry,
    release upon exit).

    `chars` will be interpreted as a sequence of Unicode characters
    (independet from keyboard layout). Supports complete Unicode character set
    but may not be compatible with every application.

    Keys will be released in reverse order (LIFO), but still practically
    instantenous.

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.
    Be aware, that the global pause defined by the PAUSE `constant` only applies
    after every call to this function, not inbetween (no pause between press
    and releasing key)!

    If `raise_on_failure` is True, then `PriorInputFailedException` will be
    raised if not all keyboard inputs could be executed successfully.

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot` is currently unsupported.
    '''
    if isinstance(chars, str):
        chars = [chars]  # make single element into iterable

    expectedPresses: int = len(chars)
    downed: int = 0
    upped: int = 0

    try:
        for c in chars:
            downed += unicode_charDown(c)
        yield
    finally:
        for c in reversed(chars):
            upped += unicode_charUp(c)
        if raise_on_failure and not (expectedPresses == downed == upped):
            raise PriorInputFailedException
# ------------------------------------------------------------------------------


# ----- unicode_typewrite ------------------------------------------------------
@_genericPyDirectInputChecks
def unicode_typewrite(
    message: str,
    interval: float = 0.0,
    logScreenshot: None = None,
    _pause: bool = True,
    *,
    delay: float = 0.0,
    duration: float = 0.0
) -> None:
    '''
    Break down `message` into characters and press them one by one.

    `message` will be interpreted as a sequence of Unicode characters
    (independet from keyboard layout). Supports complete Unicode character set
    but may not be compatible with every application.

    Explanation of time parameters (seconds as floating point numbers):

    - `interval` is the time spent waiting between sequences. If `message` is a
    single character string, then `interval` will be ignored.
    - `delay` is the time from one complete key (press+release) to the next one
    in the same sequence. If there is only a single key in a sequence, then
    `delay` will be ignored.
    - `duration` is the time spent on holding every key before releasing it
    again.

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.
    Be aware, that the global pause defined by the PAUSE `constant` only applies
    after every call to this function, not inbetween (no pause between press
    and releasing key)!

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot` is currently unsupported.
    '''
    apply_interval: bool = False
    for char in message:
        if apply_interval:
            _sleep(interval)  # sleep between iterations
        apply_interval = True

        unicode_press(char, _pause=False, delay=delay, duration=duration)
# ------------------------------------------------------------------------------


# ----- unicode_typewrite alias ------------------------------------------------
unicode_write = unicode_typewrite
# ------------------------------------------------------------------------------


# ----- unicode_hotkey ---------------------------------------------------------
@_genericPyDirectInputChecks
def unicode_hotkey(
    *args: str,
    interval: float = 0.0,
    wait: float = 0.0,
    logScreenshot: None = None,
    _pause: bool = True,
) -> None:
    '''
    Press down buttons in order they are specified as arguments,
    releasing them in reverse order.

    This function makes little sense for Unicode characters and mainly exists
    for parity with the other, lower-level hotkey functions!

    See `unicode_press()` for an alternative function that presses keys in
    series instead.

    Use keyword-only argument `interval` to specify a delay between single
    keys when pressing and releasing and `wait` for delay between last press
    and first release.

    If `_pause` is True (default), then an automatic sleep will be performed
    after the function finshes executing. The duration is set by the global
    variable `PAUSE`.
    Be aware, that the global pause defined by the PAUSE `constant` only applies
    after every call to this function, not inbetween (no pause between press
    and releasing key)!

    ----------------------------------------------------------------------------

    NOTE: `logScreenshot` is currently unsupported.
    '''
    apply_interval: bool = False
    for char in args:
        if apply_interval:
            _sleep(interval)  # sleep between iterations
        apply_interval = True

        unicode_charDown(char, _pause=False)

    _sleep(wait)

    apply_interval = False
    for char in reversed(args):
        if apply_interval:
            _sleep(interval)  # sleep between iterations
        apply_interval = True

        unicode_charUp(char, _pause=False)
# ------------------------------------------------------------------------------


# ------------------------------------------------------------------------------
# Save current Enhanced Pointer Precsion setting during import
store_mouse_acceleration_settings()
# ------------------------------------------------------------------------------
