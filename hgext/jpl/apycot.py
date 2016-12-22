#!/usr/bin/python
# -*- coding: utf-8

START_TE_RQL = """\
INSERT TestExecution TE:
  TE branch %(changeset)s,
  TE using_environment PE
WHERE
  PE local_repository REPO,
  CS from_repository REPO,
  CS changeset %(changeset)s
"""


def create_test_execution(client, changesets, tcname=None, **kwargs):
    args = {}
    rql1, rql2 = START_TE_RQL.split('WHERE')
    if kwargs.pop('keep_archive', False):
        rql1 = rql1 + ', TE keep_archive TRUE'
    script = kwargs.pop('script', None)
    if script:
        rql1 = rql1 + ', TE script %(script)s'
        args['script'] = open(script, 'r').read().encode('utf-8')
    if tcname:
        rql1 += ', TE using_config TC, TE execution_of R'
        rql2 += ', TC use_recipe R, TC name %(tcname)s'
        args['tcname'] = tcname
    if kwargs:
        rql1 = rql1 + ', TE options %(options)s'
        args['options'] = u'\n'.join(u"%s=%s" % kv for kv in kwargs.items())

    rql = '\n'.join((rql1, 'WHERE', rql2))
    queries = [(rql, dict(changeset=cs, **args))
               for cs in changesets]
    return client.rqlio(queries)


LIST_TC_RQL = """\
Any TCN, TCL
WHERE
  TC use_environment PE,
  PE local_repository REPO,
  CS from_repository REPO,
  CS changeset %(changeset)s ,
  TC label TCL, TC name TCN
"""


def list_tc(client, changesets):
    rql = LIST_TC_RQL
    queries = [(rql, dict(changeset=cs))
               for cs in changesets]
    rsets = client.rqlio(queries)
    result = set()
    for rset in rsets:
        for e in rset:
            result.add(tuple(e))
    return result
