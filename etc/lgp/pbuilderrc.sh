# Logilab lgp configuration file for pbuilder.
# Copyright (c) 2003-2009 LOGILAB S.A. (Paris, FRANCE).
# http://www.logilab.fr/ -- mailto:contact@logilab.fr

# The file in /usr/share/pbuilder/pbuilderrc is the default template.
# /etc/pbuilderrc is the one meant for editing.
#
# Read pbuilderrc.5 document for notes on specific options.

# This file is largely inspired by:
#     https://wiki.ubuntu.com/PbuilderHowto
# Thanks a lot, guys !


# Declaration of lgp suites file location
LGP_SUITES=${LGP_SUITES:-'/etc/lgp/suites'}

# Find default distributions based on LGP_SUITES file if not already specified
: ${DEBIAN_SUITES:=$(grep -B2 '^Keyring: debian' $LGP_SUITES | sed -n 's/\(Suite: \)//p')}
: ${UBUNTU_SUITES:=$(grep -B2 '^Keyring: ubuntu' $LGP_SUITES | sed -n 's/\(Suite: \)//p')}

# *** NEEDS REFACTORING ***
# FIXME make functions/scripts instead of multiple greps
# FIXME check repo availability before adding it ?
# FIXME manage error code 3 directly in lgp with error message

check_repository() {
	http_status=$(curl --write-out %{http_code} --silent --output /dev/null $1)
	if [ $http_status = "200" ]; then
		echo $1
		return 0
	fi
	return 1
}
find_lgp_distrib() {
	DIST=$1
	shift
	SUITES=$*
	RESULT=$(echo ${SUITES[@]} | sed -n "s/ /\n/gp" | grep "^$DIST$")
	if [ -n "$RESULT" ]; then
		return 0
	fi
	return 1
}

# Ugly and buggy when repository don't exist
# TODO replace by a dedicated hook
if $(find_lgp_distrib $DIST "${DEBIAN_SUITES[@]}"); then
    MIRRORSITE=${DEBIAN_MIRRORSITE}
    if [ -n "$DEBIAN_MIRROR" ]; then
        echo "W: DEBIAN_MIRROR is deprecated. Please, use DEBIAN_MIRRORSITE instead."
        echo "W: replace by 'DEBIAN_MIRRORSITE=$MIRRORSITE'"
        MIRRORSITE="http://$DEBIAN_MIRROR/debian/"
    fi
    COMPONENTS=${DEBIAN_COMPONENTS}
    if [ -f $DEBIAN_SOURCESLIST.$DIST ]; then
        eval "OTHERMIRROR=\"$(grep -v '^#\|^$' $DEBIAN_SOURCESLIST.$DIST | tr '\n' '|')\""
    elif [ -f $DEBIAN_SOURCESLIST ]; then
        eval "OTHERMIRROR=\"$(grep -v '^#\|^$' $DEBIAN_SOURCESLIST | tr '\n' '|')\""
    fi
    OTHERMIRROR=${OTHERMIRROR:-$DEBIAN_OTHERMIRROR}
elif $(find_lgp_distrib $DIST "${UBUNTU_SUITES[@]}"); then
    MIRRORSITE=${UBUNTU_MIRRORSITE}
    if [ -n "$UBUNTU_MIRROR" ]; then
        echo "W: UBUNTU_MIRROR is deprecated. Please, use UBUNTU_MIRRORSITE instead."
        echo "W: replace by 'DEBIAN_MIRRORSITE=$MIRRORSITE'"
        MIRRORSITE="http://$UBUNTU_MIRROR/ubuntu/"
    fi
    COMPONENTS=${UBUNTU_COMPONENTS}
    if [ -f $UBUNTU_SOURCESLIST.$DIST ]; then
        eval "OTHERMIRROR=\"$(grep -v '^#\|^$' $UBUNTU_SOURCESLIST.$DIST | tr '\n' '|')\""
    elif [ -f $UBUNTU_SOURCESLIST ]; then
        eval "OTHERMIRROR=\"$(grep -v '^#\|^$' $UBUNTU_SOURCESLIST | tr '\n' '|')\""
    fi
    OTHERMIRROR=${OTHERMIRROR:-$UBUNTU_OTHERMIRROR}
