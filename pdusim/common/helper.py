# This script contains useful functions
import sys
import os

install_data_dir = [
    os.path.join(os.environ['HOME'], '.pdusim'),
    os.path.join(sys.prefix, 'pdusim'),
    os.path.join(sys.prefix, 'share', 'pdusim'),
    os.path.join(os.path.split(__file__)[0], 'pdusim'),
    os.path.dirname(os.path.abspath(__file__))
]


def get_install_dir():
    configdir_found = False
    for dir in install_data_dir:
        path = os.path.join(dir, 'conf', 'host.conf')
        if os.path.exists(path):
            return dir
    if not configdir_found:
        return None


def add_third_party_to_path():
    for dir in install_data_dir:
        path = os.path.join(dir, 'third-party')
        if os.path.exists(path):
            for d in os.listdir(path):
                sys.path.insert(0, os.path.join(path, d))