from django.contrib.auth.backends import ModelBackend

from . import auth_api_client
from .exceptions import CASException
from .models import KagisoUser


class KagisoBackend(ModelBackend):

    # Django calls our backend with username='xyz', password='abc'
    # e.g. credentials = {'username': 'Fred', 'password': 'open'}
    # authenticate(**credentials), even though we set USERNAME_FIELD to
    # 'email' in models.py.
    #
    # Django AllAuth does this:
    #  credentials = {'email': 'test@kagiso.io, 'password': 'open'}
    def authenticate(self, email=None, username=None, password=None, **kwargs):
        email = username if not email else email
        user = KagisoUser.objects.filter(email=email).first()

        if not user:
            return

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

        status, data = auth_api_client.call('sessions', 'POST', payload)

        if status not in (200, 404,):
            raise CASException(status, data)

        if status == 200:
            return user
