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
module: caas_vlan
short_description: "Create, Configure, Remove VLANs on Dimension Data Managed Cloud Platform"
version_added: "1.9"
author: "Olivier GROSJEANNE, @job-so"
description: 
  - "Create, Configure, Remove Network Network VLANs on Dimension Data Managed Cloud Platform"
notes:
  - "This is a wrappper of Dimension Data CaaS API v2.1. Please refer to this documentation for more details and example : U(https://community.opsourcecloud.net/View.jsp?procId=10011686f65f51b7f474acb2013072d2)"
requirements:
    - a caas_credentials variable, see caas_credentials module.  
    - a network domain already deployed, see caas_networkdomain module.
options: 
  caas_credentials: 
    description: 
      - Complexe variable containing credentials. From an external file or from module caas_credentials (See related documentation)
    required: true
  name: 
    description: 
      - "Name that has to be given to the instance"
      - "The name must be unique inside the DataCenter"
      - "Minimum length 1 character Maximum length 75 characters."
    required: true
  state:  
    choices: ['present','absent']
    default: present
    description: 
      - "Should the resource be present or absent."
      - "Take care : Absent will delete the Vlan."
  wait:
    description:
      - "Does the task must wait for the vlan creation ? or deploy it asynchronously ?"
    choices: [true,false]
    default: true
  description:
    description:
      - "Maximum length: 255 characters."
    default: "Created and managed by ansible.CaaS - https://github.com/job-so/ansible.CaaS"
  networkDomainId:
    description:
      - "The id of a Network Domain belonging within the same MCP 2.0 data center."
      - "You can use either networkDomainId or networkDomainName, however one of them must be specified"
    default: null
  networkDomainName:
    description:
      - "The name of a Network Domain belonging within the same MCP 2.0 data center."
      - "You can use either networkDomainId or networkDomainName, however one of them must be specified"
    default: null
  privateIpv4BaseAddress:
    description:
      - "RFC1918 Dot-decimal representation of an IPv4 address."
      - "For example: “10.0.4.0”. Must be unique within the Network Domain."
    default: null
  privateIpv4BaseAddress:
    description:
      - "An Integer between 16 and 24, which represents the size of the VLAN to be deployed and must be consistent with the privateIpv4BaseAddress provided."
    default: "24"
'''

EXAMPLES = '''
# Create a new vlan named "vlan_webservers" in network domain "ansible.Caas_SandBox", 
      - name: Deploy WebServers DMZ
        caas_vlan:
          caas_credentials: "{{ caas_credentials }}"
          networkDomainName: "ansible.Caas_SandBox"
          name: "vlan_webservers"
          privateIpv4BaseAddress: "192.168.30.0"
        register: caas_vlan_webservers
# Create a new vlan named {{networkDomainName}}_vlan_webserver in a network domain referenced from a previous task.
      - name: Deploy WebServers DMZ
        caas_vlan:
          caas_credentials: "{{ caas_credentials }}"
          networkDomainName: "{{ caas_networkdomain.networkdomains.networkDomain[0].name }}"
          name: "{{caas_networkdomain.networkdomains.networkDomain[0].name}}_vlan_webservers"
          privateIpv4BaseAddress: "192.168.30.0"
        register: caas_vlan_webservers
'''

RETURN = '''
        "vlans": 
            type: Dictionary
            returned: success
            description: A list of VLANs (should be one) matching the task parameters.
            sample: 
                "pageCount": 1
                "pageNumber": 1
                "pageSize": 250
                "totalCount": 1
                "vlan":
                  - "createTime": "2016-01-28T08:49:04.000Z"
                    "datacenterId": "EU6"
                    "description": "Created and managed by ansible.CaaS - https://github.com/job-so/ansible.CaaS"
                    "id": "3a454c87-c8f6-4517-8531-b55f9440449c"
                    "ipv4GatewayAddress": "192.168.30.1"
                    "ipv6GatewayAddress": "2a00:47c0:111:1168:0:0:0:1"
                    "ipv6Range":
                        "address": "2a00:47c0:111:1168:0:0:0:0"
                        "prefixSize": 64
                    "name": "ansible.CaaS_Sandbox_vlan_webservers"
                    "networkDomain":
                        "id": "94e50925-2d2f-4727-b137-6d70ce416829"
                        "name": "ansible.CaaS_Sandbox"
                    "privateIpv4Range":
                        "address": "192.168.30.0"
                        "prefixSize": 24
                    "state": "NORMAL"
