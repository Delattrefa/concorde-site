"""
Connexion avec l'identifiant OU l'adresse e-mail du compte.
Les membres invités reçoivent un identifiant « prenom.nom », mais retiennent
plus facilement leur adresse e-mail.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class IdentifiantOuEmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username and "@" in username:
            comptes = list(get_user_model().objects.filter(email__iexact=username.strip())[:2])
            if len(comptes) == 1:  # adresse partagée par deux comptes : on ne devine pas
                membre = comptes[0]
                if membre.check_password(password) and self.user_can_authenticate(membre):
                    return membre
                return None
        return super().authenticate(request, username=username, password=password, **kwargs)
