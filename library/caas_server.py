#!/usr/bin/python
# coding: utf-8 -*-

# This module is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.

try:
    import datetime
    import json
    import logging
    import base64
    import urllib
    import urllib2
    import xml.etree.ElementTree as ET
    IMPORT_STATUS = True
except ImportError:
    IMPORT_STATUS = False

DOCUMENTATION = '''
--- 
author: "Olivier GROSJEANNE, @job-so"
description: 
  - "Create, Configure, Remove Servers on Dimension Data Managed Cloud Platform For now, this module only support MCP 2.0."
module: caas_server
options: 
  caas_apiurl: 
    description: 
      - "Africa (AF) : https://api-mea.dimensiondata.com"
      - "Asia Pacific (AP) : https://api-ap.dimensiondata.com"
      - "Australia (AU) : https://api-au.dimensiondata.com"
      - "Canada(CA) : https://api-canada.dimensiondata.com"
      - "Europe (EU) : https://api-eu.dimensiondata.com"
      - "North America (NA) : https://api-na.dimensiondata.com"
      - "South America (SA) : https://api-latam.dimensiondata.com"
    required: true
  datacenterId: 
    description: 
      - "You can use your own 'Private MCP', or any public MCP 2.0 below :"
      - "Asia Pacific (AP) :"
      - "   AP3 Singapore - Serangoon"
      - "Australia (AU) :"
      - "   AU9 Australia - Sydney"
      - "   AU10  Australia - Melbourne"
      - "   AU11 New Zealand - Hamilton"
      - "Europe (EU) :"
      - "   EU6 Germany - Frankfurt"
      - "   EU7 Netherland - Amsterdam"
      - "   EU8 UK - London"
      - "North America (NA) :"
      - "   NA9 US - Ashburn"
      - "   NA12 US - Santa Clara"
    required: true
  caas_password: 
    description: 
      - "The associated password"
    required: true
  caas_username: 
    description: 
      - "Your username credential"
    required: true
  name: 
    description: 
      - "Name that has to be given to the instance Minimum length 1 character Maximum length 75 characters."
    required: true
  count: 
    default: 1
    description: 
      - "Number of instances to deploy.  Decreasing this number as no effect."
  state:  
    choices: ['present','absent']
    default: present
    description: 
      - "Should the resource be present or absent."
      - "Take care : Absent will powerOff and delete all servers."
  action: 
    description:
      - "Action to perform against all servers."
      - "startServer : starts non-running Servers"            
      - "shutdownServer : performs guest OS initiated shutdown of running Servers (preferable to powerOffServer)"
      - "rebootServer : performs guest OS initiated restart of running Servers (preferable to resetServer)"
      - "resetServer : performs hard reset of running Servers"
      - "powerOffServer : performs hard power off of running Servers"
      - "updateVmwareTools : triggers an update of the VMware Tools software running on the guest OS of the Servers"
      - "upgradeVirtualHardware : triggers an update of the VMware Virtual Hardware. VMware recommend cloning the Server prior to performing the upgrade in case something goes wrong during the upgrade process"
    choices: ['startServer', 'shutdownServer', 'rebootServer', 'resetServer', 'powerOffServer', 'updateVmwareTools', 'upgradeVirtualHardware']
    default: "startServer"
  wait:
    description:
      - "TBC"
    choices: [true,false]
    default: true
  description:
    description:
      - "Maximum length: 255 characters."
    default: "Created and managed by ansible.CaaS - https://github.com/job-so/ansible.CaaS"
  imageId:
    description:
      - "UUID of the Server Image being used as the target for the new Server deployment"
    choices: [present, absent]
    default: null
  imageName:
    description:
      - "TBC"
    default: null
  administratorPassword:
    description:
      - "TBC"
    default: null
  networkInfo:
    description:
      - "For an MCP 2.0 request, a networkInfo element is required. networkInfo identifies the Network Domain to which the Server will be deployed."
      - "It contains a primaryNic element defining the required NIC for the Server and optional additionalNic elements defining any additional VLAN connections for the Server."
      - "Each NIC must contain either a VLAN ID (vlanId) OR a Private IPv4 address (privateIpv4) from the target VLAN which the NIC will associate the Server with."
    default: null
short_description: "Create, Configure, Remove Servers on Dimension Data Managed Cloud Platform"
version_added: "1.9"
'''

