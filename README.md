# pydirectinput_rgx

This library is a fork of https://github.com/learncodebygaming/pydirectinput

Changes to the fork include:

* Adding/fixing extended key codes
* Adding flake8 linting
* Adding mypy type hinting and adding annotations (**This makes this fork Python >=3.10 only!**)
* Adding scroll functions based on https://github.com/learncodebygaming/pydirectinput/pull/22 and improve them
* Adding hotkey functions based on https://github.com/learncodebygaming/pydirectinput/pull/30 and improve them
* Adding more available keyboard keys
* Adding optional automatic shifting for certain keayboard keys in old down/up/press functions
* Adding additional arguments for tighter timing control for press and typewrite functinos
* Adding Unicode input functions that allow sending text that couldn't be sent by simple keyboard
* Adding Scancode input functions that allow lower level access to SendInput's abstractions
* Adding support for multi-monitor setups via virtual resolution
* Adding support for swapped primary mouse buttons
* Increase documentation

**This library uses in-line type annotations that require at least Python version 3.10 or higher and there are no plans to make the code backwards compatible to older Python versions!**


## Features NOT YET Implemented

- ~~scroll functions~~
- ~~drag functions~~
- ~~hotkey functions~~
- ~~support for special characters requiring the shift key (ie. '!', '@', '#'...)~~
- ignored parameters on mouse functions: duration, tween, logScreenshot
- ignored parameters on keyboard functions: logScreenshot
- automatic testing

___

See the [old original README](OLD_README.md).

___