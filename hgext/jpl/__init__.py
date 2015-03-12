# jpl - cubicweb-vcreview interaction feature for mercurial
#
# copyright 2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This software may be used and distributed according to the terms of the
# GNU General Public License version 2 or any later version.

'''commands and revset functions to interact with a cubicweb-vcreview code review application

This extension lets you query and change the review status of patches modeling
mercurial changesets.

The forge url can be permanently defined into one of the mercurial
configuration file::

  [lglb]
  forge-url = https://www.cubicweb.org/
  auth-mech = signedrequest
  auth-token = my token
  auth-secret = 0123456789abcdef

or for kerberos authentication::

  [lglb]
  forge-url = https://my.intranet.com/
  auth-mech = kerberos

Note that you need `python-requests-kerberos`_ for this later
configuration to work.

You may also need `python-ndg-httpsclient`_ and `python-openssl`_ if
the forge application is using a SNI_ ssl configuration (ie. if you
get errors like::

  abort: error: hostname 'www.logilab.org' doesn't match either of
         'demo.cubicweb.org', 'cubicweb.org'

.. _`python-requests-kerberos`: https://pypi.python.org/pypi/requests-kerberos
.. _`python-ndg-httpsclient`: https://pypi.python.org/pypi/ndg-httpsclient
.. _`python-openssl`:https://pypi.python.org/pypi/pyOpenSSL
.. _SNI: https://en.wikipedia.org/wiki/Server_Name_Indication
.. _`cwclientlib: https://www.cubicweb.org/project/cwclientlib

'''
from cStringIO import StringIO
from mercurial import cmdutil, scmutil, util, node, demandimport
from mercurial.i18n import _
import mercurial.revset
import mercurial.templatekw

try:
    enabled = demandimport.isenabled()
except AttributeError:
    enabled = demandimport._import is __import__
demandimport.disable()
from .jplproxy import build_proxy, RequestError
from .tasks import print_tasks
from .review import ask_review, show_review, sudo_make_me_a_ticket, assign
if enabled:
    demandimport.enable()

cmdtable = {}
command = cmdutil.command(cmdtable)
colortable = {'jpl.tasks.patch': 'cyan',
              'jpl.tasks.task.todo': 'red',
              'jpl.tasks.task.done': 'green',
              'jpl.tasks.task': '',
              'jpl.tasks.description': '',
              'jpl.tasks.comment': 'yellow',
              'jpl.tasks.notask': 'green',
              'jpl.cwuri': 'yellow',
              'jpl.status.pending-review': 'red',
              'jpl.status.in-progress': 'yellow',
              'jpl.status.reviewed': 'green',
              'jpl.status.applied': 'cyan',
              }

RQL = """
Any PO, RC, P
GROUPBY PO, P, TIP, RC
ORDERBY PO, H ASC, TIP DESC
WHERE P in_state T,
      T name "reviewed",
      P patch_revision TIP,
      TIP from_repository RP,
      PO source_repository RP,
      TIP changeset RC,
      TIP hidden H,
      NOT EXISTS(RE obsoletes TIP,
                 P patch_revision RE)
"""

IVRQL = """
Any PO, RC, T
GROUPBY PO, P, T, RC
ORDERBY PO, H ASC, T DESC
WHERE P patch_revision TIP,
      TIP from_repository RP,
      PO source_repository RP,
      TIP changeset RC,
      TIP hidden H,
      NOT EXISTS(RE obsoletes TIP,
                 P patch_revision RE),
      T concerns PO,
      T done_in V,
      V num "%(version)s",
      P  patch_ticket T
"""

TASKSRQL = """
DISTINCT Any RC
WHERE P patch_revision TIP,
      TIP changeset RC,
      EXISTS(P has_activity T) OR
      EXISTS(X has_activity T,
             X point_of RX,
             P patch_revision RX),
      T in_state S,
      S name {states}
"""

import json
from urllib import quote, urlopen

def reviewed(repo, subset, x):
    """
    return changesets that are linked to reviewed patch in the jpl forge
    """
    mercurial.revset.getargs(x, 0, 0, _("reviewed takes no arguments"))
    base_url = repo.ui.config('lglb', 'forge-url')
    url = '%s/view?vid=jsonexport&rql=rql:%s' % (base_url, quote(RQL))
    raw_data = urlopen(url)
    data = json.load(raw_data)
    all = set(short for po, short, p in data)
    return [r for r in subset if str(repo[r]) in all]

