# jpl - cubicweb-vcreview interaction feature for mercurial
#
# copyright 2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This software may be used and distributed according to the terms of the
# GNU General Public License version 2 or any later version.

'''commands and revset functions to interact with a cubicweb-vcreview
code review application

This extension lets you query and change the review status of patches modeling
mercurial changesets.

The forge url can be permanently defined into one of the mercurial
configuration file::

  [jpl]
  endpoint = https://www.cubicweb.org/

or, according cwo is the id of the endpoint in your cwclientlib_ config file::

  [jpl]
  endpoint = cwo

You may need `python-ndg-httpsclient`_ and `python-openssl`_ if
the forge application is using a SNI_ ssl configuration (ie. if you
get errors like::

  abort: error: hostname 'www.logilab.org' doesn't match either of
         'demo.cubicweb.org', 'cubicweb.org'

.. _`python-ndg-httpsclient`: https://pypi.python.org/pypi/ndg-httpsclient
.. _`python-openssl`:https://pypi.python.org/pypi/pyOpenSSL
.. _SNI: https://en.wikipedia.org/wiki/Server_Name_Indication
.. _cwclientlib: https://www.cubicweb.org/project/cwclientlib

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
demandimport.disable()  # noqa

from .jplproxy import build_proxy
from .tasks import print_tasks
from .review import (ask_review, acknowledge, add_reviewer, show_review,
                     sudo_make_me_a_ticket, assign)
from .apycot import create_test_execution, list_tc
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
              'jpl.testresult.error': 'cyan',
              'jpl.testresult.failure': 'red',
              'jpl.testresult.partial': 'yellow',
              'jpl.testresult.success': 'green',
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
      V num %(version)s,
      P patch_ticket T
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


def reviewed(repo, subset, x):
    """
    return changesets that are linked to reviewed patch in the jpl forge
    """
    mercurial.revset.getargs(x, 0, 0, _("reviewed takes no arguments"))
    with build_proxy(repo.ui) as client:
        data = client.rql(RQL)
    all = set(short for po, short, p in data)
    return [r for r in subset if str(repo[r]) in all]


def inversion(repo, subset, x):
    """
    return changesets that are linked to patches linked to tickets of
    given version+project
    """
    version = mercurial.revset.getargs(
        x, 1, 1, _("inversion takes one argument"))[0][1]
    with build_proxy(repo.ui) as client:
        args = {'version': version}
        data = client.execute(IVRQL, args)
    all = set(short for po, short, p in data)
    return [r for r in subset if str(repo[r]) in all]


def tasks_predicate(repo, subset, x=None):
    """``tasks(*states)``
    Changesets linked to tasks to be done.

    The optional state arguments are task states to filter
    (default to 'todo').
    """
    states = None
    if x is not None:
        states = [val for typ, val in mercurial.revset.getlist(x)]
    if not states:
        states = '!= "done"'
    elif len(states) == 1:
        states = '"{}"'.format(states[0])
    else:
        states = 'IN ({})'.format(
            ','.join('"{}"'.format(state) for state in states))
    rql = TASKSRQL.format(states=states)
    with build_proxy(repo.ui) as client:
        data = client.rql(rql)
    all = set(short[0] for short in data)
    return [r for r in subset if str(repo[r]) in all]


def showtasks(**args):
    ":tasks: List of Strings. The text of the tasks and comments of a patch."
    output = _MockOutput()
    with build_proxy(output, args) as client:
        try:
            print_tasks(client, output,
                        iter([node.short(args['ctx'].node())]), {})
        except Exception:
            return ''
    return mercurial.templatekw.showlist('task', list(output), **args)


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
    if ui.config('jpl', 'endpoint'):
        mercurial.revset.symbols['reviewed'] = reviewed
        mercurial.revset.symbols['tasks'] = tasks_predicate
        mercurial.revset.symbols['inversion'] = inversion
        mercurial.templatekw.keywords['tasks'] = showtasks


cnxopts = [
    ('U', 'endpoint', '',
     _('endpoint (ID or URL) of the configured cwclientlib '
       'forge (jpl) server'), _('ENDPOINT')),
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

    By default, the forge url used is https://www.cubicweb.org/. Use
    -U/--endpoint to specify a different cwclientlib endpoint. The
    endpoint id of the forge can be permanently defined into one of
    the mercurial configuration file::

    [jpl]
    endpoint = https://www.cubicweb.org/

    By default, done tasks are not displayed: use -a/--all to not filter
    tasks and display all.

    """
    changesets += tuple(opts.get('rev', []))
    if not changesets:
        changesets = ('.')
    revs = scmutil.revrange(repo, changesets)
    if not revs:
        raise util.Abort(_('no working directory or revision not found: '
                           'please specify a known revision'))
    # we need to see hidden cs from here
    repo = repo.unfiltered()

    for rev in revs:
        precs = scmutil.revrange(repo, (rev, 'allprecursors(%s)' % rev))
        ctxhexs = list((node.short(repo.lookup(lrev)) for lrev in precs))
        showall = opts.get('all', None)
        with build_proxy(ui, opts) as client:
            try:
                print_tasks(client, ui, ctxhexs, showall=showall)
            except Exception as e:
                ui.write('no patch or no tasks for %s\n'
                         % node.short(repo.lookup(rev)))


@command('^ask-review', [
    ('r', 'rev', [], _('ask review for the given revision(s)'), _('REV')),
    ] + cnxopts,
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


@command('^acknowledge', [
    ('r', 'rev', [], _('ask review for the given revision(s)'), _('REV')),
    ] + cnxopts,
    _('[OPTION]... [-r] REV...'))
def accept(ui, repo, *changesets, **opts):
    """accept patches corresponding to specified revisions

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
        acknowledge(client, ctxhexs)
    showreview(ui, repo, *changesets, **opts)


@command('^show-review', [
    ('r', 'rev', [],
     _('show review status for the given revision(s)'), _('REV')),
    ('c', 'committer', '',
     _('login of the committer in JPL forge'), _('LOGIN')),
    ('T', 'test-results', False,
     _('show test results for each changeset'), ),
    ] + cnxopts,
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
    ctxhexs = [node.short(repo.lookup(rev)) for rev in revs]

    committer = opts.get('committer', None)

    def rset_revision_index(rset_row):
        for revid in rset_row[2].split(','):
            revid = revid.strip()
            if revid in ctxhexs:
                return ctxhexs.index(revid)

    with build_proxy(ui, opts) as client:
        review_results = show_review(client, ctxhexs, committer)
        if opts.get('test_results'):
            rql = ('Any PEN, TCN, ST WHERE TE status ST, '
                   'TE using_revision REV, '
                   'REV changeset %(cset)s, '
                   'TE using_environment PE, PE name PEN, '
                   'TE using_config TC, TC name TCN')
            queries = [(rql, dict(cset=cset)) for cset in ctxhexs]
            test_results = dict(zip(ctxhexs, client.rqlio(queries)))
        else:
            test_results = None
        review_results.sort(key=rset_revision_index, reverse=True)
        _format_review_result(ui, repo, client, review_results, test_results)


def _format_review_result(ui, repo, client, revs, test_results=None):
    """Display a formatted patch review list"""
    for pname, eid, rids, status, victims in revs:
        uri = client.build_url(str(eid))
        ui.write("{0}".format(uri), label='jpl.cwuri')
        if ',' in rids:
            revs = repo.revs('max({})'.format(rids.replace(',', ' or ')))
            rids = node.short(repo.lookup(revs.first()))
        ui.write(" {0}".format(rids))
        ui.write("\t[{0}]".format(status),
                 label='jpl.status.{0}'.format(status))
        ui.write("\t{0}\n".format(victims), label='jpl.reviewers')
        ui.write(pname.encode('utf-8') + '\n\n')
        if test_results:
            for rid in rids.split(','):
                for pen, tcn, st in test_results.get(rid.strip(), []):
                    ui.write('#{} {}/{}: '.format(rid, pen, tcn))
                    ui.write('{}\n'.format(st),
                             label='jpl.testresult.{0}'.format(st))


@command('^backlog', [
    ('c', 'committer', '',
     _('login of the committer in JPL forge'), _('LOGIN')),
    ] + cnxopts,
    _('[OPTION]... -c LOGIN'))
def backlog(ui, repo, *changesets, **opts):
    """show the backlog (draft changesets) of specified committer in the form
    of a review list.
    """
    revs = repo.revs('draft()')
    ctxhexs = (node.short(repo.lookup(rev)) for rev in revs)

    committer = opts.get('committer', None)

    with build_proxy(ui, opts) as client:
        rev = show_review(client, ctxhexs, committer)
        _format_review_result(ui, repo, client, rev)


@command('^assign', [
    ('r', 'rev', [],
     _('revision(s) indentifying patch(es) to be assigned to committer'),
     _('REV')),
    ('c', 'committer', '',
     _('login of the committer in JPL forge'), _('LOGIN')),
    ] + cnxopts,
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


@command('^add-reviewer', [
    ('r', 'rev', [],
     _('revision(s) indentifying patch(es) to be assigned to committer'),
     _('REV')),
    ('c', 'reviewer', '', _('login of the reviewer to add'), _('LOGIN')),
    ] + cnxopts,
    _('[OPTION]... [-r] REV... -c LOGIN'))
def addreviewer(ui, repo, *changesets, **opts):
    """Add a reviewer to patches corresponding to specified revisions.

    By default, the revision used is the parent of the working
    directory: use -r/--rev to specify a different revision.
    """
    changesets += tuple(opts.get('rev', []))
    if not changesets:
        changesets = ('.',)
    revs = scmutil.revrange(repo, changesets)
    if not revs:
        raise util.Abort(_('no working directory: please specify a revision'))
    ctxhexs = (node.short(repo.lookup(rev)) for rev in revs)

    reviewer = opts.get('reviewer', None)
    if not reviewer:
        raise util.Abort(_('unspecified reviewer login (-c LOGIN)'))

    with build_proxy(ui, opts) as client:
        add_reviewer(client, ctxhexs, reviewer)
        ui.write('OK\n')


@command('^make-ticket', [
    ('r', 'rev', [], _('create a ticket for the given revision'), _('REV')),
    ('d', 'done-in', '',
     _('new ticket should be marked as done in this version'), _('VERSION')),
    ('t', 'type', '', _('type of ticket'), _('TYPE')),
    ] + cnxopts,
    _('[OPTION]... [-d VERSION] [-t TYPE] [-r] REV'))
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
            ticket = sudo_make_me_a_ticket(client, repo, rev,
                                           version=opts.get('done_in', ''),
                                           kind=opts.get('type', 'bug'))
            ui.write("{0} {1}\n".format(
                rev, ticket[0][0] if ticket[0] else 'FAILED'))


@command('^start-test', [
    ('r', 'rev', [],
     _('start apycot tests on the given revision(s)'), _('REV')),
    ('t', 'tc-name', 'quick',
     _("the TestConfig's name to execute"), _('TCNAME')),
    ('o', 'option', [],
     _("options to add to the TestExecution"), _('OPTIONS')),
    ] + cnxopts,
    _('[OPTION]... [-r] REV...'))
def runapycot(ui, repo, *changesets, **opts):
    """start Apycot tests for the given revisions.

    By default, the revision used is the parent of the working
    directory: use -r/--rev to specify a different revision.

    Use -t/--tc-name to specify the TestConfig which describes the
    tests to be executed.
    """
    changesets += tuple(opts.get('rev', []))
    if not changesets:
        changesets = ('.')
    revs = scmutil.revrange(repo, changesets)
    if not revs:
        raise util.Abort(_('no working directory: please specify a revision'))
    ctxhexs = [node.short(repo.lookup(rev)) for rev in revs]
    tcname = opts.get('tc_name', None)
    options = dict(o.split('=') for o in opts.get('option', []))

    with build_proxy(ui, opts) as client:
        results = create_test_execution(client, ctxhexs, tcname, **options)
        rset = [x[0][0] if x else None for x in results]
        started = [client.build_url(str(eid)) for eid in rset if eid]
        if any(rset):
            ui.write('started:\n{}\n'.format(
                '\n'.join("* {}".format(e) for e in started)))
            failed = [cset for (cset, result)
                      in zip(ctxhexs, rset) if cset.strip() and not result]
            if failed:
                ui.write('WARNING: could not create tests for {}\n'.format(
                    ', '.join(failed)))
        else:
            ui.write('FAILED\n')
        ui.write('\n')


@command('^list-tc', [
    ('r', 'rev', [],
     _('list available TestConfig for the given revision(s)'), _('REV')),
    ] + cnxopts,
    _('[OPTION]... [-r] REV...'))
def listtc(ui, repo, *changesets, **opts):
    """list available test configurations for the given revisions.

    By default, the revision used is the parent of the working
    directory: use -r/--rev to specify a different revision.

    """
    changesets += tuple(opts.get('rev', []))
    if not changesets:
        changesets = ('.')
    revs = scmutil.revrange(repo, changesets)
    if not revs:
        raise util.Abort(_('no working directory: please specify a revision'))
    ctxhexs = [node.short(repo.lookup(rev)) for rev in revs]

    with build_proxy(ui, opts) as client:
        results = list_tc(client, ctxhexs)
        ui.write('{}\n'.format(
            '\n'.join('{0} ({1})'.format(str(tc), str(tn))
                      for (tc, tn) in results)))
