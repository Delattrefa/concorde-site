"""
Tests du planning des membres : accès privé, agenda, répétitions,
créneaux et inscriptions, couverture, invitations, sondages, discussions,
mentions et notifications (y compris l'envoi groupé par e-mail).

Lancement : python manage.py test planning
"""
from datetime import date, datetime, time, timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Canal,
    Creneau,
    Disponibilite,
    Evenement,
    Inscription,
    Invitation,
    Message,
    Notification,
    Preferences,
    Sondage,
    Vote,
)
from .services import decouper, dates_repetees, rendre_message

Membre = get_user_model()


def moment(jour, heure, minute=0):
    return timezone.make_aware(datetime.combine(jour, time(heure, minute)))


class Base(TestCase):
    def setUp(self):
        self.jour = timezone.localdate() + timedelta(days=10)
        self.alice = Membre.objects.create_user("alice", "alice@exemple.be", "mdp", first_name="Alice", last_name="Martin")
        self.bob = Membre.objects.create_user("bob", "bob@exemple.be", "mdp", first_name="Bob", last_name="Dubois")
        self.chef = Membre.objects.create_user("chef", "chef@exemple.be", "mdp", first_name="Claire", is_staff=True)
        self.client.force_login(self.alice)

    def evenement(self, **champs):
        valeurs = {"type": Evenement.TYPE_ACTIVITE, "titre": "Marché de Noël", "createur": self.chef,
                   "debut": moment(self.jour, 10), "fin": moment(self.jour, 18)}
        valeurs.update(champs)
        return Evenement.objects.create(**valeurs)


class AccesTests(Base):
    def test_prive(self):
        self.client.logout()
        for nom in ("planning:accueil", "planning:couverture", "planning:sondages", "planning:canaux"):
            reponse = self.client.get(reverse(nom))
            self.assertEqual(reponse.status_code, 302)
            self.assertIn(reverse("login"), reponse["Location"])

    def test_vues_de_l_agenda(self):
        # Aujourd'hui : visible aussi sur /planning/ (mois en cours), quel que soit le jour du mois
        j = timezone.localdate()
        e = self.evenement(debut=moment(j, 23), fin=moment(j, 23, 30))
        for url in (reverse("planning:accueil"), reverse("planning:mois", args=[j.year, j.month]),
                    reverse("planning:semaine", args=[j.year, j.month, j.day]),
                    reverse("planning:jour", args=[j.year, j.month, j.day]), reverse("planning:liste")):
            self.assertContains(self.client.get(url), e.titre, msg_prefix=url)
        self.assertNotContains(self.client.get(reverse("planning:liste") + "?type=reunion"), e.titre)

    def test_reserve_aux_invites(self):
        e = self.evenement(titre="Réunion du CA", reserve_aux_invites=True)
        self.assertEqual(self.client.get(e.get_absolute_url()).status_code, 404)
        self.assertNotContains(self.client.get(reverse("planning:liste")), "Réunion du CA")
        Invitation.objects.create(evenement=e, membre=self.alice)
        self.assertEqual(self.client.get(e.get_absolute_url()).status_code, 200)

    def test_menu_reservations(self):
        reponse = self.client.get(reverse("planning:accueil"))
        self.assertContains(reponse, 'id="sous-menu-reservations"')
        self.assertContains(reponse, reverse("planning:accueil"))
        self.client.logout()
        self.assertNotContains(self.client.get(reverse("calendrier:mois_courant")), "sous-menu-reservations")

    def test_seul_l_auteur_ou_un_responsable_modifie(self):
        e = self.evenement()
        self.assertEqual(self.client.get(reverse("planning:evenement_modifier", args=[e.pk])).status_code, 403)
        self.client.force_login(self.chef)
        self.assertEqual(self.client.get(reverse("planning:evenement_modifier", args=[e.pk])).status_code, 200)


