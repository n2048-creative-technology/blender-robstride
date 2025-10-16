#!/bin/bash

ip link set can0 type can bitrate 1000000 loopback off
ip link set can0 up
