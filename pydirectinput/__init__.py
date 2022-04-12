'''
Partial implementation of DirectInput function calls to simulate
mouse and keyboard inputs.
'''

# native imports
import functools
import inspect
import time
from ctypes import (
    POINTER, Array, Structure, Union, c_bool, c_int, c_long,
    c_short, c_uint, c_ulong, c_ushort, pointer, sizeof, windll,
)
from typing import (
    TYPE_CHECKING, Any, Callable, Final, Literal,
    Protocol, Sequence, TypeAlias, TypeVar,
)
from typing import cast as hint_cast


if TYPE_CHECKING:
    # https://github.com/python/mypy/issues/7540#issuecomment-845741357
    _POINTER_TYPE = pointer
else:
    # Monkeypatch typed pointer from typeshed into ctypes
    class __pointer:
        @classmethod
        def __class_getitem__(cls, item):
            return POINTER(item)
    _POINTER_TYPE = __pointer

# ==============================================================================
# ===== External constants =====================================================
# ==============================================================================

# "Constants" for failsafe check and pause
# Intendend to be modified by callers
FAILSAFE: bool = True
FAILSAFE_POINTS: list[tuple[int, int]] = [(0, 0)]
PAUSE: float = 0.01  # 1/100 second pause by default.


# Constants for the mouse button names
MOUSE_LEFT: Final[str] = "left"
MOUSE_MIDDLE: Final[str] = "middle"
MOUSE_RIGHT: Final[str] = "right"
MOUSE_PRIMARY: Final[str] = "primary"
MOUSE_SECONDARY: Final[str] = "secondary"
MOUSE_BUTTON4: Final[str] = "mouse4"
MOUSE_X1: Final[str] = "x1"
MOUSE_BUTTON5: Final[str] = "mouse5"
MOUSE_X2: Final[str] = "x2"


# ==============================================================================
# ===== Internal constants =====================================================
# ==============================================================================


# INPUT.type constants
_INPUT_MOUSE: Literal[0x0000] = 0x0000  # c_ulong(0x0000)
'''The event is a mouse event. Use the mi structure of the union.'''
_INPUT_KEYBOARD: Literal[0x0001] = 0x0001  # c_ulong(0x0001)
'''The event is a keyboard event. Use the ki structure of the union.'''
_INPUT_HARDWARE: Literal[0x0002] = 0x0002  # c_ulong(0x0002)
'''The event is a hardware event. Use the hi structure of the union.'''


# MOUSEINPUT.mouseData constants
_XBUTTON1: Literal[0x0001] = 0x0001  # c_ulong(0x0001)
'''Set if the first X button is pressed or released.'''
_XBUTTON2: Literal[0x0002] = 0x0002  # c_ulong(0x0002)
'''Set if the second X button is pressed or released.'''


# MOUSEINPUT.dwFlags constants
_MOUSEEVENTF_MOVE: Literal[0x0001] = 0x0001  # c_ulong(0x0001)
'''Movement occurred.'''

_MOUSEEVENTF_LEFTDOWN: Literal[0x0002] = 0x0002  # c_ulong(0x0002)
'''The left button was pressed.'''
_MOUSEEVENTF_LEFTUP: Literal[0x0004] = 0x0004  # c_ulong(0x0004)
'''The left button was released.'''
_MOUSEEVENTF_LEFTCLICK: Final[int] = (
    _MOUSEEVENTF_LEFTDOWN + _MOUSEEVENTF_LEFTUP  # c_ulong(0x0006)
)

_MOUSEEVENTF_RIGHTDOWN: Literal[0x0008] = 0x0008  # c_ulong(0x0008)
'''The right button was pressed.'''
_MOUSEEVENTF_RIGHTUP: Literal[0x0010] = 0x0010  # c_ulong(0x0010)
'''The right button was released.'''
_MOUSEEVENTF_RIGHTCLICK: Final[int] = (
    _MOUSEEVENTF_RIGHTDOWN + _MOUSEEVENTF_RIGHTUP  # c_ulong(0x0018)
)