else
    echo "Distribution '$DIST' cannot be found in \"${LGP_SUITES}\""
    echo "Edit this file if you want create a new unlisted distribution"
    echo "This error occured in pbuilder set up"
    exit 3
fi
echo "D: MIRRORSITE=$MIRRORSITE"
echo "D: OTHERMIRROR=$OTHERMIRROR"

# *** DEPRECATED ***
# Note: files matching *_SOURCESLIST.${DIST} in the same directory can be used
#       to override generic values
# ... or set theses variables in a sources.list format (see pbuilder man page)
# They will be used in the distribution image to fetch developped packages
#DEBIAN_OTHERMIRROR=
#UBUNTU_OTHERMIRROR=

# Set a default distribution if none is used.
#: ${DIST:="$(lsb_release --short --codename)"}
#: ${DIST:="unstable"}
# Optionally use the changelog of a package to determine the suite to use if none set
# Will use generic 'unstable' distribution name
#if [ -z "${DIST}" ] && [ -r "debian/changelog" ]; then
#	DIST=$(dpkg-parsechangelog | awk '/^Distribution: / {print $2}')
#	# Use the unstable suite for Debian experimental packages.
#	if [ "${DIST}" == "experimental" -o \
#		 "${DIST}" == "UNRELEASED" -o \
#		 "${DIST}" == "DISTRIBUTION" ]; then
#		DIST="unstable"
#	fi
#	echo "Retrieve distribution from debian/changelog: $DIST"
#fi

#export DEBIAN_BUILDARCH=athlon
##############################################################################

# Don't use DISTRIBUTION directly
DISTRIBUTION="${DIST}"

# We always define an architecture to the host architecture if none set.
# Note that you can set your own default in /etc/lgp/pbuilderrc.local
# (i.e. ${ARCH:="i386"}).
: ${ARCH:="$(dpkg --print-architecture)"}
NAME="${DIST}"

DEBOOTSTRAP=${DEBOOTSTRAP:-"cdebootstrap"}
: ${DEBOOTSTRAPOPTS:-()}
#DEBOOTSTRAPOPTS=("--include" "sysv-rc" "${DEBOOTSTRAPOPTS[@]}")
#DEBOOTSTRAPOPTS=("--include" "libc6" "${DEBOOTSTRAPOPTS[@]}")
case "${DEBOOTSTRAP}" in
	"debootstrap")
		DEBOOTSTRAPOPTS=("--variant=buildd" "${DEBOOTSTRAPOPTS[@]}")
		DEBOOTSTRAPOPTS=("--verbose" "${DEBOOTSTRAPOPTS[@]}")
		;;
	"cdebootstrap")
		DEBOOTSTRAPOPTS=("--flavour=build" "${DEBOOTSTRAPOPTS[@]}")
		DEBOOTSTRAPOPTS=("--debug" "-v" "${DEBOOTSTRAPOPTS[@]}")
		DEBOOTSTRAPOPTS=("--allow-unauthenticated" "${DEBOOTSTRAPOPTS[@]}")
		# don't work as expected
		#DEBOOTSTRAPOPTS=("--suite-config=${LGP_SUITES}")
		;;
esac

if [ "$PBCURRENTCOMMANDLINEOPERATION" = "create" -a -n "${ARCH}" ]; then
	NAME="$NAME-$ARCH"
	DEBOOTSTRAPOPTS=("--arch" "$ARCH" "${DEBOOTSTRAPOPTS[@]}")
fi

if [ "$PBCURRENTCOMMANDLINEOPERATION" = "create" -o "$PBCURRENTCOMMANDLINEOPERATION" = "update" ]; then
	echo "D: $DEBOOTSTRAP ${DEBOOTSTRAPOPTS[@]} ${DIST}"
fi

# Don't use BASETGZ directly
# Set the BASETGZ using lgp IMAGE environment variable
: ${IMAGE:="/var/cache/lgp/buildd/$NAME.tgz"}
BASETGZ=${IMAGE}
if [ ! -d $(dirname $BASETGZ) ]; then
	echo "Error: parent directory '$(dirname $BASETGZ)' has not been fully created" >/dev/stderr
	exit 2
