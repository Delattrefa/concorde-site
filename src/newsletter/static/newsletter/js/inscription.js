/*
 * Inscription à la newsletter en AJAX (sans rechargement de la page).
 * Sans JavaScript, le formulaire est envoyé normalement et la page se
 * recharge avec le message : les deux chemins donnent le même résultat.
 */
(function () {
    "use strict";
    var form = document.querySelector("[data-newsletter-form]");
    if (!form || !window.fetch) { return; }

    var zoneMessage = document.querySelector("[data-message]");
    var bouton = form.querySelector("[data-bouton]");

    function afficherMessage(texte, succes) {
        zoneMessage.innerHTML = "";
        var p = document.createElement("p");
        p.className = "newsletter-message newsletter-message--" + (succes ? "success" : "error");
        p.textContent = texte;
        zoneMessage.appendChild(p);
        zoneMessage.hidden = false;
        zoneMessage.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }

    function effacerErreurs() {
        form.querySelectorAll("[data-erreur]").forEach(function (el) { el.textContent = ""; });
        form.querySelectorAll(".form-field--error").forEach(function (el) { el.classList.remove("form-field--error"); });
    }

    form.addEventListener("submit", function (e) {
        e.preventDefault();
        effacerErreurs();

        // Vérification immédiate (le serveur contrôle à nouveau, plus strictement)
        var email = form.querySelector('input[name="email"]');
        if (!email.value.trim() || !email.checkValidity()) {
            form.querySelector('[data-erreur="email"]').textContent = "Indiquez une adresse e-mail valide.";
            email.closest(".form-field").classList.add("form-field--error");
            email.focus();
            return;
        }

        bouton.disabled = true;
        fetch(form.action, {
            method: "POST",
            body: new FormData(form),
            headers: { "X-Requested-With": "XMLHttpRequest" },
            credentials: "same-origin"
        })
            .then(function (reponse) {
                return reponse.json().catch(function () {
                    throw new Error("Réponse inattendue du serveur.");
                });
            })
            .then(function (donnees) {
                afficherMessage(donnees.message, donnees.succes);
                if (donnees.succes) {
                    form.reset();
                    return;
                }
                Object.keys(donnees.erreurs || {}).forEach(function (champ) {
                    var zone = form.querySelector('[data-erreur="' + champ + '"]');
                    if (zone) { zone.textContent = donnees.erreurs[champ].join(" "); }
                    var input = form.querySelector('[name="' + champ + '"]');
                    if (input && input.closest(".form-field")) { input.closest(".form-field").classList.add("form-field--error"); }
                });
            })
            .catch(function () {
                afficherMessage("Une erreur est survenue. Merci de réessayer dans quelques instants.", false);
            })
            .then(function () { bouton.disabled = false; });
    });
})();
