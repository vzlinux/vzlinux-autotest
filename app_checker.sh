#!/bin/bash
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

run_executable(){
echo -e "searching for a binary file"
binary_file=$(cat $PACKAGE_QL | grep "/usr/bin/\|/bin/\|/sbin/\|/usr/sbin/")
if [ $? -eq 1 ]
then
echo "Package $PKG not contain files in bindirs (/usr/bin/,/bin/,/sbin, etc)"
else
echo -e "run ldd on $PKG executable binaries" >> $RESULT_DIR/app_test_$PKG
$LDD_RUN $binary_file | grep "$PATTERN" >> $RESULT_DIR/ld_log_$PKG
$FILE_RUN $binary_file >> $RESULT_DIR/app_test_$PKG
fi
}

run_libraries(){
echo -e "searching package libs"
library_file=$(cat $PACKAGE_QL | grep ".so")
if [ $? -eq 1 ]
then
echo "Package $PKG not contain libs (*.so)"
else
echo -e "run ldd on $PKG libraries files" >> $RESULT_DIR/app_test_$PKG
$LDD_RUN $library_file | grep "$PATTERN" >> $RESULT_DIR/ld_log_$PKG
$FILE_RUN $library_file >> $RESULT_DIR/app_test_$PKG
fi
}

rpmql_package=$(rpm -q -l $PKG > $PACKAGE_QL)
result=$?
if [ $result -eq 0 ]; then
        echo "rpm $PKG exist, let's proceed"
        desktop_file=$(cat $PACKAGE_QL | grep ".desktop")
        result=$?
        if [ $result -eq 0 ]; then
                command_to_run=$(cat $desktop_file | grep '^Exec'| sed 's/^Exec=//')
		run_libraries
		if [ "$(grep 'not found' $RESULT_DIR/ld_log_$PKG)" ]; then
			echo "not ok"
			echo "Package does not working properly, check libs"
        		echo "$PKG" >> $RES_FAILED_TO_CHECK
		else
			echo "ldd says that's $PKG is good"
		fi
                echo "$command_to_run extracted from $desktop_file"
		echo "test executable from python script"
        else
		run_executable
		run_libraries
		if [ "$(grep 'not found' $RESULT_DIR/ld_log_$PKG)" ]; then
			echo "not ok"
			echo "Package does not working properly, check libs"
        		echo "$PKG" >> $RES_FAILED_TO_CHECK
		else
			echo "ldd says that's $PKG is good"
		fi
		
#                exec $binary_file & sleep $DEFAULT_TIMEOUT && kill -3 $!

        fi
else
        echo "$PKG not exist" >> $RES_FAILED_TO_CHECK
fi
}
check_apps
