.. -*- coding: utf-8 -*-

Logilab's development tools
===========================

Set of tools which aims to help the development process, including :

  * tools to check and build source and/or Debian packages

  * provides integration assistance to work with CubicWeb_, Mercurial_
    and GuestRepo_.

Set of `elisp` goodies including :

  * an emacs mode for pycover files
  * an emacs mode for ChangeLog files
  * a small set of emacs shortcuts used at logilab


ingrsh.(z)sh
------------

A shell library to source. It provides a ``ingrsh`` command that moves
the current working directory into the given shell repository and set
the ``PYTHONPATH`` and ``CDPATH`` environment variables accordingly.

The ``GUESTREPODIR`` environment variable defines where to search for for
shells (default to ``$HOME/hg/grshells/``)


grmerge/tagsmerge
-----------------

Merge tools to be used by Mercurial_, for .hgguestrepo and .hgtags files
respectively.

They must be activated from a Mercurial_ configuration file::

  [merge-patterns]
  .hgguestrepo = grmerge

  [merge-tools]
  grmerge.executable = path/to/grmerge
  grmerge.args = $local $base $other -o $output

hgext/jenkins
-------------

A Mercurial_ extension to show Jenkins build information for changesets.

hgext/jpl.py
------------

A Mercurial_ extension that eases interaction with a JPL forge.

The extension should be enabled from a Mercurial_ configuration file::

  [extensions]
  jpl = path/to/hgext/jpl/
  # or, if it has been installed via the debian package:
  jpl =

  [jpl]
  endpoint = http://www.cubicweb.org

The ``endpoint`` refers to a configuration entry in your cwclientlib_
config setup.  See cwclientlib_ documentation for more informations.

.. note::

  You can specify a default ``jpl/endpoint`` value in your main
  Mercurial configuration file (``~/.hgrc`` for Linux systems).  Then
  the local configuration file (``path/to/repository/.hg/hgrc``) can
  override this setting.


.. warning:: This version of logilab-devtools **do not** read
  authentication credentials from the mercurial config files any more;
  it fully relies on cwclientlib_ for access and authentication
  towards the cubicweb instance.

  Any mercurial configuration like::

    [lgl]
    forge-url = <url>
    auth-xxx = xxx

  should be replaced by::

    [jpl]
    endpoint = <url> # or the endpoint ID

  plus a configuration entry in your ``~/.config/cwclientlibrc`` file in which
  auth credentials are set. See cwclientlib_ documentation.


Commands
~~~~~~~~

:ask-review:
  Allows to ask review for a Patch produced by a changeset, eg.::

    $ hg ask-review # default to working directory's parent revision
    $ hg ask-review -r "draft() and ::."

:assign:
  Assign patches corresponding to specified revisions to a committer.

:backlog:
  Show the backlog (draft changesets) of specified committer.

:list-tc:
  List TestConfig available for project linked to the repository.

:make-ticket:
  Create new tickets for the specified revisions.

:show-review:
  Show review status for patches corresponding to specified revisions, eg.::

    $ hg show-review  -r 82071f767cb8 -T
    https://www.cubicweb.org/5457568 82071f767cb8   [applied]       abegey
    [schemas] cwuri should be read-only

    #82071f767cb8 nologin env/quick: partial
    #82071f767cb8 cubicweb-newsaggregator env/quick: failure
    #82071f767cb8 ner test env/quick: partial
    #82071f767cb8 person env/quick: success

:start-test:
  Start Apycot tests for the given revisions, eg.::

    $ hg start-test -r . -l "buildexp cwo" -o publish_host=publish -o upload_host=upload \
    -o debian.repository=apycot -o lgp_sign=yes -o lgp_suffix=yes

:tasks:
  Displays tasks requested by reviewers on a patch on a forge.


Revset functions
~~~~~~~~~~~~~~~~

These predicates retrieve information from the project's forge
(cubicweb-jpl instance) and are exposed as revset functions.

:tasks:
  Changesets linked to tasks to be done.

:reviewed:
  Changesets that are linked to reviewed patches in the forge

:inversion:
  Changesets that are linked to patches linked to tickets of given version+project

Examples::

  $ hg log -r "reviewed()"
  $ hg log -r "inversion(3.18.0)"
  $ # display tasks on patches that are meant to be in next 3.20.8 version:
  $ hg tasks -r "tasks() and inversion(3.20.8)"
  $ # display patches ready for integration in 3.20.8:
  $ hg show-review -r "reviewed() and inversion(3.20.8)"
  $ # are there any pending commit on my branch that is not at his place?
  $ hg log -r "draft() and ::. keyword(closes) and not inversion(3.20.8)"


Templates
~~~~~~~~~

:tasks:
  List of Strings. The text of the tasks and comments of a patch.

  Examples:

  - display all tasks (and comments) of every patch::

      $ hg log --template='{tasks}\n'

  - display the first line of the description and the first line of
    every task not yet done for draft changesets written by alain that
    are not yet reviewed::

      $ hg log -G \
      --rev 'draft() and author(alain) and tasks() and not(reviewed())' \
      --template='{desc|firstline}\n{tasks % "{task|firstline}\n"}'




.. _CubicWeb: http://www.cubicweb.org
.. _Mercurial: http://mercurial.selenic.com
.. _GuestRepo: https://bitbucket.org/selinc/guestrepo
.. _cwclientlib: https://www.cubicweb.org/projhect/cwclientlib
