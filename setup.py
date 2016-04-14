from distutils.core import setup
from pkgutil import walk_packages

import glob
import sys
import os

data_files = [ 
        (sys.prefix + '/pdusim/' + 'variation',glob.glob(os.path.join('variation', '*.py'))) 
]

for x in os.walk('snmpdata'):
    data_files.append(
            (sys.prefix + '/pdusim/' + '/'.join(os.path.split(x[0])),
            glob.glob(os.path.join(x[0], '*.snmprec')) + \
            glob.glob(os.path.join(x[0], '*.db')))
    )

for x in os.walk('conf'):
    data_files.append(
            (sys.prefix + '/pdusim/' + '/'.join(os.path.split(x[0])),
            glob.glob(os.path.join(x[0], '*')))
    )

for x in os.walk('third-party'):
    data_files.append(
            (sys.prefix + '/pdusim/' + '/'.join(os.path.split(x[0])),
            glob.glob(os.path.join(x[0], '*.py')) + \
            glob.glob(os.path.join(x[0], 'LICENSE')) + \
            glob.glob(os.path.join(x[0], 'Makefile')) + \
            glob.glob(os.path.join(x[0], '*.cfg')) + \
            glob.glob(os.path.join(x[0], '*.rst')) + \
            glob.glob(os.path.join(x[0], '*.bat')) + \
            glob.glob(os.path.join(x[0], 'README*'))
            )
    )

setup(
        name = "vpduserv",
        version = "0.1",
        author = "robert",
        author_email = "robert.xia@emc.com",
        url = "https://github.com/InfraSIM/vpduserv.git",
        packages = ["pdusim", "pdusim/common"],
        platforms = "Linux",
        classifiers = [
            "Intended Audience :: Developers",
            "Operating System :: Linux",
            "Programming Language :: Python",
            "Programming Language :: Python :: 2.6",
            "Programming Language :: Python :: 2.7",
        ],
        scripts = ["vpdud.py", "server.py"],
        data_files = data_files,
)