EXAMPLES = '''
# Creates a new server named "WebServer" of CentOS 7 with default CPU/RAM/HD, 
#   on Vlan "vlan_webservers", in Network Domain : "ansible.Caas_SandBox"
-caas_server:
    caas_apiurl: "{{ caas_apiurl }}"
    caas_username: "{{ caas_username }}"
    caas_password: "{{ caas_password }}"
    datacenterId: "{{ caas_datacenter }}"
    name: "WebServer"
    imageName: CentOS 7 64-bit 2 CPU
    administratorPassword: "{{ root_password }}"
    networkInfo:
        networkDomainName: ansible.Caas_SandBox
        primaryNic: 
            vlanName: vlan_webservers
    register: caas_server
'''

logging.basicConfig(filename='caas.log',level=logging.DEBUG)
logging.debug("--------------------------------caas_server---"+str(datetime.datetime.now()))

def _getOrgId(username, password, apiurl):
    apiuri = '/oec/0.9/myaccount'
    request = urllib2.Request(apiurl + apiuri)
    base64string = base64.encodestring('%s:%s' % (username, password)).replace('\n', '')
    request.add_header("Authorization", "Basic %s" % base64string)
    result = {}
    result['status'] = False
    try:
        response = urllib2.urlopen(request).read()
        root = ET.fromstring(response)
        ns = {'directory': 'http://oec.api.opsource.net/schemas/directory'}
        result['orgId'] = root.find('directory:orgId',ns).text
        result['status'] = True
    except urllib2.URLError as e:
        result['msg'] = e.reason
    except urllib2.HTTPError, e:
        result['msg'] = e.read()
    return result

def _listServer(module,caas_username,caas_password,caas_apiurl,orgId,wait):
	# List Servers with this Name, in this networkDomain, in this vlanId
    f = { 'networkDomainId' : module.params['networkInfo']['networkDomainId'], 'vlanId' : module.params['networkInfo']['primaryNic']['vlanId'], 'name' : module.params['name']}
    uri = module.params['caas_apiurl']+'/caas/2.1/'+orgId+'/server/server?'+urllib.urlencode(f)
    b = True;
    while wait and b:
        result = caasAPI(caas_username,caas_password, uri, '')
        serverList = result['msg']
        b = False
        for (server) in serverList['server']:
            logging.debug(server['id']+' '+server['name']+' '+server['state'])
            if server['state'] != "NORMAL":
		        b = True
        if b:
            time.sleep(5)
    return serverList

def _executeAction(module,caas_username,caas_password,caas_apiurl,orgId,serverList,action):
    logging.debug("---_executeAction "+action)
    has_changed = False
    _data = {}
    uri = caas_apiurl+'/caas/2.1/'+orgId+'/server/'+action
    for (server) in serverList['server']:
        logging.debug(server['id'])
        _data['id'] = server['id']
        data = json.dumps(_data)
        if not server['started'] and (action == "startServer" or action == "updateVmwareTools" or action == "deleteServer"):
            result = caasAPI(caas_username,caas_password, uri, data)
            if not result['status']:
                module.fail_json(msg=result['msg'])
            else:
                has_changed = True	
        if server['started'] and (action == "shutdownServer" or action == "powerOffServer" or action == "resetServer" or action == "rebootServer" or action == "upgradeVirtualHardware"):
            result = caasAPI(caas_username,caas_password, uri, data)
            if not result['status']:
                module.fail_json(msg=result['msg'])
            else:
                has_changed = True	
    return has_changed
	
def caasAPI(username, password, uri, data):
    logging.debug(uri)
    if data == '':
        request = urllib2.Request(uri)
    else:
        request	= urllib2.Request(uri, data)
    base64string = base64.encodestring('%s:%s' % (username, password)).replace('\n', '')
    request.add_header("Authorization", "Basic %s" % base64string)
    request.add_header("Content-Type", "application/json")
    result = {}
    result['status'] = False
    retryCount = 0
    while (result['status'] == False) and (retryCount < 5*6):
        try:
            response = urllib2.urlopen(request)
            result['msg'] = json.loads(response.read())
            result['status'] = True
        except urllib2.HTTPError, e:
            if e.code == 400:
                result['msg'] = json.loads(e.read())
                if result['msg']['responseCode'] == "RESOURCE_BUSY":
                    logging.debug("RESOURCE_BUSY "+str(retryCount)+"/30")
                    time.sleep(10)
                    retryCount += 1
                else:
                    retryCount = 9999
            else:
                retryCount = 9999
                result['msg'] = str(e.code) + e.reason + e.read()
        except urllib2.URLError as e:
            result['msg'] = str(e.code)
            retryCount = 9999
    return result