class EvenementTests(Base):
    def donnees(self, **champs):
        d = {"type": "reunion", "titre": "Réunion du comité", "description": "", "lieu": "Salle",
             "debut": f"{self.jour:%Y-%m-%d}T19:00", "fin": f"{self.jour:%Y-%m-%d}T21:00"}
        d.update(champs)
        return d

    def test_creation_avec_invitations_et_notifications(self):
        groupe = Group.objects.create(name="Comité")
        groupe.user_set.add(self.chef)
        reponse = self.client.post(reverse("planning:evenement_ajouter"),
                                   self.donnees(inviter_membres=[self.bob.pk], inviter_groupes=[groupe.pk]))
        e = Evenement.objects.get()
        self.assertRedirects(reponse, e.get_absolute_url())
        self.assertEqual(set(e.invitations.values_list("membre__username", flat=True)), {"bob", "chef"})
        self.assertTrue(Notification.objects.filter(destinataire=self.bob, genre=Notification.INVITATION).exists())
        self.assertTrue(Notification.objects.filter(destinataire=self.bob, genre=Notification.EVENEMENT).exists())
        self.assertFalse(Notification.objects.filter(destinataire=self.alice).exists())  # pas l'auteur

    def test_repetition_hebdomadaire_et_creneaux(self):
        fin_serie = self.jour + timedelta(weeks=3)
        self.client.post(reverse("planning:evenement_ajouter"), self.donnees(
            type="tache", titre="Ménage", repetition="hebdo", repeter_jusquau=f"{fin_serie:%Y-%m-%d}",
            duree_creneaux=60, besoin_creneaux=2))
        occurrences = list(Evenement.objects.order_by("debut"))
        self.assertEqual(len(occurrences), 4)
        self.assertEqual(len({o.serie for o in occurrences}), 1)
        self.assertEqual([timezone.localtime(o.debut).date() for o in occurrences],
                         [self.jour + timedelta(weeks=i) for i in range(4)])
        for o in occurrences:
            self.assertEqual([c.besoin for c in o.creneaux.all()], [2, 2])
            self.assertEqual(timezone.localtime(o.creneaux.first().debut).time(), time(19, 0))

    def test_modifier_toute_la_serie(self):
        self.client.post(reverse("planning:evenement_ajouter"), self.donnees(
            repetition="hebdo", repeter_jusquau=f"{self.jour + timedelta(weeks=2):%Y-%m-%d}"))
        premiere, *suivantes = Evenement.objects.order_by("debut")
        self.client.post(reverse("planning:evenement_modifier", args=[premiere.pk]), self.donnees(
            titre="Comité (nouvelle heure)", debut=f"{self.jour:%Y-%m-%d}T20:00", fin=f"{self.jour:%Y-%m-%d}T22:00",
            appliquer_serie="on"))
        for o in Evenement.objects.all():
            self.assertEqual(o.titre, "Comité (nouvelle heure)")
            self.assertEqual(timezone.localtime(o.debut).hour, 20)
        # Chaque occurrence garde sa date
        self.assertEqual(timezone.localtime(Evenement.objects.get(pk=suivantes[0].pk).debut).date(),
                         self.jour + timedelta(weeks=1))

    def test_annuler_puis_supprimer_la_serie(self):
        self.client.post(reverse("planning:evenement_ajouter"), self.donnees(
            repetition="2semaines", repeter_jusquau=f"{self.jour + timedelta(weeks=4):%Y-%m-%d}"))
        premiere = Evenement.objects.order_by("debut").first()
        self.client.post(reverse("planning:evenement_annuler", args=[premiere.pk]), {"portee": "une"})
        self.assertEqual(Evenement.objects.filter(annule=True).count(), 1)
        self.client.post(reverse("planning:evenement_supprimer", args=[premiere.pk]), {"portee": "suivantes"})
        self.assertFalse(Evenement.objects.exists())

    def test_fin_avant_debut_refusee(self):
        reponse = self.client.post(reverse("planning:evenement_ajouter"),
                                   self.donnees(fin=f"{self.jour:%Y-%m-%d}T18:00"))
        self.assertContains(reponse, "La fin doit être après le début")

    def test_repetition_mensuelle_saute_les_mois_courts(self):
        debut = timezone.make_aware(datetime(2027, 1, 31, 19))
        dates = [d.date() for d in dates_repetees(debut, "mois", date(2027, 5, 31))]
        self.assertEqual(dates, [date(2027, 3, 31), date(2027, 5, 31)])


