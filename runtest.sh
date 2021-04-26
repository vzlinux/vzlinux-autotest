#!/bin/bash

# Copyright (c) 2017-2021, Virtuozzo International GmbH
#
# Our contact details: Virtuozzo International GmbH, Vordergasse 59, 8200
# Schaffhausen, Switzerland.

usage() {
[ $# == 1 ] && echo -e "$1"
cat <<EOT
usage:
$0 [service] [package] [distro-release]
$0 [apps] [package] [distro-release]
$0 [add user $(whoami) to docker group]
$0 [example: sh runtest.sh apps firefox vl7] or [sh runtest.sh service realmd vl7] or [sh runtest.sh binapps vim-enhanced vl7]
EOT
}

# package to check
PKG="$2"
IRUN="$1"
DISTRO_RELEASE="$3"

check_in_list() {
if [[ "$IRUN" == "apps" ]]; then
FILE_PREFIX="desktop"
fi
if [[ "$IRUN" == "service" ]]; then
FILE_PREFIX="service"
fi
PATTERN="$PKG"
FILE=""$FILE_PREFIX"-"$DISTRO_RELEASE".list"

if grep -q $PATTERN $FILE;
 then
     echo "Here are the Strings with the Pattern '$PATTERN':"
     echo "proceed normal test"
 else
     echo "Error: The Pattern '$PATTERN' was NOT Found in '$FILE'"
     echo "Exiting..."
     exit 0
fi
}

run_service() {
	echo "check that service exist in service-vl7.list"
	check_in_list
	# need to run container with systemd-stuff
	docker run --privileged -td --name servicetest -v /tmp/results:/tmp/results/ vzlinux/servicetest /sbin/init
	# attach to container and exec script
	docker exec -it servicetest /run-service.sh "$PKG"
	# stop docker container before destroying
	docker stop servicetest
	# wipe used docker container, we always need clean environment
	docker rm -v $(docker ps -a -q -f status=exited)
	}

run_apps() {
	# run app check
	echo "compare app with list desktop-vl7.list"
	check_in_list
	docker run -it --rm --privileged=true -e PKG="$PKG" -v /tmp/results:/tmp/results/ vzlinux/apptest
}
run_binapps() {
	# run app check
	echo "test app not from *desktop lists files"
	docker run -it --rm --privileged=true -e PKG="$PKG" -v /tmp/results:/tmp/results/ vzlinux/binapps
}

main() {
if [[ "$1" == "service" ]]; then
run_service $@
fi
if [[ "$1" == "apps" ]]; then
run_apps $@
fi
if [[ "$1" == "binapps" ]]; then
run_binapps $@
fi

# help
if [ "$1" == "-h" ]; then
  usage
  exit 0
fi
}

main "$@"
