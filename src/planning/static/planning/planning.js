/*
 * Planning des membres — La Concorde asbl
 * - Discussions : envoi sans rechargement et arrivée des nouveaux messages
 *   (interrogation du serveur toutes les 5 secondes, page visible
 *   seulement : o2switch n'accepte pas les connexions permanentes) ;
 * - Mentions : « @ » propose la liste des membres ;
 * - Pastille des notifications non lues, mise à jour chaque minute ;
 * - Formulaire de sondage : champs selon le type, lignes supplémentaires.
 */
(function () {
    "use strict";

    var DELAI_MESSAGES = 5000;
    var DELAI_NOTIFICATIONS = 60000;

    function csrf(form) {
        var champ = form.querySelector("input[name=csrfmiddlewaretoken]");
        return champ ? champ.value : "";
    }

    // --- Discussions ---------------------------------------------------------

    function elementMessage(m) {
        var div = document.createElement("div");
        div.className = "pl-message" + (m.moi ? " pl-message--moi" : "");
        div.dataset.id = m.id;
        var entete = document.createElement("div");
        entete.className = "pl-message__entete";
        var auteur = document.createElement("strong");
        auteur.textContent = m.auteur;
        var heure = document.createElement("span");
        heure.textContent = m.heure;
        entete.append(auteur, heure);
        var texte = document.createElement("div");
        texte.className = "pl-message__texte";
        div.append(entete, texte);
        remplir(div, m);
        return div;
    }

    // Contenu d'un message (à l'arrivée ou après une modification)
    function remplir(div, m) {
        div.querySelector(".pl-message__texte").innerHTML = m.html;  // HTML échappé par le serveur
        var entete = div.querySelector(".pl-message__entete");
        if (m.modifie && !entete.querySelector(".pl-message__modifie")) {
            var marque = document.createElement("em");
            marque.className = "pl-message__modifie";
            marque.textContent = "modifié";
            entete.insertBefore(marque, entete.querySelector(".pl-message__actions"));
        }
        if (m.url_modifier) {
            div.dataset.texte = m.texte;
            div.dataset.urlModifier = m.url_modifier;
            div.dataset.urlSupprimer = m.url_supprimer;
        }
    }

    // Boutons « Modifier » et « Supprimer » sur ses propres messages
    function ajouterActions(div, form) {
        if (!div.dataset.urlModifier || div.querySelector(".pl-message__actions")) return;
        var actions = document.createElement("span");
        actions.className = "pl-message__actions";
        var modifier = document.createElement("button");
        modifier.type = "button";
        modifier.textContent = "Modifier";
        var supprimer = document.createElement("button");
        supprimer.type = "button";
        supprimer.textContent = "Supprimer";
        actions.append(modifier, supprimer);
        div.querySelector(".pl-message__entete").appendChild(actions);

        function envoyer(url, donnees) {
            donnees.append("csrfmiddlewaretoken", csrf(form));
            return fetch(url, {
                method: "POST", body: donnees, credentials: "same-origin",
                headers: { "X-Requested-With": "fetch", "X-CSRFToken": csrf(form) }
            }).then(function (r) {
                if (!r.ok) throw new Error(r.status);
                return r.json();
            });
        }

        supprimer.addEventListener("click", function () {
            if (!window.confirm("Supprimer ce message ?")) return;
            envoyer(div.dataset.urlSupprimer, new FormData())
                .then(function () { div.remove(); })
                .catch(function () { window.alert("Le message n'a pas pu être supprimé."); });
        });

        modifier.addEventListener("click", function () {
            if (div.querySelector(".pl-message__edition")) return;
            var texte = div.querySelector(".pl-message__texte");
            var edition = document.createElement("div");
            edition.className = "pl-message__edition";
            var zone = document.createElement("textarea");
            zone.maxLength = 4000;
            zone.rows = 3;
            zone.value = div.dataset.texte;
            zone.setAttribute("aria-label", "Modifier le message");
            var enregistrer = document.createElement("button");
            enregistrer.type = "button";
            enregistrer.className = "btn btn--secondary btn--small";
            enregistrer.textContent = "Enregistrer";
            var annuler = document.createElement("button");
            annuler.type = "button";
            annuler.className = "btn btn--small";
            annuler.textContent = "Annuler";
            edition.append(zone, enregistrer, annuler);
            texte.hidden = true;
            actions.hidden = true;
            div.appendChild(edition);
            zone.focus();

            function fermer() {
                edition.remove();
                texte.hidden = false;
                actions.hidden = false;
            }
            function valider() {
                var valeur = zone.value.trim();
                if (!valeur) return;
                var donnees = new FormData();
                donnees.append("texte", valeur);
                enregistrer.disabled = true;
                envoyer(div.dataset.urlModifier, donnees)
                    .then(function (d) { if (d.message) remplir(div, d.message); fermer(); })
                    .catch(function () { window.alert("Le message n'a pas pu être modifié."); })
                    .finally(function () { enregistrer.disabled = false; });
            }
            annuler.addEventListener("click", fermer);
            enregistrer.addEventListener("click", valider);
            zone.addEventListener("keydown", function (e) {
                if (e.key === "Escape") { e.preventDefault(); fermer(); }
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); valider(); }
            });
        });
    }

    function initDiscussion(bloc) {
        var liste = bloc.querySelector("[data-messages]");
        var form = bloc.querySelector("form");
        var zone = form.querySelector("textarea");
        var url = bloc.dataset.url;
        var dernier = parseInt(bloc.dataset.dernier || "0", 10);
        var maj = bloc.dataset.maj || "";
        var enCours = false;

        function enBas() {
            return liste.scrollHeight - liste.scrollTop - liste.clientHeight < 60;
        }
        function ajouter(messages) {
            var defiler = enBas();
            var vide = liste.querySelector("[data-aucun-message]");
            messages.forEach(function (m) {
                if (m.id <= dernier || liste.querySelector('[data-id="' + m.id + '"]')) return;
                if (vide) { vide.remove(); vide = null; }
                var div = elementMessage(m);
                liste.appendChild(div);
                ajouterActions(div, form);
                dernier = m.id;
            });
            if (defiler && messages.length) liste.scrollTop = liste.scrollHeight;
        }
        // Messages modifiés ou supprimés par leur auteur depuis l'affichage
        function actualiser(d) {
            if (d.existants) {
                var restants = {};
                d.existants.forEach(function (id) { restants[id] = true; });
                liste.querySelectorAll(".pl-message[data-id]").forEach(function (div) {
                    var id = parseInt(div.dataset.id, 10);
                    if (id <= dernier && !restants[id]) div.remove();
                });
            }
            (d.modifies || []).forEach(function (m) {
                var div = liste.querySelector('.pl-message[data-id="' + m.id + '"]');
                if (div && !div.querySelector(".pl-message__edition")) remplir(div, m);
            });
            if (d.maj) maj = d.maj;
        }
        function recharger() {
            if (enCours || document.hidden) return;
            enCours = true;
            var premier = liste.querySelector(".pl-message[data-id]");
            var requete = "?apres=" + dernier;
            if (premier && maj) {
                requete += "&premier=" + premier.dataset.id + "&maj=" + encodeURIComponent(maj);
            }
            fetch(url + requete, { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" })
                .then(function (r) { return r.ok ? r.json() : { messages: [] }; })
                .then(function (d) { actualiser(d); ajouter(d.messages || []); })
                .catch(function () {})
                .finally(function () { enCours = false; });
        }

        liste.querySelectorAll(".pl-message[data-id]").forEach(function (div) { ajouterActions(div, form); });
        liste.scrollTop = liste.scrollHeight;
        setInterval(recharger, DELAI_MESSAGES);
        document.addEventListener("visibilitychange", recharger);

        form.addEventListener("submit", function (e) {
            e.preventDefault();
            var texte = zone.value.trim();
            if (!texte) return;
            var bouton = form.querySelector("button[type=submit]");
            bouton.disabled = true;
            var donnees = new FormData(form);
            fetch(url, {
                method: "POST", body: donnees, credentials: "same-origin",
                headers: { "X-Requested-With": "fetch", "X-CSRFToken": csrf(form) }
            })
                .then(function (r) { return r.json(); })
                .then(function (d) {
                    if (d.message) {
                        zone.value = "";
                        ajouter([d.message]);
                        liste.scrollTop = liste.scrollHeight;
                    }
                })
                .catch(function () { form.submit(); })
                .finally(function () { bouton.disabled = false; zone.focus(); });
        });

        // Entrée envoie, Maj+Entrée va à la ligne
        zone.addEventListener("keydown", function (e) {
            if (e.key === "Enter" && !e.shiftKey && !bloc.querySelector(".pl-mentions:not([hidden])")) {
                e.preventDefault();
                form.requestSubmit();
            }
        });

        initMentions(zone);
    }

    // --- Mentions -------------------------------------------------------------

    function initMentions(zone) {
        var source = document.getElementById("membres-mention");
        if (!source) return;
        var membres = JSON.parse(source.textContent);
        var menu = document.createElement("ul");
        menu.className = "pl-mentions";
        menu.hidden = true;
        menu.setAttribute("role", "listbox");
        zone.parentNode.appendChild(menu);
        var choix = [], rang = 0, debut = -1;

        function sans_accents(t) {
            return t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
        }
        function fermer() { menu.hidden = true; debut = -1; }
        function inserer(membre) {
            var avant = zone.value.slice(0, debut);
            var apres = zone.value.slice(zone.selectionStart);
            zone.value = avant + "@" + membre.identifiant + " " + apres;
            var pos = avant.length + membre.identifiant.length + 2;
            zone.setSelectionRange(pos, pos);
            fermer();
            zone.focus();
        }
        function afficher() {
            menu.innerHTML = "";
            choix.forEach(function (m, i) {
                var li = document.createElement("li");
                li.setAttribute("role", "option");
                li.setAttribute("aria-selected", i === rang ? "true" : "false");
                li.textContent = m.nom;
                var petit = document.createElement("small");
                petit.textContent = "@" + m.identifiant;
                li.appendChild(petit);
                li.addEventListener("mousedown", function (e) { e.preventDefault(); inserer(m); });
                menu.appendChild(li);
            });
            menu.hidden = !choix.length;
        }
        zone.addEventListener("input", function () {
            var avant = zone.value.slice(0, zone.selectionStart);
            var m = avant.match(/(^|\s)@([\w.+-]*)$/);
            if (!m) { fermer(); return; }
            debut = avant.length - m[2].length - 1;
            var recherche = sans_accents(m[2]);
            choix = membres.filter(function (x) {
                return sans_accents(x.nom).indexOf(recherche) !== -1 || x.identifiant.toLowerCase().indexOf(recherche) === 0;
            }).slice(0, 8);
            rang = 0;
            afficher();
        });
        zone.addEventListener("keydown", function (e) {
            if (menu.hidden) return;
            if (e.key === "ArrowDown" || e.key === "ArrowUp") {
                e.preventDefault();
                rang = (rang + (e.key === "ArrowDown" ? 1 : choix.length - 1)) % choix.length;
                afficher();
            } else if (e.key === "Enter" || e.key === "Tab") {
                e.preventDefault();
                inserer(choix[rang]);
            } else if (e.key === "Escape") {
                fermer();
            }
        });
        zone.addEventListener("blur", function () { setTimeout(fermer, 150); });
    }

    // --- Pastille des notifications -------------------------------------------

    function initNotifications() {
        var source = document.querySelector("[data-planning-notifications]");
        if (!source) return;
        var url = source.dataset.planningNotifications;
        setInterval(function () {
            if (document.hidden) return;
            fetch(url, { credentials: "same-origin" })
                .then(function (r) { return r.ok ? r.json() : null; })
                .then(function (d) {
                    if (!d) return;
                    document.querySelectorAll("[data-compteur-notifications]").forEach(function (el) {
                        el.textContent = d.non_lues;
                        el.hidden = !d.non_lues;
                    });
                })
                .catch(function () {});
        }, DELAI_NOTIFICATIONS);
    }

    // --- Formulaire de sondage --------------------------------------------------

    function initSondage(form) {
        var type = form.querySelector("[name=type]");
        var conteneur = form.querySelector("[data-options]");
        var total = form.querySelector("[name=options-TOTAL_FORMS]");
        function majType() {
            var date = type.value === "date";
            form.querySelectorAll("[data-pour-date]").forEach(function (el) { el.hidden = !date; });
            form.querySelectorAll("[data-pour-decision]").forEach(function (el) { el.hidden = date; });
            conteneur.querySelectorAll(".pl-options-ligne").forEach(function (l) {
                l.classList.toggle("pl-options-ligne--date", date);
            });
        }
        type.addEventListener("change", majType);
        majType();
        var bouton = form.querySelector("[data-ajouter-option]");
        if (bouton) {
            bouton.addEventListener("click", function () {
                var lignes = conteneur.querySelectorAll(".pl-options-ligne");
                var modele = lignes[lignes.length - 1];
                var n = parseInt(total.value, 10);
                var copie = modele.cloneNode(true);
                copie.querySelectorAll("input").forEach(function (input) {
                    input.name = input.name.replace(/options-\d+-/, "options-" + n + "-");
                    input.id = input.id.replace(/options-\d+-/, "options-" + n + "-");
                    input.value = "";
                });
                copie.querySelectorAll("label").forEach(function (label) {
                    label.htmlFor = label.htmlFor.replace(/options-\d+-/, "options-" + n + "-");
                });
                conteneur.appendChild(copie);
                total.value = n + 1;
            });
        }
    }

    // --- Plages horaires d'une tâche : lignes supplémentaires -------------------

    function initPlages(bouton) {
        var form = bouton.closest("form");
        var conteneur = form.querySelector("[data-options]");
        var total = form.querySelector("[name=plages-TOTAL_FORMS]");
        bouton.addEventListener("click", function () {
            var lignes = conteneur.querySelectorAll(".pl-options-ligne");
            var modele = lignes[lignes.length - 1];
            var n = parseInt(total.value, 10);
            var copie = modele.cloneNode(true);
            copie.querySelectorAll("input").forEach(function (input) {
                input.name = input.name.replace(/plages-\d+-/, "plages-" + n + "-");
                input.id = input.id.replace(/plages-\d+-/, "plages-" + n + "-");
                // Le jour de la ligne précédente est repris : seules les heures changent
                if (input.type !== "date") input.value = "";
            });
            copie.querySelectorAll("label").forEach(function (label) {
                label.htmlFor = label.htmlFor.replace(/plages-\d+-/, "plages-" + n + "-");
            });
            copie.querySelectorAll(".errorlist").forEach(function (el) { el.remove(); });
            conteneur.appendChild(copie);
            total.value = n + 1;
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("[data-ajouter-plage]").forEach(initPlages);
        document.querySelectorAll("[data-discussion]").forEach(initDiscussion);
        document.querySelectorAll("[data-sondage-form]").forEach(initSondage);
        initNotifications();
    });
})();
