#!/usr/bin/env python
# -*- mode: python; sh-basic-offset: 4; indent-tabs-mode: nil; coding: utf-8 -*-
# vim: tabstop=4 softtabstop=4 expandtab shiftwidth=4 fileencoding=utf-8
#

import os
import setuptools
import sys


setuptools.setup(
    name = "clusto-ec2",
    version = "0.4.5",
    packages = setuptools.find_packages('src'),
    author = "Ron Gorodetzky",
    author_email = "ron@parktree.net",
    description = "Amazon EC2 extension for clusto",
    install_requires = [
        'clusto>0.6',
        'boto>=2.0',
        'mako',
    ],
    entry_points = {
        'console_scripts': [
        ],
    },
    zip_safe = False,
    package_dir = { '': 'src' },
)

