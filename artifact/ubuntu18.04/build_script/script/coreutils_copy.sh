#!/bin/bash

function copy
{
    list_file=$1
    while IFS='' read -r line || [[ -n "$line" ]]; do
        name=$(echo $line | awk -F' ' '{print $1}')
        filename=$(basename "${line}")

	echo cp /dataset/$filename $name
	cp /dataset/$filename $name

    done < "$list_file"

}
copy coreutils-9.1_list.txt
