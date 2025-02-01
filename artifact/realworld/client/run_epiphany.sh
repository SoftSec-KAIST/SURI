#!/bin/bash
str=$(ldd epiphany | grep libephymain.so)
if [[ "$str" == *not* ]]; then
    echo "Could not find library path for libephymain.so"
else
    libpath=$(ldd epiphany | grep libephymain.so | awk '{print $3}' | awk -F'libephymain' '{print $1}')
    export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$libpath
    ./my_epiphany
fi
