import requests
import json


class UserExists(Exception):
    pass


class ClassExists(Exception):
    pass


class UserDoesNotExist(Exception):
    pass


class OperationalError(Exception):
    pass


class RequestFailedException(Exception):
    def __init__(self, code, response=None):
        super(RequestFailedException, self).__init__()
        self.code = code
        self.response = response

    def __str__(self):
        return "RequestFailedException(code={})".format(self.code)


class Controller(object):
    root_url = '/'
    auth_url = '/api/authenticate'
    account_url = '/api/account'
    users_url = '/adm/users?per_page=100&disabled=True&activated=True&page={n}'
    user_url = '/adm/users'
    user_detail_url = '/adm/users/{user[id]}'
    classes_url = '/adm/classes?per_page=100&page={n}'
    class_url = '/api/learningClasses'
    class_detail_url = '/api/learningClasses/{e_class[id]}'
    school_url = '/adm/schools'
    groups_url = '/api/userGroups'
    group_url = groups_url
    group_detail_url = '/api/userGroups/{group[id]}'
    activate_user_url = '/adm/users/activate'

    default_student_roles = ["ROLE_STUDENT"]
    default_teacher_roles = ["ROLE_TEACHER"]

    default_user_mappings = {
        ('firstName', 'givenName'),
        ('lastName', 'sn'),
        ('middleName', 'secondName'),
        ('email', 'cms-email'),
        ('login', lambda x: "{}@ms45.edu.ru".format(x['cn'])),
        ('password', 'password'),
        ('roles', 'roles'),
        ('schoolId', 'schoolId'),
        ('id', 'id'),
        ('active', lambda x: True if 'loginDisabled' not in x or not x['loginDisabled'] else False),
    }

    default_class_mappings = {
        ('name', lambda x: " ".join(x['eline-division-name'].split(" ")[0:2]) if 'eline-division-name' in x else None),
        ('parallel', lambda x: int(x['eline-division-name'].split(" ")[0]) if 'eline-division-name' in x else None),
        ('letter', lambda x: x['eline-division-name'].split(" ")[1] if 'eline-division-name' in x else None),
        ('id', 'id'),
    }

    default_group_mappings = {
        ('name', lambda x: " ".join(x['eline-division-name'].split(" ")[0:2])),
        ('id', 'id'),
    }

    def __init__(self, url):
        self.url = str(url)
        self.cookies = None
        self.account = None
        self.managed_school = None
        self.user_list = []
        self.school_list = []
        self.class_list = []
        self.teacher_roles = type(self).default_teacher_roles
        self.student_roles = type(self).default_student_roles

    def set_managed_school(self, school_id):
        if school_id in self.managed_school_list:
            self.managed_school = school_id
        else:
            raise ValueError()

    def _get_json(self, current_url, alt=None):
        response = requests.get(
            current_url,
            cookies=self.cookies,
        )
        try:
            return json.loads(response.text)
        except json.decoder.JSONDecodeError:
            return alt

    def _get_user_list(self):
        n = 1
        self.user_list = []
        while True:
            current = self._get_json(self.url + type(self).users_url.format(n=n), [])
            self.user_list += current
            if len(current) == 0:
                break
            else:
                n+=1

    def _get_class_list(self):
        n = 1
        self.class_list = []
        while True:
            current = self._get_json(self.url + type(self).classes_url.format(n=n), [])
            self.class_list += current
            if len(current) == 0:
                break
            else:
                n+=1

    def _get_school_list(self):
        self.school_list = self._get_json(self.url + type(self).school_url, [])

    def _get_user_detail(self, user):
        return self._get_json(self.url + type(self).user_detail_url.format(user=user))

    def _get_class_detail(self, e_class):
        return self._get_json(self.url + type(self).class_detail_url.format(e_class=e_class))

    def _request_json_object(self, url, obj, method):
        if obj is not None:
            response = method(
                url,
                cookies=self.cookies,
                json=obj
            )
        else:
            response = method(
                url,
                cookies=self.cookies,
            )

        if response.status_code == 200:
            return response
        else:
            raise RequestFailedException(code=response.status_code, response=response)

    def _post_json_object(self, url, obj):
        return self._request_json_object(url, obj, requests.post)

    def _put_json_object(self, url, obj):
        return self._request_json_object(url, obj, requests.put)

    def _delete_object(self, url):
        return self._request_json_object(url, None, requests.delete)

    @classmethod
    def _map_object(cls, original_obj, mappings, old_obj=None):
        obj = {}
        for remote, local in mappings:
            if callable(local):
                obj[remote] = local(original_obj)
            elif local in original_obj:
                obj[remote] = original_obj[local]
        if old_obj is not None:
            for attr in old_obj:
                if attr not in obj:
                    obj[attr] = old_obj[attr]
        return obj

    def create_user(self, user, teacher=False, skip_update=False):
        obj = type(self)._map_object(user, type(self).default_user_mappings)
        if obj['login'] in self.login_list:
            raise UserExists()
        obj['schoolId'] = self.managed_school
        if 'roles' not in obj:
            if teacher:
                obj['roles'] = self.teacher_roles
            else:
                obj['roles'] = self.student_roles
        current_url = self.url + type(self).user_url
        try:
            if 'active' in obj and not obj['active']:
                # Cowardly refusing to create an inactive user
                return True
            self._post_json_object(current_url, obj)
            if not skip_update:
                self._get_user_list()
            return True
        except RequestFailedException as e:
            if e.code == 409:
                raise UserExists()
            else:
                return False

    def update_user(self, user):
        obj = type(self)._map_object(user, type(self).default_user_mappings)
        if obj['login'] not in self.login_list:
            raise UserDoesNotExist()
        cached_obj = self.user_for_login(obj['login'])
        old_obj = self._get_user_detail(user=cached_obj)
        for attr in old_obj:
            if attr not in obj:
                obj[attr] = old_obj[attr]
        obj['schoolId'] = self.managed_school
        current_url = self.url + type(self).user_url
        try:
            self._put_json_object(current_url, obj)
        except RequestFailedException as e:
            return False

        try:
            if 'active' in obj:
                self._put_json_object(self.url +  type(self).activate_user_url,
                                      {'id': obj['id'], 'activate': obj['active']})
            return True
        except RequestFailedException:
            raise OperationalError

    def set_password(self, login, password):
        cached_obj = self.user_for_login(login)
        old_obj = self._get_user_detail(user=cached_obj)
        obj = {
            'password': password,
        }
        for attr in old_obj:
            if attr not in obj:
                obj[attr] = old_obj[attr]
        obj['schoolId'] = self.managed_school
        current_url = self.url + type(self).user_url
        try:
            self._put_json_object(current_url, obj)
        except RequestFailedException as e:
            return False


    def delete_user(self, user):
        obj = type(self)._map_object(user, type(self).default_user_mappings)
        if obj['login'] not in self.login_list:
            raise UserDoesNotExist()
        cached_obj = self.user_for_login(obj['login'])
        current_url = self.url + type(self).user_detail_url.format(user=cached_obj)
        try:
            self._delete_object(current_url)
            self._get_user_list()
            return True
        except RequestFailedException as e:
            return False

    def create_class(self, e_class):
        # Now this probably requires at least some explanation
        #
        # We have two entities in mobedu - classes, and groups
        # You can only have one group for each class
        # You can't have a group without a class
        # You can have a class without a group,
        # but there's no point since mapping students to a class is done with groups
        #
        # This is why we always create a group after creating the class,
        # and we always delete a group after deleting the class

        # Create a class
        obj = type(self)._map_object(e_class, type(self).default_class_mappings)
        obj['school'] = self.managed_school_detail
        current_url = self.url + type(self).class_url
        try:
            response = self._post_json_object(current_url, obj)
        except RequestFailedException as e:
            if e.response is not None \
                    and 'Error_code' in e.response.headers \
                    and e.response.headers['Error_code'] == '2500':
                raise ClassExists()
            return False

        try:
            obj = json.loads(response.text)
        except json.decoder.JSONDecodeError:
            return False

        # Class created and stored as obj, now try to create a user_group
        group_obj = type(self)._map_object(e_class, type(self).default_group_mappings)
        group_obj["learningClassId"] = obj['id']

        current_url = self.url + type(self).group_url
        try:
            self._post_json_object(current_url, group_obj)
        except RequestFailedException as e:
            raise OperationalError

        # Insanity and courage! It worked.
        self._get_class_list()
        return True

    def update_class(self, e_class, mappings=None):
        obj = type(self)._map_object(e_class, type(self).default_class_mappings)

        if 'id' not in obj:
            for entry in self.class_list:
                if entry['parallel'] == obj['parallel'] and \
                    entry['letter'] == obj['letter'] and \
                        ('schoolName' not in obj or obj['schoolName'] == entry['schoolName']):
                    obj['id'] = entry['id']
                    break

        old_obj = self._get_class_detail(e_class=obj)
        for attr in old_obj:
            if attr not in obj:
                obj[attr] = old_obj[attr]
        obj['school'] = self.managed_school_detail
        current_url = self.url + type(self).class_url
        try:
            self._put_json_object(current_url, obj)
        except RequestFailedException as e:
            return False

        # Now update the group for consistency
        current_url = self.url + type(self).group_url

        group_obj = type(self)._map_object(e_class, type(self).default_group_mappings)
        group_obj["learningClassId"] = obj['id']
        group_obj['id'] = \
            self._get_json(self.url + type(self).group_detail_url.format(group=old_obj['userGroup']))['id']
        try:
            self._put_json_object(current_url, group_obj)
        except RequestFailedException as e:
            raise OperationalError

        self._get_class_list()
        return True

    def delete_class(self, e_class):
        obj = type(self)._map_object(e_class, type(self).default_class_mappings)
        old_obj = self._get_class_detail(e_class=obj)
        current_url = self.url + type(self).class_detail_url.format(e_class=old_obj)
        try:
            self._delete_object(current_url)
        except RequestFailedException as e:
            return False

        group_obj = self._get_json(self.url + type(self).group_detail_url.format(group=old_obj['userGroup']))

        current_url = self.url + type(self).group_detail_url.format(group=group_obj)

        try:
            self._delete_object(current_url)
        except RequestFailedException as e:
            raise OperationalError

        self._get_class_list()
        return True

    def get_class_group(self, e_class):
        obj = type(self)._map_object(e_class, type(self).default_class_mappings)

        if 'id' not in obj:
            for entry in self.class_list:
                if entry['parallel'] == obj['parallel'] and \
                    entry['letter'] == obj['letter'] and \
                        ('schoolName' not in obj or obj['schoolName'] == entry['schoolName']):
                    obj['id'] = entry['id']
                    break

        old_obj = self._get_class_detail(e_class=obj)
        group_obj = self._get_json(self.url + type(self).group_detail_url.format(group=old_obj['userGroup']))

        if 'userIds' not in group_obj and 'users' in group_obj:
            group_obj['userIds'] = [x['id'] for x in group_obj['users']]

        return group_obj

    def _get_user_object(self, user):
        obj = type(self)._map_object(user, type(self).default_user_mappings)
        if obj['login'] not in self.login_list:
            raise UserDoesNotExist()
        cached_obj = self.user_for_login(obj['login'])
        old_obj = self._get_user_detail(user=cached_obj)
        return old_obj

    def get_cached_member_id(self, user):
        obj = type(self)._map_object(user, type(self).default_user_mappings)
        for entry in self.user_list:
            if obj['login'] == entry['login']:
                return entry['id']
        return None

    def _set_group_members(self, group_obj):
        current_url = self.url + type(self).groups_url

        new_obj = {"tutorId": group_obj['tutorId'] if 'tutorId' in group_obj else None,
                   "learningClassId": group_obj['learningClasses'][0]['id'],
                   "name": group_obj['name'],
                   "id": group_obj['id'],
                   "userIds": group_obj['userIds']}
        try:
            self._put_json_object(current_url, new_obj)
        except RequestFailedException as e:
            raise OperationalError

    def set_class_members(self, e_class, user_ids):
        group_obj = self.get_class_group(e_class)
        group_obj['userIds'] = user_ids

        self._set_group_members(group_obj)

    def add_class_member(self, e_class, user):
        group_obj = self.get_class_group(e_class)
        user_obj = self._get_user_object(user)

        if user not in group_obj['userIds']:
            group_obj['userIds'].append(user_obj['id'])

        self._set_group_members(group_obj)

    def remove_class_member(self, e_class, user):
        group_obj = self.get_class_group(e_class)
        user_obj = self._get_user_object(user)

        if user_obj['id'] in group_obj['userIds']:
            group_obj['userIds'] = [x for x in group_obj['userIds'] if x != user_obj['id']]

        self._set_group_members(group_obj)

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
            self._get_class_list()
            self._get_school_list()
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

    @property
    def managed_school_detail(self):
        for school in self.school_list:
            if school['id'] == self.managed_school:
                return school
        return {}

    def user_for_login(self, login):
        if login not in self.login_list:
            raise UserDoesNotExist()
        return [x for x in self.user_list if x['login'] == login][0]
