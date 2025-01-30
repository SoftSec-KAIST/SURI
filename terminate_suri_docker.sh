echo 'ps -aux | grep docker | grep "suri.*:v1.0"  | awk '{print \$2}' | sudo xargs kill -9'
ps -aux | grep docker | grep "suri.*:v1.0"  | awk '{print $2}' | sudo xargs kill -9
