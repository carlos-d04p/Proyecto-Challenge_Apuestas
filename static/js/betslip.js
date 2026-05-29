document.addEventListener('DOMContentLoaded', () => {
    const betSlipContainer = document.getElementById('bet-slip-container');
    if (!betSlipContainer) return;

    let betSlip = JSON.parse(localStorage.getItem('fairbet_betslip')) || [];
    let betSlipMode = localStorage.getItem('fairbet_mode') || 'SIMPLES';
    let isBetslipMinimized = false;

    window.toggleBetslip = function() {
        isBetslipMinimized = !isBetslipMinimized;
        renderBetSlip();
    };

    window.addToBetSlip = function(id, name, odds, eventId, eventName, marketName = 'Mercado') {
        const existingSelectionIndex = betSlip.findIndex(item => item.id === id);
        if (existingSelectionIndex > -1) {
            return;
        }
        
        // Si el usuario agrega opciones excluyentes (mismo mercado del mismo evento),
        // forzamos el modo SIMPLES, ya que no se pueden combinar.
        let hasSameMarket = betSlip.some(item => item.eventId === eventId && item.marketName === marketName);
        if (hasSameMarket && betSlipMode === 'COMBINADA') {
            betSlipMode = 'SIMPLES';
            localStorage.setItem('fairbet_mode', 'SIMPLES');
            // Muestra un pequeño toast o dejamos que el cambio visual hable por sí solo
        }
        
        if (betSlip.length >= 10) {
            alert("Máximo 10 selecciones permitidas en el boleto.");
            return;
        }

        betSlip.push({ id, name, odds: parseFloat(odds), eventId, eventName, marketName, stake: 10 });
        saveAndRender();
    };

    window.removeFromBetSlip = function(id) {
        betSlip = betSlip.filter(item => item.id !== id);
        saveAndRender();
    };

    window.clearBetSlip = function() {
        betSlip = [];
        saveAndRender();
    };
    
    window.setBetSlipMode = function(mode) {
        if (mode === 'COMBINADA') {
            // Validate exclusivity by MARKET (mutually exclusive)
            let conflict = false;
            let seenMarkets = new Set();
            for (let item of betSlip) {
                let key = item.eventId + '_' + item.marketName;
                if (seenMarkets.has(key)) {
                    conflict = true;
                    break;
                }
                seenMarkets.add(key);
            }
            if (conflict) {
                alert("No puedes armar una Combinada con opciones mutuamente excluyentes (del mismo mercado). Se mantendrán como Simples.");
                return;
            }
        }
        betSlipMode = mode;
        localStorage.setItem('fairbet_mode', mode);
        saveAndRender();
    };

    function saveAndRender() {
        localStorage.setItem('fairbet_betslip', JSON.stringify(betSlip));
        renderBetSlip();
    }
    
    window.updateSingleStake = function(id, val) {
        let item = betSlip.find(i => i.id === id);
        if (item) {
            item.stake = parseFloat(val) || 0;
            saveAndRender(); // Re-render to update payouts
        }
    }

    function renderBetSlip() {
        if (betSlip.length === 0) {
            betSlipContainer.innerHTML = '';
            betSlipContainer.style.display = 'none';
            return;
        }

        betSlipContainer.style.display = 'block';

        if (isBetslipMinimized) {
            betSlipContainer.innerHTML = `
                <div class="betslip-header" style="display: flex; justify-content: space-between; align-items: center; cursor: pointer; margin-bottom: 0;" onclick="toggleBetslip()">
                    <h3 style="margin: 0; font-size: 1rem;">⚽ Boleto (${betSlip.length})</h3>
                    <span style="color: var(--primary); font-size: 0.85rem; font-weight: 600;">🔼 Maximizar</span>
                </div>
            `;
            return;
        }

        const tabsHtml = `
            <div class="betslip-tabs" style="display: flex; gap: 0.5rem; margin-bottom: 1rem;">
                <button type="button" onclick="setBetSlipMode('SIMPLES')" style="flex: 1; padding: 0.5rem; border-radius: 20px; border: 1px solid var(--border); background: ${betSlipMode === 'SIMPLES' ? 'var(--primary)' : 'transparent'}; color: ${betSlipMode === 'SIMPLES' ? '#fff' : 'var(--text)'}; cursor: pointer; font-weight: 600; font-size: 0.85rem; transition: 0.2s;">Simples</button>
                <button type="button" onclick="setBetSlipMode('COMBINADA')" style="flex: 1; padding: 0.5rem; border-radius: 20px; border: 1px solid var(--border); background: ${betSlipMode === 'COMBINADA' ? 'var(--primary)' : 'transparent'}; color: ${betSlipMode === 'COMBINADA' ? '#fff' : 'var(--text)'}; cursor: pointer; font-weight: 600; font-size: 0.85rem; transition: 0.2s;">Combinada</button>
            </div>
        `;

        let totalOdds = 1.0;
        let selectionsHtml = '';
        
        let hasConflictForAcca = false;
        let seenMarkets = new Set();
        
        if (betSlipMode === 'COMBINADA') {
            const groupedBets = {};
            betSlip.forEach(item => {
                totalOdds *= item.odds;
                if (!groupedBets[item.eventId]) {
                    groupedBets[item.eventId] = { eventName: item.eventName, selections: [] };
                }
                groupedBets[item.eventId].selections.push(item);
                
                let key = item.eventId + '_' + item.marketName;
                if (seenMarkets.has(key)) hasConflictForAcca = true;
                seenMarkets.add(key);
            });

            Object.values(groupedBets).forEach(group => {
                selectionsHtml += `
                    <div class="betslip-event-group" style="margin-bottom: 0.75rem; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: hidden;">
                        <div class="betslip-group-header" style="background: rgba(255,255,255,0.05); padding: 0.5rem 0.75rem; font-weight: 600; font-size: 0.85rem; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 0.4rem;">
                            ⚽ ${group.eventName}
                        </div>
                        <div class="betslip-group-body" style="padding: 0.25rem 0;">
                `;
                group.selections.forEach(item => {
                    const displayMarket = item.marketName || 'Mercado';
                    selectionsHtml += `
                            <div class="betslip-item" style="padding: 0.4rem 0.75rem; display: flex; justify-content: space-between; align-items: center; border-radius: 0; margin: 0; background: transparent; border: none; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                <div style="display: flex; flex-direction: column; gap: 0.15rem;">
                                    <span class="betslip-sel-name" style="font-size: 0.85rem; font-weight: 600; color: var(--text);">${item.name}</span>
                                    <span class="betslip-sel-market" style="font-size: 0.7rem; color: var(--text-soft);">${displayMarket}</span>
                                </div>
                                <div style="display: flex; align-items: center; gap: 0.75rem;">
                                    <span class="betslip-sel-odds" style="font-weight: 700; color: var(--primary);">${item.odds.toFixed(2)}</span>
                                    <button type="button" class="betslip-remove-btn" onclick="removeFromBetSlip('${item.id}')" style="color: var(--text-soft); font-size: 0.9rem; padding: 0.2rem; display: flex; align-items: center; justify-content: center; width: 24px; height: 24px; border-radius: 4px; background: rgba(255,255,255,0.1); cursor: pointer; border: none; transition: background 0.2s;">✕</button>
                                </div>
                            </div>
                    `;
                });
                selectionsHtml += `</div></div>`;
            });
            
        } else {
            // SIMPLES MODE (Grouped by Event)
            const groupedBets = {};
            betSlip.forEach(item => {
                if (!groupedBets[item.eventId]) {
                    groupedBets[item.eventId] = { eventName: item.eventName, selections: [] };
                }
                groupedBets[item.eventId].selections.push(item);
            });

            Object.values(groupedBets).forEach(group => {
                selectionsHtml += `
                    <div class="betslip-event-group" style="margin-bottom: 0.75rem; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: hidden;">
                        <div class="betslip-group-header" style="background: rgba(255,255,255,0.05); padding: 0.5rem 0.75rem; font-weight: 600; font-size: 0.85rem; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 0.4rem;">
                            ⚽ ${group.eventName}
                        </div>
                        <div class="betslip-group-body" style="padding: 0.25rem 0;">
                `;
                group.selections.forEach(item => {
                    const displayMarket = item.marketName || 'Mercado';
                    const itemPayout = (item.stake || 10) * item.odds;
                    selectionsHtml += `
                            <div class="betslip-item" style="padding: 0.5rem 0.75rem; border-radius: 0; margin: 0; background: transparent; border: none; border-bottom: 1px solid rgba(255,255,255,0.05);">
                                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
                                    <div>
                                        <div style="font-size: 0.9rem; font-weight: 600; color: var(--text);">${item.name}</div>
                                        <div style="font-size: 0.75rem; color: var(--text-soft);">${displayMarket}</div>
                                    </div>
                                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                                        <span style="font-weight: 700; color: var(--primary); font-size: 1.1rem;">${item.odds.toFixed(2)}</span>
                                        <button type="button" onclick="removeFromBetSlip('${item.id}')" style="color: var(--text-soft); font-size: 0.9rem; padding: 0.2rem; display: flex; align-items: center; justify-content: center; width: 24px; height: 24px; border-radius: 4px; background: rgba(255,255,255,0.1); cursor: pointer; border: none;">✕</button>
                                    </div>
                                </div>
                                <div style="display: flex; gap: 0.5rem; align-items: center; margin-top: 0.5rem; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 0.5rem;">
                                    <span style="font-size: 0.8rem; color: var(--text-soft);">Fichas:</span>
                                    <input type="number" class="single-stake-input" data-id="${item.id}" name="stake" value="${item.stake || 10}" min="10" step="0.01" style="width: 80px; padding: 0.3rem; border-radius: 4px; border: 1px solid var(--border); background: #111; color: white;" required>
                                    <input type="hidden" name="selection_id" value="${item.id}">
                                    <input type="hidden" name="expected_odds" value="${item.odds.toFixed(4)}">
                                    <div style="margin-left: auto; font-size: 0.8rem;">Retorno: <span style="color: var(--green); font-weight: 600;">${itemPayout.toFixed(2)}</span></div>
                                </div>
                            </div>
                    `;
                });
                selectionsHtml += `</div></div>`;
            });
        }

        const betTypeValue = betSlipMode === 'COMBINADA' ? 'ACCA' : 'SINGLE';

        let formHtml = '';
        if (betSlipMode === 'COMBINADA') {
            formHtml = `
                <div class="betslip-summary">
                    <div class="betslip-row">
                        <span>Cuota Total:</span>
                        <span class="betslip-total-odds">${totalOdds.toFixed(2)}</span>
                    </div>
                </div>
                <form id="betslip-form" action="/apuestas/apostar/" method="POST">
                    <input type="hidden" name="csrfmiddlewaretoken" value="${getCookie('csrftoken')}">
                    <input type="hidden" name="bet_type" value="${betTypeValue}">
                    <input type="hidden" name="expected_odds" value="${totalOdds.toFixed(4)}">
                    ${betSlip.map(item => `<input type="hidden" name="selection_id" value="${item.id}">`).join('')}
                    
                    <div class="betslip-stake-input">
                        <label>Monto a apostar (Fichas):</label>
                        <input type="number" id="betslip-stake" name="stake" min="10" step="0.01" value="10" required>
                    </div>

                    <div style="margin: 0.75rem 0; display: flex; align-items: center; gap: 0.5rem; background: rgba(255,255,255,0.05); padding: 0.5rem; border-radius: 6px;">
                        <input type="checkbox" id="use_bonus_checkbox" name="use_bonus" value="true" style="accent-color: var(--primary); cursor: pointer; width: 16px; height: 16px;">
                        <label for="use_bonus_checkbox" style="cursor: pointer; font-size: 0.85rem; margin:0; user-select: none;">Usar saldo de bono para esta apuesta</label>
                    </div>
                    
                    <div id="betslip-alert" class="betslip-alert" style="display: none;"></div>
                    
                    <div class="betslip-row betslip-payout">
                        <span>Retorno Potencial:</span>
                        <span id="betslip-potential-payout">${(10 * totalOdds).toFixed(2)}</span>
                    </div>
                    
                    <div class="betslip-actions">
                        <button type="button" class="btn-clear" onclick="clearBetSlip()">Limpiar</button>
                        <button type="submit" class="filter-btn active" id="betslip-submit-btn">Apostar</button>
                    </div>
                </form>
            `;
        } else {
            // Simples form
            let totalSimplesStake = betSlip.reduce((sum, item) => sum + (item.stake || 10), 0);
            let totalSimplesPayout = betSlip.reduce((sum, item) => sum + ((item.stake || 10) * item.odds), 0);
            
            formHtml = `
                <form id="betslip-form" action="/apuestas/apostar/" method="POST">
                    <input type="hidden" name="csrfmiddlewaretoken" value="${getCookie('csrftoken')}">
                    <input type="hidden" name="bet_type" value="${betTypeValue}">
                    
                    <!-- Selection and stakes inputs are rendered inside the items -->
                    ${selectionsHtml}
                    
                    <div style="margin: 0.75rem 0; display: flex; align-items: center; gap: 0.5rem; background: rgba(255,255,255,0.05); padding: 0.5rem; border-radius: 6px;">
                        <input type="checkbox" id="use_bonus_checkbox" name="use_bonus" value="true" style="accent-color: var(--primary); cursor: pointer; width: 16px; height: 16px;">
                        <label for="use_bonus_checkbox" style="cursor: pointer; font-size: 0.85rem; margin:0; user-select: none;">Usar saldo de bono para esta apuesta</label>
                    </div>
                    
                    <div id="betslip-alert" class="betslip-alert" style="display: none;"></div>
                    
                    <div class="betslip-summary" style="margin-top: 1rem; border-top: 1px solid var(--border); padding-top: 1rem;">
                        <div class="betslip-row" style="margin-bottom: 0.5rem;">
                            <span>Apuestas Totales:</span>
                            <span style="font-weight: 600;">${betSlip.length}</span>
                        </div>
                        <div class="betslip-row" style="margin-bottom: 0.5rem;">
                            <span>Monto Total:</span>
                            <span style="font-weight: 600;">${totalSimplesStake.toFixed(2)} Fichas</span>
                        </div>
                        <div class="betslip-row betslip-payout" style="margin-bottom: 1rem;">
                            <span>Retorno Total Max:</span>
                            <span>${totalSimplesPayout.toFixed(2)}</span>
                        </div>
                    </div>
                    
                    <div class="betslip-actions">
                        <button type="button" class="btn-clear" onclick="clearBetSlip()">Limpiar</button>
                        <button type="submit" class="filter-btn active" id="betslip-submit-btn">Apostar Simples</button>
                    </div>
                </form>
            `;
        }

        betSlipContainer.innerHTML = `
            <div class="betslip-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h3 style="margin: 0;">Boleto</h3>
                <div style="display: flex; gap: 0.75rem; align-items: center;">
                    <span class="badge ${betSlipMode === 'COMBINADA' ? 'placed' : 'pending'}">${betSlipMode}</span>
                    <button type="button" onclick="toggleBetslip()" style="background: none; border: none; color: var(--text-soft); cursor: pointer; font-size: 1.2rem; display: flex; align-items: center; justify-content: center; width: 24px; height: 24px; border-radius: 4px;" title="Minimizar">🔽</button>
                </div>
            </div>
            ${tabsHtml}
            <div class="betslip-body">
                ${betSlipMode === 'COMBINADA' ? selectionsHtml + formHtml : formHtml}
            </div>
        `;

        const alertBox = document.getElementById('betslip-alert');
        const submitBtn = document.getElementById('betslip-submit-btn');

        if (betSlipMode === 'COMBINADA') {
            const stakeInput = document.getElementById('betslip-stake');
            const payoutDisplay = document.getElementById('betslip-potential-payout');

            stakeInput.addEventListener('input', (e) => {
                const stake = parseFloat(e.target.value) || 0;
                const payout = stake * totalOdds;
                payoutDisplay.textContent = payout.toFixed(2);
                
                let error = null;
                if (betSlip.length < 2) {
                    error = "Se requieren mínimo 2 selecciones para una Combinada.";
                } else if (hasConflictForAcca) {
                    error = "Tienes opciones excluyentes del mismo mercado.";
                } else if (stake < 10) {
                    error = "Mínimo 10.00 fichas.";
                } else if (payout > 20000) {
                    error = `Excede retorno máx (20000). Max stake: ${(20000/totalOdds).toFixed(2)}`;
                }

                if (error) {
                    alertBox.textContent = error;
                    alertBox.style.display = 'block';
                    submitBtn.disabled = true;
                    submitBtn.style.opacity = '0.5';
                } else {
                    alertBox.style.display = 'none';
                    submitBtn.disabled = false;
                    submitBtn.style.opacity = '1';
                }
            });
            stakeInput.dispatchEvent(new Event('input'));
        } else {
            // Validation for Simples
            let error = null;
            betSlip.forEach(item => {
                if ((item.stake || 0) < 10) error = "Cada apuesta simple debe ser mínimo 10.00 fichas.";
                if ((item.stake || 0) * item.odds > 20000) error = "Una o más apuestas excede el retorno máx.";
            });
            
            if (error) {
                alertBox.textContent = error;
                alertBox.style.display = 'block';
                submitBtn.disabled = true;
                submitBtn.style.opacity = '0.5';
            } else {
                alertBox.style.display = 'none';
                submitBtn.disabled = false;
                submitBtn.style.opacity = '1';
            }
            
            // Add listeners to individual stake inputs
            document.querySelectorAll('.single-stake-input').forEach(input => {
                input.addEventListener('change', (e) => {
                    updateSingleStake(e.target.dataset.id, e.target.value);
                });
                input.addEventListener('keyup', (e) => {
                    // Update on enter or similar
                    updateSingleStake(e.target.dataset.id, e.target.value);
                });
            });
        }
        
        document.getElementById('betslip-form').addEventListener('submit', () => {
            localStorage.removeItem('fairbet_betslip');
        });
    }

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    renderBetSlip();
});
