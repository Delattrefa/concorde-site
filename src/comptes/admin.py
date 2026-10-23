"""
Invitations des nouveaux membres, dans l'administration Django.
Réservé aux super-utilisateurs : enregistrer une invitation envoie l'e-mail.
"""
from django.contrib import admin, messages

from .forms import InvitationAdminForm
from .models import InvitationMembre
from .services import envoyer_invitation


class SuperUtilisateurSeulement:
    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)


@admin.register(InvitationMembre)
class InvitationMembreAdmin(SuperUtilisateurSeulement, admin.ModelAdmin):
    form = InvitationAdminForm
    list_display = ["email", "nom_invite", "statut_affiche", "invite_par", "envoyee_le", "expire_le", "membre"]
    search_fields = ["email", "prenom", "nom"]
    actions = ["renvoyer", "annuler"]
    readonly_fields = ["statut_affiche", "invite_par", "envoyee_le", "expire_le", "acceptee_le", "membre"]

    @admin.display(description="Nom")
    def nom_invite(self, obj):
        return f"{obj.prenom} {obj.nom}".strip() or "—"

    @admin.display(description="Statut")
    def statut_affiche(self, obj):
        return obj.get_statut_display() if obj.pk else "—"

    def get_fields(self, request, obj=None):
        if obj is None:
            return ["email", "prenom", "nom", "message"]
        return ["email", "prenom", "nom", "message", *self.readonly_fields]

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return []
        # Une invitation envoyée ne se modifie plus : on l'annule ou on la renvoie
        return ["email", "prenom", "nom", "message", *self.readonly_fields]

    def _envoyer(self, request, invitation, jeton):
        try:
            envoyer_invitation(invitation, jeton)
            return True
        except Exception as erreur:
            self.message_user(
                request,
                f"L'e-mail à {invitation.email} n'a pas pu partir ({erreur}). Transmettez-lui vous-même ce lien "
                f"personnel : {InvitationMembre.lien(jeton)}",
                messages.ERROR,
            )
            return False

    def save_model(self, request, obj, form, change):
        if change:
            return super().save_model(request, obj, form, change)
        obj.invite_par = request.user
        jeton = obj.nouveau_jeton()
        super().save_model(request, obj, form, change)
        if self._envoyer(request, obj, jeton):
            self.message_user(request, f"Invitation envoyée à {obj.email}.", messages.SUCCESS)

    @admin.action(description="Renvoyer l'invitation (nouveau lien, valable à nouveau 14 jours)")
    def renvoyer(self, request, queryset):
        envoyees = 0
        for invitation in queryset:
            if invitation.statut == InvitationMembre.ACCEPTEE:
                continue
            invitation.annulee = False
            jeton = invitation.nouveau_jeton()
            invitation.save()
            envoyees += self._envoyer(request, invitation, jeton)
        if envoyees:
            self.message_user(request, f"{envoyees} invitation(s) renvoyée(s).", messages.SUCCESS)

    @admin.action(description="Annuler l'invitation (le lien ne fonctionne plus)")
    def annuler(self, request, queryset):
        nombre = queryset.filter(acceptee_le=None).update(annulee=True)
        self.message_user(request, f"{nombre} invitation(s) annulée(s).", messages.SUCCESS)
