# The section in a .desktop file we need.
SECTION="Desktop Entry"

# The directory with the results
RESULT_DIR="/tmp/results"
PACKAGE_QL="/tmp/rpmql_$PKG"
LDD_RUN="/usr/bin/ldd"
FILE_RUN="/usr/bin/file"
PATTERN="not found"
RES_FAILED_TO_CHECK="$RESULT_DIR/failed_to_check"

get_installed_list(){
echo "Returns the list of installed packages as a set."
list=$(rpm -qa --queryformat '%{NAME}\n' >> /tmp/package_list)
}

#get_installed_list
install_remove_pkg(){
rpmql_package=$(rpm -q -l $PKG > $PACKAGE_QL)
result=$?
if [ $result -eq 0 ]; then
echo "rpm $PKG already installed"
else
echo "installing $PKG"
sudo yum install -y $PKG
fi
}
install_remove_pkg

check_apps(){
echo "Processing $PKG"
if [ ! -d "$RESULT_DIR" ]; then
  mkdir -p $RESULT_DIR
fi
rpmql_package=$(rpm -q -l $PKG > $PACKAGE_QL)
result=$?
if [ $result -eq 0 ]; then
        echo "rpm $PKG exist, let's proceed"
        desktop_file=$(cat $PACKAGE_QL | grep ".desktop")
        result=$?
        if [ $result -eq 0 ]; then
                command_to_run=$(cat $desktop_file | grep '^Exec'| sed 's/^Exec=//')
                echo "$command_to_run extracted from $desktop_file"
		echo "test me from python script"
#		xvfb-run $command_to_run & sleep $DEFAULT_TIMEOUT && kill -9 $!
        else
                binary_file=$(cat $PACKAGE_QL | grep "/usr/bin/\|/bin/\|/sbin/\|/usr/sbin/")
		$LDD_RUN $binary_file | grep "$PATTERN" >> $RESULT_DIR/ld_log_$PKG
		if [ "$(grep 'not found' /tmp/ld_log_$PKG)" ]; then
			echo "not ok"
			echo "Package does not working properly, check libs"
        		echo "$PKG" >> $RES_FAILED_TO_CHECK
		else
			echo -e "run ldd on $PKG" >> $RESULT_DIR/app_test_$PKG
			$LDD_RUN $binary_file >> $RESULT_DIR/app_test_$PKG
			echo -e "run file on $PKG" >> $RESULT_DIR/app_test_$PKG
			$FILE_RUN $binary_file >> $RESULT_DIR/app_test_$PKG
			echo "ldd says that's $PKG is good"
		fi
		
#                exec $binary_file & sleep $DEFAULT_TIMEOUT && kill -3 $!

        fi
else
        echo "$PKG not exist" >> $RES_FAILED_TO_CHECK
fi
}
check_apps
