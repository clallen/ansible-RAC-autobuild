#!/bin/bash

NAME=$1
VLAN=$2
ENV=$3
P_VLAN1=$4
P_VLAN2=$5

L_ENV=$(echo $ENV | tr '[:upper:]' '[:lower:]')
U_ENV=$(echo $ENV | tr '[:lower:]' '[:upper:]')

CORES=1
MEM="16G"
MTU="1500"

if [ $# -lt 3 ]; then
        echo "Usage: `basename $0` <OVM Domain Name> <Public Net VLAN> <Environment Name> [Privnet0 VLAN] [Privnet1 VLAN]"
        exit 1
fi

#Create Guest Domain
echo ldm add-domain $NAME
echo ldm set-core $CORES $NAME
echo ldm add-memory --auto-adj $MEM $NAME

#Configure Guest Domain networking
echo ldm add-vnet id=0 mgmt0 primary-vsw0 $NAME
echo ldm add-vnet id=1 pvid=$VLAN mtu=${MTU} linkprop=phys-state pubnet0 primary-vsw1 $NAME
echo ldm add-vnet id=2 pvid=$VLAN mtu=${MTU} linkprop=phys-state pubnet1 secondary-vsw1 $NAME
if [ -z $P_VLAN1 ]; then
    echo ldm add-vnet id=3 mtu=${MTU} linkprop=phys-state privnet0 primary-vsw2 $NAME
    echo ldm add-vnet id=4 mtu=${MTU} linkprop=phys-state privnet1 secondary-vsw2 $NAME
else
    echo ldm add-vnet id=3 pvid=$P_VLAN1 mtu=${MTU} linkprop=phys-state privnet0 primary-vsw2 $NAME
    echo ldm add-vnet id=4 pvid=$P_VLAN2 mtu=${MTU} linkprop=phys-state privnet1 secondary-vsw2 $NAME
fi

#Add Virtual Disk to Guest Domain

case $NAME in
    *1)
        NODE=1
        VDS='vds0'
        ;;
    *2)
        NODE=2
        VDS='vds1'
        ;;
    *3)
        NODE=3
        VDS='vds2'
        ;;
    *4)
        NODE=4
        VDS='vds3'
        ;;
    *)
        echo "Invalid domain of: $NAME"
        echo "Not adding RAC ASM storage to domain"
        NODE=0
        ;;
esac

if [ $NODE -ne 0 ]; then
    #OS and Software Disks
    echo "#Adding OS storage..."
echo     ldm add-vdisk id=0 rootdisk0 ${NAME}-rootdisk0@primary-${VDS} $NAME
echo     ldm add-vdisk id=1 appdisk0 ${NAME}-appdisk0@primary-${VDS} $NAME
echo     ldm add-vdisk id=2 gidisk_12.1.0.2 ${NAME}-gidisk0@primary-${VDS} $NAME
echo     ldm add-vdisk id=3 dbdisk_12.1.0.2 ${NAME}-dbdisk0@primary-${VDS} $NAME
echo     ldm add-vdisk id=99 ${NAME}-cmd0 ${NAME}-cmd0@primary-${VDS} $NAME
    echo "#Done."
    
    #RAC ASM DISKS
    echo "#Adding RAC ASM storage..."
echo     ldm add-vdisk id=10 ${L_ENV}_data_01 ${U_ENV}_DATA_01@primary-${VDS} $NAME
echo     ldm add-vdisk id=11 ${L_ENV}_data_02 ${U_ENV}_DATA_02@primary-${VDS} $NAME
echo     ldm add-vdisk id=12 ${L_ENV}_data_03 ${U_ENV}_DATA_03@primary-${VDS} $NAME
echo     ldm add-vdisk id=13 ${L_ENV}_data_04 ${U_ENV}_DATA_04@primary-${VDS} $NAME
echo     ldm add-vdisk id=14 ${L_ENV}_data_05 ${U_ENV}_DATA_05@primary-${VDS} $NAME
echo     ldm add-vdisk id=15 ${L_ENV}_data_06 ${U_ENV}_DATA_06@primary-${VDS} $NAME
echo     ldm add-vdisk id=16 ${L_ENV}_data_07 ${U_ENV}_DATA_07@primary-${VDS} $NAME
echo     ldm add-vdisk id=17 ${L_ENV}_data_08 ${U_ENV}_DATA_08@primary-${VDS} $NAME
echo     ldm add-vdisk id=18 ${L_ENV}_fra_01 ${U_ENV}_FRA_01@primary-${VDS} $NAME
echo     ldm add-vdisk id=19 ${L_ENV}_fra_02 ${U_ENV}_FRA_02@primary-${VDS} $NAME
echo     ldm add-vdisk id=20 ${L_ENV}_fra_03 ${U_ENV}_FRA_03@primary-${VDS} $NAME
echo     ldm add-vdisk id=21 ${L_ENV}_fra_04 ${U_ENV}_FRA_04@primary-${VDS} $NAME
echo     ldm add-vdisk id=90 ${L_ENV}_ocr_01 ${U_ENV}_OCR_01@primary-${VDS} $NAME
echo     ldm add-vdisk id=91 ${L_ENV}_ocr_02 ${U_ENV}_OCR_02@primary-${VDS} $NAME
echo     ldm add-vdisk id=92 ${L_ENV}_ocr_03 ${U_ENV}_OCR_03@primary-${VDS} $NAME
    echo "#Done."
fi

#Set EEPROM vars
#NET=`ldm list-bindings $NAME | grep RIO | awk '{print "/"$1}'`
IP=`host ${NAME}-mgmt | awk '{print $4}'`

#ldm set-var "nvramrc=devalias net $NET" $NAME
#ldm set-var "use-nvramrc?=true" $NAME
echo ldm set-domain cpu-arch=migration-class1 $NAME
echo ldm set-var "auto-boot?=false" $NAME
echo ldm set-var "network-boot-arguments=host-ip=${IP},router-ip=130.164.28.1,subnet-mask=255.255.255.0,hostname=${NAME}-mgmt,file=http://130.164.51.133:5555/cgi-bin/wanboot-cgi" $NAME

#Bind the domain
echo ldm bind-domain $NAME

#Print MAC Address for AI configuration
#MAC=`ldm list -o network $NAME | awk '$1~/mgmt0/ {print $5}'`
#echo "echo \"MAC Address for AI: $MAC\""
