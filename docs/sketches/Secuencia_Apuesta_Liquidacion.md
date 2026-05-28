# Secuencia: Apuesta a Liquidación

Este diagrama muestra cómo interactúa el usuario con el sistema al momento de realizar una apuesta y cómo el backend procesa la liquidación automática de los pagos.

```mermaid
sequenceDiagram
    actor User
    participant Frontend
    participant BettingAPI
    participant WalletService
    participant EventService
    participant OpsConsole (Admin)

    %% Fase de Colocación de Apuesta
    User->>Frontend: Selects market & clicks "Place Bet" (wager: $10)
    Frontend->>BettingAPI: POST /api/betting/bets/ {selection, wager}
    BettingAPI->>EventService: Validate selection odds & status
    EventService-->>BettingAPI: Valid (Live or Scheduled)
    BettingAPI->>WalletService: Deduct $10 (BET_PLACEMENT)
    WalletService-->>BettingAPI: Transaction Success
    BettingAPI-->>Frontend: 201 Created (Bet: PENDING)
    Frontend-->>User: Bet placed successfully

    %% Fase de Liquidación (Event Settlement)
    Note over User, OpsConsole: Time passes, event finishes
    OpsConsole (Admin)->>EventService: Finishes event (e.g. Score 2-1)
    EventService->>BettingAPI: Trigger Settlement for Event X (WON selection)
    BettingAPI->>BettingAPI: Find all PENDING bets for selection
    loop For each winning Bet
        BettingAPI->>BettingAPI: Mark bet as WON
        BettingAPI->>WalletService: Credit Payout (BET_PAYOUT)
        WalletService-->>BettingAPI: Transaction Success
    end
    BettingAPI-->>EventService: Settlement Complete
    EventService-->>OpsConsole (Admin): Event closed and payouts done
```
