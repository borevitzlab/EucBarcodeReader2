#!/usr/bin/env python3
from setuptools import setup

desc = """euc-sampling-helpers: code assisting eucalyptus sampling"""

install_requires = [
    "docopt",
    "exifread",
    "numpy",
    "pillow",
    "tqdm",
    "zbarlight",
]

test_requires = [
]

setup(
    name="euc-sampling-helpers",
    scripts=[
        "envelope-demuxer.py",
        "tissue-sampler.py",
    ],
    version="0.1.0",
    install_requires=install_requires,
    tests_require=test_requires,
    description=desc,
    author="Kevin Murray",
    author_email="foss@kdmurray.id.au",
    url="https://github.com/borevitzlab/euc-sampling-helpers",
    keywords=["eucalyptus"],
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
    ],
)
