A set of simple scripts that checks packages with .desktop and .service files inside to ensure that corresponding programs
and services can be launched.

Once we build a new version of package into VzLinux repos, such tests are launched automatically for it.


= Test Launcher =

launcher.py is the main script (packaged as "vzlinux-autotest" binary into the vzlinux-autotest package inside VzLinux repos).

It calls check_apps_in_chroot.py script to check if applications can be launched using command lines from their desktop files
and check_services_in_vm.py to check if services works.

A set of desktop files & services to be checked is prepared in semi-automated way - we just dump all packages with desktop
or service files inside and check if the tests can be launched for them


= Docker Part (not maintained) =

docker autotester

How to build me?

* docker build --tag=vzlinux/autotest .

How to run me?

* docker run -it --rm --privileged=true -e PKG="xterm" -e PLATFORM="vzlinux-7" -e TARGET="apps" vzlinux/autotest


Mount log directory volume to the host system

* docker run -it --rm --privileged=true -e PKG="xterm" -e PLATFORM="vzlinux-7" -e TARGET="apps" -v /tmp/:/var/log/vzlinux-autotests/ vzlinux/autotest

* docker run -it --rm --privileged=true -e PKG="thunderbird" -v /tmp/results:/tmp/results/ vzlinux/autotest

Feel free to change PKG to any package from list according to vzlinux platform

Don't forgot to wipe old containers from aufs layers

* docker rm -v $(docker ps -a -q -f status=exited)

TODO:

* save results into target folder

* replace launcer.py with bash-script

docker run --privileged -td --name servicetest vzlinux/servicetest /sbin/init

docker exec -it servicetest /run-autotest.sh PKG=tuned
