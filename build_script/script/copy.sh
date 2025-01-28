#!/bin/bash

#source code directory
src_path=/data/

#benchmark directory
work_dir=/output/

function copy
{
    package=$1
	cfg_name=$2
	dest_path=$3

    list_file=$package\_list.txt

	asm_dir=$work_dir/$package/$dest_path/asm
	bin_dir=$work_dir/$package/$dest_path/bin
	stripbin_dir=$work_dir/$package/$dest_path/stripbin


	#echo $work_dir/$package/$dest_path/

	mkdir -p $asm_dir
	mkdir -p $bin_dir
	mkdir -p $stripbin_dir

    if [ "$package" == 'spec_cpu2017' ]; then

        root_path=$src_path/$package/benchspec/CPU

        while IFS='' read -r line || [[ -n "$line" ]]; do

            a1=$(echo $line | awk -F' ' '{print $1}')
            binname=$(echo $line | awk -F' ' '{print $2}')

            [ -z "$binname" ] && binname=$(echo $a1 | awk -F'.' '{print $2}')
            #echo $binname

            target=$root_path/$a1

            cd $root_path/

            if [ -d "$a1/build/$cfg_name-m64.0000/" ]
            then
                find $a1/build/$cfg_name-m64.0000/ -name '*.s' -exec cp --parents \{\} $asm_dir \;

                cp $target/build/$cfg_name-m64.0000/$binname    $bin_dir/$a1

                cp $target/build/$cfg_name-m64.0000/$binname    $stripbin_dir/$a1

                strip $stripbin_dir/$a1

	        else
                find $a1/build/$cfg_name-m64.0000/ -name '*.s' -exec cp --parents \{\} $asm_dir \;

                cp $target/build/$cfg_name-m64.0000/$binname 	$bin_dir/$a1

                cp $target/build/$cfg_name-m64.0000/$binname 	$stripbin_dir/$a1

                strip $stripbin_dir/$a1
            fi
            cd -

        done < "$list_file"

    elif [ "$package" == 'spec_cpu2006' ]; then

        root_path=$src_path/$package/benchspec/CPU2006

        while IFS='' read -r line || [[ -n "$line" ]]; do

            a1=$(echo $line | awk -F' ' '{print $1}')
            binname=$(echo $line | awk -F' ' '{print $2}')

            [ -z "$binname" ] && binname=$(echo $a1 | awk -F'.' '{print $2}')
            #echo $binname

            target=$root_path/$a1

            cd $root_path/

            if [ -d "$a1/build/$cfg_name.0000/" ]
            then
                find $a1/build/$cfg_name.0000/ -name '*.s' -exec cp --parents \{\} $asm_dir \;

                cp $target/build/$cfg_name.0000/$binname    $bin_dir/$a1

                cp $target/build/$cfg_name.0000/$binname    $stripbin_dir/$a1

                strip $stripbin_dir/$a1

	        else
                find $a1/build/$cfg_name.0000/ -name '*.s' -exec cp --parents \{\} $asm_dir \;

                cp $target/build/$cfg_name.0000/$binname 	$bin_dir/$a1

                cp $target/build/$cfg_name.0000/$binname 	$stripbin_dir/$a1

                strip $stripbin_dir/$a1
            fi
            cd -

        done < "$list_file"


    else
        cd $src_path/$package/$dest_path
        find . -name '*.s' -exec cp --parents \{\} $asm_dir \;

        cd -
        while IFS='' read -r line || [[ -n "$line" ]]; do
            name=$(echo $line | awk -F' ' '{print $1}')
            filename=$(basename "${line}")

            target=$src_path/$package/$dest_path/$name

            cp $target 	$bin_dir/$filename

            cp $target 	$stripbin_dir/$filename

            strip $stripbin_dir/$filename

        done < "$list_file"

    fi
}


function run
{
    package=$1
    name=$2
	compiler=$3
	opt=$4
    linkopt=$5
	cfg_name=build_base_$name\_$compiler\_$opt\_$linkopt.cfg
	dest_path=$compiler/$opt\_$linkopt

	copy $package $cfg_name $dest_path
}

package=$1
name=$2
compiler=$3
opt=$4
linker=$5

run $package $name $compiler $opt $linker

