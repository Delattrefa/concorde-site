/*
 * Consentement aux cookies — La Concorde asbl
 * - Affiche le bandeau tant qu'aucun choix n'a été fait (ou après expiration).
 * - Remplace les contenus externes bloqués (iframe[data-consent-src]) par un
 *   message, et les charge une fois acceptés.
 * - Le lien « Gérer les cookies » (pied de page) rouvre le bandeau.
 */
(function () {
    "use strict";

    var banniere = document.getElementById("cookies-banniere");
    if (!banniere) { return; }

    var NOM = banniere.dataset.cookieNom;
    var VERSION = banniere.dataset.cookieVersion;
    var DUREE_JOURS = parseInt(banniere.dataset.cookieDuree || "182", 10);

    var details = document.getElementById("cookies-details");
    var caseExternes = document.getElementById("cookies-externes");
    var boutonPersonnaliser = banniere.querySelector('[data-cookies-action="personnaliser"]');
    var boutonEnregistrer = banniere.querySelector('[data-cookies-action="enregistrer"]');

    var SERVICES = [
        [/google\./, "Google Maps"],
        [/youtube|youtu\.be/, "YouTube"],
        [/vimeo\./, "Vimeo"],
        [/facebook\.|fb\./, "Facebook"],
        [/instagram\./, "Instagram"],
        [/soundcloud\./, "SoundCloud"],
        [/spotify\./, "Spotify"]
    ];

    /* ---------- Lecture / écriture du choix ---------- */
    function lireChoix() {
        var m = document.cookie.match(new RegExp("(?:^|; )" + NOM + "=([^;]*)"));
        if (!m || m[1].indexOf(VERSION + "_") !== 0) { return null; }
        return { externes: m[1] === VERSION + "_externes_1" };
    }

    function enregistrerChoix(choix) {
        var valeur = VERSION + "_externes_" + (choix.externes ? "1" : "0");
        var cookie = NOM + "=" + valeur + "; Max-Age=" + (DUREE_JOURS * 86400) + "; Path=/; SameSite=Lax";
        if (location.protocol === "https:") { cookie += "; Secure"; }
        document.cookie = cookie;
    }

    /* ---------- Contenus externes ---------- */
    function nomService(domaine) {
        for (var i = 0; i < SERVICES.length; i++) {
            if (SERVICES[i][0].test(domaine)) { return SERVICES[i][1]; }
        }
        return domaine;
    }

    function afficherMessagesBlocage() {
        document.querySelectorAll("iframe[data-consent-src]").forEach(function (cadre) {
            var precedent = cadre.previousElementSibling;
            if (precedent && precedent.classList.contains("cookies-bloque")) { return; }

            var service = nomService(cadre.getAttribute("data-consent-domaine") || "");
            var bloc = document.createElement("div");
            bloc.className = "cookies-bloque";

            var texte = document.createElement("p");
            texte.textContent = "Ce contenu est fourni par " + service +
                ", qui peut déposer des cookies. Il ne s'affiche qu'avec votre accord.";
            var bouton = document.createElement("button");
            bouton.type = "button";
            bouton.className = "btn btn--primary";
            bouton.textContent = "Afficher ce contenu";
            bouton.addEventListener("click", function () {
                enregistrerChoix({ externes: true });
                activerContenus();
                fermerBanniere();
                signalerChoix({ externes: true });
            });

            bloc.appendChild(texte);
            bloc.appendChild(bouton);
            cadre.hidden = true;
            cadre.parentNode.insertBefore(bloc, cadre);
        });
    }

    function activerContenus() {
        document.querySelectorAll("iframe[data-consent-src]").forEach(function (cadre) {
            var precedent = cadre.previousElementSibling;
            if (precedent && precedent.classList.contains("cookies-bloque")) { precedent.remove(); }
            cadre.src = cadre.getAttribute("data-consent-src");
            cadre.removeAttribute("data-consent-src");
            cadre.hidden = false;
        });
    }

    /* ---------- Bandeau ---------- */
    function ouvrirBanniere(avecDetails) {
        var choix = lireChoix();
        caseExternes.checked = !!(choix && choix.externes);
        afficherDetails(!!avecDetails);
        banniere.hidden = false;
        var premier = banniere.querySelector("button:not([hidden])");
        if (premier) { premier.focus({ preventScroll: true }); }
    }

    function fermerBanniere() { banniere.hidden = true; }

    function afficherDetails(visible) {
        details.hidden = !visible;
        boutonEnregistrer.hidden = !visible;
        boutonPersonnaliser.hidden = visible;
        boutonPersonnaliser.setAttribute("aria-expanded", visible ? "true" : "false");
    }

    function signalerChoix(choix) {
        document.dispatchEvent(new CustomEvent("concorde:consentement", { detail: choix }));
    }

    function appliquer(choix) {
        var avant = lireChoix();
        enregistrerChoix(choix);
        signalerChoix(choix);
        fermerBanniere();
        if (choix.externes) {
            activerContenus();
        } else if (avant && avant.externes) {
            // Retrait du consentement : on recharge pour décharger les contenus tiers.
            location.reload();
        } else {
            afficherMessagesBlocage();
        }
    }

    banniere.addEventListener("click", function (e) {
        var bouton = e.target.closest("[data-cookies-action]");
        if (!bouton) { return; }
        var action = bouton.getAttribute("data-cookies-action");
        if (action === "accepter") { appliquer({ externes: true }); }
        else if (action === "refuser") { appliquer({ externes: false }); }
        else if (action === "personnaliser") { afficherDetails(true); }
        else if (action === "enregistrer") { appliquer({ externes: caseExternes.checked }); }
    });

    document.addEventListener("click", function (e) {
        if (e.target.closest("[data-cookies-ouvrir]")) {
            e.preventDefault();
            ouvrirBanniere(true);
        }
    });

    /* ---------- Au chargement ---------- */
    var choix = lireChoix();
    if (!choix) {
        afficherMessagesBlocage();
        ouvrirBanniere(false);
    } else if (choix.externes) {
        activerContenus();
    } else {
        afficherMessagesBlocage();
    }
    /* ---------- API pour les autres scripts (ex. visionneuse de la galerie) ---------- */
    window.ConcordeConsentement = {
        externesAcceptes: function () {
            var c = lireChoix();
            return !!(c && c.externes);
        },
        accepterExternes: function () {
            enregistrerChoix({ externes: true });
            activerContenus();
            fermerBanniere();
            signalerChoix({ externes: true });
        },
        ouvrirReglages: function () { ouvrirBanniere(true); }
    };
})();