_MOUSEEVENTF_MIDDLEDOWN: Literal[0x0020] = 0x0020  # c_ulong(0x0020)
'''The middle button was pressed.'''
_MOUSEEVENTF_MIDDLEUP: Literal[0x0040] = 0x0040  # c_ulong(0x0040)
'''The middle button was released.'''
_MOUSEEVENTF_MIDDLECLICK: Final[int] = (
    _MOUSEEVENTF_MIDDLEDOWN + _MOUSEEVENTF_MIDDLEUP  # c_ulong(0x0060)
)

_MOUSEEVENTF_XDOWN: Literal[0x0080] = 0x0080  # c_ulong(0x0080)
'''An X button was pressed.'''
_MOUSEEVENTF_XUP: Literal[0x0100] = 0x0100  # c_ulong(0x0100)
'''An X button was released.'''
_MOUSEEVENTF_XCLICK: Final[int] = (
    _MOUSEEVENTF_XDOWN + _MOUSEEVENTF_XUP  # c_ulong(0x0180)
)

_MOUSEEVENTF_WHEEL: Literal[0x0800] = 0x0800  # c_ulong(0x0800)
'''
The wheel was moved, if the mouse has a wheel.
The amount of movement is specified in mouseData.
'''
_MOUSEEVENTF_HWHEEL: Literal[0x1000] = 0x1000  # c_ulong(0x1000)
'''
The wheel was moved horizontally, if the mouse has a wheel. The amount of
movement is specified in mouseData.
Windows XP/2000: This value is not supported.
'''

_MOUSEEVENTF_MOVE_NOCOALESCE: Literal[0x2000] = 0x2000  # c_ulong(0x2000)
'''
The WM_MOUSEMOVE messages will not be coalesced. The default behavior is to
coalesce WM_MOUSEMOVE messages.
Windows XP/2000: This value is not supported.
'''
_MOUSEEVENTF_VIRTUALDESK: Literal[0x4000] = 0x4000  # c_ulong(0x4000)
'''
Maps coordinates to the entire desktop. Must be used with MOUSEEVENTF_ABSOLUTE.
'''
_MOUSEEVENTF_ABSOLUTE: Literal[0x8000] = 0x8000  # c_ulong(0x8000)
'''
The dx and dy members contain normalized absolute coordinates. If the flag is
not set, dxand dy contain relative data (the change in position since the last
reported position). This flag can be set, or not set, regardless of what kind of
mouse or other pointing device, if any, is connected to the system. For further
information about relative mouse motion, see the following Remarks section.
'''

_WHEEL_DELTA: Literal[120] = 120


# KEYBDINPUT.dwFlags Flags
_KEYEVENTF_EXTENDEDKEY: Literal[0x0001] = 0x0001  # c_ulong(0x0001)
'''
If specified, the scan code was preceded by a prefix byte that has the value
0xE0 (224).
'''
_KEYEVENTF_KEYUP: Literal[0x0002] = 0x0002  # c_ulong(0x0002)
'''
If specified, the key is being released. If not specified, the key is being
pressed.
'''
_KEYEVENTF_UNICODE: Literal[0x0004] = 0x0004  # c_ulong(0x0004)
'''
If specified, the system synthesizes a VK_PACKET keystroke. The wVk parameter
must be zero. This flag can only be combined with the KEYEVENTF_KEYUP flag.
For more information, see the Remarks section.
'''
_KEYEVENTF_SCANCODE: Literal[0x0008] = 0x0008  # c_ulong(0x0008)
'''If specified, wScan identifies the key and wVk is ignored.'''


