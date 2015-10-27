FROM centos:centos7
MAINTAINER Alex Stefanov-Khryukin <akhryukin@parallels.com>


RUN yum update -y \
    && yum upgrade -y \
    && yum install -y epel-release \
    && yum install -y mock sudo python-lockfile python-psutil \
    && echo "config_opts['use_host_resolv'] = True" >> /etc/mock/site-defaults.cfg \
    && adduser vztester \
    && usermod -a -G mock vztester \
    && echo "%mock ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers \
    && mkdir -p /usr/share/vzlinux-autotest/

WORKDIR ["/home/vztester"]
VOLUME ["/var/log/vzlinux-autotests/"]

USER vztester
ENV HOME /home/vztester

ADD ./check_apps_in_chroot.py /usr/share/vzlinux-autotest/check_apps_in_chroot.py
ADD ./mock/vzlinux-6-autotest-x86_64.cfg /etc/mock/
ADD ./mock/vzlinux-7-autotest-x86_64.cfg /etc/mock/
ADD ./launcher.py /usr/bin/test_launcher.py
ADD ./run-autotest.sh /run-autotest.sh

CMD ["/run-autotest.sh"]