def main():
    module = AnsibleModule(
        argument_spec = dict(
            caas_apiurl = dict(required=True),
            datacenterId = dict(required=True),
            caas_username = dict(required=True),
            caas_password = dict(required=True,no_log=True),
			name = dict(required=True),
			count = dict(type='int', default='1'),
            state = dict(default='present', choices=['present', 'absent']),
            action = dict(default='startServer', choices=['startServer', 'shutdownServer', 'rebootServer', 'resetServer', 'powerOffServer', 'updateVmwareTools', 'upgradeVirtualHardware']),
            wait = dict(default=True),
            description = dict(default='Created and managed by ansible.CaaS - https://github.com/job-so/ansible.CaaS'),
            imageId = dict(default=''),
            imageName = dict(default=''),
            administratorPassword = dict(default='',no_log=True),
            networkInfo = dict(),
        )
    )
    if not IMPORT_STATUS:
        module.fail_json(msg='missing dependencies for this module')
    has_changed = False
	
    # Check Authentication and get OrgId
    caas_username = module.params['caas_username']
    caas_password = module.params['caas_password']
    caas_apiurl = module.params['caas_apiurl']
    result = _getOrgId(caas_username,caas_password,caas_apiurl)
    if not result['status']:
        module.fail_json(msg=result['msg'])
    orgId = result['orgId']

	#Check dataCenterId
    #if not datacenterId
	
	# resolve imageId, networkId, vlanId
    if module.params['imageId']=='': # or null ?
        if module.params['imageName']!='':
            f = { 'datacenterId' : module.params['datacenterId'], 'name' : module.params['imageName'] }
            uri = module.params['caas_apiurl']+'/caas/2.1/'+orgId+'/image/osImage?'+urllib.urlencode(f)
            result = caasAPI(module.params['caas_username'],module.params['caas_password'], uri, '')
            if result['status']:
                if result['msg']['totalCount']==1:
                    module.params['imageId'] = result['msg']['osImage'][0]['id']
    if not 'networkDomainId' in module.params['networkInfo']:
        if 'networkDomainName' in module.params['networkInfo']:
            f = { 'name' : module.params['networkInfo']['networkDomainName'], 'datacenterId' : module.params['datacenterId']}
            uri = module.params['caas_apiurl']+'/caas/2.1/'+orgId+'/network/networkDomain?'+urllib.urlencode(f)
            result = caasAPI(module.params['caas_username'],module.params['caas_password'], uri, '')
            if result['status']:
                if result['msg']['totalCount']==1:
                    module.params['networkInfo']['networkDomainId'] = result['msg']['networkDomain'][0]['id']
    if 'primaryNic' in module.params['networkInfo']:
        if not 'vlanId' in module.params['networkInfo']['primaryNic']:
            if 'vlanName' in module.params['networkInfo']['primaryNic']:
                f = { 'name' : module.params['networkInfo']['primaryNic']['vlanName']}
                uri = module.params['caas_apiurl']+'/caas/2.1/'+orgId+'/network/vlan?'+urllib.urlencode(f)
                result = caasAPI(module.params['caas_username'],module.params['caas_password'], uri, '')
                if result['status']:
                    if result['msg']['totalCount']==1:
                        module.params['networkInfo']['primaryNic']['vlanId'] = result['msg']['vlan'][0]['id']
	
    serverList = _listServer(module,caas_username,caas_password,caas_apiurl,orgId,True)
	
   # if state=absent
    if module.params['state']=='absent':
        has_changed = _executeAction(module, caas_username,caas_password,caas_apiurl,orgId,serverList,'powerOffServer') or has_changed
        serverList = _listServer(module,caas_username,caas_password,caas_apiurl,orgId,True)
        has_changed = _executeAction(module, caas_username,caas_password,caas_apiurl,orgId,serverList,'deleteServer') or has_changed

	# if state=present
    if module.params['state'] == "present":
        i = serverList['totalCount']
        uri = module.params['caas_apiurl']+'/caas/2.1/'+orgId+'/server/deployServer'
        module.params['start'] = (module.params['action'] == 'startServer')
        data = json.dumps(module.params)
        while i < module.params['count']:
            result = caasAPI(module.params['caas_username'],module.params['caas_password'], uri, data)
            if not result['status']:
                module.fail_json(msg=result['msg'])
            else:
                has_changed = True
	    i += 1			

        # Execute Action on Servers
        has_changed = _executeAction(module, caas_username,caas_password,caas_apiurl,orgId,serverList,module.params['action']) or has_changed
		
    module.exit_json(changed=has_changed, servers=_listServer(module,caas_username,caas_password,caas_apiurl,orgId,module.params['wait']))

from ansible.module_utils.basic import *
if __name__ == '__main__':
    main()