fi
if [ ! -r ${BASETGZ} -a "$PBCURRENTCOMMANDLINEOPERATION" != "create" ]; then
	echo "Error: pbuilder image '$BASETGZ' has not been created" >/dev/stderr
	exit 2
fi

USEPROC=yes
USEDEVPTS=yes
USEDEVFS=no

# BINDMOUNTS is a space separated list of things to mount inside the chroot.
# Don't use array aggregation here
BINDMOUNTS="/sys"
if [ "$PBCURRENTCOMMANDLINEOPERATION" = "login" -o "$PBCURRENTCOMMANDLINEOPERATION" = "scripts" ]; then
	# Default value set to be used by hooks
	export BUILDRESULT="${HOME}/dists/${DIST}"
fi
if [ -d "${BUILDRESULT}" ]; then
	BINDMOUNTS="${BINDMOUNTS} $BUILDRESULT"
fi

# Using environmental variables for running pbuilder for specific distribution
# http://www.netfort.gr.jp/~dancer/software/pbuilder-doc/pbuilder-doc.html#ENVVARDISTRIBUTIONSWITCH
APTCACHE="/var/cache/pbuilder/${DIST}/aptcache/"

#REMOVEPACKAGES="lilo bash"
#EXTRAPACKAGES=gcc3.0-athlon-builder

# Use DEBOOTSTRAPOPTS instead ?
# "debconf: delaying package configuration, since apt-utils is not installed"
EXTRAPACKAGES="apt-utils nvi"

# command to satisfy build-dependencies; the default is an internal shell
# implementation which is relatively slow; there are two alternate
# implementations, the "experimental" implementation,
# "pbuilder-satisfydepends-experimental", which might be useful to pull
# packages from experimental or from repositories with a low APT Pin Priority,
# and the "aptitude" implementation, which will resolve build-dependencies and
# build-conflicts with aptitude which helps dealing with complex cases but does
# not support unsigned APT repositories
PBUILDERSATISFYDEPENDSCMD="/usr/lib/pbuilder/pbuilder-satisfydepends"

#Command-line option passed on to dpkg-buildpackage.
#DEBBUILDOPTS will be overriden by lgp
#PDEBUILD_PBUILDER=pbuilder
#USE_PDEBUILD_INTERNAL=yes

# pdebuild wants invoke debsign command after building
# We use pdebuild only for package debugging. Say 'no' (or commented) here.
#AUTO_DEBSIGN=no

# Hooks directory for pbuilder
# Force an alternate value of hookdir since hooks can be sensitive
HOOKDIR=${HOOKDIR:+"/var/lib/lgp/hooks"}

# APT configuration files directory
_APTCONFDIR="/etc/lgp/apt.conf.d"
if [[ -n "$(ls $_APTCONFDIR 2>/dev/null)" ]]; then
	APTCONFDIR=$_APTCONFDIR
fi

# the username and ID used by pbuilder, inside chroot. Needs fakeroot, really
#BUILDUSERID=$SUDO_UID
BUILDUSERID=1234
#BUILDUSERNAME=$SUDO_USER
BUILDUSERNAME=pbuilder
BUILDRESULTUID=$SUDO_UID

# Set the PATH I am going to use inside pbuilder
#export PATH="/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/X11R6/bin"

# SHELL variable is used inside pbuilder by commands like 'su'; and they need sane values
export SHELL="/bin/sh"
# Set informative prompt
export PS1="(lgp) ${DIST}/${ARCH} \$ "

# enable pkgname-logfile
#PBUILDER_BUILD_LOGFILE="${BUILDRESULT}/"$(basename "${PACKAGENAME}" .dsc)"${PKGNAME_LOGFILE_EXTENTION}"
PKGNAME_LOGFILE_EXTENTION="_${ARCH}_${DIST}$(python -c 'from logilab.devtools.lgp import BUILD_LOG_EXT; print BUILD_LOG_EXT')"
PKGNAME_LOGFILE=yes

# for pbuilder debuild
BUILDSOURCEROOTCMD="fakeroot"
PBUILDERROOTCMD="sudo"

# No debconf interaction with user by default
export DEBIAN_FRONTEND=${DEBIAN_FRONTEND:="noninteractive"}
