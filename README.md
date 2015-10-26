docker autotester

How to build me?
docker build --tag=vzlinux/autotest .

How to run me?
docker run -it --rm --privileged=true vzlinux/autotest

Don't forgot to wipe old containers from aufs layers
docker rm -v $(docker ps -a -q -f status=exited)
