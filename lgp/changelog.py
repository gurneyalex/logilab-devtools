"""Manipulation of upstream and debian change log files

See logilab.common.changelog module documentation for the upstream change log
format.

See the debian documentation for the debian change log format.


:author:    Logilab
:copyright: 2003-2008 LOGILAB S.A. (Paris, FRANCE)
:contact:   http://www.logilab.fr/ -- mailto:python-projects@logilab.org
"""

import sys
import os
import time
from os.path import join, isfile, dirname, exists
import subprocess
from commands import getstatusoutput

from logilab.common.changelog import ChangeLog as BaseChangeLog, ChangeLogEntry

CHANGEFILE = 'ChangeLog'


class ChangeLogNotFound(Exception):
    """raised when we are unable to locate the change log"""

def find_ChangeLog(base_dir=None):
    """try to find a ChangeLog file from a base directory"""
    if base_dir is None:
        base_dir = os.getcwd()
    while base_dir:
        filepath = join(base_dir, CHANGEFILE)
        if isfile(filepath):
            return filepath
        new_dir = dirname(base_dir)
        if new_dir == base_dir:
            raise ChangeLogNotFound()
        base_dir = new_dir
    raise ChangeLogNotFound()

def find_debian_changelog(base_dir=None):
    """try to find a debian changelog file from a base directory"""
    if base_dir is None:
        base_dir = os.getcwd()
    while base_dir:
        filepath = join(base_dir, 'debian', 'changelog')
        if isfile(filepath):
            return filepath
        new_dir = dirname(base_dir)
        if new_dir == base_dir:
            raise ChangeLogNotFound()
        base_dir = new_dir
    raise ChangeLogNotFound()

def get_pkg_version(base_dir=None):
    """return the current package version"""
    if base_dir is None:
        base_dir = os.getcwd()
    if exists(join(base_dir, 'version.txt')):
        return Version(open(join(base_dir, 'version.txt')).read().strip())
    sys.path.insert(0, base_dir)
    mod = __import__('__pkginfo__')
    sys.path.pop(0)
    try:
        del sys.modules['__pkginfo__']
    except KeyError:
        pass
    return Version(mod.version)

# upstream change log #########################################################

class ChangeLog(BaseChangeLog):
    """object representation of a whole ChangeLog file

    add some methods to the base class useful for the changelog command line
    utility.
    """
    
    def get_latest_revision(self):
        """return the latest revision found or 0.0.0"""
        for entry in self.entries:
            if entry.version:
                return entry.version
        return Version('0.0.0')    

    def extract(self, version='', stream=sys.stdout):
        """extract messages for a given entry"""
        self.get_entry(version).write(stream)

    @staticmethod
    def formatted_date():        
        return time.strftime('%Y-%m-%d', time.localtime(time.time()))
        
    def close(self, base_dir, create=None):
        """close the opened change log entry"""
        version = get_pkg_version(base_dir)
        entry = self.get_entry(create=create)
        today = self.formatted_date()
        if len(self.entries) > 1:
            assert self.entries[1].version < version, \
                   '%s >= %s !' % (self.entries[1].version, version)
            assert self.entries[1].date <= today, '%s > %s !' % (
                self.entries[1].date, today)
        entry.date = today
        entry.version = version

    def update(self, create=None):
        """update the change log by extracting infos from cvs

        FIXME: use vcs_agent.log_info to extract log info
        """
        entry = self.get_entry(create=create)
        tag = ('version-%s' % self.get_latest_revision()).replace('.', '_')
        stream = os.popen('cvslog -- -- -r%s::' % tag)
        for line in stream.readlines():
            entry.add_message(line)


# debian change log ###########################################################

def debian_version(self):
    """return current debian version
    """
    cwd = os.getcwd()
    os.chdir(self.base_directory)
    try:
        status, output = getstatusoutput('dpkg-parsechangelog')
        if status != 0:
            msg = 'dpkg-parsechangelog exited with status %s' % status
            raise Exception(msg)
        for line in output.split('\n'):
            line = line.strip()
            if line and line.startswith('Version:'):
                return line.split(' ', 1)[1].strip()
        raise Exception('Debian version not found')
    finally:
        os.chdir(cwd)

