# What is vpduserv?
vpduserv is a service that is trying to emulate the behaviors of physical PDU (Power Distribution Unit), it provides ability to power on/off/cycle virtual nodes in virtual infrastructre. 

# Installation

<pre><code># python setup.py install </code></pre>

# How to run vpduserv

vpduserv could be run on any linux-based operating system, but prior to starting vpduserv, you should have the following python packages installed:

``pysnmp pyasn1 snmpsim sshim``

1. Launch vPDU service

    <pre><code>vpdud.py -d --logging-method=file:/var/log/vpdud/vpdud.log</code></pre>

2. Launch remote control service. 

    <pre><code>server.py -d --logging-method=file:/var/log/vpdud/vpdud.log</code></pre>

3. Login into vPDU control interface with ssh to configure vPDU 
    <pre><code>ssh &lt;vPDU IP address&gt; -p 20022</code></pre>

**Note:** As to how to use vPDU, please reference vPDU Simulation section in [infrasim user guide](http://infrasim.readthedocs.org/en/latest/userguide.html) for more details.

