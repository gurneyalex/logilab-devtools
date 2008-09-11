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
""" %prog build [options]

    Provides functions to build a debian package for a python package
    You can use a setup.cfg file with the [LGP-BUILD] section
"""
__docformat__ = "restructuredtext en"

KNOWN_DISTRIBUTIONS = ('etch', 'lenny', 'stable', 'unstable', 'experimental', 'sid')

import os
import sys
import stat
import tempfile
import shutil
import logging
import os.path as osp
from subprocess import Popen, PIPE

from logilab.common.shellutils import mv
from logilab.common.fileutils import ensure_fs_mode, export

from logilab.devtools.lgp.exceptions import (ArchitectureException,
                                             DistributionException)
from logilab.devtools.lgp.utils import confirm, cond_exec
from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.changelog import DebianChangeLog


def get_distributions(distrib='sid'):
    """ Ensure that the target distributions exist

        :param:
            distrib: str or list
                name of a distribution
        :return:
            list of target distribution
    """
    if distrib == 'all':
        distrib = KNOWN_DISTRIBUTIONS
    else:
        if type(distrib) is str:
            distrib = distrib.split(',')
        for t in distrib:
            if t not in KNOWN_DISTRIBUTIONS:
                raise DistributionException(t)
    return distrib

def get_architectures(archi="current"):
    """ Ensure that the architectures exist

        :param:
            archi: str or list
                name of a architecture
        :return:
            list of architecture
    """
    known_archi = Popen(["dpkg-architecture", "-L"], stdout=PIPE).communicate()[0].split()
    if archi == "current":
        archi = Popen(["dpkg", "--print-architecture"], stdout=PIPE).communicate()[0].split()
    else:
        if archi == "all":
            return archi
        if type(archi) is str:
            archi = archi.split(',')
        for a in archi:
            if a not in known_archi:
                raise ArchitectureException(a)
    return archi

def run(args):
    """ Main function of lgp build command """
    builder = Builder(args)
    try :
        distributions = get_distributions(builder.config.distrib)
        architectures = get_architectures(builder.config.archi)

        if builder.config.revision :
            logging.critical(Popen(["hg", "update", builder.config.revision], stderr=PIPE).communicate())

        for arch in architectures:
            for distrib in distributions:
                packages = builder.compile(distrib=distrib, arch=arch)
                run_checkers(packages, builder.get_distrib_dir(),
                             not builder.config.verbose)
    except Exception, exc:
        logging.error(exc)
        return 1

def run_checkers(packages, distdir, quiet=True):
    """ Run common used checkers with Debian """
    separator = '+' * 15 + ' %s'
    # Run usual checkers
    checkers = ('lintian', 'linda')
    for checker in checkers:
        if quiet or confirm("run %s on generated debian packages ?" % checker):
            for package in packages:
                print separator % package
                if not package.endswith('.diff.gz'):
                    cond_exec('%s -i %s/%s' % (checker, distdir, package))

    # FIXME piuparts that doesn't work automatically for all of our packages
    if not quiet and confirm("run piuparts on generated debian packages ?"):
        for package in packages:
            print separator % package
            if package.endswith('.deb'):
                cond_exec('sudo piuparts -p %s/%s' % (distdir, package))

