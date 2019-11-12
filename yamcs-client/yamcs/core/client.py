from datetime import datetime

import pkg_resources
import requests
import six
import urllib3
from google.protobuf.message import DecodeError

from yamcs.core.exceptions import (ConnectionFailure, NotFound, Unauthorized,
                                   YamcsError)
from yamcs.protobuf.web import rest_pb2


class BaseClient(object):

    credentials = None

    def __init__(self, address, tls=False, credentials=None, user_agent=None,
                 on_token_update=None, tls_verify=True):
        if ':' in address:
            self.address = address
        else:
            self.address = address + ':8090'

        if tls:
            self.auth_root = 'https://{}/auth'.format(self.address)
            self.api_root = 'https://{}/api'.format(self.address)
            self.ws_root = 'wss://{}/_websocket'.format(self.address)
        else:
            self.auth_root = 'http://{}/auth'.format(self.address)
            self.api_root = 'http://{}/api'.format(self.address)
            self.ws_root = 'ws://{}/_websocket'.format(self.address)

        self.session = requests.Session()
        if not tls_verify:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            self.session.verify = False

        if credentials:
            self.credentials = credentials.login(
                self.session, self.auth_root, on_token_update)

        if not user_agent:
            dist = pkg_resources.get_distribution('yamcs-client')
            user_agent = 'yamcs-python-client v' + dist.version
        self.session.headers.update({'User-Agent': user_agent})

    def get_proto(self, path, **kwargs):
        headers = kwargs.pop('headers', {})
        headers['Accept'] = 'application/protobuf'
        kwargs.update({'headers': headers})
        return self.request('get', path, **kwargs)

    def put_proto(self, path, **kwargs):
        headers = kwargs.pop('headers', {})
        headers['Content-Type'] = 'application/protobuf'
        headers['Accept'] = 'application/protobuf'
        kwargs.update({'headers': headers})
        return self.request('put', path, **kwargs)

    def patch_proto(self, path, **kwargs):
        headers = kwargs.pop('headers', {})
        headers['Content-Type'] = 'application/protobuf'
        headers['Accept'] = 'application/protobuf'
        kwargs.update({'headers': headers})
        return self.request('patch', path, **kwargs)

    def post_proto(self, path, **kwargs):
        headers = kwargs.pop('headers', {})
        headers['Content-Type'] = 'application/protobuf'
        headers['Accept'] = 'application/protobuf'
        kwargs.update({'headers': headers})
        return self.request('post', path, **kwargs)

    def delete_proto(self, path, **kwargs):
        headers = kwargs.pop('headers', {})
        headers['Accept'] = 'application/protobuf'
        kwargs.update({'headers': headers})
        return self.request('delete', path, **kwargs)

    def request(self, method, path, **kwargs):
        path = '{}{}'.format(self.api_root, path)

        if self.credentials:
            self.credentials.before_request(self.session, self.auth_root)

        try:
            response = self.session.request(method, path, **kwargs)
        except requests.exceptions.SSLError as sslError:
            msg = 'Connection to {} failed: {}'.format(self.address, sslError)
            six.raise_from(ConnectionFailure(msg), None)
        except requests.exceptions.ConnectionError:
            raise ConnectionFailure('Connection to {} refused'.format(self.address))

        if 200 <= response.status_code < 300:
            return response

        exception_message = rest_pb2.RestExceptionMessage()
        try:
            exception_message.ParseFromString(response.content)
        except DecodeError:
            pass

        if response.status_code == 401:
            raise Unauthorized('401 Client Error: Unauthorized')
        elif response.status_code == 404:
            raise NotFound('404 Client Error: {}'.format(
                exception_message.msg))
        elif 400 <= response.status_code < 500:
            raise YamcsError('{} Client Error: {}'.format(
                response.status_code, exception_message.msg))
        raise YamcsError('{} Server Error: {}'.format(
            response.status_code, exception_message.msg))
