
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
from logilab.devtools.jpl.jplproxy import build_proxy, RequestError
from logilab.devtools.jpl.tasks import print_tasks
from logilab.devtools.jpl.review import ask_review
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
              'jpl.tasks.notask': 'green'}

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
      PO name "%(project)s",
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
    return changesets that are linked to reviewed patch in the cwo forge
    """
    mercurial.revset.getargs(x, 0, 0, _("reviewed takes no arguments"))
    base_url = repo.ui.config('lglb', 'forge')
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
    base_url = repo.ui.config('lglb', 'forge')
    project = repo.ui.config('lglb', 'project')
    url = '%s/view?vid=jsonexport&rql=rql:%s' % (base_url, quote(IVRQL % {'version': version,
                                                                          'project': project}))
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
    base_url = repo.ui.config('lglb', 'forge')
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
    try:
        print_tasks(output, iter([node.short(args['ctx'].node())]), {})
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
    if ui.config('lglb', 'forge'):
        mercurial.revset.symbols['reviewed'] = reviewed
        mercurial.revset.symbols['tasks'] = tasks_predicate
        mercurial.templatekw.keywords['tasks'] = showtasks

        if ui.config('lglb', 'project'):
            mercurial.revset.symbols['inversion'] = inversion

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

    By default, the forge url used is https://www.cubicweb.org/: use
    -U/--forge-url to specify a different url. The forge url can be
    permanently defined into one of the mercurial configuration file::

      [lglb]
      forge-url = https://www.cubicweb.org/
      auth-mech = signedrequest
      auth-token = my token
      auth-secret = 0123456789abcdef

    or for kerberos authentication::

      [lglb]
      forge-url = https://my.intranet.com/
      auth-mech = kerberos

    """
    changesets += tuple(opts.get('rev', []))
    if not changesets:
        changesets = ('.')
    revs = scmutil.revrange(repo, changesets)
    if not revs:
        raise util.Abort(_('no working directory: please specify a revision'))
    ctxhexs = (node.short(repo.lookup(rev)) for rev in revs)

    with build_proxy(ui, opts) as client:
        print ask_review(client, ctxhexs)