class Builder(SetupInfo):
    """ Debian builder class

    Specific options are added. See lgp build --help
    """
    name = "lgp-build"
    options = (('dist',
                {'type': 'string',
                 #'default' : osp.expanduser('~/dist'),
                 'dest' : "dist_dir",
                 'metavar': "<directory>",
                 'help': "where to put compilation results"
                }),
               ('distrib',
                {'type': 'choice',
                 'choices': KNOWN_DISTRIBUTIONS,
                 'dest': 'distrib',
                 #'default' : 'sid',
                 'metavar' : "<distribution>",
                 'help': "the distribution targetted (e.g. etch, lenny, sid). Use 'all' for all known distributions"
                }),
               ('arch',
                {'type': 'string',
                 'dest': 'archi',
                 #'default' : 'current',
                 'metavar' : "<architecture>",
                 'help': "build for the requested debian architectures only"
                }),
               ('orig-tarball',
                {'type': 'string',
                 'default' : None,
                 'dest': 'orig_tarball',
                 'metavar' : "<tarball>",
                 'help': "path to orig.tar.gz file"
                }),
              ),

    def __init__(self, *args):
        # Retrieve upstream information
        super(Builder, self).__init__(options=self.options, usage=__doc__)
        # FIXME
        self.load_file_configuration('./setup.cfg')
        args = self.load_command_line_configuration(*args)
        if self.config.pkg_dir is None:
            self.config.pkg_dir = osp.abspath(args and args[0] or os.getcwd())

        # FIXME logilab.common.configuration doesn't like default values :-(
        # Be sure to have absolute path here
        if self.config.orig_tarball is not None:
            self.config.orig_tarball = osp.abspath(osp.expanduser(self.config.orig_tarball))
        if self.config.dist_dir is None:
            self.config.dist_dir = osp.expanduser("~/dist")
        else:
            self.config.dist_dir = osp.abspath(self.config.dist_dir)
        if self.config.archi is None:
            self.config.archi = 'current'
        if self.config.distrib is None:
            self.config.distrib = 'sid'

        # check if distribution directory exists, create it if necessary
        try:
            os.makedirs(self.get_distrib_dir())
        except OSError:
            # it's not a problem here to pass silently # when the directory
            # already exists
            pass

    def compile(self, distrib, arch):
        # Go to package directory
        os.chdir(self.config.pkg_dir)

        tmpdir = tempfile.mkdtemp()

        # the upstream archive tarball is depending of the setup method
        tarball = self.create_orig_tarball(tmpdir)

        # create tmp build directory by extracting the .orig.tar.gz
        os.chdir(tmpdir)
        logging.debug("Extracting %s..." % tarball)
        status = os.system('tar xzf %s' % tarball)
        if status:
            raise IOError('An error occured while extracting the upstream '\
                          'tarball (return status: %s)' % status)

        # origpath is depending of the upstream convention
        origpath = tarball.rsplit('.orig.tar.gz')[0].replace('_', '-')

        # copying debian_dir directory into tmp build depending of the target distribution
        # in all cases, we copy the debian directory of the sid version
        # DOC If a file should not be included, touch an empty file in the overlay directory
        if distrib != 'sid':
            shutil.copytree(osp.join(self.config.pkg_dir, 'debian'), osp.join(origpath, 'debian'))
        shutil.copytree(osp.join(self.config.pkg_dir, self.get_debian_dir()), osp.join(origpath, 'debian'))

        # build the package using vbuild or default to fakeroot
        debuilder = os.environ.get('DEBUILDER') or 'vbuild'
        if debuilder ==  'vbuild':
            self.make_source_package(origpath)
            dscfile = '%s_%s.dsc' % (self.get_debian_name(), self.get_debian_version())
            logging.info("Building debian for distribution '%s' and arch '%s'" % (distrib,
                                                                                  arch))
            cmd = 'vbuild -d %s -a %s --result %s %s'
            cmd %= (distrib, arch, self.get_distrib_dir(), osp.join(tmpdir, dscfile))
            # TODO
            #cmd += ' --debbuildopts %s' % pdebuild_options
        else:
            cmd = debuilder
        if not self.config.verbose:
            cmd += ' 1>/dev/null 2>/dev/null'
        logging.debug("[VBUILD] " + ''.join(cmd))
        status = os.system(cmd)
        if status:
            raise OSError('An error occured while building the debian package ' \
                          '(return status: %s)' % status)
        # clean tmpdir
        shutil.rmtree(tmpdir)
        return self.get_packages()

    def get_debian_dir(self):
        """ get the dynamic debian directory for the configuration override

        The convention is :
        - 'debian/' is for sid distribution
        - 'debian.$OTHER' id for $OTHER distribution
        """
        if self.config.distrib == 'sid':
            return 'debian/'
        else:
            return 'debian.%s/' % self.config.distrib

    def get_debian_version(self):
        """ get the debian version depending of the last changelog entry

            Format of Debian package: <sourcepackage>_<upstreamversion>-<debian_version>
        """
        debian_version = DebianChangeLog('%s/%s/changelog' % 
                (self.config.pkg_dir, self.get_debian_dir())).get_latest_revision()
        if debian_version.debian_version != '1' and self.config.orig_tarball is None:
            raise ValueError('unable to build %s %s: --orig-tarball option is required when '\
                             'not building the first version of the debian package'
                             % (self.get_debian_name(), self.get_debian_version()))
        return debian_version

    def get_distrib_dir(self):
        """ get the dynamic target release directory """
        return osp.join(self.config.dist_dir, self.config.distrib)

    def make_source_package(self, origpath):
        """create a debian source package

        This function must be called inside an unpacked source
        package. The source package (dsc and diff.gz files) is created in
        the parent directory.

        :param:
            origpath: path to orig.tar.gz tarball
        """
        logging.info("Creation of the Debian source package: %s" % origpath)
        cmd = 'dpkg-source -b %s' % origpath
        if not self.config.verbose:
                cmd += ' 1>/dev/null 2>/dev/null'
        os.system(cmd)