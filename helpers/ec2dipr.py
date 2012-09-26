#!/usr/bin/env python
#
# ec2dipr.py - ec2_describe_ipaddress_ranges
# original script at https://gist.github.com/559397
#
# This script is merely intended for developers' sake, so far. I don't think
# updating "on the fly" is a good idea, but maybe doing it programmatically
# when building this module is less prone to errors

from BeautifulSoup import BeautifulSoup
from boto import ec2
import IPy
import random
import re
import socket
import urllib2

REGION_NAMES = [ reg.name for reg in ec2.regions() ]
ROOT_URL = 'https://forums.aws.amazon.com'
INDEX_REQ = 'forum.jspa?forumID=30'

def ec2_describe_ipaddress_ranges():
    f = urllib2.urlopen('%s/%s' % (ROOT_URL, INDEX_REQ, ))
    soup = BeautifulSoup(f.read())
    f.close()

    links = soup.findAll('a', attrs={'class': 'jive-announce-header'})
    target = None
    for link in links:
        content = link.contents.pop().lower()
        if content.find('ec2 public ip ranges') != -1:
            target = link.attrMap['href']
            break

    f = urllib2.urlopen('%s/%s' % (ROOT_URL, target,))
    soup = BeautifulSoup(f.read())
    f.close()

    if not target:
        raise ValueError('Cannot seem to find the link to the forum post...')

    data = soup.findAll('div', attrs={ 'class': 'jive-body' })[0]
    ranges = { }
    for line in str(data).split('\n'):
        m = re.search('(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2})', line)
        if not m: continue

        cidr = IPy.IP(m.group(0))
        hostname = None
        for t in [1, 2, 3]:
            ip = random.choice(cidr).strNormal()
            try:
                hostname = socket.gethostbyaddr(ip)[0]
            except (socket.herror, IndexError):
                continue
            if hostname.endswith('.amazonaws.com'):
                break
            else:
                hostname = None
                continue
        if not hostname:
            print 'Could not find the region for %s' % (cidr.strNormal(),)
            raise

        hostname = hostname.replace('compute-1', 'us-east-1.compute')
        region = hostname.split('.')[-4]

        if region not in ranges:
            ranges[region] = set()
        ranges[region].add(cidr.strNormal())

    return ranges


if __name__ == '__main__':
    ranges = ec2_describe_ipaddress_ranges()
    for region in sorted(ranges.keys()):
        print '        \'%s\': [' % (region,)
        for cidr in sorted(ranges[region]):
            print '            \'%s\',' % (cidr,)
        print '        ],'

