#!/bin/bash

mkdir -p output
python3 build.py 7zip
python3 build.py apache
python3 build.py mariadb
python3 build.py nginx
python3 build.py sqlite3
