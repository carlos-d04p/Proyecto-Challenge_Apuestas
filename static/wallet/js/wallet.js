(function () {
    const app = document.querySelector("[data-wallet-app]");
    if (!app) {
        return;
    }

    const balanceNode = app.querySelector("[data-wallet-balance]");
    const pendingNode = app.querySelector("[data-wallet-pending]");
    const bonusNode = app.querySelector("[data-wallet-bonus]");
    const messageNode = app.querySelector("[data-wallet-message]");
    const balanceStateNode = app.querySelector("[data-wallet-balance-state]");
    const historyNode = app.querySelector("[data-wallet-history]");
    const historyTypeButtons = app.querySelectorAll("[data-history-type-filter]");
    const historyDateButtons = app.querySelectorAll("[data-history-date-filter]");
    const refreshButton = app.querySelector("[data-refresh-balance]");
    const forms = app.querySelectorAll("[data-wallet-form]");
    const openDepositButton = app.querySelector("[data-open-deposit]");
    const depositPanel = app.querySelector("[data-deposit-panel]");
    const openWithdrawButton = app.querySelector("[data-open-withdraw]");
    const withdrawPanel = app.querySelector("[data-withdraw-panel]");
    const promoForm = app.querySelector("[data-promo-form]");
    const promoState = app.querySelector("[data-promo-state]");
    const bonusList = app.querySelector("[data-bonus-list]");
    const bonusListState = app.querySelector("[data-bonus-list-state]");
    const welcomeBonusStatus = app.querySelector("[data-welcome-bonus-status]");
    const welcomeBonusAmount = app.querySelector("[data-welcome-bonus-amount]");
    const welcomeBonusHelp = app.querySelector("[data-welcome-bonus-help]");
    let historyMovements = [];
    let activeHistoryType = "all";
    let activeHistoryDays = null;

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
        messageNode.classList.remove("is-success", "is-error", "is-loading");
        if (type) {
            messageNode.classList.add(`is-${type}`);
        }
    }

    function setInlineState(node, text, type) {
        if (!node) {
            return;
        }
        node.textContent = text;
        node.classList.remove("is-success", "is-error", "is-loading");
        if (type) {
            node.classList.add(`is-${type}`);
        }
    }

    function getFriendlyError(error) {
        const message = String(error && error.message ? error.message : error);
        if (message.includes("Authentication credentials")) {
            return "Inicia sesion para operar tu wallet.";
        }
        if (message.toLowerCase().includes("saldo") || message.toLowerCase().includes("insufficient")) {
            return "Saldo disponible insuficiente.";
        }
        if (message.toLowerCase().includes("luhn") || message.toLowerCase().includes("tarjeta")) {
            return "Tarjeta simulada invalida.";
        }
        if (message.toLowerCase().includes("codigo") || message.toLowerCase().includes("code")) {
            return "Codigo promocional invalido.";
        }
        if (message.toLowerCase().includes("network") || message.toLowerCase().includes("failed to fetch")) {
            return "No se pudo conectar con el servidor.";
        }
        return message || "No se pudo completar la operacion.";
    }

    function setPromoState(text, type) {
        promoState.textContent = text;
        promoState.classList.remove("is-success", "is-error", "is-warning");
        if (type) {
            promoState.classList.add(`is-${type}`);
        }
    }

    function setWelcomeBonusState(status, amount) {
        if (!welcomeBonusStatus || !welcomeBonusAmount || !welcomeBonusHelp) {
            return;
        }

        const states = {
            available: {
                label: "Bono disponible",
                className: "is-available",
                help: "Bono de bienvenida disponible en la cuenta BONUS. No se mueve al saldo disponible desde el frontend.",
            },
            applied: {
                label: "Bono aplicado",
                className: "is-applied",
                help: "Bono aplicado. El saldo se actualiza solo con confirmacion del backend.",
            },
            used: {
                label: "Bono ya utilizado",
                className: "is-used",
                help: "El bono de bienvenida ya fue utilizado para esta cuenta.",
            },
            unavailable: {
                label: "Bono no disponible",
                className: "is-unavailable",
                help: "No hay bono de bienvenida disponible para esta cuenta.",
            },
            empty: {
                label: "Sin bonos activos",
                className: "is-unavailable",
                help: "Sin bonos activos por ahora.",
            },
        };
        const state = states[status] || states.empty;

        welcomeBonusStatus.textContent = state.label;
        welcomeBonusStatus.classList.remove("is-available", "is-applied", "is-used", "is-unavailable");
        welcomeBonusStatus.classList.add(state.className);
        welcomeBonusAmount.textContent = amount || "0.00";
        welcomeBonusHelp.textContent = state.help;
    }

    function getBonusStatusMeta(status) {
        const states = {
            available: { label: "Bono disponible", className: "is-available" },
            applied: { label: "Bono aplicado", className: "is-applied" },
            already_used: { label: "Bono ya utilizado", className: "is-used" },
            not_eligible: { label: "Usuario no elegible", className: "is-unavailable" },
            inactive: { label: "Bono no disponible", className: "is-unavailable" },
        };
        return states[status] || states.inactive;
    }

    function formatWalletAmount(value) {
        const normalizedValue = String(value ?? "0").trim().replace(",", ".");
        const numericValue = Number(normalizedValue);
        if (!Number.isFinite(numericValue)) {
            return "0.00";
        }
        return numericValue.toFixed(2);
    }

    function setBonusListState(text, status) {
        if (!bonusListState) {
            return;
        }
        const meta = getBonusStatusMeta(status);
        bonusListState.textContent = text;
        bonusListState.classList.remove("is-available", "is-applied", "is-used", "is-unavailable");
        bonusListState.classList.add(meta.className);
    }

    function renderBonuses(bonuses) {
        if (!bonusList) {
            return;
        }
        if (!bonuses.length) {
            bonusList.innerHTML = '<p class="wallet-muted">Sin bonos activos.</p>';
            setBonusListState("Sin bonos activos", "inactive");
            return;
        }

        const availableCount = bonuses.filter((bonus) => bonus.status === "available").length;
        setBonusListState(
            availableCount ? `${availableCount} bono(s) disponible(s)` : "Sin bonos disponibles",
            availableCount ? "available" : "inactive",
        );
        bonusList.innerHTML = bonuses.map((bonus) => {
            const meta = getBonusStatusMeta(bonus.status);
            const reason = bonus.reason || "No retirable hasta completar 5 apuestas válidas.";
            const progress = `${bonus.completed_bets_count || 0}/${bonus.required_bets_count || 5} apuestas`;
            return `
                <article class="wallet-bonus-card">
                    <div class="wallet-bonus-card-head">
                        <div>
                            <strong>${escapeHtml(bonus.name)}</strong>
                            <code>${escapeHtml(bonus.code)}</code>
                        </div>
                        <span class="wallet-bonus-state ${meta.className}">${meta.label}</span>
                    </div>
                    <div class="wallet-bonus-amount">
                        <span>Monto</span>
                        <b>${escapeHtml(formatWalletAmount(bonus.amount))}</b>
                    </div>
                    <p class="wallet-bonus-progress">Liberacion: ${escapeHtml(progress)}</p>
                    <p class="wallet-muted">${escapeHtml(reason)}</p>
                </article>
            `;
        }).join("");
    }

    function validateAmount(value) {
        const normalized = value.trim().replace(",", ".");
        if (!normalized) {
            throw new Error("Ingresa un monto en fichas.");
        }
        if (!/^\d+(\.\d+)?$/.test(normalized)) {
            throw new Error("Ingresa un monto valido.");
        }
        const decimals = normalized.split(".")[1] || "";
        if (decimals.length > 2) {
            throw new Error("El monto solo puede tener hasta 2 decimales.");
        }
        if (moneyToUnits(normalized) <= 0n) {
            throw new Error("El monto debe ser mayor a cero.");
        }
        return formatWalletAmount(normalized);
    }

    function moneyToUnits(value) {
        const [whole, fraction = ""] = value.split(".");
        return BigInt(whole) * 10000n + BigInt(fraction.padEnd(4, "0"));
    }

    function isValidLuhn(number) {
        let sum = 0;
        let shouldDouble = false;

        for (let index = number.length - 1; index >= 0; index -= 1) {
            let digit = Number(number.charAt(index));
            if (shouldDouble) {
                digit *= 2;
                if (digit > 9) {
                    digit -= 9;
                }
            }
            sum += digit;
            shouldDouble = !shouldDouble;
        }

        return sum % 10 === 0;
    }

    function parseExpiration(value) {
        const match = value.match(/^(0[1-9]|1[0-2])\/(\d{2})$/);
        if (!match) {
            throw new Error("Ingresa una fecha de expiracion simulada en formato MM/AA.");
        }

        const month = Number(match[1]);
        const year = 2000 + Number(match[2]);

        return { month, year };
    }

    function validateExpiration(value) {
        const { month, year } = parseExpiration(value.trim());
        const today = new Date();
        const currentMonth = today.getMonth() + 1;
        const currentYear = today.getFullYear();

        if (year < currentYear || (year === currentYear && month < currentMonth)) {
            throw new Error("La fecha de expiracion simulada no debe estar vencida.");
        }
    }

    function validateDepositSimulation(form) {
        const holder = form.querySelector("input[name='card_holder']").value.trim();
        const cardNumber = form.querySelector("input[name='card_number']").value.trim();
        const cardDigits = cardNumber.replace(/\s/g, "");
        const expiration = form.querySelector("input[name='expiration']").value.trim();
        const cvv = form.querySelector("input[name='cvv']").value.trim();

        if (holder.length < 3) {
            throw new Error("Ingresa el nombre del titular simulado con minimo 3 caracteres.");
        }
        if (!/^[\d\s]+$/.test(cardNumber)) {
            throw new Error("El numero de tarjeta simulada solo puede contener digitos y espacios.");
        }
        if (!/^\d{13,19}$/.test(cardDigits)) {
            throw new Error("El numero de tarjeta simulada debe tener entre 13 y 19 digitos.");
        }
        if (!isValidLuhn(cardDigits)) {
            throw new Error("El numero de tarjeta simulada no supera la validacion Luhn.");
        }
        validateExpiration(expiration);
        if (!/^\d+$/.test(cvv)) {
            throw new Error("El CVV simulado debe contener solo numeros.");
        }
        if (!/^\d{3,4}$/.test(cvv)) {
            throw new Error("Ingresa un CVV simulado de 3 o 4 digitos.");
        }
    }

    function validateWithdrawSimulation(form, amount) {
        const method = form.querySelector("select[name='withdraw_method']").value;
        const confirmation = form.querySelector("input[name='withdraw_confirmation']").checked;
        const available = balanceNode.textContent.trim() || "0.00";

        if (!method) {
            throw new Error("Selecciona un metodo simulado de retiro.");
        }
        if (!confirmation) {
            throw new Error("Confirma que el retiro es simulado y usa solo saldo disponible.");
        }
        if (moneyToUnits(amount) > moneyToUnits(available)) {
            throw new Error("Saldo disponible insuficiente. No puedes retirar fichas pendientes ni bonos.");
        }
    }

    function keepOnlyDigits(input) {
        input.value = input.value.replace(/\D/g, "");
    }

    function formatCardNumber(input) {
        const digits = input.value.replace(/\D/g, "").slice(0, 19);
        input.value = digits.replace(/(.{4})/g, "$1 ").trim();
    }

    function formatExpiration(input) {
        const digits = input.value.replace(/\D/g, "").slice(0, 4);
        if (digits.length <= 2) {
            input.value = digits;
            return;
        }
        input.value = `${digits.slice(0, 2)}/${digits.slice(2)}`;
    }

    async function parseResponse(response) {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const detail = data.detail || data.amount || "No se pudo completar la operacion.";
            throw new Error(getFriendlyError(Array.isArray(detail) ? detail.join(" ") : String(detail)));
        }
        return data;
    }

    async function refreshBalance() {
        refreshButton.disabled = true;
        setInlineState(balanceStateNode, "Cargando saldo...", "loading");
        try {
            const response = await fetch("/api/wallet/balance/", {
                headers: { "Accept": "application/json" },
                credentials: "same-origin",
            });
            const data = await parseResponse(response);
            const visibleBalance = formatWalletAmount(data.balance);
            balanceNode.textContent = visibleBalance;
            if (data.accounts && pendingNode && bonusNode) {
                pendingNode.textContent = formatWalletAmount(data.accounts.PENDING_BETS || "0.00");
                bonusNode.textContent = formatWalletAmount(data.accounts.BONUS || "0.00");
                setWelcomeBonusState(
                    moneyToUnits(data.accounts.BONUS || "0.00") > 0n ? "available" : "empty",
                    formatWalletAmount(data.accounts.BONUS || "0.00"),
                );
            }
            setInlineState(balanceStateNode, "Saldo actualizado.", "success");
            return visibleBalance;
        } finally {
            refreshButton.disabled = false;
        }
    }

    async function refreshBonuses() {
        if (!bonusList) {
            return;
        }
        setBonusListState("Cargando bonos", "inactive");
        bonusList.innerHTML = '<p class="wallet-muted">Cargando bonos disponibles...</p>';
        const response = await fetch("/api/wallet/bonuses/", {
            headers: { "Accept": "application/json" },
            credentials: "same-origin",
        });
        const data = await parseResponse(response);
        if (bonusNode) {
            bonusNode.textContent = formatWalletAmount(data.bonus_balance || bonusNode.textContent || "0.00");
        }
        renderBonuses(data.bonuses || []);
    }

    function formatDate(value) {
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return "-";
        }
        return new Intl.DateTimeFormat("es-PE", {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        }).format(date);
    }

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function matchesHistoryType(movement) {
        if (activeHistoryType === "all") {
            return true;
        }

        const type = movement.operation_type;
        const account = movement.account;
        const matchers = {
            deposit: () => type === "Recarga simulada",
            withdrawal: () => type === "Retiro simulado",
            bonus: () => type === "Bono" || type === "Bono promocional" || account === "BONUS",
            internal_transfer: () => type === "Transferencia interna",
            pending_bets: () => type === "Fichas pendientes en apuestas" || account === "PENDING_BETS",
        };

        return matchers[activeHistoryType] ? matchers[activeHistoryType]() : true;
    }

    function matchesHistoryDate(movement) {
        if (!activeHistoryDays) {
            return true;
        }

        const movementDate = new Date(movement.date);
        if (Number.isNaN(movementDate.getTime())) {
            return false;
        }
        const threshold = new Date();
        threshold.setDate(threshold.getDate() - activeHistoryDays);
        return movementDate >= threshold;
    }

    function getFilteredHistory() {
        return historyMovements.filter((movement) => matchesHistoryType(movement) && matchesHistoryDate(movement));
    }

    function updateHistoryFilterButtons() {
        historyTypeButtons.forEach((button) => {
            button.classList.toggle("is-active", button.dataset.historyTypeFilter === activeHistoryType);
        });
        historyDateButtons.forEach((button) => {
            button.classList.toggle("is-active", Number(button.dataset.historyDateFilter) === activeHistoryDays);
        });
    }

    function renderHistory(movements) {
        if (!historyNode) {
            return;
        }
        if (!movements.length) {
            const emptyText = historyMovements.length ? "Sin movimientos para el filtro seleccionado." : "Sin movimientos registrados.";
            historyNode.innerHTML = `<tr><td colspan="6"><span class="wallet-empty-state">${emptyText}</span></td></tr>`;
            return;
        }

        historyNode.innerHTML = movements.map((movement) => {
            const isDebit = movement.amount.startsWith("-");
            const amountClass = isDebit ? "is-debit" : "is-credit";
            const reference = movement.reference
                ? (movement.operation_type === "Bono promocional" ? movement.reference : `TX-${movement.reference}`)
                : "-";
            return `
                <tr>
                    <td>${formatDate(movement.date)}</td>
                    <td>${escapeHtml(movement.operation_type)}</td>
                    <td>${escapeHtml(movement.account_label)}</td>
                    <td class="${amountClass}">${escapeHtml(formatWalletAmount(movement.amount))}</td>
                    <td><span class="wallet-history-status">${escapeHtml(movement.status)}</span></td>
                    <td><code>${escapeHtml(reference)}</code></td>
                </tr>
            `;
        }).join("");
    }

    function applyHistoryFilters() {
        updateHistoryFilterButtons();
        renderHistory(getFilteredHistory());
    }

    async function refreshHistory() {
        if (!historyNode) {
            return;
        }
        historyNode.innerHTML = '<tr><td colspan="6"><span class="wallet-empty-state">Cargando movimientos...</span></td></tr>';
        const response = await fetch("/api/wallet/history/", {
            headers: { "Accept": "application/json" },
            credentials: "same-origin",
        });
        const data = await parseResponse(response);
        historyMovements = data.movements || [];
        applyHistoryFilters();
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

    async function submitPromoCode(code) {
        const endpoint = promoForm.dataset.promoEndpoint || "/api/wallet/bonuses/redeem/";
        if (!endpoint) {
            setPromoState("Bono no disponible. La validacion de codigos aun no esta habilitada.", "warning");
            setWelcomeBonusState("unavailable", welcomeBonusAmount ? welcomeBonusAmount.textContent : "0.00");
            return;
        }

        const response = await fetch(endpoint, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
                "Idempotency-Key": crypto.randomUUID(),
            },
            body: JSON.stringify({ code }),
        });
        const data = await parseResponse(response);
        const status = data.status || "applied";

        if (status === "applied") {
            setPromoState(data.message || "Bono aplicado.", "success");
            setWelcomeBonusState("applied", formatWalletAmount(data.amount || "0.00"));
            await refreshBalance();
            await refreshBonuses();
            await refreshHistory();
            return;
        }
        if (status === "already_used") {
            setPromoState("Bono ya usado para esta cuenta.", "warning");
            setWelcomeBonusState("used", formatWalletAmount(data.amount || "0.00"));
            return;
        }
        if (status === "not_available") {
            setPromoState("Bono no disponible para esta cuenta.", "warning");
            setWelcomeBonusState("unavailable", "0.00");
            return;
        }

        setPromoState("Codigo invalido.", "error");
        setWelcomeBonusState("unavailable", welcomeBonusAmount ? welcomeBonusAmount.textContent : "0.00");
    }

    forms.forEach((form) => {
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const button = form.querySelector("button");
            const defaultButtonText = button.textContent;
            const operationState = form.querySelector("[data-operation-state]");
            const input = form.querySelector("input[name='amount']");
            const kind = form.dataset.walletForm;

            try {
                const amount = validateAmount(input.value);
                if (kind === "deposit") {
                    validateDepositSimulation(form);
                }
                if (kind === "withdraw") {
                    validateWithdrawSimulation(form, amount);
                }
                const processingText = kind === "deposit" ? "Procesando recarga..." : "Procesando retiro...";
                const buttonText = kind === "deposit" ? "Procesando recarga" : "Procesando retiro";
                setInlineState(operationState, processingText, "loading");
                setMessage(processingText, "loading");
                button.disabled = true;
                button.textContent = buttonText;
                await submitOperation(kind, amount);
                const balance = await refreshBalance();
                await refreshBonuses();
                await refreshHistory();
                const label = kind === "deposit" ? "Recarga simulada" : "Retiro simulado";
                const successText = `${label} completado. Saldo: ${balance}.`;
                setMessage(successText, "success");
                setInlineState(operationState, successText, "success");
                form.reset();
            } catch (error) {
                const friendlyError = getFriendlyError(error);
                setMessage(friendlyError, "error");
                setInlineState(operationState, friendlyError, "error");
            } finally {
                button.disabled = false;
                button.textContent = defaultButtonText;
            }
        });
    });

    if (promoForm && promoState) {
        promoForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            const button = promoForm.querySelector("button");
            const input = promoForm.querySelector("input[name='promo_code']");
            const code = input.value.trim().toUpperCase();

            if (!code || !/^[A-Z0-9_-]{3,32}$/.test(code)) {
                setPromoState("Codigo promocional invalido.", "error");
                return;
            }

            try {
                button.disabled = true;
                setPromoState("Validando codigo...", "warning");
                await submitPromoCode(code);
                input.value = "";
            } catch (error) {
                setPromoState(getFriendlyError(error), "error");
            } finally {
                button.disabled = false;
            }
        });
    }

    historyTypeButtons.forEach((button) => {
        button.addEventListener("click", () => {
            activeHistoryType = button.dataset.historyTypeFilter;
            if (activeHistoryType === "all") {
                activeHistoryDays = null;
            }
            applyHistoryFilters();
        });
    });

    historyDateButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const days = Number(button.dataset.historyDateFilter);
            activeHistoryDays = activeHistoryDays === days ? null : days;
            if (activeHistoryDays) {
                activeHistoryType = activeHistoryType === "all" ? "all" : activeHistoryType;
            }
            applyHistoryFilters();
        });
    });

    if (openDepositButton && depositPanel) {
        openDepositButton.addEventListener("click", () => {
            depositPanel.hidden = false;
            openDepositButton.hidden = true;
            const amountInput = depositPanel.querySelector("input[name='amount']");
            if (amountInput) {
                amountInput.focus();
            }
        });
    }

    if (openWithdrawButton && withdrawPanel) {
        openWithdrawButton.addEventListener("click", () => {
            withdrawPanel.hidden = false;
            openWithdrawButton.hidden = true;
            const amountInput = withdrawPanel.querySelector("input[name='amount']");
            if (amountInput) {
                amountInput.focus();
            }
        });
    }

    app.querySelectorAll("input[name='card_number']").forEach((input) => {
        input.addEventListener("input", () => formatCardNumber(input));
    });

    app.querySelectorAll("input[name='expiration']").forEach((input) => {
        input.addEventListener("input", () => formatExpiration(input));
    });

    app.querySelectorAll("input[name='cvv']").forEach((input) => {
        input.addEventListener("input", () => keepOnlyDigits(input));
    });

    refreshButton.addEventListener("click", async () => {
        try {
            const balance = await refreshBalance();
            setMessage(`Saldo actualizado: ${balance}.`, "success");
        } catch (error) {
            const friendlyError = getFriendlyError(error);
            setMessage(friendlyError, "error");
            setInlineState(balanceStateNode, "No se pudo cargar saldo.", "error");
        }
    });

    refreshBalance().catch((error) => {
        const friendlyError = getFriendlyError(error);
        setMessage(friendlyError, "error");
        setInlineState(balanceStateNode, "No se pudo cargar saldo.", "error");
    });
    refreshBonuses().catch((error) => {
        setPromoState(getFriendlyError(error), "error");
        setBonusListState("No se pudo cargar bonos", "inactive");
    });
    refreshHistory().catch((error) => {
        setMessage(getFriendlyError(error), "error");
    });
})();
