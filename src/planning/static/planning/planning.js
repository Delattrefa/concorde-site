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
        texte.innerHTML = m.html;  // HTML échappé par le serveur
        div.append(entete, texte);
        return div;
    }

    function initDiscussion(bloc) {
        var liste = bloc.querySelector("[data-messages]");
        var form = bloc.querySelector("form");
        var zone = form.querySelector("textarea");
        var url = bloc.dataset.url;
        var dernier = parseInt(bloc.dataset.dernier || "0", 10);
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
                liste.appendChild(elementMessage(m));
                dernier = m.id;
            });
            if (defiler && messages.length) liste.scrollTop = liste.scrollHeight;
        }
        function recharger() {
            if (enCours || document.hidden) return;
            enCours = true;
            fetch(url + "?apres=" + dernier, { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" })
                .then(function (r) { return r.ok ? r.json() : { messages: [] }; })
                .then(function (d) { ajouter(d.messages || []); })
                .catch(function () {})
                .finally(function () { enCours = false; });
        }

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

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll("[data-discussion]").forEach(initDiscussion);
        document.querySelectorAll("[data-sondage-form]").forEach(initSondage);
        initNotifications();
    });
})();
