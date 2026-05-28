(function () {
    const app = document.querySelector("[data-wallet-app]");
    if (!app) {
        return;
    }

    const balanceNode = app.querySelector("[data-wallet-balance]");
    const messageNode = app.querySelector("[data-wallet-message]");
    const activityNode = app.querySelector("[data-wallet-activity]");
    const refreshButton = app.querySelector("[data-refresh-balance]");
    const forms = app.querySelectorAll("[data-wallet-form]");

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) {
            return parts.pop().split(";").shift();
        }
        return "";
    }

    function setMessage(text, type) {
        messageNode.textContent = text;
        messageNode.classList.remove("is-success", "is-error");
        if (type) {
            messageNode.classList.add(`is-${type}`);
        }
    }

    function addActivity(text) {
        if (activityNode.children.length === 1 && activityNode.children[0].textContent.includes("No hay")) {
            activityNode.innerHTML = "";
        }
        const item = document.createElement("li");
        item.textContent = text;
        activityNode.prepend(item);
    }

    function validateAmount(value) {
        const normalized = value.trim().replace(",", ".");
        if (!/^\d+(\.\d{1,4})?$/.test(normalized)) {
            throw new Error("Ingresa un monto valido con hasta 4 decimales.");
        }
        if (Number(normalized) <= 0) {
            throw new Error("El monto debe ser mayor a cero.");
        }
        return normalized;
    }

    async function parseResponse(response) {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const detail = data.detail || data.amount || "No se pudo completar la operacion.";
            throw new Error(Array.isArray(detail) ? detail.join(" ") : String(detail));
        }
        return data;
    }

    async function refreshBalance() {
        refreshButton.disabled = true;
        try {
            const response = await fetch("/api/wallet/balance/", {
                headers: { "Accept": "application/json" },
                credentials: "same-origin",
            });
            const data = await parseResponse(response);
            balanceNode.textContent = data.balance;
            return data.balance;
        } finally {
            refreshButton.disabled = false;
        }
    }

    async function submitOperation(kind, amount) {
        const endpoint = kind === "deposit" ? "/api/wallet/deposit/" : "/api/wallet/withdraw/";
        const response = await fetch(endpoint, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
                "Idempotency-Key": crypto.randomUUID(),
            },
            body: JSON.stringify({ amount }),
        });
        return parseResponse(response);
    }

    forms.forEach((form) => {
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const button = form.querySelector("button");
            const input = form.querySelector("input[name='amount']");
            const kind = form.dataset.walletForm;

            try {
                const amount = validateAmount(input.value);
                button.disabled = true;
                await submitOperation(kind, amount);
                const balance = await refreshBalance();
                const label = kind === "deposit" ? "Recarga simulada" : "Retiro simulado";
                setMessage(`${label} completado. Saldo actualizado: ${balance} fichas.`, "success");
                addActivity(`${label}: ${amount} fichas virtuales`);
                input.value = "";
            } catch (error) {
                setMessage(error.message, "error");
            } finally {
                button.disabled = false;
            }
        });
    });

    refreshButton.addEventListener("click", async () => {
        try {
            const balance = await refreshBalance();
            setMessage(`Saldo actualizado: ${balance} fichas virtuales.`, "success");
        } catch (error) {
            setMessage(error.message, "error");
        }
    });

    refreshBalance().catch((error) => {
        setMessage(error.message, "error");
    });
})();
