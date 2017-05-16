import requests
import json


class UserExists(Exception):
    pass


class UserDoesNotExist(Exception):
    pass


class Controller(object):
    root_url = '/'
    auth_url = '/api/authenticate'
    account_url = '/api/account'
    users_url = '/adm/users'
    user_detail_url = '/adm/users/{user[id]}'

    default_user_mappings = {
        ('firstName', 'givenName'),
        ('lastName', 'sn'),
        ('middleName', 'secondName'),
        ('email', 'cms-email'),
        ('login', 'cn'),
        ('password', 'password'),
        ('roles', 'roles'),
        ('schoolId', 'schoolId'),
        ('id', 'id'),
    }

    preset_user_attributes = {
    }

    def __init__(self, url):
        self.url = str(url)
        self.cookies = None
        self.account = None
        self.managed_school = None
        self.user_list = []

    def set_managed_school(self, school_id):
        if school_id in self.managed_school_list:
            self.managed_school = school_id
        else:
            raise ValueError()

    def _get_user_list(self):
        current_url = self.url + type(self).users_url

        response = requests.get(
            current_url,
            cookies=self.cookies,
        )

        try:
            self.user_list = json.loads(response.text)
        except json.decoder.JSONDecodeError:
            pass

    def _get_user_detail(self, user):
        current_url = self.url + type(self).user_detail_url.format(user=user)

        response = requests.get(
            current_url,
            cookies=self.cookies,
        )

        try:
            return json.loads(response.text)
        except json.decoder.JSONDecodeError:
            return {}

    def _post_json_object(self, url, obj):
        response = requests.post(
            url,
            cookies=self.cookies,
            json=obj
        )

        if response.status_code == 200:
            return True
        else:
            return False

    def _put_json_object(self, url, obj):
        response = requests.put(
            url,
            cookies=self.cookies,
            json=obj
        )

        if response.status_code == 200:
            return True
        else:
            return False

    def _make_user(self, user, mappings=None):
        if mappings is None:
            mappings = type(self).default_user_mappings
        obj = {}
        for remote, local in mappings:
            if local in user:
                obj[remote]=user[local]
        return obj

    def create_user(self, user, mappings=None):
        obj = self._make_user(user, mappings)
        if obj['login'] in self.login_list:
            raise UserExists()
        obj['schoolId'] = self.managed_school
        current_url = self.url + type(self).users_url
        if self._post_json_object(current_url, obj):
            self._get_user_list()
            return True
        else:
            return False

    def update_user(self, user, mappings=None):
        obj = self._make_user(user, mappings)
        if obj['login'] not in self.login_list:
            raise UserDoesNotExist()
        cached_obj = self.user_for_login(obj['login'])
        old_obj = self._get_user_detail(user=cached_obj)
        for attr in old_obj:
            if attr not in obj:
                obj[attr] = old_obj[attr]
        obj['schoolId'] = self.managed_school
        current_url = self.url + type(self).users_url
        if self._put_json_object(current_url, obj):
            self._get_user_list()
            return True
        else:
            return False

    def authenticate(self, username, password):
        """Authenticate user, set account attribute.

            :param username: username for authorisation
            :param password: password for authorisation
            :returns: True if authorisation was successful, False otherwise

        """
        current_url = self.url + type(self).auth_url

        response = requests.post(
            current_url,
            json={'username': username, 'password': password}
        )

        self.cookies = response.cookies

        #
        # So, instead of Set-Cookie header, the server returns Cookie header
        # they also don't return any MaxAge, version, or anything, 'cause why bother
        # This is why we need to hack everything to make authorisation work here
        #
        # Thank you very much, Siruis Cybernetics Corporation!
        #

        try:
            cookie_name, cookie_value = response.headers['Cookie'].split("=")
        except (ValueError, KeyError):
            # Authentication error, or maybe just the stars weren't right
            return False

        self.cookies.set(cookie_name, cookie_value)

        current_url = self.url + type(self).account_url
        response = requests.get(
            current_url,
            cookies=self.cookies,
        )
        try:
            self.account = json.loads(response.text)
            self._get_user_list()
            if len(self.managed_school_list) == 1:
                self.set_managed_school(self.managed_school_list[0])
            return True
        except json.decoder.JSONDecodeError:
            return False

    @property
    def login_list(self):
        if self.user_list is not None:
            return [x['login'] for x in self.user_list]
        else:
            return []

    @property
    def managed_school_list(self):
        if self.account is not None and \
                        'additionalUserInfoDTO' in self.account and \
                        'adminSchools' in self.account['additionalUserInfoDTO']:
            return [x['id'] for x in self.account['additionalUserInfoDTO']['adminSchools']]
        else:
            return []

    def user_for_login(self, login):
        if login not in self.login_list:
            raise UserDoesNotExist()
        return [x for x in self.user_list if x['login'] == login][0]