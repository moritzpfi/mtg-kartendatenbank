#!/usr/bin/env bash
set -euo pipefail
export HADOOP_HOME=/opt/hadoop HADOOP_LOG_DIR=/tmp/mtg-hadoop-logs
mkdir -p /data/name /data/data "$HADOOP_LOG_DIR"
if [ ! -f /data/name/current/VERSION ]; then
    "$HADOOP_HOME/bin/hdfs" namenode -format -nonInteractive
fi
"$HADOOP_HOME/bin/hdfs" namenode &
namenode=$!
"$HADOOP_HOME/bin/hdfs" datanode &
datanode=$!
trap 'kill "$namenode" "$datanode" 2>/dev/null || true; wait || true' EXIT
trap 'exit 0' TERM INT
while kill -0 "$namenode" 2>/dev/null && kill -0 "$datanode" 2>/dev/null; do
    sleep 2
done
exit 1
