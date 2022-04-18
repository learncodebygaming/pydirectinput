import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pydirectinput_rgx",
    version="2.0.1",
    author="ReggX",
    author_email="dev@reggx.eu",
    description="Python mouse and keyboard input automation for Windows using Direct Input.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/reggx/pydirectinput_rgx",
    packages=['pydirectinput'],
    package_data={
        'pydirectinput': ['py.typed']
    },
    classifiers=[
        "Programming Language :: Python :: 3.10",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Environment :: Win32 (MS Windows)",
        "Topic :: Software Development :: Libraries",
        "Typing :: Typed",
    ],
    python_requires='>=3.10',
    license='MIT',
    keywords='python directinput wrapper abstraction input gui automation'
)
