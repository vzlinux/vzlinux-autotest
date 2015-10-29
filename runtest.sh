docker run --privileged -td --name servicetest -v /tmp/results:/tmp/results/ vzlinux/servicetest /sbin/init
docker exec -it servicetest /run-autotest.sh "$@"
docker stop servicetest
docker rm -v $(docker ps -a -q -f status=exited)
