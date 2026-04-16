#!/bin/bash
mkdir -p /tmp/mongodb-data
if ! pgrep -x mongod > /dev/null; then
    mongod --dbpath /tmp/mongodb-data --logpath /tmp/mongodb.log --fork
    sleep 2
fi
cd backend
python server.py
