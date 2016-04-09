#!/bin/bash

NAME=$1
CU=`echo $2 | tr '[:lower:]' '[:upper:]'`
INDEX=`echo $3 | tr '[:lower:]' '[:upper:]'`
LDEV_SIZE="50g"
[ "$HORCMINST" == 5 ] && POOL="35" || POOL="36"

if [ $# -lt 4 ]; then
        echo "Usage: `basename $0` <hostname> <CU> <index> <chassis> [chassis] [chassis] ..."
        exit 1
fi

shift 3
chassis=$@

D_IDX=`echo "ibase=16; $INDEX" | bc`

for ldev in {1..4}; do

	H_IDX=`echo "obase=16; $D_IDX" | bc`
	if [ $D_IDX -lt '16' ]; then
            LDEV_ID="${CU}:0${H_IDX}"
        else
            LDEV_ID="${CU}:${H_IDX}"
        fi

	echo raidcom reset command_status
#	echo raidcom add ldev -pool $POOL -ldev_id $LDEV_ID -offset_capacity $LDEV_SIZE
	echo raidcom add ldev -pool $POOL -ldev_id $LDEV_ID -capacity $LDEV_SIZE
	echo raidcom get command_status

	echo raidcom modify ldev -ldev_id $LDEV_ID -ldev_name ${NAME}_OS_0${ldev}

	for port in CL1-B CL2-B CL7-F CL8-F; do
            for host in $chassis; do
		echo raidcom add lun -port $port ${host}-pri -ldev_id $LDEV_ID
		echo raidcom add lun -port $port ${host}-sec -ldev_id $LDEV_ID
            done
        done
		
	let D_IDX++
done
