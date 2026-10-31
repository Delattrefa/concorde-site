/**
 * Onglets de la page d'informations : un seul panneau visible, adresse
 * directe (/info/#onglet-historique), navigation au clavier par les flèches.
 */
(function () {
    "use strict";

    var bloc = document.querySelector("[data-onglets]");
    if (!bloc) return;
    var onglets = Array.prototype.slice.call(bloc.querySelectorAll('[role="tab"]'));

    function panneau(onglet) {
        return document.getElementById(onglet.getAttribute("aria-controls"));
    }

    function activer(actif) {
        onglets.forEach(function (onglet) {
            var choisi = onglet === actif;
            onglet.setAttribute("aria-selected", choisi ? "true" : "false");
            if (choisi) onglet.removeAttribute("tabindex");
            else onglet.setAttribute("tabindex", "-1");
            panneau(onglet).hidden = !choisi;
        });
    }

    function depuisAdresse() {
        var ancre = decodeURIComponent(window.location.hash.slice(1));
        var onglet = onglets.filter(function (o) {
            return o.getAttribute("aria-controls") === ancre;
        })[0];
        if (onglet) activer(onglet);
    }

    onglets.forEach(function (onglet, i) {
        onglet.addEventListener("click", function (event) {
            event.preventDefault();
            activer(onglet);
            history.replaceState(null, "", "#" + onglet.getAttribute("aria-controls"));
        });
        onglet.addEventListener("keydown", function (event) {
            var pas = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
            if (!pas) return;
            event.preventDefault();
            var suivant = onglets[(i + pas + onglets.length) % onglets.length];
            activer(suivant);
            suivant.focus();
        });
    });

    window.addEventListener("hashchange", depuisAdresse);
    depuisAdresse();
})();
