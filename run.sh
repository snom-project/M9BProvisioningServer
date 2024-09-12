#!/bin/bash
echo "-------- start ssfd ----------"
killall -9 ssfd
pushd /home/ubuntu/ssf/ssf-linux-x86_64-3.0.0
./ssfd -p 10000&
popd
echo "-------- start docker ----------"
#sudo docker run -dit --restart unless-stopped -p 10514:10514/udp -p 8080:8080 m9bprov 
sudo docker run --log-driver json-file --log-opt max-size=10m --log-opt max-file=3 -dit --restart unless-stopped -p 10516:10516/udp -p 8080:8080 m9bprov
