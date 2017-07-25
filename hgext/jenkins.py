from __future__ import absolute_import

import json

from six.moves import urllib

from lxml import etree
from jenkins import Jenkins
from mercurial import templatekw, node, error


def repourl_from_rev(hgnode, ui):
    from hgext.jpl import jplproxy
    query = ('Any URL WHERE REV changeset %(rev)s, REV from_repository REPO,'
             ' REPO source_url URL')
    with jplproxy.build_proxy(ui) as client:
        rset = client.execute(query, {'rev': hgnode})
        if rset:
            return rset[0][0]
    raise error.Abort('could not find repository url from local repository')


def jobs_from_hgurl(ui, jenkins_server, url, branch):
    purl = urllib.parse.urlparse(url.rstrip('/'))

    def match_url(expected):
        pexpected = urllib.parse.urlparse(expected)
        return (purl.netloc == pexpected.netloc
                and purl.path == pexpected.path.rstrip('/'))

    debug = ui.debugflag
    for job in jenkins_server.get_jobs():
        job_name = job['name']
        if debug:
            ui.debug('* %s\n' % job_name)
        config = jenkins_server.get_job_config(job_name)
        root = etree.fromstring(config)
        for scm in root.findall('scm'):
            for source in scm.iterchildren('source'):
                break
            else:
                if debug:
                    ui.debug(' -> no scm definition, skipping\n')
                continue
            revision = None
            for rev_elem in scm.iterchildren('revision'):
                revision = rev_elem.text.strip()
                break
            job_url = source.text
            if match_url(job_url) and branch and branch == revision:
                if debug:
                    ui.debug(' -> matching (revision: %s)\n' % revision)
                yield job_name
            elif debug:
                ui.debug(' -> source url %s not matching %s\n' % (job_url, url))
    # raise error.Abort('no Jenkins job matching repository url %s' % url)


def buildinfo_for_job(jenkins_server, job_name):
    build_for_hgnode = {}
    for build in jenkins_server.get_job_info(job_name)['builds']:
        build_number = build['number']
        build_info = jenkins_server.get_build_info(job_name, build_number)
        for action in build_info['actions']:
            hgnode = action.get('mercurialNodeName')
            if hgnode:
                build_for_hgnode[hgnode] = {
                    'number': build_number,
                    'status': build_info['result'],
                    'building': build_info['building'],
                    'url': build_info['url'],
                }
                break
    return build_for_hgnode

class jenkinsstore(object):

    def __init__(self, svfs):
        self.svfs = svfs
        self.cache = {}

    def load(self):
        data = self.svfs.tryread('jenkins')
        if data:
            self.cache = json.loads(data)
        return self.cache

    def save(self):
        with self.svfs('jenkins', 'w') as f:
            json.dump(self.cache, f)

def showbuildstatus(**args):
    """:build_status: String. Status of build.
    """
    repo = args['repo']
    ui = repo.ui
    debug = ui.debugflag
    ctx = args['ctx']
    store = jenkinsstore(repo.svfs)
    storecache = store.load()
    if debug:
        if not storecache:
            ui.debug('jenkins cache is empty\n')
        else:
            ui.debug('jenkins cache: {}\n'.format(storecache))

    url = ui.config('jenkins', 'url')
    if not url:
        raise error.Abort('jenkins.url configuration option is not defined')
    username = ui.config('jenkins', 'username')
    password = ui.config('jenkins', 'password')
    server = Jenkins(url, username=username, password=password)

    if 'jobs' not in storecache:
        jobname = ui.config('jenkins', 'job')
        if jobname:
            jobs = [jobname]
        else:
            # look for jobs matching repository URL
            if 'repo_url' in storecache:
                if debug:
                    ui.debug('using cached repository URL\n')
                repo_url = storecache['repo_url']
            else:
                repo_url = ui.config('jenkins', 'repo-url')
                if not repo_url:
                    rev = node.short(repo.lookup(ctx.hex()))
                    repo_url = repourl_from_rev(rev, ui)
                storecache['repo_url'] = repo_url
            jobs = jobs_from_hgurl(ui, server, repo_url, ctx.branch())
        storecache['jobs'] = {name: {} for name in jobs}
    elif debug:
        ui.debug('using cached jobs\n')

    jobs_buildinfo = []
    for job, jobcache in storecache['jobs'].iteritems():
        if not jobcache:
            jobcache.update(buildinfo_for_job(server, job))
        elif debug:
            ui.debug('using cached build info for job %s\n' % job)
        build_info = jobcache.get(ctx.hex())
        if not build_info:
            jobs_buildinfo.append('{}: NOT BUILT'.format(job))
            continue
        if build_info['building']:
            status = 'BUILDING'
        else:
            status = build_info['status']
        build_url = build_info['url']
        jobs_buildinfo.append(
            '{}: {} - {}'.format(job, status, build_url))
    store.save()

    if not jobs_buildinfo:
        jobs_buildinfo.append('NOT BUILT')

    return templatekw.showlist('build_status', jobs_buildinfo, args)

try:
    from hgext.show import showview
except ImportError:
    pass
else:
    from mercurial import cmdutil, formatter, graphmod

    tmpl = '{label("changeset.{phase}{if(troubles, \' changeset.troubled\')}", shortest(node, 5))} {desc|firstline} ({author|user})\n  {build_status}\n'

    @showview('jenkins')
    def showjenkins(ui, repo):
        """Jenkins build status"""
        revs = repo.revs('sort(_underway(), topo)')

        revdag = graphmod.dagwalker(repo, revs)

        ui.setconfig('experimental', 'graphshorten', True)
        spec = formatter.lookuptemplate(ui, None, tmpl)
        displayer = cmdutil.changeset_templater(ui, repo, spec, buffered=True)
        cmdutil.displaygraph(ui, repo, revdag, displayer, graphmod.asciiedges)

def extsetup(ui):
    if ui.config('jenkins', 'url'):
        templatekw.keywords['build_status'] = showbuildstatus