# MapVirtualKey Map Types
_MAPVK_VK_TO_VSC: Literal[0] = 0  # c_unit(0)
'''
The uCode parameter is a virtual-key code and is translated into a scan code.
If it is a virtual-key code that does not distinguish between left- and
right-hand keys, the left-hand scan code is returned.
If there is no translation, the function returns 0.
'''
_MAPVK_VSC_TO_VK: Literal[1] = 1  # c_unit(1)
'''
The uCode parameter is a scan code and is translated into a virtual-key code
that does not distinguish between left- and right-hand keys.
If there is no translation, the function returns 0.
'''
_MAPVK_VK_TO_CHAR: Literal[2] = 2  # c_unit(2)
'''
The uCode parameter is a virtual-key code and is translated into an unshifted
character value in the low order word of the return value. Dead keys
(diacritics) are indicated by setting the top bit of the return value.
If there is no translation, the function returns 0.
'''
_MAPVK_VSC_TO_VK_EX: Literal[3] = 3  # c_unit(3)
'''
The uCode parameter is a scan code and is translated into a virtual-key code
that distinguishes between left- and right-hand keys.
If there is no translation, the function returns 0.
'''
_MAPVK_VK_TO_VSC_EX: Literal[4] = 4  # c_unit(4)
'''
Windows Vista and later: The uCode parameter is a virtual-key code and is
translated into a scan code. If it is a virtual-key code that does not
distinguish between left- and right-hand keys, the left-hand scan code is
returned. If the scan code is an extended scan code, the high byte of the uCode
value can contain either 0xe0 or 0xe1 to specify the extended scan code.
If there is no translation, the function returns 0.
'''

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

# GetSystemMetrics nIndex arguments
_SM_CXSCREEN: Literal[0] = 0
'''
The width of the screen of the primary display monitor, in pixels. This is the
same value obtained by calling GetDeviceCaps[1] as follows:
`GetDeviceCaps(hdcPrimaryMonitor, HORZRES)`.

[1] https://docs.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-getdevicecaps
'''
_SM_CYSCREEN: Literal[1] = 1
'''
The height of the screen of the primary display monitor, in pixels. This is the
same value obtained by calling GetDeviceCaps[1] as follows:
`GetDeviceCaps(hdcPrimaryMonitor, VERTRES)`.

[1] https://docs.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-getdevicecaps
'''


# struct translation constants
_MOUSE_PRESS: Literal[0] = 0
_MOUSE_RELEASE: Literal[1] = 1
_MOUSE_CLICK: Literal[2] = 2


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
_MOUSE_MAPPING_EVENTF: dict[str, tuple[int, int, int]] = {
    MOUSE_PRIMARY: _MOUSEEVENTF_LEFT,
    MOUSE_LEFT: _MOUSEEVENTF_LEFT,
    MOUSE_MIDDLE: _MOUSEEVENTF_MIDDLE,
    MOUSE_SECONDARY: _MOUSEEVENTF_RIGHT,
    MOUSE_RIGHT: _MOUSEEVENTF_RIGHT,
    MOUSE_BUTTON4: _MOUSEEVENTF_X,
    MOUSE_X1: _MOUSEEVENTF_X,
    MOUSE_BUTTON5: _MOUSEEVENTF_X,
    MOUSE_X2: _MOUSEEVENTF_X,
}
_MOUSE_MAPPING_DATA: dict[str, int] = {
    MOUSE_PRIMARY: 0,
    MOUSE_LEFT: 0,
    MOUSE_MIDDLE: 0,
    MOUSE_SECONDARY: 0,
    MOUSE_RIGHT: 0,
    MOUSE_BUTTON4: _XBUTTON1,
    MOUSE_X1: _XBUTTON1,
    MOUSE_BUTTON5: _XBUTTON2,
    MOUSE_X2: _XBUTTON2,
}


# ==============================================================================
# ===== C struct redefinitions =================================================
# ==============================================================================
_PUL_PyType: TypeAlias = type[_POINTER_TYPE[c_ulong]]
_PUL: _PUL_PyType = POINTER(c_ulong)


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
    dwExtraInfo: _POINTER_TYPE[c_ulong]
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
    dwExtraInfo: _POINTER_TYPE[c_ulong]
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


# ==============================================================================
# ===== C struct factory functions =============================================
# ==============================================================================
def _create_mouse_input(
    dx: int = 0,         # c_long
    dy: int = 0,         # c_long
    mouseData: int = 0,  # c_ulong
    dwFlags: int = 0,    # c_ulong
    time: int = 0,       # c_ulong
) -> _INPUT:
    '''Create INPUT structure for mouse input'''
    dwExtraInfo = c_ulong(0)
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


def _create_keyboard_input(
    wVk: int = 0,      # c_ushort
    wScan: int = 0,    # c_ushort
    dwFlags: int = 0,  # c_ulong
    time: int = 0      # c_ulong
) -> _INPUT:
    '''Create INPUT structure for keyboard input'''
    dwExtraInfo = c_ulong(0)
    input_struct = _INPUT(_INPUT_KEYBOARD)
    input_struct.ki = _KEYBDINPUT(
        wVk,
        wScan,
        dwFlags,
        time,
        pointer(dwExtraInfo)
    )
    return input_struct


