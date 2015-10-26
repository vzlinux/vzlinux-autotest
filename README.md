docker autotester

How to build me?
docker build --tag=vzlinux/autotest .

How to run me?
Feel free to change PKG to any package from list according to vzlinux platform
docker run -it --rm --privileged=true -e PKG="xterm" -e PLATFORM="vzlinux-7" -e TARGET="apps" vzlinux/autotest

Don't forgot to wipe old containers from aufs layers
docker rm -v $(docker ps -a -q -f status=exited)