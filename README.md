# pydirectinput_rgx

This library is a fork of https://github.com/learncodebygaming/pydirectinput 1.0.4

This package extends PyDirectInput in multiple ways. It fixes some bugs, adds the remaining missing input functions that still required using PyAutoGUI and provides additional keyword-only arguments to give more precise control over function behavior.

Contrary to the upstream PyDirectInput package, this package intends to replace PyAutoGUI almost completely for basic usage, skipping more advanced options like logging screenshots and custom tweening functions. This should reduce the need to install both PyDirectInput and PyAutoGUI side-by-side and thereby keep the number of dependencies to a minimum.

This library is fully in-line type-annotated and passes `mypy --strict`. Unfortunately, that also means this package **only works on Python 3.7 or higher**. There are **no** plans to backport changes to older versions.

This is why this package is available standalone and uses the same package name. There's no reason to use both side-by-side. Once Python's type annotations have reached wider adoption, this package may be merged back and integrated upstream. Until that moment, this package exists to fill that gap.

## Okay, but what is PyDirectInput in the first place?

PyDirectInput exists because PyAutoGUI uses older and less compatible API functions.

In order to increase compatibility with DirectX software and games, the internals have been replaced with SendInput() and Scan Codes instead of Virtual Key Codes.

For more information, see the original README at https://github.com/learncodebygaming/pydirectinput


## Installation

`pip install pydirectinput-rgx`

## Provided functions with same/similar signature to PyAutoGui:

* Informational:
  - `position()`
  - `size()`
  - `onScreen()`
  - `isValidKey()`
* Mouse input:
  - `moveTo()`
  - `move()` / `moveRel()`
  - `mouseDown()`
  - `mouseUp()`
  - `click()` and derivatives:
    - `leftClick()`
    - `rightClick()`
    - `middleClick()`
    - `doubleClick()`
    - `tripleClick()`
  - `scroll()` / `vscroll()`
  - `hscroll()`
  - `dragTo()`
  - `drag()` / `dragRel()`
* Keyboard input:
  - `keyDown()`
  - `keyUp()`
  - `press()`
  - `hold()` (supports context manager)
  - `write()` / `typewrite()`
  - `hotkey()`


### Additionally, keyboard input has been extended with :
* low-level scancode_* functions that allow integer scancode as arguments:
  - `scancode_keyDown()`
  - `scancode_keyUp()`
  - `scancode_press()`
  - `scancode_hold()` (supports context manager)
  - `scancode_hotkey()`
* higher-level unicode_* functions that allow inserting Unicode characters into supported programs:
  - `unicode_charDown()`
  - `unicode_charUp()`
  - `unicode_press()`
  - `unicode_hold()` (supports context manager)
  - `unicode_write()` / `unicode_typewrite()`
  - `unicode_hotkey()`


## Missing features compared to PyAutoGUI

- `logScreenshot` arguments. No screenshots will be created.
- `tween` arguments. The tweening function is hardcoded at the moment.

___

### Changelog compared to forked origin point PyDirectInput version 1.0.4:

* Adding/fixing extended key codes
* Adding flake8 linting
* Adding mypy type hinting and adding annotations (**This makes this fork Python >=3.7 only!**)
* Adding scroll functions based on [learncodebygaming/PR #22](https://github.com/learncodebygaming/pydirectinput/pull/22) and improve them
* Adding hotkey functions based on [learncodebygaming/PR #30](https://github.com/learncodebygaming/pydirectinput/pull/30) and improve them
* Adding more available keyboard keys
* Adding optional automatic shifting for certain keayboard keys in old down/up/press functions
* Adding additional arguments for tighter timing control for press and typewrite functions
* Adding Unicode input functions that allow sending text that couldn't be sent by simple keyboard
* Adding Scancode input functions that allow lower level access to SendInput's abstractions
* Adding support for multi-monitor setups via virtual resolution (most functions should work without just fine)
* Adding support for swapped primary mouse buttons
* Adding duration support for mouse functions
* Adding sleep calibration for mouse duration
* Adding automatic disabling of mouse acceleration for more accurate relative mouse movement
* Increase documentation
* Improve performance of _genericPyDirectInputChecks decorator (Thanks Agade09 for [reggx/PR #1](https://github.com/ReggX/pydirectinput_rgx/pull/1))

**This library uses in-line type annotations that require at least Python version 3.7 or higher and there are no plans to make the code backwards compatible to older Python versions!**


___
See the [pydirectinput's original README](OLD_README.md).
___
