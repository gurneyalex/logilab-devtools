#!/usr/bin/python
# -*- coding: utf-8

START_TE_RQL = """\
INSERT TestExecution TE:
  TE branch %(changeset)s,
  TE using_environment PE,
  TE using_config TC,
  TE execution_of R
WHERE
  TC use_recipe R,
  PE local_repository REPO,
  CS from_repository REPO,
  CS changeset %(changeset)s ,
  TC label %(label)s
"""

def create_test_execution(client, changesets, label, **kwargs):
    rql = START_TE_RQL
    args = {'label': label}
    if kwargs:
        options = u'\n'.join(u"%s=%s" % kv for kv in kwargs.items())
        rql1, rql2 = rql.split('WHERE')
        rql = '{0}, TE options %(options)s WHERE {1}'.format(rql1, rql2)
        args['options'] = options

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