class CreneauxTests(Base):
    def test_decouper(self):
        e = self.evenement(debut=moment(self.jour, 10), fin=moment(self.jour, 15))
        creneaux = decouper(e, 120, 2)
        self.assertEqual([(timezone.localtime(c.debut).hour, timezone.localtime(c.fin).hour) for c in creneaux],
                         [(10, 12), (12, 14), (14, 15)])

    def test_inscription_en_un_clic_et_complet(self):
        e = self.evenement()
        c = Creneau.objects.create(evenement=e, debut=e.debut, fin=e.fin, besoin=1)
        self.client.post(reverse("planning:creneau_inscrire", args=[c.pk]))
        self.assertTrue(Inscription.objects.filter(creneau=c, membre=self.alice).exists())
        self.client.force_login(self.bob)
        self.client.post(reverse("planning:creneau_inscrire", args=[c.pk]))
        self.assertFalse(Inscription.objects.filter(creneau=c, membre=self.bob).exists())
        self.client.force_login(self.alice)
        self.client.post(reverse("planning:creneau_desinscrire", args=[c.pk]))
        self.assertFalse(c.inscriptions.exists())
        self.assertTrue(Notification.objects.filter(destinataire=self.chef, texte__contains="désinscrit").exists())

    def test_affecter_un_membre_reserve_aux_responsables(self):
        e = self.evenement()
        c = Creneau.objects.create(evenement=e, debut=e.debut, fin=e.fin, besoin=2)
        self.assertEqual(self.client.post(reverse("planning:creneau_inscrire", args=[c.pk]), {"membre": self.bob.pk}).status_code, 403)
        self.client.force_login(self.chef)
        self.client.post(reverse("planning:creneau_inscrire", args=[c.pk]), {"membre": self.bob.pk})
        self.assertTrue(c.inscriptions.filter(membre=self.bob).exists())
        self.assertTrue(Notification.objects.filter(destinataire=self.bob, texte__contains="vous a inscrit").exists())

    def test_couverture_et_bouche_trou(self):
        e = self.evenement()
        trou = Creneau.objects.create(evenement=e, debut=e.debut, fin=e.debut + timedelta(hours=2), besoin=2, libelle="Bar")
        complet = Creneau.objects.create(evenement=e, debut=e.debut, fin=e.debut + timedelta(hours=2), besoin=1, libelle="Caisse")
        Inscription.objects.create(creneau=complet, membre=self.bob)
        Disponibilite.objects.create(membre=self.bob, date=self.jour)
        reponse = self.client.get(reverse("planning:couverture"))
        self.assertContains(reponse, "Bar")
        self.assertNotContains(reponse, "Caisse")
        self.assertEqual(reponse.context["stats"]["manque"], 2)
        self.client.post(reverse("planning:creneau_inscrire", args=[trou.pk]), {"retour": reverse("planning:couverture")})
        self.assertTrue(trou.inscriptions.filter(membre=self.alice).exists())
        # Le responsable voit tout, et qui est disponible ce jour-là
        self.client.force_login(self.chef)
        reponse = self.client.get(reverse("planning:couverture") + "?tout=1")
        self.assertContains(reponse, "Caisse")
        self.assertContains(reponse, "Bob Dubois (toute la journée)")

    def test_alerte_creneau_urgent_une_seule_fois(self):
        demain = timezone.localdate() + timedelta(days=1)
        e = self.evenement(debut=moment(demain, 10), fin=moment(demain, 12))
        Creneau.objects.create(evenement=e, debut=e.debut, fin=e.fin, besoin=2)
        call_command("planning_taches", stdout=StringIO())
        self.assertEqual(Notification.objects.filter(genre=Notification.URGENCE).count(), 3)  # tous les membres
        call_command("planning_taches", stdout=StringIO())
        self.assertEqual(Notification.objects.filter(genre=Notification.URGENCE).count(), 3)


class InvitationsTests(Base):
    def test_repondre(self):
        e = self.evenement(type=Evenement.TYPE_REUNION)
        Invitation.objects.create(evenement=e, membre=self.alice)
        self.client.post(reverse("planning:evenement_repondre", args=[e.pk]), {"statut": "accepte", "commentaire": "Avec plaisir"})
        invitation = Invitation.objects.get()
        self.assertEqual((invitation.statut, invitation.commentaire), (Invitation.ACCEPTEE, "Avec plaisir"))
        self.assertTrue(Notification.objects.filter(destinataire=self.chef, texte__contains="accepte").exists())
        self.assertContains(self.client.get(reverse("planning:invitations")), "Accepté")


