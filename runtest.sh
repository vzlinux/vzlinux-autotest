#!/bin/bash
usage() {
[ $# == 1 ] && echo -e "$1"
cat <<EOT
usage:
$0 [service] [package] [distro-release]
$0 [apps] [package] [distro-release]
$0 [add user $(whoami) to docker group]
EOT
}

# package to check
PKG="$2"

run_service() {
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
	docker run -it --rm --privileged=true -e PKG="$PKG" -v /tmp/results:/tmp/results/ vzlinux/apptest
}

main() {
if [[ "$1" == "service" ]]; then
run_service $@
fi
if [[ "$1" == "apps" ]]; then
run_apps $@
fi

# help
if [ "$1" == "-h" ]; then
  usage
  exit 0
fi
}

main "$@"