...
'''

logging.basicConfig(filename='caas.log',level=logging.DEBUG)
logging.debug("--------------------------------caas_networkdomain---"+str(datetime.datetime.now()))

def _getOrgId(caas_credentials):
    apiuri = '/oec/0.9/myaccount'
    request = urllib2.Request(caas_credentials['apiurl'] + apiuri)
    base64string = base64.encodestring('%s:%s' % (caas_credentials['username'], caas_credentials['password'])).replace('\n', '')
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

def caasAPI(caas_credentials, uri, data):
    logging.debug(uri)
    if data == '':
        request = urllib2.Request(caas_credentials['apiurl'] + uri)
    else:
        request	= urllib2.Request(caas_credentials['apiurl'] + uri, data)
    base64string = base64.encodestring('%s:%s' % (caas_credentials['username'], caas_credentials['password'])).replace('\n', '')
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

def _listVlan(module,caas_credentials,orgId,wait):
    f = { 'name' : module.params['name'], 'networkDomainId' : module.params['networkDomainId']}
    uri = '/caas/2.1/'+orgId+'/network/vlan?'+urllib.urlencode(f)
    b = True;
    while b:
        result = caasAPI(caas_credentials, uri, '')
        vlanList = result['msg']
        b = False
        for (vlan) in vlanList['vlan']:
            logging.debug(vlan['id']+' '+vlan['name']+' '+vlan['state'])
            if (vlan['state'] != "NORMAL") and wait:
		        b = True
        if b:
            time.sleep(5)
    return vlanList

def main():
    module = AnsibleModule(
        supports_check_mode=True,
        argument_spec = dict(
            caas_credentials = dict(required=True,no_log=True),
            state = dict(default='present', choices=['present', 'absent']),
            wait = dict(default=True),
            name = dict(required=True),
            description = dict(default='Created and managed by ansible.CaaS - https://github.com/job-so/ansible.CaaS'),
            networkDomainId = dict(default=None),
            networkDomainName = dict(default=None),
            privateIpv4BaseAddress = dict(default=None),
            privateIpv4PrefixSize = dict(default=24),
        )
    )
    if not IMPORT_STATUS:
        module.fail_json(msg='missing dependencies for this module')
    has_changed = False
	
    # Check Authentication and get OrgId
    caas_credentials = module.params['caas_credentials']
    module.params['datacenterId'] = module.params['caas_credentials']['datacenter']

    state = module.params['state']
    wait = module.params['wait']

    result = _getOrgId(caas_credentials)
    if not result['status']:
        module.fail_json(msg=result['msg'])
    orgId = result['orgId']

	#Check dataCenterId
    #if not datacenterId
	
    if module.params['networkDomainId']==None:
        if module.params['networkDomainName']!=None:
            f = { 'name' : module.params['networkDomainName'], 'datacenterId' : module.params['datacenterId']}
            uri = '/caas/2.1/'+orgId+'/network/networkDomain?'+urllib.urlencode(f)
            result = caasAPI(caas_credentials, uri, '')
            if result['status']:
                if result['msg']['totalCount']==1:
                    module.params['networkDomainId'] = result['msg']['networkDomain'][0]['id']
	
    vlanList = _listVlan(module,caas_credentials,orgId,True)
#ABSENT
    if state == 'absent':
        if vlanList['totalCount'] == 1:
            uri = '/caas/2.1/'+orgId+'/network/deleteVlan'
            _data = {}
            _data['id'] = vlanList['vlan'][0]['id']
            data = json.dumps(_data)
            if module.check_mode: has_changed=True
            else: 
                result = caasAPI(caas_credentials, uri, data)
                if not result['status']: module.fail_json(msg=result['msg'])
                else: has_changed = True

#PRESENT
    if state == "present":
        if vlanList['totalCount'] < 1:
            uri = '/caas/2.1/'+orgId+'/network/deployVlan'
            _data = {}
            _data['name'] = module.params['name']
            _data['description'] = module.params['description']
            _data['networkDomainId'] = module.params['networkDomainId']
            _data['privateIpv4BaseAddress'] = module.params['privateIpv4BaseAddress']
            _data['privateIpv4PrefixSize'] = module.params['privateIpv4PrefixSize']
            data = json.dumps(_data)
            if module.check_mode: has_changed=True
            else: 
                result = caasAPI(caas_credentials, uri, data)
                if not result['status']: module.fail_json(msg=result['msg'])
                else: has_changed = True
	
    vlanList = _listVlan(module,caas_credentials,orgId,wait)
    module.exit_json(changed=has_changed, vlans=vlanList)

from ansible.module_utils.basic import *
if __name__ == '__main__':
    main()