class Version(object):
    def __init__(self, versionstr):
        self.value = versionstr
    def __str__(self):
        return self.value
    def __compare(self, op, other):
        if isinstance(other, Version):
            status = subprocess.call(['dpkg', '--compare-versions', self.value, op, other.value])
            return (status == 0)
        return NotImplemented
    
    def __eq__(self, other):
        return self.__compare('eq', other)
    def __ne__(self, other):
        return self.__compare('ne', other)
    def __lt__(self, other):
        return self.__compare('lt', other)
    def __le__(self, other):
        return self.__compare('le', other)
    def __gt__(self, other):
        return self.__compare('gt', other)
    def __ge__(self, other):
        return self.__compare('ge', other)
        
class DebianVersion(Version):
    """simple class to handle debian version number has a tuple while
    correctly printing it as X.Y.Z-D
    """
    # XXX lots of things supported by 'real' debian versions are not supported
    # see Debian Policy for the full gory details
    def __init__(self, versionstr):
        Version.__init__(self, versionstr)
        if ':' in versionstr:
            self.epoch, versionstr = versionstr.split(':')
        else:
            self.epoch = ''
        self.upstream_version, self.debian_version = versionstr.split('-')
        

class DebianChangeLogEntry(ChangeLogEntry):
    """object representation of a debian/changelog entry
    """
    version_class = DebianVersion
    def write(self, stream=sys.stdout):
        """write the entry to file """
        # pylint: disable-msg=E1101
        write = stream.write
        write('%s (%s) %s; urgency=%s\n\n' % (self.package, self.version,
                                              self.distrib, self.urgency))
        for msg, sub in self.messages:
            write('  * %s' % ''.join(msg))
            for sub_msg in sub:
                write('     - %s' % join(msg))
        write(' -- %s  %s\n\n' % (self.author, self.date))


class DebianChangeLog(ChangeLog):
    """object representation of a whole debian/changelog file"""
    
    entry_class = DebianChangeLogEntry

    @staticmethod
    def formatted_date():
        return time.strftime('%a, %d %b %Y %T %z', time.localtime(time.time()))
    
    def close(self, base_dir, create=None):
        """close the opened change log entry"""
        version = get_pkg_version(base_dir)
        entry = self.get_entry(create=create)
        today = self.formatted_date()
        if len(self.entries) > 1:
            centry = self.entries[1]
            upstream_version = centry.version.upstream_version
            assert upstream_version <= version
            assert centry.date < today
            if version == upstream_version:
                debian_version = centry.version.upstream_version + 1
            else:
                debian_version = 1
            fullversion = '%s-%s' % (version, debian_version)
        else:
            fullversion = '%s-1' % version
        entry.date = today
        entry.version = DebianVersion(version)

    def format_title(self):
        return ''
            
    def load(self):
        """ read a debian/changelog from file """
        try:
            stream = open(self.file)
        except IOError:
            return
        last = None
        for line in stream.readlines():
            sline = line.strip()
            if sline.startswith('-- '):
                try:
                    author, date = sline[3:].split('>')
                    author = author.strip() + '>'
                    date = date.strip()
                except TypeError:
                    author, date = '', ''
                last.date = date
                last.author = author
                last = None
            elif 'urgency' in sline:
                pkg, version, distrib, urgency = sline.split()
                version = version[1:-1]
                urgency = urgency[8:]
                distrib = distrib[:-1]
                last = self.entry_class(version=version, package=pkg,
                                        urgency=urgency, distrib=distrib)
                self.add_entry(last)
            elif last:
                if sline.startswith('* '):
                    last.add_message(line.lstrip()[1:].lstrip())
                elif last.messages:
                    last.complete_latest_message(line)
        stream.close()
