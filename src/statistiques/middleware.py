"""
Compte les pages vues du site public (voir mesure.py). Sans cookie ni
script : la mesure se fait côté serveur, une fois la page produite.
"""
from .mesure import mesurer


class MesureAudienceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        mesurer(request, response)
        return response
