#!/bin/bash

function build()
{
    target=$1
    python3 build.py $target --verbose
    python3 ../../../emitter.py $target output/$target.s  --ofolder output
}
mkdir -p output
build epiphany
build filezilla
build openssh
build putty
build vim

