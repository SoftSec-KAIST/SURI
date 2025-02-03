
function copy()
{
    src=$1
    dst=$2
    name=$(basename $src | awk -F'my_' '{print $2}' )
    if [ -f $dst ]; then
        cp $src $dst
        echo "[+] Replace $name file in phoronix directory."
    else
        echo "[-] Error: The target file for '$name' does not exist."
        echo "    Please run: phoronix-test-suite benchmark $name"
    fi
}
copy /data/output/my_7zip /var/lib/phoronix-test-suite/installed-tests/pts/compress-7zip-1.11.0/CPP/7zip/Bundles/Alone2/_o/7zz
# phoronix-test-suite benchmark 7zip

copy /data/output/my_apache /var/lib/phoronix-test-suite/installed-tests/pts/apache-3.0.0/httpd_/bin/httpd
# phoronix-test-suite benchmark apache

copy /data/output/my_mariadb /var/lib/phoronix-test-suite/installed-tests/pts/mysqlslap-1.5.0/mysql_/bin/mariadb
# phoronix-test-suite benchmark mysqlslap

copy /data/output/my_nginx /var/lib/phoronix-test-suite/installed-tests/pts/nginx-3.0.1/nginx_/sbin/nginx
# phoronix-test-suite benchmark nginx

copy /data/output/my_sqlite3 /var/lib/phoronix-test-suite/installed-tests/pts/sqlite-2.2.0/sqlite_/bin/sqlite3
# phoronix-test-suite benchmark sqlite

