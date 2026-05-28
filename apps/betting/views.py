from django.shortcuts import render
import uuid
from datetime import datetime, timedelta

def dashboard(request):
    # Mock data following the DBML schema in basededatos.txt
    
    # 1. Usuario & Perfil KYC
    user_id = "e57b322a-cf39-4458-9418-2cfa0d99ba14"
    kyc_profile = {
        "user_id": user_id,
        "username": "Jesus_Senmache",
        "email": "j.senmache@fairbet.pe",
        "dni": "72948102",
        "birth_date": "1998-05-12",
        "status": "VERIFIED", # PENDING/VERIFIED/BLOCKED/SELF_EXCLUDED
        "verified_at": "2026-04-10 14:32:00",
        "daily_limit": 500.00,
        "weekly_limit": 2000.00,
        "monthly_limit": 5000.00,
    }

    # 2. Eventos, Mercados y Selecciones
    events = [
        {
            "id": "f512db20-c207-4e78-bc5a-cb20db91cfb1",
            "name": "Real Madrid vs Manchester City",
            "sport": "Fútbol - Champions League",
            "starts_at": (datetime.now() + timedelta(hours=2)).strftime("%d %b, %H:%M"),
            "status": "LIVE",
            "markets": [
                {
                    "id": "m1",
                    "kind": "1X2",
                    "name": "Resultado del Partido",
                    "selections": [
                        {"id": "s1_1", "name": "Real Madrid", "odds": 2.45},
                        {"id": "s1_x", "name": "Empate", "odds": 3.60},
                        {"id": "s1_2", "name": "Manchester City", "odds": 2.80}
                    ]
                },
                {
                    "id": "m2",
                    "kind": "OU",
                    "name": "Total Goles (Más/Menos 2.5)",
                    "selections": [
                        {"id": "s2_o", "name": "Más 2.5", "odds": 1.75},
                        {"id": "s2_u", "name": "Menos 2.5", "odds": 2.05}
                    ]
                }
            ]
        },
        {
            "id": "f512db20-c207-4e78-bc5a-cb20db91cfb2",
            "name": "Los Angeles Lakers vs Boston Celtics",
            "sport": "Básquetbol - NBA",
            "starts_at": (datetime.now() + timedelta(hours=5)).strftime("%d %b, %H:%M"),
            "status": "SCHEDULED",
            "markets": [
                {
                    "id": "m3",
                    "kind": "1X2",
                    "name": "Ganador del Partido",
                    "selections": [
                        {"id": "s3_1", "name": "Lakers", "odds": 1.95},
                        {"id": "s3_2", "name": "Celtics", "odds": 1.87}
                    ]
                }
            ]
        },
        {
            "id": "f512db20-c207-4e78-bc5a-cb20db91cfb3",
            "name": "Carlos Alcaraz vs Novak Djokovic",
            "sport": "Tenis - Roland Garros",
            "starts_at": (datetime.now() + timedelta(days=1)).strftime("%d %b, %H:%M"),
            "status": "SCHEDULED",
            "markets": [
                {
                    "id": "m4",
                    "kind": "1X2",
                    "name": "Ganador del Partido",
                    "selections": [
                        {"id": "s4_1", "name": "Alcaraz", "odds": 1.65},
                        {"id": "s4_2", "name": "Djokovic", "odds": 2.25}
                    ]
                }
            ]
        }
    ]

    # 3. Transacciones y Asientos Ledger
    ledger = [
        {"id": 1, "tx_id": "tx001", "kind": "DEPOSIT", "account": "USER_WALLET", "amount": 1000.00, "direction": "CREDIT", "date": "2026-05-27 10:00"},
        {"id": 2, "tx_id": "tx001", "kind": "DEPOSIT", "account": "HOUSE", "amount": 1000.00, "direction": "DEBIT", "date": "2026-05-27 10:00"},
        {"id": 3, "tx_id": "tx002", "kind": "BET_PLACEMENT", "account": "USER_WALLET", "amount": 100.00, "direction": "DEBIT", "date": "2026-05-27 15:30"},
        {"id": 4, "tx_id": "tx002", "kind": "BET_PLACEMENT", "account": "PENDING_BETS", "amount": 100.00, "direction": "CREDIT", "date": "2026-05-27 15:30"},
        {"id": 5, "tx_id": "tx003", "kind": "BET_PAYOUT", "account": "PENDING_BETS", "amount": 100.00, "direction": "DEBIT", "date": "2026-05-27 17:15"},
        {"id": 6, "tx_id": "tx003", "kind": "BET_PAYOUT", "account": "USER_WALLET", "amount": 245.00, "direction": "CREDIT", "date": "2026-05-27 17:15"},
        {"id": 7, "tx_id": "tx003", "kind": "BET_PAYOUT", "account": "HOUSE", "amount": 145.00, "direction": "DEBIT", "date": "2026-05-27 17:15"},
    ]

    # 4. Audit Log de Cadena de Hashes (SHA-256 Chain)
    audit_trail = [
        {
            "sequence": 1,
            "event_type": "USER_REGISTRATION",
            "payload": '{"username": "Jesus_Senmache", "dni": "72948102"}',
            "previous_hash": "000000000000000000000000000000000000000000000000000000000000000",
            "hash": "8f4a3e2b9c7d6e5a4f3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1a"
        },
        {
            "sequence": 2,
            "event_type": "KYC_VERIFICATION",
            "payload": '{"status": "VERIFIED", "reviewer": "compliance_bot"}',
            "previous_hash": "8f4a3e2b9c7d6e5a4f3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1a",
            "hash": "4a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1a8f4a3e2b9c7d6e5a4f3b2c1d0e9f"
        },
        {
            "sequence": 3,
            "event_type": "DEPOSIT_LIMITS_SET",
            "payload": '{"daily": 500, "weekly": 2000, "monthly": 5000}',
            "previous_hash": "4a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1a8f4a3e2b9c7d6e5a4f3b2c1d0e9f",
            "hash": "7f6a5b4c3d2e1a8f4a3e2b9c7d6e5a4f3b2c1d0e9f4a7b6c5d4e3f2a1b0c9d8e"
        }
    ]

    # 5. Actividades sospechosas
    suspicious_activities = [
        {
            "id": 1,
            "reason": "Intento de depósito excediendo límite diario",
            "evidence": '{"monto_intento": 600.0, "limite_diario": 500.0}',
            "detected_at": "Hace 2 horas",
            "status": "PENDIENTE"
        },
        {
            "id": 2,
            "reason": "Inicio de sesión desde IP compartida sospechosa",
            "evidence": '{"ip": "190.235.12.8", "coincidencias": ["user_reg_04", "user_reg_09"]}',
            "detected_at": "Hace 1 día",
            "status": "REVISADO"
        }
    ]

    context = {
        "kyc": kyc_profile,
        "events": events,
        "ledger": ledger,
        "audit_trail": audit_trail,
        "suspicious_activities": suspicious_activities,
        "user_balance": 1145.00, # 1000 - 100 + 245
    }
    
    return render(request, "base.html", context)
