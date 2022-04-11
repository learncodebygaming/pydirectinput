import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pydirectinput_rgx",
    version="2.0.0",
    author="ReggX",
    author_email="dev@reggx.eu",
    description="Python mouse and keyboard input automation for Windows using Direct Input.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/reggx/pydirectinput",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
    ],
    python_requires='>=3.10',
)
