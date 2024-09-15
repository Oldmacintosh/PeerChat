# -*- coding: utf-8 -*-
r"""
This module configures kivy settings like window height, width, logger
path,etc.
Settings, Logs, app data are stored in the following path:
"C:\\Users\\<UserName>\\AppData\Local\\<Project Name>"
This folder is created, and data is stored in it as after compilation
of the application the home directory (Program Files Folder), it is not
easily writable.
"""

import os
import configparser
import logging
import main  # noqa
from tblib import pickling_support

# Create the necessary folders
for folder in [main.main_dir, main.data_dir]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Important to set the KIVY_HOME environment variable before importing
# kivy modules
os.environ['KIVY_HOME'] = main.main_dir

from kivy.logger import Logger  # noqa PEP 8: E402
from kivy.config import Config  # noqa PEP 8: E402

pickling_support.install()
logging.getLogger().setLevel(logging.INFO)

MIN_HEIGHT: str = '650'
MIN_WIDTH: str = '850'
DEFAULT: bool = False

while True:
    try:
        # If debug mode is on, we explicitly raise a ValueError to
        # write the default settings to the config file
        if main.__DEBUG__:
            if not DEFAULT:
                DEFAULT = True
                raise ValueError

        max_processes = int(Config.get('app', 'max_processes'))

        # Perform settings check before proceeding
        assert 0 <= max_processes <= 5

        Logger.info('kivy_config: Kivy successfully configured.')
        break
    except (configparser.NoSectionError, configparser.NoOptionError,
            ValueError, TypeError, AssertionError):
        Logger.info('kivy_config: Writing default settings to config file')
        log_name = f'%H-%M-%S_{main.__PROJECT__.lower()}_%y-%m-%d_%_.txt'
        if not log_name == Config.get('kivy', 'log_name'):
            Config.set('kivy', 'log_name', log_name)
        Config.set('kivy', 'window_icon', r'dependencies\icons\Icon.png')
        Config.set('kivy', 'exit_on_escape', '0')
        Config.set('kivy', 'log_maxfiles', '25')
        Config.set('graphics', 'height', '650')
        Config.set('graphics', 'width', '850')
        Config.set('graphics', 'minimum_height', MIN_HEIGHT)
        Config.set('graphics', 'minimum_width', MIN_WIDTH)
        Config.set('input', 'mouse', 'mouse,disable_multitouch')
        # Add extra settings for the application
        try:
            Config.add_section('server')
            Config.add_section('app')
        except configparser.DuplicateSectionError:
            pass
        Config.set('server', 'host', main.HOST)
        Config.set('server', 'port', main.PORT)
        Config.set('app', 'max_processes', main.MAX_PROCESSES)
        Config.write()
