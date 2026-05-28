# Diagrama ER de la Billetera (Wallet)

El siguiente diagrama de Entidad-Relación describe el modelo de **Partida Doble** (Double-Entry Ledger) utilizado para garantizar la integridad financiera en la casa de apuestas.

```mermaid
erDiagram
    USER ||--|| WALLET : has
    USER {
        uuid id PK
        string username
        string email
    }
    
    TRANSACTION ||--|{ LEDGER_ENTRY : contains
    TRANSACTION }|--|| USER : created_by
    TRANSACTION {
        uuid id PK
        string kind "DEPOSIT | WITHDRAWAL | BET_PLACEMENT | BET_PAYOUT | CASH_OUT"
        string reference "Idempotency key / Reference"
        datetime created_at
    }

    LEDGER_ENTRY {
        uuid id PK
        uuid transaction_id FK
        string account "USER_WALLET | HOUSE_LIABILITY | HOUSE_REVENUE"
        string direction "CREDIT | DEBIT"
        decimal amount
    }
    
    WALLET {
        uuid id PK
        uuid user_id FK
        decimal balance "Calculated sum of credits - debits"
    }

```
