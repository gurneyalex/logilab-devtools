#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2003-2008 LOGILAB S.A. (Paris, FRANCE).
# http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
"""command line wrapper for lib.changelog"""

import sys
import getopt

from logilab.devtools.lib import changelog


USAGE = """%s
USAGE: changelog [OPTIONS] [COMMAND] [COMMAND_ARGS]

OPTIONS:
  --help
    display this help message
  --package-dir <dir>
    base directory of the package
  --new
    create a new entry if no current entry found 
  --debian
    act on a debian change log (debian/changelog) instead of an upstream
    changelog (ChangeLog)
   
COMMAND COMMANDS_ARGS
  extract [release]
    extract messages for a given release. If no release is given, get
    messages for the latest entry.
    
  lastrev
    retreive the latest version released
    
  add <message>
    add a message to the current entry
    
  update
    update the change log by fectching log entries from cvs

  close
    close the current entry (version is read from the package
    __pkginfo__.py file)
""" % changelog.__doc__
    
def run(args):
    """main"""
    # read option
    l_opt = ['package-dir=', 'new', 'debian', 'help']
    (opts, args) = getopt.getopt(args, 'h', l_opt)
    pkg_dir = None
    create = None
    debian = False
    for name, value in opts:
        if name == ('--pkg-dir', '-p'):
            pkg_dir = value
        elif name in ('--new', '-n'):
            create = True
        elif name in ('--debian', '-d'):
            debian = True
        elif name in ('--help', '-h'):
            print USAGE
            sys.exit(0)
    if not args:
        print USAGE
        sys.exit(1)
    if debian:
        chlogfile = changelog.find_debian_changelog(pkg_dir)
        chlg = changelog.DebianChangeLog(chlogfile)
    else:
        chlogfile = changelog.find_ChangeLog(pkg_dir)
        chlg = changelog.ChangeLog(chlogfile)
    
    if args[0] == 'extract':
        if len(args) == 2:
            arg = args[1]
        else:
            arg = ''
        chlg.extract(arg)
    elif args[0] == 'lastrev':
        print chlg.get_latest_revision()
    elif args[0] == 'update':
        chlg.update(create)
        chlg.save()
    elif args[0] == 'add':
        assert args[1]
        chlg.add(' '.join(args[1:]), create)
        chlg.save()
    elif args[0] == 'close':
        chlg.close(pkg_dir, create)
        chlg.save()
    else:
        print USAGE
        sys.exit(1)
    sys.exit(0)

if __name__ == '__main__':
    run(sys.argv[1:])
