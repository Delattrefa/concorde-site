/**
 * Effets de fondu / ouverture au défilement.
 * Chaque élément portant une classe .fade-up / .fade-in-left / .fade-in-right
 * reçoit la classe .is-visible dès qu'il entre dans le champ de vision,
 * ce qui déclenche la transition CSS correspondante (voir main.css).
 */
(function () {
    "use strict";

    var targets = document.querySelectorAll(
        ".fade-up, .fade-in-left, .fade-in-right"
    );

    if ("IntersectionObserver" in window && targets.length) {
        var observer = new IntersectionObserver(
            function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("is-visible");
                        observer.unobserve(entry.target);
                    }
                });
            },
            { threshold: 0.15, rootMargin: "0px 0px -60px 0px" }
        );

        targets.forEach(function (el) {
            observer.observe(el);
        });
    } else {
        // Navigateur trop ancien : on affiche directement le contenu
        targets.forEach(function (el) {
            el.classList.add("is-visible");
        });
    }

    // Menu mobile : ouverture / fermeture du panneau (navigation + recherche)
    var toggle = document.querySelector(".nav-toggle");
    var menu = document.querySelector(".site-menu");
    if (toggle && menu) {
        var fermerMenu = function () {
            menu.classList.remove("is-open");
            toggle.setAttribute("aria-expanded", "false");
            toggle.setAttribute("aria-label", "Ouvrir le menu");
        };

        toggle.addEventListener("click", function () {
            var isOpen = menu.classList.toggle("is-open");
            toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
            toggle.setAttribute("aria-label", isOpen ? "Fermer le menu" : "Ouvrir le menu");
        });

        // Fermer après le choix d'un lien, avec la touche Échap, ou en
        // touchant la page en dehors du menu.
        menu.addEventListener("click", function (e) {
            if (e.target.closest("a")) { fermerMenu(); }
        });
        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape" && menu.classList.contains("is-open")) {
                fermerMenu();
                toggle.focus();
            }
        });
        document.addEventListener("click", function (e) {
            if (menu.classList.contains("is-open") && !menu.contains(e.target) && !toggle.contains(e.target)) {
                fermerMenu();
            }
        });
        // Revenu en grand écran : on réinitialise l'état du menu.
        window.addEventListener("resize", function () {
            if (window.innerWidth > 1100) { fermerMenu(); }
        });
    }

    // Sous-menus déroulants du menu principal : le bouton ▾ ouvre / ferme
    // son sous-menu (au clic, au toucher ou au clavier) ; un seul ouvert à
    // la fois. Au survol de la souris, l'ouverture est gérée en CSS.
    var parents = document.querySelectorAll(".main-nav__item--parent");
    if (parents.length) {
        var basculerSousMenu = function (item, ouvrir) {
            item.classList.toggle("is-open", ouvrir);
            var bouton = item.querySelector(".main-nav__deplier");
            if (bouton) { bouton.setAttribute("aria-expanded", ouvrir ? "true" : "false"); }
        };
        var fermerSousMenus = function (sauf) {
            parents.forEach(function (item) {
                if (item !== sauf) { basculerSousMenu(item, false); }
            });
        };

        parents.forEach(function (item) {
            var bouton = item.querySelector(".main-nav__deplier");
            if (!bouton) { return; }
            bouton.addEventListener("click", function () {
                var ouvrir = !item.classList.contains("is-open");
                fermerSousMenus(item);
                basculerSousMenu(item, ouvrir);
            });
            // Navigation au clavier : on referme quand le focus quitte l'élément
            item.addEventListener("focusout", function (e) {
                if (e.relatedTarget && !item.contains(e.relatedTarget)) {
                    basculerSousMenu(item, false);
                }
            });
        });

        document.addEventListener("keydown", function (e) {
            if (e.key !== "Escape") { return; }
            var ouvert = document.querySelector(".main-nav__item--parent.is-open");
            if (ouvert) {
                basculerSousMenu(ouvert, false);
                ouvert.querySelector(".main-nav__deplier").focus();
            }
        });
        document.addEventListener("click", function (e) {
            if (!e.target.closest(".main-nav__item--parent")) { fermerSousMenus(null); }
        });
    }
})();
