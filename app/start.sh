#!/bin/bash

# turn on bash's job control
set -m

# recompile all proto files
pushd protobuf
protoc -I=. --python_out=.. rtx8200.proto
protoc -I=. --python_out=.. wrappers.proto
popd


# Start the Viewer process and put it in the background
/usr/sbin/rsyslogd&
python ./SnomM9BProvisioningServer.py
