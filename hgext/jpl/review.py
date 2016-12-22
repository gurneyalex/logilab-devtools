#!/usr/bin/python
# -*- coding: utf-8

from cwclientlib import builders


def ask_review(client, revs):
    eids = client.rql(
        '''Any P WHERE P patch_revision R, R changeset IN ({revs}),
                       P in_state S, S name 'in-progress'
        '''.format(revs=','.join('%r' % rev for rev in revs)))
    queries = [builders.build_trinfo(eid[0], 'ask review') for eid in eids]
    return client.rqlio(queries)


def acknowledge(client, revs, msg=None):
    """Set patch reviewed OK
    """
    eids = client.rql(
        '''Any P WHERE P patch_revision R, R changeset IN ({revs}),
                       P in_state S,
                       S name IN ('pending-review', 'in-progress')
        '''.format(revs=','.join('%r' % rev for rev in revs)))
    queries = [builders.build_trinfo(eid[0], 'accept', comment=msg)
               for eid in eids]
    return client.rqlio(queries)


def show_review(client, revs, committer=None):
    query = '''\
Any PN, P, GROUP_CONCAT(CSET), N, GROUP_CONCAT(L) GROUPBY PN,P,N
WHERE
  P patch_revision R,
  R changeset IN ({revs}),
  R changeset CSET,
  P in_state S,
  S name N,
  P cwuri URI,
  P patch_name PN,
  P patch_reviewer U?,
  U login L'''
    fmt = {'revs': ','.join('%r' % rev for rev in revs)}
    if committer:
        query += ', P patch_committer PC, PC login "{committer}"'
        fmt['committer'] = committer
    query = query.format(**fmt)
    return client.rql(query)


def assign(client, revs, committer):
    """Assign patches corresponding to specified revisions to specified committer.
    """
    revstr = ','.join('%r' % rev for rev in revs)
    if revstr.count(',') > 0:
        revq = 'IN ({revs})'.format(revs=revstr)
    else:
        revq = revstr
    query = '''SET P patch_committer U WHERE P patch_revision R,
                                             R changeset {revq},
                                             U login '{login}'
            '''.format(revq=revq, login=committer)
    return client.rqlio([(query, {})])[0]


def add_reviewer(client, revs, reviewer):
    """Add a reviewer to patches corresponding to specified revisions.
    """
    revstr = ','.join('%r' % rev for rev in revs)
    if revstr.count(',') > 0:
        revq = 'IN ({revs})'.format(revs=revstr)
    else:
        revq = revstr
    query = '''SET P patch_reviewer U WHERE P patch_revision R,
                                            R changeset {revq},
                                            U login '{login}'
            '''.format(revq=revq, login=reviewer)
    return client.rqlio([(query, {})])[0]


def sudo_make_me_a_ticket(client, repo, rev, version=None, kind=None):
    query = '''
INSERT Ticket T:
   T concerns PROJ,
   T title %%(title)s,
   T type %%(type)s,
   T description %%(desc)s%s
WHERE REV from_repository REPO,
      PROJ source_repository REPO,
      REV changeset %%(cs)s%s'''
    if version:
        query %= (', T done_in V', ', V num %(version)s, V version_of PROJ')
    else:
        query %= ('', '')
    desc = repo[rev].description()
    if not desc:
        raise Exception('changeset has no description')
    # Use a public revision to identify the repository instead of the
    # given revision, otherwise we cannot create a ticket if the given
    # revision is not yet know by the forge.
    # Using the last public revision is not bullet proof, but should
    # cover most cases.
    publicrev = repo.revs('last(public() and branch(default))')
    if not publicrev:
        publicrev = repo.revs('last(public())')
    publicrev = publicrev.last()

    args = {
        'title': desc.splitlines()[0],
        'desc': desc,
        'cs': str(repo[publicrev]),
        'version': version,
        'type': kind or 'bug',
    }
    return client.rqlio([(query, args)])