class SondagesTests(Base):
    def test_sondage_de_date_puis_reunion(self):
        reponse = self.client.post(reverse("planning:sondage_nouveau"), {
            "type": "date", "titre": "Prochain comité", "description": "",
            "options-TOTAL_FORMS": "2", "options-INITIAL_FORMS": "0",
            "options-0-date": f"{self.jour:%Y-%m-%d}", "options-0-heure_debut": "19:00", "options-0-heure_fin": "21:00",
            "options-1-date": f"{self.jour + timedelta(days=1):%Y-%m-%d}", "options-1-heure_debut": "19:00",
        })
        sondage = Sondage.objects.get()
        self.assertRedirects(reponse, sondage.get_absolute_url())
        self.assertEqual(Notification.objects.filter(genre=Notification.SONDAGE).count(), 2)  # bob et chef
        o1, o2 = sondage.options.all()
        self.client.post(reverse("planning:sondage_voter", args=[sondage.pk]), {f"option_{o1.pk}": "oui", f"option_{o2.pk}": "si_besoin"})
        self.client.force_login(self.bob)
        self.client.post(reverse("planning:sondage_voter", args=[sondage.pk]), {f"option_{o1.pk}": "oui", f"option_{o2.pk}": "non"})
        reponse = self.client.get(sondage.get_absolute_url())
        meilleures = [o for o in reponse.context["options"] if o.meilleur]
        self.assertEqual(meilleures, [o1])
        # Planifier : date reprise, votants invités
        self.client.force_login(self.alice)
        reponse = self.client.get(reverse("planning:evenement_ajouter") + f"?sondage={sondage.pk}&option={o1.pk}")
        form = reponse.context["form"]
        self.assertEqual(form.initial["debut"].hour, 19)
        self.assertEqual(set(form.initial["inviter_membres"]), {self.alice.pk, self.bob.pk})

    def test_sondage_de_decision_choix_unique(self):
        sondage = Sondage.objects.create(type=Sondage.TYPE_DECISION, titre="Couleur des t-shirts", createur=self.chef)
        rouge = sondage.options.create(libelle="Rouge")
        bleu = sondage.options.create(libelle="Bleu")
        self.client.post(reverse("planning:sondage_voter", args=[sondage.pk]), {"choix": [rouge.pk, bleu.pk]})
        self.assertEqual(list(Vote.objects.values_list("option", flat=True)), [rouge.pk])

    def test_sondage_cible(self):
        sondage = Sondage.objects.create(titre="Pour Bob seulement", createur=self.chef)
        sondage.destinataires.add(self.bob)
        self.assertEqual(self.client.get(sondage.get_absolute_url()).status_code, 404)
        self.assertNotContains(self.client.get(reverse("planning:sondages")), "Pour Bob seulement")

    def test_au_moins_deux_options(self):
        reponse = self.client.post(reverse("planning:sondage_nouveau"), {
            "type": "decision", "titre": "Oui ou non ?", "options-TOTAL_FORMS": "1", "options-INITIAL_FORMS": "0",
            "options-0-libelle": "Oui",
        })
        self.assertContains(reponse, "au moins deux")
        self.assertFalse(Sondage.objects.exists())


class DiscussionTests(Base):
    def test_message_mention_et_lecture(self):
        canal = Canal.objects.get(nom="Général")
        url = reverse("planning:canal_messages", args=[canal.pk])
        reponse = self.client.post(url, {"texte": "Bonjour @bob, tu viens ?"}, HTTP_X_REQUESTED_WITH="fetch")
        donnees = reponse.json()["message"]
        self.assertIn('<span class="mention">@Bob Dubois</span>', donnees["html"])
        self.assertTrue(donnees["moi"])
        self.assertTrue(Notification.objects.filter(destinataire=self.bob, genre=Notification.MENTION).exists())
        # Bob reçoit le message en interrogeant le serveur
        self.client.force_login(self.bob)
        messages_recus = self.client.get(url, {"apres": 0}).json()["messages"]
        self.assertEqual([m["auteur"] for m in messages_recus], ["Alice Martin"])
        self.assertEqual(self.client.get(url, {"apres": messages_recus[-1]["id"]}).json()["messages"], [])

    def test_fil_d_un_evenement_previent_les_participants(self):
        e = self.evenement()
        c = Creneau.objects.create(evenement=e, debut=e.debut, fin=e.fin)
        Inscription.objects.create(creneau=c, membre=self.bob)
        self.assertContains(self.client.get(e.get_absolute_url()), "data-discussion")
        canal = e.canal
        self.client.post(reverse("planning:canal_messages", args=[canal.pk]), {"texte": "J'apporte les rallonges"})
        destinataires = set(Notification.objects.filter(genre=Notification.MESSAGE).values_list("destinataire__username", flat=True))
        self.assertEqual(destinataires, {"bob", "chef"})

    def test_texte_echappe(self):
        html = rendre_message("<script>alert(1)</script> https://exemple.be", {})
        self.assertNotIn("<script>", html)
        self.assertIn('href="https://exemple.be"', html)

    def test_canal_d_un_evenement_prive_invisible(self):
        e = self.evenement(reserve_aux_invites=True)
        canal = Canal.objects.create(nom="CA", evenement=e)
        self.assertEqual(self.client.get(reverse("planning:canal_messages", args=[canal.pk])).status_code, 404)

    def test_creer_un_canal_reserve_aux_responsables(self):
        self.assertEqual(self.client.get(reverse("planning:canal_nouveau")).status_code, 403)


