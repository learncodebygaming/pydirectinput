# PyDirectInput

This library aims to replicate the functionality of the PyAutoGUI mouse and keyboard inputs, but by utilizing DirectInput scan codes and the more modern SendInput() win32 function. PyAutoGUI uses Virtual Key Codes (VKs) and the deprecated mouse_event() and keybd_event() win32 functions. You may find that PyAutoGUI does not work in some applications, particularly in video games and other software that rely on DirectX. If you find yourself in that situation, give this library a try!

`pip install pydirectinput`

This package is intended to be used in conjunction with PyAutoGUI. You can continue to use PyAutoGUI for all of its cool features and simply substitute in PyDirectInput for the inputs that aren't working. The function interfaces are the same, but this package may not implement all optional parameters and features.

Want to see a missing feature implemented? Why not give it a try yourself! I welcome all pull requests and will be happy to work with you to get a solution fleshed out. Get involved in open source! Learn more about programming! Pad your resume! Have fun!

Source code available at https://github.com/learncodebygaming/pydirectinput

Watch the tutorial here: https://www.youtube.com/watch?v=LFDGgFRqVIs

## Example Usage

```python
    >>> import pyautogui
    >>> import pydirectinput
    >>> pydirectinput.moveTo(100, 150) # Move the mouse to the x, y coordinates 100, 150.
    >>> pydirectinput.click() # Click the mouse at its current location.
    >>> pydirectinput.click(200, 220) # Click the mouse at the x, y coordinates 200, 220.
    >>> pydirectinput.move(None, 10)  # Move mouse 10 pixels down, that is, move the mouse relative to its current position.
    >>> pydirectinput.doubleClick() # Double click the mouse at the
    >>> pydirectinput.press('esc') # Simulate pressing the Escape key.
    >>> pydirectinput.keyDown('shift')
    >>> pydirectinput.keyUp('shift')
```

## Documentation

The DirectInput key codes can be found by following the breadcrumbs in the documentation here: https://docs.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-input

You might also be interested in the main SendInput documentation here: https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput

You can find a discussion of the problems with using vkCodes in video games here: https://stackoverflow.com/questions/14489013/simulate-python-keypresses-for-controlling-a-game

## Testing

To run the supplied tests: first setup a virtualenv. Then you can pip install this project in an editable state by doing `pip install -e .`. This allows any edits you make to these project files to be reflected when you run the tests. Run the test file with `python3 tests`.

I have been testing with Half-Life 2 to confirm that these inputs work with DirectX games.

## Features Implemented

- Fail Safe Check
- Pause
- position()
- size()
- moveTo(x, y)
- move(x, y) / moveRel(x, y)
- mouseDown()
- mouseUp()
- click()
- keyDown()
- keyUp()
- press()
- write() / typewrite()

## Features NOT Implemented

- scroll functions
- drag functions
- hotkey functions
- support for special characters requiring the shift key (ie. '!', '@', '#'...)
- ignored parameters on mouse functions: duration, tween, logScreenshot
- ignored parameters on keyboard functions: logScreenshot