def inversion(repo, subset, x):
    """
    return changesets that are linked to patches linked to tickets of given version+project
    """
    version = mercurial.revset.getargs(x, 1, 1, _("inversion takes one argument"))[0][1]
    base_url = repo.ui.config('lglb', 'forge-url')
    url = '%s/view?vid=jsonexport&rql=rql:%s' % (base_url, quote(IVRQL % {'version': version}))
    raw_data = urlopen(url)
    data = json.load(raw_data)
    all = set(short for po, short, p in data)
    return [r for r in subset if str(repo[r]) in all]

def tasks_predicate(repo, subset, x=None):
    """``tasks(*states)``
    Changesets linked to tasks to be done.

    The optional state arguments are task states to filter
    (default to 'todo').
    """
    base_url = repo.ui.config('lglb', 'forge-url')
    states = None
    if x is not None:
        states = [val for typ, val in mercurial.revset.getlist(x)]
    if not states:
        states = '!= "done"'
    elif len(states) == 1:
        states = '"{}"'.format(states[0])
    else:
        states = 'IN ({})'.format(','.join('"{}"'.format(state) for state in states))
    rql = TASKSRQL.format(states=states)
    url = '%s/view?vid=jsonexport&rql=rql:%s' % (base_url, quote(rql))
    raw_data = urlopen(url)
    data = json.load(raw_data)
    all = set(short[0] for short in data)
    return [r for r in subset if str(repo[r]) in all]

def showtasks(**args):
    """:tasks: List of Strings. The text of the tasks and comments of a patch."""
    output = _MockOutput()
    with build_proxy(output, args) as client:
        try:
            print_tasks(client, output, iter([node.short(args['ctx'].node())]), {})
        except RequestError:
            return ''
    return mercurial.templatekw.showlist('task', list(output), **args)
    #return str(output).strip()

class _MockOutput(object):
    def __init__(self):
        self._ios = [StringIO()]
    def write(self, msg, label=None):
        if msg.startswith('Task:'):
            self._ios.append(StringIO())
        self._ios[-1].write(msg)
    def __iter__(self):
        for io in self._ios:
            yield io.getvalue()

def extsetup(ui):
    if ui.config('lglb', 'forge-url'):
        mercurial.revset.symbols['reviewed'] = reviewed
        mercurial.revset.symbols['tasks'] = tasks_predicate
        mercurial.revset.symbols['inversion'] = inversion
        mercurial.templatekw.keywords['tasks'] = showtasks

cnxopts  = [
    ('U', 'forge-url', '', _('base url of the forge (jpl) server'), _('URL')),
    ('S', 'no-verify-ssl', None, _('do NOT verify server SSL certificate')),
    ('Y', 'auth-mech', '', _('authentication mechanism used to connect to the forge'), _('MECH')),
    ('t', 'auth-token', '', _('authentication token (when using signed request)'), _('TOKEN')),
    ('s', 'auth-secret', '', _('authentication secret (when using signed request)'), ('SECRET')),
    ]

@command('^tasks', [
    ('r', 'rev', [], _('tasks for the given revision(s)'), _('REV')),
    ('a', 'all', False, _('also display done tasks')),
    ] + cnxopts,
    _('[OPTION]... [-a] [-r] REV...'))
def tasks(ui, repo, *changesets, **opts):
    """show tasks related to the given revision.

    By default, the revision used is the parent of the working
    directory: use -r/--rev to specify a different revision.

    By default, the forge url used is https://www.cubicweb.org/: use
    -U/--forge-url to specify a different url. The forge url can be
    permanently defined into one of the mercurial configuration file::

    [lglb]
    forge-url = https://www.cubicweb.org/

    By default, done tasks are not displayed: use -a/--all to not filter
    tasks and display all.
    """
    changesets += tuple(opts.get('rev', []))
    if not changesets:
        changesets = ('.')
    revs = scmutil.revrange(repo, changesets)
    if not revs:
        raise util.Abort(_('no working directory or revision not found: please specify a known revision'))
    # we need to see hidden cs from here
    repo = repo.unfiltered()

    for rev in revs:
        precs = scmutil.revrange(repo, (rev, 'allprecursors(%s)' % rev))
        ctxhexs = list((node.short(repo.lookup(lrev)) for lrev in precs))
        showall = opts.get('all', None)
        with build_proxy(ui, opts) as client:
            try:
                print_tasks(client, ui, ctxhexs, showall=showall)
            except RequestError, e:
                ui.write('no patch or no tasks for %s\n' % node.short(repo.lookup(rev)))


