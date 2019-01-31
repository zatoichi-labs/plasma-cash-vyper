#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup, find_packages


extras_require = {
    'test': [
        "pytest>=4.0.0",
        "pytest-ethereum>=0.1.3a4",
        "pytest-xdist",
        "tox>=2.6.0,<3",
        "hypothesis==3.7.0",
    ],
    'lint': [
        "flake8==3.4.1",
    ],
    'dev': [
        "bumpversion>=0.5.3,<1",
        "wheel",
        "twine",
    ],
}

extras_require['dev'] = (
    extras_require['dev'] +
    extras_require['test'] +
    extras_require['lint']
)

setup(
    name='plasma-cash',
    # *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
    version='0.1.0',
    description="""Python implementation of Plasma Cash. Contracts in Vyper.""",
    long_description_markdown_filename='README.md',
    author='@fubloubu',
    url='https://github.com/zatoichi-labs/plasma-cash-vyper',
    include_package_data=True,
    py_modules=['plasma_cash'],
    python_requires='>=3.5.3,<4',
    install_requires=[
        "eth-utils>=1.3.0,<2.0.0",
        "trie>=1.3.8,<2.0.0",
        "rlp>=1,<2",
        "web3>=4.8.1",
        "vyper>=0.1.0b6",
    ],
    extras_require=extras_require,
    license="MIT",
    zip_safe=False,
    keywords='ethereum blockchain plasma cash',
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        "Operating System :: OS Independent",
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Software Development',
    ],
)

