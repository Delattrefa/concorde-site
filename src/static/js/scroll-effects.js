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
})();
