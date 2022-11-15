#!/usr/bin/env bash

sudo apt-get update
sudo apt-get upgrade

sudo apt install gcc python3-pip
python3 -m pip install -U "discord.py[voice]"
pip3 install call_to_dxcc

gcc -o rbn_cw rbn_cw.c -O
#nohup python3 ./cw_spots_BOT.py &
