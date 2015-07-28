#!/usr/bin/env python
#
# -*- mode:python; sh-basic-offset:4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim:set tabstop=4 softtabstop=4 expandtab shiftwidth=4 fileencoding=utf-8:
#

import setuptools


setuptools.setup(
    name='clusto-ec2',
    version='0.6.3',
    packages=setuptools.find_packages('src'),
    author='Ron Gorodetzky',
    author_email='ron@parktree.net',
    description='Amazon EC2 extension for clusto',
    install_requires=[
        'clusto>0.6',
        'boto>=2.0',
        'mako',
    ],
    entry_points={
        'console_scripts': [
            'clusto-ec2 = clustoec2.commands.ec2:main',
            'clusto-vpc = clustoec2.commands.vpc:main',
            'clusto-ec2-bootstrap = clustoec2.commands.bootstrap:main',
        ],
    },
    zip_safe=False,
    package_dir={
        '': 'src',
    },
)
