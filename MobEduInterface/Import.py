import ldap3
import random
from .Controller import UserExists, ClassExists, OperationalError, UserDoesNotExist

random_password_characters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"


class Importer(object):
    def get_users(self):
        raise NotImplementedError

    def get_classes(self):
        raise NotImplementedError

    def get_user_key(self, user):
        raise NotImplementedError

    def get_class_key(self, user):
        raise NotImplementedError

    def get_class_user_keys(self, e_class):
        raise NotImplementedError

    def do_import(self, controller):
        user_by_key = {}

        for user in self.get_users():
            user_by_key[self.get_user_key(user)] = user
            try:
                print("{}: {}".format(self.get_user_key(user),
                                      controller.create_user(user, teacher=user["is_teacher"], skip_update=True)))
            except UserExists:
                print("{}: update {}".format(self.get_user_key(user),
                                      controller.update_user(user)))

        controller._get_user_list()

        for e_class in self.get_classes():
            try:
                print("{}: {}".format(self.get_class_key(e_class),
                                      controller.create_class(e_class)))
            except ClassExists as e:
                print("{}: update {}".format(self.get_class_key(e_class),
                                             controller.update_class(e_class)))

            members = []
            for user_key in self.get_class_user_keys(e_class):
                user = user_by_key[user_key]
                if 'id' not in user:
                    id = controller.get_cached_member_id(user)
                    if id is not None:
                        user['id'] = id
                    else:
                        try:
                            old_user = controller._get_user_object(user)
                            user['id'] = old_user['id']
                        except UserDoesNotExist:
                            print("!!! WARNING !!!")
                            print("User not found.")
                            print(user)
                            print("!!! WARNING !!!")

                members.append(user['id'])

            try:
                controller.set_class_members(e_class, members)
                print("{}: set members OK".format(self.get_class_key(e_class)))
            except OperationalError:
                print("{}: set members OPERATIONAL ERROR".format(self.get_class_key(e_class)))


class LdapImporter(Importer):
    def __init__(self, ldap_connection, base, scope=ldap3.SUBTREE,
                 check_if_teacher=None,
                 user_filter="(objectClass=inetOrgPerson)",
                 class_filter="(objectClass=groupOfNames)",
                 attributes=ldap3.ALL_ATTRIBUTES):
        super(LdapImporter, self).__init__()
        self.connection = ldap_connection
        self.user_filter = user_filter
        self.class_filter = class_filter
        self.base = base
        self.scope = scope
        self.attributes = attributes
        self.check_if_teacher = check_if_teacher

    def get_objects(self, current_filter, do_teacher_check = False):
        results = []

        for base in self.base:
            self.connection.search(
                base,
                current_filter,
                search_scope=self.scope,
                attributes=self.attributes
            )
            for entry in self.connection.response:
                attributes = {'original': entry}
                for k in entry['attributes']:
                    try:
                        attributes[k] = ", ".join(entry['attributes'][k])
                    except (TypeError, ValueError):
                        pass
                attributes['dn'] = entry['dn']

                # We add a fake password. It has to be set later by user
                attributes['password'] = "".join([random.choice(random_password_characters) for x in range(30)])

                if do_teacher_check:
                    if self.check_if_teacher is None:
                        attributes['is_teacher'] = False
                    elif callable(self.check_if_teacher):
                        attributes['is_teacher'] = bool(self.check_if_teacher(entry))
                    else:
                        attributes['is_teacher'] = bool(attributes[str(self.check_if_teacher)])
                results.append(attributes)
        return results

    def get_users(self):
        return self.get_objects(self.user_filter, do_teacher_check=True)

    def get_classes(self):
        return self.get_objects(self.class_filter)

    def get_user_key(self, user):
        return user['dn']

    def get_class_key(self, e_class):
        return e_class['dn']

    def get_class_user_keys(self, e_class):
        try:
            return e_class['original']['attributes']['member']
        except KeyError:
            return []
