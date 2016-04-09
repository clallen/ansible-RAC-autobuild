#!/bin/bash

ENV=$1
POOL=$2
INDEX=`echo $3 | tr '[:lower:]' '[:upper:]'`

if [ $# -lt 4 ]; then
        echo "Usage: `basename $0` <environment name> <pool> <index> <chassis> [chassis] [chassis] ..."
        exit 1
fi

shift 3
chassis=$@

L_ENV=`echo $ENV | tr '[:upper:]' '[:lower:]'`
U_ENV=`echo $ENV | tr '[:lower:]' '[:upper:]'`
D_IDX=`echo "ibase=16; $INDEX" | bc`

DATA_INCR=1
FRA_INCR=1
OCR_INCR=1

#echo raidcom -login raidcom Aoe4bVKR
echo raidcom lock resource -resource_name meta_resource -time 300

for ldev in {0..14}; do

        H_IDX=`echo "obase=16; $D_IDX" | bc`
	if [ $D_IDX -lt '16' ]; then
            LDEV_ID="${POOL}:0${H_IDX}"
        else
            LDEV_ID="${POOL}:${H_IDX}"
        fi

	case $ldev in
		[0-7])
			relo_opt="enable_reallocation 5"
			LDEV_NAME="${U_ENV}_DATA_0${DATA_INCR}"
			LDEV_SIZE="1024g"
			let DATA_INCR++
			;;
		[8-9]|1[0-1])
			relo_opt="enable_reallocation 5"
			LDEV_NAME="${U_ENV}_FRA_0${FRA_INCR}"
			LDEV_SIZE="100g"
			let FRA_INCR++
			;;
		1[2-4])
			relo_opt="enable_reallocation 5"
			LDEV_NAME="${U_ENV}_OCR_0${OCR_INCR}"
			LDEV_SIZE="50g"
			let OCR_INCR++
			;;
	esac

	echo raidcom reset command_status
#	echo raidcom add ldev -pool $POOL -ldev_id $LDEV_ID -offset_capacity $LDEV_SIZE
	echo raidcom add ldev -pool $POOL -ldev_id $LDEV_ID -capacity $LDEV_SIZE
	echo raidcom get command_status

        echo raidcom modify ldev -ldev_id $LDEV_ID -ldev_name $LDEV_NAME
        if [[ $POOL = "16" || $POOL = "15" ]]; then
            echo raidcom modify ldev -ldev_id $LDEV_ID -status $relo_opt
        fi
        
        for port in CL1-B CL2-B CL7-F CL8-F; do
            for host in $chassis; do
                echo raidcom add lun -port $port ${host}-pri -ldev_id $LDEV_ID
                echo raidcom add lun -port $port ${host}-sec -ldev_id $LDEV_ID
            done
        done

        let D_IDX++

done

echo raidcom unlock resource -resource_name meta_resource
#raidcom -logout
