import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pydirectinput_rgx",
    version="2.0.6",
    author="ReggX",
    author_email="dev@reggx.eu",
    description=(
        "Python mouse and keyboard input automation for Windows using "
        "Direct Input."
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/reggx/pydirectinput_rgx",
    packages=['pydirectinput'],
    package_data={
        'pydirectinput': ['py.typed']
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Win32 (MS Windows)",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries",
        "Typing :: Typed",
    ],
    install_requires=[
        "typing-extensions>=4.2.0, <5.0; python_version < '3.9'"
    ],
    python_requires='>=3.7',
    license='MIT',
    keywords='python directinput wrapper abstraction input gui automation'
)
