#!/bin/bash

ENV=$1
L_ENV=`echo $ENV | tr '[:upper:]' '[:lower:]'`
U_ENV=`echo $ENV | tr '[:lower:]' '[:upper:]'`

OFS=$IFS
#IFS="\n"
IFS='
'

if [ $# -ne 1 ]; then
        echo "Usage: `basename $0` <environment name>"
        exit 1
fi

# Add Devices to Virtual Disk Service
for line in $(ls /dev/rdsk* | /HORCM/usr/bin/inqraid -fnx -CLI | /usr/gnu/bin/egrep -i "\<${U_ENV}_(data|fra|ocr)"); do
#    echo $line | gawk -v env=$U_ENV '$9~/"env"/ {name=$9}
    echo $line | gawk '{print "ldm add-vdsdev -f mpgroup="$9"_1 /dev/dsk/"$1" "$9"@primary-vds0";
                        print "ldm add-vdsdev -f mpgroup="$9"_1 /dev/dsk/"$1" "$9"@secondary-vds0";
                        print "ldm add-vdsdev -f mpgroup="$9"_2 /dev/dsk/"$1" "$9"@primary-vds1";
                        print "ldm add-vdsdev -f mpgroup="$9"_2 /dev/dsk/"$1" "$9"@secondary-vds1";
                       }'
done

IFS=$OFS
