/*
 * Partage d'une actualité.
 * - « Partager… » : menu de partage du téléphone (Instagram, Messenger,
 *   WhatsApp, SMS...), affiché seulement si le navigateur le permet.
 * - Facebook, X, LinkedIn : petite fenêtre plutôt qu'un nouvel onglet.
 * - « Copier le lien » : copie l'adresse de l'article.
 */
(function () {
    "use strict";
    document.querySelectorAll("[data-partage]").forEach(function (bloc) {
        var url = bloc.dataset.url, titre = bloc.dataset.titre, texte = bloc.dataset.texte;

        // Menu de partage natif (surtout sur téléphone)
        var natif = bloc.querySelector("[data-partage-natif]");
        if (natif && navigator.share) {
            natif.closest(".partage__natif").hidden = false;
            natif.addEventListener("click", function () {
                navigator.share({ title: titre, text: texte || titre, url: url }).catch(function () {});
            });
        }

        // Fenêtre de partage
        bloc.querySelectorAll("[data-fenetre]").forEach(function (lien) {
            lien.addEventListener("click", function (e) {
                if (window.matchMedia("(max-width: 700px)").matches) { return; }   // mobile : onglet / application
                var l = 600, h = 560;
                var fenetre = window.open(lien.href, "partage",
                    "width=" + l + ",height=" + h + ",left=" + (screen.width - l) / 2 + ",top=" + (screen.height - h) / 2 +
                    ",noopener,noreferrer");
                if (fenetre !== null) { e.preventDefault(); }
            });
        });

        // Copier le lien
        var copier = bloc.querySelector("[data-partage-copier]");
        var libelle = bloc.querySelector("[data-partage-libelle]");
        var aide = bloc.querySelector("[data-partage-aide]");
        if (copier) {
            copier.addEventListener("click", function () {
                var reussi = function () {
                    libelle.textContent = "Lien copié ✓";
                    aide.hidden = false;
                    setTimeout(function () { libelle.textContent = "Copier le lien"; }, 2500);
                };
                if (navigator.clipboard && window.isSecureContext) {
                    navigator.clipboard.writeText(url).then(reussi, function () { window.prompt("Copiez le lien :", url); });
                } else {
                    window.prompt("Copiez le lien :", url);
                }
            });
        }
    });
})();
