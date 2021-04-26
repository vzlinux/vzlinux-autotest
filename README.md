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