def _create_hardware_input(  # pyright: ignore[reportUnusedFunction]
    uMsg: int = 0,     # c_ulong
    wParamL: int = 0,  # c_short
    wParamH: int = 0   # c_ushort
) -> _INPUT:
    '''Create INPUT structure for hardware input'''
    input_struct = _INPUT(_INPUT_HARDWARE)
    input_struct.hi = _HARDWAREINPUT(
        uMsg,
        wParamL,
        wParamH
    )
    return input_struct


# ==============================================================================
# ==== User32 functions ========================================================
# ==============================================================================
_user32 = windll.user32


# ----- SendInput --------------------------------------------------------------
class _SendInputType(Protocol):
    argtypes: tuple[type[c_uint], type[_POINTER_TYPE[_INPUT]], type[c_int]]
    restype: type[c_uint]

    def __call__(
        self,
        cInputs: c_uint | int,
        pInputs: _POINTER_TYPE[_INPUT] | _INPUT | Array[_INPUT],
        cbSize: c_int | int
    ) -> int:
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
    cbSize: c_int = c_int(sizeof(inputs_array))
    # execute function
    # inputs_array will be automatically be referenced by pointer
    return _SendInput(cInputs, inputs_array, cbSize)


# ----- MapVirtualKeyW ---------------------------------------------------------
class _MapVirtualKeyWType(Protocol):
    argtypes: tuple[type[c_uint], type[c_uint]]
    restype: type[c_uint]

    def __call__(
        self,
        uCode: c_uint | int,
        uMapType: c_uint | int
    ) -> int:
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
    uMapType: Literal[0, 1, 2, 3]
) -> int:
    '''
    Abstraction layer over MapVirtualKeyW (winuser.h)

    See https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-mapvirtualkeyw
    '''
    return _MapVirtualKeyW(c_uint(uCode), c_uint(uMapType))


