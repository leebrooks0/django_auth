from django.contrib.auth.backends import ModelBackend
from django.db.models.signals import pre_save

from .auth_api_client import AuthApiClient
from .exceptions import CASUnexpectedStatusCode
from .models import KagisoUser, save_user_to_cas


class KagisoBackend(ModelBackend):

    # Django calls our backend with username='xyz', password='abc'
    # e.g. credentials = {'username': 'Fred', 'password': 'open'}
    # authenticate(**credentials), even though we set USERNAME_FIELD to
    # 'email' in models.py.
    #
    # Django AllAuth does this:
    #  credentials = {'email': 'test@kagiso.io, 'password': 'open'}
    def authenticate(self, email=None, username=None, password=None, **kwargs):
        cas_credentials = kwargs.get('cas_credentials')

        email = username if not email else email
        existing_user = KagisoUser.objects.filter(email=email).first()

        payload = {
            'email': email,
        }

        # Social signins don't have passwords
        if password:
            payload['password'] = password

        # Support social sign_ins
        strategy = kwargs.get('strategy')
        if strategy:
            payload['strategy'] = strategy

        auth_api_client = AuthApiClient(cas_credentials)
        status, data = auth_api_client.call('sessions', 'POST', payload)

        if status not in (200, 404,):
            raise CASUnexpectedStatusCode(status, data)

        if status == 200:
            if existing_user:
                existing_user.override_cas_credentials(cas_credentials)
            else:
                try:
                    # Do not on save sync to CAS, as we just got the user's
                    # data from CAS, and nothing has changed in the interim
                    pre_save.disconnect(save_user_to_cas, sender=KagisoUser)
                    existing_user = KagisoUser()
                    existing_user.set_password(password)
                    existing_user.build_from_cas_data(data)
                    existing_user.save()
                finally:
                    pre_save.connect(save_user_to_cas, sender=KagisoUser)

            return existing_user
