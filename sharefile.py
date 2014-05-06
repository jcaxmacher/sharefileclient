from __future__ import print_function
from functools import wraps
from datetime import datetime
import json
import httplib
import os
import mimetypes
import time
import urlparse
import urllib
import urllib2
 

def get_authorization_header(token):
    return {'Authorization':'Bearer %s'%(token['access_token'])}
     

def get_hostname(token):
    return '%s.sf-api.com'%(token['subdomain'])


def ensure_auth(auth_type):
    def decorator(f):
        @wraps(f)
        def wrapper(self, *args, **kwargs):
            if auth_type == 'https' and not self.authid:
                self.get_authid()
            elif auth_type == 'rest' and not self.token:
                self.get_token()
            elif auth_type not in ('https', 'rest'):
                raise RuntimeError('Incorrect auth type: {}'.format(auth_type))
            return f(self, *args, **kwargs)
        return wrapper
    return decorator


class ShareFileClient(object):

    def __init__(self, hostname, client_id, client_secret, username, password,
                 company):
        self.hostname = hostname
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        self.company = company
        self.authid = None
        self.token = None
        self.https_url = ('https://%s/rest/{endpoint}.aspx?'
                          '{options}') % self.hostname
        self.url_path = '/rest/{endpoint}.aspx?{params}'

    def get_token(self):
        uri_path = '/oauth/token'
        headers = {'Content-Type':'application/x-www-form-urlencoded'}
        params = {
            'grant_type': 'password',
            'client_id': self.client_id,
            'client_secret': self.client_secret, 
            'username': self.username,
            'password': self.password
        }
        http = httplib.HTTPSConnection(self.hostname)
        http.request('POST', uri_path, urllib.urlencode(params),
                     headers=headers)
        response = http.getresponse()
        if response.status == 200:
            self.token = json.loads(response.read())
        http.close()
        return self.token

    def get_authid(self):
        url_params = {
            'username': self.username,
            'password': self.password,
            'fmt':'json'
        }
        encoded_params = urllib.urlencode(url_params)
        url = self.https_url.format(endpoint='getAuthID',
                                    options=encoded_params)
        authid = None
        response = json.loads(urllib2.urlopen(url).read())
        if not response['error']:
            authid = response['value']
        self.authid = authid
        return authid

    def list_employees(self):
        endpoint = '/sf/v3/Accounts/Employees?$expand=*'
        return json.loads(self._rest_method(endpoint, 'GET'))

    def get_employee(self, emp_id):
        email = emp_id + '@ca.com' if '@' not in emp_id else emp_id
        data = {'id': email}
        return self._http_method('users', 'get', data)

    def delete_employee(self, target, holding=None, completely=True):
        op = 'delete' if completely else 'deletef'
        employee = self.get_employee(target)
        if employee['error']:
            return {'error': False}
        data = {'id': employee['value']['id']}
        if holding:
            new_owner = self.get_employee(holding)
            if new_owner['error']:
                raise RuntimeError('Could not get ID of holding'
                                                     ' account!')
            else:
                data.update(reassignid=new_owner['value']['id'])
        return self._http_method('users', op, data)

    def create_employee(self, email, first_name, last_name, password=None):
        data = {
            'email': email,
            'lastname': last_name,
            'company': self.company,
            'firstname': first_name,
            'canviewmysettings': True,
            'canresetpassword': True,
            'createfolders': True,
            'manageusers': True,
            'isemployee': True,
            'usefilebox': True,
            'addshared': True,
            'notify': False,
            'confirm': True
        }
        if password:
            data.update(password=password)
        return self._http_method('users', 'create', data)

    def get_shared_folders(self):
        return self.list_folder('allshared')

    def delete_folder(self, folder_id):
        data = {'id': folder_id}
        return self._http_method('folder', 'delete', data)

    # Do not use, just delete
    def mark_user_disabled(self, user_id):
        today = datetime.now().strftime('%m/%d/%Y')
        data = {
            'id': user_id,
            'firstname': 'Disabled',
            'lastname': 'Disabled',
            'company': (self.company + '(disabled on {})').format(today)
        }
        return self._http_method('users', 'edit', data)

    def list_folder(self, folder_id):
        data = {'id': folder_id}
        return self._http_method('folder', 'list', data)

    def upload_file_to_home(self, file_name):
        home_list = self.list_folder('home')
        home_id = home_list['value'][0]['parentid']
        return self.upload_file(home_id, file_name)

    def upload_file(self, folder_id, file_name):
        folder, name = os.path.split(file_name)
        upload_url = self._get_upload_url(folder_id, name)
        added_query = urllib.urlencode({'raw': 1, 'filename': name})
        url = urllib2.urlparse.urlparse(upload_url)
        http = httplib.HTTPSConnection(url.netloc)
        path = '{}?{}&{}'.format(url.path, url.query, added_query)
        http.request('POST', path, open(file_name, 'rb'),
                     {'content-type': 'application/octet-stream'})
        response = http.getresponse()
        return response.read()

    def _get_upload_url(self, folder_id, file_name):
        data = {'filename': file_name, 'folderid': folder_id}
        uploader = self._http_method('file', 'upload', data)
        return uploader['value']

    @ensure_auth('https')
    def _http_method(self, endpoint, op, params, data=None, method='GET',
                     headers=None):
        headers = headers if headers else {}
        params.update(authid=self.authid, fmt='json', op=op)
        encoded_params = urllib.urlencode(params)
        url_path = self.url_path.format(endpoint=endpoint, params=encoded_params)
        http = httplib.HTTPSConnection(self.hostname)
        http.request(method.upper(), url_path, data, headers)
        response = http.getresponse()
        return json.loads(response.read())

    @ensure_auth('rest')
    def _rest_method(self, endpoint, method, data=None):
        encoded_data = urllib.urlencode(data) if data else None
        http = httplib.HTTPSConnection(get_hostname(self.token))
        http.request(method.upper(), endpoint, encoded_data,
                     headers=get_authorization_header(self.token))
        response = http.getresponse()
        return response.read()
