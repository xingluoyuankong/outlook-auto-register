#!/bin/bash
set -euo pipefail
SRC="/home/workspace/Email-Register"
scp -i /home/workspace/zo-mesh/config/keys/node3.pem -P 10037 \
  "$SRC/deploy/fix_node_deps.sh" "$SRC/deploy/trigger_manual_round.sh" \
  root@ts13.zocomputer.io:/home/workspace/Email-Register/deploy/
ssh -i /home/workspace/zo-mesh/config/keys/node3.pem -p 10037 root@ts13.zocomputer.io \
  'EMAIL_REGISTER_ROOT=/home/workspace/Email-Register bash /home/workspace/Email-Register/deploy/fix_node_deps.sh'

scp -i /home/workspace/zo-mesh/config/keys/gcore.pem \
  "$SRC/deploy/fix_node_deps.sh" "$SRC/deploy/trigger_manual_round.sh" \
  ubuntu@31.184.244.145:/home/ubuntu/Email-Register/deploy/
ssh -i /home/workspace/zo-mesh/config/keys/gcore.pem ubuntu@31.184.244.145 \
  'EMAIL_REGISTER_ROOT=/home/ubuntu/Email-Register bash /home/ubuntu/Email-Register/deploy/fix_node_deps.sh'
echo "zo3+gcore fixed"