class NotificationsTests(Base):
    def test_compteur_lecture_et_email_groupe(self):
        Preferences.objects.create(membre=self.bob, email_evenements=False)
        self.client.post(reverse("planning:evenement_ajouter"), {
            "type": "reunion", "titre": "AG", "debut": f"{self.jour:%Y-%m-%d}T19:00", "fin": f"{self.jour:%Y-%m-%d}T21:00",
            "inviter_membres": [self.bob.pk],
        })
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(reverse("planning:notifications_compte")).json()["non_lues"], 2)
        call_command("planning_taches", stdout=StringIO())
        # Un seul e-mail par membre ; Bob ne veut pas les e-mails « événement »
        destinataires = sorted(m.to[0] for m in mail.outbox)
        self.assertEqual(destinataires, ["bob@exemple.be", "chef@exemple.be"])
        bob = next(m for m in mail.outbox if m.to == ["bob@exemple.be"])
        self.assertIn("vous invite", bob.subject)
        self.assertIn("/planning/evenement/", bob.body)
        call_command("planning_taches", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 2)  # rien de renvoyé
        notification = Notification.objects.filter(destinataire=self.bob).first()
        self.client.get(reverse("planning:notification_ouvrir", args=[notification.pk]))
        notification.refresh_from_db()
        self.assertTrue(notification.lue)
        self.client.post(reverse("planning:notifications_tout_lu"))
        self.assertEqual(self.client.get(reverse("planning:notifications_compte")).json()["non_lues"], 0)

    def test_message_non_envoye_par_email_par_defaut(self):
        canal = Canal.objects.get(nom="Général")
        e = self.evenement()
        Invitation.objects.create(evenement=e, membre=self.bob)
        from .services import canal_de, publier
        publier(canal_de(e), self.alice, "Simple message")
        notification = Notification.objects.get(destinataire=self.bob)
        self.assertFalse(notification.a_envoyer)
        self.assertEqual(canal.messages.count(), 0)
        self.assertEqual(Message.objects.count(), 1)


class OrdreTests(Base):
    def test_couverture_chronologique(self):
        tard = self.evenement(titre="Plus tard", debut=moment(self.jour + timedelta(days=5), 9), fin=moment(self.jour + timedelta(days=5), 11))
        tot = self.evenement(titre="Plus tôt")
        for e in (tard, tot):
            Creneau.objects.create(evenement=e, debut=e.debut, fin=e.fin, besoin=1)
        titres = [b["evenement"].titre for b in self.client.get(reverse("planning:couverture")).context["evenements"]]
        self.assertEqual(titres, ["Plus tôt", "Plus tard"])


