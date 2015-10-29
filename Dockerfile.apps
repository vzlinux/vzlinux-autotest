FROM vzlinux/vztester
MAINTAINER Alex Stefanov-Khryukin <akhryukin@parallels.com>

RUN yum update -y \
    && yum upgrade -y \
    && yum install -y sudo which python-lockfile python-psutil xorg-x11-server-Xvfb \
    && adduser vztester \
    && echo "%vztester ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers \
    && mkdir -p /usr/share/vzlinux-autotest/

WORKDIR ["/home/vztester"]

USER vztester
ENV HOME /home/vztester

ADD ./check_apps_in_chroot.py /usr/share/vzlinux-autotest/check_apps_in_chroot.py
ADD ./run-autotest.sh /run-autotest.sh

CMD ["/run-autotest.sh"]
