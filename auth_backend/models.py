from dateutil import parser
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver
from jsonfield import JSONField

from . import auth_api_client

# TODO: possible fields to add to CAS
# first_name, last_name, is_staff, is_superadmin


class KagisoUser(AbstractBaseUser, PermissionsMixin):
    USERNAME_FIELD = 'email'

    id = models.IntegerField(primary_key=True)
    email = models.EmailField(max_length=250, unique=True)
    profile = JSONField(null=True)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField()
    modified = models.DateTimeField()

    confirmation_token = None
    raw_password = None

    @property
    def is_staff(self):
        return self.profile and self.profile.get('is_staff', False)

    @is_staff.setter
    def is_staff(self, value):
        assert value in (True, False, )
        self.profile = self.profile or {}
        self.profile['is_staff'] = value

    @property
    def is_superadmin(self):
        # TODO: implement
        return False

    def get_full_name(self):
        return self.email

    def get_shortname(self):
        return self.email

    def set_password(self, raw_password):
        # We don't want to save passwords locally
        self.set_unusable_password()
        self.raw_password = raw_password
        # TODO: Update password on CAS?

    def _create_user_in_db_and_cas(self):
        payload = {
            'email': self.email,
            'password': self.raw_password,
            'profile': self.profile,
        }

        status, data = auth_api_client.call('users', 'POST', payload)

        assert status == 201

        self.id = data['id']
        self.email = data['email']
        self.profile = data['profile']
        self.confirmation_token = data['confirmation_token']
        self.date_joined = parser.parse(data['created'])
        self.modified = parser.parse(data['modified'])

    def _update_user_in_cas(self):
        payload = {
            'email': self.email,
            'profile': self.profile,
        }

        status, data = auth_api_client.call(
            'users/{id}'.format(id=self.id), 'PUT', payload)

        assert status == 200

        self.email = data['email']
        self.profile = data['profile']
        self.modified = parser.parse(data['modified'])


@receiver(pre_delete, sender=KagisoUser)
def delete_user_from_cas(sender, instance, *args, **kwargs):
    status, data = auth_api_client.call(
        'users/{id}'.format(id=instance.id), 'DELETE')
    assert status == 204


@receiver(pre_save, sender=KagisoUser)
def save_user_to_cas(sender, instance, *args, **kwargs):
    if not instance.id:
        instance._create_user_in_db_and_cas()
    else:
        instance._update_user_in_cas()
