"""show Jenkins build information for Mercurial changesets

This extension provides:

* a "build_status" template keyword
* a "jenkins" view for `hg show` command (requires the built-in "show"
  extension)

Information to access the Jenkins server and job needs to be defined in a
"jenkins" configuration section::

  [jenkins]
  url = <URL of Jenkins server>
  job = <name of the job>,<name of another job>

  [auth]
  jenkins.schemes = https
  jenkins.prefix = jenkins.logilab.org
  jenkins.username = <Jenkins user ID>
  jenkins.password = <respective Jenkins user API token>
"""
from __future__ import absolute_import

from collections import defaultdict
import json

from jenkins import (
    Jenkins,
    NotFoundException,
)
from mercurial import (
    httpconnection as httpconnectionmod,
    templatekw,
    error,
    registrar,
    util,
)


cmdtable = {}
command = registrar.command(cmdtable)


@command(b'debugjenkins', [
    (b'', b'clear', None, b'clear Jenkins store'),
])
def debugjenkins(ui, repo, **opts):
    """debug actions for 'jenkins' extension."""
    if opts.get(r'clear'):
        jenkinsstore(repo.svfs, None).clear()
    else:
        ui.warn(b'no option specified, did nothing\n')


def buildinfo_for_job(jenkins_server, job_name):
    # We retrieve all builds matching a hg-node.
    build_for_hgnode = defaultdict(list)
    try:
        jobinfo = jenkins_server.get_job_info(job_name)
    except NotFoundException:
        raise error.ConfigError(
            "job '%s' not found" % job_name,
            hint='see if jenkins.job config entry is correct',
        )
    for build in jobinfo['builds']:
        build_number = build['number']
        build_info = jenkins_server.get_build_info(job_name, build_number)
        for action in build_info['actions']:
            hgnode = action.get('mercurialNodeName')
            if hgnode:
                build_for_hgnode[hgnode].append({
                    'number': build_number,
                    'status': build_info['result'],
                    'building': build_info['building'],
                    'url': build_info['url'],
                })
                break
    # Ultimately, we only keep the latest build (i.e. the one with largest
    # build number) for each hg-node.
    for hgnode, values in build_for_hgnode.items():
        values.sort(key=lambda d: d['number'])
        build_for_hgnode[hgnode] = values[-1]
    return build_for_hgnode


class jenkinsstore(object):
    """file-system cache for Jenkins data.

    The cache is invalidated (not used and thus rebuilt) when specified
    `tiprev` is greater that stored one, typically after a pull.
    """

    def __init__(self, svfs, tiprev):
        self.svfs = svfs
        self.cache = {'tip': tiprev}

    def load(self, ui):
        """Possibly load "jenkins" store cache if still valid (w.r.t. tiprev).
        """
        data = self.svfs.tryread(b'jenkins')
        if data:
            data = json.loads(data.decode('utf-8'))
            try:
                storedtiprev = data['tip']
            except KeyError:
                pass
            else:
                if storedtiprev >= self.cache['tip']:
                    self.cache = data
                else:
                    ui.warn(b'rebuidling "jenkins" store\n')
        return self.cache

    def save(self):
        with self.svfs(b'jenkins', b'wb') as f:
            f.write(json.dumps(self.cache).encode('utf-8'))

    def clear(self):
        self.svfs.unlink(b'jenkins')


def showbuildstatus(context, mapping):
    """:build_status: String. Status of build.
    """
    repo = context.resource(mapping, b'repo')
    ui = repo.ui
    debug = ui.debugflag
    ctx = context.resource(mapping, b'ctx')
    store = jenkinsstore(repo.svfs, repo[b'tip'].rev())
    storecache = store.load(ui)
    if debug:
        if len(storecache) <= 1:
            ui.debug(b'jenkins cache is empty\n')
        else:
            ui.debug(b'jenkins cache: {}\n'.format(storecache))

    url = ui.config(b'jenkins', b'url')
    if not url:
        raise error.Abort('jenkins.url configuration option is not defined')
    res = httpconnectionmod.readauthforuri(repo.ui, url, util.url(url).user)
    if res:
        group, auth = res
        ui.debug(b"using auth.%s.* for authentication\n" % group)
        username = auth.get('username')
        password = auth.get('password')
        if not username or not password:
            raise error.Abort(
                "cannot fine 'username' and/or 'password' values for %s"
                % url
            )
    else:
        ui.debug(b"no 'auth' configuration for %s\n" % url)
        username, password = None, None
    username = ui.config(b'jenkins', b'username')
    password = ui.config(b'jenkins', b'password')
    server = Jenkins(url.decode('utf-8'), username=username, password=password)

    if 'jobs' not in storecache:
        jobnames = ui.config(b'jenkins', b'job').decode('utf-8')
        jobs = [n.strip() for n in jobnames.split(',')]
        storecache['jobs'] = {name: {} for name in jobs}
    elif debug:
        ui.debug(b'using cached jobs\n')

    def gen_jobs_buildinfo():
        for job, jobcache in storecache['jobs'].items():
            if not jobcache:
                jobcache.update(buildinfo_for_job(server, job))
            elif debug:
                ui.debug(b'using cached build info for job %s\n' % job)
            build_info = jobcache.get(ctx.hex().decode('utf-8'))
            if not build_info:
                yield '{}: NOT BUILT\n'.format(job)
                continue
            if build_info['building']:
                status = 'BUILDING'
            else:
                status = build_info['status']
            build_url = build_info['url']
            yield '{}: {} - {}\n'.format(job, status, build_url)

    jobs_buildinfo = [v.encode('utf-8') for v in gen_jobs_buildinfo()]
    store.save()

    if not jobs_buildinfo:
        jobs_buildinfo.append(b'NOT BUILT')

    return templatekw.compatlist(context, mapping, b'build_status',
                                 jobs_buildinfo)


try:
    from hgext.show import showview
except ImportError:
    pass
else:
    from mercurial import formatter, graphmod
    try:
        from mercurial.logcmdutil import (
            displaygraph,
            changesettemplater,
        )
    except ImportError:
        # Mercurial < 4.6
        from mercurial.cmdutil import (
            displaygraph,
            changeset_templater as changesettemplater,
        )

    tmpl = (
        b'{label("changeset.{phase}{if(troubles, \' changeset.troubled\')}", '
        b'shortest(node, 5))} '
        b'[{label("log.branch", branch)}] '
        b'{label("log.description", desc|firstline)} '
        b'({label("log.user", author|user)})'
        b'\n {build_status}\n'
    )

    @showview(b'jenkins')
    def showjenkins(ui, repo):
        """Jenkins build status"""
        revs = repo.revs('sort(_underway(), topo)')

        revdag = graphmod.dagwalker(repo, revs)

        ui.setconfig(b'experimental', b'graphshorten', True)
        spec = formatter.lookuptemplate(ui, None, tmpl)
        displayer = changesettemplater(ui, repo, spec, buffered=True)
        displaygraph(ui, repo, revdag, displayer, graphmod.asciiedges)


def extsetup(ui):
    if ui.config(b'jenkins', b'url'):
        templatekw.templatekeyword(
            b'build_status', requires={'ctx', 'repo'},
        )(showbuildstatus)