# ----- GetSystemMetrics -------------------------------------------------------
class _GetSystemMetricsType(Protocol):
    argtypes: tuple[type[c_int]]
    restype: type[c_int]

    def __call__(
        self,
        nIndex: c_int | int,
    ) -> int:
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

    See https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getsystemmetrics
    '''
    return _GetSystemMetrics(nIndex)


# ----- GetCursorPos -----------------------------------------------------------
class _GetCursorPosType(Protocol):
    argtypes: tuple[type[_POINTER_TYPE[_POINT]]]
    restype: type[c_bool]

    def __call__(
        self,
        lpPoint: _POINTER_TYPE[_POINT] | _POINT
    ) -> int:
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


# ==============================================================================
# ===== Keyboard Scan Code Mappings ============================================
# ==============================================================================

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
    'up': _map_virtual_key(0x26, _MAPVK_VK_TO_VSC),
    'left': _map_virtual_key(0x25, _MAPVK_VK_TO_VSC),
    'down': _map_virtual_key(0x28, _MAPVK_VK_TO_VSC),
    'right': _map_virtual_key(0x27, _MAPVK_VK_TO_VSC),
}


# ==============================================================================
# ===== Fail Safe and Pause implementation =====================================
# ==============================================================================

class FailSafeException(Exception):
    pass


def _failSafeCheck() -> None:
    if FAILSAFE and tuple(_position()) in FAILSAFE_POINTS:
        raise FailSafeException(
            "PyDirectInput fail-safe triggered from mouse moving to a corner "
            "of the screen. "
            "To disable this fail-safe, set pydirectinput.FAILSAFE to False. "
            "DISABLING FAIL-SAFE IS NOT RECOMMENDED."
        )


def _handlePause(_pause: Any) -> None:
    '''
    Pause the default amount of time if `_pause=True` in function arguments.
    '''
    if _pause:
        assert isinstance(PAUSE, int) or isinstance(PAUSE, float)
        time.sleep(PAUSE)


RT = TypeVar('RT')  # return type


# direct copy of _genericPyAutoGUIChecks()
def _genericPyDirectInputChecks(
    wrappedFunction: Callable[..., RT]
) -> Callable[..., RT]:
    '''Decorator for wrapping input functions'''
    @functools.wraps(wrappedFunction)
    def wrapper(*args: Any, **kwargs: Any):
        funcArgs = inspect.getcallargs(wrappedFunction, *args, **kwargs)
        _failSafeCheck()
        returnVal = wrappedFunction(*args, **kwargs)
        _handlePause(funcArgs.get("_pause"))
        return returnVal
    return wrapper


# ==============================================================================
# ===== Helper Functions =======================================================
# ==============================================================================

def _to_windows_coordinates(x: int = 0, y: int = 0) -> tuple[int, int]:
    '''
    Convert x,y coordinates to windows form and return as tuple (x, y).
    '''
    display_width, display_height = _size()

    # the +1 here prevents exactly mouse movements from sometimes ending up
    # off by 1 pixel
    windows_x = (x * 65536) // display_width + 1
    windows_y = (y * 65536) // display_height + 1

    return windows_x, windows_y


# position() works exactly the same as PyAutoGUI.
# I've duplicated it here so that moveRel() can use it to calculate
# relative mouse positions.
def _position(x: int | None = None, y: int | None = None) -> tuple[int, int]:
    '''
    Return the current mouse position as tuple (x, y).
    '''
    cursor = _get_cursor_pos()
    return (x if x else cursor.x, y if y else cursor.y)


# size() works exactly the same as PyAutoGUI.
# I've duplicated it here so that _to_windows_coordinates() can use it
# to calculate the window size.
def _size() -> tuple[int, int]:
    '''
    Return the display size as tuple (x, y).
    '''
    return (
        _get_system_metrics(_SM_CXSCREEN),
        _get_system_metrics(_SM_CYSCREEN)
    )


def _get_mouse_struct_data(
    button: str,
    method: Literal[0, 1, 2]
) -> tuple[int | None, int]:
    '''Translate a button string to INPUT struct data'''
    if not (0 <= method <= 2):
        raise ValueError(f"method index {method} is not a valid argument!")
    event_value: int | None
    event_value = _MOUSE_MAPPING_EVENTF.get(button, (None, None, None))[method]
    mouseData: int = _MOUSE_MAPPING_DATA.get(button, 0)
    return event_value, mouseData


# ==============================================================================
# ===== Main Mouse Functions ===================================================
# ==============================================================================

# Ignored parameters: duration, tween, logScreenshot
@_genericPyDirectInputChecks
def mouseDown(
    x: int | None = None,
    y: int | None = None,
    button: str = MOUSE_PRIMARY,
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

    event_value: int | None = None
    mouseData: int
    event_value, mouseData = _get_mouse_struct_data(button, _MOUSE_PRESS)

    if not event_value:
        raise ValueError(
            'button arg to _click() must be one of "left", "middle", or '
            f'"right", not {button}'
        )

    input_struct = _create_mouse_input(mouseData=mouseData, dwFlags=event_value)

    _send_input(input_struct)


# Ignored parameters: duration, tween, logScreenshot
@_genericPyDirectInputChecks
def mouseUp(
    x: int | None = None,
    y: int | None = None,
    button: str = MOUSE_PRIMARY,
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

    event_value: int | None = None
    mouseData: int
    event_value, mouseData = _get_mouse_struct_data(button, _MOUSE_RELEASE)

    if not event_value:
        raise ValueError(
            'button arg to _click() must be one of "left", "middle", or '
            f'"right", not {button}'
        )

    input_struct = _create_mouse_input(mouseData=mouseData, dwFlags=event_value)

    _send_input(input_struct)


# Ignored parameters: duration, tween, logScreenshot
@_genericPyDirectInputChecks
def click(
    x: int | None = None,
    y: int | None = None,
    clicks: int = 1,
    interval: float = 0.0,
    button: str = MOUSE_PRIMARY,
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

    event_value: int | None = None
    mouseData: int
    event_value, mouseData = _get_mouse_struct_data(button, _MOUSE_CLICK)

    if not event_value:
        raise ValueError(
            'button arg to _click() must be one of "left", "middle", or '
            f'"right", not {button}'
        )

    for _ in range(clicks):
        _failSafeCheck()

        input_struct = _create_mouse_input(mouseData=mouseData, dwFlags=event_value)

        _send_input(input_struct)
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
    click(x, y, 1, interval, MOUSE_LEFT, duration, tween, logScreenshot, _pause)


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
    click(x, y, 1, interval, MOUSE_RIGHT, duration, tween, logScreenshot, _pause)


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
    click(x, y, 1, interval, MOUSE_MIDDLE, duration, tween, logScreenshot, _pause)


def doubleClick(
    x: int | None = None,
    y: int | None = None,
    interval: float = 0.0,
    button: str = MOUSE_LEFT,
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
    button: str = MOUSE_LEFT,
    duration: float = 0.0,
    tween: None = None,
    logScreenshot: bool = False,
    _pause: bool = True,
) -> None:
    '''
    Triple click `button`.
    '''
    click(x, y, 3, interval, button, duration, tween, logScreenshot, _pause)


# Originally implemented by
# https://github.com/learncodebygaming/pydirectinput/pull/22
# A negative number of clicks will scroll down and a positive number will
# scroll up
@_genericPyDirectInputChecks
def scroll(clicks: int = 0, interval: float = 0) -> None:
    '''
    Mouse scroll `clicks` number of times, waiting `interval` seconds between
    every scroll.
    '''
    direction: Literal[-1, 1]
    if clicks >= 0:
        direction = 1
    else:
        direction = -1
        clicks = abs(clicks)

    for _ in range(clicks):
        input_struct = _create_mouse_input(
            mouseData=(direction * _WHEEL_DELTA),
            dwFlags=_MOUSEEVENTF_WHEEL
        )
        _send_input(input_struct)
        time.sleep(interval)


@_genericPyDirectInputChecks
def hscroll(clicks: int = 0, interval: float = 0) -> None:
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
        input_struct = _create_mouse_input(
            mouseData=(direction * _WHEEL_DELTA),
            dwFlags=_MOUSEEVENTF_HWHEEL
        )
        _send_input(input_struct)
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
        # if only x or y is provided, will keep the current position for the
        # other axis
        x, y = _to_windows_coordinates(*_position(x, y))
        input_struct = _create_mouse_input(
            dx=x, dy=y,
            dwFlags=(_MOUSEEVENTF_MOVE | _MOUSEEVENTF_ABSOLUTE)
        )
        _send_input(input_struct)
    else:
        currentX, currentY = _position()
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
    if xOffset is None:
        xOffset = 0
    if yOffset is None:
        yOffset = 0
    if not relative:
        x, y = _position()
        moveTo(x + xOffset, y + yOffset)
    else:
        # When using MOUSEEVENTF_MOVE for relative movement the results may be
        # inconsistent. "Relative mouse motion is subject to the effects of the
        # mouse speed and the two-mouse threshold values. A user sets these
        # three values with the Pointer Speed slider of the Control Panel's
        # Mouse Properties sheet. You can obtain and set these values using the
        # SystemParametersInfo function."
        # https://docs.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-mouseinput
        # https://stackoverflow.com/questions/50601200/pyhon-directinput-mouse-relative-moving-act-not-as-expected
        input_struct = _create_mouse_input(
            dx=xOffset, dy=yOffset,
            dwFlags=_MOUSEEVENTF_MOVE
        )
        _send_input(input_struct)


move = moveRel


# Missing feature: drag functions


# ==============================================================================
# ===== Keyboard Functions =====================================================
# ==============================================================================

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

    input_struct = _create_keyboard_input(
        wScan=hexKeyCode,
        dwFlags=keybdFlags
    )
    insertedEvents += _send_input(input_struct)

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

    input_struct = _create_keyboard_input(
        wScan=hexKeyCode,
        dwFlags=keybdFlags
    )

    # SendInput returns the number of event successfully inserted into
    # input stream
    # https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput#return-value
    insertedEvents += _send_input(input_struct)

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
            _failSafeCheck()
            downed = keyDown(k)
            upped = keyUp(k)
            # Count key press as complete if key was "downed" and "upped"
            # successfully
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
        _failSafeCheck()


write = typewrite


# Originally implemented by
# https://github.com/learncodebygaming/pydirectinput/pull/30
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