@command('^ask-review', [
    ('r', 'rev', [], _('ask review for the given revision(s)'), _('REV')),
    ]  + cnxopts,
    _('[OPTION]... [-r] REV...'))
def askreview(ui, repo, *changesets, **opts):
    """ask for review for patches corresponding to specified revisions

    By default, the revision used is the parent of the working
    directory: use -r/--rev to specify a different revision.

    """
    changesets += tuple(opts.get('rev', []))
    if not changesets:
        changesets = ('.')
    revs = scmutil.revrange(repo, changesets)
    if not revs:
        raise util.Abort(_('no working directory: please specify a revision'))
    ctxhexs = (node.short(repo.lookup(rev)) for rev in revs)

    with build_proxy(ui, opts) as client:
        ask_review(client, ctxhexs)
        ui.write('OK\n')

@command('^show-review', [
    ('r', 'rev', [], _('show review status for the given revision(s)'), _('REV')),
    ('c', 'committer', '', _('login of the committer in JPL forge'), _('LOGIN')),
    ]  + cnxopts,
    _('[OPTION]... [-r] REV...'))
def showreview(ui, repo, *changesets, **opts):
    """show review status for patches corresponding to specified revisions

    By default, the revision used is the parent of the working
    directory: use -r/--rev to specify a different revision.

    """
    changesets += tuple(opts.get('rev', []))
    if not changesets:
        changesets = ('.')
    revs = scmutil.revrange(repo, changesets)
    if not revs:
        raise util.Abort(_('no working directory: please specify a revision'))
    ctxhexs = (node.short(repo.lookup(rev)) for rev in revs)

    committer = opts.get('committer', None)

    with build_proxy(ui, opts) as client:
        rev = show_review(client, ctxhexs, committer)
        for pname, eid, status, victims in  rev:
            uri = client.buildurl(str(eid))
            ui.write("{0}".format(uri), label='jpl.cwuri')
            ui.write("\t[{0}]".format(status), label='jpl.status.{0}'.format(status))
            ui.write("\t{0}\n".format(victims), label='jpl.reviewers')
            ui.write(pname.encode('utf-8') + '\n\n')

@command('^assign', [
    ('r', 'rev', [], _('revision(s) indentifying patch(es) to be assigned to committer'), _('REV')),
    ('c', 'committer', '', _('login of the committer in JPL forge'), _('LOGIN')),
    ]  + cnxopts,
    _('[OPTION]... [-r] REV... -c LOGIN'))
def patch_assign(ui, repo, *changesets, **opts):
    """Assign patches corresponding to specified revisions to a committer.

    By default, the revision used is the parent of the working
    directory: use -r/--rev to specify a different revision.
    """
    changesets += tuple(opts.get('rev', []))
    if not changesets:
        changesets = ('.')
    revs = scmutil.revrange(repo, changesets)
    if not revs:
        raise util.Abort(_('no working directory: please specify a revision'))
    ctxhexs = (node.short(repo.lookup(rev)) for rev in revs)

    committer = opts.get('committer', None)
    if not committer:
        raise util.Abort(_('unspecified committer login (-c LOGIN)'))

    with build_proxy(ui, opts) as client:
        assign(client, ctxhexs, committer)
        ui.write('OK\n')

@command('^make-ticket', [
    ('r', 'rev', [], _('create a ticket for the given revision'), _('REV')),
    ('d', 'done-in', '', _('new ticket should be marked as done in this version'), _('VERSION')),
    ] + cnxopts,
    _('[OPTION]... [-d VERSION] [-r] REV'))
def make_ticket(ui, repo, *changesets, **opts):
    """create new tickets for the specified revisions
    """
    changesets += tuple(opts.get('rev', []))
    if not changesets:
        changesets = ('.',)
    revs = scmutil.revrange(repo, changesets)
    if not revs:
        raise util.Abort(_('no working directory: please specify a revision'))

    with build_proxy(ui, opts) as client:
        for rev in revs:
            ticket = sudo_make_me_a_ticket(client, repo, rev, opts.get('done_in', ''))
            ui.write("{0} {1}\n".format(rev, ticket[0][0]))
