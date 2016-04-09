#!/bin/bash

HOST=$1
[ "$HORCMINST" == 5 ] && CMD="c0t60060E801604710000010471000035FFd0s2" || CMD="c0t60060E80166BCD0000016BCD000036FFd0s2" 

if [ $# -ne 1 ]; then
        echo "Usage: `basename $0` <hostname>"
        exit 1
fi

case $HOST in
    *1)
        VDS=vds0
        ;;
    *2)
        VDS=vds1
        ;;
    *3)
        VDS=vds2
        ;;
    *4)
        VDS=vds3
        ;;
    *)
        VDS=vds0
        ;;
esac

OFS=$IFS
#IFS="\n"
IFS='
'

for line in `ls /dev/rdsk* | /HORCM/usr/bin/inqraid -fnx -CLI | grep -i $HOST`; do
    echo $line | gawk -v host=$HOST -v vds=$VDS '$9~/OS_01/ {disk="rootdisk0"}
                                     $9~/OS_02/ {disk="appdisk0"}
                                     $9~/OS_03/ {disk="gidisk0"}
                                     $9~/OS_04/ {disk="dbdisk0"}
                                     
                                     {print "ldm add-vdsdev -f mpgroup="host"-"disk" /dev/dsk/"$1" "host"-"disk"@primary-"vds}
                                     {print "ldm add-vdsdev -f mpgroup="host"-"disk" /dev/dsk/"$1" "host"-"disk"@secondary-"vds}
                                    '
done

IFS=$OFS

echo ldm add-vdsdev -f mpgroup=${HOST}-cmd0 /dev/dsk/${CMD} ${HOST}-cmd0@primary-${VDS}
echo ldm add-vdsdev -f mpgroup=${HOST}-cmd0 /dev/dsk/${CMD} ${HOST}-cmd0@secondary-${VDS}
