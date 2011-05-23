# Copyright (c) 2003 Sylvain Thenault (thenault@gmail.com)
# Copyright (c) 2003-2008 Logilab (devel@logilab.fr)
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
"""miscellaneous utilities, mostly shared by package'checkers
"""

import glob
import sys
import time
import os.path as osp
import re
from subprocess import Popen, PIPE
import logging

from debian.deb822 import Deb822

from logilab.devtools.lgp import LGP_SUITES
from logilab.devtools.lgp.exceptions import (ArchitectureException,
                                             DistributionException,
                                             SetupException,
                                             LGPException)


def get_debian_name():
    """obtain the debian package name

    The information is found in debian/control withe the 'Source:' field
    """
    try:
        control = osp.join('debian', 'control')
        for line in open(control):
            line = line.split(' ', 1)
            if line[0] == "Source:":
                return line[1].rstrip()
    except IOError, err:
        raise LGPException('a Debian control file should exist in "%s"' % control)

def guess_debian_distribution():
    """guess the default debian distribution in debian/changelog

       Useful to determine a default distribution different from unstable if need
    """
    distribution = _parse_deb_distrib()
    logging.debug('retrieve default debian distribution from debian/changelog: %s'
                  % distribution)
    if distribution in ['experimental', 'UNRELEASED']:
        logging.warn("distribution '%s' should only be used for debugging purpose"
                     % distribution)
        return ["unstable",]
    return [distribution,]

def is_architecture_independent():
    return 'all' in get_debian_architecture()

def guess_debian_architecture():
    """guess debian architecture(s)
    """
    try:
        archi = get_debian_architecture()
        logging.debug('retrieve architecture field value from debian/control: %s'
                      % ','.join(archi))
    except LGPException:
        logging.debug('no debian/control available. will use "current" architecture')
        archi = ["current"]
    return archi

def get_architectures(archi=None, basetgz=None):
    """ Ensure that the architectures exist

        "all" keyword can be confusing about the targeted architectures.
        Consider using the "any" keyword to force the build on all
        architectures or let lgp find the value in debian/control by
        itself in doubt.

        lgp replaces "all" with "current" architecture value

        :param:
            archi: str or list
                name of a architecture
        :return:
            list of architecture
    """
    known_archi = Popen(["dpkg-architecture", "-L"], stdout=PIPE).communicate()[0].split()

    # try to guess targeted architectures
    if archi is None or len(archi)==0:
        archi = guess_debian_architecture()

    # "all" means architecture-independent. so we can replace by "current"
    # architecture only
    if 'all' in archi:
        archi = ['current']
    if 'current' in archi:
        archi = Popen(["dpkg", "--print-architecture"], stdout=PIPE).communicate()[0].split()
    else:
        if 'any' in archi:
            if not osp.isdir(basetgz):
                raise SetupException("default location '%s' for the archived "
                                     "chroot images was not found"
                                     % basetgz)
            try:
                archi = [osp.basename(f).split('-', 1)[1].split('.')[0]
                         for f in glob.glob(osp.join(basetgz,'*.tgz'))]
            except IndexError:
                raise SetupException("there is no available chroot images in default location '%s'"
                                     "\nPlease run 'lgp setup -c create'"
                                     % basetgz)
            archi = set(known_archi) & set(archi)
        for a in archi:
            if a not in known_archi:
                msg = "architecture '%s' not found in '%s' (create it or unreference it)"
                raise ArchitectureException(msg % (a, basetgz))
    return archi

def get_debian_architecture():
    """get debian architecture(s) to use in build

    The information is found in debian/control with the 'Architecture:' field
    """
    try:
        control = osp.join('debian', 'control')
        for line in open(control):
            line = line.split(' ', 1)
            if line[0] == "Architecture:":
                archi = line[1].rstrip().split(' ')
                if "source" in archi:
                    archi.pop('source')
                return archi
    except IOError, err:
        raise LGPException('a Debian control file should exist in "%s"' % control)

def get_distributions(distrib=None, basetgz=None, suites=LGP_SUITES):
    """ensure that the target distributions exist or return all the valid distributions

    param distrib: specified distrib
                   'all' to retrieved created distributions on filesystem
                   'None' to detect available images by cdebootstrap
    param basetgz: location of the pbuilder images
    """
    if distrib is None:
        import email
        distrib = email.message_from_file(file(suites))
        distrib = [i.split()[1] for i in distrib.get_payload().split('\n\n') if i]
    elif 'all' in distrib or len(distrib)==0:
        # this case fixes unittest_distributions.py when basetgz is None
        if basetgz is None:
            return get_distributions(basetgz=basetgz, suites=suites)
        distrib = [osp.basename(f).split('-', 1)[0]
                   for f in glob.glob(osp.join(basetgz,'*.tgz'))]
    elif distrib:
        mapped = ()
        # special setup case (all distribution names are available)
        if (len(sys.argv)>1 and sys.argv[1] in ["setup"]):
            distributions = get_distributions(basetgz=basetgz, suites=suites)
        # generic case: we retrieve distributions based on filesystem
        else:
            distributions = get_distributions('all', basetgz, suites)
        # check input distrib parameter and filter if really known
        for t in distrib:
            if t not in distributions:
                # Allow some lgp commands to be run outside a project repository
                if (len(sys.argv)>1 and sys.argv[1] == "check"):
                    logging.debug("'%s' image not found in '%s'" % (t, basetgz))
                    logging.debug("act as if 'unstable' image was existing in filesystem")
                    return ('unstable',)
                msg = "distribution '%s' image not found in '%s' (create it or unreference it)" % (t, basetgz)
                raise DistributionException(msg)
            else:
                mapped += (t,)
        distrib = mapped
    return tuple(set(distrib))

def guess_debian_source_format():
    """guess debian source format

    Default is 1.0 except if specified in `debian/source/format`

    :see: man dpkg-source
    """
    try:
        return open("debian/source/format").readline().strip()
    except:
        return "1.0"

def cached(func):
    """run a function only once and return always the same cache

       This decorator is used to reduce the overheads due to many system calls
    """
    def decorated(*args, **kwargs):
        try:
            return decorated._once_result
        except AttributeError:
            decorated._once_result = func(*args, **kwargs)
            return decorated._once_result
    return decorated

def wait_jobs(joblist, print_dots=True):
    t0 = time.time()
    status = 0
    while joblist:
        for j in joblist:
            j.poll()
            if j.returncode is not None:
                status += j.returncode
                joblist.remove(j)
        if print_dots:
            time.sleep(1)
            sys.stderr.write('.')
    if print_dots:
        sys.stderr.write('\n')
    return status, time.time() - t0

def _parse_deb_distrib(changelog='debian/changelog'):
    try:
        return re.search("\) (.+);", open(changelog).readline()).group(1).strip()
    except IOError:
        raise DistributionException("Debian changelog '%s' cannot be found" % changelog)
    except AttributeError:
        raise DistributionException("Debian distribution field not found in '%s'" % changelog)

def _parse_deb_archi(control='debian/control'):
    return filter(None, [p.get('Architecture').strip() for p
                         in Deb822.iter_paragraphs(file(control))])

def _parse_deb_version(changelog='debian/changelog'):
    try:
        return re.search("\((.+)\)", open(changelog).readline()).group(1).strip()
    except IOError:
        raise LGPException("Debian changelog '%s' cannot be found" % changelog)
    except AttributeError:
        raise LGPException("Debian version field not found in '%s'" % changelog)

def _parse_deb_project(changelog='debian/changelog'):
    return re.search("^(.+?) ", open(changelog).readline()).group(1).strip()


