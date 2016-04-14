'''
*********************************************************
Copyright @ 2015 EMC Corporation All Rights Reserved
*********************************************************
'''
#! /usr/bin/python

import socket
import fcntl
import struct
import subprocess

IFNAME = 'eth0'

def getMac(ifname):
    s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    info = fcntl.ioctl(s.fileno(),0x8927,struct.pack('256s',ifname[:15]))[18:24]
    mac = ":".join(['%02x' % ord(char) for char in info])

    return mac

def getIp(ifname):
    s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    try:
        ip = socket.inet_ntoa(fcntl.ioctl(s.fileno(),0x8915,struct.pack('256s',ifname[:15]))[20:24])
    except IOError, e:
        print 'There is no ip for %s' % ifname

    return ip

def hasGw(ifname):
    with open('/proc/net/route') as fh:
        for line in fh:
            if ifname in line:
                fields = line.strip().split()
                if fields[2] == '00000000':
                    return False
                else:
                    return True

def rptClient():
    dest = ('<broadcast>',55555)
    name = "vpdu"
    key = "registered!"
    mac = getMac(IFNAME)
    ip = getIp(IFNAME)
    if not hasGw(IFNAME):
        tmp = ip.split('.')
        gw = '%s.%s.%s.%s' % (tmp[0],tmp[1],tmp[2],'1')
        subprocess.call(['route','add','default','gw',gw,IFNAME])
    msg = "%s(%s)@%s" % (name,mac,ip)

    s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)

    while True:
        try:
            s.sendto(msg,dest)
            s.settimeout(2)
            (buf,addr) = s.recvfrom(1024)
            if not len(buf):
                break

            if buf == key:
                break
        except socket.timeout:
            pass

    s.close()


if __name__ == "__main__":
    rptClient();