class TableauDesTachesTests(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.chef)
        self.e = self.evenement(debut=moment(self.jour, 14), fin=moment(self.jour, 23))

    def ajouter_tache(self, libelle, plages, besoin=2, **champs):
        donnees = {"libelle": libelle, "besoin": besoin, "plages-TOTAL_FORMS": str(len(plages)),
                   "plages-INITIAL_FORMS": "0", **champs}
        for i, (de, a) in enumerate(plages):
            donnees.update({f"plages-{i}-date": f"{self.jour:%Y-%m-%d}", f"plages-{i}-heure_debut": de,
                            f"plages-{i}-heure_fin": a})
        return self.client.post(reverse("planning:tache_ajouter", args=[self.e.pk]), donnees)

    def grille(self):
        return self.client.get(self.e.get_absolute_url()).context["grille"]

    def test_colonnes_lignes_et_cases_grisees(self):
        self.ajouter_tache("Montage", [("14:00", "17:00")])
        self.ajouter_tache("Bar", [("18:00", "20:00"), ("20:00", "22:00")])
        self.ajouter_tache("Vaisselle", [("21:00", "23:00")], besoin=3)
        g = self.grille()
        self.assertEqual([c["tache"] for c in g["colonnes"]], ["Montage", "Bar", "Vaisselle"])
        horaires = [(timezone.localtime(l["debut"]).strftime("%H:%M"), timezone.localtime(l["fin"]).strftime("%H:%M"))
                    for l in g["lignes"]]
        # 17 h–18 h : personne n'est attendu, la ligne disparaît
        self.assertEqual(horaires, [("14:00", "17:00"), ("18:00", "20:00"), ("20:00", "21:00"),
                                    ("21:00", "22:00"), ("22:00", "23:00")])
        lignes = [[("vide" if "vide" in case else f"{case['creneau'].libelle}×{case['hauteur']}") for case in l["cases"]]
                  for l in g["lignes"]]
        self.assertEqual(lignes, [
            ["Montage×1", "vide", "vide"],
            ["vide", "Bar×1", "vide"],
            ["vide", "Bar×2", "vide"],   # le bar de 20 h à 22 h s'étend sur deux lignes
            ["vide", "Vaisselle×2"],     # case du bar absente (rowspan)
            ["vide", "vide"],            # 22 h–23 h : bar fini, vaisselle en cours (rowspan)
        ])
        self.assertContains(self.client.get(self.e.get_absolute_url()), "pl-case-grille--indispo")

    def test_plage_passant_minuit_et_decoupage(self):
        self.ajouter_tache("Bar", [("22:00", "02:00")], duree=120)
        creneaux = list(self.e.creneaux.order_by("debut"))
        self.assertEqual([(timezone.localtime(c.debut).hour, timezone.localtime(c.fin).hour) for c in creneaux],
                         [(22, 0), (0, 2)])
        self.assertEqual(timezone.localtime(creneaux[-1].fin).date(), self.jour + timedelta(days=1))

    def test_inscription_dans_une_case(self):
        self.ajouter_tache("Caisse", [("18:00", "20:00")], besoin=1)
        case = self.e.creneaux.get()
        self.client.force_login(self.alice)
        self.client.post(reverse("planning:creneau_inscrire", args=[case.pk]))
        g = self.grille()
        self.assertEqual([m.username for m in g["lignes"][0]["cases"][0]["creneau"].inscrits], ["alice"])
        self.assertContains(self.client.get(self.e.get_absolute_url()), "pl-case-grille--complet")

    def test_modifier_et_supprimer_une_tache(self):
        self.ajouter_tache("Bar", [("18:00", "20:00"), ("20:00", "22:00")])
        Inscription.objects.create(creneau=self.e.creneaux.first(), membre=self.bob)
        url = reverse("planning:tache_modifier", args=[self.e.pk]) + "?tache=Bar"
        self.client.post(url, {"libelle": "Bar à bières", "besoin": 3, "tache_initiale": "Bar",
                               "plages-TOTAL_FORMS": "1", "plages-INITIAL_FORMS": "0",
                               "plages-0-date": f"{self.jour:%Y-%m-%d}", "plages-0-heure_debut": "22:00",
                               "plages-0-heure_fin": "23:00"})
        self.assertEqual(set(self.e.creneaux.values_list("libelle", "besoin")), {("Bar à bières", 3)})
        self.assertEqual(self.e.creneaux.count(), 3)
        self.client.post(reverse("planning:tache_supprimer", args=[self.e.pk]) + "?tache=Bar%20%C3%A0%20bi%C3%A8res")
        self.assertFalse(self.e.creneaux.exists())
        self.assertTrue(Notification.objects.filter(destinataire=self.bob, texte__contains="Tâche supprimée").exists())

    def test_nom_de_tache_deja_pris_et_plage_obligatoire(self):
        self.ajouter_tache("Bar", [("18:00", "20:00")])
        self.assertContains(self.ajouter_tache("Bar", [("20:00", "22:00")]), "existe déjà")
        self.assertContains(self.ajouter_tache("Caisse", []), "au moins une plage")

    def test_reserve_a_l_auteur_et_aux_responsables(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.ajouter_tache("Bar", [("18:00", "20:00")]).status_code, 403)

    def test_une_activite_creee_enchaine_sur_les_taches(self):
        reponse = self.client.post(reverse("planning:evenement_ajouter"), {
            "type": "activite", "titre": "Brocante", "debut": f"{self.jour:%Y-%m-%d}T08:00",
            "fin": f"{self.jour:%Y-%m-%d}T18:00"})
        nouvel = Evenement.objects.get(titre="Brocante")
        self.assertRedirects(reponse, reverse("planning:tache_ajouter", args=[nouvel.pk]))
        formulaire = self.client.get(reverse("planning:tache_ajouter", args=[nouvel.pk]))
        self.assertContains(formulaire, 'value="08:00"')  # première plage = horaires de l'événement
